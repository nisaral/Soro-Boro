"""Real MCP Catalogs Loader.

Loads 3 real MCP environments from third_party/MCPAgentBench/servers:
1. Filesystem Catalog (search_and_read_files, patch_file)
2. Database Catalog (connect_database, Connect_SQL_Server)
3. API Services Catalog (make_api_request, weather_data_retriever)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class MCPToolDescriptor:
    name: str
    catalog: str
    handler: Callable[..., Any]
    input_schema: dict[str, Any]
    is_idempotent: bool
    is_retryable: bool
    risk_class: str
    declared_equivalents: list[str]


def find_mcp_servers_dir() -> Path:
    """Locate the third_party/MCPAgentBench/servers directory."""
    env_dir = os.environ.get("MCP_BENCH_SERVERS_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)

    # Search upwards from current file
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        candidate = parent / "third_party" / "MCPAgentBench" / "servers"
        if candidate.is_dir():
            return candidate
        # Also check sibling of veyra
        candidate2 = parent.parent / "third_party" / "MCPAgentBench" / "servers"
        if candidate2.is_dir():
            return candidate2

    raise FileNotFoundError("Could not locate third_party/MCPAgentBench/servers directory")


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class RealMCPCatalogManager:
    """Manages the 3 real MCP server environments."""

    def __init__(self, servers_dir: Path | None = None):
        self.servers_dir = servers_dir or find_mcp_servers_dir()
        self.tools: dict[str, MCPToolDescriptor] = {}
        self._load_all_catalogs()

    def _load_all_catalogs(self) -> None:
        # Add servers dir to sys.path so modules can resolve local imports if needed
        s_path = str(self.servers_dir)
        if s_path not in sys.path:
            sys.path.insert(0, s_path)

        # 1. Filesystem Catalog
        s_files_mod = _load_module("search_and_read_files", self.servers_dir / "search_and_read_files.py")
        p_file_mod = _load_module("patch_file", self.servers_dir / "patch_file.py")

        self.tools["search_and_read_files"] = MCPToolDescriptor(
            name="search_and_read_files",
            catalog="filesystem",
            handler=s_files_mod.search_and_read_files,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            is_idempotent=True,
            is_retryable=True,
            risk_class="low",
            declared_equivalents=["find_files"],
        )

        self.tools["patch_file"] = MCPToolDescriptor(
            name="patch_file",
            catalog="filesystem",
            handler=p_file_mod.patch_file,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "changes_path": {"type": "string"},
                },
                "required": ["path", "changes_path"],
            },
            is_idempotent=False,
            is_retryable=False,
            risk_class="medium",
            declared_equivalents=["apply_patch"],
        )

        # 2. Database Catalog
        c_db_mod = _load_module("connect_database", self.servers_dir / "connect_database.py")
        c_sql_mod = _load_module("Connect_SQL_Server", self.servers_dir / "Connect_SQL_Server.py")

        self.tools["connect_database"] = MCPToolDescriptor(
            name="connect_database",
            catalog="database",
            handler=c_db_mod.connect_database,
            input_schema={
                "type": "object",
                "properties": {"database_name": {"type": "string"}},
                "required": ["database_name"],
            },
            is_idempotent=True,
            is_retryable=True,
            risk_class="low",
            declared_equivalents=["get_db_connection"],
        )

        self.tools["Connect_SQL_Server"] = MCPToolDescriptor(
            name="Connect_SQL_Server",
            catalog="database",
            handler=c_sql_mod.Connect_SQL_Server,
            input_schema={
                "type": "object",
                "properties": {"connectionString": {"type": "integer"}},
                "required": ["connectionString"],
            },
            is_idempotent=True,
            is_retryable=True,
            risk_class="low",
            declared_equivalents=["connect_sql"],
        )

        # 3. External API Catalog
        api_mod = _load_module("make_api_request", self.servers_dir / "make_api_request.py")
        weather_mod = _load_module("weather_data_retriever", self.servers_dir / "weather_data_retriever.py")

        self.tools["make_api_request"] = MCPToolDescriptor(
            name="make_api_request",
            catalog="api",
            handler=api_mod.make_api_request,
            input_schema={
                "type": "object",
                "properties": {
                    "apiName": {"type": "string"},
                    "url": {"type": "string"},
                    "endpoint": {"type": "string"},
                },
                "required": ["apiName", "url", "endpoint"],
            },
            is_idempotent=True,
            is_retryable=True,
            risk_class="low",
            declared_equivalents=["http_get"],
        )

        self.tools["weather_data_retriever"] = MCPToolDescriptor(
            name="weather_data_retriever",
            catalog="api",
            handler=weather_mod.weather_data_retriever,
            input_schema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "range": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["start_date", "end_date", "range", "location"],
            },
            is_idempotent=True,
            is_retryable=True,
            risk_class="low",
            declared_equivalents=["get_weather"],
        )

    def get_tool(self, name: str) -> MCPToolDescriptor | None:
        return self.tools.get(name)

    def list_tools(self, catalog: str | None = None) -> list[MCPToolDescriptor]:
        if catalog:
            return [t for t in self.tools.values() if t.catalog == catalog]
        return list(self.tools.values())
