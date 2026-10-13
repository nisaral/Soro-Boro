# Stdio MCP Server: JSON Schema & Query MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "validate_json",\n    "description": "Validate JSON object against schema",\n    "inputSchema": {\n      "properties": {\n        "json_str": {\n          "type": "string"\n        },\n        "schema_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "format_json",\n    "description": "Format or pretty print JSON string",\n    "inputSchema": {\n      "properties": {\n        "raw_json": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "diff_json_objects",\n    "description": "Compute structural diff between two JSON objects",\n    "inputSchema": {\n      "properties": {\n        "obj_a": {\n          "type": "object"\n        },\n        "obj_b": {\n          "type": "object"\n        }\n      }\n    },\n    "readOnlyHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "validate_json":
        return {"valid": True}
    elif name == "format_json":
        return {"formatted": "{}"}
    elif name == "diff_json_objects":
        return {"differences": []}
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
                    "serverInfo": {"name": "JSON Schema & Query MCP Server", "version": "1.0.0"}
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
