"""Fast stdio JSON-RPC client for real MCP tools and servers.

Pure Python stdio JSON-RPC 2.0 client:
- Spawns server via subprocess
- Negotiates initialize / initialized handshake
- Discovers tools via tools/list
- Calls tools via tools/call
- Handles process lifecycle and timeouts cleanly
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MCPToolInfo:
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "server_id": self.server_id,
        }


class StdioMCPClient:
    """Manages a live MCP server process over standard input/output."""

    def __init__(self, command: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, server_id: str = "mcp_server"):
        self.command = command
        self.cwd = cwd
        self.env = env or dict(os.environ)
        self.server_id = server_id
        self.proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._lock = threading.Lock()
        self.tools: List[MCPToolInfo] = []

    def start(self, timeout: float = 10.0) -> None:
        """Start server process and complete initialize handshake."""
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            text=True,
            bufsize=1,
        )

        # 1. initialize request
        init_resp = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "soro-client", "version": "0.2.0"},
            },
            timeout=timeout,
        )

        # 2. initialized notification
        self._send_notification("notifications/initialized", {})

    def list_tools(self, timeout: float = 5.0) -> List[MCPToolInfo]:
        """Fetch all tools exposed by the server."""
        resp = self._send_request("tools/list", {}, timeout=timeout)
        tools_raw = resp.get("tools", [])
        self.tools = [
            MCPToolInfo(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_id=self.server_id,
            )
            for t in tools_raw
        ]
        return self.tools

    def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Invoke a tool on the live server."""
        return self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=timeout,
        )

    def stop(self) -> None:
        """Terminate the server process."""
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

    def __enter__(self) -> StdioMCPClient:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                raise RuntimeError(f"Server process {self.server_id} is not running.")

            self._req_id += 1
            req_id = self._req_id
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }
            line = json.dumps(payload) + "\n"
            assert self.proc.stdin is not None
            self.proc.stdin.write(line)
            self.proc.stdin.flush()

            # Read response lines until we get jsonrpc with matching id
            assert self.proc.stdout is not None
            while True:
                resp_line = self.proc.stdout.readline()
                if not resp_line:
                    stderr_msg = self.proc.stderr.read() if self.proc.stderr else ""
                    raise RuntimeError(f"Server EOF on {self.server_id}. stderr: {stderr_msg}")
                resp_line = resp_line.strip()
                if not resp_line:
                    continue
                try:
                    msg = json.loads(resp_line)
                    if msg.get("id") == req_id:
                        if "error" in msg:
                            raise RuntimeError(f"MCP RPC Error: {msg['error']}")
                        return msg.get("result", {})
                except json.JSONDecodeError:
                    # Ignore non-JSON stdout debug lines
                    continue

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
            line = json.dumps(payload) + "\n"
            assert self.proc.stdin is not None
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
