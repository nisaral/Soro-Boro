"""Veyra Policy: Tool Reliability Engine (Phase 5 Specification).

Maintains online statistical reliability for each executable tool:
- Success count & failure count
- Timeout rate & rate-limit rate
- Recent failure rate (sliding window)
- Latency estimate
- Beta-Bernoulli reliability estimation with credible intervals
- EWMA (Exponentially Weighted Moving Average) for success & latency
- CUSUM (Cumulative Sum Control Chart) sequential degradation detection
- ReliabilityAwareRoutePolicy: prefers healthier candidate ONLY inside explicitly permitted equivalence set.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Any

from soro.boundary.taxonomy import FailureClassification, FailureKind, FailureProvenance
from soro.core.action import ExecutableAction
from soro.core.decision import Decision
from soro.core.state import ExecutionState
from soro.core.trace import ExecutionTrace
from soro.policy.base import RoutePolicy


@dataclass
class ToolHealthStats:
    """Statistical health state of a single executable tool."""

    tool_name: str
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    total_calls: int = 0

    # Sliding window of recent binary outcomes (True = success, False = failure)
    recent_window: list[bool] = field(default_factory=list)
    window_size: int = 20

    # Beta-Bernoulli prior (alpha_0=1, beta_0=1 represents uniform prior)
    alpha_prior: float = 1.0
    beta_prior: float = 1.0

    # EWMA parameters (decay lambda = 0.2 gives higher weight to recent calls)
    ewma_lambda: float = 0.2
    ewma_success_rate: float = 1.0
    ewma_latency_ms: float = 10.0

    # CUSUM parameters for detecting abrupt degradation in error rate
    # Target in-control error rate mu_0 = 0.05, slack allowance k = 0.10, alarm threshold h = 3.0
    cusum_s: float = 0.0
    cusum_mu0: float = 0.05
    cusum_k: float = 0.10
    cusum_threshold: float = 3.0
    is_degraded: bool = False

    def observe(
        self,
        success: bool,
        latency_ms: float = 0.0,
        provenance: FailureProvenance | str | None = None,
    ) -> None:
        self.total_calls += 1
        prov_str = str(provenance) if provenance else ""

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if "TIMEOUT" in prov_str or "timeout" in prov_str.lower():
                self.timeout_count += 1
            if "RATE_LIMIT" in prov_str or "rate" in prov_str.lower():
                self.rate_limit_count += 1

        # Sliding window update
        self.recent_window.append(success)
        if len(self.recent_window) > self.window_size:
            self.recent_window.pop(0)

        # EWMA updates
        outcome_val = 1.0 if success else 0.0
        self.ewma_success_rate = (self.ewma_lambda * outcome_val) + ((1.0 - self.ewma_lambda) * self.ewma_success_rate)
        if latency_ms > 0:
            self.ewma_latency_ms = (self.ewma_lambda * latency_ms) + ((1.0 - self.ewma_lambda) * self.ewma_latency_ms)

        # CUSUM change detector update (tracks error spikes)
        error_val = 0.0 if success else 1.0
        increment = error_val - self.cusum_mu0 - self.cusum_k
        self.cusum_s = max(0.0, self.cusum_s + increment)
        if self.cusum_s >= self.cusum_threshold:
            self.is_degraded = True
        elif self.cusum_s <= 0.5:
            self.is_degraded = False

    @property
    def timeout_rate(self) -> float:
        return (self.timeout_count / self.total_calls) if self.total_calls > 0 else 0.0

    @property
    def rate_limit_rate(self) -> float:
        return (self.rate_limit_count / self.total_calls) if self.total_calls > 0 else 0.0

    @property
    def recent_failure_rate(self) -> float:
        if not self.recent_window:
            return 0.0
        failures = sum(1 for s in self.recent_window if not s)
        return failures / len(self.recent_window)

    @property
    def beta_mean(self) -> float:
        """Expected reliability under Beta-Bernoulli posterior E[theta]."""
        a = self.alpha_prior + self.success_count
        b = self.beta_prior + self.failure_count
        return a / (a + b)

    @property
    def beta_lower_credible_bound(self) -> float:
        """Conservative lower bound (approx 95% one-sided) E[theta] - 1.65 * std."""
        a = self.alpha_prior + self.success_count
        b = self.beta_prior + self.failure_count
        mean = a / (a + b)
        var = (a * b) / (((a + b) ** 2) * (a + b + 1.0))
        std = math.sqrt(var)
        return max(0.0, mean - (1.65 * std))

    @property
    def composite_health_score(self) -> float:
        """Unified health metric combining Bayesian mean, EWMA, and CUSUM status."""
        degraded_penalty = 0.40 if self.is_degraded else 0.0
        raw_score = (0.50 * self.beta_lower_credible_bound) + (0.50 * self.ewma_success_rate) - degraded_penalty
        return max(0.0, min(1.0, raw_score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_rate": round(self.timeout_rate, 4),
            "rate_limit_rate": round(self.rate_limit_rate, 4),
            "recent_failure_rate": round(self.recent_failure_rate, 4),
            "beta_expected_reliability": round(self.beta_mean, 4),
            "beta_lower_bound": round(self.beta_lower_credible_bound, 4),
            "ewma_success_rate": round(self.ewma_success_rate, 4),
            "ewma_latency_ms": round(self.ewma_latency_ms, 2),
            "cusum_statistic": round(self.cusum_s, 2),
            "is_degraded": self.is_degraded,
            "composite_health": round(self.composite_health_score, 4),
        }


class ToolReliabilityTracker:
    """Registry maintaining real-time reliability statistics across all registered tools."""

    def __init__(self):
        self._stats: dict[str, ToolHealthStats] = {}

    def get_or_create(self, tool_name: str) -> ToolHealthStats:
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolHealthStats(tool_name=tool_name)
        return self._stats[tool_name]

    def observe_trace(self, trace: ExecutionTrace | dict[str, Any]) -> None:
        if isinstance(trace, ExecutionTrace):
            t_dict = trace.to_dict(redact=False)
        else:
            t_dict = dict(trace)

        resolved_tool = t_dict.get("resolved_tool") or t_dict.get("selected_action", {}).get("tool")
        if not resolved_tool:
            return

        success = (t_dict.get("outcome") == "success") or t_dict.get("final_success", False)
        latency = t_dict.get("latency_ms") or t_dict.get("latency", 0.0)

        fail_info = t_dict.get("failure") or {}
        prov = fail_info.get("provenance") if isinstance(fail_info, dict) else t_dict.get("failure_provenance")

        stats = self.get_or_create(resolved_tool)
        stats.observe(success=success, latency_ms=latency, provenance=prov)

    def get_health_score(self, tool_name: str) -> float:
        if tool_name not in self._stats:
            # Unobserved tool starts with neutral prior (0.75 composite health)
            return 0.75
        return self._stats[tool_name].composite_health_score

    def get_summary(self) -> dict[str, dict[str, Any]]:
        return {name: stats.to_dict() for name, stats in self._stats.items()}


class ReliabilityAwareRoutePolicy(RoutePolicy):
    """Route policy that prefers healthier candidates strictly within the explicitly declared equivalence set."""

    def __init__(
        self,
        tracker: ToolReliabilityTracker | None = None,
        health_delta_threshold: float = 0.20,
    ):
        self.tracker = tracker or ToolReliabilityTracker()
        self.health_delta_threshold = health_delta_threshold

    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        if not candidates:
            return Decision.deny(reason="no valid candidates after constraint filtering")

        if len(candidates) == 1:
            return Decision.select(candidates[0], reason="single valid candidate")

        primary = candidates[0]
        primary_health = self.tracker.get_health_score(primary.tool)

        best_candidate = primary
        best_health = primary_health
        health_reasons = []

        # Invariant: ONLY evaluate candidates inside the explicitly declared equivalence set passed in candidates
        for cand in candidates[1:]:
            cand_health = self.tracker.get_health_score(cand.tool)
            # If an alternate candidate has substantially higher health (>= delta threshold) or primary is degraded
            primary_stats = self.tracker._stats.get(primary.tool)
            primary_degraded = primary_stats.is_degraded if primary_stats else False

            if (cand_health - primary_health >= self.health_delta_threshold) or (primary_degraded and cand_health > primary_health):
                if cand_health > best_health:
                    best_health = cand_health
                    best_candidate = cand
                    health_reasons.append(
                        f"preferred healthier '{cand.tool}' (health={cand_health:.2f}) over primary '{primary.tool}' (health={primary_health:.2f})"
                    )

        if best_candidate.tool != primary.tool:
            reason_str = "; ".join(health_reasons)
            return Decision.select(best_candidate, reason=f"reliability routing: {reason_str}")

        return Decision.select(
            primary,
            reason=f"primary candidate selected (health={primary_health:.2f})",
        )
