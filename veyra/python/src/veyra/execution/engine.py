"""Veyra Execution Engine.

Implements the Section 4 Core Runtime Pipeline:
Agent Proposed Action
  -> Candidate Resolution
  -> Hard Constraints
  -> RoutePolicy
  -> Resolved Action (validate & normalize)
  -> Execution
  -> Outcome Classification
  -> RecoveryPolicy (if failure)
  -> Trace
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.boundary.validator import SchemaValidationError, validate_and_normalize
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind, RecoveryDecisionKind
from veyra.core.state import ExecutionState
from veyra.core.trace import ExecutionTrace, TraceSink
from veyra.policy.base import RoutePolicy
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.recovery import RecoveryPolicy, SafeRecoveryPolicy
from veyra.registry.resolver import CandidateResolver, DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolRegistry


class ExecutionEngine:
    """Core runtime engine mediating between agent tool proposals and tool execution."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        resolver: CandidateResolver | None = None,
        route_policy: RoutePolicy | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        trace_sink: TraceSink | None = None,
    ):
        self.registry = registry or ToolRegistry()
        self.resolver = resolver or DeterministicCandidateResolver(self.registry)
        self.route_policy = route_policy or DeterministicRoutePolicy()
        self.recovery_policy = recovery_policy or SafeRecoveryPolicy()
        self.trace_sink = trace_sink or TraceSink()

    def execute(
        self,
        proposal: ExecutableAction,
        state: ExecutionState | None = None,
    ) -> Any:
        """Execute a proposed action through the complete Veyra runtime pipeline."""
        state = state or ExecutionState(agent="default_agent")
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # Step 1: Candidate Resolution + Hard Constraints
        candidates = self.resolver.resolve(proposal, state)
        candidate_names = [c.tool for c in candidates]

        # Step 2: RoutePolicy Resolution
        route_decision = self.route_policy.resolve(state, candidates)

        if route_decision.kind == DecisionKind.DENY:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            clf = FailureClassification(
                kind=FailureKind.AUTHORIZATION_ERROR,
                retryable=False,
                repairable=False,
                requires_agent=True,
                safe_to_retry=False,
                message=route_decision.reason or "Denied by policy constraints",
                status_code=403,
            )
            trace = ExecutionTrace(
                trace_id=trace_id,
                agent=state.agent,
                proposal=proposal.to_dict(),
                candidates=candidate_names,
                filtered_candidates=candidate_names,
                resolved_tool=proposal.tool,
                policy=type(self.route_policy).__name__,
                decision="deny",
                failure=clf.to_dict(),
                latency_ms=latency_ms,
                attempt=1,
                safe=True,
                outcome="failure",
                risk_class=proposal.risk_class,
                is_idempotent=proposal.is_idempotent,
                is_retryable=proposal.is_retryable,
                state_signature=state.compute_signature(),
                previous_tools=state.previous_tools,
            )
            self.trace_sink.record(trace)
            raise VeyraBoundaryError(clf)

        if route_decision.kind == DecisionKind.DEFER or route_decision.action is None:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            clf = FailureClassification(
                kind=FailureKind.UNKNOWN,
                retryable=False,
                repairable=False,
                requires_agent=True,
                safe_to_retry=False,
                message=route_decision.reason or "Route policy deferred action to agent",
            )
            trace = ExecutionTrace(
                trace_id=trace_id,
                agent=state.agent,
                proposal=proposal.to_dict(),
                candidates=candidate_names,
                filtered_candidates=candidate_names,
                resolved_tool=proposal.tool,
                policy=type(self.route_policy).__name__,
                decision="defer",
                failure=clf.to_dict(),
                latency_ms=latency_ms,
                attempt=1,
                safe=True,
                outcome="failure",
                state_signature=state.compute_signature(),
                previous_tools=state.previous_tools,
            )
            self.trace_sink.record(trace)
            raise VeyraBoundaryError(clf)

        resolved_action = route_decision.action

        # Step 3: Validate and safely normalize arguments
        schema = resolved_action.metadata.get("schema")
        fn = resolved_action.executable

        try:
            resolved_args, corrections = validate_and_normalize(
                proposed_args=resolved_action.arguments,
                schema=schema,
                fn=fn,
            )
        except SchemaValidationError as s_err:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            clf = classify_exception(s_err)
            trace = ExecutionTrace(
                trace_id=trace_id,
                agent=state.agent,
                proposal=proposal.to_dict(),
                candidates=candidate_names,
                filtered_candidates=candidate_names,
                resolved_tool=resolved_action.tool,
                resolved_arguments={},
                policy=type(self.route_policy).__name__,
                decision="failed_escalated",
                failure=clf.to_dict(),
                latency_ms=latency_ms,
                attempt=1,
                safe=True,
                outcome="failure",
                corrections=[],
                risk_class=resolved_action.risk_class,
                is_idempotent=resolved_action.is_idempotent,
                is_retryable=resolved_action.is_retryable,
                equivalence_group=resolved_action.equivalence_group,
                state_signature=state.compute_signature(),
                previous_tools=state.previous_tools,
            )
            self.trace_sink.record(trace)
            raise VeyraBoundaryError(clf, original_exc=s_err) from s_err

        # Step 4: Execution Loop with Safe Recovery
        attempt = 1
        executable = resolved_action.executable

        while True:
            try:
                if executable is None:
                    raise RuntimeError(f"Tool '{resolved_action.tool}' has no executable function configured")

                result = executable(**resolved_args)

                # Tool succeeded
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                decision_label = (
                    "retried_and_succeeded"
                    if attempt > 1
                    else ("corrected_and_executed" if corrections else "direct_execution")
                )
                trace = ExecutionTrace(
                    trace_id=trace_id,
                    agent=state.agent,
                    proposal=proposal.to_dict(),
                    candidates=candidate_names,
                    filtered_candidates=candidate_names,
                    resolved_tool=resolved_action.tool,
                    resolved_arguments=resolved_args,
                    policy=type(self.route_policy).__name__,
                    decision=decision_label,
                    failure=None,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    safe=True,
                    outcome="success",
                    corrections=corrections,
                    risk_class=resolved_action.risk_class,
                    is_idempotent=resolved_action.is_idempotent,
                    is_retryable=resolved_action.is_retryable,
                    equivalence_group=resolved_action.equivalence_group,
                    state_signature=state.compute_signature(),
                    previous_tools=state.previous_tools,
                )
                self.trace_sink.record(trace)
                return result

            except Exception as exc:
                classification = classify_exception(
                    exc,
                    is_idempotent=resolved_action.is_idempotent,
                    is_declared_retryable=resolved_action.is_retryable,
                )

                # Step 5: Consult RecoveryPolicy
                recovery_dec = self.recovery_policy.recover(
                    failed_action=resolved_action,
                    failure=classification,
                    state=state,
                    attempt=attempt,
                )

                if recovery_dec.kind == RecoveryDecisionKind.RETRY:
                    if recovery_dec.delay_sec > 0:
                        time.sleep(recovery_dec.delay_sec)
                    attempt += 1
                    continue

                # Unrecoverable -> strictly escalate structured error
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                trace = ExecutionTrace(
                    trace_id=trace_id,
                    agent=state.agent,
                    proposal=proposal.to_dict(),
                    candidates=candidate_names,
                    filtered_candidates=candidate_names,
                    resolved_tool=resolved_action.tool,
                    resolved_arguments=resolved_args,
                    policy=type(self.route_policy).__name__,
                    decision="failed_escalated",
                    failure=classification.to_dict(),
                    recovery=recovery_dec.to_dict(),
                    latency_ms=latency_ms,
                    attempt=attempt,
                    safe=True,
                    outcome="failure",
                    corrections=corrections,
                    risk_class=resolved_action.risk_class,
                    is_idempotent=resolved_action.is_idempotent,
                    is_retryable=resolved_action.is_retryable,
                    equivalence_group=resolved_action.equivalence_group,
                    state_signature=state.compute_signature(),
                    previous_tools=state.previous_tools,
                )
                self.trace_sink.record(trace)
                raise VeyraBoundaryError(classification, original_exc=exc) from exc
