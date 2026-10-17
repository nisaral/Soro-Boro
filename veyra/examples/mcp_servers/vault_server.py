"""External real MCP server 2: File System & Log Vault MCP server (non-MCPAgentBench)."""

import json
import os
import sys
import tempfile

def main():
    vault_dir = tempfile.mkdtemp(prefix="vault_")

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
                    "serverInfo": {"name": "vault-mcp-server", "version": "1.0.0"},
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
                            "name": "vault_write_record",
                            "description": "Store a record key-value pair in secure vault.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["key", "content"],
                                "properties": {
                                    "key": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                            },
                        },
                        {
                            "name": "vault_read_record",
                            "description": "Read a stored record from vault by key.",
                            "inputSchema": {
                                "type": "object",
                                "required": ["key"],
                                "properties": {"key": {"type": "string"}},
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
            key = args.get("key", "default")
            file_path = os.path.join(vault_dir, f"{key}.dat")

            try:
                if name == "vault_write_record":
                    content = args.get("content", "")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    res_content = f"Stored {len(content)} bytes under {key}"
                else:
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            res_content = f.read()
                    else:
                        res_content = "KEY_NOT_FOUND"

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
