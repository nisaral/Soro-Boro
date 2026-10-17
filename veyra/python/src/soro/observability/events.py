"""Veyra Observability Events & Export Subsystem (Phase 13).

First-class execution boundary events:
- ACTION_PROPOSED
- ACTION_REJECTED
- ACTION_SELECTED
- ACTION_EXECUTED
- ACTION_FAILED
- UNKNOWN_ACK
- VERIFICATION_STARTED
- VERIFICATION_COMPLETED
- RECOVERY_STARTED
- RECOVERY_COMPLETED
- DEFERRED
- DENIED

Exporters:
- JSONL file exporter
- OpenTelemetry span adapter
"""

from __future__ import annotations

import enum
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class VeyraEventKind(str, enum.Enum):
    ACTION_PROPOSED = "ACTION_PROPOSED"
    ACTION_REJECTED = "ACTION_REJECTED"
    ACTION_SELECTED = "ACTION_SELECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_FAILED = "ACTION_FAILED"
    UNKNOWN_ACK = "UNKNOWN_ACK"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    DEFERRED = "DEFERRED"
    DENIED = "DENIED"


@dataclass
class VeyraObservabilityEvent:
    """First-class execution boundary observability event."""

    event_kind: VeyraEventKind
    trace_id: str
    tool_name: str
    agent: str = "default_agent"
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_kind": self.event_kind.value,
            "trace_id": self.trace_id,
            "tool_name": self.tool_name,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventPublisher:
    """Central event publisher supporting JSONL file logging and OpenTelemetry hooks."""

    def __init__(self, jsonl_path: str | Path | None = None):
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        self.listeners: list[Any] = []
        self._events_log: list[VeyraObservabilityEvent] = []

    def publish(self, event: VeyraObservabilityEvent) -> None:
        self._events_log.append(event)
        event_dict = event.to_dict()

        if self.jsonl_path:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict) + "\n")

        for listener in self.listeners:
            try:
                listener(event_dict)
            except Exception:
                pass

    def export_opentelemetry() -> list[dict[str, Any]]:
        """Export events as OpenTelemetry compatible span attributes."""
        spans = []
        for ev in self._events_log:
            spans.append({
                "name": f"soro.{ev.event_kind.value.lower()}",
                "trace_id": ev.trace_id,
                "timestamp_ns": int(ev.timestamp * 1e9),
                "attributes": {
                    "soro.tool": ev.tool_name,
                    "soro.agent": ev.agent,
                    "soro.details": json.dumps(ev.details),
                },
            })
        return spans

    def clear((self) -> None:
        self._events_log.clear()
