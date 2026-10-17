import json
import urllib.request

# Try fetching public server listing from glama or smithery
urls = [
    "https://api.github.com/search/code?q=readOnlyHint+filename:index.ts&per_page=100",
    "https://api.github.com/search/code?q=readOnlyHint+filename:server.py&per_page=100",
    "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-research", "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = res.read()
            print(f"URL: {url} -> {len(data)} bytes")
    except Exception as e:
        print(f"URL: {url} -> {e}")
