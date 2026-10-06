"""Comparative Evaluation Harness for Real FastMCP Servers.

Implements Milestone v0.2:
Evaluates 5 system arms on real FastMCP server implementations from MCPAgentBench:
1. RAW_AGENT: Directly invokes the MCP tool handler without interceptor.
2. NAIVE_RETRY: Blindly retries any tool error up to 3 times (risks unsafe mutations).
3. COMPETENT_BASELINE: Standard production engineering boundary (safe coercion, safe idempotent retries, 0 unsafe retries).
4. STRUCTURED_FEEDBACK: Returns classified error diagnostic, forcing an agent re-plan.
5. VEYRA: Applies transparent boundary normalization, safe retries, and failure provenance tracking.

Metrics computed:
- Task Success Rate (with 95% Wilson CI)
- Boundary Recovery Rate (with 95% Wilson CI)
- Unsafe Retries / Harmful Interventions
- Agent Re-plans (explicit measured ReplanEvent objects)
- Trace Audits & Latency
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from veyra.bench.mcp_real.catalogs import MCPToolDescriptor, RealMCPCatalogManager
from veyra.bench.mcp_real.scenarios import RealMCPTask, get_real_mcp_scenarios
from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.core.trace import ReplanEvent


BENCHMARK_SPEC = {
    "benchmark": "MCPAgentBench-real-servers",
    "paper": "arXiv:2508.14704",
    "pinned_commit": "e89bf24",
    "server_count": 141,
    "controlled_test_tasks": 40,
    "spec_version": "v0.1.0-pinned",
}


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Compute 95% Wilson score confidence interval for binomial proportion."""
    if n <= 0:
        return 0.0, 0.0
    z = 1.95996  # 95% confidence
    p = k / n
    denom = 1 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    half_width = (z * ((p * (1 - p) / n + (z**2) / (4 * n**2)) ** 0.5)) / denom
    lower = max(0.0, (center - half_width) * 100.0)
    upper = min(100.0, (center + half_width) * 100.0)
    return round(lower, 1), round(upper, 1)


class RealMCPArm(str, Enum):
    RAW_AGENT = "raw_agent"
    NAIVE_RETRY = "naive_retry"
    COMPETENT_BASELINE = "competent_baseline"
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
    replan_events: list[ReplanEvent] = field(default_factory=list)
    scenario_traces: list[dict[str, Any]] = field(default_factory=list)
    latency_ms_total: float = 0.0
    boundary_recoveries: int = 0
    eligible_failures_denominator: int = 0
    non_recoverable_failures: int = 0

    @property
    def agent_replans(self) -> int:
        return len(self.replan_events)

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
    def task_success_ci_95(self) -> tuple[float, float]:
        return compute_wilson_ci(self.task_success_count, self.tasks_count)

    @property
    def boundary_recovery_rate(self) -> float:
        return (self.boundary_recoveries / max(1, self.eligible_failures_denominator)) * 100.0

    @property
    def boundary_recovery_ci_95(self) -> tuple[float, float]:
        return compute_wilson_ci(self.boundary_recoveries, self.eligible_failures_denominator)

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_ms_total / max(1, self.tasks_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "tasks_count": self.tasks_count,
            "task_success_count": self.task_success_count,
            "task_success_rate": f"{self.task_success_rate:.1f}%",
            "task_success_ci_95": self.task_success_ci_95,
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
            "boundary_recovery_ci_95": self.boundary_recovery_ci_95,
            "avg_latency_ms": f"{self.avg_latency_ms:.2f}ms",
        }


