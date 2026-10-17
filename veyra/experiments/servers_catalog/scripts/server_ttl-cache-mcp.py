# Stdio MCP Server: In-Memory TTL Cache MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "cache_get",\n    "description": "Get cached item if present",\n    "inputSchema": {\n      "properties": {\n        "key": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "cache_set",\n    "description": "Store item in cache with TTL",\n    "inputSchema": {\n      "properties": {\n        "key": {\n          "type": "string"\n        },\n        "val": {\n          "type": "string"\n        },\n        "ttl": {\n          "type": "integer"\n        }\n      }\n    },\n    "idempotentHint": true\n  },\n  {\n    "name": "cache_purge",\n    "description": "Purge all expired items from cache",\n    "inputSchema": {\n      "properties": {}\n    },\n    "idempotentHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    c = SERVER_STATE.setdefault("cache", {})
    if name == "cache_get":
        return {"val": c.get(args.get("key"))}
    elif name == "cache_set":
        c[args.get("key")] = args.get("val")
        return {"cached": True}
    elif name == "cache_purge":
        return {"purged_count": 0}
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
                    "serverInfo": {"name": "In-Memory TTL Cache MCP Server", "version": "1.0.0"}
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
