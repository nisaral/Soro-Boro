"""Gate 1: net oracle headroom with a same-harness null.

Cross-harness oracle: for each task, the best seed across *different* harnesses.
Same-harness null: for each task, the best of k seeds of one harness (mean over
harnesses, or the best fixed harness — both are reported).

Net headroom = cross-harness oracle − same-harness null.

A bootstrap CI on the paired per-task difference is the stop rule. Cost is
mean USD among tasks that both systems solve, plus mean USD over all tasks.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Trial:
    task: str
    harness: str
    seed: str
    passed: bool
    cost: float = 0.0


def load_trials(path: Path) -> list[Trial]:
    rows: list[Trial] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            passed = str(raw.get("pass") or raw.get("passed") or "").strip().lower()
            ok = passed in {"1", "true", "yes", "pass"}
            cost = float(raw.get("cost") or raw.get("usd") or 0 or 0)
            rows.append(Trial(
                task=str(raw["task"]),
                harness=str(raw["harness"]),
                seed=str(raw.get("seed") or "0"),
                passed=ok,
                cost=cost,
            ))
    return rows


def _best_pass(trials: Iterable[Trial]) -> bool:
    return any(t.passed for t in trials)


def per_task_rates(trials: list[Trial]) -> dict[str, dict[str, float]]:
    """For each task: oracle (any harness any seed), null (best mean same-harness)."""
    by_task: dict[str, list[Trial]] = defaultdict(list)
    for t in trials:
        by_task[t.task].append(t)
    out: dict[str, dict[str, float]] = {}
    for task, group in by_task.items():
        by_h: dict[str, list[Trial]] = defaultdict(list)
        for t in group:
            by_h[t.harness].append(t)
        oracle = 1.0 if _best_pass(group) else 0.0
        # Same-harness null: best of k seeds *within* each harness, then the
        # *mean* across harnesses so we do not pick the best harness twice.
        same = [1.0 if _best_pass(hs) else 0.0 for hs in by_h.values()]
        null = sum(same) / len(same) if same else 0.0
        best_fixed = max(same) if same else 0.0
        costs = [t.cost for t in group]
        out[task] = {
            "oracle": oracle,
            "null_mean_same": null,
            "best_fixed": best_fixed,
            "net": oracle - null,
            "net_vs_best_fixed": oracle - best_fixed,
            "mean_cost": sum(costs) / len(costs) if costs else 0.0,
        }
    return out


def bootstrap_mean(values: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    means = []
    k = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(k)] for _ in range(k)]
        means.append(sum(sample) / k)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[min(int(0.975 * n), n - 1)]
    return sum(values) / k, lo, hi


def summarize(trials: list[Trial]) -> dict:
    rates = per_task_rates(trials)
    nets = [r["net"] for r in rates.values()]
    nets_bf = [r["net_vs_best_fixed"] for r in rates.values()]
    mean, lo, hi = bootstrap_mean(nets)
    mean_bf, lo_bf, hi_bf = bootstrap_mean(nets_bf)
    return {
        "n_tasks": len(rates),
        "n_trials": len(trials),
        "net_headroom_mean": mean,
        "net_headroom_ci95": [lo, hi],
        "net_vs_best_fixed_mean": mean_bf,
        "net_vs_best_fixed_ci95": [lo_bf, hi_bf],
        "stop_if_ci_upper_below_pp": 0.02,
        "gate1_stop": hi < 0.02,
        "mean_cost": sum(t.cost for t in trials) / len(trials) if trials else 0.0,
    }


def report_markdown(summary: dict) -> str:
    lo, hi = summary["net_headroom_ci95"]
    stop = "STOP" if summary["gate1_stop"] else "CONTINUE"
    return "\n".join([
        "# Gate 1 headroom",
        "",
        f"tasks: {summary['n_tasks']}  trials: {summary['n_trials']}",
        f"net headroom (oracle - mean same-harness best-of-k): {summary['net_headroom_mean']:.4f}",
        f"95% CI: [{lo:.4f}, {hi:.4f}]",
        f"net vs best fixed harness: {summary['net_vs_best_fixed_mean']:.4f}  CI [{summary['net_vs_best_fixed_ci95'][0]:.4f}, {summary['net_vs_best_fixed_ci95'][1]:.4f}]",
        f"mean cost per trial: ${summary['mean_cost']:.4f}",
        f"stop rule (CI upper bound < 2pp): **{stop}**",
        "",
        "This is not a Terminal-Bench score. It is the Gate 1 statistic on the trials file you passed.",
    ])


def write_report(trials_path: Path, out_path: Path) -> dict:
    trials = load_trials(trials_path)
    summary = summarize(trials)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_markdown(summary) + "\n", encoding="utf-8")
    (out_path.with_suffix(".json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
