"""Simulated standalone stdio MCP server for weather querying."""

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
                    "serverInfo": {"name": "weather-mcp-server", "version": "1.0.0"},
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
                            "name": "get_current_weather",
                            "description": "Get real-time weather temperature and condition by city.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["city"],
                                "properties": {"city": {"type": "string"}},
                            },
                        }
                    ]
                },
            }
            print(json.dumps(resp), flush=True)
        elif method == "tools/call":
            params = req.get("params", {})
            args = params.get("arguments", {})
            city = args.get("city", "Unknown")
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"72F sunny in {city}"}],
                    "isError": False,
                },
            }
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
