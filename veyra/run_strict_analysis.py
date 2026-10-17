import sys
sys.path.insert(0, "python/src")
from pathlib import Path
from collections import defaultdict
import json
import math
import random
from veyra.analysis.gate1_advanced import load_all_trials, MODEL_PRICING

data_dir = Path("data/tb2_leaderboard")
trials = load_all_trials(data_dir)
print(f"Total valid trials loaded: {len(trials)}")

# We evaluate strictly on N=89 tasks (or N=88 for Gemini Flash where 1 task was missing)
cohort_defs = [
    ("gpt-5.3-codex", ["SageAgent", "Droid", "Mux"], "GPT-5.3-Codex Vendor Triplet (Sage, Droid, Mux)"),
    ("gpt-5.3-codex", ["SageAgent", "Droid"], "GPT-5.3-Codex Vendor Pair (Sage, Droid)"),
    ("gemini-3.1-pro-preview", ["TongAgents", "Forge Code"], "Gemini 3.1 Pro Pair (TongAgents + Forge Code)"),
    ("claude-opus-4.7", ["vix", "0error Ledger"], "Claude Opus 4.7 Pair (vix + 0error Ledger)"),
    ("claude-opus-4.6", ["Meta-Harness", "Mux"], "Claude Opus 4.6 Pair (Meta-Harness + Mux)"),
    ("gemini-3-flash-preview", ["Dirac", "Gemini CLI"], "Gemini 3 Flash Preview Pair (Dirac + Gemini CLI)"),
]

