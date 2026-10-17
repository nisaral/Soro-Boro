"""Constrained Belief-State Recovery Controller (Experimental Algorithmic Module).

Maintains calibrated uncertainty over hidden execution states:
  - NOT_COMMITTED
  - IN_FLIGHT
  - COMMITTED
  - PARTIAL
  - DUPLICATED
  - UNKNOWN

Integrates safe read-only evidence acquisition:
  UNKNOWN -> CAN SAFE EVIDENCE REDUCE UNCERTAINTY? -> Acquire Evidence -> Update Belief -> Select Safe Action

Maximizes expected utility subject to hard safety constraint:
  maximize EU(action) subject to P(unsafe external effect) <= epsilon
  If no candidate satisfies safety: DEFER / DENY.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable

from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract, SideEffectClass


class HiddenExecutionState(str, enum.Enum):
    NOT_COMMITTED = "NOT_COMMITTED"
    IN_FLIGHT = "IN_FLIGHT"
    COMMITTED = "COMMITTED"
    PARTIAL = "PARTIAL"
    DUPLICATED = "DUPLICATED"
    UNKNOWN = "UNKNOWN"


class RecoveryActionType(str, enum.Enum):
    VERIFY = "VERIFY"
    RETRY = "RETRY"
    IDEMPOTENCY_REPLAY = "IDEMPOTENCY_REPLAY"
    RECONCILE = "RECONCILE"
    COMPENSATE = "COMPENSATE"
    FALLBACK = "FALLBACK"
    DEFER = "DEFER"
    DENY = "DENY"


@dataclass
class BeliefDistribution:
    """Discrete probability distribution over hidden execution states."""

    p_not_committed: float = 0.0
    p_in_flight: float = 0.0
    p_committed: float = 0.0
    p_partial: float = 0.0
    p_duplicated: float = 0.0
    p_unknown: float = 0.0


    def __post_init__(self) -> None:
        self.normalize()

    def normalize(self) -> None:
        total = (
            self.p_not_committed
            + self.p_in_flight
            + self.p_committed
            + self.p_partial
            + self.p_duplicated
            + self.p_unknown
        )
        if total <= 0.0:
            self.p_unknown = 1.0
            total = 1.0
        self.p_not_committed /= total
        self.p_in_flight /= total
        self.p_committed /= total
        self.p_partial /= total
        self.p_duplicated /= total
        self.p_unknown /= total

    def to_dict(self) -> dict[str, float]:
        return {
            "NOT_COMMITTED": round(self.p_not_committed, 4),
            "IN_FLIGHT": round(self.p_in_flight, 4),
            "COMMITTED": round(self.p_committed, 4),
            "PARTIAL": round(self.p_partial, 4),
            "DUPLICATED": round(self.p_duplicated, 4),
            "UNKNOWN": round(self.p_unknown, 4),
        }


@dataclass
class RecoveryCandidate:
    action_type: RecoveryActionType
    tool_or_fn: Any
    requires_capability: str = ""
    side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY
    risk: str = "low"
    expected_observability: float = 1.0


@dataclass
class ControllerDecision:
    action_type: RecoveryActionType
    belief_before: dict[str, float]
    belief_after: dict[str, float]
    evidence_acquired: bool
    evidence_details: dict[str, Any]
    expected_utility: float
    unsafe_probability: float
    reason: str
    target_action: Any = None


class BeliefStateEstimator:
    """Transparent Bayesian / deterministic belief updater for tool execution boundaries."""

    def initial_belief(self, failure_type: str, status_code: int | None = None) -> BeliefDistribution:
        fl = failure_type.lower()
        if "pre" in fl or "connection_refused" in fl or status_code in (400, 401, 403, 404, 422):
            return BeliefDistribution(p_not_committed=0.95, p_unknown=0.05)
        if "timeout" in fl or status_code == 504:
            # Post-dispatch timeout: commit status is ambiguous
            return BeliefDistribution(p_committed=0.55, p_in_flight=0.30, p_not_committed=0.15)
        if "connection_reset" in fl or "reset" in fl or status_code in (500, 502, 503):
            # Dropped socket or server 5xx: could have committed or aborted
            return BeliefDistribution(p_committed=0.60, p_partial=0.15, p_not_committed=0.25)
        if "partial" in fl:
            return BeliefDistribution(p_partial=0.85, p_committed=0.10, p_not_committed=0.05)
        return BeliefDistribution(p_unknown=1.0)

    def update_with_evidence(
        self,
        prior: BeliefDistribution,
        probe_result: dict[str, Any] | bool | None,
        probe_reliability: float = 1.0,
    ) -> BeliefDistribution:
        if probe_result is None:
            return prior

        # Check standard probe keys
        if isinstance(probe_result, bool):
            committed = probe_result
            count = 1 if committed else 0
        elif isinstance(probe_result, dict):
            committed = probe_result.get("committed", False) or probe_result.get("exists", False)
            count = probe_result.get("count", 1 if committed else 0)
        else:
            committed = bool(probe_result)
            count = 1 if committed else 0

        # Incorporate probe reliability P(probe_correct) via Bayesian update
        p_rel = max(0.5, min(1.0, probe_reliability))
        p_err = 1.0 - p_rel

        if count > 1:
            p_dup = prior.p_duplicated * p_rel + (1.0 - prior.p_duplicated) * p_err
            return BeliefDistribution(p_duplicated=p_dup, p_committed=1.0 - p_dup)

        # Baseline uninformative allocation for unknown mass
        unallocated_c = 0.5 * prior.p_unknown
        unallocated_nc = 0.5 * prior.p_unknown

        if committed:
            # Probe indicates committed: P(committed | probe=committed)
            prior_c = prior.p_committed + prior.p_in_flight + unallocated_c
            numerator = prior_c * p_rel
            denominator = numerator + (1.0 - prior_c) * p_err
            p_post = numerator / max(denominator, 1e-9)
            return BeliefDistribution(
                p_committed=p_post,
                p_in_flight=0.0,
                p_not_committed=1.0 - p_post,
            )
        else:
            # Probe indicates NOT committed: P(not_committed | probe=not_committed)
            prior_nc = prior.p_not_committed + unallocated_nc
            numerator = prior_nc * p_rel
            denominator = numerator + (1.0 - prior_nc) * p_err
            p_post = numerator / max(denominator, 1e-9)
            return BeliefDistribution(
                p_not_committed=p_post,
                p_committed=1.0 - p_post,
            )



# =========================================================================
# EXPERIMENTAL / RESEARCH CONTROLLER (Not Production Default)
# =========================================================================
class ConstrainedBeliefStateRecoveryController:
    """Constrained Belief-State Recovery Controller (EXPERIMENTAL / RESEARCH).
    
    NOTE: Production default is Deterministic Contract Enforcement with VerifiedExecutionProfile.
    This Bayesian controller is quarantined for research under partial observability.
    It operates solely on observed evidence and historical execution records,
    never receiving ground-truth or evaluator-supplied reliability parameters.
    """

    def __init__(
        self,
        epsilon_unsafe: float = 0.01,
        recovery_value: float = 100.0,
        duplicate_cost: float = 500.0,
        latency_cost_weight: float = 0.01,
        tool_call_cost: float = 1.0,
    ):
        self.epsilon_unsafe = epsilon_unsafe
        self.recovery_value = recovery_value
        self.duplicate_cost = duplicate_cost
        self.latency_cost_weight = latency_cost_weight
        self.tool_call_cost = tool_call_cost
        self.estimator = BeliefStateEstimator()

    def decide_recovery(
        self,
        failed_action: ExecutableAction,
        failure_type: str,
        contract: ExecutionContract,
        status_code: int | None = None,
        verification_fn: Callable[..., Any] | None = None,
        idempotency_key: str | None = None,
        supports_idempotency_key: bool = False,
        compensation_fn: Callable[..., Any] | None = None,
        reconcile_fn: Callable[..., Any] | None = None,
        evidence_probes: list[Callable[..., Any]] | None = None,
        historical_probe_confidence: float | None = None,
    ) -> ControllerDecision:
        # Step 1: Form initial belief distribution
        prior = self.estimator.initial_belief(failure_type, status_code)
        current_belief = prior
        evidence_acquired = False
        evidence_details: dict[str, Any] = {}

        is_mutation = (
            contract.side_effect_class in (SideEffectClass.NON_IDEMPOTENT_MUTATION, SideEffectClass.DESTRUCTIVE)
            or not failed_action.is_idempotent
        )

        # Step 2: Evidence Acquisition (Directive §4)
        # If uncertain and safe read-only evidence probe exists, acquire evidence before selecting action
        active_probe = verification_fn
        if active_probe is None and evidence_probes:
            active_probe = evidence_probes[0]

        if active_probe is not None:
            try:
                # Read-only timeout-controlled probe execution
                probe_res = active_probe(**failed_action.arguments)
                evidence_acquired = True
                # Use historical confidence if provided from past tests, or metadata from probe result, else neutral 0.90
                rel = historical_probe_confidence if historical_probe_confidence is not None else 0.90
                if isinstance(probe_res, dict) and "confidence" in probe_res:
                    rel = float(probe_res["confidence"])
                evidence_details = {
                    "probe_name": getattr(active_probe, "__name__", "evidence_probe"),
                    "result": probe_res,
                    "confidence": rel,
                }
                current_belief = self.estimator.update_with_evidence(prior, probe_res, probe_reliability=rel)
            except Exception as probe_err:
                evidence_details = {"probe_error": str(probe_err)}


        # Step 3: Candidate Generation & Safety Constraint Evaluation (Directive §3 & §5)
        candidates: list[RecoveryCandidate] = []

        if current_belief.p_committed >= 0.90:
            candidates.append(
                RecoveryCandidate(
                    action_type=RecoveryActionType.VERIFY,
                    tool_or_fn=active_probe,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    risk="none",
                )
            )

        if is_mutation:
            if supports_idempotency_key and idempotency_key:
                candidates.append(
                    RecoveryCandidate(
                        action_type=RecoveryActionType.IDEMPOTENCY_REPLAY,
                        tool_or_fn=failed_action.executable,
                        side_effect_class=contract.side_effect_class,
                        risk="low",
                    )
                )
            if current_belief.p_partial >= 0.70 and reconcile_fn:
                candidates.append(
                    RecoveryCandidate(
                        action_type=RecoveryActionType.RECONCILE,
                        tool_or_fn=reconcile_fn,
                        side_effect_class=contract.side_effect_class,
                        risk="medium",
                    )
                )
            if current_belief.p_partial >= 0.50 and compensation_fn:
                candidates.append(
                    RecoveryCandidate(
                        action_type=RecoveryActionType.COMPENSATE,
                        tool_or_fn=compensation_fn,
                        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
                        risk="medium",
                    )
                )
            if current_belief.p_not_committed >= (1.0 - self.epsilon_unsafe):
                candidates.append(
                    RecoveryCandidate(
                        action_type=RecoveryActionType.RETRY,
                        tool_or_fn=failed_action.executable,
                        side_effect_class=contract.side_effect_class,
                        risk="high",
                    )
                )
        else:
            # Read-only or idempotent: always safe to retry
            candidates.append(
                RecoveryCandidate(
                    action_type=RecoveryActionType.RETRY,
                    tool_or_fn=failed_action.executable,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    risk="none",
                )
            )

        # Step 4: Constrained Optimization across candidates
        best_candidate: RecoveryCandidate | None = None
        best_utility = -float("inf")
        selected_p_unsafe = 1.0

        for cand in candidates:
            # P(unsafe external effect) calculation
            if cand.action_type == RecoveryActionType.VERIFY:
                p_unsafe = 0.0
                p_success = current_belief.p_committed
            elif cand.action_type == RecoveryActionType.IDEMPOTENCY_REPLAY:
                p_unsafe = 0.0  # Protected by idempotency key
                p_success = 1.0
            elif cand.action_type == RecoveryActionType.RECONCILE:
                p_unsafe = current_belief.p_not_committed * 0.05
                p_success = current_belief.p_partial
            elif cand.action_type == RecoveryActionType.COMPENSATE:
                p_unsafe = current_belief.p_not_committed * 0.05
                p_success = current_belief.p_partial
            elif cand.action_type == RecoveryActionType.RETRY:
                if is_mutation:
                    p_unsafe = current_belief.p_committed + current_belief.p_in_flight + current_belief.p_unknown
                    p_success = current_belief.p_not_committed
                else:
                    p_unsafe = 0.0
                    p_success = 1.0
            else:
                p_unsafe = 0.0
                p_success = 0.0

            # Hard safety constraint: P(unsafe external effect) <= epsilon
            if p_unsafe > self.epsilon_unsafe:
                continue

            # Expected Utility: EU = P(success)*V_rec - P(duplicate)*C_dup - Costs
            p_dup = current_belief.p_committed if (cand.action_type == RecoveryActionType.RETRY and is_mutation) else 0.0
            utility = (p_success * self.recovery_value) - (p_dup * self.duplicate_cost) - self.tool_call_cost

            if utility > best_utility:
                best_utility = utility
                best_candidate = cand
                selected_p_unsafe = p_unsafe

        # Step 5: Fallback to safe abstention (DEFER / DENY) if no candidate passes safety constraint
        if best_candidate is None:
            return ControllerDecision(
                action_type=RecoveryActionType.DEFER,
                belief_before=prior.to_dict(),
                belief_after=current_belief.to_dict(),
                evidence_acquired=evidence_acquired,
                evidence_details=evidence_details,
                expected_utility=0.0,
                unsafe_probability=current_belief.p_committed + current_belief.p_in_flight,
                reason="Safe DEFER enforced: Unsafe replay probability exceeds safety epsilon with no verifiable probe or idempotency key.",
                target_action=None,
            )

        return ControllerDecision(
            action_type=best_candidate.action_type,
            belief_before=prior.to_dict(),
            belief_after=current_belief.to_dict(),
            evidence_acquired=evidence_acquired,
            evidence_details=evidence_details,
            expected_utility=round(best_utility, 2),
            unsafe_probability=round(selected_p_unsafe, 4),
            reason=f"Selected {best_candidate.action_type.value} maximizing expected utility ({best_utility:.1f}) under P(unsafe) <= {self.epsilon_unsafe}",
            target_action=best_candidate.tool_or_fn,
        )
