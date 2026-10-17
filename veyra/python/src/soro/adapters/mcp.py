"""MCP protocol adapter."""

from __future__ import annotations
from typing import Any, Dict

class MCPAdapter:
    """Adapts MCP tool definitions into Veyra ToolDefinitions."""

    @staticmethod
    def adapt_tool(mcp_tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": mcp_tool_schema.get("name"),
            "description": mcp_tool_schema.get("description", ""),
            "schema": mcp_tool_schema.get("inputSchema", {}),
            "protocol": "mcp",
        }
