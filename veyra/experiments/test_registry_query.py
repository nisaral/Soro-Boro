import json
import urllib.request

try:
    url = "https://registry.npmjs.org/-/v1/search?text=mcp-server&size=250"
    req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-research"})
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read())
        objs = data.get("objects", [])
        print(f"NPM packages found: {len(objs)}, total in registry: {data.get('total')}")
        if objs:
            print("First 5 packages:", [o["package"]["name"] for o in objs[:5]])
except Exception as e:
    print("NPM error:", e)

try:
    url = "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
    req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-research"})
    with urllib.request.urlopen(req, timeout=10) as res:
        content = res.read().decode("utf-8")
        print(f"Awesome-MCP-Servers README fetched: {len(content)} bytes")
except Exception as e:
    print("Awesome MCP error:", e)
