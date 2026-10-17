# Stdio MCP Server: Color Spaces & Palette MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "hex_to_rgb",\n    "description": "Convert hex color to RGB tuple",\n    "inputSchema": {\n      "properties": {\n        "hex_color": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "rgb_to_hsl",\n    "description": "Convert RGB to HSL values",\n    "inputSchema": {\n      "properties": {\n        "r": {\n          "type": "integer"\n        },\n        "g": {\n          "type": "integer"\n        },\n        "b": {\n          "type": "integer"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "calculate_contrast",\n    "description": "Calculate WCAG contrast ratio between two colors",\n    "inputSchema": {\n      "properties": {\n        "color1": {\n          "type": "string"\n        },\n        "color2": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "hex_to_rgb":
        return {"r": 255, "g": 255, "b": 255}
    elif name == "rgb_to_hsl":
        return {"h": 0, "s": 0, "l": 100}
    elif name == "calculate_contrast":
        return {"contrast_ratio": 21.0}
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
                    "serverInfo": {"name": "Color Spaces & Palette MCP Server", "version": "1.0.0"}
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
