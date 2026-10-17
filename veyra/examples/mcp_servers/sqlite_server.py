"""External real MCP server 1: Database SQLite MCP server (non-MCPAgentBench)."""

import json
import sqlite3
import sys

def main():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, balance REAL)")
    cursor.execute("INSERT INTO users (id, name, balance) VALUES (1, 'Alice', 100.0)")
    conn.commit()

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
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sqlite-mcp-server", "version": "1.0.0"},
                },
            }
            print(json.dumps(resp), flush=True)
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "sqlite_query",
                            "description": "Execute a SELECT query against the SQLite database.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["sql"],
                                "properties": {"sql": {"type": "string"}},
                            },
                        },
                        {
                            "name": "sqlite_execute",
                            "description": "Execute an INSERT/UPDATE mutation against SQLite.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["sql"],
                                "properties": {"sql": {"type": "string"}},
                            },
                        },
                    ]
                },
            }
            print(json.dumps(resp), flush=True)
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            sql = args.get("sql", "")

            try:
                cursor.execute(sql)
                if name == "sqlite_query":
                    rows = cursor.fetchall()
                    res_content = str(rows)
                else:
                    conn.commit()
                    res_content = f"Rows affected: {cursor.rowcount}"
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": res_content}],
                        "isError": False,
                    },
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {e}"}],
                        "isError": True,
                    },
                }
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
