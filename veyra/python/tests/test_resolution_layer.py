"""Unit tests for Section 2 & 3: Veyra Resolution Layer and Deterministic Resolvers."""

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution import (
    FreshnessAwareResolver,
    HealthAwareResolver,
    PolicyAwareResolver,
    ResolutionDecision,
    StaticPriorityResolver,
    TrajectoryFailureKind,
    VeyraResolver,
    classify_trajectory_failure,
)


@pytest.fixture
def sample_registry():
    reg = ToolRegistry()
    # Primary tool and equivalent
    reg.register(
        ToolDefinition(
            name="primary_data_query",
            healthy=True,
            freshness_sec=2.0,
            reliability=0.99,
            latency_ms=15.0,
            permissions=["read:data"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1", "replica_id": "rep_a"},
        )
    )
    reg.register(
        ToolDefinition(
            name="replica_data_query",
            healthy=True,
            freshness_sec=1.0,
            reliability=0.99,
            latency_ms=8.0,
            permissions=["read:data"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1", "replica_id": "rep_b"},
        )
    )
    reg.register(
        ToolDefinition(
            name="unhealthy_data_query",
            healthy=False,
            freshness_sec=0.5,
            reliability=0.50,
            latency_ms=5.0,
            permissions=["read:data"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1", "replica_id": "rep_c"},
        )
    )
    reg.register(
        ToolDefinition(
            name="stale_data_query",
            healthy=True,
            freshness_sec=120.0,
            reliability=0.99,
            latency_ms=10.0,
            permissions=["read:data"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1", "replica_id": "rep_d"},
        )
    )
    reg.register(
        ToolDefinition(
            name="unauthorized_data_query",
            healthy=True,
            freshness_sec=0.1,
            reliability=1.0,
            latency_ms=1.0,
            permissions=["admin:super"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1"},
        )
    )
    reg.register(
        ToolDefinition(
            name="foreign_tenant_query",
            healthy=True,
            freshness_sec=0.1,
            reliability=1.0,
            latency_ms=1.0,
            permissions=["read:data"],
            capabilities=["query", "search"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_other"},
        )
    )
    reg.register_equivalence(
        "primary_data_query",
        [
            "primary_data_query",
            "replica_data_query",
            "unhealthy_data_query",
            "stale_data_query",
            "unauthorized_data_query",
            "foreign_tenant_query",
        ],
    )
    return reg


def test_static_priority_resolver(sample_registry):
    resolver = StaticPriorityResolver(sample_registry)
    proposal = ExecutableAction(tool="primary_data_query", metadata={"side_effect_class": "read_only"})
    state = ExecutionState(agent="agent_1", permissions={"read:data"}, context={"tenant": "tenant_1"})

    res = resolver.resolve(proposal, state)
    assert res.decision == ResolutionDecision.SELECT.value
    assert res.selected_candidate is not None
    assert res.selected_candidate.tool == "primary_data_query"


def test_health_aware_resolver_filters_unhealthy(sample_registry):
    resolver = HealthAwareResolver(sample_registry)
    # Propose unhealthy tool
    proposal = ExecutableAction(tool="unhealthy_data_query", metadata={"side_effect_class": "read_only"})
    state = ExecutionState(agent="agent_1", permissions={"read:data"}, context={"tenant": "tenant_1"})

    res = resolver.resolve(proposal, state)
    assert res.decision == ResolutionDecision.SELECT.value
    # Should reject unhealthy tool and choose healthy replica
    assert "unhealthy_data_query" in res.rejected_candidates
    assert res.selected_candidate.tool in ("primary_data_query", "replica_data_query")


def test_freshness_aware_resolver_filters_stale(sample_registry):
    resolver = FreshnessAwareResolver(sample_registry)
    # Propose stale tool with strict max_freshness_sec = 5.0
    proposal = ExecutableAction(
        tool="stale_data_query",
        metadata={"side_effect_class": "read_only", "max_freshness_sec": 5.0},
    )
    state = ExecutionState(agent="agent_1", permissions={"read:data"}, context={"tenant": "tenant_1"})

    res = resolver.resolve(proposal, state)
    assert res.decision == ResolutionDecision.SELECT.value
    assert "stale_data_query" in res.rejected_candidates
    # Chooses a fresh candidate (under 5.0s)
    assert res.selected_candidate.tool in ("unhealthy_data_query", "replica_data_query", "primary_data_query")


def test_policy_aware_resolver_enforces_hard_constraints(sample_registry):
    resolver = PolicyAwareResolver(sample_registry)
    state = ExecutionState(agent="agent_1", permissions={"read:data"}, context={"tenant": "tenant_1"})

    # 1. Negative control: valid proposal is preserved with 0 unnecessary intervention
    valid_proposal = ExecutableAction(tool="primary_data_query", metadata={"side_effect_class": "read_only"})
    res_valid = resolver.resolve(valid_proposal, state)
    assert res_valid.decision == ResolutionDecision.SELECT.value
    assert res_valid.selected_candidate.tool == "primary_data_query"
    assert "negative control" in res_valid.reason

    # 2. Authorization enforcement: proposing unauthorized tool
    unauth_proposal = ExecutableAction(
        tool="unauthorized_data_query",
        metadata={"side_effect_class": "read_only", "permissions": ["admin:super"]},
    )
    res_unauth = resolver.resolve(unauth_proposal, state)
    # The unauthorized candidate must be rejected
    assert "unauthorized_data_query" in res_unauth.rejected_candidates
    assert res_unauth.selected_candidate.tool != "unauthorized_data_query"

    # 3. Tenant isolation: foreign tenant must be rejected
    foreign_proposal = ExecutableAction(
        tool="foreign_tenant_query",
        metadata={"side_effect_class": "read_only", "tenant": "tenant_other"},
    )
    res_tenant = resolver.resolve(foreign_proposal, state)
    assert "foreign_tenant_query" in res_tenant.rejected_candidates
    assert res_tenant.selected_candidate.tool != "foreign_tenant_query"

    # 4. Transaction safety: UNKNOWN_ACK + non-idempotent mutation = NO BLIND REPLAY
    state_tx = ExecutionState(
        agent="agent_1",
        permissions={"read:data", "write:data"},
        context={"tenant": "tenant_1", "tx_state": "unknown_ack"},
    )
    mutate_proposal = ExecutableAction(
        tool="charge_card",
        metadata={"is_idempotent": False, "is_mutation": True, "side_effect_class": "non_idempotent_mutation"},
    )
    res_tx = resolver.resolve(mutate_proposal, state_tx)
    assert res_tx.decision == ResolutionDecision.DENY.value
    assert "UNKNOWN_ACK" in res_tx.reason or "UNKNOWN_ACK" in str(res_tx.rejected_candidates)


def test_veyra_resolver_pipeline_and_ranking(sample_registry):
    resolver = VeyraResolver(sample_registry)
    state = ExecutionState(
        agent="agent_1",
        permissions={"read:data"},
        context={"tenant": "tenant_1", "max_freshness_sec": 10.0},
    )

    # Propose primary data query
    proposal = ExecutableAction(tool="primary_data_query", metadata={"side_effect_class": "read_only"})
    res = resolver.resolve(proposal, state)

    assert res.decision == ResolutionDecision.SELECT.value
    assert res.selected_candidate is not None
    assert res.risk_level == "low"
    assert res.confidence > 0.8
    # Unhealthy candidate was rejected by soft preferences or evaluated properly
    assert len(res.evaluations) > 0


def test_veyra_resolver_hard_constraints_never_overridden_by_ranking():
    """CRITICAL INVARIANT: Ranking / Soft Preferences must NEVER override hard constraints."""
    reg = ToolRegistry()
    # Fast, healthy, but UNAUTHORIZED candidate
    reg.register(
        ToolDefinition(
            name="super_fast_unauth",
            healthy=True,
            latency_ms=0.01,
            reliability=1.0,
            permissions=["admin:root"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1"},
        )
    )
    # Slow, authorized candidate
    reg.register(
        ToolDefinition(
            name="slow_authorized",
            healthy=True,
            latency_ms=500.0,
            reliability=0.90,
            permissions=["read:data"],
            side_effect_class="read_only",
            metadata={"tenant": "tenant_1"},
        )
    )
    reg.register_equivalence("super_fast_unauth", ["super_fast_unauth", "slow_authorized"])

    resolver = VeyraResolver(reg)
    state = ExecutionState(agent="agent_1", permissions={"read:data"}, context={"tenant": "tenant_1"})

    proposal = ExecutableAction(tool="super_fast_unauth", metadata={"side_effect_class": "read_only"})
    res = resolver.resolve(proposal, state)

    # Must NEVER select the unauthorized tool regardless of latency/health scores
    assert res.selected_candidate.tool == "slow_authorized"
    assert "super_fast_unauth" in res.rejected_candidates
    assert "unauthorized" in res.rejected_candidates["super_fast_unauth"]


def test_failure_taxonomy_classification():
    record1 = classify_trajectory_failure("Tenant mismatch error", {"tool": "api_call"})
    assert record1.failure_kind == TrajectoryFailureKind.TENANT_FAILURE
    assert record1.is_addressable is True

    record2 = classify_trajectory_failure("Permission denied: missing rbac read", {"tool": "api_call"})
    assert record2.failure_kind == TrajectoryFailureKind.AUTHORIZATION_FAILURE
    assert record2.is_addressable is True

    record3 = classify_trajectory_failure("Lost ACK during commit", {"tool": "charge_card"})
    assert record3.failure_kind == TrajectoryFailureKind.UNKNOWN_ACK
    assert record3.is_addressable is True

    record4 = classify_trajectory_failure("Agent failed reasoning about math", {"tool": "calc"})
    assert record4.failure_kind == TrajectoryFailureKind.AGENT_REASONING_FAILURE
    assert record4.is_addressable is False
