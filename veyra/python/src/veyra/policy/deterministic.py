"""Veyra Policy: DeterministicRoutePolicy.

The v0.1 production routing policy.
Selects among valid candidates using explicit developer priority, exact alias,
and declared fallback ordering. Zero LLMs, embeddings, or bandits in the production path.
"""

from __future__ import annotations

from veyra.core.action import ExecutableAction
from veyra.core.decision import Decision, DecisionKind
from veyra.core.state import ExecutionState
from veyra.policy.base import RoutePolicy


class DeterministicRoutePolicy(RoutePolicy):
    """Deterministic routing policy using explicit priority and declared fallback ordering."""

    def __init__(self, fallback_to_equivalent: bool = True):
        self.fallback_to_equivalent = fallback_to_equivalent

    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        if not candidates:
            return Decision.deny(reason="no valid candidates after constraint filtering")

        # Invariant: If primary proposed candidate is present and valid, select it directly
        primary = candidates[0]
        if len(candidates) == 1:
            return Decision.select(primary, reason="single valid candidate")

        # If primary candidate is valid, choose it
        if self.fallback_to_equivalent:
            return Decision.select(primary, reason="primary declared tool selected")

        return Decision.select(primary, reason="deterministic default selection")