def run_real_mcp_benchmark(
    scenarios: list[RealMCPTask] | None = None,
    catalog_mgr: RealMCPCatalogManager | None = None,
    traces_dir: Path | str | None = None,
) -> dict[str, RealMCPResult]:
    """Run comparative evaluation across the 5 system arms on real MCP environments."""
    tasks = scenarios or get_real_mcp_scenarios()
    mgr = catalog_mgr or RealMCPCatalogManager()
    results: dict[str, RealMCPResult] = {}

    for arm in (
        RealMCPArm.RAW_AGENT,
        RealMCPArm.NAIVE_RETRY,
        RealMCPArm.COMPETENT_BASELINE,
        RealMCPArm.STRUCTURED_FEEDBACK,
        RealMCPArm.VEYRA,
    ):
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

        if traces_dir:
            out_p = Path(traces_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            trace_file = out_p / f"mcp_real_{arm.value}_traces.jsonl"
            with open(trace_file, "w", encoding="utf-8") as f:
                for trace in res.scenario_traces:
                    f.write(json.dumps(trace) + "\n")

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
    start_time = time.perf_counter()
    success = False
    boundary_recovered = False
    task_replans: list[ReplanEvent] = []
    unsafe_interventions_count = 0

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
            success = True
        except Exception as exc:
            clf = classify_exception(exc)
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1

            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="RAW_MCP_EXCEPTION",
                provenance=clf.provenance.value,
                failure_kind=clf.kind.value,
                error_message=str(exc),
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)

    # -------------------------------------------------------------
    # System B: NAIVE RETRY (blindly retries everything 3 times)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.NAIVE_RETRY:
        attempts = 0
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
                    unsafe_interventions_count += 1
                clf = classify_exception(exc)
                if clf.kind == FailureKind.SCHEMA_ERROR:
                    stats.schema_failures += 1
                elif clf.kind == FailureKind.PRECONDITION_ERROR:
                    stats.precondition_failures += 1

        if success:
            stats.task_success_count += 1
        else:
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="NAIVE_RETRIES_EXHAUSTED",
                provenance=FailureProvenance.UNKNOWN.value,
                failure_kind=FailureKind.TRANSIENT_ERROR.value,
                error_message="Naive retry limit exceeded",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)

    # -------------------------------------------------------------
    # System C: COMPETENT BOUNDARY BASELINE (Standard engineering implementation: safe coercion, safe idempotent retry, 0 unsafe retries)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.COMPETENT_BASELINE:
        coerced_args = dict(task.arguments)
        for k, v in coerced_args.items():
            prop = descriptor.input_schema.get("properties", {}).get(k, {})
            if prop.get("type") == "integer" and isinstance(v, str) and v.isdigit():
                coerced_args[k] = int(v)
            elif prop.get("type") == "string" and isinstance(v, str):
                coerced_args[k] = v.strip()

        attempts = 0
        max_attempts = 3 if task.is_retryable and task.is_idempotent else 1

        while attempts < max_attempts:
            attempts += 1
            if attempts > 1:
                stats.retry_count += 1
            try:
                raw_mcp_call(**coerced_args)
                success = True
                break
            except Exception as exc:
                clf = classify_exception(exc)
                if clf.kind == FailureKind.SCHEMA_ERROR:
                    stats.schema_failures += 1
                elif clf.kind == FailureKind.PRECONDITION_ERROR:
                    stats.precondition_failures += 1

        if success:
            stats.task_success_count += 1
            if task.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1
                boundary_recovered = True
        else:
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="COMPETENT_BOUNDARY_FAILURE",
                provenance=FailureProvenance.UNKNOWN_STATE.value,
                failure_kind=FailureKind.TRANSIENT_ERROR.value if task.is_idempotent else FailureKind.UNKNOWN_STATE.value,
                error_message="Competent baseline failed to safely resolve",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)

    # -------------------------------------------------------------
    # System D: STRUCTURED FEEDBACK (diagnostic error, agent re-plans)
    # -------------------------------------------------------------
    elif arm == RealMCPArm.STRUCTURED_FEEDBACK:
        try:
            raw_mcp_call(**task.arguments)
            stats.task_success_count += 1
            success = True
        except Exception as exc:
            clf = classify_exception(exc)
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1

            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="STRUCTURED_FEEDBACK_ESCALATION",
                provenance=clf.provenance.value,
                failure_kind=clf.kind.value,
                error_message=f"[{clf.provenance.value}] {clf.kind.value}: {str(exc)}",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)

    # -------------------------------------------------------------
    # System E: VEYRA (transparent boundary resolver & safe retry)
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
            success = True

            if task.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1
                boundary_recovered = True

        except VeyraBoundaryError as vbe:
            # Unrecoverable error safely escalated to agent with structured classification
            clf = vbe.classification
            if clf.kind == FailureKind.SCHEMA_ERROR:
                stats.schema_failures += 1
            elif clf.kind == FailureKind.PRECONDITION_ERROR:
                stats.precondition_failures += 1

            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="VEYRA_BOUNDARY_ESCALATION",
                provenance=clf.provenance.value,
                failure_kind=clf.kind.value,
                error_message=str(vbe),
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    stats.scenario_traces.append({
        "task_id": task.task_id,
        "arm": arm.value,
        "tool_name": task.tool_name,
        "arguments": task.arguments,
        "is_idempotent": task.is_idempotent,
        "is_retryable": task.is_retryable,
        "eligible_for_recovery": task.eligible_for_boundary_recovery,
        "success": success,
        "boundary_recovered": boundary_recovered,
        "unsafe_interventions": unsafe_interventions_count,
        "replans": [r.to_dict() for r in task_replans],
        "duration_ms": duration_ms,
    })
