"""Phase 6 Unit Tests: Selective Resolution with Calibrated Uncertainty.

Verifies:
- High confidence (>= theta) emits SELECT
- Insufficient confidence (< theta) emits DEFER
- Policy/risk constraint violations emit DENY
- Invariant: Never force a low-confidence substitution
- End-to-end integration with ExecutionEngine
"""

from __future__ import annotations

import pytest

from veyra.boundary.taxonomy import FailureKind, VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.state import ExecutionState
from veyra.execution.engine import ExecutionEngine
from veyra.policy.history_adaptive import OnlineExecutionMemory
from veyra.policy.reliability import ToolReliabilityTracker
from veyra.policy.selective import (
    CalibratedUncertaintyEstimator,
    SelectiveResolutionPolicy,
)
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


def test_selective_resolution_high_confidence_select():
    tracker = ToolReliabilityTracker()
    memory = OnlineExecutionMemory()

    # Seed high health for tool_alpha
    stats = tracker.get_or_create("tool_alpha")
    for _ in range(10):
        stats.observe(success=True, latency_ms=10.0)

    estimator = CalibratedUncertaintyEstimator(memory=memory, tracker=tracker)
    policy = SelectiveResolutionPolicy(estimator=estimator, select_threshold=0.60)

    cand = ExecutableAction(tool="tool_alpha", arguments={"id": 1})
    state = ExecutionState(agent="agent_1")

    decision = policy.resolve(state, [cand])
    assert decision.kind == DecisionKind.SELECT
    assert decision.action.tool == "tool_alpha"
    assert "selective resolution SELECT" in decision.reason


def test_selective_resolution_insufficient_confidence_defer():
    tracker = ToolReliabilityTracker()
    memory = OnlineExecutionMemory()

    # Tool has low health due to errors
    stats = tracker.get_or_create("shaky_tool")
    for _ in range(5):
        stats.observe(success=False, provenance="TIMEOUT")

    estimator = CalibratedUncertaintyEstimator(memory=memory, tracker=tracker)
    # Strict threshold requires 0.75 confidence
    policy = SelectiveResolutionPolicy(estimator=estimator, select_threshold=0.75)

    cand = ExecutableAction(tool="shaky_tool", arguments={"id": 1})
    state = ExecutionState(agent="agent_1")

    # Policy MUST NOT force a low-confidence substitution; it must DEFER!
    decision = policy.resolve(state, [cand])
    assert decision.kind == DecisionKind.DEFER
    assert "insufficient" in decision.reason.lower()


def test_selective_resolution_policy_violation_deny():
    estimator = CalibratedUncertaintyEstimator()
    policy = SelectiveResolutionPolicy(estimator=estimator)

    cand = ExecutableAction(tool="unauthorized_tool", arguments={"id": 1})
    # State context explicitly restricts allowed tools
    state = ExecutionState(agent="agent_1", context={"allowed_tools": ["allowed_tool_only"]})

    decision = policy.resolve(state, [cand])
    assert decision.kind == DecisionKind.DENY
    assert "not in policy-allowed" in decision.reason


def test_selective_resolution_risk_class_deny():
    estimator = CalibratedUncertaintyEstimator()
    policy = SelectiveResolutionPolicy(estimator=estimator)

    # Destructive action proposed in low-risk environment
    cand = ExecutableAction(tool="drop_table", arguments={}, metadata={"risk_class": "destructive"})
    state = ExecutionState(agent="agent_1", context={"max_risk": "low"})

    decision = policy.resolve(state, [cand])
    assert decision.kind == DecisionKind.DENY
    assert "risk class 'destructive' exceeds" in decision.reason


def test_selective_policy_in_execution_engine():
    registry = ToolRegistry()
    registry.register(ToolDefinition(name="calc", executable=lambda x: x * 2, idempotent=True))

    tracker = ToolReliabilityTracker()
    stats = tracker.get_or_create("calc")
    for _ in range(5):
        stats.observe(success=True)

    estimator = CalibratedUncertaintyEstimator(tracker=tracker)
    policy = SelectiveResolutionPolicy(estimator=estimator, select_threshold=0.60)
    engine = ExecutionEngine(registry=registry, route_policy=policy)

    # High confidence executes cleanly
    res = engine.execute(ExecutableAction(tool="calc", arguments={"x": 21}))
    assert res == 42

    # Under high uncertainty (threshold 0.99), engine cleanly escalates/defers
    strict_policy = SelectiveResolutionPolicy(estimator=estimator, select_threshold=0.99)
    strict_engine = ExecutionEngine(registry=registry, route_policy=strict_policy)

    with pytest.raises(VeyraBoundaryError) as exc_info:
        strict_engine.execute(ExecutableAction(tool="calc", arguments={"x": 21}))

    assert "defer" in str(exc_info.value).lower()
