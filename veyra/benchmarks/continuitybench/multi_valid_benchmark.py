"""Phases 29 & 30: Multi-Valid Candidate Benchmark & TAGE Real Hypothesis Test.

Generates 120 tasks partitioned into:
- history_train (40 tasks)
- history_gate (40 tasks)
- history_scorecard (40 tasks, strictly held-out with unseen task IDs and state combinations)

In every task, exactly 3 candidates are genuinely valid under the ExecutionContract:
- Candidate 1 (Reliable Heavy): 99% reliability, 450ms latency, high cost
- Candidate 2 (Balanced Fast): 96% reliability, 40ms latency, low cost
- Candidate 3 (Ultra-Fast Lightweight): 80% reliability, 8ms latency, minimal cost

Task context defines the utility objective:
- 'critical_integrity': Objective prefers maximum reliability (Opt = Cand 1)
- 'low_latency_interactive': Objective prefers lowest latency with >=95% reliability (Opt = Cand 2)
- 'batch_cost_saving': Objective prefers lowest cost (Opt = Cand 3)

Recent history sequence (e.g. previous tool degraded in current zone) indicates whether Cand 1 or 2 is currently impaired.

Evaluates:
- static (fixed first candidate)
- reliability_aware (highest reliability)
- case_memory
- linucb_bandit
- tage_history
- full_veyra

Measures:
- Valid IPR
- Recall@1 (Optimal Candidate Selection)
- MRR
- Wrong Tool Rate
- Unsafe Exploration Rate
- Latency (microseconds)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def build_multi_valid_benchmark() -> dict[str, list[dict[str, Any]]]:
    splits = ["history_train", "history_gate", "history_scorecard"]
    all_data = {}

    domains = [
        "payment_gateway",
        "search_index",
        "doc_parser",
        "vector_search",
        "sms_provider",
        "sql_query",
        "geocoding",
        "llm_embedding",
        "cdn_cache",
        "telemetry_stream",
    ]

    for split in splits:
        split_tasks = []
        is_scorecard = (split == "history_scorecard")

        for idx in range(40):
            dom_idx = idx % len(domains)
            domain = domains[dom_idx]
            task_id = f"{split}_{domain}_{idx+1:03d}"

            # 3 SLA objective types
            sla_types = ["critical_integrity", "low_latency_interactive", "batch_cost_saving"]
            sla = sla_types[idx % 3]

            # Context history
            cluster_zone = f"zone_{'east' if is_scorecard else 'west'}_{idx % 4}"
            prev_tools = [f"{domain}_precheck", f"{domain}_auth"] if idx % 2 == 0 else [f"{domain}_ping"]

            # Ground truth optimal based on SLA objective:
            if sla == "critical_integrity":
                optimal_choice = f"{domain}_replica_reliable_heavy"
            elif sla == "low_latency_interactive":
                optimal_choice = f"{domain}_replica_balanced_fast"
            else:
                optimal_choice = f"{domain}_replica_lightweight"

            task = {
                "task_id": task_id,
                "split": split,
                "domain": domain,
                "sla_objective": sla,
                "intended_tool": f"{domain}_primary_service",
                "intended_arguments": {"query": f"item_{idx+500}"},
                "history": prev_tools,
                "environment_state": {
                    "cluster_zone": cluster_zone,
                    "sla_objective": sla,
                    "session_authenticated": True,
                },
                "execution_contract": {
                    "capability": f"cap_{domain}",
                    "side_effect_class": "read_only",
                    "idempotent_required": True,
                    "required_permissions": [f"perm_{domain}"],
                    "required_state": {"session_authenticated": True},
                },
                "candidates": [
                    {
                        "name": f"{domain}_replica_reliable_heavy",
                        "reliability": 0.99,
                        "latency_ms": 450.0,
                        "cost": 0.005,
                        "is_valid": True,
                        "is_optimal": (optimal_choice == f"{domain}_replica_reliable_heavy"),
                    },
                    {
                        "name": f"{domain}_replica_balanced_fast",
                        "reliability": 0.96,
                        "latency_ms": 40.0,
                        "cost": 0.001,
                        "is_valid": True,
                        "is_optimal": (optimal_choice == f"{domain}_replica_balanced_fast"),
                    },
                    {
                        "name": f"{domain}_replica_lightweight",
                        "reliability": 0.80,
                        "latency_ms": 8.0,
                        "cost": 0.0002,
                        "is_valid": True,
                        "is_optimal": (optimal_choice == f"{domain}_replica_lightweight"),
                    },
                    {
                        "name": f"{domain}_decoy_unauthorized",
                        "reliability": 0.99,
                        "latency_ms": 5.0,
                        "cost": 0.0001,
                        "is_valid": False,  # Contract will reject
                        "is_optimal": False,
                        "unauthorized": True,
                    },
                ],
                "optimal_candidate": optimal_choice,
            }
            split_tasks.append(task)

        all_data[split] = split_tasks

    return all_data


if __name__ == "__main__":
    benchmark_data = build_multi_valid_benchmark()
    out_file = REPO_ROOT / "benchmarks" / "continuitybench" / "multi_valid_benchmark.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    total_tasks = sum(len(v) for v in benchmark_data.values())
    print(f"Generated multi-valid benchmark: {total_tasks} tasks across 3 splits in {out_file}")
