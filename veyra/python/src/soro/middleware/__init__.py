"""Veyra Middleware package for wrapping functions, MCP servers, HTTP clients, and AI agent frameworks."""

from soro.middleware.function import FunctionWrapper
from soro.middleware.mcp import MCPWrapper, VeyraMCPProxy
from soro.middleware.http import HTTPWrapper
from soro.middleware.agent import AgentWrapper

__all__ = [
    "FunctionWrapper",
    "MCPWrapper",
    "VeyraMCPProxy",
    "HTTPWrapper",
    "AgentWrapper",
]
