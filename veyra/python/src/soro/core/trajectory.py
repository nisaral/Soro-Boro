"""Standardized Machine-Readable Trajectory Logging Schema (Phase 0 Specification).

Every trajectory records exact execution decisions, policy choices, candidate actions,
failure provenance, and token accounting for rigorous offline evaluation and audit.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from soro.boundary.taxonomy import FailureProvenance


@dataclass
class TrajectoryRecord:
    """Standardized machine-readable trajectory record required by Phase 0."""

    task_id: str
    arm: str
    turn_index: int
    proposed_action: dict[str, Any]
    candidate_actions: list[dict[str, Any]]
    selected_action: dict[str, Any] | None
    resolution_reason: str
    policy_decision: str  # SELECT | DEFER | DENY
    failure_kind: str | None
    failure_provenance: str | None
    retry_count: int
    recovery_action: str | None
    agent_replan: bool
    tool_result: dict[str, Any] | None
    final_success: bool
    tokens: dict[str, int]
    latency: float
    timestamp_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryRecord:
        return cls(**data)


class TrajectoryWriter:
    """Appends standardized trajectory records to a JSONL file."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: TrajectoryRecord) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(record.to_json() + "\n")

    def write_many(self, records: list[TrajectoryRecord]) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(r.to_json() + "\n")
