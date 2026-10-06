"""Veyra Core: Execution Trace Schema and Recorder.

Implements the Section 11 trace format for execution observability and future routing research.
Supports configurable redaction of sensitive arguments/payloads.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


REDACTED_KEYS = {"api_key", "token", "secret", "password", "auth", "authorization", "bearer", "private_key"}


def sanitize_payload(payload: Any) -> Any:
    """Recursively redact sensitive keys from dictionaries and logs."""
    if isinstance(payload, dict):
        cleaned = {}
        for k, v in payload.items():
            if str(k).lower() in REDACTED_KEYS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_payload(v)
        return cleaned
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


@dataclass
class ExecutionTrace:
    """Rich execution trace captured for every Veyra boundary call."""

    trace_id: str
    agent: str
    proposal: dict[str, Any]
    candidates: list[str] = field(default_factory=list)
    filtered_candidates: list[str] = field(default_factory=list)
    resolved_tool: str = ""
    resolved_arguments: dict[str, Any] = field(default_factory=dict)
    policy: str = "deterministic"
    decision: str = "select"
    failure: dict[str, Any] | None = None
    recovery: dict[str, Any] | None = None
    latency_ms: float = 0.0
    attempt: int = 1
    safe: bool = True
    outcome: str = "success"  # success | failure
    corrections: list[str] = field(default_factory=list)

    # Future routing research fields
    risk_class: str = "low"
    is_idempotent: bool = False
    is_retryable: bool = False
    equivalence_group: str | None = None
    state_signature: str = ""
    previous_tools: list[str] = field(default_factory=list)

    # Compatibility properties for TraceRecord interface
    @property
    def tool_proposed(self) -> str:
        return str(self.proposal.get("tool", ""))

    @property
    def arguments_proposed(self) -> dict[str, Any]:
        return dict(self.proposal.get("arguments", {}))

    @property
    def tool_resolved(self) -> str:
        return self.resolved_tool

    @property
    def arguments_resolved(self) -> dict[str, Any]:
        return self.resolved_arguments

    def to_dict(self, redact: bool = True) -> dict[str, Any]:
        d = asdict(self)
        d["tool_proposed"] = self.tool_proposed
        d["arguments_proposed"] = self.arguments_proposed
        d["tool_resolved"] = self.tool_resolved
        d["arguments_resolved"] = self.arguments_resolved
        if redact:
            d["proposal"] = sanitize_payload(d["proposal"])
            d["resolved_arguments"] = sanitize_payload(d["resolved_arguments"])
            d["arguments_proposed"] = sanitize_payload(d["arguments_proposed"])
        return d


class TraceSink:
    """Sink for recording and persisting execution traces."""

    def __init__(
        self,
        log_path: Path | str | None = None,
        auto_flush: bool = True,
        listener: Any = None,
    ):
        self.traces: list[ExecutionTrace] = []
        self.log_path = Path(log_path) if log_path else None
        self.auto_flush = auto_flush
        self.listener = listener
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, trace: ExecutionTrace) -> None:
        self.traces.append(trace)
        if self.listener is not None and hasattr(self.listener, "record"):
            try:
                self.listener.record(trace)
            except Exception:
                pass
        if self.log_path and self.auto_flush:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")

    def clear(self) -> None:
        self.traces.clear()
        if self.listener is not None and hasattr(self.listener, "clear"):
            try:
                self.listener.clear()
            except Exception:
                pass
