"""Veyra Tool Boundary Interceptor.

Core abstraction:
Agent proposes -> Veyra resolves -> Tool executes.

Sits between the agent's proposed tool call and the actual tool:
1. Validates proposed ExecutableAction & arguments.
2. Resolves candidates and applies hard constraints & RoutePolicy.
3. Classifies failures into structured taxonomy.
4. Safely retries idempotent transient errors via RecoveryPolicy.
5. Returns structured diagnostic errors when Veyra cannot safely resolve.
6. Records complete audit trace.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.trace import TraceRecorder
from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.core.trace import TraceSink
from veyra.execution.engine import ExecutionEngine
from veyra.policy.base import RoutePolicy
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.recovery import SafeRecoveryPolicy
from veyra.registry.resolver import DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


class Veyra:
    """Drop-in tool boundary reliability layer."""

    def __init__(
        self,
        recorder: TraceRecorder | TraceSink | None = None,
        retry_policy: SafeRetryPolicy | None = None,
        route_policy: RoutePolicy | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.registry = registry or ToolRegistry()
        self.retry_policy = retry_policy or SafeRetryPolicy()
        self.route_policy = route_policy or DeterministicRoutePolicy()
        self.resolver = DeterministicCandidateResolver(self.registry)
        self.recovery_policy = SafeRecoveryPolicy(self.retry_policy)

        # Support both TraceRecorder and TraceSink
        if isinstance(recorder, TraceRecorder):
            self.trace_sink = TraceSink(listener=recorder)
            self._compat_recorder = recorder
        elif isinstance(recorder, TraceSink):
            self.trace_sink = recorder
            self._compat_recorder = None
        else:
            self.trace_sink = TraceSink()
            self._compat_recorder = None

        self.engine = ExecutionEngine(
            registry=self.registry,
            resolver=self.resolver,
            route_policy=self.route_policy,
            recovery_policy=self.recovery_policy,
            trace_sink=self.trace_sink,
        )

    @property
    def recorder(self) -> Any:
        """Compatibility property for access to trace records."""
        if self._compat_recorder is not None:
            # Sync traces from engine trace sink
            self._compat_recorder.traces = list(self.trace_sink.traces)  # type: ignore
            return self._compat_recorder
        return self.trace_sink

    def equivalent(self, canonical_name: str, equivalent_names: list[str]) -> None:
        """Explicitly declare equivalent tools (Section 7).

        Example:
            veyra.equivalent("get_customer", ["crm.get_customer", "legacy.get_customer"])
        """
        self.registry.register_equivalence(canonical_name, equivalent_names)

    def tool(
        self,
        retryable: bool = False,
        idempotent: bool = False,
        schema: dict[str, Any] | None = None,
        name: str | None = None,
        risk_class: str = "low",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to wrap a Python function with Veyra's boundary reliability layer."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__

            # Register in registry
            self.registry.register(
                ToolDefinition(
                    name=tool_name,
                    schema=schema,
                    executable=fn,
                    retryable=retryable,
                    idempotent=idempotent,
                    risk_class=risk_class,
                    capabilities=capabilities or [],
                    permissions=permissions or [],
                    protocol="python",
                )
            )

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                sig = inspect.signature(fn)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                proposed_args = dict(bound.arguments)
                for p_name, p in sig.parameters.items():
                    if p.kind == inspect.Parameter.VAR_KEYWORD and p_name in proposed_args:
                        var_kwargs = proposed_args.pop(p_name)
                        if isinstance(var_kwargs, dict):
                            proposed_args.update(var_kwargs)

                return self.call(
                    tool_name=tool_name,
                    arguments=proposed_args,
                    fn=fn,
                    schema=schema,
                    retryable=retryable,
                    idempotent=idempotent,
                )

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
        state: ExecutionState | None = None,
    ) -> Any:
        """Resolve and execute a proposed tool call through Veyra's execution engine."""
        action = ExecutableAction(
            tool=tool_name,
            arguments=dict(arguments),
            metadata={
                "retryable": retryable,
                "idempotent": idempotent,
                "schema": schema,
            },
            executable=fn,
        )

        exec_state = state or ExecutionState(agent=agent)
        return self.engine.execute(proposal=action, state=exec_state)
