"""Veyra Strategy Lab: Structural Matching Strategy.

Evaluates schema compatibility between proposed arguments and candidate tool parameters:
- Required parameter coverage
- Argument name Jaccard overlap
- Tool name lexical token overlap
Zero machine learning, purely deterministic schema introspection.
"""

from __future__ import annotations

import re
import sys
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


def tokenize(name: str) -> set[str]:
    """Split snake_case, camelCase, or dots into lowercase word tokens."""
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", name)
    return {t.lower() for t in tokens if len(t) > 1}


class StructuralMatchingStrategy(ResolutionStrategy):
    """Structural matching strategy evaluating parameter and schema compatibility."""

    @property
    def name(self) -> str:
        return "structural_matching"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        # Structural matching does not require offline fitting
        pass

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        prop_args = set(query.proposed_arguments.keys())
        prop_tokens = tokenize(query.proposed_tool)
        scored: list[RankedCandidate] = []

        for tool_spec in query.candidate_tools:
            name = tool_spec["name"]
            params = tool_spec.get("parameters", {})
            properties = set(params.get("properties", {}).keys())
            required = set(params.get("required", []))

            # 1. Required argument coverage (0.0 to 1.0)
            if required:
                req_cov = len(prop_args.intersection(required)) / len(required)
            else:
                req_cov = 1.0

            # 2. Argument name Jaccard similarity
            union_args = prop_args.union(properties)
            if union_args:
                jaccard_args = len(prop_args.intersection(properties)) / len(union_args)
            else:
                jaccard_args = 1.0 if not prop_args and not properties else 0.0

            # 3. Tool name token overlap
            cand_tokens = tokenize(name)
            union_tokens = prop_tokens.union(cand_tokens)
            if union_tokens:
                name_sim = len(prop_tokens.intersection(cand_tokens)) / len(union_tokens)
            else:
                name_sim = 0.0

            # Direct tool name equality bonus
            if name.lower() == query.proposed_tool.lower():
                name_sim = 1.0

            # Combined structural score
            score = (0.45 * req_cov) + (0.35 * jaccard_args) + (0.20 * name_sim)
            confidence = min(1.0, max(0.0, score))

            scored.append(
                RankedCandidate(
                    tool=name,
                    score=round(score, 4),
                    confidence=round(confidence, 4),
                    reason=f"req_cov={req_cov:.2f}, arg_jaccard={jaccard_args:.2f}, name_sim={name_sim:.2f}",
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def estimate_memory_bytes(self) -> int:
        return sys.getsizeof(self)
