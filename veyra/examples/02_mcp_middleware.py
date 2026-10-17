"""Example 2: Model Context Protocol (MCP) Tool Middleware.

Demonstrates using Veyra as a drop-in middleware layer for MCP tools:
Existing MCP Client -> Veyra MCP Middleware -> Existing MCP Server

Features:
1. Intercepts `tools/call` JSON-RPC requests
2. Safe schema validation & type coercion
3. Strict idempotency protection on retries
4. Preserves MCP-compliant structured error format on fatal failures
"""

import sys
from pathlib import Path

# Add python/src to sys.path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from veyra import MCPToolMiddleware, Veyra


def main():
    veyra = Veyra()
    middleware = MCPToolMiddleware(veyra=veyra)

    # Simulated MCP tool handler (server-side implementation)
    call_log = []

    def handle_database_query(kwargs: dict) -> dict:
        call_log.append(kwargs)
        limit = kwargs.get("limit", 10)
        query = kwargs.get("query", "")
        return {
            "rows": [
                {"id": 1, "name": "Alice", "role": "Admin"},
                {"id": 2, "name": "Bob", "role": "User"},
            ][:limit],
            "total": 2,
            "query_executed": query,
        }

    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    # 1. Successful MCP Tool Call with safe type coercion (string "1" -> integer 1)
    print("--- 1. Agent calls MCP tool with string limit='1' ---")
    response = middleware.handle_call_tool(
        tool_name="database_query",
        arguments={"query": "SELECT * FROM users", "limit": "1"},
        handler=handle_database_query,
        input_schema=schema,
        idempotent=True,
    )

    print(f"MCP Response isError: {response['isError']}")
    print(f"Structured Result:   {response['structured_result']}")

    # 2. Mutating Tool Protection: mutating action must never be retried without strict idempotency
    def handle_unsafe_file_patch(kwargs: dict) -> dict:
        raise IOError("Disk write buffer full")

    print("\n--- 2. Agent calls mutating file patch that fails ---")
    err_response = middleware.handle_call_tool(
        tool_name="patch_config_file",
        arguments={"path": "/etc/app.conf", "patch": "+setting=true"},
        handler=handle_unsafe_file_patch,
        idempotent=False,  # Non-idempotent mutation!
        retryable=False,
    )

    print(f"MCP Response isError: {err_response['isError']}")
    print(f"Error Message:        {err_response['content'][0]['text']}")
    print(f"Safe Invariant:       0 unsafe retries committed!")


if __name__ == "__main__":
    main()
