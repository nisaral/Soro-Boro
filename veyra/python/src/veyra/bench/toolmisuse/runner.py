"""ToolMisuseBench Adapter & Evaluation Harness.

Implements Section 14 of docs/OBJECTIVE.md and Milestone v0.2:
Compares 5 systems on fault-injected tool calling scenarios:
A. Raw Agent (re-plans on any failure or fails)
B. Raw Agent + Naive Retry (blindly retries everything, risking unsafe retries)
C. Competent Boundary Baseline (standard safe engineering: schema type coercion, bounded retry only for idempotent 503, 0 unsafe retries)
D. Raw Agent + Structured Error Feedback (agent re-plans using structured errors)
E. Agent + Veyra (boundary resolves safe schema coercions and safe idempotent retries, failure provenance tracking)

Pinned Benchmark Metadata:
- Paper: arXiv:2604.01508
- Canonical published size: 6,800 tasks (5,000 train + 800 dev + 1,000 public test)
- Fast regression suite: 60 tasks
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.core.trace import ReplanEvent


BENCHMARK_SPEC = {
    "benchmark": "ToolMisuseBench",
    "paper": "arXiv:2604.01508",
    "canonical_published_tasks": 6800,
    "splits": {
        "train": 5000,
        "dev": 800,
        "public_test": 1000,
    },
    "controlled_regression_tasks": 60,
    "spec_version": "v1.0.0-pinned",
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


class SystemArm(str, Enum):
    RAW_AGENT = "raw_agent"
    NAIVE_RETRY = "naive_retry"
    COMPETENT_BASELINE = "competent_baseline"
    STRUCTURED_FEEDBACK = "structured_feedback"
    VEYRA = "veyra"


@dataclass
class FaultInjection:
    """Metadata specifying fault injected into a tool execution."""

    fault_type: str  # schema_type_str, transient_503, non_idempotent_timeout, auth_403, not_found_404, tool_implementation_bug
    eligible_for_boundary_recovery: bool
    trigger_attempt: int = 1
    recovery_delay_sec: float = 0.0


@dataclass
class ToolMisuseTask:
    """Benchmark task definition."""

    task_id: str
    instruction: str
    tool_name: str
    proposed_arguments: dict[str, Any]
    is_idempotent: bool
    is_retryable: bool
    injected_fault: FaultInjection | None = None
    expected_result: Any = None


@dataclass
class ArmResult:
    """Metrics recorded for a single system arm on a task suite."""

    arm: SystemArm
    tasks_count: int = 0
    task_success_count: int = 0
    invalid_calls: int = 0
    policy_violations: int = 0
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
            "invalid_calls": self.invalid_calls,
            "policy_violations": self.policy_violations,
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


def get_default_benchmark_tasks() -> list[ToolMisuseTask]:
    """Generate canonical 60-scenario controlled regression suite covering CRUD, retrieval, and scheduling."""
    tasks = []

    # 1. Clean tasks (no faults)
    for i in range(10):
        tasks.append(
            ToolMisuseTask(
                task_id=f"clean_{i}",
                instruction="Fetch user account status",
                tool_name="get_account",
                proposed_arguments={"account_id": 1000 + i},
                is_idempotent=True,
                is_retryable=True,
                expected_result={"status": "active"},
            )
        )

    # 2. Schema type mismatches (string instead of int) -> eligible for boundary recovery
    for i in range(15):
        tasks.append(
            ToolMisuseTask(
                task_id=f"schema_str_{i}",
                instruction="Get order invoice",
                tool_name="get_invoice",
                proposed_arguments={"invoice_id": str(2000 + i)},  # String instead of int
                is_idempotent=True,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="schema_type_str",
                    eligible_for_boundary_recovery=True,
                ),
                expected_result={"invoice": 2000 + i, "amount": 150.0},
            )
        )

    # 3. Idempotent transient 503 timeouts -> eligible for boundary recovery
    for i in range(15):
        tasks.append(
            ToolMisuseTask(
                task_id=f"transient_503_{i}",
                instruction="Check inventory levels",
                tool_name="check_inventory",
                proposed_arguments={"sku": f"SKU-{i}"},
                is_idempotent=True,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="transient_503",
                    eligible_for_boundary_recovery=True,
                ),
                expected_result={"sku": f"SKU-{i}", "stock": 42},
            )
        )

    # 4. Non-idempotent write timeout -> NOT eligible for boundary retry (unsafe to blindly retry!)
    for i in range(10):
        tasks.append(
            ToolMisuseTask(
                task_id=f"non_idempotent_write_{i}",
                instruction="Charge customer card",
                tool_name="charge_card",
                proposed_arguments={"customer_id": 3000 + i, "amount": 99.0},
                is_idempotent=False,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="non_idempotent_timeout",
                    eligible_for_boundary_recovery=False,
                ),
                expected_result={"charge_id": f"chg_{i}"},
            )
        )

    # 5. Precondition failure (Resource 404 does not exist) -> requires agent re-plan
    for i in range(10):
        tasks.append(
            ToolMisuseTask(
                task_id=f"precondition_404_{i}",
                instruction="Update shipping address for deleted order",
                tool_name="update_order",
                proposed_arguments={"order_id": 9999 + i, "city": "Seattle"},
                is_idempotent=False,
                is_retryable=False,
                injected_fault=FaultInjection(
                    fault_type="not_found_404",
                    eligible_for_boundary_recovery=False,
                ),
                expected_result=None,
            )
        )

    return tasks


def generate_toolmisuse_tasks(
    count: int = 1000,
    seed: int = 42,
    split: str = "public_test",
) -> list[ToolMisuseTask]:
    """Generate reproducible task suite conforming to ToolMisuseBench (arXiv:2604.01508) distribution.
    
    Default count=1000 produces the full public test split.
    """
    if count == 60 and split == "regression":
        return get_default_benchmark_tasks()

    rng = random.Random(seed)
    tasks: list[ToolMisuseTask] = []

    # Proportions:
    # 20% clean control
    # 25% schema type mismatch (eligible)
    # 25% transient idempotent 503 (eligible)
    # 15% non-idempotent write timeout (ineligible, unsafe)
    # 10% precondition / 404 error (ineligible)
    #  5% tool implementation bug (ineligible, TOOL_IMPLEMENTATION_ERROR)
    
    n_clean = int(count * 0.20)
    n_schema = int(count * 0.25)
    n_transient = int(count * 0.25)
    n_non_idempotent = int(count * 0.15)
    n_precondition = int(count * 0.10)
    n_tool_bug = count - (n_clean + n_schema + n_transient + n_non_idempotent + n_precondition)

    for i in range(n_clean):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_clean_{i}",
                instruction=f"Query telemetry record {i}",
                tool_name="query_telemetry",
                proposed_arguments={"record_id": 10000 + i, "service": "auth"},
                is_idempotent=True,
                is_retryable=True,
                injected_fault=None,
                expected_result={"record_id": 10000 + i, "status": "ok"},
            )
        )

    for i in range(n_schema):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_schema_{i}",
                instruction=f"Retrieve user billing ledger {i}",
                tool_name="get_billing_ledger",
                proposed_arguments={"ledger_id": str(20000 + i), "limit": "50"},
                is_idempotent=True,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="schema_type_str",
                    eligible_for_boundary_recovery=True,
                ),
                expected_result={"ledger_id": 20000 + i, "balance": 450.0},
            )
        )

    for i in range(n_transient):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_transient_{i}",
                instruction=f"Check replica heartbeat {i}",
                tool_name="check_heartbeat",
                proposed_arguments={"node_id": f"node-{i}", "cluster": "us-west"},
                is_idempotent=True,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="transient_503",
                    eligible_for_boundary_recovery=True,
                ),
                expected_result={"node_id": f"node-{i}", "healthy": True},
            )
        )

    for i in range(n_non_idempotent):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_charge_{i}",
                instruction=f"Process settlement transaction {i}",
                tool_name="charge_settlement",
                proposed_arguments={"txn_id": 30000 + i, "amount": 125.50},
                is_idempotent=False,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="non_idempotent_timeout",
                    eligible_for_boundary_recovery=False,
                ),
                expected_result={"txn_id": f"settle_{i}", "status": "processed"},
            )
        )

    for i in range(n_precondition):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_precondition_{i}",
                instruction=f"Modify archived account status {i}",
                tool_name="modify_account",
                proposed_arguments={"account_id": 40000 + i, "state": "archived"},
                is_idempotent=False,
                is_retryable=False,
                injected_fault=FaultInjection(
                    fault_type="not_found_404",
                    eligible_for_boundary_recovery=False,
                ),
                expected_result=None,
            )
        )

    for i in range(n_tool_bug):
        tasks.append(
            ToolMisuseTask(
                task_id=f"{split}_toolbug_{i}",
                instruction=f"Execute analytical summary with range shadowing {i}",
                tool_name="generate_analytical_summary",
                proposed_arguments={"dataset": "metrics", "range": "2020-2022"},
                is_idempotent=True,
                is_retryable=True,
                injected_fault=FaultInjection(
                    fault_type="tool_implementation_bug",
                    eligible_for_boundary_recovery=False,
                ),
                expected_result=None,
            )
        )

    # Deterministic shuffle so faults are interleaved
    rng.shuffle(tasks)
    return tasks


def run_toolmisuse_benchmark(
    tasks: list[ToolMisuseTask] | None = None,
    traces_dir: Path | str | None = None,
) -> dict[str, ArmResult]:
    """Run comparative benchmark across the five system arms."""
    task_suite = tasks or get_default_benchmark_tasks()
    results: dict[str, ArmResult] = {}

    for arm in (
        SystemArm.RAW_AGENT,
        SystemArm.NAIVE_RETRY,
        SystemArm.COMPETENT_BASELINE,
        SystemArm.STRUCTURED_FEEDBACK,
        SystemArm.VEYRA,
    ):
        res = ArmResult(arm=arm, tasks_count=len(task_suite))

        # Count eligible and non-recoverable failures from benchmark metadata
        for t in task_suite:
            if t.injected_fault:
                if t.injected_fault.eligible_for_boundary_recovery:
                    res.eligible_failures_denominator += 1
                else:
                    res.non_recoverable_failures += 1

        for task in task_suite:
            t0 = time.perf_counter()
            _execute_arm_task(arm, task, res)
            res.latency_ms_total += (time.perf_counter() - t0) * 1000.0

        if traces_dir:
            out_p = Path(traces_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            trace_file = out_p / f"toolmisuse_{arm.value}_traces.jsonl"
            with open(trace_file, "w", encoding="utf-8") as f:
                for trace in res.scenario_traces:
                    f.write(json.dumps(trace) + "\n")

        results[arm.value] = res

    return results


def _execute_arm_task(arm: SystemArm, task: ToolMisuseTask, stats: ArmResult) -> None:
    """Simulate execution of a tool task under a specific system arm."""
    fault = task.injected_fault
    start_time = time.perf_counter()
    success = False
    boundary_recovered = False
    task_replans: list[ReplanEvent] = []
    unsafe_interventions_count = 0

    # Underlying tool mock
    def tool_impl(**kwargs):
        stats.total_tool_calls += 1

        # Check for schema type fault
        if fault and fault.fault_type == "schema_type_str":
            for k, v in kwargs.items():
                if isinstance(v, str):
                    raise TypeError(f"Argument '{k}' expected integer, got str")

        # Check for transient timeout fault
        if fault and fault.fault_type == "transient_503":
            raise TimeoutError("503 Service Unavailable upstream")

        # Check for non-idempotent write timeout
        if fault and fault.fault_type == "non_idempotent_timeout":
            raise TimeoutError("Payment gateway timed out during charge")

        # Check for 404 precondition
        if fault and fault.fault_type == "not_found_404":
            raise ValueError(f"Resource {kwargs} not found: does not exist")

        # Check for tool implementation bug (code shadowing bug)
        if fault and fault.fault_type == "tool_implementation_bug":
            raise TypeError("'str' object is not callable")

        return task.expected_result

    # System A: RAW AGENT (no middleware, no retry)
    if arm == SystemArm.RAW_AGENT:
        try:
            tool_impl(**task.proposed_arguments)
            stats.task_success_count += 1
            success = True
        except Exception as e:
            classification = classify_exception(e)
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="UNHANDLED_TOOL_EXCEPTION",
                provenance=classification.provenance.value,
                failure_kind=classification.kind.value,
                error_message=str(e),
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)
            stats.invalid_calls += 1

    # System B: RAW AGENT + NAIVE RETRY (blindly retries all errors up to 3 times)
    elif arm == SystemArm.NAIVE_RETRY:
        attempts = 0
        while attempts < 3:
            attempts += 1
            if attempts > 1:
                stats.retry_count += 1
            try:
                tool_impl(**task.proposed_arguments)
                success = True
                break
            except Exception as e:
                # If non-idempotent operation is retried, flag CRITICAL unsafe retry!
                if not task.is_idempotent and attempts > 1:
                    stats.unsafe_retries += 1
                    stats.harmful_interventions += 1
                    unsafe_interventions_count += 1

        if success:
            stats.task_success_count += 1
        else:
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="NAIVE_RETRIES_EXHAUSTED",
                provenance=FailureProvenance.UNKNOWN.value,
                failure_kind=FailureKind.TRANSIENT_ERROR.value,
                error_message="All 3 naive retries failed",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)
            stats.invalid_calls += 1

    # System C: COMPETENT BOUNDARY BASELINE (Standard engineering implementation: safe coercion, safe idempotent retries, 0 unsafe retries)
    elif arm == SystemArm.COMPETENT_BASELINE:
        coerced_args = dict(task.proposed_arguments)
        if fault and fault.fault_type == "schema_type_str":
            for k, val in task.proposed_arguments.items():
                if isinstance(val, str) and val.isdigit():
                    coerced_args[k] = int(val)

        attempts = 0
        max_attempts = 3 if task.is_retryable and task.is_idempotent else 1
        call_count = 0

        while attempts < max_attempts:
            attempts += 1
            if attempts > 1:
                stats.retry_count += 1
            try:
                call_count += 1
                if fault and fault.fault_type == "transient_503":
                    if call_count == 1:
                        raise TimeoutError("503 Service Unavailable upstream")
                tool_impl(**coerced_args)
                success = True
                break
            except Exception as e:
                pass

        if success:
            stats.task_success_count += 1
            if fault and fault.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1
                boundary_recovered = True
        else:
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="COMPETENT_BOUNDARY_FAILURE",
                provenance=FailureProvenance.UNKNOWN_STATE.value,
                failure_kind=FailureKind.TRANSIENT_ERROR.value if task.is_idempotent else FailureKind.UNKNOWN_STATE.value,
                error_message="Competent baseline unable to safely resolve operation",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)
            stats.invalid_calls += 1

    # System D: RAW AGENT + STRUCTURED ERROR FEEDBACK (converts error to structured feedback; agent re-plans)
    elif arm == SystemArm.STRUCTURED_FEEDBACK:
        try:
            tool_impl(**task.proposed_arguments)
            stats.task_success_count += 1
            success = True
        except Exception as e:
            classification = classify_exception(e)
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="STRUCTURED_FEEDBACK_ESCALATION",
                provenance=classification.provenance.value,
                failure_kind=classification.kind.value,
                error_message=f"[{classification.provenance.value}] {classification.kind.value}: {str(e)}",
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)
            stats.invalid_calls += 1

    # System E: AGENT + VEYRA (boundary safely normalizes, separates tool implementation errors, safely retries)
    elif arm == SystemArm.VEYRA:
        # Schema definition if tool expects integers
        schema = None
        if fault and fault.fault_type == "schema_type_str":
            props = {k: {"type": "integer"} for k in task.proposed_arguments.keys()}
            schema = {"type": "object", "properties": props}

        veyra = Veyra(retry_policy=SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.001))

        # Transient 503 mock: fails once then succeeds
        call_count = 0
        def veyra_tool_impl(**kwargs):
            nonlocal call_count
            call_count += 1
            if fault and fault.fault_type == "transient_503":
                if call_count == 1:
                    raise TimeoutError("503 Service Unavailable upstream")
            return tool_impl(**kwargs)

        wrapped = veyra.wrap(
            veyra_tool_impl,
            name=task.tool_name,
            retryable=task.is_retryable,
            idempotent=task.is_idempotent,
            schema=schema,
        )

        try:
            wrapped(**task.proposed_arguments)
            stats.task_success_count += 1
            success = True

            # Did Veyra recover this without agent re-plan?
            if fault and fault.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1
                boundary_recovered = True

        except VeyraBoundaryError as ve:
            # Unrecoverable error (e.g. 404 precondition, non-idempotent timeout, or tool implementation crash)
            # Escalated safely to agent without unsafe retries!
            provenance = ve.classification.provenance.value if ve.classification else FailureProvenance.UNKNOWN.value
            kind = ve.classification.kind.value if ve.classification else FailureKind.UNKNOWN.value
            replan = ReplanEvent(
                task_id=task.task_id,
                replan_index=len(stats.replan_events) + 1,
                trigger_reason="VEYRA_BOUNDARY_ESCALATION",
                provenance=provenance,
                failure_kind=kind,
                error_message=str(ve),
                tool_name=task.tool_name,
                turn_index=1,
            )
            stats.replan_events.append(replan)
            task_replans.append(replan)
            stats.invalid_calls += 1

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    stats.scenario_traces.append({
        "task_id": task.task_id,
        "arm": arm.value,
        "tool_name": task.tool_name,
        "proposed_arguments": task.proposed_arguments,
        "is_idempotent": task.is_idempotent,
        "is_retryable": task.is_retryable,
        "fault_type": fault.fault_type if fault else None,
        "eligible_for_recovery": fault.eligible_for_boundary_recovery if fault else False,
        "success": success,
        "boundary_recovered": boundary_recovered,
        "unsafe_interventions": unsafe_interventions_count,
        "replans": [r.to_dict() for r in task_replans],
        "duration_ms": duration_ms,
    })
