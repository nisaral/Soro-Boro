"""Phase 2 Unit Tests: Deterministic Resolution & Safety Invariants.

Verifies:
1. Structural / schema compatibility
2. Explicit equivalence groups (Category A)
3. Explicit parameter alias maps (Category B)
4. Schema-compatible transformations (Category C)
5. Bounded fallback chains (Category D)
6. Compound resolution (Category E)
7. Safety Invariants:
   - Never semantically guess missing arguments
   - Never expand allowed action set
   - Never substitute undeclared side-effecting tools
   - Never retry uncertain-state writes without strict idempotency
   - Proper SELECT / DEFER / DENY decisions
"""

from __future__ import annotations

import pytest

from veyra.boundary.taxonomy import FailureClassification, FailureKind, FailureProvenance, VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.decision import Decision, DecisionKind, RecoveryDecision, RecoveryDecisionKind
from veyra.core.state import ExecutionState
from veyra.execution.engine import ExecutionEngine
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.recovery import SafeRecoveryPolicy
from veyra.registry.resolver import DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


def test_category_a_exact_equivalent_resolution():
    """Agent proposes an alias name; Veyra resolves to canonical equivalent tool."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="get_user_profile",
            executable=lambda user_id: {"id": user_id, "name": "Alice"},
            schema={"type": "object", "properties": {"user_id": {"type": "integer"}}, "required": ["user_id"]},
            idempotent=True,
        )
    )
    registry.register_equivalence("get_user_profile", ["get_user_info", "fetch_user"])

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="get_user_info", arguments={"user_id": 42})

    result = engine.execute(proposal)
    assert result == {"id": 42, "name": "Alice"}


def test_category_b_parameter_alias_mapping():
    """Agent proposes a known parameter alias; Veyra remaps to canonical argument name."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="search_catalog",
            executable=lambda query_term: f"results for {query_term}",
            schema={"type": "object", "properties": {"query_term": {"type": "string"}}, "required": ["query_term"]},
            idempotent=True,
        )
    )
    registry.register_parameter_aliases("search_catalog", {"q": "query_term", "query": "query_term"})

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="search_catalog", arguments={"q": "wireless headphones"})

    result = engine.execute(proposal)
    assert result == "results for wireless headphones"


def test_category_c_schema_compatible_transformation():
    """Agent passes stringified arguments; Veyra safely coerces them without guessing."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="fetch_records",
            executable=lambda limit, offset, active: {"limit": limit, "offset": offset, "active": active},
            schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "active": {"type": "boolean"},
                },
                "required": ["limit", "offset", "active"],
            },
            idempotent=True,
        )
    )

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="fetch_records", arguments={"limit": "25", "offset": "50", "active": "true"})

    result = engine.execute(proposal)
    assert result == {"limit": 25, "offset": 50, "active": True}


def test_category_d_primary_to_declared_fallback():
    """Primary tool fails with 503; Veyra falls back to declared backup tool."""
    call_counts = {"primary": 0, "backup": 0}

    def failing_primary(city: str):
        call_counts["primary"] += 1
        raise ConnectionError("503 Service Unavailable on primary API")

    def backup_service(city: str):
        call_counts["backup"] += 1
        return {"city": city, "temp": 22.5, "source": "backup_node"}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="weather_primary",
            executable=failing_primary,
            schema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            idempotent=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="weather_backup",
            executable=backup_service,
            schema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            idempotent=True,
        )
    )
    registry.register_fallback_chain("weather_primary", ["weather_backup"])

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="weather_primary", arguments={"city": "Tokyo"})

    result = engine.execute(proposal)
    assert result == {"city": "Tokyo", "temp": 22.5, "source": "backup_node"}
    assert call_counts["primary"] >= 1
    assert call_counts["backup"] == 1


def test_category_e_compound_failure_with_alias_and_coercion():
    """Primary fails; fallback requires parameter alias remapping AND schema coercion."""
    def failing_legacy(id_str: str):
        raise RuntimeError("Legacy service decommissioned")

    def modern_lookup(account_id: int):
        return {"account_id": account_id, "balance": 1500}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="legacy_lookup",
            executable=failing_legacy,
            schema={"type": "object", "properties": {"id_str": {"type": "string"}}, "required": ["id_str"]},
            idempotent=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="modern_lookup",
            executable=modern_lookup,
            schema={"type": "object", "properties": {"account_id": {"type": "integer"}}, "required": ["account_id"]},
            idempotent=True,
        )
    )
    registry.register_fallback_chain("legacy_lookup", ["modern_lookup"])
    registry.register_parameter_aliases("modern_lookup", {"id_str": "account_id"})

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="legacy_lookup", arguments={"id_str": "99401"})

    result = engine.execute(proposal)
    assert result == {"account_id": 99401, "balance": 1500}


def test_safety_invariant_1_never_guess_arguments():
    """Missing required argument cannot be guessed semantically -> execution is DENIED."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="send_payment",
            executable=lambda amount, recipient, currency="USD": "sent",
            schema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "recipient": {"type": "string"},
                },
                "required": ["amount", "recipient"],
            },
            idempotent=False,
        )
    )

    engine = ExecutionEngine(registry=registry)
    # Missing 'recipient' parameter
    proposal = ExecutableAction(tool="send_payment", arguments={"amount": 100})

    with pytest.raises(VeyraBoundaryError) as exc_info:
        engine.execute(proposal)

    # Must be denied by policy or schema error, never guessed
    assert exc_info.value.classification.kind in (FailureKind.SCHEMA_ERROR, FailureKind.AUTHORIZATION_ERROR)


