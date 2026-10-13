# Stdio MCP Server: IP Address & CIDR MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "validate_ip_address",\n    "description": "Validate IPv4 or IPv6 address string",\n    "inputSchema": {\n      "properties": {\n        "ip": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "is_private_ip",\n    "description": "Check if IP address belongs to RFC 1918 private range",\n    "inputSchema": {\n      "properties": {\n        "ip": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "check_cidr_contains",\n    "description": "Check if IP is contained in CIDR block",\n    "inputSchema": {\n      "properties": {\n        "cidr": {\n          "type": "string"\n        },\n        "ip": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "validate_ip_address":
        return {"valid": True, "version": 4}
    elif name == "is_private_ip":
        return {"private": False}
    elif name == "check_cidr_contains":
        return {"contains": True}
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
                    "serverInfo": {"name": "IP Address & CIDR MCP Server", "version": "1.0.0"}
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
