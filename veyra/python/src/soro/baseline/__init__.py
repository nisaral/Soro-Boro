"""Veyra Baseline Evaluation Arms (Phase 12 Specification).

Defines the 4 explicit benchmark arms:
1. raw_agent (no middleware)
2. competent_boundary (schema validation, safe coercion, retry, idempotency)
3. static_resolution (same declarations + fallbacks as Veyra, fixed priority)
4. oracle (ground truth sanity bound)
"""

from soro.baseline.competent import CompetentBaselineMiddleware, coerce_argument_types, is_idempotent
from soro.baseline.static_resolution import (
    FairStaticResolutionMiddleware,
    StaticResolutionMiddleware,
    WeakStaticResolutionMiddleware,
)

__all__ = [
    "CompetentBaselineMiddleware",
    "StaticResolutionMiddleware",
    "FairStaticResolutionMiddleware",
    "WeakStaticResolutionMiddleware",
    "coerce_argument_types",
    "is_idempotent",
]
