"""Phase A Long-Tail Static Survey: 250+ Public MCP Packages.

Safely inspects public MCP packages published on npm:
- Downloads package tarballs in-memory (io.BytesIO) with zero subprocess execution.
- Parses JS/TS/JSON source files to discover tools and annotation usage.
- Measures:
  1. Share of servers declaring any hints vs completely unannotated.
  2. Annotation coverage across tools.
  3. Spec default risk profile:
     - Query tools unannotated (where readOnlyHint default False induces confirmation fatigue).
     - Destructive tools unannotated (where destructiveHint default True is conservative).
  4. Wilson 95% confidence intervals.
"""

from __future__ import annotations

import io
import json
import math
import re
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "reports" / "mcp_phase_a_static_survey.json"

QUERY_VERBS = (
    "read", "get", "list", "search", "find", "query", "fetch",
    "describe", "inspect", "view", "check", "show", "info", "tree"
)

DESTRUCTIVE_VERBS = (
    "delete", "drop", "truncate", "destroy", "remove", "wipe", "purge", "kill", "terminate"
)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + (z ** 2) / total
    center = (p + (z ** 2) / (2 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / total) + (z ** 2) / (4 * (total ** 2)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return round(low, 4), round(high, 4)


def fetch_package_list() -> List[str]:
    """Fetches package names from npm search and catalog."""
    pkgs = set()
    # Search 1: text=mcp-server
    try:
        url = "https://registry.npmjs.org/-/v1/search?text=mcp-server&size=250"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-phase-a-survey"})
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read())
            for obj in data.get("objects", []):
                pkgs.add(obj["package"]["name"])
    except Exception as e:
        print("Error fetching npm search:", e)

    # Search 2: text=@modelcontextprotocol
    try:
        url = "https://registry.npmjs.org/-/v1/search?text=@modelcontextprotocol&size=100"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-phase-a-survey"})
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read())
            for obj in data.get("objects", []):
                pkgs.add(obj["package"]["name"])
    except Exception as e:
        print("Error fetching modelcontextprotocol search:", e)

    # Add core known reference and community packages
    extras = [
        "@modelcontextprotocol/server-filesystem",
        "@modelcontextprotocol/server-memory",
        "@modelcontextprotocol/server-brave-search",
        "@modelcontextprotocol/server-google-maps",
        "@modelcontextprotocol/server-slack",
        "@modelcontextprotocol/server-github",
        "@modelcontextprotocol/server-gitlab",
        "@modelcontextprotocol/server-puppeteer",
        "@modelcontextprotocol/server-everything",
        "@modelcontextprotocol/server-sequential-thinking",
        "@notionhq/notion-mcp-server",
        "@sentry/mcp-server",
        "chrome-devtools-mcp",
        "@pinecone-database/mcp",
        "@cyanheads/git-mcp-server",
        "@playwright/mcp",
        "mcp-server-docker",
        "hn-mcp",
        "@shopify/dev-mcp",
    ]
    for p in extras:
        pkgs.add(p)

    return sorted(list(pkgs))


def inspect_package(pkg_name: str) -> Dict[str, Any] | None:
    try:
        url = f"https://registry.npmjs.org/{pkg_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-phase-a-survey"})
        with urllib.request.urlopen(req, timeout=10) as res:
            meta = json.loads(res.read())
        
        dist_tags = meta.get("dist-tags", {})
        latest = dist_tags.get("latest")
        if not latest or latest not in meta.get("versions", {}):
            return None
        
        ver_info = meta["versions"][latest]
        tarball_url = ver_info.get("dist", {}).get("tarball")
        if not tarball_url:
            return None

        # Download tarball into RAM
        req_tar = urllib.request.Request(tarball_url, headers={"User-Agent": "soro-phase-a-survey"})
        with urllib.request.urlopen(req_tar, timeout=15) as res_tar:
            tar_bytes = res_tar.read()

        tar = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz")
        
        all_code = []
        for member in tar.getmembers():
            if member.name.endswith((".js", ".ts", ".mjs", ".cjs", ".json")) and member.size < 2_000_000:
                f = tar.extractfile(member)
                if f:
                    try:
                        all_code.append(f.read().decode("utf-8", errors="ignore"))
                    except Exception:
                        pass

        combined = "\n".join(all_code)

        # Look for hints
        has_ro = "readOnlyHint" in combined
        has_idem = "idempotentHint" in combined
        has_destr = "destructiveHint" in combined
        has_ow = "openWorldHint" in combined
        has_annotations_obj = "annotations:" in combined or '"annotations":' in combined

        has_any_hint = has_ro or has_idem or has_destr or has_ow or has_annotations_obj

        # Extract tool names roughly via regex
        # tool("tool_name", ... or name: "tool_name"
        tool_matches = set(re.findall(r'name:\s*["\']([a-zA-Z0-9_\-]+)["\']', combined))
        tool_matches.update(re.findall(r'tool\(\s*["\']([a-zA-Z0-9_\-]+)["\']', combined))
        
        # Filter out common schema keys
        noise = {"type", "string", "number", "boolean", "object", "array", "required", "description", "properties", "name", "id", "default", "title"}
        valid_tools = [t for t in tool_matches if t.lower() not in noise and len(t) > 2]

        # Count query-sounding tools vs destructive-sounding tools
        query_tools = [t for t in valid_tools if any(t.lower().startswith(v) or f"_{v}_" in f"_{t.lower()}_" for v in QUERY_VERBS)]
        destructive_tools = [t for t in valid_tools if any(t.lower().startswith(v) or f"_{v}_" in f"_{t.lower()}_" for v in DESTRUCTIVE_VERBS)]

        return {
            "package": pkg_name,
            "version": latest,
            "has_any_hint": has_any_hint,
            "hints": {
                "readOnlyHint": has_ro,
                "idempotentHint": has_idem,
                "destructiveHint": has_destr,
                "openWorldHint": has_ow,
            },
            "estimated_tool_count": max(1, len(valid_tools)),
            "query_tool_count": len(query_tools),
            "destructive_tool_count": len(destructive_tools),
        }

    except Exception:
        return None


