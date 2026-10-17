"""Example 2: MCP Agent Tool Wrapping with Veyra.

Runnable from fresh checkout.
Demonstrates:
- Wrapping an MCP client call_tool handler
- Transparent boundary validation without changing the agent reasoning loop
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware


class MockMCPClient:
    """Simulates standard MCP client with call_tool method."""

    def call_tool(self, name: str, arguments: dict):
        if name == "calculator.add":
            return {"result": arguments.get("a", 0) + arguments.get("b", 0)}
        elif name == "file.read":
            return {"content": "Sample file data for " + str(arguments.get("path"))}
        raise ValueError(f"Unknown tool: {name}")


class SimpleAgent:
    """Standard ReAct / Tool-using Agent."""

    def __init__(self, mcp_client):
        self.mcp = mcp_client

    def execute_plan(self, tool_name: str, args: dict):
        # The agent reasoning loop is completely unaware of Veyra!
        return self.mcp.call_tool(tool_name, args)


def main():
    print("=== Veyra Drop-In Middleware: MCP Agent Example ===\n")

    raw_mcp = MockMCPClient()
    middleware = VeyraMiddleware(ProductionConfig(mode=Mode.NORMAL))

    # Wrap MCP Client at the boundary
    wrapped_mcp = middleware.wrap_mcp(raw_mcp)

    # Initialize agent with wrapped MCP
    agent = SimpleAgent(mcp_client=wrapped_mcp)

    print("1. Agent executing calculator.add via MCP...")
    res = agent.execute_plan("calculator.add", {"a": 12, "b": 30})
    print(f"Agent received response: {res}\n")

    latest_explanation = middleware.audit_trail[-1]["explanation"]
    print("Veyra Boundary Audit:")
    print(f"  Decision: {latest_explanation['decision']}")
    print(f"  Tool: {latest_explanation['selected_tool']}")
    print(f"  Checks: {latest_explanation['checks']}")
    print("\n=== MCP Agent Example Completed Successfully ===")


if __name__ == "__main__":
    main()
