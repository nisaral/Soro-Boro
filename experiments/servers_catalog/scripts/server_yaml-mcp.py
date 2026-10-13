# Stdio MCP Server: YAML Parser MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "validate_yaml",\n    "description": "Check if YAML is valid",\n    "inputSchema": {\n      "properties": {\n        "yaml_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "yaml_to_json",\n    "description": "Convert YAML into JSON object",\n    "inputSchema": {\n      "properties": {\n        "yaml_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "json_to_yaml",\n    "description": "Convert JSON object into YAML string",\n    "inputSchema": {\n      "properties": {\n        "json_obj": {\n          "type": "object"\n        }\n      }\n    },\n    "readOnlyHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "validate_yaml":
        return {"valid": True}
    elif name == "yaml_to_json":
        return {"data": {"foo": "bar"}}
    elif name == "json_to_yaml":
        return {"yaml": "foo: bar\n"}
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
                    "serverInfo": {"name": "YAML Parser MCP Server", "version": "1.0.0"}
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
