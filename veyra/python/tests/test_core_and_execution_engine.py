"""Unit tests for Veyra Core, ToolRegistry, CandidateResolver, RoutePolicy, and ExecutionEngine."""

import pytest
from veyra.boundary.taxonomy import FailureKind, VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind, RecoveryDecisionKind
from veyra.core.state import ExecutionState
from veyra.core.trace import ExecutionTrace, TraceSink
from veyra.execution.engine import ExecutionEngine
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.recovery import SafeRecoveryPolicy
from veyra.registry.resolver import DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


class TestCoreAbstractions:
    def test_executable_action_metadata(self):
        action = ExecutableAction(
            tool="refund_payment",
            arguments={"tx_id": "tx_123", "amount": 100},
            metadata={
                "idempotent": True,
                "retryable": True,
                "risk_class": "high",
                "capabilities": ["billing", "refund"],
                "permissions": ["billing:write"],
                "equivalence_group": "payments.refund",
            },
        )
        assert action.tool == "refund_payment"
        assert action.is_idempotent is True
        assert action.is_retryable is True
        assert action.risk_class == "high"
        assert action.capabilities == ["billing", "refund"]
        assert action.required_permissions == ["billing:write"]
        assert action.equivalence_group == "payments.refund"

    def test_execution_state_signature(self):
        state1 = ExecutionState(agent="agent_v1", step=1, history=[{"tool": "search"}], context={"user": "alice"})
        state2 = ExecutionState(agent="agent_v1", step=1, history=[{"tool": "search"}], context={"user": "bob"})
        assert state1.compute_signature() == state2.compute_signature()

        state3 = ExecutionState(agent="agent_v2", step=2, history=[{"tool": "update"}], context={"user": "alice"})
        assert state1.compute_signature() != state3.compute_signature()


class TestToolRegistryAndResolver:
    def test_declared_equivalence_resolution(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="get_customer", capabilities=["crm"]))
        registry.register(ToolDefinition(name="crm.get_customer", capabilities=["crm"]))
        registry.register(ToolDefinition(name="legacy.get_customer", capabilities=["crm"]))

        # Explicit developer declaration: zero guessing
        registry.register_equivalence("get_customer", ["crm.get_customer", "legacy.get_customer"])

        resolver = DeterministicCandidateResolver(registry)
        proposal = ExecutableAction(tool="get_customer", arguments={"id": "cust_1"})
        state = ExecutionState()

        candidates = resolver.resolve(proposal, state)
        candidate_names = [c.tool for c in candidates]
        assert "get_customer" in candidate_names
        assert "crm.get_customer" in candidate_names
        assert "legacy.get_customer" in candidate_names

    def test_hard_constraints_filtering(self):
        registry = ToolRegistry()
        # 1. Unhealthy tool
        registry.register(ToolDefinition(name="broken_tool", healthy=False))
        # 2. Permission-restricted tool
        registry.register(ToolDefinition(name="admin_tool", permissions=["admin:delete"]))
        # 3. High risk tool
        registry.register(ToolDefinition(name="wipe_db", risk_class="destructive"))
        # 4. Normal tool
        registry.register(ToolDefinition(name="list_users", risk_class="low"))

        resolver = DeterministicCandidateResolver(registry)

        # State has no admin permissions and max_risk=low
        state = ExecutionState(permissions={"user:read"}, context={"max_risk": "low"})

        # Try broken
        assert resolver.resolve(ExecutableAction(tool="broken_tool"), state) == []
        # Try admin
        assert resolver.resolve(ExecutableAction(tool="admin_tool"), state) == []
        # Try wipe_db
        assert resolver.resolve(ExecutableAction(tool="wipe_db"), state) == []
        # Try list_users
        assert len(resolver.resolve(ExecutableAction(tool="list_users"), state)) == 1

    def test_policy_allowed_action_space_invariant(self):
        """Invariant: router/candidate resolver must never widen the policy-allowed action space."""
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="tool_a"))
        registry.register(ToolDefinition(name="tool_b"))
        registry.register_equivalence("tool_a", ["tool_b"])

        resolver = DeterministicCandidateResolver(registry)

        # Context explicitly restricts allowed tools to ["tool_a"]
        state = ExecutionState(context={"allowed_tools": ["tool_a"]})
        candidates = resolver.resolve(ExecutableAction(tool="tool_a"), state)

        # Even though tool_b is declared equivalent, policy restricts to tool_a only
        assert [c.tool for c in candidates] == ["tool_a"]


class TestExecutionEnginePipeline:
    def test_end_to_end_pipeline_success(self):
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="multiply",
                executable=lambda x, y: x * y,
                schema={"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}},
                risk_class="low",
            )
        )
        sink = TraceSink()
        engine = ExecutionEngine(registry=registry, trace_sink=sink)

        proposal = ExecutableAction(
            tool="multiply",
            arguments={"x": "6", "y": "7"},  # String integers should be safely coerced
        )

        result = engine.execute(proposal)
        assert result == 42
        assert len(sink.traces) == 1

        trace = sink.traces[0]
        assert trace.resolved_tool == "multiply"
        assert trace.resolved_arguments == {"x": 6, "y": 7}
        assert trace.decision == "corrected_and_executed"
        assert trace.outcome == "success"
        assert "Coerced 'x': '6' -> 6" in trace.corrections[0]

    def test_end_to_end_pipeline_denies_unauthorized_tool(self):
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="delete_all", permissions=["root:super"])
        )
        sink = TraceSink()
        engine = ExecutionEngine(registry=registry, trace_sink=sink)

        proposal = ExecutableAction(tool="delete_all")
        state = ExecutionState(permissions=set())

        with pytest.raises(VeyraBoundaryError) as exc_info:
            engine.execute(proposal, state)

        assert exc_info.value.classification.kind == FailureKind.AUTHORIZATION_ERROR
        assert len(sink.traces) == 1
        assert sink.traces[0].decision == "deny"
        assert sink.traces[0].outcome == "failure"
