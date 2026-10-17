"""Unit tests for Phase 60 (Transaction Safety) and Phase 61/62 (Production Layer)."""

from __future__ import annotations

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState
from veyra.core.transaction import RecoveryActionType, TransactionSafetyPolicy, TransactionState
from veyra.production.production_layer import ProductionConfig, VeyraMiddleware


def test_transaction_safety_unknown_ack():
    policy = TransactionSafetyPolicy()
    contract = ExecutionContract(
        capability="payment",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )
    # Mutation replay without verification must be rejected
    act_mutation = ExecutableAction(tool="pay_post", metadata={"idempotent": False})
    safe, act_type, reason = policy.evaluate_transition(TransactionState.UNKNOWN_ACK, act_mutation, contract)
    assert not safe
    assert act_type == RecoveryActionType.BLIND_RETRY
    assert "UNSAFE REPLAY REJECTED" in reason

    # Verification tool in UNKNOWN_ACK must be allowed
    act_verify = ExecutableAction(tool="pay_status", metadata={"is_verification_tool": True, "idempotent": True})
    safe, act_type, _ = policy.evaluate_transition(TransactionState.UNKNOWN_ACK, act_verify, contract)
    assert safe
    assert act_type == RecoveryActionType.VERIFY


def test_transaction_safety_partial_mutation():
    policy = TransactionSafetyPolicy()
    contract = ExecutionContract(
        capability="db",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )
    # Blind retry on partial mutation rejected
    act_retry = ExecutableAction(tool="db_commit", metadata={"idempotent": False})
    safe, act_type, _ = policy.evaluate_transition(TransactionState.PARTIAL, act_retry, contract)
    assert not safe
    assert act_type == RecoveryActionType.BLIND_RETRY

    # Compensation action allowed
    act_rollback = ExecutableAction(tool="db_rollback", metadata={"is_compensating_action": True})
    safe, act_type, _ = policy.evaluate_transition(TransactionState.PARTIAL, act_rollback, contract)
    assert safe
    assert act_type == RecoveryActionType.COMPENSATE


def test_production_dry_run_and_shadow():
    mw = VeyraMiddleware()
    contract = ExecutionContract(capability="search", side_effect_class=SideEffectClass.READ_ONLY)
    state = ExecutionState()
    proposal = ExecutableAction(tool="search_v1", metadata={"capability": "search", "side_effect_class": "read_only"})

    # Dry run
    decision = mw.resolve_action(proposal, [], contract, state, dry_run=True)
    assert decision.kind == DecisionKind.SELECT
    res = mw.execute_action(decision)
    assert res["status"] == "DRY_RUN_SUCCESS"


def test_production_circuit_breaker_and_audit_trail():
    mw = VeyraMiddleware()
    cb = mw.get_circuit_breaker("flaky_tool")
    assert cb.can_execute()

    for _ in range(5):
        cb.record_failure()
    assert not cb.can_execute()
    assert cb.state == "OPEN"

    # Audit trail check
    contract = ExecutionContract(capability="read", side_effect_class=SideEffectClass.READ_ONLY)
    state = ExecutionState()
    prop = ExecutableAction(tool="flaky_tool", metadata={"capability": "read", "side_effect_class": "read_only"})
    replica = ExecutableAction(tool="healthy_tool", metadata={"capability": "read", "side_effect_class": "read_only"})

    dec = mw.resolve_action(prop, [replica], contract, state)
    assert dec.kind == DecisionKind.FALLBACK
    assert dec.action.tool == "healthy_tool"
    assert len(mw.audit_trail) >= 1
    assert "entry_hash" in mw.audit_trail[-1]
