"""Veyra Export: Structured Trace and Trajectory Exporter.

Supports exporting Veyra machine-readable trajectories to:
1. Standardized JSONL audit files
2. OpenTelemetry (OTel) compatible span dictionaries
3. Aggregated execution performance summaries
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soro.core.trajectory import TrajectoryRecord, TrajectoryWriter


class StructuredTraceExporter:
    """Exports structured execution traces and trajectories across formats."""

    def __init__(self, records: list[TrajectoryRecord] | None = None):
        self.records: list[TrajectoryRecord] = list(records or [])

    def add(self, record: TrajectoryRecord) -> None:
        self.records.append(record)

    def export_jsonl(self, output_path: str | Path) -> Path:
        """Export all trajectory records to a JSONL file."""
        writer = TrajectoryWriter(output_path)
        for r in self.records:
            writer.write(r)
        return Path(output_path)

    def export_otel_spans(self) -> list[dict[str, Any]]:
        """Convert trajectory records to OpenTelemetry-compatible span dictionaries."""
        spans = []
        for r in self.records:
            span = {
                "name": f"soro.resolution/{r.proposed_action.get('tool', 'unknown')}",
                "context": {
                    "trace_id": r.task_id,
                    "span_id": f"{r.task_id}-{r.turn_index}",
                },
                "attributes": {
                    "soro.arm": r.arm,
                    "soro.policy_decision": r.policy_decision,
                    "soro.resolution_reason": r.resolution_reason,
                    "soro.selected_tool": r.selected_action.get("tool") if r.selected_action else None,
                    "soro.failure_provenance": r.failure_provenance,
                    "soro.agent_replan": r.agent_replan,
                    "soro.retry_count": r.retry_count,
                    "soro.final_success": r.final_success,
                    "soro.latency_ms": r.latency * 1000.0,
                    "llm.tokens.prompt": r.tokens.get("prompt", 0),
                    "llm.tokens.completion": r.tokens.get("completion", 0),
                    "llm.tokens.total": r.tokens.get("total", 0),
                },
                "status": {
                    "code": "OK" if r.final_success else "ERROR",
                    "description": r.failure_kind or "",
                },
            }
            spans.append(span)
        return spans

    def compute_summary_metrics(self) -> dict[str, Any]:
        """Compute aggregated recovery and efficiency metrics across all records."""
        if not self.records:
            return {"total_records": 0}

        n = len(self.records)
        successes = sum(1 for r in self.records if r.final_success)
        replans = sum(1 for r in self.records if r.agent_replan)
        total_tokens = sum(r.tokens.get("total", 0) for r in self.records)
        latencies = [r.latency for r in self.records]

        provenances: dict[str, int] = {}
        for r in self.records:
            if r.failure_provenance:
                provenances[r.failure_provenance] = provenances.get(r.failure_provenance, 0) + 1

        return {
            "total_records": n,
            "success_count": successes,
            "success_rate": round(successes / n, 4),
            "replan_count": replans,
            "total_tokens": total_tokens,
            "mean_latency_ms": round((sum(latencies) / n) * 1000.0, 3) if latencies else 0.0,
            "failure_provenance_breakdown": provenances,
        }
