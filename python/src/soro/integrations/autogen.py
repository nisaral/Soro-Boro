"""AutoGen integration for soro.

Provides function and MCP wrapper compatibility for AutoGen tool calls.
"""

from __future__ import annotations

from typing import Any, Callable, Dict


class VeyraAutoGenAdapter:
    """Tool adapter for AutoGen agents."""

    def __init__(self, veyra_instance: Any):
        self.veyra = veyra_instance

    def register_function(self, fn: Callable[..., Any], name: str | None = None) -> Callable[..., Any]:
        """Wrap and register a function for AutoGen agent execution."""
        return self.soro.wrap(fn, name=name)

    def wrap_mcp_client(self, mcp_client: Any) -> Any:
        """Wrap MCP client for AutoGen agents."""
        return self.soro.wrap_mcp(mcp_client)
