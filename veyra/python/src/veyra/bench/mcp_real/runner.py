"""Real MCP Catalogs Comparative Evaluation Runner.

Implements Milestone V0.1 -> V0.2:
Tests existing MCP tools across 3 real catalogs (Filesystem, Database, API)
under 4 comparative execution arms:
A. raw_agent: Direct MCP invocation, no middleware.
B. naive_retry: Blindly retries any failure up to 3 times (recording unsafe retries on non-idempotent calls).
C. structured_feedback: Emits structured error text; agent must re-plan.
D. veyra: Transparent MCP boundary interceptor resolving safe normalizations
   and safe idempotent retries, while blocking unsafe retries and emitting traces.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from veyra.bench.mcp_real.catalogs import MCPToolDescriptor, RealMCPCatalogManager
from veyra.bench.mcp_real.scenarios import RealMCPTask, get_real_mcp_scenarios
from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureClassification, FailureKind, VeyraBoundaryError, classify_exception


class RealMCPArm(str, Enum):
    RAW_AGENT = "raw_agent"
    NAIVE_RETRY = "naive_retry"
    STRUCTURED_FEEDBACK = "structured_feedback"
    VEYRA = "veyra"


@dataclass
class RealMCPResult:
    """Metrics recorded for a single system arm on the real MCP benchmark."""

    arm: RealMCPArm
    tasks_count: int = 0
    task_success_count: int = 0
    schema_failures: int = 0
    precondition_failures: int = 0
    timeout_failures: int = 0
    rate_limit_failures: int = 0
    authorization_failures: int = 0
    harmful_interventions: int = 0
    unsafe_retries: int = 0
    total_tool_calls: int = 0
    retry_count: int = 0
    agent_replans: int = 0
    latency_ms_total: float = 0.0
    boundary_recoveries: int = 0
    eligible_failures_denominator: int = 0
    non_recoverable_failures: int = 0

    @property
    def eligible_injected_failures(self) -> int:
        return self.eligible_failures_denominator

    @property
    def successful_safe_recoveries(self) -> int:
        return self.boundary_recoveries

    @property
    def unsafe_interventions(self) -> int:
        return self.unsafe_retries + self.harmful_interventions

    @property
    def task_success_rate(self) -> float:
        return (self.task_success_count / max(1, self.tasks_count)) * 100.0

    @property
    def boundary_recovery_rate(self) -> float:
        return (self.boundary_recoveries / max(1, self.eligible_failures_denominator)) * 100.0

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_ms_total / max(1, self.tasks_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "tasks_count": self.tasks_count,
            "task_success_count": self.task_success_count,
            "task_success_rate": f"{self.task_success_rate:.1f}%",
            "schema_failures": self.schema_failures,
            "precondition_failures": self.precondition_failures,
            "timeout_failures": self.timeout_failures,
            "rate_limit_failures": self.rate_limit_failures,
            "authorization_failures": self.authorization_failures,
            "harmful_interventions": self.harmful_interventions,
            "unsafe_retries": self.unsafe_retries,
            "total_tool_calls": self.total_tool_calls,
            "retry_count": self.retry_count,
            "agent_replans": self.agent_replans,
            "eligible_injected_failures": self.eligible_injected_failures,
            "successful_safe_recoveries": self.successful_safe_recoveries,
            "unsafe_interventions": self.unsafe_interventions,
            "non_recoverable_failures": self.non_recoverable_failures,
            "boundary_recovery_rate": f"{self.boundary_recovery_rate:.1f}%",
            "avg_latency_ms": f"{self.avg_latency_ms:.2f}ms",
        }


def run_real_mcp_benchmark(
    scenarios: list[RealMCPTask] | None = None,
    catalog_mgr: RealMCPCatalogManager | None = None,
) -> dict[str, RealMCPResult]:
    """Run comparative evaluation across the 4 system arms on real MCP environments."""
    tasks = scenarios or get_real_mcp_scenarios()
    mgr = catalog_mgr or RealMCPCatalogManager()
    results: dict[str, RealMCPResult] = {}

    for arm in (RealMCPArm.RAW_AGENT, RealMCPArm.NAIVE_RETRY, RealMCPArm.STRUCTURED_FEEDBACK, RealMCPArm.VEYRA):
        res = RealMCPResult(arm=arm, tasks_count=len(tasks))

        # Count eligible and non-recoverable failures from scenario ground-truth
        for t in tasks:
            is_fault = (
                t.eligible_for_boundary_recovery
                or t.injected_transient
                or t.injected_rate_limit
                or t.injected_network_timeout
                or t.expected_failure_kind is not None
            )
            if is_fault:
                if t.eligible_for_boundary_recovery:
                    res.eligible_failures_denominator += 1
                else:
                    res.non_recoverable_failures += 1

        for task in tasks:
            descriptor = mgr.get_tool(task.tool_name)
            if descriptor is None:
                raise KeyError(f"Tool {task.tool_name} not found in real catalog manager")

            t0 = time.perf_counter()
            _execute_arm_task(arm, task, descriptor, res)
            res.latency_ms_total += (time.perf_counter() - t0) * 1000.0

        results[arm.value] = res

    return results


def _execute_arm_task(
    arm: RealMCPArm,
    task: RealMCPTask,
    descriptor: MCPToolDescriptor,
    stats: RealMCPResult,
) -> None:
    """Execute a single benchmark task under the designated system arm."""
    call_attempt = 0

    def raw_mcp_call(**kwargs):
        nonlocal call_attempt
        call_attempt += 1
        stats.total_tool_calls += 1

        # Check injected transient 503
        if task.injected_transient:
            if call_attempt == 1:
                stats.timeout_failures += 1
                raise TimeoutError("503 Service Unavailable upstream: weather gateway timeout")

        # Check injected rate limit 429
        if task.injected_rate_limit:
            if call_attempt == 1:
                stats.rate_limit_failures += 1
                raise RuntimeError("HTTP 429 Too Many Requests: Rate limit exceeded, retry-after: 0.001")

        # Check non-idempotent write timeout
        if task.injected_network_timeout:
            stats.timeout_failures += 1
            raise TimeoutError("Network timeout during file write: operation state unknown")

        # Invoke actual FastMCP tool function
        res = descriptor.handler(**kwargs)

        # Inspect if tool returned an error string
        if isinstance(res, str) and res.startswith("Error:"):
            raise ValueError(res)

        return res

    # -------------------------------------------------------------
    # System A: RAW AGENT (no middleware)
    # -------------------------------------------------------------
    if arm == RealMCPArm.RAW_AGENT:
        try:
            raw_mcp_call(**task.arguments)
            stats.task_success_count += 1
        except Exception as exc:
            stats.agent_replans += 1
            clf = classify_exception(exc)
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1

    # -------------------------------------------------------------
    # System B: NAIVE RETRY (blindly retries everything 3 times)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.NAIVE_RETRY:
        attempts = 0
        success = False
        while attempts < 3:
            attempts += 1
            if attempts > 1:
                stats.retry_count += 1
            try:
                raw_mcp_call(**task.arguments)
                success = True
                break
            except Exception as exc:
                # If non-idempotent operation is retried blindly, record CRITICAL unsafe retry!
                if not task.is_idempotent and attempts > 1:
                    stats.unsafe_retries += 1
                    stats.harmful_interventions += 1
                clf = classify_exception(exc)
                if clf.kind == FailureKind.SCHEMA_ERROR:
                    stats.schema_failures += 1
                elif clf.kind == FailureKind.PRECONDITION_ERROR:
                    stats.precondition_failures += 1

        if success:
            stats.task_success_count += 1
        else:
            stats.agent_replans += 1

    # -------------------------------------------------------------
    # System C: STRUCTURED FEEDBACK (diagnostic error, agent re-plans)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.STRUCTURED_FEEDBACK:
        try:
            raw_mcp_call(**task.arguments)
            stats.task_success_count += 1
        except Exception as exc:
            stats.agent_replans += 1
            clf = classify_exception(exc)
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1

    # -------------------------------------------------------------
    # System D: VEYRA (transparent boundary resolver & safe retry)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.VEYRA:
        veyra = Veyra(
            retry_policy=SafeRetryPolicy(
                max_attempts=3,
                base_backoff_sec=0.001,
                max_backoff_sec=0.005,
                jitter=False,
            )
        )

        wrapped = veyra.wrap(
            raw_mcp_call,
            name=descriptor.name,
            retryable=descriptor.is_retryable,
            idempotent=descriptor.is_idempotent,
            schema=descriptor.input_schema,
        )

        try:
            wrapped(**task.arguments)
            stats.task_success_count += 1

            if task.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1

        except VeyraBoundaryError as vbe:
            # Unrecoverable error safely escalated to agent with structured classification
            stats.agent_replans += 1
            clf = vbe.classification
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1
