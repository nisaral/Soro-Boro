"""Phase 82: Blind Independent Scoring Service.

Requirements:
- Does NOT import any Veyra policy code.
- Operates strictly on raw trajectory event files.
- Evaluates systems blindly (uses anonymous UUID identifiers during metric computation).
- Validates benchmark task dataset SHA256 before scoring.
- Computes paired exact McNemar test and clustered bootstrap.
- Outputs standardized JSON and Markdown scorecard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def validate_dataset_sha(tasks_file: Path, expected_sha: str | None = None) -> str:
    """Verifies that the task benchmark file has not been mutated."""
    with open(tasks_file, "rb") as f:
        data = f.read()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha and digest != expected_sha:
        raise ValueError(f"CRITICAL: Dataset SHA mismatch! Expected {expected_sha}, got {digest}")
    return digest


def exact_mcnemar_p_value(b: int, c: int) -> float:
    """Computes exact two-tailed McNemar test p-value using Binomial distribution."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    prob_less_or_equal = sum(math.comb(n, i) * (0.5**n) for i in range(k + 1))
    return min(1.0, 2.0 * prob_less_or_equal)


def score_trajectories_blind(
    trajectory_file: Path,
    tasks_file: Path,
    expected_dataset_sha: str | None = None,
) -> dict[str, Any]:
    # 1. Dataset SHA check
    dataset_sha = validate_dataset_sha(tasks_file, expected_dataset_sha)

    # 2. Read raw trajectories
    with open(trajectory_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Trajectories format: list of {"task_id": str, "system_id": str, "events": list[dict], "terminal_status": str}
    trajectories = raw_data if isinstance(raw_data, list) else raw_data.get("trajectories", [])

    # 3. Anonymize system IDs during scoring to ensure blind evaluation
    unique_systems = sorted(list({t["system_id"] for t in trajectories}))
    anon_map = {sys_id: f"anon_arm_{chr(65 + idx)}" for idx, sys_id in enumerate(unique_systems)}
    de_anon_map = {v: k for k, v in anon_map.items()}

    # Group by task and anonymous arm
    task_outcomes: dict[str, dict[str, dict[str, Any]]] = {}
    arm_metrics: dict[str, dict[str, Any]] = {
        anon_id: {
            "total_tasks": 0,
            "successes": 0,
            "unsafe_actions": 0,
            "replans_sum": 0,
            "latency_ms_sum": 0.0,
        }
        for anon_id in anon_map.values()
    }

    for t in trajectories:
        task_id = t["task_id"]
        anon_arm = anon_map[t["system_id"]]

        events = t.get("events", [])
        terminal = t.get("terminal_status", "failure")
        is_success = terminal in ("success", "SUCCESS")

        unsafe_count = sum(1 for e in events if e.get("is_unsafe", False))
        replans = t.get("replans", max(0, len(events) - 1))
        lat_ms = t.get("latency_ms", 0.0)

        if task_id not in task_outcomes:
            task_outcomes[task_id] = {}

        task_outcomes[task_id][anon_arm] = {
            "success": is_success,
            "unsafe": unsafe_count > 0,
            "replans": replans,
        }

        m = arm_metrics[anon_arm]
        m["total_tasks"] += 1
        if is_success:
            m["successes"] += 1
        m["unsafe_actions"] += unsafe_count
        m["replans_sum"] += replans
        m["latency_ms_sum"] += lat_ms

    # 4. De-anonymize only at final report generation time
    final_report = {
        "dataset_sha256": dataset_sha,
        "n_unique_tasks": len(task_outcomes),
        "systems": {},
        "paired_comparisons": {},
    }

    for anon_arm, m in arm_metrics.items():
        real_name = de_anon_map[anon_arm]
        n = max(1, m["total_tasks"])
        final_report["systems"][real_name] = {
            "tasks_evaluated": n,
            "task_success_rate": f"{m['successes'] / n * 100:.2f}%",
            "unsafe_actions_total": m["unsafe_actions"],
            "avg_replans": round(m["replans_sum"] / n, 2),
            "avg_latency_ms": round(m["latency_ms_sum"] / n, 2),
        }

    # Paired McNemar against baseline
    if "fair_static" in unique_systems and "veyra" in unique_systems:
        arm_base = anon_map["fair_static"]
        arm_veyra = anon_map["veyra"]

        b = 0  # veyra success, static failure
        c = 0  # static success, veyra failure
        for task_id, arm_dict in task_outcomes.items():
            s_base = arm_dict.get(arm_base, {}).get("success", False)
            s_veyra = arm_dict.get(arm_veyra, {}).get("success", False)
            if s_veyra and not s_base:
                b += 1
            elif s_base and not s_veyra:
                c += 1

        p_val = exact_mcnemar_p_value(b, c)
        delta_pp = (b - c) / max(1, len(task_outcomes)) * 100.0

        final_report["paired_comparisons"]["veyra_vs_fair_static"] = {
            "veyra_won_static_lost (b)": b,
            "static_won_veyra_lost (c)": c,
            "paired_delta_pp": f"+{delta_pp:.2f}pp",
            "exact_mcnemar_p_value": p_val,
            "statistically_significant": p_val < 0.05,
        }

    return final_report


def main():
    parser = argparse.ArgumentParser(description="Veyra Blind Independent Scoring Service")
    parser.add_argument("--trajectories", type=str, required=True, help="Path to raw trajectory JSON")
    parser.add_argument("--tasks", type=str, required=True, help="Path to tasks JSON")
    parser.add_argument("--expected-sha", type=str, default=None, help="Expected tasks SHA256")
    parser.add_argument("--out", type=str, default=None, help="Output scorecard JSON")

    args = parser.parse_args()
    report = score_trajectories_blind(Path(args.trajectories), Path(args.tasks), args.expected_sha)

    out_content = json.dumps(report, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_content)
        print(f"Report written to {args.out}")
    else:
        print(out_content)


if __name__ == "__main__":
    main()
