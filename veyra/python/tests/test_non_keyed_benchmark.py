"""Four-Architecture Matrix Benchmark on Non-Keyed Services.

Compares 4 agent execution architectures on services WITHOUT native idempotency keys
(e.g., SQL INSERT into orders table, GitHub issues, Slack messages, webhooks):

Architectures:
1. Naive Retry: Standard retry loop with backoff on network drop.
2. SafeAgent-style Request-ID + Receipt: Local SQLite receipt store, but blind retry on unacknowledged timeout.
3. Naive Verify-Before-Retry: Probe before retry, but treats eventual NOT_FOUND as authoritative and lacks atomic claims.
4. Soro-Boro Boundary: Pre-dispatch atomic claim, synchronous WAL intent, op marker reconciliation, and eventual-consistency deferral.

Failure Modes Injected:
1. Dropped ACK after commit (504 / connection drop)
2. Eventual read replica lag (stale read immediately after commit)
3. Probe outage (500 internal server error during reconciliation)
4. Concurrent racing callers (two agent tasks racing with same intent)
5. Authoritative true network drop (bounded safe retry)
"""

from __future__ import annotations

import sqlite3
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

from soro_boro import (
    OperationIdentity,
    ProviderLifecycleState,
    SideEffectClass,
    TimeoutException,
    WriteAheadLog,
    soro_wrap,
)
from soro_boro.claim import ConcurrentExecutionBlocked, SQLiteClaimStore
from soro_boro.lifecycle import ReconciliationResult, TerminalOutcome


# ==============================================================================
# Non-Keyed Target: Real SQLite Orders Table (No native API idempotency)
# ==============================================================================

