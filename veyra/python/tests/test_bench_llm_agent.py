"""Tests for the True LLM Agent Comparative Evaluation Harness (Step 3 & Tier 2)."""

import pytest
from veyra.bench.llm_agent import (
    AgentArm,
    DeterministicSimulatedAgentDriver,
    LLMAgentHarness,
    get_llm_agent_tasks,
    run_llm_agent_benchmark,
)


def test_llm_agent_scenarios_generated():
    """Verify scenarios for each seed produce distinct valid tasks."""
    for s in (1, 2, 3, 4, 5):
        tasks = get_llm_agent_tasks(seed=s)
        assert len(tasks) == 4
        assert all(t.seed == s for t in tasks)
        assert any(t.injected_transient for t in tasks)
        assert any(t.injected_schema_mismatch for t in tasks)


def test_llm_agent_comparative_benchmark_all_seeds(tmp_path):
    """Run true agent harness across 5 seeds comparing Raw, Competent Baseline, and Veyra."""
    result = run_llm_agent_benchmark(
        seeds=[1, 2, 3, 4, 5],
        traces_dir=tmp_path,
    )

    assert "raw" in result.arm_results
    assert "competent_baseline" in result.arm_results
    assert "veyra" in result.arm_results

    raw_arm = result.arm_results["raw"]
    competent_arm = result.arm_results["competent_baseline"]
    veyra_arm = result.arm_results["veyra"]

    # Total tasks across 5 seeds = 5 seeds * 4 tasks = 20 tasks
    assert raw_arm.total_tasks == 20
    assert competent_arm.total_tasks == 20
    assert veyra_arm.total_tasks == 20

    # Veyra achieves higher or equal task success with lower turns and fewer replans
    assert veyra_arm.success_rate >= raw_arm.success_rate
    assert veyra_arm.total_replans < raw_arm.total_replans
    assert veyra_arm.boundary_recoveries > 0

    # Critical Safety Invariant: ZERO unsafe retries
    assert veyra_arm.unsafe_retries == 0
    assert competent_arm.unsafe_retries == 0

    # Traces were persisted
    trace_files = list(tmp_path.glob("*.jsonl"))
    assert len(trace_files) == 3


def test_llm_agent_harness_single_task():
    """Verify single task execution through the harness."""
    harness = LLMAgentHarness()
    tasks = get_llm_agent_tasks(seed=1)
    task = tasks[0]  # weather_calc task with alias proposal
    agent = DeterministicSimulatedAgentDriver()

    res_raw = harness.run_task(task=task, agent=agent, arm=AgentArm.RAW)
    res_veyra = harness.run_task(task=task, agent=agent, arm=AgentArm.VEYRA)

    # Raw agent encounters tool alias error and must re-plan
    assert res_raw.replan_count >= 1

    # Veyra resolves the alias transparently at the tool boundary, avoiding the re-plan turn!
    assert res_veyra.replan_count == 0
    assert res_veyra.boundary_recoveries >= 1
    assert res_veyra.success is True
