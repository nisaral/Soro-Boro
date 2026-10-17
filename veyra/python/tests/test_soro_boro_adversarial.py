"""Adversarial Benchmark & Test Suite for Soro-Boro.

Evaluates 4 architectures under 5 distributed systems failure modes:
1. Dropped ACK on committed write (504 Timeout)
2. Delayed visibility on eventual read replica
3. Probe outage (500 on verification probe)
4. Authoritative Not Found with safe bounded retry
5. Write-Ahead Log crash recovery (uncommitted in-flight intent)
6. Real GitHub Issue mutation recovery
"""

import tempfile
from pathlib import Path

import pytest
from soro_boro import (
    OperationIdentity,
    ProviderLifecycleState,
    SideEffectClass,
    SoroBoundary,
    TimeoutException,
    WriteAheadLog,
    soro_wrap,
)
from soro_boro.integrations.github_issue import (
    MockGitHubBackend,
    build_github_reconciler,
)
from soro_boro.integrations.stripe_refund import (
    MockStripeBackend,
    build_stripe_reconciler,
)


def test_dropped_ack_prevents_duplicate_charge():
    """Scenario 1: Server commits the refund, but network timeout drops ACK on caller.
    
    Naive agent: Retries and creates a second refund (duplicate effect!).
    Soro-Boro: Traps UNKNOWN_ACK, reconciles upstream state via metadata marker, returns PREVENTED_DUPLICATE.
    """
    backend = MockStripeBackend()
    backend.drop_ack_on_charge = True  # Commits, then raises TimeoutException
    reconciler = build_stripe_reconciler(backend)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        reconciler=reconciler,
        wal_path=wal_path,
    )
    def refund_tool(charge_id: str, amount: int, op: OperationIdentity | None = None):
        return backend.create_refund(
            charge_id=charge_id,
            amount_cents=amount,
            idempotency_key=op.idempotency_key,
            metadata={"soro_op_id": op.operation_id},
        )

    # First invocation: triggers timeout on connection drop
    outcome = refund_tool(charge_id="ch_1001", amount=14999)

    assert outcome.status == "PREVENTED_DUPLICATE"
    assert outcome.provider_state == ProviderLifecycleState.SUCCEEDED
    assert outcome.data["id"] == "re_0001"
    assert backend.total_mutations_executed == 1
    assert backend.duplicate_mutations_count == 0  # Zero duplicates!


def test_stale_replica_causes_safe_deferral():
    """Scenario 2: Read replica is eventual and hasn't synced the commit yet.
    
    Naive verify-before-retry: Sees NOT_FOUND on probe, assumes action failed, retries -> DUPLICATE!
    Soro-Boro: Detects eventual consistency -> fails closed to AMBIGUOUS_DEFERRED.
    """
    backend = MockStripeBackend()
    backend.drop_ack_on_charge = True
    backend.simulate_stale_replica = True  # Probe returns [] due to replica delay!
    reconciler = build_stripe_reconciler(backend)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        reconciler=reconciler,
        wal_path=wal_path,
    )
    def refund_tool(charge_id: str, amount: int, op: OperationIdentity | None = None):
        return backend.create_refund(
            charge_id=charge_id,
            amount_cents=amount,
            idempotency_key=op.idempotency_key,
            metadata={"soro_op_id": op.operation_id},
        )

    outcome = refund_tool(charge_id="ch_1002", amount=5000)

    # Must NOT blind-retry on eventual replica! Safe deferral required!
    assert outcome.status == "AMBIGUOUS_DEFERRED"
    assert outcome.is_ambiguous
    assert backend.duplicate_mutations_count == 0  # Safe: no duplicate created!


def test_probe_failure_fails_closed():
    """Scenario 3: Reconciliation probe itself encounters a 500 internal server error.
    
    Soro-Boro: Fails closed to AMBIGUOUS_DEFERRED without retrying blindly.
    """
    backend = MockStripeBackend()
    backend.drop_ack_on_charge = True
    backend.simulate_probe_failure = True
    reconciler = build_stripe_reconciler(backend)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        reconciler=reconciler,
        wal_path=wal_path,
    )
    def refund_tool(charge_id: str, amount: int, op: OperationIdentity | None = None):
        return backend.create_refund(
            charge_id=charge_id,
            amount_cents=amount,
            idempotency_key=op.idempotency_key,
            metadata={"soro_op_id": op.operation_id},
        )

    outcome = refund_tool(charge_id="ch_1003", amount=2500)

    assert outcome.status == "AMBIGUOUS_DEFERRED"
    assert backend.duplicate_mutations_count == 0


