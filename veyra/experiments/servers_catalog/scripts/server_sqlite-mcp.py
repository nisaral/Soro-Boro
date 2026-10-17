# Stdio MCP Server: SQLite Database MCP Server
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

TOOLS = json.loads('[\n  {\n    "name": "query_read",\n    "description": "Execute a SELECT query against SQLite database",\n    "inputSchema": {\n      "properties": {\n        "query": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "get_table_schema",\n    "description": "Describe schema of a table",\n    "inputSchema": {\n      "properties": {\n        "table": {\n          "type": "string"\n        }\n      }\n    },\n    "readOnlyHint": true\n  },\n  {\n    "name": "upsert_row",\n    "description": "Idempotently insert or update record",\n    "inputSchema": {\n      "properties": {\n        "table": {\n          "type": "string"\n        },\n        "key": {\n          "type": "string"\n        },\n        "val": {\n          "type": "string"\n        }\n      }\n    },\n    "idempotentHint": true\n  },\n  {\n    "name": "insert_log_row",\n    "description": "Insert a mutating audit log record",\n    "inputSchema": {\n      "properties": {\n        "message": {\n          "type": "string"\n        }\n      }\n    }\n  }\n]')

# Local server state
SERVER_STATE = {}

def handle_call(name, args):
    if name == "query_read":
        return [{"col": "val"}]
    elif name == "get_table_schema":
        return {"columns": ["id", "data"]}
    elif name == "upsert_row":
        SERVER_STATE.setdefault("rows", {})[args.get("key")] = args.get("val")
        return {"status": "upserted"}
    elif name == "insert_log_row":
        SERVER_STATE.setdefault("logs", []).append(args.get("message"))
        return {"log_id": len(SERVER_STATE["logs"])}
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
                    "serverInfo": {"name": "SQLite Database MCP Server", "version": "1.0.0"}
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
