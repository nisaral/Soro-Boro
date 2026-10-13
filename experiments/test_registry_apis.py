import json
import urllib.request

endpoints = [
    ("Smithery", "https://smithery.ai/api/servers"),
    ("Glama", "https://glama.ai/api/mcp/servers"),
    ("PulseMCP", "https://api.pulsemcp.com/v1/servers"),
    ("GitHub MCP Topic", "https://api.github.com/search/repositories?q=topic:mcp-server&per_page=100"),
]

for name, url in endpoints:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-research"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = res.read()
            print(f"{name}: Success, received {len(data)} bytes")
    except Exception as e:
        print(f"{name}: {e}")
