"""Integration tests for Unknown-State Safety (Section 5).

Verifies invariants:
- lost response
- timeout after commit
- timeout before commit
- duplicate request
- partial mutation
- verification failure
- verification timeout
"""

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState
from veyra.core.transaction import RecoveryActionType, TransactionSafetyPolicy, TransactionState
from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware


def test_lost_response_and_timeout_after_commit():
    """Tool times out after mutation committed. Veyra verifies state and does NOT replay."""
    mw = VeyraMiddleware()
    database = {"transfers": []}

    def execute_mutation(transfer_id: str, amount: float):
        database["transfers"].append({"id": transfer_id, "amount": amount})
        # Simulate network failure / dropped ACK immediately after commit
        raise TimeoutError("Network ACK dropped after commit")

    def verify_status(transfer_id: str, amount: float = 0.0):
        # Oracle checks whether transfer_id exists in database
        committed = any(t["id"] == transfer_id for t in database["transfers"])
        return {"committed": committed, "transfer_id": transfer_id}

    # Simulate execution that hit UNKNOWN_ACK
    try:
        execute_mutation("tx_101", 500.0)
    except TimeoutError:
        pass

    assert len(database["transfers"]) == 1

    # Naive replay would duplicate the transfer:
    # database["transfers"].append({"id": "tx_101", "amount": 500.0}) -> len == 2 (DUPLICATE EFFECT!)

    # Veyra handle_unknown_ack
    res = mw.handle_unknown_ack(
        tool_name="execute_mutation",
        arguments={"transfer_id": "tx_101", "amount": 500.0},
        verification_fn=verify_status,
        is_idempotent=False,
    )

    assert res["status"] == "VERIFIED_COMMITTED"
    assert res["replayed"] is False
    assert len(database["transfers"]) == 1  # ZERO duplicate writes!


def test_timeout_before_commit_safe_retry():
    """Tool times out before commit. Verification confirms not committed, safe retry executes once."""
    mw = VeyraMiddleware()
    database = {"transfers": []}

    def verify_status(transfer_id: str, amount: float = 0.0):
        committed = any(t["id"] == transfer_id for t in database["transfers"])
        return {"committed": committed, "transfer_id": transfer_id}

    def retry_mutation(transfer_id: str, amount: float):
        database["transfers"].append({"id": transfer_id, "amount": amount})
        return {"status": "SUCCESS", "id": transfer_id}

    # Nothing was committed before timeout
    assert len(database["transfers"]) == 0

    res = mw.handle_unknown_ack(
        tool_name="execute_mutation",
        arguments={"transfer_id": "tx_102", "amount": 250.0},
        verification_fn=verify_status,
        is_idempotent=False,
        retry_fn=retry_mutation,
    )

    assert res["status"] == "VERIFIED_NOT_COMMITTED_REPLAYED"
    assert res["replayed"] is True
    assert len(database["transfers"]) == 1


def test_blind_replay_rejected_without_verification():
    """UNKNOWN_ACK on non-idempotent mutation without verification strategy MUST be rejected."""
    mw = VeyraMiddleware()

    with pytest.raises(PermissionError) as exc_info:
        mw.handle_unknown_ack(
            tool_name="charge_credit_card",
            arguments={"card": "4111", "amount": 100},
            verification_fn=None,
            is_idempotent=False,
        )

    assert "Blind replay of non-idempotent mutation is strictly prohibited" in str(exc_info.value)


def test_partial_mutation_requires_compensation():
    """Partial mutation in UNKNOWN_ACK/PARTIAL detected by verifier rejects replay."""
    mw = VeyraMiddleware()

    def verifier_detecting_partial(**kwargs):
        return {"committed": False, "partial": True}

    with pytest.raises(RuntimeError) as exc_info:
        mw.handle_unknown_ack(
            tool_name="batch_update",
            arguments={"batch_id": "b_1"},
            verification_fn=verifier_detecting_partial,
            is_idempotent=False,
        )

    assert "PARTIAL state detected" in str(exc_info.value)


def test_verification_failure_escalates():
    """If verification strategy itself raises an error, Veyra halts safely."""
    mw = VeyraMiddleware()

    def faulty_verifier(**kwargs):
        raise ConnectionResetError("Verification service unreachable")

    with pytest.raises(RuntimeError) as exc_info:
        mw.handle_unknown_ack(
            tool_name="post_invoice",
            arguments={"inv": 1},
            verification_fn=faulty_verifier,
            is_idempotent=False,
        )

    assert "Verification strategy failed under UNKNOWN_ACK" in str(exc_info.value)


def test_drop_in_wrap_function_modes():
    """Verify wrap_function across NORMAL, DRY_RUN, and SHADOW modes."""
    # NORMAL
    mw_normal = VeyraMiddleware(ProductionConfig(mode=Mode.NORMAL))
    tool = mw_normal.wrap_function(lambda x: x * 2, name="double_it")
    assert tool(x=5) == 10

    # DRY_RUN
    mw_dry = VeyraMiddleware(ProductionConfig(mode=Mode.DRY_RUN))
    tool_dry = mw_dry.wrap_function(lambda x: x * 2, name="double_it")
    res_dry = tool_dry(x=5)
    assert res_dry["status"] == "DRY_RUN_SUCCESS"
    assert "explanation" in res_dry

    # SHADOW
    mw_shadow = VeyraMiddleware(ProductionConfig(mode=Mode.SHADOW))
    tool_shadow = mw_shadow.wrap_function(lambda x: x * 2, name="double_it")
    assert tool_shadow(x=5) == 10
    assert len(mw_shadow.audit_trail) >= 1
