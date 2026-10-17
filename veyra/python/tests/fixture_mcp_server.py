"""Lightweight Mock MCP Server for Soro Audit Oracle Regression Tests.

Runs over stdio and responds to standard JSON-RPC 2.0 messages:
- initialize
- notifications/initialized
- tools/list
- tools/call
"""

import json
import os
import sys


def handle_request(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture-audit-server", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "append_log",
                        "description": "Appends a line to log.txt. Erroneously claims idempotentHint=True.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"line": {"type": "string"}},
                            "required": ["line"],
                        },
                        "annotations": {
                            "readOnlyHint": False,
                            "idempotentHint": True,  # False claim: appending is non-idempotent
                            "destructiveHint": False,
                            "openWorldHint": False,
                        },
                    },
                    {
                        "name": "overwrite_config",
                        "description": "Overwrites config.json. Verified idempotent write.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                        # Omits idempotentHint: tests optimization detection
                    },
                    {
                        "name": "get_status",
                        "description": "Returns current status without modifying disk. Verified read-only.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                        },
                        # Omits readOnlyHint: tests confirmation fatigue detection
                    },
                    {
                        "name": "false_read_only_tool",
                        "description": "Claims readOnlyHint=True, but writes to a file.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"tag": {"type": "string"}},
                        },
                        "annotations": {
                            "readOnlyHint": True,  # False claim: mutates disk
                            "openWorldHint": False,
                        },
                    },
                    {
                        "name": "failing_validation_tool",
                        "description": "Fails execution with isError=True.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"key": {"type": "string"}},
                            "required": ["key"],
                        },
                    },
                    {
                        "name": "delete_backup",
                        "description": "Deletes old backup files. Omits destructiveHint.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                        # Omits destructiveHint: tests spec default destructiveHint=True
                    },
                ]
            },
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "append_log":
            line = args.get("line", "entry\n")
            with open("log.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")
            # Returns identical acknowledgment on both calls
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "OK: appended"}], "isError": False},
            }

        if tool_name == "overwrite_config":
            val = args.get("value", "default")
            with open("config.json", "w", encoding="utf-8") as f:
                f.write(json.dumps({"val": val}))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "OK: written"}], "isError": False},
            }

        if tool_name == "get_status":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "status: ready"}], "isError": False},
            }

        if tool_name == "false_read_only_tool":
            with open("covert_mutation.txt", "a", encoding="utf-8") as f:
                f.write("mutated\n")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "read done"}], "isError": False},
            }

        if tool_name == "failing_validation_tool":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "Validation Error: invalid key"}], "isError": True},
            }

        if tool_name == "delete_backup":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": "Backup purged"}], "isError": False},
            }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            if res is not None:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
