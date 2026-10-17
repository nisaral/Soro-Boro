"""Veyra Execution Trace Format & Recorder.

Conforms to the frozen trace specification in docs/OBJECTIVE.md (Section 22).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TraceRecord:
    trace_id: str
    tool_proposed: str
    arguments_proposed: dict[str, Any]
    tool_resolved: str
    arguments_resolved: dict[str, Any]
    decision: str  # "direct_execution" | "corrected_and_executed" | "retried_and_succeeded" | "failed_escalated"
    failure: dict[str, Any] | None
    latency_ms: float
    attempt: int
    safe: bool
    outcome: str  # "success" | "failure"
    agent: str = "default_agent"
    corrections: list[str] = field(default_factory=list)
    state_before: str | None = None
    state_after: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TraceRecorder:
    """Records boundary traces to memory and optional JSONL log file."""

    def __init__(self, log_path: Path | str | None = None):
        self.log_path = Path(log_path) if log_path else None
        self.traces: list[TraceRecord] = []
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, trace: TraceRecord) -> None:
        self.traces.append(trace)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")

    def clear(self) -> None:
        self.traces.clear()
