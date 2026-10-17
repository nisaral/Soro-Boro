"""Simulated standalone stdio MCP server for notification dispatch."""

import json
import sys

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
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "notify-mcp-server", "version": "1.0.0"},
                },
            }
            print(json.dumps(resp), flush=True)
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "send_alert",
                            "description": "Send urgent push alert notification to user device.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["channel", "message"],
                                "properties": {
                                    "channel": {"type": "string"},
                                    "message": {"type": "string"},
                                },
                            },
                        }
                    ]
                },
            }
            print(json.dumps(resp), flush=True)
        elif method == "tools/call":
            params = req.get("params", {})
            args = params.get("arguments", {})
            chan = args.get("channel", "general")
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Alert dispatched to #{chan}"}],
                    "isError": False,
                },
            }
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
