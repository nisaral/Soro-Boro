"""Adapters for MCP, HTTP, and Python execution targets."""

from soro.adapters.mcp import MCPAdapter
from soro.adapters.http import HTTPAdapter
from soro.adapters.python import PythonAdapter

__all__ = ["MCPAdapter", "HTTPAdapter", "PythonAdapter"]