def analyze_cohort_strict(target_model, target_agents, label, n_bootstrap=10000, seed=42):
    cohort_trials = [t for t in trials if t.model == target_model and t.agent in target_agents]
    agents = sorted(set(t.agent for t in cohort_trials))
    m = len(agents)

    # data[agent][task] -> list of (passed, cost)
    data = defaultdict(lambda: defaultdict(list))
    for t in cohort_trials:
        data[t.agent][t.task].append((t.passed, t.cost_usd))

    common_tasks = sorted([
        t for t in set.union(*[set(data[a].keys()) for a in agents])
        if all(len(data[a][t]) >= 3 for a in agents)
    ])
    N = len(common_tasks)

    # 1. Best agent in-sample & out-of-sample
    agent_means_all = {
        a: sum(sum(v[0] for v in data[a][t]) / len(data[a][t]) for t in common_tasks) / N
        for a in agents
    }
    best_agent_is = max(agents, key=lambda a: agent_means_all[a])
    best_agent_is_rate = agent_means_all[best_agent_is]

    # Out-of-sample best agent baseline (train trials 0-1, test trials 2+)
    train_means = {
        a: sum(sum(v[0] for i, v in enumerate(data[a][t]) if i < 2) / max(1, len([v for i, v in enumerate(data[a][t]) if i < 2])) for t in common_tasks) / N
        for a in agents
    }
    best_agent_train = max(agents, key=lambda a: train_means[a])
    test_rates_best_agent = [
        sum(v[0] for i, v in enumerate(data[best_agent_train][t]) if i >= 2) / max(1, len([v for i, v in enumerate(data[best_agent_train][t]) if i >= 2]))
        for t in common_tasks
    ]
    best_agent_oos_rate = sum(test_rates_best_agent) / N

    # 2. SPLIT-HALF ROUTING ORACLE (Pick best agent per task on trials 0-1, evaluate on trials 2+)
    split_half_oracle_test_rates = []
    for t in common_tasks:
        # choose best agent on trials 0-1 for task t
        task_train_p = {}
        for a in agents:
            v_train = [v[0] for i, v in enumerate(data[a][t]) if i < 2]
            task_train_p[a] = sum(v_train) / len(v_train) if v_train else 0.0
        chosen_a = max(agents, key=lambda a: task_train_p[a])

        # score chosen agent on trials 2+
        v_test = [v[0] for i, v in enumerate(data[chosen_a][t]) if i >= 2]
        split_half_oracle_test_rates.append(sum(v_test) / len(v_test) if v_test else 0.0)

    split_half_routing_rate = sum(split_half_oracle_test_rates) / N
    split_half_gain_over_best_fixed = split_half_routing_rate - best_agent_oos_rate

    # In-sample routing oracle (upward biased)
    task_p_all = {
        t: [sum(v[0] for v in data[a][t]) / len(data[a][t]) for a in agents]
        for t in common_tasks
    }
    in_sample_routing_oracle = sum(max(task_p_all[t]) for t in common_tasks) / N

    # 3. Matched Null (best-of-m retries with early stopping) vs Cascade Union
    task_deltas = []
    task_null_rates = []
    task_cascade_rates = []

    # Costs
    cost_per_agent = {
        a: sum(sum(v[1] for v in data[a][t]) / len(data[a][t]) for t in common_tasks) / N
        for a in agents
    }
    cost_best = cost_per_agent[best_agent_is]

    # Fair Early-Stopping Null Cost:
    # E[Cost] = cost_best * sum_{k=0}^{m-1} (1 - p_best)^k
    # Fair Early-Stopping Cascade Cost (cheapest first):
    cheapest_order = sorted(agents, key=lambda a: cost_per_agent[a])

    task_null_expected_costs = []
    task_cascade_expected_costs = []

    for t in common_tasks:
        p_best = sum(v[0] for v in data[best_agent_is][t]) / len(data[best_agent_is][t])
        c_best = sum(v[1] for v in data[best_agent_is][t]) / len(data[best_agent_is][t])

        # Null pass rate & expected cost with early stopping
        null_pass = 1.0 - math.pow(1.0 - p_best, m)
        task_null_rates.append(null_pass)

        # Expected cost of retrying best agent up to m times, stopping on success:
        # Step 1: cost
        # Step 2 (if step 1 failed): (1 - p_best) * cost
        # ... Step m: (1 - p_best)^{m-1} * cost
        expected_null_cost = sum(math.pow(1.0 - p_best, k) * c_best for k in range(m))
        task_null_expected_costs.append(expected_null_cost)

        # Cascade pass rate (union)
        p_fail_prod = 1.0
        for p in task_p_all[t]:
            p_fail_prod *= (1.0 - p)
        union_pass = 1.0 - p_fail_prod
        task_cascade_rates.append(union_pass)

        task_deltas.append(union_pass - null_pass)

        # Expected cost of cascade (cheapest first, stopping on success):
        expected_cascade_cost = 0.0
        prob_reach = 1.0
        for a in cheapest_order:
            p_a = sum(v[0] for v in data[a][t]) / len(data[a][t])
            c_a = sum(v[1] for v in data[a][t]) / len(data[a][t])
            expected_cascade_cost += prob_reach * c_a
            prob_reach *= (1.0 - p_a)
        task_cascade_expected_costs.append(expected_cascade_cost)

    mean_null_rate = sum(task_null_rates) / N
    mean_cascade_rate = sum(task_cascade_rates) / N
    mean_delta = sum(task_deltas) / N

    # Bootstrap CI
    rng = random.Random(seed)
    boot_deltas = []
    for _ in range(n_bootstrap):
        sampled = [task_deltas[rng.randrange(N)] for _ in range(N)]
        boot_deltas.append(sum(sampled) / N)
    boot_deltas.sort()
    ci_lo = boot_deltas[int(0.025 * n_bootstrap)]
    ci_hi = boot_deltas[min(int(0.975 * n_bootstrap), n_bootstrap - 1)]
    se_delta = math.sqrt(sum((d - mean_delta) ** 2 for d in task_deltas) / (N - 1)) / math.sqrt(N)

    # Cost totals
    fair_null_cost = sum(task_null_expected_costs) / N
    fair_cascade_cost = sum(task_cascade_expected_costs) / N
    cost_delta_pct = (fair_cascade_cost - fair_null_cost) / fair_null_cost * 100.0 if fair_null_cost > 0 else 0.0

    print("=" * 80)
    print(f"COHORT: {label} (m={m} agents, N={N} tasks)")
    print(f"Agents: {agents}")
    print(f"1. Single Best Fixed Agent:")
    print(f"   • In-Sample Baseline (1 trial): {best_agent_is} -> {best_agent_is_rate*100:.2f}%")
    print(f"   • Out-of-Sample Baseline (trials 3-5): {best_agent_oos_rate*100:.2f}%")
    print(f"2. Per-Task Routing:")
    print(f"   • In-Sample Routing Oracle (biased): {in_sample_routing_oracle*100:.2f}% (+{in_sample_routing_oracle*100 - best_agent_is_rate*100:+.2f}pp)")
    print(f"   • Split-Half Routing Oracle (unbiased OOS): {split_half_routing_rate*100:.2f}% (Gain over OOS Best: {split_half_gain_over_best_fixed*100:+.2f}pp)")
    print(f"3. Verify-and-Fallback Cascade Union vs Matched Null (m={m} attempts):")
    print(f"   • Matched Null (Best-of-{m} on {best_agent_is}): {mean_null_rate*100:.2f}%")
    print(f"   • Cascade Union ({m} distinct agents): {mean_cascade_rate*100:.2f}%")
    print(f"   • Net Headroom: {mean_delta*100:+.2f}pp (95% CI: [{ci_lo*100:+.2f}pp, {ci_hi*100:+.2f}pp], SE={se_delta*100:.2f}pp)")
    print(f"4. Fair Early-Stopping Cost Accounting (stop at 1st success):")
    print(f"   • Single 1-Trial Cost: ${cost_best:.4f} / task")
    print(f"   • Fair Null Cost (Early-Stopping Best-of-{m}): ${fair_null_cost:.4f} / task")
    print(f"   • Cheap-First Cascade Cost (Early-Stopping): ${fair_cascade_cost:.4f} / task")
    if fair_null_cost > 0:
        if cost_delta_pct < 0:
            print(f"   • Cost Comparison: Cascade saves {-cost_delta_pct:.1f}% vs Early-Stopping Null")
        else:
            print(f"   • Cost Comparison: Cascade costs +{cost_delta_pct:.1f}% more than Early-Stopping Null")

for model, agents, label in cohort_defs:
    analyze_cohort_strict(model, agents, label)
