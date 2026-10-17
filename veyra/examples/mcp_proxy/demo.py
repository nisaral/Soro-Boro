"""Veyra MCP Proxy End-to-End Demo (Phase 5 / Phase 24).

Demonstrates placing Veyra between an MCP client and server to interpose execution control.
"""

from veyra import Veyra
from veyra.middleware.mcp import VeyraMCPProxy

def main():
    veyra = Veyra(mode="fail_closed")
    proxy = VeyraMCPProxy(veyra)

    # Simulated MCP JSON-RPC call from an agent
    request = '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "query_db", "arguments": {"id": 42}}, "id": 1}'
    response = proxy.handle_request(request)
    print("Agent request:", request)
    print("Veyra proxy response:", response)

if __name__ == "__main__":
    main()
