import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.continuitybench.builder import build_all_tasks
from benchmarks.continuitybench.evaluator import build_harness_for_task, run_single_arm
from benchmarks.continuitybench.schema import ContinuityTask, GeneralizationSplit, PerturbationType
from veyra.core.execution_contract import ExecutionContract, SideEffectClass


def test_continuitybench_task_generation():
    """Verify task builder produces 120 valid tasks across all 3 splits and 10 perturbation types."""
    tasks = build_all_tasks()
    assert len(tasks) == 120

    splits = {t.split: 0 for t in tasks}
    for t in tasks:
        splits[t.split] += 1

    assert splits[GeneralizationSplit.REPAIR.value] == 40
    assert splits[GeneralizationSplit.GATE.value] == 40
    assert splits[GeneralizationSplit.SCORECARD.value] == 40

    # Ensure every task has valid execution contract
    for t in tasks:
        assert t.execution_contract.capability
        assert len(t.tools) >= 3
        assert len(t.valid_resolution_tools) >= 1
        assert len(t.forbidden_resolution_tools) >= 1


def test_paired_perturbation_clean_vs_perturbed():
    """Verify clean run succeeds on primary, while perturbed run exercises alternate resolution."""
    tasks = build_all_tasks()
    task = tasks[0]

    # Clean run: primary succeeds
    reg_clean, calls_clean = build_harness_for_task(task, is_perturbed=False)
    res_clean = run_single_arm("raw_agent", task, is_perturbed=False, registry=reg_clean, calls=calls_clean)
    assert res_clean["success"] is True
    assert res_clean["resolved_tool"] == task.intended_tool

    # Perturbed run: raw_agent fails, while veyra resolves to valid replica
    reg_pert, calls_pert = build_harness_for_task(task, is_perturbed=True)
    res_raw_pert = run_single_arm("raw_agent", task, is_perturbed=True, registry=reg_pert, calls=calls_pert)
    assert res_raw_pert["success"] is False

    reg_pert2, calls_pert2 = build_harness_for_task(task, is_perturbed=True)
    res_veyra_pert = run_single_arm("veyra", task, is_perturbed=True, registry=reg_pert2, calls=calls_pert2)
    assert res_veyra_pert["success"] is True
    assert res_veyra_pert["intent_preserved"] is True
    assert res_veyra_pert["resolved_tool"] in task.valid_resolution_tools


def test_static_resolution_fails_contract_where_veyra_succeeds():
    """Verify that on state/freshness constrained tasks, static_resolution selects stale tool whereas Veyra preserves intent."""
    tasks = build_all_tasks()
    stale_tasks = [t for t in tasks if t.perturbation_type == PerturbationType.G_STALE_IMPLEMENTATION.value]
    assert len(stale_tasks) > 0
    task = stale_tasks[0]

    # Static resolution picks first declared fallback (which is stale)
    reg_static, calls_static = build_harness_for_task(task, is_perturbed=True)
    res_static = run_single_arm("static_resolution", task, is_perturbed=True, registry=reg_static, calls=calls_static)
    assert res_static["success"] is True
    # Fails intent preservation because stale tool violates freshness contract
    assert res_static["intent_preserved"] is False

    # Veyra enforces ExecutionContract, skips stale, selects fresh replica
    reg_veyra, calls_veyra = build_harness_for_task(task, is_perturbed=True)
    res_veyra = run_single_arm("veyra", task, is_perturbed=True, registry=reg_veyra, calls=calls_veyra)
    assert res_veyra["success"] is True
    assert res_veyra["intent_preserved"] is True
    assert res_veyra["unsafe_substitution"] is False
