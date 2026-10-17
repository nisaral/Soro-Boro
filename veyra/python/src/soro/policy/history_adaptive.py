"""Veyra Policy: Case-Based Execution Memory & TAGE-Style History Policy (Phase 4 Specification).

Learns online from successful execution traces without any LLM dependency:
1. Online execution memory matching:
   - proposed tool name
   - argument shape (names + value types)
   - recent action history (H1, H2, H4, H8)
   - previous failure context
   - tool health
2. TAGE-style multi-history predictor with 3-bit saturating counters (0 to 7)
3. Safety invariants enforced behind RoutePolicy interface.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from soro.core.action import ExecutableAction
from soro.core.decision import Decision
from soro.core.state import ExecutionState
from soro.core.trace import ExecutionTrace
from soro.policy.base import RoutePolicy

HISTORY_LENGTHS = [0, 1, 2, 4, 8]


def get_argument_shape(arguments: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Extract argument names and their primitive type signatures."""
    sig = []
    for k in sorted(arguments.keys()):
        v = arguments[k]
        type_name = type(v).__name__
        sig.append((k, type_name))
    return tuple(sig)


@dataclass
class MemoryCase:
    proposed_tool: str
    arg_shape: tuple[tuple[str, str], ...]
    history_slice: tuple[str, ...]
    previous_failure: str | None
    resolved_tool: str
    success_count: int = 1
    failure_count: int = 0


@dataclass
class TageHistoryEntry:
    target_tool: str
    counter: int = 4  # 3-bit saturating counter (0=strong wrong, 4=neutral, 7=strong right)


class OnlineExecutionMemory:
    """Stores online execution cases and maintains TAGE history tables."""

    def __init__(self, history_lengths: list[int] | None = None):
        self.history_lengths = history_lengths or HISTORY_LENGTHS
        # TAGE tables: table_index -> {tag: TageHistoryEntry}
        self.tage_tables: list[dict[str, TageHistoryEntry]] = [{} for _ in self.history_lengths]
        # Cases list
        self.cases: list[MemoryCase] = []
        # Tool health stats: tool_name -> {"success": int, "failure": int}
        self.tool_health: dict[str, dict[str, int]] = {}

    def _compute_tag(self, proposed_tool: str, hist_slice: tuple[str, ...], arg_shape: tuple[tuple[str, str], ...]) -> str:
        shape_str = ",".join(f"{k}:{t}" for k, t in arg_shape)
        hist_str = "->".join(hist_slice)
        return f"{proposed_tool}#[{shape_str}]@{hist_str}"

    def observe(self, trace: ExecutionTrace | dict[str, Any]) -> None:
        """Update online memory and TAGE counters from an execution trace."""
        if isinstance(trace, ExecutionTrace):
            t_dict = trace.to_dict(redact=False)
        else:
            t_dict = dict(trace)

        prop = t_dict.get("proposal", {})
        p_tool = prop.get("tool", "")
        p_args = prop.get("arguments", {})
        arg_shape = get_argument_shape(p_args)

        resolved_tool = t_dict.get("resolved_tool") or t_dict.get("selected_action", {}).get("tool")
        success = t_dict.get("outcome") == "success" or t_dict.get("final_success", False)
        history = tuple(t_dict.get("previous_tools", []))

        failure = t_dict.get("failure")
        fail_kind = failure.get("kind") if isinstance(failure, dict) else None

        if not p_tool or not resolved_tool:
            return

        # Update tool health
        if resolved_tool not in self.tool_health:
            self.tool_health[resolved_tool] = {"success": 0, "failure": 0}

        if success:
            self.tool_health[resolved_tool]["success"] += 1
        else:
            self.tool_health[resolved_tool]["failure"] += 1

        # Update TAGE tables across all geometric history lengths
        for idx, h_len in enumerate(self.history_lengths):
            h_slice = history[-h_len:] if h_len > 0 and len(history) >= h_len else (() if h_len == 0 else None)
            if h_slice is None:
                continue

            tag = self._compute_tag(p_tool, h_slice, arg_shape)
            table = self.tage_tables[idx]

            if tag not in table:
                if success:
                    table[tag] = TageHistoryEntry(target_tool=resolved_tool, counter=5)
            else:
                entry = table[tag]
                if success:
                    if entry.target_tool == resolved_tool:
                        entry.counter = min(7, entry.counter + 1)
                    else:
                        entry.counter = max(0, entry.counter - 1)
                        if entry.counter <= 1:
                            entry.target_tool = resolved_tool
                            entry.counter = 4
                else:
                    if entry.target_tool == resolved_tool:
                        entry.counter = max(0, entry.counter - 1)

        # Store or update memory case on success
        if success:
            found = False
            for c in self.cases:
                if (
                    c.proposed_tool == p_tool
                    and c.arg_shape == arg_shape
                    and c.resolved_tool == resolved_tool
                ):
                    c.success_count += 1
                    found = True
                    break
            if not found:
                self.cases.append(
                    MemoryCase(
                        proposed_tool=p_tool,
                        arg_shape=arg_shape,
                        history_slice=history[-2:] if len(history) >= 2 else history,
                        previous_failure=fail_kind,
                        resolved_tool=resolved_tool,
                        success_count=1,
                    )
                )

    def predict_tage(
        self,
        proposed_tool: str,
        arguments: dict[str, Any],
        history: list[str],
        allowed_candidates: set[str],
    ) -> tuple[str | None, int, float]:
        """Query TAGE tables using longest matching history rule.
        
        Returns (predicted_tool, history_length, confidence_0_to_1).
        """
        arg_shape = get_argument_shape(arguments)
        hist_tuple = tuple(history)

        for idx in reversed(range(len(self.history_lengths))):
            h_len = self.history_lengths[idx]
            h_slice = hist_tuple[-h_len:] if h_len > 0 and len(hist_tuple) >= h_len else (() if h_len == 0 else None)
            if h_slice is None:
                continue

            tag = self._compute_tag(proposed_tool, h_slice, arg_shape)
            table = self.tage_tables[idx]

            if tag in table:
                entry = table[tag]
                if entry.target_tool in allowed_candidates and entry.counter >= 4:
                    conf = entry.counter / 7.0
                    return entry.target_tool, h_len, conf

        return None, 0, 0.0

    def query_case_similarity(
        self,
        proposed_tool: str,
        arguments: dict[str, Any],
        history: list[str],
        allowed_candidates: set[str],
    ) -> tuple[str | None, float]:
        """Query case-based execution memory for candidate match."""
        arg_shape = get_argument_shape(arguments)
        q_keys = set(arguments.keys())
        q_prev = history[-1] if history else None

        best_tool = None
        best_sim = 0.0

        for c in self.cases:
            if c.resolved_tool not in allowed_candidates:
                continue

            # Tool match
            t_sim = 1.0 if c.proposed_tool == proposed_tool else 0.0

            # Arg shape match
            c_keys = {k for k, _ in c.arg_shape}
            union = q_keys.union(c_keys)
            k_sim = (len(q_keys.intersection(c_keys)) / len(union)) if union else 1.0

            # Shape type match
            exact_shape_bonus = 0.3 if c.arg_shape == arg_shape else 0.0

            # Context match
            c_prev = c.history_slice[-1] if c.history_slice else None
            p_sim = 0.2 if c_prev == q_prev else 0.0

            sim = (0.5 * t_sim) + (0.3 * k_sim) + exact_shape_bonus + p_sim
            if sim > best_sim:
                best_sim = sim
                best_tool = c.resolved_tool

        return best_tool, min(1.0, best_sim)

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self.tage_tables) + sys.getsizeof(self.cases) + sys.getsizeof(self.tool_health)
        for t in self.tage_tables:
            mem += sys.getsizeof(t)
            for k, v in t.items():
                mem += sys.getsizeof(k) + sys.getsizeof(v)
        for c in self.cases:
            mem += sys.getsizeof(c)
        return mem


