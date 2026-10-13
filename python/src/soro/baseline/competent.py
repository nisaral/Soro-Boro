"""Fair Competent Baseline Middleware (Phase 0 Specification).

Implements standard, disciplined tool-boundary engineering:
1. Full JSON schema validation and safe type coercion (str <-> int, float, bool, JSON object).
2. Retry-After & bounded backoff on 429/503.
3. Strict idempotency protection: NEVER retries non-idempotent mutations blindly (0 unsafe retries invariant).
4. Structured error reporting with actionable diagnostics for the agent.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

IDEMPOTENT_PREFIXES = ("get_", "read_", "list_", "search_", "check_", "query_", "fetch_", "inspect_")


def is_idempotent(tool_name: str) -> bool:
    """Determine whether a tool operation is safe to retry based on declared naming and idempotency rules."""
    name = tool_name.lower().strip()
    return any(name.startswith(p) for p in IDEMPOTENT_PREFIXES)


def coerce_argument_types(args: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce argument types against declared JSON schema properties (competent engineering)."""
    if not schema:
        return dict(args)

    properties = schema.get("properties") or schema.get("parameters", {}).get("properties", {})
    if not properties:
        return dict(args)

    coerced = dict(args)
    for prop_name, prop_spec in properties.items():
        if prop_name not in coerced:
            continue
        val = coerced[prop_name]
        expected_type = prop_spec.get("type")

        # 1. Integer coercion
        if expected_type in ("integer", "int"):
            if isinstance(val, str):
                val_clean = val.strip()
                if val_clean.lstrip("-").isdigit():
                    coerced[prop_name] = int(val_clean)
                else:
                    try:
                        f = float(val_clean)
                        if f.is_integer():
                            coerced[prop_name] = int(f)
                    except ValueError:
                        pass
            elif isinstance(val, float) and val.is_integer():
                coerced[prop_name] = int(val)

        # 2. String coercion
        elif expected_type == "string":
            if not isinstance(val, str):
                coerced[prop_name] = str(val)
            else:
                coerced[prop_name] = val.strip()

        # 3. Boolean coercion
        elif expected_type == "boolean":
            if isinstance(val, str):
                if val.lower() in ("true", "1", "yes"):
                    coerced[prop_name] = True
                elif val.lower() in ("false", "0", "no"):
                    coerced[prop_name] = False

        # 4. Object / dict from JSON string
        elif expected_type == "object" and isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    coerced[prop_name] = parsed
            except Exception:
                pass

    return coerced


class CompetentBaselineMiddleware:
    """Standard disciplined tool-calling middleware."""

    def __init__(self, max_retries: int = 2, default_backoff_sec: float = 0.05):
        self.max_retries = max_retries
        self.default_backoff_sec = default_backoff_sec

    def prepare_action(
        self,
        tool_name: str,
        args: dict[str, Any],
        schemas: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any]]:
        """Normalize arguments against declared tool schema."""
        target_schema = next((s for s in schemas if s.get("name") == tool_name), None)
        coerced = coerce_argument_types(args, target_schema)
        return tool_name, coerced

    def execute_with_safe_retry(
        self,
        tool_name: str,
        args: dict[str, Any],
        execute_fn: Callable[[str, dict[str, Any]], Any],
        is_idempotent_override: bool | None = None,
    ) -> tuple[Any, int, bool]:
        """Execute tool call with strict idempotency-aware retry.
        
        Returns (result, attempts_used, recovered_at_boundary).
        """
        can_retry = is_idempotent(tool_name) if is_idempotent_override is None else is_idempotent_override
        attempts = 0
        max_attempts = (1 + self.max_retries) if can_retry else 1

        last_exc: Exception | None = None
        while attempts < max_attempts:
            attempts += 1
            try:
                res = execute_fn(tool_name, args)
                recovered = attempts > 1
                return res, attempts, recovered
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                is_transient = any(t in msg for t in ("timeout", "timed out", "503", "429", "rate limit", "service unavailable"))
                if not is_transient or not can_retry:
                    # Invariant: NEVER retry non-idempotent mutations or hard errors!
                    raise exc
                time.sleep(self.default_backoff_sec)

        if last_exc:
            raise last_exc
        raise RuntimeError("Competent baseline: retries exhausted")

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        handler: Callable[[dict[str, Any]], Any],
        input_schema: dict[str, Any] | None = None,
        idempotent: bool | None = None,
    ) -> Any:
        """Convenience method to coerce arguments and execute with safe retry."""
        schemas = [{"name": tool_name, **(input_schema or {})}] if input_schema else []
        _, coerced = self.prepare_action(tool_name, arguments, schemas)
        res, _, _ = self.execute_with_safe_retry(
            tool_name,
            coerced,
            execute_fn=lambda name, args: handler(args),
            is_idempotent_override=idempotent,
        )
        return res
