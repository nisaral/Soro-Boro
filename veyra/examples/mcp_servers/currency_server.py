"""Simulated standalone stdio MCP server for currency conversion."""

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
                    "serverInfo": {"name": "currency-mcp-server", "version": "1.0.0"},
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
                            "name": "convert_currency",
                            "description": "Convert foreign exchange amount between currency pairs.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["amount", "from_currency", "to_currency"],
                                "properties": {
                                    "amount": {"type": "number"},
                                    "from_currency": {"type": "string"},
                                    "to_currency": {"type": "string"},
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
            amt = args.get("amount", 1.0)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"{amt} USD = {amt * 0.92} EUR"}],
                    "isError": False,
                },
            }
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
