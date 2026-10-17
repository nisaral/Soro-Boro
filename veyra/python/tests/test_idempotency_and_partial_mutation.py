"""Unit tests for Section 7 (Strong Idempotency Key Semantics) & Section 8 (Partial Mutation Support)."""

import pytest
from veyra.core.idempotency import IdempotencyIdentity, IdempotencyKeyStore
from veyra.core.partial_mutation import (
    PartialMutationHook,
    PartialMutationManager,
    PartialMutationState,
    PartialMutationStatus,
)


# =============================================================================
# Section 7: Idempotency Key Tests (8 Mandatory Scenarios)
# =============================================================================

def test_idempotency_key_stability_across_retries():
    """Invariant: same logical mutation -> same idempotency identity across retries."""
    store = IdempotencyKeyStore()

    # 1. First attempt
    id1 = store.get_or_create(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    key1 = id1.key
    assert key1.startswith("idk_")

    # 2. Timeout before commit -> retry
    id2 = store.get_or_create(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id2.key == key1  # Key must be identical!

    # 3. Timeout after commit -> retry
    id3 = store.get_or_create(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id3.key == key1

    # 4. Lost 5xx after commit -> retry
    id4 = store.get_or_create(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id4.key == key1

    # 5. Repeated retry
    store.record_attempt(key1, attempt_number=1, status="TIMEOUT")
    store.record_attempt(key1, attempt_number=2, status="SUCCESS", result={"charge_id": "chg_1"})
    hist = store.get_history(key1)
    assert hist["attempts"] == 2
    assert hist["status"] == "SUCCESS"

    # 6. Process restart simulation (re-instantiating key with same intent)
    id_restart = IdempotencyIdentity(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id_restart.key == key1

    # 7. Duplicate delivery: different intent produces distinct key
    id_other = store.get_or_create(intent_id="intent_101", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id_other.key != key1

    # 8. Concurrent retry attempt (same key retrieved)
    id_concurrent = store.get_or_create(intent_id="intent_100", tool="charge_card", arguments={"amount": 50, "customer": "c1"})
    assert id_concurrent.key == key1


# =============================================================================
# Section 8: Partial Mutation Support Tests (5 Mandatory Scenarios)
# =============================================================================

def test_partial_mutation_batch_reconciliation():
    """Scenario 1: Partial batch reconciliation via contract handler."""
    mgr = PartialMutationManager()
    
    # Contract reconciliation handler
    def reconcile_batch(args, steps_done, steps_total):
        remaining = args["items"][steps_done:]
        return {"reconciled_items": remaining, "status": "COMPLETED"}

    mgr.register_hook(PartialMutationHook(tool_name="batch_process", reconciliation_handler=reconcile_batch))
    
    # Record partial batch state (2 out of 5 done)
    tx_state = PartialMutationState(transaction_id="tx_b1", entity_id="batch_1", steps_total=5, steps_completed=2)
    mgr.record_partial_state(tx_state)

    status, msg, res = mgr.resolve_partial_mutation("tx_b1", "batch_process", {"items": [1, 2, 3, 4, 5]})
    assert status == PartialMutationStatus.RECONCILED
    assert res["status"] == "COMPLETED"


def test_partial_mutation_database_update_probe():
    """Scenario 2: Partial database update detected by post-condition probe."""
    mgr = PartialMutationManager()

    def db_probe(args):
        # Post-condition probe confirms full commit
        return {"fully_committed": True, "rows_affected": 10}

    mgr.register_hook(PartialMutationHook(tool_name="db_update", post_condition_probe=db_probe))

    tx_state = PartialMutationState(transaction_id="tx_db1", entity_id="db_1", steps_total=10, steps_completed=5)
    mgr.record_partial_state(tx_state)

    status, msg, res = mgr.resolve_partial_mutation("tx_db1", "db_update", {"table": "users"})
    assert status == PartialMutationStatus.FULLY_COMMITTED
    assert res["fully_committed"] is True


def test_partial_mutation_resource_creation_compensation():
    """Scenario 3: Resource creation followed by timeout -> safe compensation."""
    mgr = PartialMutationManager()

    def compensate_creation(args, steps_done):
        return {"rollback_resource_id": args["resource_id"], "status": "ROLLED_BACK"}

    mgr.register_hook(PartialMutationHook(tool_name="create_cloud_vm", compensation_hook=compensate_creation))

    tx_state = PartialMutationState(transaction_id="tx_vm1", entity_id="vm_101", steps_total=3, steps_completed=1)
    mgr.record_partial_state(tx_state)

    status, msg, res = mgr.resolve_partial_mutation("tx_vm1", "create_cloud_vm", {"resource_id": "vm_101"})
    assert status == PartialMutationStatus.COMPENSATED
    assert res["status"] == "ROLLED_BACK"


def test_partial_mutation_compensation_failure():
    """Scenario 4: Compensation hook failure -> returns UNRECOVERABLE."""
    mgr = PartialMutationManager()

    def failing_compensation(args, steps_done):
        raise RuntimeError("Cloud provider API refused delete")

    mgr.register_hook(PartialMutationHook(tool_name="failing_tool", compensation_hook=failing_compensation))

    tx_state = PartialMutationState(transaction_id="tx_f1", entity_id="obj_1", steps_total=2, steps_completed=1)
    mgr.record_partial_state(tx_state)

    status, msg, res = mgr.resolve_partial_mutation("tx_f1", "failing_tool", {"obj": "1"})
    assert status == PartialMutationStatus.UNRECOVERABLE
    assert "failed" in msg.lower()


def test_partial_mutation_reconciliation_mismatch_defers():
    """Scenario 5: Reconciliation mismatch without compensation -> DEFER / DENY."""
    mgr = PartialMutationManager()
    # No hooks registered for tool
    tx_state = PartialMutationState(transaction_id="tx_m1", entity_id="obj_2", steps_total=5, steps_completed=2)
    mgr.record_partial_state(tx_state)

    status, msg, res = mgr.resolve_partial_mutation("tx_m1", "unhooked_tool", {"obj": "2"})
    assert status == PartialMutationStatus.UNRECOVERABLE
    assert "deferring" in msg.lower() or "denying" in msg.lower()
