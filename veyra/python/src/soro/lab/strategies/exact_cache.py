"""Veyra Strategy Lab: Exact / Cache Strategy.

Maps exact (proposed_tool, argument_keys_signature) tuples to historical resolved tools.
O(1) lookup time, high precision, zero extrapolation.
"""

from __future__ import annotations

import sys
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


class ExactCacheStrategy(ResolutionStrategy):
    """Exact cache lookup strategy."""

    def __init__(self):
        # Cache maps (proposed_tool, tuple(sorted(arg_keys))) -> dict of (target_tool -> frequency)
        self._cache: dict[tuple[str, tuple[str, ...]], dict[str, int]] = {}

    @property
    def name(self) -> str:
        return "exact_cache"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        self._cache.clear()
        for trace in training_traces:
            prop = trace.get("proposed_action", {})
            p_tool = prop.get("tool", "")
            p_args = tuple(sorted(prop.get("arguments", {}).keys()))
            target = trace.get("selected_action", {}).get("tool") if trace.get("selected_action") else None
            success = trace.get("final_success", False)

            if p_tool and target and success:
                key = (p_tool, p_args)
                if key not in self._cache:
                    self._cache[key] = {}
                self._cache[key][target] = self._cache[key].get(target, 0) + 1

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        key = (query.proposed_tool, tuple(sorted(query.proposed_arguments.keys())))
        candidates = []

        avail_names = {t["name"] for t in query.candidate_tools}

        if key in self._cache:
            freq_map = self._cache[key]
            total = sum(freq_map.values())
            sorted_targets = sorted(freq_map.items(), key=lambda kv: kv[1], reverse=True)

            for target, count in sorted_targets:
                if target in avail_names:
                    conf = count / total if total > 0 else 0.0
                    candidates.append(
                        RankedCandidate(
                            tool=target,
                            score=conf,
                            confidence=conf,
                            reason=f"exact cache hit (freq={count}/{total})",
                        )
                    )

        # If cache missed, check if proposed tool is directly available
        if not candidates and query.proposed_tool in avail_names:
            candidates.append(
                RankedCandidate(
                    tool=query.proposed_tool,
                    score=0.5,
                    confidence=0.5,
                    reason="direct tool name match in catalog",
                )
            )

        return candidates[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._cache)
        for k, v in self._cache.items():
            mem += sys.getsizeof(k) + sys.getsizeof(v)
            for target in v:
                mem += sys.getsizeof(target)
        return mem
