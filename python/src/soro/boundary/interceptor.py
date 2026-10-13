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

from soro.boundary.retry import SafeRetryPolicy
from soro.boundary.trace import TraceRecorder
from soro.core.action import ExecutableAction
from soro.core.state import ExecutionState
from soro.core.trace import TraceSink
from soro.execution.engine import ExecutionEngine
from soro.policy.base import RoutePolicy
from soro.policy.deterministic import DeterministicRoutePolicy
from soro.policy.recovery import SafeRecoveryPolicy
from soro.registry.resolver import DeterministicCandidateResolver
from soro.registry.tool_registry import ToolDefinition, ToolRegistry


class Veyra:
    """Drop-in tool boundary reliability layer."""

    def __init__(
        self,
        policy: Any | None = None,
        mode: str = "fail_closed",
        recorder: TraceRecorder | TraceSink | None = None,
        retry_policy: SafeRetryPolicy | None = None,
        route_policy: RoutePolicy | None = None,
        registry: ToolRegistry | None = None,
        recovery_policy: str | Any | None = None,
    ):
        self.mode = mode
        self.registry = registry or ToolRegistry()
        self.retry_policy = retry_policy or SafeRetryPolicy()
        if route_policy is not None:
            self.route_policy = route_policy
        elif policy is not None and not isinstance(policy, str):
            self.route_policy = policy
        else:
            self.route_policy = DeterministicRoutePolicy()

        self.resolver = DeterministicCandidateResolver(self.registry)
        
        # Directive §18: Default remains deterministic; belief_state_experimental is opt-in
        self.recovery_policy_mode = recovery_policy or "deterministic"
        if isinstance(recovery_policy, str) and recovery_policy == "belief_state_experimental":
            from soro.core.recovery_controller import ConstrainedBeliefStateRecoveryController
            self.belief_recovery_controller = ConstrainedBeliefStateRecoveryController()
        else:
            self.belief_recovery_controller = None

        if hasattr(recovery_policy, "recover"):
            self.recovery_policy = recovery_policy
        else:
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
            soro.equivalent("get_customer", ["crm.get_customer", "legacy.get_customer"])
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
        fn: Callable[..., Any] | None = None,
        schema: dict[str, Any] | None = None,
        retryable: bool = False,
        idempotent: bool = False,
        agent: str = "default_agent",
        state: ExecutionState | None = None,
    ) -> Any:
        """Resolve and execute a proposed tool call through Veyra's execution engine."""
        executable_fn = fn
        if executable_fn is None:
            tool_def = self.registry.get(tool_name)
            if tool_def is not None and tool_def.executable is not None:
                executable_fn = tool_def.executable
                if schema is None:
                    schema = tool_def.schema
                retryable = retryable or tool_def.retryable
                idempotent = idempotent or tool_def.idempotent

        action = ExecutableAction(
            tool=tool_name,
            arguments=dict(arguments),
            metadata={
                "retryable": retryable,
                "idempotent": idempotent,
                "schema": schema,
            },
            executable=executable_fn,
        )

        exec_state = state or ExecutionState(agent=agent)
        return self.engine.execute(proposal=action, state=exec_state)

    def execute(
        self,
        proposal: ExecutableAction,
        state: ExecutionState | None = None,
    ) -> Any:
        """Directly execute a proposal through soro."""
        exec_state = state or ExecutionState()
        return self.engine.execute(proposal=proposal, state=exec_state)

    def wrap_mcp(self, mcp_client: Any) -> Any:
        """Wrap an MCP client with Veyra policy and execution control."""
        from soro.middleware.mcp import MCPWrapper
        return MCPWrapper(self, mcp_client)

    def wrap_http(self, http_client: Any) -> Any:
        """Wrap an HTTP client with Veyra policy and execution control."""
        from soro.middleware.http import HTTPWrapper
        return HTTPWrapper(self, http_client)

    def wrap_agent(self, agent: Any) -> Any:
        """Wrap an AI agent instance with Veyra policy and execution control."""
        from soro.middleware.agent import AgentWrapper
        return AgentWrapper(self, agent)
