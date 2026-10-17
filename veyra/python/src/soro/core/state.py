"""Veyra Core: ExecutionState abstraction.

Captures agent task context, execution step, tool history, and environmental state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionState:
    """Represents the context and state at the moment of an action proposal."""

    agent: str = "default_agent"
    step: int = 1
    history: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    permissions: set[str] = field(default_factory=set)

    @property
    def previous_tools(self) -> list[str]:
        tools = []
        for h in self.history:
            if isinstance(h, str):
                tools.append(h)
            elif isinstance(h, dict) and "tool" in h:
                tools.append(str(h["tool"]))
        return tools

    def compute_signature(self) -> str:
        """Deterministic fingerprint of state context and recent history."""
        payload = {
            "agent": self.agent,
            "step": self.step,
            "recent_tools": self.previous_tools[-5:],
            "context_keys": sorted(self.context.keys()),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "step": self.step,
            "history": self.history,
            "context": self.context,
            "permissions": list(self.permissions),
            "state_signature": self.compute_signature(),
        }
