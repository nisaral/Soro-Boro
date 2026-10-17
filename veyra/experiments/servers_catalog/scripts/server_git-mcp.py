# Stdio MCP Server: Git Repository MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "git_status",\n    "description": "Read current git working tree status",\n    "inputSchema": {\n      "properties": {}\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "git_log",\n    "description": "Read commit history",\n    "inputSchema": {\n      "properties": {\n        "limit": {\n          "type": "integer"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "git_tag_force",\n    "description": "Force tag a commit ref",\n    "inputSchema": {\n      "properties": {\n        "tag": {\n          "type": "string"\n        },\n        "ref": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  },\n  {\n    "name": "git_commit_change",\n    "description": "Commit changes to git repository",\n    "inputSchema": {\n      "properties": {\n        "message": {\n          "type": "string"\n        }\n      }\n    }\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "git_status":
        return {"branch": "main", "clean": True}
    elif name == "git_log":
        return [{"sha": "abc1234", "message": "initial commit"}]
    elif name == "git_tag_force":
        SERVER_STATE.setdefault("tags", {})[args.get("tag")] = args.get("ref")
        return {"tag": args.get("tag"), "ref": args.get("ref")}
    elif name == "git_commit_change":
        SERVER_STATE.setdefault("commits", []).append(args.get("message"))
        return {"new_commit": f"commit_{len(SERVER_STATE['commits'])}"}
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
                    "serverInfo": {"name": "Git Repository MCP Server", "version": "1.0.0"}
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
