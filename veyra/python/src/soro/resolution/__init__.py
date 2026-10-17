"""Veyra Resolution Layer.

Formal execution resolution pipeline conforming to Sections 2 and 3:
- Candidate Generation
- Hard Constraint Filtering (authorization, tenant, capability, contract, side-effect safety, transaction invariants)
- Policy Resolution
- State / Health / Freshness Checks
- Preference Ranking
- Deterministic Resolvers (StaticPriority, HealthAware, FreshnessAware, PolicyAware, VeyraResolver)
- Formal 15-class Failure Taxonomy
"""

from __future__ import annotations

from soro.resolution.resolvers import (
    BaseResolver,
    FreshnessAwareResolver,
    HealthAwareResolver,
    PolicyAwareResolver,
    StaticPriorityResolver,
    VeyraResolver,
)
from soro.resolution.taxonomy import (
    TrajectoryFailureKind,
    TrajectoryFailureRecord,
    VEYRA_ADDRESSABLE_FAILURES,
    classify_trajectory_failure,
)
from soro.resolution.types import (
    CandidateEvaluation,
    ResolutionDecision,
    ResolutionResult,
    RiskLevel,
)

__all__ = [
    "ResolutionDecision",
    "RiskLevel",
    "CandidateEvaluation",
    "ResolutionResult",
    "BaseResolver",
    "StaticPriorityResolver",
    "HealthAwareResolver",
    "FreshnessAwareResolver",
    "PolicyAwareResolver",
    "VeyraResolver",
    "TrajectoryFailureKind",
    "TrajectoryFailureRecord",
    "VEYRA_ADDRESSABLE_FAILURES",
    "classify_trajectory_failure",
]
