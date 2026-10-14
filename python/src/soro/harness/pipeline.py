"""Soro Unified Harness Pipeline: Route -> Repair -> Guard.

A lightweight, developer-first tool harness that chains:
1. Conformal Tool Routing: 2-stage pipeline (Fast shortlist -> Calibrated LocalKev scoring -> Conformal LAC filter).
2. Argument Repair: Auto-coerces LLM type mismatches and maps semantic misnomers to target schema properties.
3. Idempotent Execution Guard: Soro-Boro boundary protecting against runaway LLM duplicate loops and retry double-writes.
"""

from __future__ import annotations

import datetime
import functools
import inspect
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

from soro_boro import SideEffectClass, TerminalOutcome, soro_wrap
from soro.routing.kev_local import LocalKevScorer, _text_to_vec, _cosine

F = TypeVar("F", bound=Callable[..., Any])

COMMON_SYNONYMS: dict[str, set[str]] = {
    "id": {"identifier", "uuid", "key", "number", "code", "no"},
    "amount": {"value", "val", "total", "cost", "price", "fee", "sum", "quantity"},
    "user": {"customer", "client", "account", "member", "person", "usr"},
    "query": {"search", "q", "term", "text", "prompt", "lookup"},
    "reason": {"explanation", "memo", "description", "details", "comment", "note"},
    "target": {"destination", "dest", "to", "output", "path"},
    "source": {"origin", "src", "from", "input"},
}


@dataclass
class ToolEntry:
    name: str
    description: str
    fn: Callable[..., Any]
    side_effect: SideEffectClass
    parameters: dict[str, Any]
    wrapped_fn: Callable[..., TerminalOutcome[Any]]


@dataclass
class RouteResult:
    """Conformal routing decision output with prediction set S."""

    action: str  # "EXECUTE", "ASK", "ABSTAIN"
    selected_tool: str | None
    candidates: list[str]  # Prediction set S
    probabilities: dict[str, float] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    alpha: float = 0.10
    reason: str = ""

    def __iter__(self):
        return iter(self.candidates)

    def __getitem__(self, idx: int | slice):
        return self.candidates[idx]

    def __len__(self) -> int:
        return len(self.candidates)

    def __bool__(self) -> bool:
        return bool(self.candidates)


def _split_tokens(name: str) -> set[str]:
    clean = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return set(re.findall(r"[a-z0-9]+", clean))


def _semantic_param_similarity(input_key: str, target_param: str, target_type: Any) -> float:
    in_toks = _split_tokens(input_key)
    tar_toks = _split_tokens(target_param)
    if not in_toks or not tar_toks:
        return 0.0

    # 1. Exact match
    if input_key.lower() == target_param.lower():
        return 1.0

    # 2. Token overlap (Jaccard)
    overlap = in_toks.intersection(tar_toks)
    overlap_score = len(overlap) / float(len(in_toks | tar_toks)) if (in_toks | tar_toks) else 0.0

    # 3. Synonym matching
    has_synonym = False
    for tar in tar_toks:
        syns = COMMON_SYNONYMS.get(tar, set())
        if syns.intersection(in_toks):
            has_synonym = True
            break
    if not has_synonym:
        for in_t in in_toks:
            syns = COMMON_SYNONYMS.get(in_t, set())
            if syns.intersection(tar_toks):
                has_synonym = True
                break

    # 4. Dense cosine similarity
    vec_in = _text_to_vec(input_key)
    vec_tar = _text_to_vec(target_param)
    dense_sim = max(0.0, _cosine(vec_in, vec_tar))

    score = 0.0
    if overlap_score > 0:
        score = max(score, 0.5 + 0.5 * overlap_score)
    if has_synonym:
        score = max(score, 0.75)
    score = max(score, dense_sim)
    return score


