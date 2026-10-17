"""Soro-Boro Reference Integration: Stripe Consequential Refund Mutation.

Demonstrates:
1. Stable OperationIdentity mapping.
2. Passing stable idempotency_key to Stripe.
3. Authoritative reconciliation inspecting rich Stripe refund lifecycle states.
4. Handling dropped ACKs, stale replicas, and probe outages.
"""

from __future__ import annotations

import time
from typing import Any

from soro_boro.boundary import TimeoutException, soro_wrap
from soro_boro.identity import OperationIdentity
from soro_boro.lifecycle import (
    ProviderLifecycleState,
    ReconciliationResult,
    SideEffectClass,
    TerminalOutcome,
)


class MockStripeBackend:
    """Mock Stripe API simulating distributed network and replication conditions."""

    def __init__(self):
        self.refunds_by_id: dict[str, dict[str, Any]] = {}
        self.refunds_by_idemp_key: dict[str, dict[str, Any]] = {}
        self.total_mutations_executed: int = 0
        self.duplicate_mutations_count: int = 0

        # Fault injection controls
        self.drop_ack_on_charge: bool = False
        self.simulate_stale_replica: bool = False
        self.simulate_probe_failure: bool = False
        self.network_timeout_on_first_try: bool = False

    def create_refund(
        self,
        charge_id: str,
        amount_cents: int,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Simulates POST /v1/refunds with idempotency key deduplication."""
        # 1. Native Idempotency Check
        if idempotency_key in self.refunds_by_idemp_key:
            # Replaying with same key returns cached original object!
            return self.refunds_by_idemp_key[idempotency_key]

        # 2. Check if this is a duplicate mutation for the same charge
        for existing in self.refunds_by_id.values():
            if existing["charge_id"] == charge_id and existing["amount"] == amount_cents:
                self.duplicate_mutations_count += 1

        self.total_mutations_executed += 1
        refund_id = f"re_{len(self.refunds_by_id) + 1:04d}"
        refund_obj = {
            "id": refund_id,
            "charge_id": charge_id,
            "amount": amount_cents,
            "status": "succeeded",
            "created": int(time.time()),
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
        }
        self.refunds_by_id[refund_id] = refund_obj
        self.refunds_by_idemp_key[idempotency_key] = refund_obj

        # Fault Injection: Network timeout on caller connection AFTER server commit
        if self.drop_ack_on_charge:
            self.drop_ack_on_charge = False  # Trigger once
            raise TimeoutException("504 Gateway Timeout: connection dropped before response received")

        return refund_obj

    def list_refunds_for_charge(self, charge_id: str) -> list[dict[str, Any]]:
        """Simulates Stripe Refund.list(charge=charge_id).
        
        Note: Stripe idempotency keys have NO effect on GET/list requests and cannot
        be queried directly via Refund.list. Reconcilers must inspect metadata op markers.
        """
        if self.simulate_probe_failure:
            raise RuntimeError("500 Internal Server Error: Stripe reconciliation probe failed")

        if self.simulate_stale_replica:
            # Simulates read replica lag where recent writes are not yet visible
            return []

        return [r for r in self.refunds_by_id.values() if r["charge_id"] == charge_id]

    def get_refund_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        """Helper for checking cached items in mock."""
        return self.refunds_by_idemp_key.get(idempotency_key)


def build_stripe_reconciler(
    backend: MockStripeBackend,
    charge_id: str | None = None,
    guarantee_read_after_write: bool = False,
):
    """Factory creating an authoritative Stripe reconciler bound to backend.
    
    Adheres strictly to Stripe documentation:
    1. Reconciles by listing refunds for the specific charge (Refund.list(charge=...)).
    2. Matches the operation intent marker stored in metadata: metadata['soro_op_id'] == op.operation_id.
    3. Avoids Stripe Search API due to indexing latency.
    4. Treats NOT_FOUND as non-authoritative by default due to eventual consistency of read replicas.
    """

    def stripe_reconciler(op: OperationIdentity) -> ReconciliationResult:
        try:
            target_charge_id = charge_id or op.arguments.get("charge_id")
            if not target_charge_id:
                return ReconciliationResult(
                    state=ProviderLifecycleState.UNKNOWN,
                    authoritative=False,
                    error="Cannot reconcile Stripe refund: charge_id missing from operation context",
                )

            # List refunds for this specific charge
            refunds = backend.list_refunds_for_charge(target_charge_id)

            # Match on metadata operation marker
            matched_refund = None
            for r in refunds:
                meta = r.get("metadata") or {}
                if meta.get("soro_op_id") == op.operation_id:
                    matched_refund = r
                    break
                # Fallback to key in metadata if present
                if meta.get("idempotency_key") == op.idempotency_key:
                    matched_refund = r
                    break

            if not matched_refund:
                # Default: NOT_FOUND is non-authoritative unless provider guarantees read-after-write
                is_auth = guarantee_read_after_write and not backend.simulate_stale_replica
                consistency = "strong" if is_auth else "eventual"
                return ReconciliationResult(
                    state=ProviderLifecycleState.NOT_FOUND,
                    authoritative=is_auth,
                    consistency_observed=consistency,
                )

            status = matched_refund.get("status")
            state_map = {
                "succeeded": ProviderLifecycleState.SUCCEEDED,
                "pending": ProviderLifecycleState.PENDING,
                "failed": ProviderLifecycleState.FAILED,
                "requires_action": ProviderLifecycleState.REQUIRES_ACTION,
            }
            return ReconciliationResult(
                state=state_map.get(status, ProviderLifecycleState.UNKNOWN),
                authoritative=True,
                raw_response=matched_refund,
                consistency_observed="strong",
            )
        except Exception as ex:
            return ReconciliationResult(
                state=ProviderLifecycleState.UNKNOWN,
                authoritative=False,
                error=str(ex),
            )

    return stripe_reconciler
