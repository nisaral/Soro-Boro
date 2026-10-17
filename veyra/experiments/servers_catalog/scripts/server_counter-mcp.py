# Stdio MCP Server: Stateful Counter MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "read_count",\n    "description": "Read current counter value",\n    "inputSchema": {\n      "properties": {}\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "increment_count",\n    "description": "Increment counter by delta",\n    "inputSchema": {\n      "properties": {\n        "delta": {\n          "type": "integer"\n        }\n      }\n    }\n  },\n  {\n    "name": "set_count",\n    "description": "Set counter to specific value",\n    "inputSchema": {\n      "properties": {\n        "val": {\n          "type": "integer"\n        }\n      }\n    },\n    "idempotentHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    cnt = SERVER_STATE.get("count", 0)
    if name == "read_count":
        return {"count": cnt}
    elif name == "increment_count":
        SERVER_STATE["count"] = cnt + args.get("delta", 1)
        return {"new_count": SERVER_STATE["count"]}
    elif name == "set_count":
        SERVER_STATE["count"] = args.get("val", 0)
        return {"count": SERVER_STATE["count"]}
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
                    "serverInfo": {"name": "Stateful Counter MCP Server", "version": "1.0.0"}
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
