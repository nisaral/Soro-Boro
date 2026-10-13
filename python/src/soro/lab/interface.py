"""Veyra Resolution Strategy Lab: Common Plugin Interface (Phase 3 Specification).

Defines the contract for offline resolution strategies:
1. exact/cache
2. structural matching
3. BM25
4. dense embedding
5. case-based execution memory
6. TAGE-style variable-history policy
7. process-mined routing
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolutionQuery:
    """Input query presented to a resolution strategy."""

    proposed_tool: str
    proposed_arguments: dict[str, Any]
    candidate_tools: list[dict[str, Any]]  # Catalog of available tool schemas
    history: list[str] = field(default_factory=list)  # Prior tool sequence e.g. ["login", "get_token"]
    context: dict[str, Any] = field(default_factory=dict)
    query_text: str = ""  # Natural language instruction or intent if available


@dataclass
class RankedCandidate:
    """A scored candidate returned by a resolution strategy."""

    tool: str
    score: float
    confidence: float = 1.0  # Calibrated confidence 0.0 to 1.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyMetrics:
    """Standard evaluation metrics computed for an offline strategy."""

    strategy_name: str
    recall_at_1: float
    recall_at_3: float
    mrr: float
    ndcg: float
    wrong_tool_rate: float
    deferral_rate: float
    coverage: float
    mean_latency_ms: float
    memory_footprint_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy_name,
            "Recall@1": round(self.recall_at_1, 4),
            "Recall@3": round(self.recall_at_3, 4),
            "MRR": round(self.mrr, 4),
            "NDCG": round(self.ndcg, 4),
            "wrong_tool_rate": round(self.wrong_tool_rate, 4),
            "deferral_rate": round(self.deferral_rate, 4),
            "coverage": round(self.coverage, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "memory_footprint_kb": round(self.memory_footprint_bytes / 1024, 2),
        }


class ResolutionStrategy(ABC):
    """Abstract interface for all resolution strategy plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the strategy plugin."""
        pass

    @abstractmethod
    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        """Train or index historical execution traces."""
        pass

    @abstractmethod
    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        """Rank candidate tools for the given resolution query."""
        pass

    @abstractmethod
    def estimate_memory_bytes(self) -> int:
        """Estimate the memory footprint of this strategy's internal state / index."""
        pass
