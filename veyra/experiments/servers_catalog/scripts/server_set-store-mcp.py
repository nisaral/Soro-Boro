# Stdio MCP Server: Set Deduplication MCP Server
import sys
import json
import os
import sqlite3
import math
import uuid
import re
import datetime
import urllib.parse
import ipaddress

TOOLS = json.loads('[\n  {\n    "name": "list_elements",\n    "description": "List all members of set",\n    "inputSchema": {\n      "properties": {}\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "add_element",\n    "description": "Add element to set (idempotent set deduplication)",\n    "inputSchema": {\n      "properties": {\n        "item": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  },\n  {\n    "name": "remove_element",\n    "description": "Remove element from set",\n    "inputSchema": {\n      "properties": {\n        "item": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    s = SERVER_STATE.setdefault("set", set())
    if name == "list_elements":
        return {"items": list(s)}
    elif name == "add_element":
        s.add(args.get("item", ""))
        return {"status": "added", "size": len(s)}
    elif name == "remove_element":
        s.discard(args.get("item", ""))
        return {"status": "removed", "size": len(s)}
    return {}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "Set Deduplication MCP Server", "version": "1.0.0"}
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            try:
                out = handle_call(name, args)
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(out)}],
                        "isError": False
                    }
                }
            except Exception as e:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(e)}],
                        "isError": True
                    }
                }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
