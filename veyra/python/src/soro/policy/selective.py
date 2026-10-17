"""Veyra Policy: Selective Resolution & Calibrated Uncertainty (Phase 6 Specification).

Implements calibrated selective routing:
- High confidence (>= theta): SELECT
- Insufficient confidence (< theta): DEFER
- Policy or hard constraint forbidden: DENY
- Invariant: Never force a low-confidence substitution!
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from soro.core.action import ExecutableAction
from soro.core.decision import Decision, DecisionKind
from soro.core.state import ExecutionState
from soro.policy.base import RoutePolicy
from soro.policy.history_adaptive import OnlineExecutionMemory
from soro.policy.reliability import ToolReliabilityTracker


@dataclass
class CalibratedScore:
    tool: str
    confidence: float
    uncertainty: float
    health_score: float
    history_score: float
    schema_score: float
    is_forbidden: bool = False
    deny_reason: str = ""


class CalibratedUncertaintyEstimator:
    """Estimates calibrated confidence and uncertainty for candidate tools."""

    def __init__(
        self,
        memory: OnlineExecutionMemory | None = None,
        tracker: ToolReliabilityTracker | None = None,
    ):
        self.memory = memory or OnlineExecutionMemory()
        self.tracker = tracker or ToolReliabilityTracker()

    def evaluate_candidate(
        self,
        candidate: ExecutableAction,
        proposal: ExecutableAction,
        state: ExecutionState,
    ) -> CalibratedScore:
        name = candidate.tool

        # Check policy constraints (allowed_tools)
        allowed_tools = state.context.get("allowed_tools")
        if allowed_tools is not None and name not in allowed_tools:
            return CalibratedScore(
                tool=name,
                confidence=0.0,
                uncertainty=1.0,
                health_score=0.0,
                history_score=0.0,
                schema_score=0.0,
                is_forbidden=True,
                deny_reason=f"tool '{name}' is not in policy-allowed tool set",
            )

        # Check risk constraints
        max_risk = state.context.get("max_risk")
        if max_risk == "low" and candidate.risk_class in ("medium", "high", "destructive"):
            return CalibratedScore(
                tool=name,
                confidence=0.0,
                uncertainty=1.0,
                health_score=0.0,
                history_score=0.0,
                schema_score=0.0,
                is_forbidden=True,
                deny_reason=f"tool '{name}' risk class '{candidate.risk_class}' exceeds allowed 'low'",
            )

        # 1. Health score (Bayesian reliability + EWMA - CUSUM)
        health = self.tracker.get_health_score(name)

        # 2. History & TAGE score
        history = list(state.previous_tools)
        tage_tool, h_len, tage_conf = self.memory.predict_tage(
            proposed_tool=proposal.tool,
            arguments=proposal.arguments,
            history=history,
            allowed_candidates={name},
        )
        hist_score = tage_conf if tage_tool == name else (0.50 if name == proposal.tool else 0.30)

        # 3. Schema & argument compatibility
        schema = candidate.metadata.get("schema") or {}
        req = schema.get("required") or schema.get("parameters", {}).get("required", [])
        if req:
            req_matched = sum(1 for r in req if r in candidate.arguments)
            schema_score = req_matched / len(req)
        else:
            schema_score = 1.0

        # Calibrated multiplicative confidence
        raw_conf = (0.40 * health) + (0.35 * hist_score) + (0.25 * schema_score)
        conf = max(0.0, min(1.0, raw_conf))
        uncertainty = 1.0 - conf

        return CalibratedScore(
            tool=name,
            confidence=round(conf, 4),
            uncertainty=round(uncertainty, 4),
            health_score=round(health, 4),
            history_score=round(hist_score, 4),
            schema_score=round(schema_score, 4),
        )


class SelectiveResolutionPolicy(RoutePolicy):
    """Calibrated selective route policy enforcing SELECT / DEFER / DENY."""

    def __init__(
        self,
        estimator: CalibratedUncertaintyEstimator | None = None,
        select_threshold: float = 0.65,
    ):
        self.estimator = estimator or CalibratedUncertaintyEstimator()
        self.select_threshold = select_threshold

    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        if not candidates:
            return Decision.deny(reason="no candidates available after constraint filtering")

        proposal_act = candidates[0]
        scored_candidates: list[tuple[ExecutableAction, CalibratedScore]] = []

        for cand in candidates:
            score = self.estimator.evaluate_candidate(cand, proposal_act, state)
            scored_candidates.append((cand, score))

        # Check if all candidates are forbidden -> DENY
        valid_candidates = [(c, s) for c, s in scored_candidates if not s.is_forbidden]
        if not valid_candidates:
            first_reason = scored_candidates[0][1].deny_reason or "candidates forbidden by policy"
            return Decision.deny(reason=first_reason)

        # Sort valid candidates by calibrated confidence
        valid_candidates.sort(key=lambda cs: cs[1].confidence, reverse=True)
        best_cand, best_score = valid_candidates[0]

        # Case 1: High confidence (>= select_threshold) -> SELECT
        if best_score.confidence >= self.select_threshold:
            return Decision.select(
                best_cand,
                reason=(
                    f"selective resolution SELECT: calibrated confidence {best_score.confidence:.2f} "
                    f">= {self.select_threshold:.2f} (health={best_score.health_score:.2f}, hist={best_score.history_score:.2f})"
                ),
            )

        # Case 2: Insufficient confidence (< select_threshold) -> DEFER
        # INVARIANT: Never force a low-confidence substitution!
        return Decision.defer(
            reason=(
                f"selective resolution DEFER: confidence {best_score.confidence:.2f} is insufficient "
                f"(< {self.select_threshold:.2f}, uncertainty={best_score.uncertainty:.2f}) for tool '{best_cand.tool}'"
            )
        )