class SoroHarness:
    """Type-safe MCP & Agent Tool Harness chaining Conformal Route -> Semantic Repair -> Soro-Boro Guard."""

    def __init__(
        self,
        dedupe_mode: str = "loop_guard",
        window_sec: float = 120.0,
        claims_db_path: str | None = None,
        wal_path: str | None = None,
        scorer: LocalKevScorer | None = None,
        default_alpha: float = 0.10,
    ):
        self.dedupe_mode = dedupe_mode
        self.window_sec = window_sec
        self.claims_db_path = claims_db_path
        self.wal_path = wal_path
        self._tools: dict[str, ToolEntry] = {}
        self._scorer = scorer or LocalKevScorer()
        self.default_alpha = default_alpha

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        side_effect: str | SideEffectClass = "read_only",
        reconciler: Callable[..., Any] | None = None,
        window_sec: float | None = None,
    ) -> Callable[[F], F]:
        """Decorator to register a tool in the harness with boundary protection."""
        if isinstance(side_effect, str):
            s_clean = side_effect.strip().lower()
            if s_clean in ("mutation", "write", "non_idempotent", "non_idempotent_mutation"):
                sec = SideEffectClass.NON_IDEMPOTENT_MUTATION
            elif s_clean in ("read", "read_only", "readonly", "lookup"):
                sec = SideEffectClass.READ_ONLY
            elif s_clean in ("idempotent", "idempotent_mutation", "upsert"):
                sec = SideEffectClass.IDEMPOTENT_MUTATION
            elif s_clean in ("destructive", "delete", "drop"):
                sec = SideEffectClass.DESTRUCTIVE
            else:
                sec = SideEffectClass(s_clean)
        else:
            sec = side_effect
        eff_window = window_sec if window_sec is not None else self.window_sec

        def decorator(fn: F) -> F:
            t_name = name or getattr(fn, "__name__", "anonymous_tool")
            t_desc = description or getattr(fn, "__doc__", "") or t_name

            # Inspect parameters from signature
            sig = inspect.signature(fn)
            params = {}
            for p_name, param in sig.parameters.items():
                if p_name in ("op", "_sb_intent_id"):
                    continue
                params[p_name] = {
                    "type": param.annotation if param.annotation != inspect.Parameter.empty else Any,
                    "default": param.default if param.default != inspect.Parameter.empty else inspect.Parameter.empty,
                }

            # Wrap with soro_boro boundary
            wrapped = soro_wrap(
                side_effect_class=sec,
                reconciler=reconciler,
                dedupe_mode=self.dedupe_mode,
                window_sec=eff_window,
                claims_db_path=self.claims_db_path,
                wal_path=self.wal_path,
            )(fn)

            entry = ToolEntry(
                name=t_name,
                description=t_desc,
                fn=fn,
                side_effect=sec,
                parameters=params,
                wrapped_fn=wrapped,
            )
            self._tools[t_name] = entry
            return fn

        return decorator

    def register(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        side_effect: str | SideEffectClass = "read_only",
        reconciler: Callable[..., Any] | None = None,
    ) -> None:
        """Register an existing function without using a decorator."""
        self.tool(
            name=name,
            description=description,
            side_effect=side_effect,
            reconciler=reconciler,
        )(fn)

    # --------------------------------------------------------------------------
    # 1. ROUTE: 2-stage Conformal Router (Dense Shortlist -> Kev Scorer -> LAC)
    # --------------------------------------------------------------------------
    def route(
        self,
        query: str,
        top_k: int = 3,
        alpha: float | None = None,
    ) -> RouteResult:
        """2-stage Conformal Router returning calibrated prediction set S and action."""
        if not self._tools:
            return RouteResult(
                action="ABSTAIN",
                selected_tool=None,
                candidates=[],
                alpha=alpha or self.default_alpha,
                reason="No tools registered",
            )

        eff_alpha = alpha if alpha is not None else self.default_alpha
        query_vec = _text_to_vec(query)
        query_terms = set(re.findall(r"\w+", query.lower()))

        # Stage 1: Fast Dense Shortlist (up to 16 candidates)
        shortlist_scores: list[tuple[float, str]] = []
        for name, entry in self._tools.items():
            text = f"{name} {entry.description}"
            tool_vec = _text_to_vec(text)
            sim = _cosine(query_vec, tool_vec)

            entry_terms = set(re.findall(r"\w+", text.lower()))
            overlap = query_terms.intersection(entry_terms)
            # If no term overlaps, dense similarity must be at least 0.28 to be considered relevant
            if not overlap and sim < 0.28:
                sim = 0.0

            # Name match bonus
            for q in query_terms:
                if q in name.lower() and len(q) >= 3:
                    sim += 0.35

            shortlist_scores.append((sim, name))

        shortlist_scores.sort(key=lambda x: x[0], reverse=True)
        max_raw_sim = shortlist_scores[0][0] if shortlist_scores else 0.0

        # Out-of-domain check: if best raw similarity is essentially zero/noise (< 0.15), abstain immediately
        if max_raw_sim < 0.15:
            return RouteResult(
                action="ABSTAIN",
                selected_tool=None,
                candidates=[],
                probabilities={},
                scores={name: s for s, name in shortlist_scores},
                alpha=eff_alpha,
                reason=f"Top candidate similarity {max_raw_sim:.3f} below minimum semantic threshold",
            )

        top_candidates = [name for _, name in shortlist_scores[:16]]

        # Stage 2: Calibrated System-One Scoring via LocalKevScorer
        options = {name: self._tools[name].description for name in top_candidates}
        probs = self._scorer.probabilities(query, options)
        scores_map = {name: s for s, name in shortlist_scores if name in probs}

        sorted_by_prob = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        if not sorted_by_prob:
            return RouteResult(
                action="ABSTAIN",
                selected_tool=None,
                candidates=[],
                probabilities=probs,
                scores=scores_map,
                alpha=eff_alpha,
                reason="No candidate probabilities available",
            )

        top_tool, top_prob = sorted_by_prob[0]
        second_prob = sorted_by_prob[1][1] if len(sorted_by_prob) > 1 else 0.0
        gap = top_prob - second_prob

        # Clear dominant winner check (e.g. margin gap >= 0.20 and prob >= 0.55)
        if top_prob >= 0.55 and gap >= 0.20:
            return RouteResult(
                action="EXECUTE",
                selected_tool=top_tool,
                candidates=[top_tool],
                probabilities=probs,
                scores=scores_map,
                alpha=eff_alpha,
                reason=f"Clear dominant top-1 candidate ({top_tool}, p={top_prob:.3f}, gap={gap:.3f})",
            )

        # Conformal Softmax-LAC Set Selection: accumulate until mass >= 1 - alpha
        target_mass = 1.0 - eff_alpha
        accumulated_set: list[str] = []
        running_mass = 0.0

        for tool_name, p in sorted_by_prob:
            accumulated_set.append(tool_name)
            running_mass += p
            if running_mass >= target_mass or len(accumulated_set) >= top_k:
                break

        # Decision Mapping
        set_size = len(accumulated_set)
        if set_size == 1:
            action = "EXECUTE"
            selected = accumulated_set[0]
            reason = f"Unambiguous singleton ({top_tool}, p={top_prob:.3f} >= {target_mass:.2f})"
        elif 2 <= set_size <= 8:
            action = "ASK"
            selected = accumulated_set[0]
            reason = f"Ambiguous prediction set size {set_size} under alpha={eff_alpha}"
        else:
            action = "ABSTAIN"
            selected = None
            reason = f"Set size {set_size} exceeds threshold"

        return RouteResult(
            action=action,
            selected_tool=selected,
            candidates=accumulated_set,
            probabilities=probs,
            scores=scores_map,
            alpha=eff_alpha,
            reason=reason,
        )

    # --------------------------------------------------------------------------
    # 2. REPAIR: Rule-Based Coercions + Semantic Key Mapping
    # --------------------------------------------------------------------------
    def repair(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Repair and validate proposed arguments against the tool's schema."""
        entry = self._tools.get(tool_name)
        if not entry:
            return dict(arguments)

        repaired: dict[str, Any] = {}
        raw = dict(arguments)

        # 1. Direct and camelCase -> snake_case matching
        raw_normalized: dict[str, Any] = {}
        matched_keys: set[str] = set()

        for k, v in raw.items():
            raw_normalized[k] = v
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower()
            if snake != k:
                raw_normalized.setdefault(snake, v)

        for p_name, p_info in entry.parameters.items():
            if p_name in raw_normalized:
                repaired[p_name] = raw_normalized[p_name]
                matched_keys.add(p_name)
                # Also mark camelCase source key as matched
                for raw_k in raw:
                    snake_k = re.sub(r"(?<!^)(?=[A-Z])", "_", raw_k).lower()
                    if snake_k == p_name or raw_k == p_name:
                        matched_keys.add(raw_k)

        # 2. Semantic Key Mapping for unrecognized arguments
        unmatched_raw = {k: v for k, v in raw.items() if k not in matched_keys}
        unpopulated_params = {p: info for p, info in entry.parameters.items() if p not in repaired}

        if unmatched_raw and unpopulated_params:
            for raw_k, raw_v in list(unmatched_raw.items()):
                best_param = None
                best_sim = 0.0

                for p_name, p_info in unpopulated_params.items():
                    sim = _semantic_param_similarity(raw_k, p_name, p_info["type"])
                    if sim > best_sim:
                        best_sim = sim
                        best_param = p_name

                # If confidence exceeds threshold, map the argument
                if best_param and best_sim >= 0.40:
                    repaired[best_param] = raw_v
                    matched_keys.add(raw_k)
                    del unpopulated_params[best_param]

        # 3. Type Coercion & Normalization on populated fields
        for p_name, p_info in entry.parameters.items():
            target_type = p_info["type"]
            val = repaired.get(p_name)

            if val is None:
                if p_info["default"] != inspect.Parameter.empty:
                    repaired[p_name] = p_info["default"]
                continue

            try:
                # Integer coercion
                if target_type in (int, "int") and isinstance(val, (str, float)) and not isinstance(val, bool):
                    repaired[p_name] = int(float(val))
                # Float coercion
                elif target_type in (float, "float") and isinstance(val, (str, int)) and not isinstance(val, bool):
                    repaired[p_name] = float(val)
                # Boolean coercion
                elif target_type in (bool, "bool") and isinstance(val, (str, int)):
                    if isinstance(val, str):
                        repaired[p_name] = val.strip().lower() in ("true", "1", "yes", "on")
                    elif isinstance(val, int):
                        repaired[p_name] = bool(val)
                # Serialized JSON string parsing
                elif target_type in (dict, list) and isinstance(val, str):
                    try:
                        repaired[p_name] = json.loads(val)
                    except Exception:
                        repaired[p_name] = val
                # ISO Date Normalization
                elif target_type in (str, "str") and isinstance(val, str):
                    clean_val = val.strip()
                    # Check YYYY/MM/DD or ISO with T
                    if "/" in clean_val or "T" in clean_val:
                        for fmt in ("%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%dT%H:%M:%SZ"):
                            try:
                                dt = datetime.datetime.strptime(clean_val.split("T")[0] if "T" in clean_val else clean_val, fmt.split("T")[0])
                                clean_val = dt.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                pass
                    repaired[p_name] = clean_val
                elif target_type in (str, "str") and not isinstance(val, str):
                    repaired[p_name] = str(val)
            except (ValueError, TypeError):
                repaired[p_name] = val

        # Forward extra keys only if target function accepts **kwargs
        sig = inspect.signature(entry.fn)
        has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_var_kwargs:
            for k, v in raw.items():
                if k not in repaired:
                    repaired[k] = v

        return repaired

    # --------------------------------------------------------------------------
    # 3. GUARD: Execute with loop guard and idempotency boundary
    # --------------------------------------------------------------------------
    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        **extra_kwargs: Any,
    ) -> TerminalOutcome[Any]:
        """Repair arguments and safely execute the tool via Soro-Boro boundary."""
        entry = self._tools.get(tool_name)
        if not entry:
            raise KeyError(f"Tool '{tool_name}' is not registered in SoroHarness.")

        raw_args = dict(arguments or {})
        raw_args.update(extra_kwargs)
        clean_args = self.repair(tool_name, raw_args)

        return entry.wrapped_fn(**clean_args)

    # --------------------------------------------------------------------------
    # FULL PIPELINE: Route -> Repair -> Guard
    # --------------------------------------------------------------------------
    def run(
        self,
        query: str,
        arguments: dict[str, Any] | None = None,
        tool_name: str | None = None,
        alpha: float | None = None,
    ) -> TerminalOutcome[Any]:
        """Chain Route -> Repair -> Guard in a single call."""
        target_tool = tool_name
        if not target_tool:
            route_res = self.route(query, top_k=1, alpha=alpha)
            if not route_res.candidates:
                raise ValueError(f"No suitable tool found for query: '{query}' ({route_res.reason})")
            target_tool = route_res.selected_tool or route_res.candidates[0]

        return self.execute(target_tool, arguments=arguments)

    @property
    def tools(self) -> list[str]:
        return list(self._tools.keys())