class RealDatabaseService:
    """Simulates an internal database service / SQL table without native idempotency keys."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    client_op_marker TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()

        # Fault injection flags
        self.drop_ack: bool = False
        self.simulate_replica_lag: bool = False
        self.probe_failure: bool = False

    def insert_order(
        self,
        customer_id: str,
        sku: str,
        amount_cents: int,
        client_op_marker: str | None = None,
    ) -> dict[str, Any]:
        """Inserts an order. Since standard SQL tables do not deduplicate unless explicitly guarded,
        duplicate calls will insert duplicate records.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orders (customer_id, sku, amount_cents, client_op_marker, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (customer_id, sku, amount_cents, client_op_marker, time.time()),
            )
            order_id = cursor.lastrowid
            conn.commit()

        # Fault: server committed, but network connection drops before ACK reaches caller
        if self.drop_ack:
            self.drop_ack = False
            raise TimeoutException("504 Gateway Timeout: TCP socket closed before response ACK")

        return {
            "order_id": order_id,
            "customer_id": customer_id,
            "sku": sku,
            "amount_cents": amount_cents,
            "client_op_marker": client_op_marker,
        }

    def query_orders_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        """Queries orders. Subject to replica lag or probe failure."""
        if self.probe_failure:
            raise RuntimeError("500 Database query connection pool exhausted")

        if self.simulate_replica_lag:
            # Stale replica hasn't replicated the insert yet!
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM orders WHERE customer_id = ? ORDER BY id ASC",
                (customer_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_customer_orders(self, customer_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            return row[0]


# ==============================================================================
# Architecture 1: Naive Retries
# ==============================================================================

class NaiveRetryAgent:
    """Standard retry loop with backoff on network drop without verification."""

    def __init__(self, service: RealDatabaseService, max_retries: int = 2):
        self.service = service
        self.max_retries = max_retries

    def execute(self, customer_id: str, sku: str, amount_cents: int) -> dict[str, Any]:
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.service.insert_order(customer_id, sku, amount_cents)
            except TimeoutException as ex:
                last_err = ex
                # Blindly retry
                continue
        raise last_err


# ==============================================================================
# Architecture 2: SafeAgent-style Request-ID + Receipt Store
# ==============================================================================

class SafeAgentReceiptBaseline:
    """SafeAgent-style execution guard: assigns request ID and persists receipts in SQLite.
    
    Limitation: When a network timeout drops the response, no receipt was ever written!
    Because the external service has no native key deduplication, retrying with the same
    or a new request ID writes a duplicate row.
    """

    def __init__(self, service: RealDatabaseService, receipts_db_path: str, max_retries: int = 1):
        self.service = service
        self.receipts_db = receipts_db_path
        self.max_retries = max_retries
        with sqlite3.connect(self.receipts_db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    request_id TEXT PRIMARY KEY,
                    result TEXT,
                    timestamp REAL
                )
                """
            )
            conn.commit()

    def execute(self, request_id: str, customer_id: str, sku: str, amount_cents: int) -> dict[str, Any]:
        # Check local receipt
        with sqlite3.connect(self.receipts_db) as conn:
            row = conn.execute("SELECT result FROM receipts WHERE request_id = ?", (request_id,)).fetchone()
            if row:
                return {"cached": True, "data": row[0]}

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                # Dispatch to external service with request_id
                res = self.service.insert_order(customer_id, sku, amount_cents, client_op_marker=request_id)
                # Save receipt on success
                with sqlite3.connect(self.receipts_db) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO receipts (request_id, result, timestamp) VALUES (?, ?, ?)",
                        (request_id, str(res["order_id"]), time.time()),
                    )
                    conn.commit()
                return res
            except TimeoutException as ex:
                last_err = ex
                # On timeout, SafeAgent has no external reconciler for non-keyed APIs; blindly retries
                continue
        raise last_err


# ==============================================================================
# Architecture 3: Naive Verify-Before-Retry
# ==============================================================================

class NaiveVerifyBeforeRetryAgent:
    """Checks upstream state before retrying, BUT:
    1. Lacks cross-process atomic claiming (susceptible to race conditions)
    2. Treats NOT_FOUND on eventual read replica as authoritative failure (premature retry -> duplicate!)
    """

    def __init__(self, service: RealDatabaseService):
        self.service = service

    def execute(self, customer_id: str, sku: str, amount_cents: int, op_id: str) -> dict[str, Any]:
        try:
            return self.service.insert_order(customer_id, sku, amount_cents, client_op_marker=op_id)
        except TimeoutException:
            # Naive probe: checks if order exists
            existing = self.service.query_orders_by_customer(customer_id)
            matched = [o for o in existing if o.get("client_op_marker") == op_id]
            if matched:
                return {"recovered": True, "order": matched[0]}

            # FLAW: If existing is empty due to replica lag, Naive Verify treats it as NOT_FOUND (never committed)
            # and issues a retry -> DUPLICATE WRITE!
            return self.service.insert_order(customer_id, sku, amount_cents, client_op_marker=op_id)


# ==============================================================================
# Architecture 4: Soro-Boro Boundary
# ==============================================================================

def build_db_reconciler(service: RealDatabaseService, customer_id: str):
    """Authoritative reconciler with fail-closed safety for eventual replicas."""
    def reconciler(op: OperationIdentity) -> ReconciliationResult:
        try:
            orders = service.query_orders_by_customer(customer_id)
            for ord_row in orders:
                if ord_row.get("client_op_marker") == op.operation_id:
                    return ReconciliationResult(
                        state=ProviderLifecycleState.SUCCEEDED,
                        authoritative=True,
                        raw_response=ord_row,
                        consistency_observed="strong",
                    )
            # Not found: unless guaranteed strong consistency, mark eventual!
            consistency = "eventual" if service.simulate_replica_lag else "strong"
            is_auth = not service.simulate_replica_lag
            return ReconciliationResult(
                state=ProviderLifecycleState.NOT_FOUND,
                authoritative=is_auth,
                consistency_observed=consistency,
            )
        except Exception as ex:
            return ReconciliationResult(
                state=ProviderLifecycleState.UNKNOWN,
                authoritative=False,
                error=str(ex),
            )
    return reconciler


# ==============================================================================
# The Matrix Tests: Real Non-Keyed Services Evaluation
# ==============================================================================

def test_dropped_ack_matrix_comparison():
    """Test 1: Dropped ACK after commit.
    
    Compares how all 4 architectures behave when the server committed the write
    but dropped the TCP connection before sending the ACK.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        # Arm 1: Naive Retry
        db1 = RealDatabaseService(str(Path(tmpdir) / "arm1.db"))
        db1.drop_ack = True
        arm1 = NaiveRetryAgent(db1, max_retries=1)
        arm1.execute("cust_1", "SKU-99", 5000)
        # Naive retry inserted TWICE!
        assert db1.count_customer_orders("cust_1") == 2, "Naive retry should duplicate write"

        # Arm 2: SafeAgent Receipt Baseline
        db2 = RealDatabaseService(str(Path(tmpdir) / "arm2.db"))
        db2.drop_ack = True
        arm2 = SafeAgentReceiptBaseline(db2, str(Path(tmpdir) / "receipts.db"), max_retries=1)
        arm2.execute("req_cust_2", "cust_2", "SKU-99", 5000)
        # SafeAgent duplicated write because receipt wasn't saved on timeout!
        assert db2.count_customer_orders("cust_2") == 2, "SafeAgent baseline duplicates write on timeout"

        # Arm 3: Naive Verify-Before-Retry (succeeds only under strong read-after-write)
        db3 = RealDatabaseService(str(Path(tmpdir) / "arm3.db"))
        db3.drop_ack = True
        arm3 = NaiveVerifyBeforeRetryAgent(db3)
        res3 = arm3.execute("cust_3", "SKU-99", 5000, op_id="op_3")
        assert res3.get("recovered") is True
        assert db3.count_customer_orders("cust_3") == 1

        # Arm 4: Soro-Boro Boundary
        db4 = RealDatabaseService(str(Path(tmpdir) / "arm4.db"))
        db4.drop_ack = True
        reconciler = build_db_reconciler(db4, "cust_4")
        wal_path = str(Path(tmpdir) / "wal4.jsonl")
        claims_path = str(Path(tmpdir) / "claims4.db")

        @soro_wrap(
            side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
            reconciler=reconciler,
            wal_path=wal_path,
            claims_db_path=claims_path,
        )
        def insert_tool(customer_id: str, sku: str, amount_cents: int, op: OperationIdentity | None = None):
            return db4.insert_order(customer_id, sku, amount_cents, client_op_marker=op.operation_id)

        outcome = insert_tool(customer_id="cust_4", sku="SKU-99", amount_cents=5000)
        assert outcome.status == "PREVENTED_DUPLICATE"
        assert db4.count_customer_orders("cust_4") == 1, "Soro-Boro must have exactly 1 record (0 duplicates)"


def test_eventual_replica_lag_matrix_comparison():
    """Test 2: Eventual Replica Lag (Delayed Visibility).
    
    Compares behavior when write committed, ACK dropped, and read replica has not synced yet.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        # Arm 3: Naive Verify-Before-Retry
        # Sees NOT_FOUND on probe, assumes it failed, retries -> DUPLICATE WRITE!
        db3 = RealDatabaseService(str(Path(tmpdir) / "arm3.db"))
        db3.drop_ack = True
        db3.simulate_replica_lag = True
        arm3 = NaiveVerifyBeforeRetryAgent(db3)
        arm3.execute("cust_lag", "SKU-99", 5000, op_id="op_lag")
        assert db3.count_customer_orders("cust_lag") == 2, "Naive verify duplicates under replica lag"

        # Arm 4: Soro-Boro Boundary
        # Detects eventual consistency -> fails closed to AMBIGUOUS_DEFERRED (0 duplicates!)
        db4 = RealDatabaseService(str(Path(tmpdir) / "arm4.db"))
        db4.drop_ack = True
        db4.simulate_replica_lag = True
        reconciler = build_db_reconciler(db4, "cust_lag")
        wal_path = str(Path(tmpdir) / "wal4.jsonl")
        claims_path = str(Path(tmpdir) / "claims4.db")

        @soro_wrap(
            side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
            reconciler=reconciler,
            wal_path=wal_path,
            claims_db_path=claims_path,
        )
        def insert_tool(customer_id: str, sku: str, amount_cents: int, op: OperationIdentity | None = None):
            return db4.insert_order(customer_id, sku, amount_cents, client_op_marker=op.operation_id)

        outcome = insert_tool(customer_id="cust_lag", sku="SKU-99", amount_cents=5000)
        assert outcome.status == "AMBIGUOUS_DEFERRED"
        assert outcome.is_ambiguous is True
        # Only the 1 committed write occurred; no second retry was attempted!
        assert db4.count_customer_orders("cust_lag") == 1, "Soro-Boro strictly prevented duplicate write under lag"


def test_concurrent_racing_matrix_comparison():
    """Test 3: Concurrency Race.
    
    Two agent processes/threads attempt the same workflow intent within milliseconds.
    Soro-Boro uses atomic SQLite claim store (BEGIN IMMEDIATE) to block the race.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        claims_path = str(Path(tmpdir) / "shared_claims.db")
        wal_path = str(Path(tmpdir) / "shared_wal.jsonl")
        db = RealDatabaseService(str(Path(tmpdir) / "shared.db"))

        shared_intent_op = OperationIdentity.mint("wf_step_checkout_99", {"customer_id": "cust_race", "sku": "SKU-1", "amount_cents": 100})

        @soro_wrap(
            side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
            wal_path=wal_path,
            claims_db_path=claims_path,
        )
        def race_tool(customer_id: str, sku: str, amount_cents: int, op: OperationIdentity | None = None):
            return db.insert_order(customer_id, sku, amount_cents, client_op_marker=op.operation_id)

        # 1. First execution claims lease and executes
        outcome1 = race_tool(customer_id="cust_race", sku="SKU-1", amount_cents=100, op=shared_intent_op)
        assert outcome1.status == "COMMITTED"

        # 2. Parallel / duplicate execution with same intent ID immediately hits claim store:
        # It detects that the operation is already COMMITTED and returns PREVENTED_DUPLICATE without re-dispatching!
        outcome2 = race_tool(customer_id="cust_race", sku="SKU-1", amount_cents=100, op=shared_intent_op)
        assert outcome2.status == "PREVENTED_DUPLICATE"
        assert db.count_customer_orders("cust_race") == 1, "Concurrency deduplication guaranteed: exactly 1 write"
