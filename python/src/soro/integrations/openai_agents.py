"""OpenAI Agents SDK integration for soro.

Interposes Veyra execution boundary control on OpenAI Agents function tools and MCP tools while preserving tracing correlation and decision metadata.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Dict, List, Optional


class VeyraOpenAIAgentsAdapter:
    """Adapter for OpenAI Agents SDK tool execution interception."""

    def __init__(self, veyra_instance: Any):
        self.veyra = veyra_instance

    def wrap_tool(self, tool_fn: Callable[..., Any], name: Optional[str] = None) -> Callable[..., Any]:
        """Wrap an OpenAI function tool with Veyra contract validation & execution safety."""
        tool_name = name or getattr(tool_fn, "__name__", "openai_tool")

        @functools.wraps(tool_fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.soro.call(
                tool_name=tool_name,
                arguments=kwargs or (args[0] if args and isinstance(args[0], dict) else {}),
                fn=tool_fn,
            )

        wrapper.__veyra_wrapped__ = True
        return wrapper

    def wrap_mcp_tool(self, mcp_client: Any) -> Any:
        """Wrap OpenAI Agents MCP client tool runner."""
        return self.soro.wrap_mcp(mcp_client)
