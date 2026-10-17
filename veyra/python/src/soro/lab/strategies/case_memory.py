"""Veyra Strategy Lab: Case-Based Execution Memory Strategy.

Implements Case-Based Reasoning (CBR) retrieval from past successful execution trajectories.
Matches proposed tool signatures, argument sets, and contextual history against verified prior cases.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


@dataclass
class ExecutionCase:
    proposed_tool: str
    arg_keys: frozenset[str]
    prev_tool: str | None
    resolved_tool: str
    success_count: int = 1


class CaseBasedMemoryStrategy(ResolutionStrategy):
    """Case-based execution memory strategy."""

    def __init__(self):
        self._cases: list[ExecutionCase] = []

    @property
    def name(self) -> str:
        return "case_based_memory"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        self._cases.clear()
        case_map: dict[tuple[str, frozenset[str], str | None, str], int] = {}

        for trace in training_traces:
            if not trace.get("final_success", False):
                continue

            prop = trace.get("proposed_action", {})
            p_tool = prop.get("tool", "")
            p_args = frozenset(prop.get("arguments", {}).keys())

            sel = trace.get("selected_action")
            resolved = sel.get("tool") if sel else None

            prev_tool = trace.get("previous_tools", [])[-1] if trace.get("previous_tools") else None

            if p_tool and resolved:
                key = (p_tool, p_args, prev_tool, resolved)
                case_map[key] = case_map.get(key, 0) + 1

        for (p_tool, p_args, prev_tool, resolved), count in case_map.items():
            self._cases.append(
                ExecutionCase(
                    proposed_tool=p_tool,
                    arg_keys=p_args,
                    prev_tool=prev_tool,
                    resolved_tool=resolved,
                    success_count=count,
                )
            )

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        q_args = frozenset(query.proposed_arguments.keys())
        q_prev = query.history[-1] if query.history else None
        avail_tools = {t["name"] for t in query.candidate_tools}

        tool_scores: dict[str, float] = {}
        tool_counts: dict[str, int] = {}

        for case in self._cases:
            if case.resolved_tool not in avail_tools:
                continue

            # 1. Proposed tool similarity
            tool_sim = 1.0 if case.proposed_tool == query.proposed_tool else 0.0

            # 2. Argument Jaccard similarity
            union = q_args.union(case.arg_keys)
            inter = q_args.intersection(case.arg_keys)
            arg_sim = (len(inter) / len(union)) if union else 1.0

            # 3. Contextual previous tool similarity
            prev_sim = 1.0 if case.prev_tool == q_prev else 0.0

            sim = (0.5 * tool_sim) + (0.35 * arg_sim) + (0.15 * prev_sim)

            if sim > 0.3:
                weighted_score = sim * min(2.0, 1.0 + (case.success_count * 0.1))
                if case.resolved_tool not in tool_scores or weighted_score > tool_scores[case.resolved_tool]:
                    tool_scores[case.resolved_tool] = weighted_score
                    tool_counts[case.resolved_tool] = case.success_count

        # Fallback if no matching cases found: check direct catalog presence
        if not tool_scores and query.proposed_tool in avail_tools:
            tool_scores[query.proposed_tool] = 0.4
            tool_counts[query.proposed_tool] = 1

        candidates: list[RankedCandidate] = []
        for t_name, score in sorted(tool_scores.items(), key=lambda kv: kv[1], reverse=True):
            conf = min(1.0, score / 1.5)
            candidates.append(
                RankedCandidate(
                    tool=t_name,
                    score=round(score, 4),
                    confidence=round(conf, 4),
                    reason=f"cbr_sim={score:.3f} (past_cases={tool_counts.get(t_name, 1)})",
                )
            )

        return candidates[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._cases)
        for c in self._cases:
            mem += sys.getsizeof(c)
        return mem
