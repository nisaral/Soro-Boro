"""Standard Evaluation Metrics Schema (Directive §11, §14, §21)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BaselineRunMetric:
    system_name: str
    n_scenarios: int
    safe_recovery_rate: float
    duplicate_effect_rate: float
    unsafe_action_rate: float
    unnecessary_abstention_rate: float
    abstention_rate: float
    mean_latency_ms: float
    p95_latency_ms: float
    probe_calls: int
    oracle_gap: float = 0.0
    ci_95_low: float = 0.0
    ci_95_high: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_wilson_ci(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculates Wilson score interval for binomial proportion."""
    if total <= 0:
        return 0.0, 0.0
    z = 1.95996  # 95%
    p_hat = successes / total
    denom = 1.0 + (z**2) / total
    center = (p_hat + (z**2) / (2 * total)) / denom
    err = (z * math.sqrt((p_hat * (1 - p_hat) / total) + (z**2 / (4 * total**2)))) / denom
    return max(0.0, center - err), min(1.0, center + err)
