"""Phase 5 Unit Tests: Tool Reliability Engine.

Verifies:
- Beta-Bernoulli conjugate reliability estimation and credible intervals
- EWMA success rate and latency tracking
- CUSUM sequential degradation detection on error bursts
- ReliabilityAwareRoutePolicy routing to healthier candidate inside equivalence group
- Integration with ExecutionEngine
"""

from __future__ import annotations

import pytest

from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.state import ExecutionState
from veyra.execution.engine import ExecutionEngine
from veyra.policy.reliability import (
    ReliabilityAwareRoutePolicy,
    ToolHealthStats,
    ToolReliabilityTracker,
)
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


def test_beta_bernoulli_and_ewma_tracking():
    stats = ToolHealthStats(tool_name="api_v1")

    # Initially: prior alpha=1, beta=1 -> mean = 0.50
    assert stats.beta_mean == 0.50

    # Observe 9 successes and 1 failure
    for _ in range(9):
        stats.observe(success=True, latency_ms=12.0)
    stats.observe(success=False, latency_ms=100.0, provenance="TIMEOUT")

    assert stats.total_calls == 10
    assert stats.success_count == 9
    assert stats.failure_count == 1
    assert stats.timeout_count == 1
    assert stats.timeout_rate == 0.10

    # Beta mean: (1 + 9) / (1 + 1 + 10) = 10 / 12 = 0.8333
    assert round(stats.beta_mean, 2) == 0.83
    assert stats.beta_lower_credible_bound < stats.beta_mean

    # EWMA should reflect high success rate
    assert stats.ewma_success_rate > 0.70
    assert not stats.is_degraded


def test_cusum_change_detector_on_error_spike():
    stats = ToolHealthStats(tool_name="flaky_service")

    # Seed with 10 successes
    for _ in range(10):
        stats.observe(success=True, latency_ms=10.0)
    assert not stats.is_degraded
    assert stats.cusum_s == 0.0

    # Sudden burst of 5 consecutive failures (service outage)
    for _ in range(5):
        stats.observe(success=False, latency_ms=500.0, provenance="TIMEOUT")

    # CUSUM statistic should exceed threshold and trip degradation alarm
    assert stats.cusum_s >= stats.cusum_threshold
    assert stats.is_degraded
    assert stats.composite_health_score < 0.40


def test_reliability_aware_route_policy():
    tracker = ToolReliabilityTracker()
    policy = ReliabilityAwareRoutePolicy(tracker=tracker, health_delta_threshold=0.20)

    # Tool A (primary) has degraded
    stats_a = tracker.get_or_create("service_a")
    for _ in range(6):
        stats_a.observe(success=False, provenance="TIMEOUT")
    assert stats_a.is_degraded

    # Tool B (declared replica) is healthy
    stats_b = tracker.get_or_create("service_b")
    for _ in range(10):
        stats_b.observe(success=True, latency_ms=15.0)

    cand_a = ExecutableAction(tool="service_a", arguments={"q": "test"})
    cand_b = ExecutableAction(tool="service_b", arguments={"q": "test"})
    candidates = [cand_a, cand_b]

    state = ExecutionState(agent="agent_1")
    decision = policy.resolve(state, candidates)

    assert decision.kind == DecisionKind.SELECT
    assert decision.action.tool == "service_b"
    assert "preferred healthier 'service_b'" in decision.reason


def test_reliability_integration_with_execution_engine():
    registry = ToolRegistry()
    call_counts = {"primary": 0, "replica": 0}

    def exec_primary(q: str):
        call_counts["primary"] += 1
        return "primary ok"

    def exec_replica(q: str):
        call_counts["replica"] += 1
        return "replica ok"

    registry.register(ToolDefinition(name="node_primary", executable=exec_primary, idempotent=True))
    registry.register(ToolDefinition(name="node_replica", executable=exec_replica, idempotent=True))
    registry.register_equivalence("node_primary", ["node_replica"])

    tracker = ToolReliabilityTracker()
    policy = ReliabilityAwareRoutePolicy(tracker=tracker)
    engine = ExecutionEngine(registry=registry, route_policy=policy)

    # Primary initially healthy -> routes to node_primary
    engine.execute(ExecutableAction(tool="node_primary", arguments={"q": "1"}))
    assert call_counts["primary"] == 1
    assert call_counts["replica"] == 0

    # Primary experiences failure spike
    stats_p = tracker.get_or_create("node_primary")
    for _ in range(5):
        stats_p.observe(success=False, provenance="TIMEOUT")

    stats_r = tracker.get_or_create("node_replica")
    for _ in range(5):
        stats_r.observe(success=True)

    # Next call: engine automatically routes to node_replica due to degraded primary!
    engine.execute(ExecutableAction(tool="node_primary", arguments={"q": "2"}))
    assert call_counts["replica"] == 1
