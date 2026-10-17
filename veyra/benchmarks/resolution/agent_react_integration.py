"""ReAct Agent Integration (Section 8).

Demonstrates zero-rewrite integration of an existing ReAct agent with Veyra:
existing ReAct agent
+
one Veyra middleware layer
without rewriting the agent loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import VeyraResolver
from veyra.resolution.types import ResolutionDecision


class LegacyReActAgent:
    """Standard, unmodified ReAct-style agent loop."""

    def __init__(self, tools_available: list[str]):
        self.tools_available = tools_available
        self.history: list[dict[str, Any]] = []

    def plan_step(self, task: str) -> dict[str, Any]:
        """Proposes thought and action using standard ReAct pattern."""
        if not self.history:
            return {
                "thought": "I need to query customer details to solve task.",
                "action": "legacy_crm_query",
                "action_input": {"customer_id": "cust_1001"},
            }
        last_obs = self.history[-1].get("observation", {})
        return {
            "thought": f"Got observation {last_obs}, concluding task.",
            "final_answer": f"Processed successfully: {last_obs}",
        }

    def run_raw(self, task: str, tool_executor: Callable[[str, dict[str, Any]], Any]) -> str:
        """Original execution loop: calls tools directly."""
        for step in range(5):
            plan = self.plan_step(task)
            if "final_answer" in plan:
                return plan["final_answer"]

            tool_name = plan["action"]
            args = plan["action_input"]
            obs = tool_executor(tool_name, args)
            self.history.append({"step": step, "action": tool_name, "observation": obs})

        return "Max steps reached"


class VeyraReActMiddleware:
    """Minimal Veyra middleware layer wrapping any existing tool executor without touching the agent."""

    def __init__(self, registry: ToolRegistry):
        self.resolver = VeyraResolver(registry)

    def wrap_executor(
        self,
        base_executor: Callable[[str, dict[str, Any]], Any],
        state: ExecutionState | None = None,
    ) -> Callable[[str, dict[str, Any]], Any]:
        """Wrap the executor in place so the agent loop remains completely untouched."""
        exec_state = state or ExecutionState(agent="react_agent")

        def intercepted_executor(tool_name: str, args: dict[str, Any]) -> Any:
            proposal = ExecutableAction(tool=tool_name, arguments=args)
            # Resolve through Veyra execution layer
            resolution = self.resolver.resolve(proposal, exec_state)

            if resolution.decision == ResolutionDecision.DENY.value or resolution.selected_candidate is None:
                raise PermissionError(f"[Veyra Denied] {resolution.reason}")

            cand = resolution.selected_candidate
            # Execute safely on resolved candidate
            return base_executor(cand.tool, cand.arguments)

        return intercepted_executor


def demo_react_integration() -> dict[str, Any]:
    """Demonstrates existing ReAct agent + one Veyra middleware layer."""
    # Setup registry with declared equivalents and health status
    reg = ToolRegistry()
    # legacy_crm_query is degraded/unhealthy, modern_crm_query is healthy
    reg.register(ToolDefinition(name="legacy_crm_query", healthy=False, latency_ms=80.0, side_effect_class="read_only"))
    reg.register(ToolDefinition(name="modern_crm_query", healthy=True, latency_ms=10.0, side_effect_class="read_only"))
    reg.register_equivalence("legacy_crm_query", ["legacy_crm_query", "modern_crm_query"])

    def backend_api(tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "legacy_crm_query":
            raise ConnectionResetError("Legacy service timeout / 503")
        return {"name": "Alice Corp", "status": "ACTIVE", "resolved_tool": tool_name}

    # 1. Unmodified Agent + Unmodified Executor (Raw fails)
    raw_agent = LegacyReActAgent(tools_available=["legacy_crm_query"])
    raw_failed = False
    try:
        raw_agent.run_raw("Query customer cust_1001", backend_api)
    except ConnectionResetError:
        raw_failed = True

    # 2. Existing Agent + 1 Veyra Middleware Layer (Zero changes to LegacyReActAgent!)
    veyra_mw = VeyraReActMiddleware(reg)
    protected_executor = veyra_mw.wrap_executor(backend_api)

    protected_agent = LegacyReActAgent(tools_available=["legacy_crm_query"])
    final_output = protected_agent.run_raw("Query customer cust_1001", protected_executor)

    return {
        "raw_failed_due_to_unhealthy_tool": raw_failed,
        "protected_agent_succeeded": "Alice Corp" in final_output,
        "final_output": final_output,
        "agent_code_modified": False,
    }


if __name__ == "__main__":
    res = demo_react_integration()
    print("ReAct Integration Demo Results:")
    print(json.dumps(res, indent=2))
