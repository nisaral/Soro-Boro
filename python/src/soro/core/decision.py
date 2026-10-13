"""Veyra Core: Decision and RecoveryDecision abstractions.

Represents routing and recovery choices made at the execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from soro.core.action import ExecutableAction


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
    """Outcome of RoutePolicy evaluation with full explainability."""

    kind: DecisionKind
    action: ExecutableAction | None = None
    reason: str = ""
    confidence: float = 1.0
    candidate_rejections: dict[str, str] = field(default_factory=dict)
    policy_version: str = "v1.0"
    benchmark_version: str = "ContinuityBench-v1.0"
    is_shadow: bool = False
    is_dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def select(
        cls,
        action: ExecutableAction,
        reason: str = "selected by policy",
        confidence: float = 1.0,
        candidate_rejections: dict[str, str] | None = None,
        is_dry_run: bool = False,
        is_shadow: bool = False,
    ) -> Decision:
        return cls(
            kind=DecisionKind.SELECT,
            action=action,
            reason=reason,
            confidence=confidence,
            candidate_rejections=candidate_rejections or {},
            is_dry_run=is_dry_run,
            is_shadow=is_shadow,
        )

    @classmethod
    def deny(
        cls,
        reason: str = "denied by hard constraints or policy",
        candidate_rejections: dict[str, str] | None = None,
    ) -> Decision:
        return cls(
            kind=DecisionKind.DENY,
            action=None,
            reason=reason,
            confidence=1.0,
            candidate_rejections=candidate_rejections or {},
        )

    @classmethod
    def defer(
        cls,
        reason: str = "policy deferred to agent/fallback",
        candidate_rejections: dict[str, str] | None = None,
    ) -> Decision:
        return cls(
            kind=DecisionKind.DEFER,
            action=None,
            reason=reason,
            confidence=0.5,
            candidate_rejections=candidate_rejections or {},
        )

    def explain(self) -> dict[str, Any]:
        """Return deterministic, structured explanation of the routing decision (Phase 9 API)."""
        req_action = self.metadata.get("requested_action") or (self.action.tool if self.action else "unknown")
        sel_cand = self.action.tool if self.action else None
        
        return {
            "decision": self.kind.value.upper(),
            "requested_action": req_action,
            "selected_candidate": sel_cand,
            "rejected_candidates": self.candidate_rejections,
            "hard_constraints": self.metadata.get("hard_constraints", {"authorization": "PASSED", "tenant": "PASSED"}),
            "soft_preferences": self.metadata.get("soft_preferences", {"health": "OPTIMAL", "freshness": "VALID"}),
            "recovery_plan": self.metadata.get("recovery_plan", "NONE" if self.kind == DecisionKind.SELECT else "DEFER_TO_AGENT"),
            "risk_level": self.action.risk_class if self.action else "low",
            "confidence": self.confidence,
            "reason": self.reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "action": self.action.to_dict() if self.action else None,
            "reason": self.reason,
            "confidence": self.confidence,
            "candidate_rejections": self.candidate_rejections,
            "policy_version": self.policy_version,
            "benchmark_version": self.benchmark_version,
            "is_shadow": self.is_shadow,
            "is_dry_run": self.is_dry_run,
            "metadata": self.metadata,
            "explanation": self.explain(),
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
    def fallback(cls, action: ExecutableAction, reason: str = "fallback to declared candidate") -> RecoveryDecision:
        return cls(kind=RecoveryDecisionKind.FALLBACK, action=action, reason=reason)

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
