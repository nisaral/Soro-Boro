"""Case Memory Held-Out Transfer Evaluation (Section 6).

Evaluates Case Memory across strict Train/Dev/Test split (no scenario duplication):
- Train Case Memory ONLY on TRAIN split (N=120 scenarios)
- Zero tuning or training on TEST split (N=60 held-out scenarios)

Compares on held-out TEST:
1. Static Priority (StaticPriorityResolver)
2. Policy-Aware (PolicyAwareResolver)
3. Veyra (VeyraResolver default)
4. Veyra + CaseMemory (VeyraResolver with Case Memory)

Reports: Recall@1, Recall@3, Intent Preservation, Policy Violations, Unsafe Selection, Latency.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import PolicyAwareResolver, StaticPriorityResolver, VeyraResolver
from benchmarks.resolution.eval_harness import MockCaseMemory, evaluate_resolver_on_scenario
from benchmarks.resolution.scenarios import ResolutionScenario, generate_resolution_scenarios


@dataclass
class TransferMetrics:
    resolver: str
    split: str
    n_scenarios: int
    recall_at_1: float
    recall_at_3: float
    intent_preservation_rate: float
    policy_violation_rate: float
    unsafe_selection_rate: float
    latency_p50_us: float


def run_case_memory_transfer_experiment(seed: int = 42) -> dict[str, Any]:
    """Execute strict Train/Dev/Test transfer experiment for Case Memory."""
    rng = random.Random(seed)
    all_scenarios = generate_resolution_scenarios(n_per_category=12)  # 240 scenarios total
    rng.shuffle(all_scenarios)

    # 50% TRAIN (120), 25% DEV (60), 25% TEST (60)
    train_split = all_scenarios[:120]
    dev_split = all_scenarios[120:180]
    test_split = all_scenarios[180:]

    # Train Case Memory ONLY on TRAIN split
    case_memory_data: dict[str, float] = {}
    for scen in train_split:
        if scen.expected_selected_tool:
            case_memory_data[scen.expected_selected_tool] = case_memory_data.get(scen.expected_selected_tool, 0.0) + 1.0

    mock_case_memory = MockCaseMemory(case_memory_data)

    resolvers_to_test = ["static_priority", "policy_aware", "veyra", "veyra_case_memory"]
    results_by_resolver: dict[str, TransferMetrics] = {}

    for res_name in resolvers_to_test:
        eval_results = []
        for scen in test_split:
            reg = scen.build_registry()
            if res_name == "static_priority":
                inst = StaticPriorityResolver(reg)
            elif res_name == "policy_aware":
                inst = PolicyAwareResolver(reg)
            elif res_name == "veyra":
                inst = VeyraResolver(reg)
            elif res_name == "veyra_case_memory":
                inst = VeyraResolver(reg, case_memory=mock_case_memory, enable_case_memory=True)
            else:
                inst = None

            eval_res = evaluate_resolver_on_scenario(res_name, inst, scen, rng)
            eval_results.append(eval_res)

        total = len(eval_results)
        rec1 = sum(1 for r in eval_results if r.is_recall_1) / total * 100.0
        rec3 = sum(1 for r in eval_results if r.is_recall_3) / total * 100.0
        viol = sum(1 for r in eval_results if r.has_policy_violation) / total * 100.0
        unsafe = sum(1 for r in eval_results if r.is_unsafe) / total * 100.0
        neg_ctrls = [r for r in eval_results if r.is_negative_control]
        intent_pres = (sum(1 for r in neg_ctrls if not r.unnecessary_intervention) / len(neg_ctrls) * 100.0) if neg_ctrls else 100.0

        lats = sorted(r.latency_us for r in eval_results)
        p50 = lats[int(len(lats) * 0.50)]

        results_by_resolver[res_name] = TransferMetrics(
            resolver=res_name,
            split="held_out_test",
            n_scenarios=total,
            recall_at_1=round(rec1, 2),
            recall_at_3=round(rec3, 2),
            intent_preservation_rate=round(intent_pres, 2),
            policy_violation_rate=round(viol, 2),
            unsafe_selection_rate=round(unsafe, 2),
            latency_p50_us=round(p50, 2),
        )

    # Decision rule: check if Case Memory improves held-out TEST
    veyra_rec1 = results_by_resolver["veyra"].recall_at_1
    cm_rec1 = results_by_resolver["veyra_case_memory"].recall_at_1
    transfer_successful = (cm_rec1 >= veyra_rec1)

    return {
        "train_scenarios_count": len(train_split),
        "held_out_test_scenarios_count": len(test_split),
        "results": {k: asdict(v) for k, v in results_by_resolver.items()},
        "case_memory_held_out_transfer": transfer_successful,
        "recommendation": "Retain Case Memory in optional policy ranking" if transfer_successful else "Remove Case Memory from default path",
    }


if __name__ == "__main__":
    report = run_case_memory_transfer_experiment()
    print("\n# CASE MEMORY HELD-OUT TRANSFER EXPERIMENT\n")
    print(json.dumps(report, indent=2))
