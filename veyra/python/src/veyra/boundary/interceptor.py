"""Veyra Tool Boundary Interceptor.

Core abstraction:
Agent proposes -> Veyra resolves.

Sits between the agent's proposed tool call and the actual tool:
1. Intercepts proposed tool call & arguments.
2. Validates and applies provably safe normalizations.
3. Classifies failures into structured taxonomy.
4. Safely retries idempotent transient errors.
5. Returns structured diagnostic errors when Veyra cannot safely resolve.
6. Records complete audit trace.
"""

from __future__ import annotations

import functools
import time
import uuid
from typing import Any, Callable

from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.boundary.trace import TraceRecord, TraceRecorder
from veyra.boundary.validator import SchemaValidationError, validate_and_normalize


class Veyra:
    """Drop-in tool boundary reliability layer."""

    def __init__(
        self,
        recorder: TraceRecorder | None = None,
        retry_policy: SafeRetryPolicy | None = None,
    ):
        self.recorder = recorder or TraceRecorder()
        self.retry_policy = retry_policy or SafeRetryPolicy()

    def tool(
        self,
        retryable: bool = False,
        idempotent: bool = False,
        schema: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to wrap a Python function with Veyra's boundary reliability layer."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Merge positional arguments into kwargs if possible
                import inspect
                sig = inspect.signature(fn)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                proposed_args = dict(bound.arguments)

                return self.call(
                    tool_name=tool_name,
                    arguments=proposed_args,
                    fn=fn,
                    schema=schema,
                    retryable=retryable,
                    idempotent=idempotent,
                )

            # Store metadata on wrapper for introspection
            wrapper.__veyra_tool_name__ = tool_name  # type: ignore
            wrapper.__veyra_retryable__ = retryable  # type: ignore
            wrapper.__veyra_idempotent__ = idempotent  # type: ignore
            wrapper.__veyra_schema__ = schema  # type: ignore
            return wrapper

        return decorator

    def wrap(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        retryable: bool = False,
        idempotent: bool = False,
        schema: dict[str, Any] | None = None,
    ) -> Callable[..., Any]:
        """Wrap an existing function."""
        return self.tool(retryable=retryable, idempotent=idempotent, schema=schema, name=name)(fn)

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        fn: Callable[..., Any],
        schema: dict[str, Any] | None = None,
        retryable: bool = False,
        idempotent: bool = False,
        agent: str = "default_agent",
    ) -> Any:
        """Resolve and execute a proposed tool call through Veyra's boundary."""
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # Step 1: Validate and safely normalize arguments
        try:
            resolved_args, corrections = validate_and_normalize(
                proposed_args=arguments,
                schema=schema,
                fn=fn,
            )
        except SchemaValidationError as val_err:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            classification = classify_exception(val_err)
            trace = TraceRecord(
                trace_id=trace_id,
                agent=agent,
                tool_proposed=tool_name,
                arguments_proposed=arguments,
                tool_resolved=tool_name,
                arguments_resolved={},
                decision="failed_escalated",
                failure=classification.to_dict(),
                latency_ms=latency_ms,
                attempt=1,
                safe=True,
                outcome="failure",
                corrections=[],
            )
            self.recorder.record(trace)
            raise VeyraBoundaryError(classification, original_exc=val_err) from val_err

        # Step 2: Execute with safe retry
        attempt = 1
        last_classification: FailureClassification | None = None
        last_exc: Exception | None = None

        while True:
            try:
                # Call underlying function with resolved arguments
                result = fn(**resolved_args)

                # Tool succeeded
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                decision = (
                    "retried_and_succeeded"
                    if attempt > 1
                    else ("corrected_and_executed" if corrections else "direct_execution")
                )
                trace = TraceRecord(
                    trace_id=trace_id,
                    agent=agent,
                    tool_proposed=tool_name,
                    arguments_proposed=arguments,
                    tool_resolved=tool_name,
                    arguments_resolved=resolved_args,
                    decision=decision,
                    failure=None,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    safe=True,
                    outcome="success",
                    corrections=corrections,
                )
                self.recorder.record(trace)
                return result

            except Exception as exc:
                last_exc = exc
                classification = classify_exception(
                    exc,
                    is_idempotent=idempotent,
                    is_declared_retryable=retryable,
                )
                last_classification = classification

                # Check if safe to retry
                if self.retry_policy.is_safe_to_retry(
                    classification=classification,
                    is_idempotent=idempotent,
                    is_declared_retryable=retryable,
                    current_attempt=attempt,
                ):
                    delay = self.retry_policy.calculate_delay(classification, attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Not safe to retry or attempts exhausted -> Escalate structured error
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                trace = TraceRecord(
                    trace_id=trace_id,
                    agent=agent,
                    tool_proposed=tool_name,
                    arguments_proposed=arguments,
                    tool_resolved=tool_name,
                    arguments_resolved=resolved_args,
                    decision="failed_escalated",
                    failure=classification.to_dict(),
                    latency_ms=latency_ms,
                    attempt=attempt,
                    safe=True,
                    outcome="failure",
                    corrections=corrections,
                )
                self.recorder.record(trace)
                raise VeyraBoundaryError(classification, original_exc=exc) from exc
