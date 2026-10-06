"""Veyra Audit Diagnostic Surface.

Conforms to Section 23 of docs/OBJECTIVE.md:
Parses execution traces and produces an audit summary of tool calls,
failure distributions, boundary recoveries, replans avoided, and unsafe retries.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from veyra.boundary.taxonomy import FailureKind
from veyra.boundary.trace import TraceRecord


@dataclass
class AuditSummary:
    total_calls: int
    total_failures: int
    total_recoveries: int
    agent_replans_avoided: int
    unsafe_retries: int
    failure_distribution: dict[str, int]
    problematic_tools: list[tuple[str, int]]

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)

    def to_text(self) -> str:
        return self.format_text()

    def format_text(self) -> str:
        lines = [
            "=" * 60,
            "                   VEYRA EXECUTION AUDIT",
            "=" * 60,
            f"Total Tool Calls:             {self.total_calls}",
            f"Total Initial Failures:       {self.total_failures}",
            f"Veyra Automatically Recovered: {self.total_recoveries} / {max(1, self.total_failures)}",
            f"Agent Re-plans Avoided:       {self.agent_replans_avoided}",
            f"Unsafe Retry Attempts:        {self.unsafe_retries} (CRITICAL: MUST BE 0)",
            "",
            "--- Failure Distribution ---",
        ]

        if not self.failure_distribution:
            lines.append("  (No failures recorded)")
        else:
            for kind, count in sorted(self.failure_distribution.items(), key=lambda x: x[1], reverse=True):
                pct = (count / max(1, self.total_failures)) * 100.0
                lines.append(f"  {kind:<22} {count:4d} ({pct:5.1f}%)")

        lines.extend([
            "",
            "--- Most Problematic Tools ---",
        ])
        if not self.problematic_tools:
            lines.append("  (None)")
        else:
            for tool, count in self.problematic_tools[:5]:
                lines.append(f"  {tool:<25} {count} failures")

        lines.append("=" * 60)
        return "\n".join(lines)


def run_audit(traces: Iterable[TraceRecord | dict[str, Any]]) -> AuditSummary:
    """Analyze a sequence of trace records and generate the audit summary."""
    total_calls = 0
    total_failures = 0
    recoveries = 0
    replans_avoided = 0
    unsafe_retries = 0
    failure_counts: Counter[str] = Counter()
    tool_failures: Counter[str] = Counter()

    for item in traces:
        t = item if isinstance(item, dict) else item.to_dict()
        total_calls += 1

        decision = t.get("decision", "")
        outcome = t.get("outcome", "")
        failure = t.get("failure") or {}
        tool = t.get("tool_proposed", "unknown_tool")

        # Did it encounter a failure?
        if failure or decision in ("retried_and_succeeded", "failed_escalated"):
            total_failures += 1
            kind = failure.get("kind", FailureKind.UNKNOWN.value)
            failure_counts[kind] += 1
            tool_failures[tool] += 1

            # Did Veyra recover it safely?
            if decision == "retried_and_succeeded" or (decision == "corrected_and_executed" and outcome == "success"):
                recoveries += 1
                replans_avoided += 1

        elif decision == "corrected_and_executed":
            # Argument normalization prevented a schema rejection
            recoveries += 1
            replans_avoided += 1

        # Check safety invariant: was an unsafe retry attempted?
        if t.get("attempt", 1) > 1 and not t.get("safe", True):
            unsafe_retries += 1

    return AuditSummary(
        total_calls=total_calls,
        total_failures=total_failures,
        total_recoveries=recoveries,
        agent_replans_avoided=replans_avoided,
        unsafe_retries=unsafe_retries,
        failure_distribution=dict(failure_counts),
        problematic_tools=tool_failures.most_common(5),
    )


def audit_from_file(log_path: Path | str) -> AuditSummary:
    """Read a JSONL trace log and compute the audit summary."""
    p = Path(log_path)
    if not p.exists():
        return AuditSummary(0, 0, 0, 0, 0, {}, [])

    traces = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except Exception:
                    pass

    return run_audit(traces)
