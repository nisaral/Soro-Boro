"""Unit tests for Phase 12 (Fair Baselines) and Phase 14 (ExecutionContract)."""

import pytest

from veyra.baseline.static_resolution import StaticResolutionMiddleware
from veyra.boundary.taxonomy import VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.boundary.interceptor import Veyra


def test_execution_contract_freshness_boundary():
    """Verify ground-truth freshness contract examples from Phase 13/14 specification.

    Example 1:
      requested: freshness <= 10 seconds
      candidate A: freshness 5 seconds -> EQUIVALENT
      candidate B: freshness 30 seconds -> NOT EQUIVALENT

    Example 2:
      requested: freshness <= 60 seconds
      candidate B: freshness 30 seconds -> EQUIVALENT
    """
    state = ExecutionState()

    cand_a = ExecutableAction(tool="tool_a", metadata={"freshness_sec": 5.0})
    cand_b = ExecutableAction(tool="tool_b", metadata={"freshness_sec": 30.0})

    # Example 1: max freshness 10s
    contract_10s = ExecutionContract(max_freshness_sec=10.0)
    is_valid_a, _ = contract_10s.validate_candidate(cand_a, state)
    is_valid_b, reason_b = contract_10s.validate_candidate(cand_b, state)

    assert is_valid_a is True
    assert is_valid_b is False
    assert "Freshness contract violated" in reason_b

    # Example 2: max freshness 60s
    contract_60s = ExecutionContract(max_freshness_sec=60.0)
    is_valid_b_60s, _ = contract_60s.validate_candidate(cand_b, state)
    assert is_valid_b_60s is True


def test_execution_contract_side_effect_and_idempotency_invariants():
    """Verify that mutating candidates cannot be substituted for READ_ONLY contracts."""
    state = ExecutionState()

    read_contract = ExecutionContract(side_effect_class=SideEffectClass.READ_ONLY, idempotent_required=True)

    safe_candidate = ExecutableAction(
        tool="safe_query",
        metadata={"idempotent": True, "side_effect_class": "read_only"},
    )
    mutating_candidate = ExecutableAction(
        tool="unsafe_update",
        metadata={"idempotent": False, "side_effect_class": "non_idempotent_mutation"},
    )

    valid_safe, _ = read_contract.validate_candidate(safe_candidate, state)
    valid_mut, reason_mut = read_contract.validate_candidate(mutating_candidate, state)

    assert valid_safe is True
    assert valid_mut is False
    assert "mutating side-effects" in reason_mut


def test_execution_contract_required_state_assertions():
    """Contract enforces required state conditions (e.g. database_connected=True)."""
    contract = ExecutionContract(required_state={"db_session": "active", "auth_tier": "premium"})

    state_valid = ExecutionState(context={"env_state": {"db_session": "active", "auth_tier": "premium"}})
    state_invalid = ExecutionState(context={"env_state": {"db_session": "active", "auth_tier": "basic"}})

    candidate = ExecutableAction(tool="execute_report")

    is_valid, _ = contract.validate_candidate(candidate, state_valid)
    assert is_valid is True

    is_invalid, reason = contract.validate_candidate(candidate, state_invalid)
    assert is_invalid is False
    assert "auth_tier" in reason


def test_static_resolution_baseline_matches_same_declarations():
    """StaticResolutionMiddleware must receive EXACTLY the same declarations as Veyra and resolve primary to fallback."""
    registry = ToolRegistry()

    def primary():
        raise ConnectionError("Primary down")

    def replica():
        return {"data": "replica_data"}

    registry.register(ToolDefinition(name="primary_tool", executable=primary, idempotent=True))
    registry.register(ToolDefinition(name="replica_tool", executable=replica, idempotent=True))
    registry.register_equivalence("primary_tool", ["replica_tool"])
    registry.register_fallback_chain("primary_tool", ["replica_tool"])

    # Both static resolution and Veyra should succeed on this clean fallback
    static_mw = StaticResolutionMiddleware(registry=registry)
    veyra = Veyra(registry=registry)

    res_static = static_mw.call("primary_tool", {})
    assert res_static == {"data": "replica_data"}

    res_veyra = veyra.call("primary_tool", {}, idempotent=True)
    assert res_veyra == {"data": "replica_data"}


def test_veyra_differentiates_from_static_resolution_on_execution_contract():
    """Veyra preserves intent under contract constraints where static resolution fails.

    Scenario:
    - Primary tool is degraded.
    - Two candidates in equivalence group:
      Candidate 1 (first declared): freshness = 30s (violates requested <= 10s)
      Candidate 2 (second declared): freshness = 5s (satisfies requested <= 10s)
    - Static resolution naively picks the first declared candidate (Candidate 1), violating the contract.
    - Veyra evaluates ExecutionContract, rejects Candidate 1, and selects Candidate 2!
    """
    registry = ToolRegistry()

    calls = []

    def cand1_stale():
        calls.append("cand1_stale")
        return {"source": "cand1", "freshness_sec": 30.0}

    def cand2_fresh():
        calls.append("cand2_fresh")
        return {"source": "cand2", "freshness_sec": 5.0}

    registry.register(
        ToolDefinition(
            name="cand1_stale",
            executable=cand1_stale,
            freshness_sec=30.0,
            idempotent=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="cand2_fresh",
            executable=cand2_fresh,
            freshness_sec=5.0,
            idempotent=True,
        )
    )

    registry.register_equivalence("primary_data", ["cand1_stale", "cand2_fresh"])
    registry.register_fallback_chain("primary_data", ["cand1_stale", "cand2_fresh"])

    # 1. Static Resolution: blindly picks first candidate (cand1_stale)
    static_mw = StaticResolutionMiddleware(registry=registry)
    res_static = static_mw.call("primary_data", {})
    # Static resolution returns stale data!
    assert res_static["source"] == "cand1"
    assert res_static["freshness_sec"] == 30.0

    # 2. Veyra: Enforces ExecutionContract (freshness <= 10s)
    veyra = Veyra(registry=registry)
    proposal = ExecutableAction(
        tool="primary_data",
        metadata={
            "freshness": 10.0,  # Max requested freshness 10s
            "max_freshness_sec": 10.0,
            "idempotent": True,
        },
    )

    state = ExecutionState()
    res_veyra = veyra.execute(proposal, state=state)

    # Veyra filtered out cand1_stale because freshness 30s > 10s, preserving user intent by picking cand2_fresh!
    assert res_veyra["source"] == "cand2"
    assert res_veyra["freshness_sec"] == 5.0
