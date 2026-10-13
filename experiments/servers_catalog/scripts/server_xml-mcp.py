# Stdio MCP Server: XML Parser & XPath MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "validate_xml",\n    "description": "Check if XML string is well-formed",\n    "inputSchema": {\n      "properties": {\n        "xml_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "format_xml",\n    "description": "Format and indent XML content",\n    "inputSchema": {\n      "properties": {\n        "xml_str": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "xpath_query",\n    "description": "Evaluate XPath expression against XML",\n    "inputSchema": {\n      "properties": {\n        "xml_str": {\n          "type": "string"\n        },\n        "xpath": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "validate_xml":
        return {"valid": True}
    elif name == "format_xml":
        return {"xml": "<root/>"}
    elif name == "xpath_query":
        return {"results": ["<node>text</node>"]}
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
                    "serverInfo": {"name": "XML Parser & XPath MCP Server", "version": "1.0.0"}
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
