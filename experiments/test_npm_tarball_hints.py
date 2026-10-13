import io
import json
import tarfile
import urllib.request

packages = [
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-memory",
    "@modelcontextprotocol/server-brave-search",
    "@modelcontextprotocol/server-google-maps",
    "@modelcontextprotocol/server-slack",
    "@notionhq/notion-mcp-server",
    "@sentry/mcp-server",
    "chrome-devtools-mcp",
    "npm-search-mcp-server",
    "contextplus",
    "@pinecone-database/mcp",
    "hn-mcp",
    "@cyanheads/git-mcp-server",
    "@playwright/mcp",
    "mcp-server-docker",
]

results = []

for pkg in packages:
    try:
        url = f"https://registry.npmjs.org/{pkg}"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-research"})
        with urllib.request.urlopen(req, timeout=10) as res:
            meta = json.loads(res.read())
        latest = meta["dist-tags"]["latest"]
        tarball_url = meta["versions"][latest]["dist"]["tarball"]
        print(f"Checking {pkg}@{latest} ...")

        req_tar = urllib.request.Request(tarball_url, headers={"User-Agent": "soro-audit-research"})
        with urllib.request.urlopen(req_tar, timeout=15) as res_tar:
            tar_bytes = res_tar.read()

        tar = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz")
        found_hints = False
        hints_found = []
        for member in tar.getmembers():
            if member.name.endswith((".js", ".ts", ".mjs", ".cjs", ".json")):
                f = tar.extractfile(member)
                if f:
                    content = f.read().decode("utf-8", errors="ignore")
                    for h in ["readOnlyHint", "idempotentHint", "destructiveHint", "openWorldHint"]:
                        if h in content:
                            found_hints = True
                            if h not in hints_found:
                                hints_found.append(h)
        results.append({
            "package": pkg,
            "version": latest,
            "has_hints": found_hints,
            "hints": hints_found,
        })
        print(f"  -> has_hints: {found_hints}, hints: {hints_found}")
    except Exception as e:
        print(f"  Error checking {pkg}: {e}")

print("\nSummary:", json.dumps(results, indent=2))
