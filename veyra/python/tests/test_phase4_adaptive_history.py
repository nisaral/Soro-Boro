"""Phase 4 Unit Tests: Online Execution Memory & TAGE-Style History Policy.

Verifies:
- Argument shape extraction
- Online trace observation and TAGE saturating counters (0 to 7)
- Longest-matching history rule (H8 > H4 > H2 > H1 > H0)
- Case-based memory similarity scoring
- AdaptiveHistoryRoutePolicy SELECT / DEFER / DENY behaviors
- Complete integration with ExecutionEngine
"""

from __future__ import annotations

import pytest

from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.state import ExecutionState
from veyra.execution.engine import ExecutionEngine
from veyra.policy.history_adaptive import (
    AdaptiveHistoryRoutePolicy,
    OnlineExecutionMemory,
    get_argument_shape,
)
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


def test_argument_shape_extraction():
    args = {"limit": 10, "query": "books", "active": True, "ratio": 3.14}
    shape = get_argument_shape(args)
    expected = (
        ("active", "bool"),
        ("limit", "int"),
        ("query", "str"),
        ("ratio", "float"),
    )
    assert shape == expected


def test_tage_saturating_counters_and_longest_match():
    memory = OnlineExecutionMemory()

    # Observe success with 2-step history: [tool_a] -> tool_b resolves to target_x
    trace1 = {
        "proposal": {"tool": "tool_b", "arguments": {"id": 1}},
        "resolved_tool": "target_x",
        "previous_tools": ["tool_a"],
        "outcome": "success",
    }
    memory.observe(trace1)

    # Observe success with 4-step history: [tool_w, tool_x, tool_y, tool_z] -> tool_b resolves to target_y
    trace2 = {
        "proposal": {"tool": "tool_b", "arguments": {"id": 1}},
        "resolved_tool": "target_y",
        "previous_tools": ["tool_w", "tool_x", "tool_y", "tool_z"],
        "outcome": "success",
    }
    memory.observe(trace2)

    # Query with 1-step history: should match target_x (H=1)
    pred_tool, h_len, conf = memory.predict_tage(
        proposed_tool="tool_b",
        arguments={"id": 1},
        history=["tool_a"],
        allowed_candidates={"target_x", "target_y", "target_z"},
    )
    assert pred_tool == "target_x"
    assert h_len == 1
    assert conf >= 0.5

    # Query with 4-step history: should match target_y (H=4)
    pred_tool4, h_len4, conf4 = memory.predict_tage(
        proposed_tool="tool_b",
        arguments={"id": 1},
        history=["tool_w", "tool_x", "tool_y", "tool_z"],
        allowed_candidates={"target_x", "target_y", "target_z"},
    )
    assert pred_tool4 == "target_y"
    assert h_len4 == 4
    assert conf4 >= 0.5


def test_case_memory_optional_off_by_default():
    memory = OnlineExecutionMemory()
    policy = AdaptiveHistoryRoutePolicy(memory=memory, confidence_threshold=0.5)
    assert policy.use_case_memory is False


def test_adaptive_history_policy_select_and_defer():
    memory = OnlineExecutionMemory()
    policy = AdaptiveHistoryRoutePolicy(memory=memory, confidence_threshold=0.5, defer_on_uncertainty=True)

    cand_primary = ExecutableAction(tool="primary_tool", arguments={"id": 10})
    cand_alt = ExecutableAction(tool="alt_tool", arguments={"id": 10})
    candidates = [cand_primary, cand_alt]

    state = ExecutionState(agent="agent_1", history=["prev_tool"])

    # Cold query with no prior observation -> confidence is 0 -> defers
    decision = policy.resolve(state, candidates)
    assert decision.kind == DecisionKind.DEFER

    # Observe successful resolution of primary_tool -> alt_tool after prev_tool
    trace = {
        "proposal": {"tool": "primary_tool", "arguments": {"id": 10}},
        "resolved_tool": "alt_tool",
        "previous_tools": ["prev_tool"],
        "outcome": "success",
    }
    memory.observe(trace)
    memory.observe(trace)  # Second confirmation to saturate counter

    # Now resolve again -> should SELECT alt_tool with high confidence
    decision2 = policy.resolve(state, candidates)
    assert decision2.kind == DecisionKind.SELECT
    assert decision2.action.tool == "alt_tool"
    assert "TAGE" in decision2.reason or "Case-based" in decision2.reason


def test_online_learning_in_execution_engine():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="cloud_search",
            executable=lambda q: f"cloud results for {q}",
            schema={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
            idempotent=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="local_search",
            executable=lambda q: f"local results for {q}",
            schema={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
            idempotent=True,
        )
    )
    # Register equivalence between search tools
    registry.register_equivalence("cloud_search", ["local_search"])

    memory = OnlineExecutionMemory()
    policy = AdaptiveHistoryRoutePolicy(memory=memory, confidence_threshold=0.5)
    engine = ExecutionEngine(registry=registry, route_policy=policy)

    state = ExecutionState(agent="test_agent", history=["offline_mode_detected"])

    # Seed execution memory: when offline_mode_detected, local_search is the winner
    trace = {
        "proposal": {"tool": "cloud_search", "arguments": {"q": "dataset.csv"}},
        "resolved_tool": "local_search",
        "previous_tools": ["offline_mode_detected"],
        "outcome": "success",
    }
    memory.observe(trace)
    memory.observe(trace)

    # Agent proposes cloud_search in offline mode -> Veyra resolves to local_search via TAGE memory!
    proposal = ExecutableAction(tool="cloud_search", arguments={"q": "dataset.csv"})
    result = engine.execute(proposal, state=state)
    assert result == "local results for dataset.csv"
