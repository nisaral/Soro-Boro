"""Veyra Strategy Lab: TAGE-Style Variable-History Predictor Strategy.

Adapts the TAGE (TAgged GEometric history length) branch prediction architecture
for tool sequence routing:
- Base predictor T0 (history length 0)
- Tagged tables T1 (L=1), T2 (L=2), T3 (L=4), T4 (L=8)
- 3-bit saturating counters (0 to 7) for confidence tracking
- Provider selection with longest-matching history rule
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy

HISTORY_LENGTHS = [0, 1, 2, 4, 8]


@dataclass
class TageEntry:
    target_tool: str
    counter: int = 4  # 3-bit saturating counter initialized at neutral confidence (4)
    useful: int = 0


def compute_tag(proposed_tool: str, hist_slice: tuple[str, ...]) -> str:
    return f"{proposed_tool}|{'->'.join(hist_slice)}"


class TageHistoryStrategy(ResolutionStrategy):
    """TAGE-style multi-history resolution strategy."""

    def __init__(self, history_lengths: list[int] | None = None):
        self.history_lengths = history_lengths or HISTORY_LENGTHS
        # Tagged tables for each history length: table_idx -> {tag -> TageEntry}
        self._tables: list[dict[str, TageEntry]] = [{} for _ in self.history_lengths]

    @property
    def name(self) -> str:
        return "tage_history"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        for trace in training_traces:
            if not trace.get("final_success", False):
                continue

            prop_tool = trace.get("proposed_action", {}).get("tool", "")
            target_tool = trace.get("selected_action", {}).get("tool") if trace.get("selected_action") else None
            hist = trace.get("previous_tools", [])

            if not prop_tool or not target_tool:
                continue

            for idx, h_len in enumerate(self.history_lengths):
                hist_slice = tuple(hist[-h_len:]) if h_len > 0 and len(hist) >= h_len else (() if h_len == 0 else None)
                if hist_slice is None:
                    continue

                tag = compute_tag(prop_tool, hist_slice)
                table = self._tables[idx]

                if tag not in table:
                    table[tag] = TageEntry(target_tool=target_tool, counter=4)
                else:
                    entry = table[tag]
                    if entry.target_tool == target_tool:
                        # Saturate up to 7
                        entry.counter = min(7, entry.counter + 1)
                    else:
                        # Decrement on mismatch
                        entry.counter = max(0, entry.counter - 1)
                        if entry.counter <= 1:
                            # Replace target tool on depleted counter
                            entry.target_tool = target_tool
                            entry.counter = 4

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        avail_tools = {t["name"] for t in query.candidate_tools}
        hist = query.history
        prop_tool = query.proposed_tool

        hits: list[tuple[int, TageEntry]] = []

        # Find all matching tables from longest history to base
        for idx in reversed(range(len(self.history_lengths))):
            h_len = self.history_lengths[idx]
            hist_slice = tuple(hist[-h_len:]) if h_len > 0 and len(hist) >= h_len else (() if h_len == 0 else None)
            if hist_slice is None:
                continue

            tag = compute_tag(prop_tool, hist_slice)
            if tag in self._tables[idx]:
                entry = self._tables[idx][tag]
                if entry.target_tool in avail_tools:
                    hits.append((h_len, entry))

        candidates: list[RankedCandidate] = []
        seen = set()

        for h_len, entry in hits:
            if entry.target_tool in seen:
                continue
            seen.add(entry.target_tool)

            # Score combines history depth (longer history = more specific context) and saturating counter
            conf = entry.counter / 7.0
            score = (conf * 0.7) + (min(1.0, h_len / 8.0) * 0.3)

            candidates.append(
                RankedCandidate(
                    tool=entry.target_tool,
                    score=round(score, 4),
                    confidence=round(conf, 4),
                    reason=f"tage_match(H={h_len}, ctr={entry.counter}/7)",
                )
            )

        # Base fallback if no hit
        if not candidates and prop_tool in avail_tools:
            candidates.append(
                RankedCandidate(
                    tool=prop_tool,
                    score=0.4,
                    confidence=0.4,
                    reason="tage_unpredicted_default",
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._tables)
        for t in self._tables:
            mem += sys.getsizeof(t)
            for k, v in t.items():
                mem += sys.getsizeof(k) + sys.getsizeof(v)
        return mem
