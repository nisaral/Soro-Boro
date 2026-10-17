"""MCP-Native Agent Integration (Section 8).

Demonstrates zero-rewrite integration of an MCP-native client/agent with Veyra:
existing MCP agent
+
one Veyra middleware layer
without rewriting the agent loop or MCP protocol communication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import VeyraResolver
from veyra.resolution.types import ResolutionDecision


class MockMCPClient:
    """Standard MCP client conforming to the Model Context Protocol specification."""

    def __init__(self, server_endpoints: dict[str, Any]):
        self.server_endpoints = server_endpoints
        self.call_history: list[dict[str, Any]] = []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Direct call to an MCP server tool."""
        self.call_history.append({"tool": name, "args": arguments})
        handler = self.server_endpoints.get(name)
        if handler is None:
            raise KeyError(f"MCP Tool not found: {name}")
        return handler(arguments)


class VeyraMCPInterceptor:
    """MCP-Native Boundary Interceptor.

    Wraps standard `call_tool` protocol method transparently:
    Intercepts proposed MCP tool call -> resolves contract / permissions / replicas -> dispatches to MCP server.
    """

    def __init__(self, mcp_client: MockMCPClient, registry: ToolRegistry):
        self.client = mcp_client
        self.registry = registry
        self.resolver = VeyraResolver(registry)

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        state: ExecutionState | None = None,
    ) -> dict[str, Any]:
        exec_state = state or ExecutionState(agent="mcp_agent")
        proposal = ExecutableAction(tool=name, arguments=arguments, metadata={"protocol": "mcp"})

        # Resolve through Veyra execution layer
        resolution = self.resolver.resolve(proposal, exec_state)

        if resolution.decision == ResolutionDecision.DENY.value or resolution.selected_candidate is None:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"[Veyra Policy Denied] {resolution.reason}"}],
            }

        cand = resolution.selected_candidate
        # Dispatch to MCP client
        raw_result = self.client.call_tool(cand.tool, cand.arguments)
        return {
            "isError": False,
            "content": [{"type": "text", "text": json.dumps(raw_result)}],
            "metadata": {
                "resolved_tool": cand.tool,
                "intervened": cand.tool != name,
                "risk_class": resolution.risk_level,
            },
        }


def demo_mcp_integration() -> dict[str, Any]:
    """Demonstrates MCP agent using Veyra MCP interceptor with minimal code changes."""
    # MCP server handlers
    def mcp_unhealthy_replica(args: dict[str, Any]):
        raise RuntimeError("MCP server replica timeout 504")

    def mcp_healthy_replica(args: dict[str, Any]):
        return {"result": "success", "data": [1, 2, 3], "source": "mcp_replica_v2"}

    mcp_endpoints = {
        "postgres_query_v1": mcp_unhealthy_replica,
        "postgres_query_v2": mcp_healthy_replica,
    }

    client = MockMCPClient(mcp_endpoints)

    # Tool registry declarations
    reg = ToolRegistry()
    reg.register(ToolDefinition(name="postgres_query_v1", protocol="mcp", healthy=False, side_effect_class="read_only"))
    reg.register(ToolDefinition(name="postgres_query_v2", protocol="mcp", healthy=True, side_effect_class="read_only"))
    reg.register_equivalence("postgres_query_v1", ["postgres_query_v1", "postgres_query_v2"])

    # 1. Direct MCP call fails
    direct_failed = False
    try:
        client.call_tool("postgres_query_v1", {"sql": "SELECT 1;"})
    except RuntimeError:
        direct_failed = True

    # 2. Veyra-intercepted MCP call succeeds via healthy equivalent
    interceptor = VeyraMCPInterceptor(client, reg)
    result = interceptor.call_tool("postgres_query_v1", {"sql": "SELECT 1;"})

    return {
        "direct_mcp_failed": direct_failed,
        "intercepted_mcp_succeeded": not result.get("isError", True),
        "result": result,
    }


if __name__ == "__main__":
    res = demo_mcp_integration()
    print("MCP Integration Demo Results:")
    print(json.dumps(res, indent=2))
