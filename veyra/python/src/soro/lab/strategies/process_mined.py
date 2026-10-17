"""Veyra Strategy Lab: Process-Mined Routing Strategy.

Mines workflow transition graphs from successful multi-step execution traces:
- Computes transition probability matrix P(T_next | T_prev)
- Prioritizes structurally plausible next-step capabilities based on workflow graph
- Zero LLMs, purely statistical process mining
"""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


class ProcessMinedStrategy(ResolutionStrategy):
    """Process-mined transition routing strategy."""

    def __init__(self):
        # transitions[prev_tool][next_tool] = frequency
        self._transitions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._start_counts: dict[str, int] = defaultdict(int)
        self._tool_occurrences: dict[str, int] = defaultdict(int)

    @property
    def name(self) -> str:
        return "process_mined"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        self._transitions.clear()
        self._start_counts.clear()
        self._tool_occurrences.clear()

        # Group traces by task_id to extract coherent tool call workflows
        task_traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trace in training_traces:
            if trace.get("final_success", False):
                t_id = trace.get("task_id", "")
                task_traces[t_id].append(trace)

        for t_id, trace_list in task_traces.items():
            # Sort by turn_index
            trace_list.sort(key=lambda x: x.get("turn_index", 1))
            executed_tools = []
            for t in trace_list:
                sel = t.get("selected_action")
                tool = sel.get("tool") if sel else t.get("proposed_action", {}).get("tool")
                if tool:
                    executed_tools.append(tool)

            if not executed_tools:
                continue

            self._start_counts[executed_tools[0]] += 1
            for i in range(len(executed_tools)):
                curr_tool = executed_tools[i]
                self._tool_occurrences[curr_tool] += 1
                if i > 0:
                    prev_tool = executed_tools[i - 1]
                    self._transitions[prev_tool][curr_tool] += 1

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        prev_tool = query.history[-1] if query.history else None
        avail_tools = {t["name"] for t in query.candidate_tools}

        scored: list[RankedCandidate] = []

        if prev_tool and prev_tool in self._transitions:
            next_map = self._transitions[prev_tool]
            total = sum(next_map.values())
            for t_name in avail_tools:
                count = next_map.get(t_name, 0)
                prob = (count / total) if total > 0 else 0.0

                # Compatibility bonus if proposed_tool shares name tokens with candidate
                bonus = 0.2 if query.proposed_tool in t_name or t_name in query.proposed_tool else 0.0
                score = prob + bonus
                conf = prob

                if score > 0.0:
                    scored.append(
                        RankedCandidate(
                            tool=t_name,
                            score=round(score, 4),
                            confidence=round(conf, 4),
                            reason=f"process_transition(P({t_name}|{prev_tool})={prob:.2f})",
                        )
                    )
        elif not prev_tool:
            # Initial action in workflow
            total_starts = sum(self._start_counts.values())
            for t_name in avail_tools:
                count = self._start_counts.get(t_name, 0)
                prob = (count / total_starts) if total_starts > 0 else 0.0
                bonus = 0.2 if query.proposed_tool in t_name or t_name in query.proposed_tool else 0.0
                score = prob + bonus
                if score > 0.0:
                    scored.append(
                        RankedCandidate(
                            tool=t_name,
                            score=round(score, 4),
                            confidence=round(prob, 4),
                            reason=f"process_start(P({t_name})={prob:.2f})",
                        )
                    )

        # Fallback if unobserved in process graph
        if not scored and query.proposed_tool in avail_tools:
            scored.append(
                RankedCandidate(
                    tool=query.proposed_tool,
                    score=0.3,
                    confidence=0.3,
                    reason="process_fallback_default",
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._transitions) + sys.getsizeof(self._start_counts) + sys.getsizeof(self._tool_occurrences)
        for k, v in self._transitions.items():
            mem += sys.getsizeof(k) + sys.getsizeof(v)
            for sub_k in v:
                mem += sys.getsizeof(sub_k)
        return mem
