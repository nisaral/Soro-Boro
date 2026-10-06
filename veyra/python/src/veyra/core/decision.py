"""Veyra Core: Decision and RecoveryDecision abstractions.

Represents routing and recovery choices made at the execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from veyra.core.action import ExecutableAction


class DecisionKind(str, Enum):
    """Core routing decisions supported by RoutePolicy."""

    SELECT = "select"
    DEFER = "defer"
    DENY = "deny"
    # Extensible decision kinds for future routing
    REPAIR = "repair"
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_AGENT = "ask_agent"


@dataclass
class Decision:
    """Outcome of RoutePolicy evaluation."""

    kind: DecisionKind
    action: ExecutableAction | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def select(cls, action: ExecutableAction, reason: str = "selected by policy") -> Decision:
        return cls(kind=DecisionKind.SELECT, action=action, reason=reason)

    @classmethod
    def deny(cls, reason: str = "denied by hard constraints or policy") -> Decision:
        return cls(kind=DecisionKind.DENY, action=None, reason=reason)

    @classmethod
    def defer(cls, reason: str = "policy deferred to agent/fallback") -> Decision:
        return cls(kind=DecisionKind.DEFER, action=None, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "action": self.action.to_dict() if self.action else None,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class RecoveryDecisionKind(str, Enum):
    """Outcomes of RecoveryPolicy evaluation after tool execution failure."""

    RETRY = "retry"
    REPAIR_AND_RETRY = "repair_and_retry"
    FALLBACK = "fallback"
    ESCALATE_TO_AGENT = "escalate_to_agent"


@dataclass
class RecoveryDecision:
    """Outcome of RecoveryPolicy evaluation."""

    kind: RecoveryDecisionKind
    action: ExecutableAction | None = None
    delay_sec: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def retry(cls, action: ExecutableAction, delay_sec: float = 0.0, reason: str = "safe retry") -> RecoveryDecision:
        return cls(kind=RecoveryDecisionKind.RETRY, action=action, delay_sec=delay_sec, reason=reason)

    @classmethod
    def escalate(cls, reason: str = "unrecoverable at boundary") -> RecoveryDecision:
        return cls(kind=RecoveryDecisionKind.ESCALATE_TO_AGENT, action=None, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "action": self.action.to_dict() if self.action else None,
            "delay_sec": self.delay_sec,
            "reason": self.reason,
            "metadata": self.metadata,
        }
