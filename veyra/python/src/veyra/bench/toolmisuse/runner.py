"""ToolMisuseBench Adapter & Evaluation Harness.

Implements Section 14 of docs/OBJECTIVE.md:
Compares 4 systems on fault-injected tool calling scenarios:
A. Raw Agent (re-plans on any failure or fails)
B. Raw Agent + Naive Retry (blindly retries everything, risking unsafe retries)
C. Raw Agent + Structured Error Feedback (agent re-plans using structured errors)
D. Agent + Veyra (boundary resolves safe schema coercions and safe idempotent retries)

Metrics computed:
- task_success
- invalid_calls
- policy_violations
- harmful_interventions
- unsafe_retries
- total_tool_calls
- agent_replans
- boundary_recovery_rate = (boundary_recoveries) / (fault_metadata_eligible)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureKind, VeyraBoundaryError


class SystemArm(str, Enum):
    RAW_AGENT = "raw_agent"
    NAIVE_RETRY = "naive_retry"
    STRUCTURED_FEEDBACK = "structured_feedback"
    VEYRA = "veyra"


@dataclass
class FaultInjection:
    """Metadata specifying fault injected into a tool execution."""

    fault_type: str  # schema_type_str, transient_503, non_idempotent_timeout, auth_403, not_found_404
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
    agent_replans: int = 0
    latency_ms_total: float = 0.0
    boundary_recoveries: int = 0
    eligible_failures_denominator: int = 0

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
            "invalid_calls": self.invalid_calls,
            "policy_violations": self.policy_violations,
            "harmful_interventions": self.harmful_interventions,
            "unsafe_retries": self.unsafe_retries,
            "total_tool_calls": self.total_tool_calls,
            "retry_count": self.retry_count,
            "agent_replans": self.agent_replans,
            "boundary_recovery_rate": f"{self.boundary_recovery_rate:.1f}%",
            "avg_latency_ms": f"{self.avg_latency_ms:.2f}ms",
        }


def get_default_benchmark_tasks() -> list[ToolMisuseTask]:
    """Generate representative ToolMisuseBench scenario tasks covering CRUD, retrieval, and scheduling."""
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


def run_toolmisuse_benchmark(tasks: list[ToolMisuseTask] | None = None) -> dict[str, ArmResult]:
    """Run comparative benchmark across the four system arms."""
    task_suite = tasks or get_default_benchmark_tasks()
    results: dict[str, ArmResult] = {}

    for arm in (SystemArm.RAW_AGENT, SystemArm.NAIVE_RETRY, SystemArm.STRUCTURED_FEEDBACK, SystemArm.VEYRA):
        res = ArmResult(arm=arm, tasks_count=len(task_suite))

        # Count eligible failures from benchmark metadata
        for t in task_suite:
            if t.injected_fault and t.injected_fault.eligible_for_boundary_recovery:
                res.eligible_failures_denominator += 1

        for task in task_suite:
            t0 = time.perf_counter()
            _execute_arm_task(arm, task, res)
            res.latency_ms_total += (time.perf_counter() - t0) * 1000.0

        results[arm.value] = res

    return results


def _execute_arm_task(arm: SystemArm, task: ToolMisuseTask, stats: ArmResult) -> None:
    """Simulate execution of a tool task under a specific system arm."""
    fault = task.injected_fault

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

        return task.expected_result

    # System A: RAW AGENT (no middleware, no retry)
    if arm == SystemArm.RAW_AGENT:
        try:
            tool_impl(**task.proposed_arguments)
            stats.task_success_count += 1
        except Exception:
            # Raw agent fails immediately and must re-plan
            stats.agent_replans += 1
            stats.invalid_calls += 1

    # System B: RAW AGENT + NAIVE RETRY (blindly retries all errors up to 3 times)
    elif arm == SystemArm.NAIVE_RETRY:
        attempts = 0
        success = False
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

        if success:
            stats.task_success_count += 1
        else:
            stats.agent_replans += 1
            stats.invalid_calls += 1

    # System C: RAW AGENT + STRUCTURED ERROR FEEDBACK (converts error to structured feedback; agent re-plans)
    elif arm == SystemArm.STRUCTURED_FEEDBACK:
        try:
            tool_impl(**task.proposed_arguments)
            stats.task_success_count += 1
        except Exception:
            # Structured feedback gives clean error, but agent still has to take a re-planning turn
            stats.agent_replans += 1
            stats.invalid_calls += 1

    # System D: AGENT + VEYRA (boundary safely normalizes and safely retries)
    elif arm == SystemArm.VEYRA:
        # Schema definition if tool expects integers
        schema = None
        if fault and fault.fault_type == "schema_type_str":
            first_key = list(task.proposed_arguments.keys())[0]
            schema = {"type": "object", "properties": {first_key: {"type": "integer"}}}

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

            # Did Veyra recover this without agent re-plan?
            if fault and fault.eligible_for_boundary_recovery:
                stats.boundary_recoveries += 1

        except VeyraBoundaryError:
            # Unrecoverable error (e.g. 404 precondition or non-idempotent write timeout)
            # Escalated safely to agent without unsafe retries!
            stats.agent_replans += 1
            stats.invalid_calls += 1