class AdaptiveHistoryRoutePolicy(RoutePolicy):
    """RoutePolicy integrating online case-based execution memory and TAGE branch prediction."""

    def __init__(
        self,
        memory: OnlineExecutionMemory | None = None,
        confidence_threshold: float = 0.50,
        defer_on_uncertainty: bool = False,
        use_case_memory: bool = False,
    ):
        self.memory = memory or OnlineExecutionMemory()
        self.confidence_threshold = confidence_threshold
        self.defer_on_uncertainty = defer_on_uncertainty
        self.use_case_memory = use_case_memory

    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        if not candidates:
            return Decision.deny(reason="no valid candidates after constraint filtering")

        if len(candidates) == 1:
            return Decision.select(candidates[0], reason="single valid candidate")

        allowed_tools = {c.tool for c in candidates}
        cand_by_name = {c.tool: c for c in candidates}

        proposed_tool = candidates[0].tool
        proposed_args = candidates[0].arguments
        history = list(state.previous_tools)

        # 1. Consult TAGE multi-history predictor
        tage_tool, h_len, tage_conf = self.memory.predict_tage(
            proposed_tool=proposed_tool,
            arguments=proposed_args,
            history=history,
            allowed_candidates=allowed_tools,
        )

        if tage_tool and tage_conf >= self.confidence_threshold:
            selected_action = cand_by_name[tage_tool]
            return Decision.select(
                selected_action,
                reason=f"TAGE multi-history match (H={h_len}, conf={tage_conf:.2f})",
            )

        cbr_sim = 0.0
        if self.use_case_memory:
            cbr_tool, cbr_sim = self.memory.query_case_similarity(
                proposed_tool=proposed_tool,
                arguments=proposed_args,
                history=history,
                allowed_candidates=allowed_tools,
            )
            if cbr_tool and cbr_sim >= self.confidence_threshold:
                selected_action = cand_by_name[cbr_tool]
                return Decision.select(
                    selected_action,
                    reason=f"Case-based execution memory match (sim={cbr_sim:.2f})",
                )

        if self.defer_on_uncertainty:
            return Decision.defer(
                reason=f"insufficient confidence for resolution (tage={tage_conf:.2f}, cbr={cbr_sim:.2f})"
            )

        # Default: select primary candidate safely
        return Decision.select(candidates[0], reason="deterministic default candidate selection")
