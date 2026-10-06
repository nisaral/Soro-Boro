"""Veyra Model Context Protocol (MCP) Tool Middleware.

Architecture:
Existing MCP Client -> Veyra MCP Middleware -> Existing MCP Server

Intercepts `tools/call` JSON-RPC requests:
1. Validates arguments against MCP tool's `inputSchema`.
2. Applies provably safe normalizations (types, dates, enums).
3. Safely retries transient/rate-limit errors for declared idempotent tools.
4. Returns structured error messages on unresolvable failures.
5. Emits standard Veyra execution traces.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from veyra.boundary.interceptor import Veyra
from veyra.boundary.taxonomy import VeyraBoundaryError


class MCPToolMiddleware:
    """Middleware wrapper for MCP tool execution."""

    def __init__(self, veyra: Veyra | None = None):
        self.veyra = veyra or Veyra()

    def handle_call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        input_schema: dict[str, Any] | None = None,
        retryable: bool = False,
        idempotent: bool = False,
    ) -> dict[str, Any]:
        """Intercept and execute an MCP call_tool request."""
        try:
            # Veyra resolves arguments and handles safe execution
            result = self.veyra.call(
                tool_name=tool_name,
                arguments=arguments,
                fn=lambda **kwargs: handler(kwargs),
                schema=input_schema,
                retryable=retryable,
                idempotent=idempotent,
            )
            return {
                "isError": False,
                "content": [{"type": "text", "text": str(result)}],
                "structured_result": result,
            }
        except VeyraBoundaryError as vbe:
            # Return structured error to the agent according to MCP spec
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool execution failed: {vbe.classification.message}",
                    }
                ],
                "error_classification": vbe.classification.to_dict(),
            }
        except Exception as exc:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {exc}"}],
            }