def test_authoritative_not_found_safely_retries():
    """Scenario 4: Request never reached backend (true network drop before execution).
    
    Authoritative query confirms NOT_FOUND with strong consistency.
    Soro-Boro: Performs bounded retry WITH THE EXACT SAME IDEMPOTENCY KEY and succeeds.
    """
    backend = MockStripeBackend()
    attempts_seen = 0

    def unreliable_dispatch(charge_id: str, amount: int, op: OperationIdentity | None = None):
        nonlocal attempts_seen
        attempts_seen += 1
        if attempts_seen == 1:
            raise TimeoutException("Connection dropped before packet reached gateway")
        return backend.create_refund(
            charge_id=charge_id,
            amount_cents=amount,
            idempotency_key=op.idempotency_key,
            metadata={"soro_op_id": op.operation_id},
        )

    reconciler = build_stripe_reconciler(backend, guarantee_read_after_write=True)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    wrapped = soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        reconciler=reconciler,
        max_retries=1,
        wal_path=wal_path,
    )(unreliable_dispatch)

    outcome = wrapped(charge_id="ch_1004", amount=7500)

    assert outcome.status == "COMMITTED"
    assert outcome.attempts == 2
    assert backend.total_mutations_executed == 1
    assert backend.duplicate_mutations_count == 0


def test_wal_durability_and_crash_recovery():
    """Scenario 5: Write-Ahead Intent is synchronously flushed before tool call.
    
    If the process dies before OUTCOME is recorded, startup scan detects orphaned intent.
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    wal = WriteAheadLog(wal_path)

    # 1. Normal complete transaction
    wal.record_intent("op_1", "key_1", "refund", {"amount": 100})
    wal.record_outcome("op_1", "key_1", "refund", "COMMITTED", "SUCCEEDED", "ok")

    # 2. Simulated crash: Intent flushed, but process killed before outcome
    wal.record_intent("op_2_crashed", "key_2", "refund", {"amount": 500})

    # 3. On reboot, new WAL instance inspects log
    fresh_wal = WriteAheadLog(wal_path)
    recoverable, expired = fresh_wal.find_orphaned_intents()

    assert len(recoverable) == 1
    assert len(expired) == 0
    assert recoverable[0].operation_id == "op_2_crashed"
    assert recoverable[0].idempotency_key == "key_2"


def test_github_issue_duplicate_prevention():
    """Scenario 6: GitHub issue creation with network timeout."""
    backend = MockGitHubBackend()
    backend.drop_ack = True
    reconciler = build_github_reconciler(backend, repo="org/infra")

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        wal_path = tf.name

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        reconciler=reconciler,
        wal_path=wal_path,
    )
    def create_incident(title: str, body: str, op: OperationIdentity | None = None):
        return backend.create_issue(
            repo="org/infra",
            title=title,
            body=body,
            op_id=op.operation_id,
        )

    outcome = create_incident(title="Outage in us-east-1", body="Cluster CPU at 99%")

    assert outcome.status == "PREVENTED_DUPLICATE"
    assert outcome.data["title"] == "Outage in us-east-1"
    assert len(backend.issues) == 1
    assert backend.duplicate_issues_count == 0


def test_loop_guard_blocks_duplicate_llm_turns():
    """Scenario 7: LLM gets stuck in a loop and calls the same tool twice across turns.
    
    In loop_guard mode (default), even with no explicit intent_id provided,
    the second call is blocked and returns PREVENTED_DUPLICATE.
    """
    call_count = 0

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        dedupe_mode="loop_guard",
        window_sec=120.0,
    )
    def send_slack_alert(channel: str, message: str):
        nonlocal call_count
        call_count += 1
        return {"status": "sent", "channel": channel, "call_num": call_count}

    # Turn 1: LLM proposes action without intent_id
    res1 = send_slack_alert(channel="#prod-alerts", message="High latency detected")
    assert res1.status == "COMMITTED"
    assert res1.data["call_num"] == 1
    assert call_count == 1

    # Turn 2: LLM repeats the exact same call (no intent_id passed)
    res2 = send_slack_alert(channel="#prod-alerts", message="High latency detected")
    assert res2.status == "PREVENTED_DUPLICATE"
    assert res2.data["call_num"] == 1  # Returns cached result from turn 1
    assert call_count == 1  # Underlying tool was NOT re-dispatched!


def test_explicit_intent_allows_separate_steps():
    """Scenario 8: In explicit_intent mode, calls without intent_id are treated as separate steps."""
    call_count = 0

    @soro_wrap(
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        dedupe_mode="explicit_intent",
    )
    def partial_charge(order_id: str, amount: int):
        nonlocal call_count
        call_count += 1
        return {"status": "charged", "order_id": order_id, "amount": amount, "num": call_count}

    res1 = partial_charge(order_id="ord_99", amount=10)
    assert res1.status == "COMMITTED"
    assert call_count == 1

    # Second distinct step with identical parameters is permitted in explicit_intent mode
    res2 = partial_charge(order_id="ord_99", amount=10)
    assert res2.status == "COMMITTED"
    assert call_count == 2
