"""Veyra Policy: RoutePolicy abstract interface.

Defines the contract for all routing strategies (Deterministic, BM25, Embedding, TAGE, Bandits, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from veyra.core.action import ExecutableAction
from veyra.core.decision import Decision
from veyra.core.state import ExecutionState


class RoutePolicy(ABC):
    """Abstract routing policy interface.

    Responsible for deciding which candidate action to SELECT, DEFER, or DENY.
    """

    @abstractmethod
    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        """Resolve a candidate action for execution."""
        pass
