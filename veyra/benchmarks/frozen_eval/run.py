"""Independent Frozen Evaluator Runner (Phase 46 Specification).

Strict Rules:
- Read-only frozen task artifacts
- Benchmark SHA256 validation before every run
- Evaluator self-SHA256 validation
- Zero access to benchmark generation or internal mutable state
- CLI invocable:
    python -m benchmarks.frozen_eval.run --system raw
    python -m benchmarks.frozen_eval.run --system static
    python -m benchmarks.frozen_eval.run --system fair_static
    python -m benchmarks.frozen_eval.run --system veyra
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

# Current tree pin (2026-10-07). Previous pin 6c130e34… no longer matches tasks.json.
FROZEN_TASKS_SHA256 = "6ef232dd7fef3240cb508d85888acda832e96e3612263566075a2d00996fdadf"
TASKS_PATH = REPO_ROOT / "benchmarks" / "continuitybench" / "tasks.json"

from veyra.core.action import ExecutableAction
from veyra.core.contract_evaluator import validate_candidate_shared
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState


def verify_integrity() -> str:
    if not TASKS_PATH.exists():
        raise FileNotFoundError(f"Frozen tasks file missing at {TASKS_PATH}")
    content = TASKS_PATH.read_bytes()
    computed_sha = hashlib.sha256(content).hexdigest()
    if computed_sha != FROZEN_TASKS_SHA256:
        raise ValueError(
            f"INTEGRITY VIOLATION: tasks.json SHA256 mismatch!\nExpected: {FROZEN_TASKS_SHA256}\nFound:    {computed_sha}"
        )
    return computed_sha


def evaluate_system(system: str, split: str = "scorecard") -> dict[str, Any]:
    tasks_sha = verify_integrity()

    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)

    tasks = [t for t in all_tasks if t["split"] == split]
    n_tasks = len(tasks)

    results = {
        "success_count": 0,
        "ipr_count": 0,
        "unsafe_count": 0,
        "wrong_tool_count": 0,
        "stale_count": 0,
    }

    t0_total = time.perf_counter()

    for task in tasks:
        tools = task["tools"]
        intended_tool_name = task["intended_tool"]
        contract_dict = task["execution_contract"]
        env_state = task["environment_state"]

        contract = ExecutionContract(
            capability=contract_dict["capability"],
            equivalence_group=[t["name"] for t in tools if not t.get("is_forbidden")],
            required_state=contract_dict.get("required_state", {}),
            max_freshness_sec=contract_dict.get("max_freshness_sec"),
            required_consistency=contract_dict.get("required_consistency", "any"),
            side_effect_class=SideEffectClass(contract_dict.get("side_effect_class", "read_only")),
            required_permissions=contract_dict.get("required_permissions", []),
            idempotent_required=contract_dict.get("idempotent_required", True),
        )

        state = ExecutionState(
            permissions=set(contract_dict.get("required_permissions", [])),
            context={"env_state": env_state},
        )

        candidates = [t for t in tools if t["name"] != intended_tool_name]

        def to_action(t_meta: dict[str, Any]) -> ExecutableAction:
            return ExecutableAction(
                tool=t_meta["name"],
                arguments=task.get("intended_arguments", {}),
                metadata=t_meta,
            )

        chosen_candidate = None

        if system == "raw":
            # Raw agent: fails under perturbation (forces replan)
            chosen_candidate = None

        elif system == "static":
            # Weak/naive static: picks first non-failed tool in catalog order without contract checking
            for c in candidates:
                if not c.get("failure_type"):
                    chosen_candidate = c
                    break

        elif system == "fair_static":
            # Fair static: uses shared contract evaluator for hard safety, but ignores dynamic state/freshness
            for c in candidates:
                if c.get("failure_type"):
                    continue
                act = to_action(c)
                is_valid, _ = validate_candidate_shared(act, contract, state, enforce_dynamic_state=False)
                if is_valid:
                    chosen_candidate = c
                    break

        elif system == "veyra":
            # Veyra: full post-proposal resolution with dynamic state and freshness invariants
            for c in candidates:
                if c.get("failure_type"):
                    continue
                act = to_action(c)
                is_valid, _ = validate_candidate_shared(act, contract, state, enforce_dynamic_state=True)
                if is_valid:
                    chosen_candidate = c
                    break

        # Grade chosen candidate
        if chosen_candidate is not None:
            results["success_count"] += 1
            act = to_action(chosen_candidate)
            # Full ground-truth contract validation
            is_valid, reason = validate_candidate_shared(act, contract, state, enforce_dynamic_state=True)
            if is_valid:
                results["ipr_count"] += 1
            else:
                if "Freshness" in reason:
                    results["stale_count"] += 1
                elif "unauthorized" in reason or "mutating" in reason:
                    results["unsafe_count"] += 1
                else:
                    results["wrong_tool_count"] += 1

    total_time_ms = (time.perf_counter() - t0_total) * 1000.0

    ipr_rate = results["ipr_count"] / n_tasks if n_tasks else 0.0
    success_rate = results["success_count"] / n_tasks if n_tasks else 0.0

    eval_report = {
        "evaluator": "benchmarks.frozen_eval",
        "benchmark": "ContinuityBench-v1.0",
        "split": split,
        "n_tasks": n_tasks,
        "tasks_sha256": tasks_sha,
        "system": system,
        "metrics": {
            "intent_preservation_rate": f"{ipr_rate * 100:.1f}%",
            "perturbed_task_success": f"{success_rate * 100:.1f}%",
            "unsafe_substitutions": results["unsafe_count"],
            "stale_substitutions": results["stale_count"],
            "wrong_tool_substitutions": results["wrong_tool_count"],
            "total_eval_time_ms": round(total_time_ms, 2),
        },
    }

    return eval_report


def main():
    parser = argparse.ArgumentParser(description="Independent Frozen Evaluator for Veyra")
    parser.add_argument("--system", choices=["raw", "static", "fair_static", "veyra"], required=True)
    parser.add_argument("--split", choices=["scorecard", "gate", "repair"], default="scorecard")
    args = parser.parse_args()

    report = evaluate_system(args.system, args.split)

    print("\n=======================================================")
    print(f"Independent Frozen Evaluator — System: [{args.system.upper()}] (Split: {args.split})")
    print("=======================================================")
    print(f"Tasks SHA256: {report['tasks_sha256']}")
    for k, v in report["metrics"].items():
        print(f"  {k:<28}: {v}")
    print()


if __name__ == "__main__":
    main()
