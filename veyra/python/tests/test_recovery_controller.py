"""Tests for Constrained Belief-State Recovery Controller (Directive §1 - §5)."""

from __future__ import annotations

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.recovery_controller import (
    BeliefDistribution,
    ConstrainedBeliefStateRecoveryController,
    HiddenExecutionState,
    RecoveryActionType,
)


def test_initial_belief_formation():
    ctrl = ConstrainedBeliefStateRecoveryController()
    
    # Pre-execution network drop -> NOT_COMMITTED
    b_pre = ctrl.estimator.initial_belief("pre_execution_timeout")
    assert b_pre.p_not_committed >= 0.90

    # Post-commit timeout -> High probability committed, but unknown
    b_timeout = ctrl.estimator.initial_belief("post_commit_timeout", status_code=504)
    assert b_timeout.p_committed >= 0.50
    assert b_timeout.p_in_flight >= 0.20

    # Partial mutation
    b_partial = ctrl.estimator.initial_belief("partial_batch_failure")
    assert b_partial.p_partial >= 0.80


def test_evidence_acquisition_and_safe_recovery():
    ctrl = ConstrainedBeliefStateRecoveryController()
    
    # Contract: Payment charge (Non-idempotent mutation)
    contract = ExecutionContract(
        capability="payment.charge",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )
    action = ExecutableAction(
        tool="charge",
        arguments={"transfer_id": "tx_123", "amount": 50.0},
        executable=lambda **kw: {"status": "ok"},
    )

    # Verification probe reports payment was actually committed
    def probe_verify(**kw):
        return {"committed": True, "count": 1}

    decision = ctrl.decide_recovery(
        failed_action=action,
        failure_type="timeout_after_commit",
        contract=contract,
        status_code=504,
        verification_fn=probe_verify,
    )

    # Controller must acquire evidence, update belief, and select VERIFY without blind replay
    assert decision.evidence_acquired is True
    assert decision.belief_after["COMMITTED"] >= 0.95
    assert decision.action_type == RecoveryActionType.VERIFY
    assert decision.unsafe_probability <= 0.01


def test_ambiguous_state_safe_abstention():
    ctrl = ConstrainedBeliefStateRecoveryController(epsilon_unsafe=0.01)
    
    contract = ExecutionContract(
        capability="legacy.mutation",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )
    action = ExecutableAction(
        tool="legacy_write",
        arguments={"id": "rec_999"},
        executable=lambda **kw: {"status": "ok"},
    )

    # No probe available and no idempotency key on non-idempotent mutation
    decision = ctrl.decide_recovery(
        failed_action=action,
        failure_type="connection_reset",
        contract=contract,
        verification_fn=None,
        supports_idempotency_key=False,
    )

    # Unsafe replay probability exceeds safety epsilon -> DEFER enforced
    assert decision.action_type == RecoveryActionType.DEFER
    assert "DEFER" in decision.reason
    assert decision.target_action is None


def test_idempotency_key_replay_allowed():
    ctrl = ConstrainedBeliefStateRecoveryController(epsilon_unsafe=0.01)
    
    contract = ExecutionContract(
        capability="order.create",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )
    action = ExecutableAction(
        tool="create_order",
        arguments={"order_id": "ord_101"},
        executable=lambda **kw: {"status": "created"},
    )

    decision = ctrl.decide_recovery(
        failed_action=action,
        failure_type="500_internal_error",
        contract=contract,
        idempotency_key="idemp_key_unique_101",
        supports_idempotency_key=True,
    )

    # Idempotency key makes replay safe (P(unsafe) = 0)
    assert decision.action_type == RecoveryActionType.IDEMPOTENCY_REPLAY
    assert decision.unsafe_probability <= 0.01
