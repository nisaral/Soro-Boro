"""Soro Unified Harness Pipeline: Route -> Repair -> Guard.

A lightweight, developer-first tool harness that chains:
1. Conformal Tool Routing: Fast local candidate shortlisting and filtering.
2. Argument Repair: Auto-coerces LLM type mismatches (strings to numbers, JSON strings to dicts, camelCase to snake_case).
3. Idempotent Execution Guard: Soro-Boro boundary protecting against runaway LLM duplicate loops and retry double-writes.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

from soro_boro import SideEffectClass, TerminalOutcome, soro_wrap

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ToolEntry:
    name: str
    description: str
    fn: Callable[..., Any]
    side_effect: SideEffectClass
    parameters: dict[str, Any]
    wrapped_fn: Callable[..., TerminalOutcome[Any]]


class SoroHarness:
    """Type-safe MCP & Agent Tool Harness chaining Route -> Repair -> Guard."""

    def __init__(
        self,
        dedupe_mode: str = "loop_guard",
        window_sec: float = 120.0,
        claims_db_path: str | None = None,
        wal_path: str | None = None,
    ):
        self.dedupe_mode = dedupe_mode
        self.window_sec = window_sec
        self.claims_db_path = claims_db_path
        self.wal_path = wal_path
        self._tools: dict[str, ToolEntry] = {}

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        side_effect: str | SideEffectClass = "read_only",
        reconciler: Callable[..., Any] | None = None,
        window_sec: float | None = None,
    ) -> Callable[[F], F]:
        """Decorator to register a tool in the harness with boundary protection."""
        # Friendly side effect alias resolution
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
    # 1. ROUTE: Fast local tool routing
    # --------------------------------------------------------------------------
    def route(self, query: str, top_k: int = 3) -> list[str]:
        """Route a natural language query to the most relevant tools."""
        if not self._tools:
            return []

        query_terms = set(re.findall(r"\w+", query.lower()))
        scores: list[tuple[float, str]] = []

        for name, entry in self._tools.items():
            text = f"{name} {entry.description}".lower()
            entry_terms = set(re.findall(r"\w+", text))
            if not entry_terms:
                continue

            # Jaccard + exact substring token match score
            overlap = query_terms.intersection(entry_terms)
            score = len(overlap) / float(len(query_terms | entry_terms) or 1)

            # Name match bonus
            for q in query_terms:
                if q in name.lower():
                    score += 0.5

            scores.append((score, name))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [name for _, name in scores[:top_k]]

    # --------------------------------------------------------------------------
    # 2. REPAIR: Auto-coerce LLM argument formatting mistakes
    # --------------------------------------------------------------------------
    def repair(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Repair and validate proposed arguments against the tool's schema."""
        entry = self._tools.get(tool_name)
        if not entry:
            return dict(arguments)

        repaired: dict[str, Any] = {}
        raw = dict(arguments)

        # Normalize camelCase to snake_case matching
        raw_normalized = {}
        for k, v in raw.items():
            raw_normalized[k] = v
            # add snake_case alias if key is camelCase
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower()
            if snake != k:
                raw_normalized.setdefault(snake, v)

        for p_name, p_info in entry.parameters.items():
            target_type = p_info["type"]
            val = raw_normalized.get(p_name)

            if val is None:
                if p_info["default"] != inspect.Parameter.empty:
                    repaired[p_name] = p_info["default"]
                continue

            # Auto-repair type coercion
            try:
                if target_type in (int, "int") and isinstance(val, (str, float)):
                    repaired[p_name] = int(float(val))
                elif target_type in (float, "float") and isinstance(val, (str, int)):
                    repaired[p_name] = float(val)
                elif target_type in (bool, "bool") and isinstance(val, str):
                    repaired[p_name] = val.strip().lower() in ("true", "1", "yes")
                elif target_type in (dict, list) and isinstance(val, str):
                    # LLM passed serialized JSON string
                    try:
                        repaired[p_name] = json.loads(val)
                    except Exception:
                        repaired[p_name] = val
                elif target_type in (str, "str") and not isinstance(val, str):
                    repaired[p_name] = str(val)
                else:
                    repaired[p_name] = val
            except (ValueError, TypeError):
                repaired[p_name] = val

        # Only forward extra keys if the target function accepts **kwargs
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
    ) -> TerminalOutcome[Any]:
        """Chain Route -> Repair -> Guard in a single call."""
        target_tool = tool_name
        if not target_tool:
            ranked = self.route(query, top_k=1)
            if not ranked:
                raise ValueError(f"No suitable tool found for query: '{query}'")
            target_tool = ranked[0]

        return self.execute(target_tool, arguments=arguments)

    @property
    def tools(self) -> list[str]:
        return list(self._tools.keys())
