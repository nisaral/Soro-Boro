"""Runner for the True LLM Agent Comparative Benchmark.

Implements Step 3 & Tier 2:
Runs across 5 seeds (seeds 1 to 5) evaluating:
- Raw Agent
- Competent Boundary Baseline
- Veyra
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veyra.bench.llm_agent.agent import AgentDriver, DeterministicSimulatedAgentDriver
from veyra.bench.llm_agent.harness import AgentArm, LLMAgentHarness, TrajectoryResult
from veyra.bench.llm_agent.scenarios import AgentBenchmarkTask, get_llm_agent_tasks
from veyra.bench.toolmisuse.runner import compute_wilson_ci


BENCHMARK_SPEC = {
    "benchmark": "Veyra-LLM-Agent-Real-MCP",
    "tier": "Tier 2 — Real MCP Agent Evaluation",
    "architecture": "Real LLM Agent -> proposed tool call -> Boundary Arm -> Real FastMCP Server -> real result",
    "models_supported": ["openai-compatible", "simulated-deterministic"],
    "seeds": [1, 2, 3, 4, 5],
    "arms": ["raw", "competent_baseline", "veyra"],
    "spec_version": "v0.2.0-pinned",
}


@dataclass
class LLMAgentArmResult:
    """Aggregated metrics for an arm evaluated on the LLM agent benchmark across seeds."""

    arm: AgentArm
    total_tasks: int = 0
    successful_tasks: int = 0
    total_turns: int = 0
    total_replans: int = 0
    boundary_recoveries: int = 0
    unsafe_retries: int = 0
    total_latency_ms: float = 0.0
    trajectories: list[TrajectoryResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.successful_tasks / max(1, self.total_tasks)) * 100.0

    @property
    def success_ci_95(self) -> tuple[float, float]:
        return compute_wilson_ci(self.successful_tasks, self.total_tasks)

    @property
    def avg_turns_per_task(self) -> float:
        return self.total_turns / max(1, self.total_tasks)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(1, self.total_tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "success_rate": f"{self.success_rate:.1f}%",
            "success_ci_95": self.success_ci_95,
            "total_turns": self.total_turns,
            "avg_turns_per_task": round(self.avg_turns_per_task, 2),
            "total_replans": self.total_replans,
            "boundary_recoveries": self.boundary_recoveries,
            "unsafe_retries": self.unsafe_retries,
            "avg_latency_ms": f"{self.avg_latency_ms:.2f}ms",
        }


@dataclass
class LLMAgentBenchmarkResult:
    """Complete results across arms and seeds."""

    model_name: str
    seeds_evaluated: list[int]
    arm_results: dict[str, LLMAgentArmResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "seeds_evaluated": self.seeds_evaluated,
            "spec": BENCHMARK_SPEC,
            "arms": {k: v.to_dict() for k, v in self.arm_results.items()},
        }


def run_llm_agent_benchmark(
    agent_driver: AgentDriver | None = None,
    model_name: str = "simulated-agent",
    seeds: list[int] | None = None,
    arms: list[AgentArm] | None = None,
    traces_dir: Path | str | None = None,
) -> LLMAgentBenchmarkResult:
    """Run comparative agent-level evaluation across designated seeds and arms."""
    evaluated_seeds = seeds or [1, 2, 3, 4, 5]
    evaluated_arms = arms or [AgentArm.RAW, AgentArm.COMPETENT_BASELINE, AgentArm.VEYRA]
    agent = agent_driver or DeterministicSimulatedAgentDriver()
    harness = LLMAgentHarness()

    overall = LLMAgentBenchmarkResult(
        model_name=model_name,
        seeds_evaluated=evaluated_seeds,
    )

    for arm in evaluated_arms:
        arm_res = LLMAgentArmResult(arm=arm)

        for seed in evaluated_seeds:
            tasks = get_llm_agent_tasks(seed=seed)
            for task in tasks:
                traj = harness.run_task(task=task, agent=agent, arm=arm)
                arm_res.total_tasks += 1
                if traj.success:
                    arm_res.successful_tasks += 1
                arm_res.total_turns += traj.turns_count
                arm_res.total_replans += traj.replan_count
                arm_res.boundary_recoveries += traj.boundary_recoveries
                arm_res.unsafe_retries += traj.unsafe_retries
                arm_res.total_latency_ms += traj.total_latency_ms
                arm_res.trajectories.append(traj)

        if traces_dir:
            out_p = Path(traces_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            trace_file = out_p / f"llm_agent_{model_name}_{arm.value}_traces.jsonl"
            with open(trace_file, "w", encoding="utf-8") as f:
                for traj in arm_res.trajectories:
                    f.write(json.dumps(traj.to_dict()) + "\n")

        overall.arm_results[arm.value] = arm_res

    return overall
