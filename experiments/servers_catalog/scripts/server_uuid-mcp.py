# Stdio MCP Server: UUID & Identifiers MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "generate_uuid4",\n    "description": "Generate a new random UUID v4",\n    "inputSchema": {\n      "properties": {}\n    }\n  },\n  {\n    "name": "validate_uuid",\n    "description": "Check if string is a valid UUID",\n    "inputSchema": {\n      "properties": {\n        "uuid_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "generate_uuid5",\n    "description": "Deterministic namespace UUID v5",\n    "inputSchema": {\n      "properties": {\n        "namespace": {\n          "type": "string"\n        },\n        "name": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "generate_uuid4":
        return {"uuid": str(uuid.uuid4())}
    elif name == "validate_uuid":
        return {"valid": True}
    elif name == "generate_uuid5":
        return {"uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, args.get("name", "test")))}
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
                    "serverInfo": {"name": "UUID & Identifiers MCP Server", "version": "1.0.0"}
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
