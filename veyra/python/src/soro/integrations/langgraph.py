"""LangGraph tool execution node wrapper for soro.

Provides a clean tool execution wrapper node for LangGraph workflows without rebuilding its graph model.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


class VeyraLangGraphNode:
    """Tool execution node integration for LangGraph."""

    def __init__(self, veyra_instance: Any, tools: List[Callable[..., Any]]):
        self.veyra = veyra_instance
        self.tools = {getattr(t, "__name__", str(t)): veyra_instance.wrap(t) for t in tools}

    def execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node execution function.

        Expects state to contain 'messages' or 'proposed_action' with tool name and arguments.
        """
        proposed = state.get("proposed_action", {})
        tool_name = proposed.get("tool")
        args = proposed.get("arguments", {})

        if not tool_name or tool_name not in self.tools:
            return {**state, "error": f"Tool '{tool_name}' not found in Veyra LangGraph node"}

        try:
            result = self.tools[tool_name](**args)
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "error": str(e)}

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.execute_node(state)
