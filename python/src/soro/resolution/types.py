"""Veyra Resolution Layer: Types and Data Structures.

Defines the formal resolution contracts, decision structures, candidate evaluation
breakdowns, and risk levels conforming to Section 2 and 3 of the Veyra Resolution Layer.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any

from soro.core.action import ExecutableAction


class ResolutionDecision(str, enum.Enum):
    """Core resolution decision kinds."""

    SELECT = "select"
    DEFER = "defer"
    DENY = "deny"


class RiskLevel(str, enum.Enum):
    """Execution risk level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


@dataclass
class CandidateEvaluation:
    """Individual candidate evaluation breakdown across hard constraints and soft preferences."""

    candidate: ExecutableAction
    is_valid: bool = True
    rejection_reason: str | None = None
    # Hard constraints
    contract_valid: bool = True
    authorized: bool = True
    tenant_matched: bool = True
    capability_compatible: bool = True
    side_effect_safe: bool = True
    transaction_safe: bool = True
    policy_allowed: bool = True
    # Soft preference attributes & scores
    health_score: float = 1.0
    freshness_score: float = 1.0
    reliability_score: float = 1.0
    latency_score: float = 1.0
    history_score: float = 1.0
    cost_score: float = 1.0
    preference_score: float = 1.0
    total_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.candidate.tool,
            "is_valid": self.is_valid,
            "rejection_reason": self.rejection_reason,
            "contract_valid": self.contract_valid,
            "authorized": self.authorized,
            "tenant_matched": self.tenant_matched,
            "capability_compatible": self.capability_compatible,
            "side_effect_safe": self.side_effect_safe,
            "transaction_safe": self.transaction_safe,
            "policy_allowed": self.policy_allowed,
            "health_score": self.health_score,
            "freshness_score": self.freshness_score,
            "reliability_score": self.reliability_score,
            "latency_score": self.latency_score,
            "history_score": self.history_score,
            "total_score": self.total_score,
        }


@dataclass
class ResolutionResult:
    """Outcome of Veyra execution resolution.

    Formal invariant:
    Routing may select only from policy-allowed candidates.
    Routing must never widen the policy-allowed action space.
    """

    selected_candidate: ExecutableAction | None
    rejected_candidates: dict[str, str] = field(default_factory=dict)
    decision: str = "select"  # select | deny | defer
    reason: str = ""
    confidence: float = 1.0
    risk_level: str = "low"  # low | medium | high | destructive
    evaluations: list[CandidateEvaluation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_candidate": self.selected_candidate.to_dict() if self.selected_candidate else None,
            "rejected_candidates": dict(self.rejected_candidates),
            "decision": self.decision,
            "reason": self.reason,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "metadata": dict(self.metadata),
        }
