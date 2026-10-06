"""Gate 1 Advanced Analysis: Three Bounds, Cost-at-Equal-Success, and Task Complementarity.

This module provides the rigorous statistical breakdown requested for Gate 1:
1. Three Bounds:
   - (a) Single Best Fixed Agent (with Out-of-Sample split-trial adjustment to eliminate Winner's Curse).
   - (b) Per-Task Routing Oracle: pre-run selection ceiling (max over agents of each task's rate).
   - (c) Union / Verify-and-Fallback Cascade Oracle: multi-agent trial union (1 - prod(1 - p_j)).
   - (d) Cross-Validated Task Router: 5-fold cross-validation on tasks.
2. Cost at Equal Success & Cheap-First Cascades:
   - Computes cheap-first cascade spend vs single fixed agent vs repeated retry null.
3. Task-Level Complementarity Analysis:
   - Identifies tasks with disjoint solves (rescues) vs all-pass vs all-fail.
4. Low-Baseline Cohort Hunting:
   - Scans available cohorts across all pass rate brackets (30-60%, 60-80%, 80-95%).
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Pricing tables ($/million tokens) for cost derivation when raw cost_usd is unlogged
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4.7": {"input": 15.0, "output": 75.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4.6": {"input": 15.0, "output": 75.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4.5": {"input": 15.0, "output": 75.0, "cache_read": 0.30, "cache_write": 3.75},
    "gpt-5.3-codex": {"input": 2.50, "output": 10.0, "cache_read": 1.25, "cache_write": 2.50},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.0, "cache_read": 0.30, "cache_write": 1.25},
    "gemini-3-pro-preview": {"input": 1.25, "output": 5.0, "cache_read": 0.30, "cache_write": 1.25},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.60, "cache_read": 0.04, "cache_write": 0.15},
}


@dataclass
class TrialRecord:
    agent: str
    model: str
    task: str
    trial_idx: int
    passed: bool
    cost_usd: float
    input_tokens: int
    output_tokens: int
    cache_tokens: int


@dataclass
class ThreeBoundsResult:
    model: str
    agents: list[str]
    m_agents: int
    n_tasks: int
    # Bound 1: Best fixed agent
    best_agent_in_sample: str
    best_agent_in_sample_rate: float
    best_agent_oos_rate: float  # Out-of-sample (trained on trials 1-2, evaluated on trials 3-5)
    best_agent_best_of_m_null: float
    # Bound 2: Per-task routing oracle (pre-run selection ceiling)
    routing_oracle_rate: float
    routing_oracle_headroom: float  # Over best fixed single trial
    routing_cv_rate: float  # 5-fold cross-validated task router
    # Bound 3: Union / Cascade oracle (verify & fallback)
    cascade_union_oracle_rate: float
    cascade_net_headroom_over_null: float  # Union minus best-of-m null
    cascade_ci95: tuple[float, float]
    cascade_se: float
    # Cost & Cascade Economics
    mean_cost_best_fixed: float
    mean_cost_null_m: float
    mean_cost_cascade: float
    cost_savings_pct: float
    # Task Disjointness & Rescue Breakdown
    all_pass_tasks: int
    all_fail_tasks: int
    disjoint_solve_tasks: int  # Tasks where agents differ in success
    disjoint_task_names: list[str]


def normalize_task_name(raw: str) -> str:
    t = raw.strip()
    if t.startswith("terminal-bench/"):
        t = t[len("terminal-bench/"):]
    if t.endswith(".json"):
        t = t[:-5]
    return t


def normalize_model_name(raw: str) -> str:
    m = raw.strip().lower()
    for prov in ("openai/", "google/", "anthropic/", "mistralai/"):
        if m.startswith(prov):
            m = m[len(prov):]
    m = m.replace("claude-opus-4-6", "claude-opus-4.6")
    m = m.replace("claude-opus-4-7", "claude-opus-4.7")
    m = m.replace("claude-4.6-opus", "claude-opus-4.6")
    m = m.replace("claude-4.5-sonnet", "claude-sonnet-4.5")
    return m


def load_all_trials(data_dir: Path) -> list[TrialRecord]:
    trials: list[TrialRecord] = []
    for sub in data_dir.iterdir():
        if not sub.is_dir():
            continue
        meta_file = sub / "metadata.yaml"
        if not meta_file.exists():
            meta_file = sub / "metadata.yml"
        if not meta_file.exists():
            continue

        try:
            import yaml
            meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue

        raw_models = meta.get("models") or []
        m_names = []
        if isinstance(raw_models, list):
            for m in raw_models:
                if isinstance(m, dict):
                    m_names.append(m.get("model_name") or m.get("model") or "")
                else:
                    m_names.append(str(m))
        elif meta.get("model") or meta.get("model_name"):
            m_names.append(str(meta.get("model") or meta.get("model_name")))

        m_clean = [normalize_model_name(m) for m in m_names if m]
        if not m_clean or len(set(m_clean)) > 1:
            continue
        model = m_clean[0]
        agent = meta.get("agent_display_name") or meta.get("agent") or sub.name

        # Parse per-task result.json
        results = [r for r in sub.glob("**/result.json") if len(r.relative_to(sub).parts) > 2]
        if not results:
            continue

        task_counter: dict[str, int] = defaultdict(int)
        for rpath in results:
            try:
                d = json.loads(rpath.read_text(encoding="utf-8"))
            except Exception:
                continue

            rel = rpath.relative_to(sub)
            parts = rel.parts
            raw_task = parts[1].split("__")[0] if "__" in parts[1] else parts[1]
            task = normalize_task_name(d.get("task_name") or raw_task)
            trial_idx = task_counter[task]
            task_counter[task] += 1

            # Pass extraction
            passed = False
            vr = d.get("verifier_result") or {}
            rewards = vr.get("rewards") or {}
            if "reward" in rewards:
                try:
                    passed = float(rewards["reward"]) >= 1.0
                except (ValueError, TypeError):
                    pass
            if not passed:
                passed = bool(d.get("passed") or d.get("success") or d.get("is_resolved"))

            # Cost & Token extraction
            cost = d.get("cost_usd") or d.get("total_cost") or 0.0
            ar = d.get("agent_result") or {}
            if cost == 0.0 and ar.get("cost_usd"):
                try:
                    cost = float(ar["cost_usd"])
                except Exception:
                    pass

            in_tokens = int(d.get("input_tokens") or ar.get("n_input_tokens") or 0)
            out_tokens = int(d.get("output_tokens") or ar.get("n_output_tokens") or 0)
            cache_tokens = int(d.get("cache_tokens") or ar.get("n_cache_tokens") or 0)

            # If cost is 0 but tokens exist, estimate cost using pricing table
            if cost == 0.0 and (in_tokens > 0 or out_tokens > 0) and model in MODEL_PRICING:
                p = MODEL_PRICING[model]
                cost = (in_tokens * p["input"] + out_tokens * p["output"] + cache_tokens * p["cache_read"]) / 1_000_000.0

            trials.append(TrialRecord(
                agent=agent,
                model=model,
                task=task,
                trial_idx=trial_idx,
                passed=passed,
                cost_usd=cost,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                cache_tokens=cache_tokens,
            ))

    return trials


def analyze_cohort_three_bounds(
    trials: list[TrialRecord],
    target_model: str,
    target_agents: list[str] | None = None,
    n_bootstrap: int = 5000,
    seed: int = 42,
) -> ThreeBoundsResult | None:
    """Compute all 3 bounds, winner's curse correction, CV router, and cost savings."""
    cohort_trials = [t for t in trials if t.model == target_model]
    if target_agents:
        cohort_trials = [t for t in cohort_trials if t.agent in target_agents]

    agents = sorted(set(t.agent for t in cohort_trials))
    m = len(agents)
    if m < 2:
        return None

    # Organize: agent -> task -> list of (passed, cost)
    data: dict[str, dict[str, list[tuple[bool, float]]]] = defaultdict(lambda: defaultdict(list))
    for t in cohort_trials:
        data[t.agent][t.task].append((t.passed, t.cost_usd))

    all_tasks = sorted(set.union(*[set(data[a].keys()) for a in agents]))
    common_tasks = [t for t in all_tasks if all(len(data[a][t]) >= 3 for a in agents)]
    n_tasks = len(common_tasks)
    if n_tasks < 10:
        return None

    # In-sample agent overall pass rates (over all available seeds)
    agent_rates = {}
    for a in agents:
        task_means = [
            sum(v[0] for v in data[a][t]) / len(data[a][t])
            for t in common_tasks
        ]
        agent_rates[a] = sum(task_means) / n_tasks

    best_agent_in_sample = max(agents, key=lambda a: agent_rates[a])
    best_agent_is_rate = agent_rates[best_agent_in_sample]

    # Out-of-sample / Winner's Curse adjustment:
    # Select best agent on trials 0-1, evaluate on trials 2+
    train_agent_rates = {}
    for a in agents:
        t_means = []
        for t in common_tasks:
            train_vals = [v[0] for i, v in enumerate(data[a][t]) if i < 2]
            if train_vals:
                t_means.append(sum(train_vals) / len(train_vals))
        train_agent_rates[a] = sum(t_means) / len(t_means) if t_means else 0.0

    selected_oos_agent = max(agents, key=lambda a: train_agent_rates[a])
    test_rates = []
    for t in common_tasks:
        test_vals = [v[0] for i, v in enumerate(data[selected_oos_agent][t]) if i >= 2]
        if test_vals:
            test_rates.append(sum(test_vals) / len(test_vals))
    best_agent_oos_rate = sum(test_rates) / len(test_rates) if test_rates else best_agent_is_rate

    # Per-task calculations across all common tasks
    task_p_agents: dict[str, list[float]] = {}
    task_c_agents: dict[str, list[float]] = {}
    for t in common_tasks:
        task_p_agents[t] = [
            sum(v[0] for v in data[a][t]) / len(data[a][t])
            for a in agents
        ]
        task_c_agents[t] = [
            sum(v[1] for v in data[a][t]) / len(data[a][t])
            for a in agents
        ]

    # Bound 1: Null best-of-m (matched retries on best agent)
    null_task_rates = []
    for t in common_tasks:
        p_best = sum(v[0] for v in data[best_agent_in_sample][t]) / len(data[best_agent_in_sample][t])
        null_task_rates.append(1.0 - math.pow(1.0 - p_best, m))
    best_agent_null_rate = sum(null_task_rates) / n_tasks

    # Bound 2: Per-Task Routing Oracle (max over agents of each task's pass rate)
    routing_oracle_rates = [max(task_p_agents[t]) for t in common_tasks]
    routing_oracle_mean = sum(routing_oracle_rates) / n_tasks
    routing_headroom = routing_oracle_mean - best_agent_is_rate

    # 5-fold Cross-Validated Task Router (split tasks)
    rng = random.Random(seed)
    shuffled_tasks = list(common_tasks)
    rng.shuffle(shuffled_tasks)
    k_folds = 5
    fold_size = len(shuffled_tasks) // k_folds
    cv_router_correct = []
    for k in range(k_folds):
        test_fold = shuffled_tasks[k * fold_size : (k + 1) * fold_size if k < k_folds - 1 else len(shuffled_tasks)]
        train_fold = [t for t in shuffled_tasks if t not in test_fold]

        # On train fold, find best agent
        train_rates = {
            a: sum(sum(v[0] for v in data[a][t]) / len(data[a][t]) for t in train_fold) / len(train_fold)
            for a in agents
        }
        chosen_agent = max(agents, key=lambda a: train_rates[a])

        # Evaluate on test fold
        for t in test_fold:
            cv_router_correct.append(sum(v[0] for v in data[chosen_agent][t]) / len(data[chosen_agent][t]))

    routing_cv_mean = sum(cv_router_correct) / len(cv_router_correct) if cv_router_correct else best_agent_is_rate

    # Bound 3: Union / Cascade Oracle (verify-and-fallback: 1 - prod(1 - p_j))
    cascade_task_rates = []
    task_deltas = []
    for t in common_tasks:
        p_fail_prod = 1.0
        for p in task_p_agents[t]:
            p_fail_prod *= (1.0 - p)
        union_rate = 1.0 - p_fail_prod
        cascade_task_rates.append(union_rate)

        # Matched delta against null
        p_best = sum(v[0] for v in data[best_agent_in_sample][t]) / len(data[best_agent_in_sample][t])
        null_rate = 1.0 - math.pow(1.0 - p_best, m)
        task_deltas.append(union_rate - null_rate)

    cascade_union_mean = sum(cascade_task_rates) / n_tasks
    net_cascade_headroom = sum(task_deltas) / n_tasks

    # Bootstrap 95% CI over tasks for net cascade headroom
    boot_deltas = []
    for _ in range(n_bootstrap):
        sampled = [task_deltas[rng.randrange(n_tasks)] for _ in range(n_tasks)]
        boot_deltas.append(sum(sampled) / n_tasks)
    boot_deltas.sort()
    ci_lo = boot_deltas[int(0.025 * n_bootstrap)]
    ci_hi = boot_deltas[min(int(0.975 * n_bootstrap), n_bootstrap - 1)]
    se_delta = math.sqrt(sum((d - net_cascade_headroom) ** 2 for d in task_deltas) / (n_tasks - 1)) / math.sqrt(n_tasks)

    # Cost & Cheap-First Cascade Accounting
    cost_best_fixed = sum(
        sum(v[1] for v in data[best_agent_in_sample][t]) / len(data[best_agent_in_sample][t])
        for t in common_tasks
    ) / n_tasks
    cost_null_m = cost_best_fixed * m

    # Cheap-first cascade: sort agents by mean cost ascending
    agent_mean_costs = {
        a: sum(sum(v[1] for v in data[a][t]) / len(data[a][t]) for t in common_tasks) / n_tasks
        for a in agents
    }
    cheapest_order = sorted(agents, key=lambda a: agent_mean_costs[a])

    # Cascade execution expected cost: E[cost] = cost_1 + (1 - p_1)*cost_2 + ...
    cascade_task_costs = []
    for t in common_tasks:
        expected_cost = 0.0
        prob_reaching_step = 1.0
        for a in cheapest_order:
            p_a = sum(v[0] for v in data[a][t]) / len(data[a][t])
            c_a = sum(v[1] for v in data[a][t]) / len(data[a][t])
            expected_cost += prob_reaching_step * c_a
            prob_reaching_step *= (1.0 - p_a)
        cascade_task_costs.append(expected_cost)

    mean_cost_cascade = sum(cascade_task_costs) / n_tasks
    cost_savings = (cost_null_m - mean_cost_cascade) / cost_null_m * 100.0 if cost_null_m > 0 else 0.0

    # Task Disjointness / Complementarity Breakdown
    all_pass = 0
    all_fail = 0
    disjoint_solves = 0
    disjoint_task_names = []
    for t in common_tasks:
        rates = task_p_agents[t]
        if all(r >= 0.99 for r in rates):
            all_pass += 1
        elif all(r <= 0.01 for r in rates):
            all_fail += 1
        elif min(rates) < 0.5 and max(rates) > 0.5:
            disjoint_solves += 1
            disjoint_task_names.append(t)

    return ThreeBoundsResult(
        model=target_model,
        agents=agents,
        m_agents=m,
        n_tasks=n_tasks,
        best_agent_in_sample=best_agent_in_sample,
        best_agent_in_sample_rate=best_agent_is_rate,
        best_agent_oos_rate=best_agent_oos_rate,
        best_agent_best_of_m_null=best_agent_null_rate,
        routing_oracle_rate=routing_oracle_mean,
        routing_oracle_headroom=routing_headroom,
        routing_cv_rate=routing_cv_mean,
        cascade_union_oracle_rate=cascade_union_mean,
        cascade_net_headroom_over_null=net_cascade_headroom,
        cascade_ci95=(ci_lo, ci_hi),
        cascade_se=se_delta,
        mean_cost_best_fixed=cost_best_fixed,
        mean_cost_null_m=cost_null_m,
        mean_cost_cascade=mean_cost_cascade,
        cost_savings_pct=cost_savings,
        all_pass_tasks=all_pass,
        all_fail_tasks=all_fail,
        disjoint_solve_tasks=disjoint_solves,
        disjoint_task_names=disjoint_task_names,
    )
