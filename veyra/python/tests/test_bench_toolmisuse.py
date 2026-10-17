"""Tests for ToolMisuseBench Evaluation Harness."""

from veyra.bench.toolmisuse.runner import SystemArm, get_default_benchmark_tasks, run_toolmisuse_benchmark


def test_toolmisuse_comparative_benchmark():
    tasks = get_default_benchmark_tasks()
    results = run_toolmisuse_benchmark(tasks)

    assert SystemArm.RAW_AGENT.value in results
    assert SystemArm.NAIVE_RETRY.value in results
    assert SystemArm.COMPETENT_BASELINE.value in results
    assert SystemArm.STRUCTURED_FEEDBACK.value in results
    assert SystemArm.VEYRA.value in results

    raw_arm = results[SystemArm.RAW_AGENT.value]
    naive_arm = results[SystemArm.NAIVE_RETRY.value]
    veyra_arm = results[SystemArm.VEYRA.value]

    # Veyra achieves higher task success by safely resolving eligible faults at the boundary
    assert veyra_arm.task_success_rate > raw_arm.task_success_rate

    # Veyra achieves boundary recoveries without agent replanning
    assert veyra_arm.boundary_recoveries > 0
    assert veyra_arm.boundary_recovery_rate > 0.0

    # Naive retry commits unsafe retries on non-idempotent actions
    assert naive_arm.unsafe_retries > 0

    # Critical Safety Invariant: Veyra commits ZERO unsafe retries
    assert veyra_arm.unsafe_retries == 0
    assert veyra_arm.harmful_interventions == 0
