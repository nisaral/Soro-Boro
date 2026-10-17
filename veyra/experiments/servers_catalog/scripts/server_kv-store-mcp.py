# Stdio MCP Server: Key-Value Store MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "get_val",\n    "description": "Retrieve value by key",\n    "inputSchema": {\n      "properties": {\n        "key": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "put_val",\n    "description": "Store key-value pair idempotently",\n    "inputSchema": {\n      "properties": {\n        "key": {\n          "type": "string"\n        },\n        "value": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  },\n  {\n    "name": "delete_val",\n    "description": "Delete key from store",\n    "inputSchema": {\n      "properties": {\n        "key": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    kv = SERVER_STATE.setdefault("kv", {})
    if name == "get_val":
        return {"val": kv.get(args.get("key"))}
    elif name == "put_val":
        kv[args.get("key")] = args.get("value")
        return {"status": "stored"}
    elif name == "delete_val":
        kv.pop(args.get("key"), None)
        return {"status": "deleted"}
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
                    "serverInfo": {"name": "Key-Value Store MCP Server", "version": "1.0.0"}
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
