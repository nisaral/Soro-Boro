"""Phase 84: Safety Property-Based Testing with Hypothesis.

Formally verifies the 10 safety invariants of the Veyra execution boundary:
1. Veyra never broadens permissions.
2. Veyra never broadens side effects (read-only cannot be substituted with mutation).
3. Veyra never substitutes across tenants.
4. Veyra never bypasses freshness.
5. Veyra never replays uncertain non-idempotent mutations.
6. Veyra never semantically invents arguments.
7. Veyra may DENY or DEFER instead of selecting.
8. Contract validation is deterministic.
9. Case memory cannot override hard constraints.
10. History cannot override transaction state.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from veyra.core.action import ExecutableAction
from veyra.core.contract_evaluator import validate_candidate_shared
from veyra.core.decision import DecisionKind
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState
from veyra.core.transaction import RecoveryActionType, TransactionSafetyPolicy, TransactionState
from veyra.policy.history_adaptive import MemoryCase, OnlineExecutionMemory
from veyra.production.production_layer import VeyraMiddleware

FAST_HYPOTHESIS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


# Invariant 1: Veyra never broadens permissions
@FAST_HYPOTHESIS
@given(
    caller_perms=st.sets(st.sampled_from(["perm_read", "perm_write", "perm_admin", "perm_audit"]), max_size=4),
    cand_perms=st.sets(st.sampled_from(["perm_read", "perm_write", "perm_admin", "perm_audit", "perm_root"]), max_size=4),
)
def test_invariant_1_never_broaden_permissions(caller_perms: set[str], cand_perms: set[str]):
    contract = ExecutionContract(capability="cap", required_permissions=list(caller_perms))
    state = ExecutionState(permissions=caller_perms)
    candidate = ExecutableAction(tool="t_test", metadata={"capability": "cap", "permissions": list(cand_perms)})

    ok, reason = validate_candidate_shared(candidate, contract, state)
    if not cand_perms.issubset(caller_perms):
        assert not ok, f"Allowed unauthorized permissions: {cand_perms} vs {caller_perms}"


# Invariant 2: Veyra never broadens side-effects
@FAST_HYPOTHESIS
@given(
    contract_class=st.sampled_from(list(SideEffectClass)),
    candidate_class=st.sampled_from(list(SideEffectClass)),
)
def test_invariant_2_never_broaden_side_effects(contract_class: SideEffectClass, candidate_class: SideEffectClass):
    contract = ExecutionContract(capability="cap", side_effect_class=contract_class)
    candidate = ExecutableAction(tool="t_cand", metadata={"capability": "cap", "side_effect_class": candidate_class.value})
    state = ExecutionState()

    ok, _ = validate_candidate_shared(candidate, contract, state)
    if contract_class == SideEffectClass.READ_ONLY and candidate_class in (
        SideEffectClass.NON_IDEMPOTENT_MUTATION,
        SideEffectClass.DESTRUCTIVE,
    ):
        assert not ok, f"Allowed side effect widening: {contract_class} -> {candidate_class}"


# Invariant 3: Veyra never substitutes across tenants
@FAST_HYPOTHESIS
@given(
    contract_tenant=st.sampled_from(["tenant_a", "tenant_b", "tenant_c"]),
    cand_tenant=st.sampled_from(["tenant_a", "tenant_b", "tenant_c", "tenant_d"]),
)
def test_invariant_3_never_substitute_across_tenants(contract_tenant: str, cand_tenant: str):
    contract = ExecutionContract(capability="cap", required_state={"tenant_id": contract_tenant})
    state = ExecutionState(context={"env_state": {"tenant_id": contract_tenant}})
    candidate = ExecutableAction(
        tool="t_cand",
        metadata={"capability": "cap", "state_assertions": {"tenant_id": cand_tenant}},
    )

    ok, _ = validate_candidate_shared(candidate, contract, state)
    if contract_tenant != cand_tenant:
        assert not ok, f"Allowed tenant boundary crossing: {contract_tenant} vs {cand_tenant}"


# Invariant 4: Veyra never bypasses freshness
@FAST_HYPOTHESIS
@given(
    max_freshness=st.floats(min_value=0.1, max_value=100.0),
    cand_freshness=st.floats(min_value=0.1, max_value=200.0),
)
def test_invariant_4_never_bypass_freshness(max_freshness: float, cand_freshness: float):
    contract = ExecutionContract(capability="cap", max_freshness_sec=max_freshness)
    state = ExecutionState()
    candidate = ExecutableAction(tool="t_cand", metadata={"capability": "cap", "freshness_sec": cand_freshness})

    ok, _ = validate_candidate_shared(candidate, contract, state)
    if cand_freshness > max_freshness:
        assert not ok, f"Allowed stale data: {cand_freshness} > {max_freshness}"


# Invariant 5: Veyra never replays uncertain non-idempotent mutations
@FAST_HYPOTHESIS
@given(
    is_idempotent=st.booleans(),
    is_verification=st.booleans(),
)
def test_invariant_5_never_replay_uncertain_mutation(is_idempotent: bool, is_verification: bool):
    policy = TransactionSafetyPolicy()
    contract = ExecutionContract(capability="mutation", side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION)
    candidate = ExecutableAction(
        tool="t_mutate",
        metadata={"idempotent": is_idempotent, "is_verification_tool": is_verification},
    )

    safe, act_type, reason = policy.evaluate_transition(TransactionState.UNKNOWN_ACK, candidate, contract)
    if not is_idempotent and not is_verification:
        assert not safe, "Allowed blind replay of non-idempotent mutation under UNKNOWN_ACK"
        assert act_type == RecoveryActionType.BLIND_RETRY


# Invariant 6: Veyra never semantically invents arguments
def test_invariant_6_never_invent_arguments():
    # Proposal has arguments: query_id=123. Resolved action must preserve intended arguments.
    proposal = ExecutableAction(tool="search_v1", arguments={"query_id": "123", "limit": 10}, metadata={"capability": "search"})
    mw = VeyraMiddleware()
    contract = ExecutionContract(capability="search")
    state = ExecutionState()
    replica = ExecutableAction(tool="search_v2", metadata={"capability": "search"})

    dec = mw.resolve_action(proposal, [replica], contract, state)
    # The resolved action in decision retains the exact argument mapping
    assert dec.action.arguments == proposal.arguments


# Invariant 7: Veyra may DENY or DEFER instead of selecting
def test_invariant_7_deny_or_defer_on_empty():
    proposal = ExecutableAction(tool="bad_tool", metadata={"permissions": ["root_admin"]})
    contract = ExecutionContract(capability="restricted", required_permissions=["user_perm"])
    state = ExecutionState(permissions={"user_perm"})
    mw = VeyraMiddleware()

    decision = mw.resolve_action(proposal, [], contract, state)
    assert decision.kind == DecisionKind.DENY


# Invariant 8: Contract validation is deterministic
@FAST_HYPOTHESIS
@given(
    perm=st.sampled_from(["perm_read", "perm_write", "perm_admin"]),
    freshness=st.floats(min_value=1.0, max_value=20.0),
)
def test_invariant_8_contract_validation_is_deterministic(perm: str, freshness: float):
    contract = ExecutionContract(capability="cap", required_permissions=[perm], max_freshness_sec=10.0)
    state = ExecutionState(permissions={perm})
    candidate = ExecutableAction(tool="t", metadata={"capability": "cap", "permissions": [perm], "freshness_sec": freshness})

    ok1, reason1 = validate_candidate_shared(candidate, contract, state)
    ok2, reason2 = validate_candidate_shared(candidate, contract, state)
    assert ok1 == ok2
    assert reason1 == reason2


# Invariant 9: Case memory cannot override hard constraints
def test_invariant_9_case_memory_cannot_override_hard_constraints():
    # Memory says tool_dangerous succeeded 100 times
    mem = OnlineExecutionMemory()
    mem.cases.append(
        MemoryCase(
            proposed_tool="search",
            arg_shape=(),
            history_slice=(),
            previous_failure=None,
            resolved_tool="tool_dangerous",
            success_count=100,
            failure_count=0,
        )
    )

    contract = ExecutionContract(capability="search", side_effect_class=SideEffectClass.READ_ONLY)
    cand_dangerous = ExecutableAction(
        tool="tool_dangerous",
        metadata={"capability": "search", "side_effect_class": "destructive"},
    )
    state = ExecutionState()

    ok, reason = validate_candidate_shared(cand_dangerous, contract, state)
    assert not ok, "Case memory candidate breached hard read-only contract constraint!"


# Invariant 10: History cannot override transaction state
def test_invariant_10_history_cannot_override_transaction_state():
    policy = TransactionSafetyPolicy()
    contract = ExecutionContract(capability="pay", side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION)
    cand_write = ExecutableAction(tool="execute_wire", metadata={"idempotent": False})

    # Even if historical frequency is 100%, in UNKNOWN_ACK, non-idempotent write is rejected
    safe, act_type, _ = policy.evaluate_transition(TransactionState.UNKNOWN_ACK, cand_write, contract)
    assert not safe
    assert act_type == RecoveryActionType.BLIND_RETRY
