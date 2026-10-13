"""MCP (Model Context Protocol) middleware wrapper and Veyra MCP proxy."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("soro.mcp")

class MCPWrapper:
    """Wraps an MCP client to interpose Veyra policy and execution control on tool calls."""

    def __init__(self, veyra_instance: Any, mcp_client: Any):
        self.veyra = veyra_instance
        self.client = mcp_client

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Intersects MCP tool call, validates against Veyra policies, and executes."""
        async def _execute_mcp(**kwargs):
            if hasattr(self.client, "call_tool"):
                res = await self.client.call_tool(name, kwargs)
                return res
            elif hasattr(self.client, "execute_tool"):
                return await self.client.execute_tool(name, kwargs)
            else:
                raise AttributeError("MCP client does not expose a supported tool call method.")

        return self.soro.call(
            tool_name=name,
            arguments=arguments,
            fn=_execute_mcp,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)


class VeyraMCPProxy:
    """Stdio and Streamable HTTP MCP Proxy server.

    Plugs between an MCP client (Agent) and real MCP server:
      Agent -> Veyra MCP Proxy -> Veyra Execution Control -> Real MCP Server
    """

    def __init__(self, veyra_instance: Any, upstream_command: Optional[List[str]] = None, upstream_url: Optional[str] = None):
        self.veyra = veyra_instance
        self.upstream_command = upstream_command
        self.upstream_url = upstream_url

    def handle_request(self, request_json: str) -> str:
        """Synchronously process a JSON-RPC MCP request through soro."""
        try:
            req = json.loads(request_json)
        except Exception as e:
            return json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {e}"}, "id": None})

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/call":
            tool_name = params.get("name", "unknown_mcp_tool")
            tool_args = params.get("arguments", {})

            # Execution proposal through Veyra
            try:
                def _dummy_executor(**args):
                    return {"status": "success", "tool": tool_name, "args": args}

                result = self.soro.call(
                    tool_name=tool_name,
                    arguments=tool_args,
                    fn=_dummy_executor,
                )
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                    "id": req_id,
                })
            except Exception as e:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": f"Veyra execution blocked/failed: {str(e)}"},
                    "id": req_id,
                })
        else:
            # Pass-through negotiation methods (initialize, ping, tools/list)
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "ok", "method": method},
                "id": req_id,
            })
