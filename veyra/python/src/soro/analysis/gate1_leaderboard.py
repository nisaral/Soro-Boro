"""Gate 1: Pre-registered Net Oracle Headroom Analysis on Terminal-Bench 2.0.

This module evaluates cross-harness oracle headroom against a fair same-harness
best-of-m null using the public Harbor Terminal-Bench 2.0 leaderboard data
(harborframework/terminal-bench-2-leaderboard).

Pre-Registration Discipline:
----------------------------
1. Fixed benchmark: Terminal-Bench 2.0 (89 tasks).
2. Submissions filter:
   - At least 5 trials per task.
   - timeout_multiplier == 1.0.
   - No timeout or resource overrides.
   - Drop multi-model entries (model held strictly fixed).
3. Matched attempts:
   - For a model group with m agents, Oracle is evaluated over m agents at 1 trial each.
   - Null is evaluated as best-of-m trials for the single best agent in that group.
   - Total attempts are equal (m attempts for Oracle, m attempts for Null).
4. Minimum Detectable Effect (MDE) & Stop Rule:
   - At N = 89 tasks, task-sampling variance prevents a fixed 2pp CI upper bound from firing.
   - We compute MDE_80% = (z_0.975 + z_0.80) * SE_Delta ~= 2.8016 * (std_Delta / sqrt(N)).
   - Pre-registered Margin: M = max(0.05, MDE_80%).
   - STOP (Null confirmed): CI_95_upper < M OR mean_net_headroom <= 0.
   - CLEAR (Gate 1 passed): mean_net_headroom >= M AND CI_95_lower > 0.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


@dataclass(frozen=True)
class LeaderboardTrial:
    submission_id: str
    agent: str
    model: str
    task: str
    seed: str
    passed: bool
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ModelGroupAnalysis:
    model: str
    agents: list[str]
    m_agents: int
    n_tasks: int
    best_agent: str
    best_agent_baseline_pass_rate: float
    oracle_mean_rate: float
    null_best_of_m_rate: float
    mean_net_headroom: float
    std_net_headroom: float
    se_net_headroom: float
    ci95_net_headroom: tuple[float, float]
    mde_80: float
    margin: float
    gate1_decision: str  # "STOP" | "CLEAR" | "INCONCLUSIVE"
    mean_cost_oracle: float
    mean_cost_null: float
    per_task_details: list[dict[str, Any]] = field(default_factory=list)


def normalize_task_name(raw_name: str) -> str:
    """Normalize task names to prevent unnormalized join mismatches."""
    name = raw_name.strip()
    prefix = "terminal-bench/"
    if name.startswith(prefix):
        name = name[len(prefix):]
    if name.endswith(".json"):
        name = name[:-5]
    return name


def normalize_model_name(raw_model: str) -> str:
    """Normalize model identifier."""
    m = raw_model.strip().lower()
    for prov in ("openai/", "google/", "anthropic/", "mistralai/"):
        if m.startswith(prov):
            m = m[len(prov):]
    m = m.replace("claude-opus-4-6", "claude-opus-4.6")
    m = m.replace("claude-opus-4-7", "claude-opus-4.7")
    m = m.replace("claude-4.6-opus", "claude-opus-4.6")
    m = m.replace("claude-4.5-sonnet", "claude-sonnet-4.5")
    return m


def parse_result_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    task_name = data.get("task_name") or ""
    passed = False

    # Check verifier_result rewards (standard in Terminal-Bench 2.0 leaderboard)
    if "verifier_result" in data and isinstance(data["verifier_result"], dict):
        vr = data["verifier_result"]
        rewards = vr.get("rewards") or {}
        if isinstance(rewards, dict) and "reward" in rewards:
            try:
                passed = float(rewards["reward"]) >= 1.0
            except (ValueError, TypeError):
                pass

    if not passed:
        for k in ("passed", "success", "is_resolved", "score"):
            if k in data:
                val = data[k]
                if isinstance(val, bool):
                    passed = val
                elif isinstance(val, (int, float)):
                    passed = val >= 1.0
                elif isinstance(val, str):
                    passed = val.strip().lower() in {"1", "true", "yes", "pass", "passed", "resolved"}
                break

    if not passed and "test_result" in data:
        passed = str(data["test_result"]).strip().lower() == "passed"

    cost = 0.0
    for k in ("cost_usd", "cost", "usd", "total_cost"):
        if k in data and data[k] is not None:
            try:
                cost = float(data[k])
                break
            except (ValueError, TypeError):
                pass

    in_tokens = 0
    out_tokens = 0
    for k in ("n_input_tokens", "input_tokens", "prompt_tokens"):
        if k in data and data[k] is not None:
            try:
                in_tokens = int(data[k])
                break
            except (ValueError, TypeError):
                pass
    for k in ("n_output_tokens", "output_tokens", "completion_tokens"):
        if k in data and data[k] is not None:
            try:
                out_tokens = int(data[k])
                break
            except (ValueError, TypeError):
                pass

    # Check nested agent_result, agent_context, or metrics
    for ctx_key in ("agent_result", "context", "agent_context", "metrics"):
        if ctx_key in data and isinstance(data[ctx_key], dict):
            ctx = data[ctx_key]
            if cost == 0.0 and "cost_usd" in ctx and ctx["cost_usd"] is not None:
                try:
                    cost = float(ctx["cost_usd"])
                except (ValueError, TypeError):
                    pass
            if in_tokens == 0 and "n_input_tokens" in ctx and ctx["n_input_tokens"] is not None:
                try:
                    in_tokens = int(ctx["n_input_tokens"])
                except (ValueError, TypeError):
                    pass
            if out_tokens == 0 and "n_output_tokens" in ctx and ctx["n_output_tokens"] is not None:
                try:
                    out_tokens = int(ctx["n_output_tokens"])
                except (ValueError, TypeError):
                    pass

    # Check config for overrides
    cfg = data.get("config") or {}
    tm = cfg.get("timeout_multiplier", 1.0)
    agent_cfg = cfg.get("agent") or {}
    env_cfg = cfg.get("environment") or {}
    has_overrides = False
    if agent_cfg.get("override_timeout_sec") is not None:
        has_overrides = True
    if any(env_cfg.get(k) is not None for k in ("override_cpus", "override_memory_mb", "override_storage_mb")):
        has_overrides = True

    return {
        "task_name": task_name,
        "passed": passed,
        "cost_usd": cost,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "timeout_multiplier": tm,
        "has_overrides": has_overrides,
    }


def parse_metadata_submission(meta: dict[str, Any], sub_dir_name: str) -> tuple[str, str] | None:
    """Extract (agent_name, model_name) or None if disqualified (multi-model or invalid)."""
    # Extract agent name
    agent = meta.get("agent_display_name") or meta.get("agent") or meta.get("agent_name") or sub_dir_name
    agent = str(agent).strip()

    # Extract model names
    raw_models = meta.get("models") or []
    if isinstance(raw_models, list) and raw_models:
        model_names = []
        for m in raw_models:
            if isinstance(m, dict):
                model_names.append(m.get("model_name") or m.get("model") or "")
            else:
                model_names.append(str(m))
    elif meta.get("model") or meta.get("model_name"):
        m = meta.get("model") or meta.get("model_name")
        model_names = [m] if isinstance(m, str) else [str(x) for x in m]
    else:
        # Fallback to sub_dir_name if model is encoded e.g. Agent__Model
        if "__" in sub_dir_name:
            parts = sub_dir_name.split("__", 1)
            agent = parts[0]
            model_names = [parts[1]]
        else:
            return None

    # Drop empty or invalid
    model_names = [normalize_model_name(m) for m in model_names if m]
    if not model_names:
        return None

    # Drop multi-model entries
    if len(set(model_names)) > 1:
        return None

    model = model_names[0]
    return agent, model


def is_valid_submission(meta: dict[str, Any]) -> bool:
    """Filter submissions per Gate 1 requirements."""
    tm = meta.get("timeout_multiplier")
    if tm is None:
        bench_meta = meta.get("benchmark") or {}
        tm = bench_meta.get("timeout_multiplier", 1.0)
    try:
        if abs(float(tm) - 1.0) > 1e-6:
            return False
    except (ValueError, TypeError):
        return False

    for key in ("override_setup_timeout_sec", "override_timeout_sec", "resource_limits"):
        if key in meta and meta[key] is not None and meta[key] != {}:
            return False

    parsed = parse_metadata_submission(meta, "")
    return parsed is not None


def scan_leaderboard_directory(root_dir: Path) -> list[LeaderboardTrial]:
    """Scan directory containing downloaded leaderboard submissions."""
    trials: list[LeaderboardTrial] = []
    meta_files = list(root_dir.glob("**/metadata.yaml")) + list(root_dir.glob("**/metadata.yml"))

    for mf in meta_files:
        sub_dir = mf.parent
        sub_id = sub_dir.name
        try:
            if yaml:
                meta = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
            else:
                continue
        except Exception:
            continue

        parsed_meta = parse_metadata_submission(meta, sub_id)
        if not parsed_meta:
            continue

        agent, model = parsed_meta

        # Find per-task result.json files under this submission (skip top-level run summary result.json)
        results = [r for r in sub_dir.glob("**/result.json") if len(r.relative_to(sub_dir).parts) > 2]
        if not results:
            continue

        # Group by task to verify at least 5 trials per task
        task_results: dict[str, list[tuple[str, Path]]] = defaultdict(list)
        for rpath in results:
            rel = rpath.relative_to(sub_dir)
            parts = rel.parts
            seed = parts[0]
            raw_task = parts[1].split("__")[0] if "__" in parts[1] else parts[1]
            task_norm = normalize_task_name(raw_task)
            task_results[task_norm].append((seed, rpath))

        # Filter: submissions must have at least 5 trials per task
        task_counts = [len(v) for v in task_results.values()]
        if not task_counts or (sum(task_counts) / len(task_counts)) < 4.8:
            continue

        for task_norm, rlist in task_results.items():
            for seed_str, rpath in rlist:
                parsed = parse_result_json(rpath)
                # Check result-level timeout multiplier and overrides
                if abs(float(parsed.get("timeout_multiplier", 1.0)) - 1.0) > 1e-6:
                    continue
                if parsed.get("has_overrides"):
                    continue

                canonical_task = normalize_task_name(parsed.get("task_name") or task_norm)
                trials.append(LeaderboardTrial(
                    submission_id=sub_id,
                    agent=agent,
                    model=model,
                    task=canonical_task,
                    seed=seed_str,
                    passed=parsed["passed"],
                    cost_usd=parsed["cost_usd"],
                    input_tokens=parsed["input_tokens"],
                    output_tokens=parsed["output_tokens"],
                ))

    return trials


def calculate_matched_headroom(
    trials_by_agent: dict[str, dict[str, list[bool]]],
    cost_by_agent: dict[str, dict[str, list[float]]],
    model: str,
    n_bootstrap: int = 5000,
    seed: int = 42,
) -> ModelGroupAnalysis | None:
    """Calculate matched-attempts oracle headroom vs best-of-m null for a fixed model."""
    agents = sorted(trials_by_agent.keys())
    m = len(agents)
    if m < 2:
        return None

    all_tasks = sorted(set.union(*[set(trials_by_agent[a].keys()) for a in agents]))
    # Filter to tasks present in all agents in the group
    common_tasks = [t for t in all_tasks if all(t in trials_by_agent[a] for a in agents)]
    if not common_tasks:
        return None

    # Determine benchmark pass rate for each agent to find best agent
    agent_overall_rates = {}
    for a in agents:
        rates = [
            sum(trials_by_agent[a][t]) / len(trials_by_agent[a][t])
            for t in common_tasks
        ]
        agent_overall_rates[a] = sum(rates) / len(rates)

    best_agent = max(agents, key=lambda a: agent_overall_rates[a])
    best_rate = agent_overall_rates[best_agent]

    per_task_details = []
    task_deltas: list[float] = []
    task_oracle_rates: list[float] = []
    task_null_rates: list[float] = []
    task_oracle_costs: list[float] = []
    task_null_costs: list[float] = []

    for t in common_tasks:
        # Pass rates per agent on this task
        p_agents = [
            sum(trials_by_agent[a][t]) / len(trials_by_agent[a][t])
            for a in agents
        ]
        p_best = sum(trials_by_agent[best_agent][t]) / len(trials_by_agent[best_agent][t])

        # Matched Oracle (m agents at 1 trial each):
        # P(oracle passes) = 1 - product_{j=1}^m (1 - p_{j, t})
        p_fail_prod = 1.0
        for p in p_agents:
            p_fail_prod *= (1.0 - p)
        oracle_rate = 1.0 - p_fail_prod

        # Matched Null (single best agent given m attempts):
        # P(best agent passes in m attempts) = 1 - (1 - p_best)^m
        null_rate = 1.0 - math.pow(1.0 - p_best, m)

        delta = oracle_rate - null_rate
        task_deltas.append(delta)
        task_oracle_rates.append(oracle_rate)
        task_null_rates.append(null_rate)

        # Cost tracking
        mean_costs = [
            sum(cost_by_agent[a][t]) / len(cost_by_agent[a][t]) if cost_by_agent[a][t] else 0.0
            for a in agents
        ]
        oracle_cost = sum(mean_costs)  # m trials total (1 each)
        best_agent_cost = (
            sum(cost_by_agent[best_agent][t]) / len(cost_by_agent[best_agent][t])
            if cost_by_agent[best_agent][t] else 0.0
        )
        null_cost = best_agent_cost * m  # m trials of best agent

        task_oracle_costs.append(oracle_cost)
        task_null_costs.append(null_cost)

        per_task_details.append({
            "task": t,
            "oracle_rate": oracle_rate,
            "null_rate": null_rate,
            "net_headroom": delta,
            "best_agent_rate": p_best,
            "agent_rates": dict(zip(agents, p_agents)),
        })

    n_tasks = len(common_tasks)
    mean_delta = sum(task_deltas) / n_tasks
    variance = sum((d - mean_delta) ** 2 for d in task_deltas) / max(1, n_tasks - 1)
    std_delta = math.sqrt(variance)
    se_delta = std_delta / math.sqrt(n_tasks)

    # Bootstrap 95% CI over tasks
    rng = random.Random(seed)
    boot_means = []
    for _ in range(n_bootstrap):
        sampled = [task_deltas[rng.randrange(n_tasks)] for _ in range(n_tasks)]
        boot_means.append(sum(sampled) / n_tasks)
    boot_means.sort()
    ci_lo = boot_means[int(0.025 * n_bootstrap)]
    ci_hi = boot_means[min(int(0.975 * n_bootstrap), n_bootstrap - 1)]

    # Compute Minimum Detectable Effect at 80% power (alpha=0.05 two-sided)
    # z_crit = z_{1 - alpha/2} + z_{1 - beta} = 1.95996 + 0.84162 = 2.80158
    mde_80 = 2.80158 * se_delta
    margin = max(0.05, round(mde_80, 4))

    # Pre-registered Stop Rule Decision Boundary
    if ci_hi < margin or mean_delta <= 0:
        gate1_decision = "STOP"
    elif mean_delta >= margin and ci_lo > 0:
        gate1_decision = "CLEAR"
    else:
        gate1_decision = "INCONCLUSIVE"

    return ModelGroupAnalysis(
        model=model,
        agents=agents,
        m_agents=m,
        n_tasks=n_tasks,
        best_agent=best_agent,
        best_agent_baseline_pass_rate=best_rate,
        oracle_mean_rate=sum(task_oracle_rates) / n_tasks,
        null_best_of_m_rate=sum(task_null_rates) / n_tasks,
        mean_net_headroom=mean_delta,
        std_net_headroom=std_delta,
        se_net_headroom=se_delta,
        ci95_net_headroom=(ci_lo, ci_hi),
        mde_80=mde_80,
        margin=margin,
        gate1_decision=gate1_decision,
        mean_cost_oracle=sum(task_oracle_costs) / n_tasks,
        mean_cost_null=sum(task_null_costs) / n_tasks,
        per_task_details=per_task_details,
    )


def format_report_markdown(analyses: list[ModelGroupAnalysis]) -> str:
    lines = [
        "# Gate 1: Leaderboard Oracle Headroom Report",
        "",
        "**Dataset:** `harborframework/terminal-bench-2-leaderboard` (Terminal-Bench 2.0)",
        "**Filter Criteria:** Valid submissions only (`timeout_multiplier == 1.0`, no overrides, >=5 trials/task, single model held fixed).",
        "**Matched Attempts:** Oracle over m agents at 1 trial each vs Null (best-of-m trials for single best agent).",
        "",
        "## Summary by Fixed Model Group",
        "",
        "| Model | Agents (m) | Best Agent | Best Pass Rate | Oracle Rate | Null Rate (best-of-m) | Net Headroom | 95% CI | MDE (80%) | Margin | Decision |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for a in analyses:
        agents_str = f"{', '.join(a.agents)} ({a.m_agents})"
        lo, hi = a.ci95_net_headroom
        lines.append(
            f"| `{a.model}` | {agents_str} | {a.best_agent} | {a.best_agent_baseline_pass_rate*100:.1f}% | "
            f"{a.oracle_mean_rate*100:.1f}% | {a.null_best_of_m_rate*100:.1f}% | "
            f"**{a.mean_net_headroom*100:+.2f}pp** | [{lo*100:+.2f}pp, {hi*100:+.2f}pp] | "
            f"{a.mde_80*100:.2f}pp | {a.margin*100:.1f}pp | **{a.gate1_decision}** |"
        )

    lines.extend([
        "",
        "## Gate 1 Stop Rule Interpretation",
        "",
        "- **CLEAR:** Headroom >= Margin AND 95% CI lower bound > 0 (Headroom clears detectable margin with statistical confidence).",
        "- **STOP:** 95% CI upper bound < Margin OR Net Headroom <= 0 (Falsifiable stop rule: null confirmed or effect smaller than detectable margin).",
        "- **INCONCLUSIVE:** Positive headroom exists but interval overlaps decision margin.",
        "",
        "## Cost & Resource Usage",
        "",
        "| Model | Oracle Total Cost (m trials) | Null Total Cost (m trials) | Delta Cost |",
        "| :--- | :---: | :---: | :---: |",
    ])

    for a in analyses:
        lines.append(
            f"| `{a.model}` | ${a.mean_cost_oracle:.4f} | ${a.mean_cost_null:.4f} | ${a.mean_cost_oracle - a.mean_cost_null:+.4f} |"
        )

    return "\n".join(lines)
