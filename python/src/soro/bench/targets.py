"""Public benchmarks Veyra is aiming at, and the shifts in Veyra-ShiftBench.

This module is the checklist. It does not download or score the upstream
suites. A target stays ``not_run`` until a recorded command produces a table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    id: str
    role: str
    status: str
    upstream: str


TARGETS: tuple[Target, ...] = (
    Target("harbor-public", "step 0, $0 re-analysis", "not_run",
           "Harbor 8 models × Terminus-2 vs native, 54 benches, 3 trials; oracle vs same-harness null"),
    Target("terminal-bench-2.0", "first paid Harbor run", "not_run",
           "89 verifier-scored tasks; pilot 20 then 3 arms × 3 seeds"),
    Target("swe-harbor", "repo-split SWE-style adapter", "not_run",
           "~100 tasks through Harbor; split by repository"),
    Target("aider-polyglot", "cheap gap check", "not_run",
           "published harness gaps; mid-strength model"),
    Target("harbor-index", "breadth / rescue pool", "not_run",
           "82 hard tasks after Terminal-Bench"),
    Target("stt-arena", "shift and abstain", "not_scheduled",
           "227 tasks, 30 impossible; simulated tools"),
    Target("mcpagentbench", "smoke only", "smoke",
           "not the public claim; Gemma 1-task TFS 0.0 (no native tool calls)"),
    Target("toolsandbox", "later stateful tools", "not_scheduled",
           "after Gate 1"),
    Target("tau-bench", "later user+tool+policy", "not_scheduled",
           "after Gate 1"),
)

SHIFTS: tuple[str, ...] = (
    "unavailable",
    "expensive",
    "unreliable",
    "schema",
    "permission",
    "new_tool",
    "misleading",
)

ARMS: tuple[str, ...] = (
    "fixed-react",
    "static-router",
    "veyra-heuristic",
    "veyra-decision",
    "veyra-decision-bandit",
)

METRICS: tuple[str, ...] = (
    "task_success",
    "tool_selection_accuracy",
    "wasted_tool_calls",
    "cost_usd",
    "latency_ms",
    "recovery_after_shift",
    "unsafe_actions",
    "abstentions",
)


def checklist() -> str:
    lines = ["benchmarks (none of these is a measured Veyra score)", ""]
    for target in TARGETS:
        lines.append(f"  {target.status:14} {target.id:20} {target.role}")
    lines.append("")
    lines.append("arms: " + ", ".join(ARMS))
    lines.append("metrics: " + ", ".join(METRICS))
    lines.append("shiftbench: " + ", ".join(SHIFTS))
    return "\n".join(lines)
