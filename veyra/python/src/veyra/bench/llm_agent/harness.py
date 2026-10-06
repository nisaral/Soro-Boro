"""Execution Harness for Real LLM Agent Comparative Evaluation.

Implements Step 3 & Tier 2:
Architecture:
Real LLM Agent ↓ proposed tool call ↓ Veyra (or Arm) ↓ real MCP server ↓ real result
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from veyra.bench.llm_agent.agent import AgentDriver, AgentTurnOutput
from veyra.bench.llm_agent.scenarios import AgentBenchmarkTask
from veyra.bench.mcp_real.catalogs import MCPToolDescriptor, RealMCPCatalogManager
from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.core.trace import ReplanEvent
from veyra.registry import DeterministicCandidateResolver, ToolDefinition, ToolRegistry


class AgentArm(str, Enum):
    RAW = "raw"
    COMPETENT_BASELINE = "competent_baseline"
    VEYRA = "veyra"


@dataclass
class TurnRecord:
    """Record of a single turn in an agent trajectory."""

    turn_index: int
    thought: str
    proposed_tool: str | None
    proposed_args: dict[str, Any]
    resolved_tool: str | None
    resolved_args: dict[str, Any]
    observation: str
    is_replan: bool = False
    boundary_recovered: bool = False
    duration_ms: float = 0.0


@dataclass
class TrajectoryResult:
    """Outcome and execution record of an agent solving a task."""

    task_id: str
    seed: int
    arm: AgentArm
    success: bool
    final_answer: str
    turns_count: int
    replan_count: int
    boundary_recoveries: int
    unsafe_retries: int
    total_latency_ms: float
    replan_events: list[ReplanEvent] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "arm": self.arm.value,
            "success": self.success,
            "final_answer": self.final_answer,
            "turns_count": self.turns_count,
            "replan_count": self.replan_count,
            "boundary_recoveries": self.boundary_recoveries,
            "unsafe_retries": self.unsafe_retries,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "replans": [r.to_dict() for r in self.replan_events],
            "turns": [
                {
                    "turn_index": t.turn_index,
                    "thought": t.thought,
                    "proposed_tool": t.proposed_tool,
                    "proposed_args": t.proposed_args,
                    "resolved_tool": t.resolved_tool,
                    "observation": t.observation[:200] if len(t.observation) > 200 else t.observation,
                    "is_replan": t.is_replan,
                    "boundary_recovered": t.boundary_recovered,
                }
                for t in self.turns
            ],
        }


class LLMAgentHarness:
    """Runs a multi-turn agent loop against real MCP tools under a chosen arm."""

    def __init__(
        self,
        catalog_mgr: RealMCPCatalogManager | None = None,
    ):
        self.catalog = catalog_mgr or RealMCPCatalogManager()

    def run_task(
        self,
        task: AgentBenchmarkTask,
        agent: AgentDriver,
        arm: AgentArm,
    ) -> TrajectoryResult:
        """Run a single benchmark task to completion or turn limit."""
        available_tools: list[dict[str, Any]] = []
        for name in task.allowed_tools:
            desc = self.catalog.get_tool(name)
            if desc:
                available_tools.append({
                    "name": desc.name,
                    "description": getattr(desc, "description", f"{desc.catalog} tool"),
                    "schema": desc.input_schema,
                })

        conversation_history: list[dict[str, Any]] = []
        replan_events: list[ReplanEvent] = []
        turns: list[TurnRecord] = []
        boundary_recoveries = 0
        unsafe_retries = 0
        start_traj_time = time.perf_counter()

        # Build Veyra boundary resolver if evaluating VEYRA arm
        veyra_interceptor = None
        if arm == AgentArm.VEYRA:
            veyra_interceptor = Veyra(
                retry_policy=SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.001)
            )
            for t_name in task.allowed_tools:
                desc = self.catalog.get_tool(t_name)
                if desc:
                    veyra_interceptor.registry.register(
                        ToolDefinition(
                            name=desc.name,
                            schema=desc.input_schema,
                            retryable=desc.is_retryable,
                            idempotent=desc.is_idempotent,
                        )
                    )
            # Register known equivalents / aliases
            for alias, canonical in task.tool_aliases.items():
                veyra_interceptor.equivalent(canonical, [alias])

        call_attempts_map: dict[str, int] = {}

        for turn_idx in range(1, task.max_turns + 1):
            t_start = time.perf_counter()
            agent_output: AgentTurnOutput = agent.act(
                task=task,
                conversation_history=conversation_history,
                available_tools=available_tools,
            )

            # Check if agent terminated with a final answer
            if agent_output.final_answer is not None:
                is_success = True
                if task.verifier is not None:
                    is_success = task.verifier(agent_output.final_answer, conversation_history)

                traj_duration = (time.perf_counter() - start_traj_time) * 1000.0
                return TrajectoryResult(
                    task_id=task.task_id,
                    seed=task.seed,
                    arm=arm,
                    success=is_success,
                    final_answer=agent_output.final_answer,
                    turns_count=turn_idx,
                    replan_count=len(replan_events),
                    boundary_recoveries=boundary_recoveries,
                    unsafe_retries=unsafe_retries,
                    total_latency_ms=traj_duration,
                    replan_events=replan_events,
                    turns=turns,
                )

            # Agent proposed a tool call
            proposed_tool = agent_output.tool_name or ""
            proposed_args = agent_output.tool_args or {}
            resolved_tool = proposed_tool
            resolved_args = dict(proposed_args)
            observation = ""
            is_replan = False
            boundary_recovered = False

            # Dispatch proposed tool under chosen arm
            if arm == AgentArm.RAW:
                # Direct call to tool without mediation
                desc = self.catalog.get_tool(proposed_tool)
                if desc is None:
                    # Tool name not found: causes raw failure
                    err_msg = f"Tool '{proposed_tool}' not found in active catalog."
                    observation = f"Tool Error: {err_msg}"
                    replan = ReplanEvent(
                        task_id=task.task_id,
                        replan_index=len(replan_events) + 1,
                        trigger_reason="TOOL_NOT_FOUND",
                        provenance=FailureProvenance.AGENT_ARGUMENT_ERROR.value,
                        failure_kind=FailureKind.SCHEMA_ERROR.value,
                        error_message=err_msg,
                        tool_name=proposed_tool,
                        turn_index=turn_idx,
                    )
                    replan_events.append(replan)
                    is_replan = True
                else:
                    try:
                        # Check injected transient 503
                        attempt = call_attempts_map.get(proposed_tool, 0) + 1
                        call_attempts_map[proposed_tool] = attempt
                        if task.injected_transient and attempt == 1:
                            raise TimeoutError("503 Service Unavailable upstream")

                        raw_res = desc.handler(**proposed_args)
                        observation = str(raw_res)
                    except Exception as e:
                        clf = classify_exception(e)
                        observation = f"Tool Error: {str(e)}"
                        replan = ReplanEvent(
                            task_id=task.task_id,
                            replan_index=len(replan_events) + 1,
                            trigger_reason="RAW_TOOL_EXCEPTION",
                            provenance=clf.provenance.value,
                            failure_kind=clf.kind.value,
                            error_message=str(e),
                            tool_name=proposed_tool,
                            turn_index=turn_idx,
                        )
                        replan_events.append(replan)
                        is_replan = True

            elif arm == AgentArm.COMPETENT_BASELINE:
                # Production engineering baseline: basic coercion and safe idempotent retry
                desc = self.catalog.get_tool(proposed_tool)
                if desc is None:
                    err_msg = f"Tool '{proposed_tool}' not found."
                    observation = f"Tool Error: {err_msg}"
                    replan = ReplanEvent(
                        task_id=task.task_id,
                        replan_index=len(replan_events) + 1,
                        trigger_reason="TOOL_NOT_FOUND",
                        provenance=FailureProvenance.AGENT_ARGUMENT_ERROR.value,
                        failure_kind=FailureKind.SCHEMA_ERROR.value,
                        error_message=err_msg,
                        tool_name=proposed_tool,
                        turn_index=turn_idx,
                    )
                    replan_events.append(replan)
                    is_replan = True
                else:
                    # Basic string-to-int coercion
                    coerced = dict(proposed_args)
                    for k, v in proposed_args.items():
                        if isinstance(v, str) and v.isdigit():
                            coerced[k] = int(v)

                    max_retries = 3 if desc.is_idempotent and desc.is_retryable else 1
                    call_success = False
                    last_err = None

                    for att in range(1, max_retries + 1):
                        try:
                            # Injected transient check
                            total_att = call_attempts_map.get(proposed_tool, 0) + 1
                            call_attempts_map[proposed_tool] = total_att
                            if task.injected_transient and total_att == 1:
                                raise TimeoutError("503 Service Unavailable upstream")

                            raw_res = desc.handler(**coerced)
                            observation = str(raw_res)
                            call_success = True
                            if att > 1 or coerced != proposed_args:
                                boundary_recovered = True
                                boundary_recoveries += 1
                            break
                        except Exception as e:
                            last_err = e

                    if not call_success:
                        clf = classify_exception(last_err)
                        observation = f"Tool Error: {str(last_err)}"
                        replan = ReplanEvent(
                            task_id=task.task_id,
                            replan_index=len(replan_events) + 1,
                            trigger_reason="COMPETENT_BASELINE_UNRESOLVED",
                            provenance=clf.provenance.value,
                            failure_kind=clf.kind.value,
                            error_message=str(last_err),
                            tool_name=proposed_tool,
                            turn_index=turn_idx,
                        )
                        replan_events.append(replan)
                        is_replan = True

            elif arm == AgentArm.VEYRA:
                # Full Veyra resolution layer: candidate resolver + schema coercion + safe retry
                assert veyra_interceptor is not None
                action_prop = ExecutableAction(tool=proposed_tool, arguments=proposed_args)
                state = ExecutionState(agent="llm_agent")
                candidates = veyra_interceptor.resolver.resolve(action_prop, state)
                desc = None
                resolved_tool = proposed_tool
                for c in candidates:
                    d = self.catalog.get_tool(c.tool)
                    if d is not None:
                        resolved_tool = c.tool
                        desc = d
                        break
                if desc is None:
                    observation = f"Veyra Resolution Error: No tool candidate matches '{proposed_tool}'."
                    replan = ReplanEvent(
                        task_id=task.task_id,
                        replan_index=len(replan_events) + 1,
                        trigger_reason="VEYRA_NO_CANDIDATE",
                        provenance=FailureProvenance.AGENT_ARGUMENT_ERROR.value,
                        failure_kind=FailureKind.SCHEMA_ERROR.value,
                        error_message=observation,
                        tool_name=proposed_tool,
                        turn_index=turn_idx,
                    )
                    replan_events.append(replan)
                    is_replan = True
                else:
                    def tool_call_fn(**kwargs):
                        total_att = call_attempts_map.get(desc.name, 0) + 1
                        call_attempts_map[desc.name] = total_att
                        if task.injected_transient and total_att == 1:
                            raise TimeoutError("503 Service Unavailable upstream")
                        return desc.handler(**kwargs)

                    wrapped = veyra_interceptor.wrap(
                        tool_call_fn,
                        name=desc.name,
                        retryable=desc.is_retryable,
                        idempotent=desc.is_idempotent,
                        schema=desc.input_schema,
                    )

                    try:
                        raw_res = wrapped(**proposed_args)
                        observation = str(raw_res)

                        # Was there an alias or transient recovery that avoided an agent replan?
                        if resolved_tool != proposed_tool or task.injected_transient or task.injected_schema_mismatch:
                            boundary_recovered = True
                            boundary_recoveries += 1

                    except VeyraBoundaryError as vbe:
                        clf = vbe.classification
                        observation = f"[{clf.provenance.value}] {clf.kind.value}: {str(vbe)}"
                        replan = ReplanEvent(
                            task_id=task.task_id,
                            replan_index=len(replan_events) + 1,
                            trigger_reason="VEYRA_BOUNDARY_ESCALATION",
                            provenance=clf.provenance.value,
                            failure_kind=clf.kind.value,
                            error_message=str(vbe),
                            tool_name=resolved_tool,
                            turn_index=turn_idx,
                        )
                        replan_events.append(replan)
                        is_replan = True

            # Record turn
            turn_duration = (time.perf_counter() - t_start) * 1000.0
            turn_rec = TurnRecord(
                turn_index=turn_idx,
                thought=agent_output.thought,
                proposed_tool=proposed_tool,
                proposed_args=proposed_args,
                resolved_tool=resolved_tool,
                resolved_args=resolved_args,
                observation=observation,
                is_replan=is_replan,
                boundary_recovered=boundary_recovered,
                duration_ms=turn_duration,
            )
            turns.append(turn_rec)

            conversation_history.append({
                "thought": agent_output.thought,
                "tool_call": {"name": proposed_tool, "args": proposed_args},
                "observation": observation,
            })

        # Exceeded max turns
        traj_duration = (time.perf_counter() - start_traj_time) * 1000.0
        return TrajectoryResult(
            task_id=task.task_id,
            seed=task.seed,
            arm=arm,
            success=False,
            final_answer="MAX_TURNS_EXCEEDED",
            turns_count=task.max_turns,
            replan_count=len(replan_events),
            boundary_recoveries=boundary_recoveries,
            unsafe_retries=unsafe_retries,
            total_latency_ms=traj_duration,
            replan_events=replan_events,
            turns=turns,
        )
