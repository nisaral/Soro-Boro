"""Phase A Long-Tail Static Survey of Public MCP Servers.

Analyzes the machine-introspected public MCP servers tool catalog:
- 359 successfully introspected public servers from registries, awesome-lists, npm, and PyPI
- 9,922 captured tools from live `tools/list` JSON-RPC calls

Evaluates:
1. Annotation Coverage:
   - Share of servers declaring any hints
   - Share of servers completely unannotated (omitting all hints)
   - Share of tools declaring explicit readOnlyHint, idempotentHint, destructiveHint
2. Spec Defaults & Risk Profile:
   - Query/Read tools unannotated (where readOnlyHint default False induces confirmation fatigue)
   - Share where spec defaults imply risky or conservative reading
3. Computes exact fractions and Wilson score 95% confidence intervals.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "mcp_catalog"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOOLS_PARQUET_URL = "https://huggingface.co/datasets/automatelab/mcp-servers-tool-catalog/resolve/main/data/tools.parquet"
SERVERS_PARQUET_URL = "https://huggingface.co/datasets/automatelab/mcp-servers-tool-catalog/resolve/main/data/servers.parquet"

TOOLS_FILE = DATA_DIR / "tools.parquet"
SERVERS_FILE = DATA_DIR / "servers.parquet"

QUERY_PREFIXES = (
    "read_", "get_", "list_", "search_", "find_", "query_", "fetch_",
    "describe_", "inspect_", "view_", "check_", "show_", "info_", "tree_"
)

DESTRUCTIVE_PREFIXES = (
    "delete_", "drop_", "truncate_", "destroy_", "remove_", "wipe_", "purge_", "kill_", "terminate_"
)

MUTATING_PREFIXES = (
    "create_", "add_", "insert_", "update_", "set_", "post_", "write_", "edit_", "append_", "modify_", "save_"
)


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[cached] {dest.name} ({dest.stat().st_size} bytes)")
        return
    print(f"[downloading] {url} -> {dest} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "soro-audit-phase-a"})
    with urllib.request.urlopen(req, timeout=60) as res, open(dest, "wb") as f:
        f.write(res.read())
    print(f"[downloaded] {dest.name} ({dest.stat().st_size} bytes)")


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Calculates Wilson score 95% confidence interval for a binomial proportion."""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + (z ** 2) / total
    center = (p + (z ** 2) / (2 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / total) + (z ** 2) / (4 * (total ** 2)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return low, high


def run_survey() -> Dict[str, Any]:
    download_file(TOOLS_PARQUET_URL, TOOLS_FILE)
    download_file(SERVERS_PARQUET_URL, SERVERS_FILE)

    tools_table = pq.read_table(TOOLS_FILE)
    servers_table = pq.read_table(SERVERS_FILE)

    tools_df = tools_table.to_pylist()
    servers_df = servers_table.to_pylist()

    total_servers = len(servers_df)
    total_tools = len(tools_df)

    print(f"\nAnalyzing {total_tools} tools across {total_servers} servers...")

    # Group tools by server_id / server_name
    server_tools: Dict[str, List[Dict[str, Any]]] = {}
    for t in tools_df:
        s_id = str(t.get("server_id") or t.get("server_name") or "unknown")
        if s_id not in server_tools:
            server_tools[s_id] = []
        server_tools[s_id].append(t)

    # Metrics
    servers_with_any_hints = 0
    servers_completely_unannotated = 0

    tools_with_any_hints = 0
    tools_with_readonly_hint = 0
    tools_with_idempotent_hint = 0
    tools_with_destructive_hint = 0
    tools_with_openworld_hint = 0

    # Risk analysis under MCP spec defaults:
    # 1. Query-sounding tools lacking readOnlyHint: true
    # (Spec default readOnlyHint: false induces confirmation fatigue / operator friction)
    query_tools_total = 0
    query_tools_unannotated = 0
    query_tools_annotated_read_only = 0

    # 2. Mutating tools with destructive names
    destructive_tools_total = 0
    destructive_tools_explicitly_annotated = 0

    for s_id, s_tools in server_tools.items():
        server_has_hint = False
        for t in s_tools:
            raw_ann = t.get("annotations")
            ann = {}
            if isinstance(raw_ann, str) and raw_ann.strip():
                try:
                    ann = json.loads(raw_ann)
                except Exception:
                    pass
            elif isinstance(raw_ann, dict):
                ann = raw_ann

            # Check top-level or annotations dict
            ro = ann.get("readOnlyHint", t.get("readOnlyHint"))
            idem = ann.get("idempotentHint", t.get("idempotentHint"))
            destr = ann.get("destructiveHint", t.get("destructiveHint"))
            ow = ann.get("openWorldHint", t.get("openWorldHint"))

            has_hint = any(v is not None for v in (ro, idem, destr, ow))
            if has_hint:
                server_has_hint = True
                tools_with_any_hints += 1

            if ro is not None:
                tools_with_readonly_hint += 1
            if idem is not None:
                tools_with_idempotent_hint += 1
            if destr is not None:
                tools_with_destructive_hint += 1
            if ow is not None:
                tools_with_openworld_hint += 1

            t_name = str(t.get("name") or "").lower()
            t_desc = str(t.get("description") or "").lower()

            # Is it a query / read-only candidate?
            is_query = any(t_name.startswith(p) for p in QUERY_PREFIXES) or "read" in t_desc[:50] or "get" in t_desc[:50] or "list" in t_desc[:50]
            if is_query:
                query_tools_total += 1
                if ro is True:
                    query_tools_annotated_read_only += 1
                else:
                    query_tools_unannotated += 1

            # Is it a destructive candidate?
            is_destr = any(t_name.startswith(p) for p in DESTRUCTIVE_PREFIXES) or "delete" in t_desc[:50] or "drop" in t_desc[:50] or "destroy" in t_desc[:50]
            if is_destr:
                destructive_tools_total += 1
                if destr is not None:
                    destructive_tools_explicitly_annotated += 1

        if server_has_hint:
            servers_with_any_hints += 1
        else:
            servers_completely_unannotated += 1

    server_unannotated_rate = servers_completely_unannotated / max(1, total_servers)
    server_unann_ci = wilson_interval(servers_completely_unannotated, total_servers)

    tool_unannotated_rate = (total_tools - tools_with_any_hints) / max(1, total_tools)
    tool_unann_ci = wilson_interval(total_tools - tools_with_any_hints, total_tools)

    query_unannotated_rate = query_tools_unannotated / max(1, query_tools_total)
    query_unann_ci = wilson_interval(query_tools_unannotated, query_tools_total)

    report = {
        "dataset_provenance": {
            "source": "automatelab/mcp-servers-tool-catalog",
            "last_extracted": "2026-10-01",
            "license": "CC-BY-4.0",
        },
        "servers": {
            "total_servers": total_servers,
            "servers_with_any_hints": servers_with_any_hints,
            "servers_completely_unannotated": servers_completely_unannotated,
            "unannotated_server_rate": round(server_unannotated_rate, 4),
            "unannotated_server_95_ci": [round(server_unann_ci[0], 4), round(server_unann_ci[1], 4)],
        },
        "tools": {
            "total_tools": total_tools,
            "tools_with_any_hints": tools_with_any_hints,
            "tools_completely_unannotated": total_tools - tools_with_any_hints,
            "unannotated_tool_rate": round(tool_unannotated_rate, 4),
            "unannotated_tool_95_ci": [round(tool_unann_ci[0], 4), round(tool_unann_ci[1], 4)],
            "hints_breakdown": {
                "readOnlyHint_count": tools_with_readonly_hint,
                "idempotentHint_count": tools_with_idempotent_hint,
                "destructiveHint_count": tools_with_destructive_hint,
                "openWorldHint_count": tools_with_openworld_hint,
            },
        },
        "spec_defaults_risk_analysis": {
            "query_tools_total": query_tools_total,
            "query_tools_unannotated_rate": round(query_unannotated_rate, 4),
            "query_tools_unannotated_count": query_tools_unannotated,
            "query_tools_unannotated_95_ci": [round(query_unann_ci[0], 4), round(query_unann_ci[1], 4)],
            "destructive_tools_total": destructive_tools_total,
            "destructive_tools_explicitly_annotated": destructive_tools_explicitly_annotated,
            "destructive_tools_omitted_count": destructive_tools_total - destructive_tools_explicitly_annotated,
        },
    }

    out_json = ROOT / "reports" / "mcp_phase_a_survey_359_servers.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote survey report to {out_json}")

    return report


if __name__ == "__main__":
    rep = run_survey()
    print("\n" + "=" * 70)
    print("PHASE A LONG-TAIL SURVEY RESULTS (359 Public MCP Servers · 9,922 Tools)")
    print("=" * 70)
    print(f"Total Servers Audited:           {rep['servers']['total_servers']}")
    print(f"Servers Completely Unannotated:  {rep['servers']['servers_completely_unannotated']} / {rep['servers']['total_servers']} ({rep['servers']['unannotated_server_rate']*100:.1f}%) [95% CI: {rep['servers']['unannotated_server_95_ci'][0]*100:.1f}% - {rep['servers']['unannotated_server_95_ci'][1]*100:.1f}%]")
    print(f"Servers with Any Hints:          {rep['servers']['servers_with_any_hints']} / {rep['servers']['total_servers']} ({(1-rep['servers']['unannotated_server_rate'])*100:.1f}%)")
    print("-" * 70)
    print(f"Total Tools Audited:             {rep['tools']['total_tools']}")
    print(f"Tools Completely Unannotated:    {rep['tools']['tools_completely_unannotated']} / {rep['tools']['total_tools']} ({rep['tools']['unannotated_tool_rate']*100:.1f}%) [95% CI: {rep['tools']['unannotated_tool_95_ci'][0]*100:.1f}% - {rep['tools']['unannotated_tool_95_ci'][1]*100:.1f}%]")
    print(f"Tools Declaring Any Hint:        {rep['tools']['tools_with_any_hints']} / {rep['tools']['total_tools']} ({(1-rep['tools']['unannotated_tool_rate'])*100:.1f}%)")
    print("-" * 70)
    print(f"Query Tools Analyzed:            {rep['spec_defaults_risk_analysis']['query_tools_total']}")
    print(f"Query Tools Unannotated:         {rep['spec_defaults_risk_analysis']['query_tools_unannotated_count']} ({rep['spec_defaults_risk_analysis']['query_tools_unannotated_rate']*100:.1f}%) [95% CI: {rep['spec_defaults_risk_analysis']['query_tools_unannotated_95_ci'][0]*100:.1f}% - {rep['spec_defaults_risk_analysis']['query_tools_unannotated_95_ci'][1]*100:.1f}%]")
    print(f"  -> Consequence: Under MCP spec default (readOnlyHint=False), these cause Confirmation Fatigue")
    print(f"Destructive Tools Analyzed:      {rep['spec_defaults_risk_analysis']['destructive_tools_total']}")
    print(f"Destructive Tools Omitted:       {rep['spec_defaults_risk_analysis']['destructive_tools_omitted_count']}")
    print(f"  -> Consequence: Under MCP spec default (destructiveHint=True), omitting is conservative & safe")
    print("=" * 70)
