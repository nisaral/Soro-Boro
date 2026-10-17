"""Test for Phase 26-40 adversarial safety, contract aliases, and explainable decision records."""

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.decision import Decision, DecisionKind
from veyra.core.execution_contract import (
    ActionContract,
    ExecutionContract,
    ExecutionRequirements,
    ResolutionContract,
    SideEffectClass,
)
from veyra.core.state import ExecutionState


def test_contract_aliases():
    assert ResolutionContract is ExecutionContract
    assert ActionContract is ExecutionContract
    assert ExecutionRequirements is ExecutionContract


def test_explainable_decision_records():
    act = ExecutableAction(tool="tool_opt", arguments={"q": 1})
    d = Decision.select(
        action=act,
        reason="optimal replica under latency SLA",
        confidence=0.98,
        candidate_rejections={"tool_stale": "freshness 60s exceeds 10s"},
        is_dry_run=True,
    )
    assert d.kind == DecisionKind.SELECT
    assert d.confidence == 0.98
    assert d.is_dry_run is True
    assert "tool_stale" in d.candidate_rejections
    d_dict = d.to_dict()
    assert d_dict["confidence"] == 0.98
    assert d_dict["is_dry_run"] is True


def test_adversarial_side_effect_and_stale_rejection():
    contract = ExecutionContract(
        capability="crm_read",
        max_freshness_sec=10.0,
        side_effect_class=SideEffectClass.READ_ONLY,
        required_permissions=["perm_read"],
        required_state={"tenant": "acme"},
    )
    state = ExecutionState(permissions={"perm_read"}, context={"env_state": {"tenant": "acme"}})

    # Stale candidate
    stale_act = ExecutableAction(tool="stale_t", metadata={"freshness_sec": 45.0, "permissions": ["perm_read"], "idempotent": True})
    valid, reason = contract.validate_candidate(stale_act, state)
    assert not valid
    assert "Freshness contract violated" in reason

    # Mutating candidate
    mutating_act = ExecutableAction(tool="mut_t", metadata={"freshness_sec": 2.0, "side_effect_class": "non_idempotent_mutation", "idempotent": False})
    valid, reason = contract.validate_candidate(mutating_act, state)
    assert not valid
    assert "mutating side-effects" in reason or "idempotency" in reason

    # Wrong tenant
    wrong_tenant_state = ExecutionState(permissions={"perm_read"}, context={"env_state": {"tenant": "other"}})
    valid_act = ExecutableAction(tool="valid_t", metadata={"freshness_sec": 2.0, "permissions": ["perm_read"], "idempotent": True, "side_effect_class": "read_only"})
    valid, reason = contract.validate_candidate(valid_act, wrong_tenant_state)
    assert not valid
    assert "Required state condition failed" in reason

    # Compliant candidate
    valid, reason = contract.validate_candidate(valid_act, state)
    assert valid


def test_baseline_parity_shared_evaluator():
    from veyra.baseline import FairStaticResolutionMiddleware, WeakStaticResolutionMiddleware
    from veyra.core.contract_evaluator import validate_candidate_shared
    from veyra.registry import ToolDefinition, ToolRegistry

    def failing_read():
        raise RuntimeError("read_tool unavailable")

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="read_tool", executable=failing_read, idempotent=True, side_effect_class="read_only"))
    registry.register(ToolDefinition(name="mut_tool", executable=lambda: "mutated!", idempotent=False, side_effect_class="non_idempotent_mutation"))
    registry.register_equivalence("read_tool", ["mut_tool"])  # Malicious/flawed catalog ordering

    state = ExecutionState(permissions=set())

    # Weak static blindly executes mut_tool fallback
    weak = WeakStaticResolutionMiddleware(registry)
    res_weak = weak.call("read_tool", {})
    assert res_weak == "mutated!"

    # Fair static receives the read_only contract, evaluates mut_tool fallback, and rejects it!
    fair = FairStaticResolutionMiddleware(registry)
    with pytest.raises(Exception):
        fair.call("read_tool", {}, idempotent=True, contract=ExecutionContract(capability="read", side_effect_class=SideEffectClass.READ_ONLY, idempotent_required=True))