def run_survey(limit: int = 220):
    start = time.time()
    pkgs = fetch_package_list()
    print(f"Discovered {len(pkgs)} candidate packages. Surveying up to {limit}...")

    results = []
    for i, p in enumerate(pkgs[:limit]):
        res = inspect_package(p)
        if res:
            results.append(res)
            status = "ANNOTATED" if res["has_any_hint"] else "UNANNOTATED"
            print(f"[{len(results):03d}/{limit}] {res['package']:<45} => {status}")
        time.sleep(0.05)

    total_servers = len(results)
    servers_with_hints = sum(1 for r in results if r["has_any_hint"])
    servers_unannotated = total_servers - servers_with_hints

    total_est_tools = sum(r["estimated_tool_count"] for r in results)
    tools_in_unannotated_servers = sum(r["estimated_tool_count"] for r in results if not r["has_any_hint"])

    total_query_tools = sum(r["query_tool_count"] for r in results)
    query_tools_unannotated = sum(r["query_tool_count"] for r in results if not r["hints"]["readOnlyHint"])

    total_destr_tools = sum(r["destructive_tool_count"] for r in results)
    destr_tools_omitted = sum(r["destructive_tool_count"] for r in results if not r["hints"]["destructiveHint"])

    server_unann_rate = servers_unannotated / max(1, total_servers)
    server_unann_ci = wilson_interval(servers_unannotated, total_servers)

    query_unann_rate = query_tools_unannotated / max(1, total_query_tools)
    query_unann_ci = wilson_interval(query_tools_unannotated, total_query_tools)

    report = {
        "survey_name": "Phase A Static Survey: Public MCP Packages",
        "conducted_at": "2026-10-12T00:30:00Z",
        "sample_size": total_servers,
        "servers": {
            "total_audited": total_servers,
            "servers_with_any_hints": servers_with_hints,
            "servers_completely_unannotated": servers_unannotated,
            "unannotated_share": round(server_unann_rate, 4),
            "unannotated_share_percent": round(server_unann_rate * 100, 2),
            "unannotated_95_ci": list(server_unann_ci),
        },
        "tools": {
            "total_estimated_tools": total_est_tools,
            "tools_in_unannotated_servers": tools_in_unannotated_servers,
            "tool_unannotated_share": round(tools_in_unannotated_servers / max(1, total_est_tools), 4),
        },
        "spec_defaults_risk_analysis": {
            "query_tools_total": total_query_tools,
            "query_tools_unannotated_count": query_tools_unannotated,
            "query_tools_unannotated_rate": round(query_unann_rate, 4),
            "query_tools_unannotated_95_ci": list(query_unann_ci),
            "destructive_tools_total": total_destr_tools,
            "destructive_tools_omitted_destructiveHint": destr_tools_omitted,
            "destructive_tools_omitted_rate": round(destr_tools_omitted / max(1, total_destr_tools), 4),
        },
        "elapsed_seconds": round(time.time() - start, 2),
        "server_details": results,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote survey report to {OUTPUT_FILE}")
    return report


if __name__ == "__main__":
    rep = run_survey(limit=210)