def test_safety_invariant_2_never_expand_allowed_action_set():
    """Candidate outside allowed_tools context is strictly filtered out."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_file",
            executable=lambda path: "contents",
            idempotent=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="delete_file",
            executable=lambda path: "deleted",
            idempotent=False,
        )
    )
    registry.register_equivalence("read_file", ["delete_file"])

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="delete_file", arguments={"path": "/tmp/test"})

    # Context explicitly restricts allowed tools to read_file only
    state = ExecutionState(agent="restricted_agent", context={"allowed_tools": ["read_file"]})

    with pytest.raises(VeyraBoundaryError) as exc_info:
        engine.execute(proposal, state=state)

    assert "denied" in str(exc_info.value).lower() or "no valid candidates" in str(exc_info.value).lower()


def test_safety_invariant_3_never_substitute_undeclared_mutations():
    """Undeclared side-effecting tools cannot be substituted for one another."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="charge_stripe",
            executable=lambda amount: "charged",
            idempotent=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="charge_paypal",
            executable=lambda amount: "charged",
            idempotent=False,
        )
    )
    # Fallback chain is registered, BUT charge_paypal is NOT in declared equivalence group
    registry.register_fallback_chain("charge_stripe", ["charge_paypal"])

    resolver = DeterministicCandidateResolver(registry)
    proposal = ExecutableAction(tool="charge_stripe", arguments={"amount": 50})
    candidates = resolver.resolve(proposal, ExecutionState(agent="test"))

    # Because charge_paypal is a mutation (idempotent=False) and NOT an explicit declared equivalent,
    # resolver MUST NOT include it as an undeclared mutation substitute!
    cand_tools = [c.tool for c in candidates]
    assert "charge_paypal" not in cand_tools


def test_safety_invariant_4_never_retry_uncertain_mutations():
    """Timeout on non-idempotent tool is an uncertain state write -> NEVER retried or substituted."""
    registry = ToolRegistry()
    call_counts = {"charges": 0}

    def timeout_charge(amount: int):
        call_counts["charges"] += 1
        raise TimeoutError("Gateway timeout during credit card write")

    registry.register(
        ToolDefinition(
            name="execute_transfer",
            executable=timeout_charge,
            idempotent=False,  # Mutation!
        )
    )

    engine = ExecutionEngine(registry=registry)
    proposal = ExecutableAction(tool="execute_transfer", arguments={"amount": 500})

    with pytest.raises(VeyraBoundaryError) as exc_info:
        engine.execute(proposal)

    # Exactly 1 call; NEVER retried after timeout on mutation!
    assert call_counts["charges"] == 1
    assert exc_info.value.classification.provenance == FailureProvenance.TIMEOUT
    assert not exc_info.value.classification.safe_to_retry
