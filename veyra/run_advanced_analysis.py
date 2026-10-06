import sys
sys.path.insert(0, "python/src")
from pathlib import Path
from veyra.analysis.gate1_advanced import load_all_trials, analyze_cohort_three_bounds

data_dir = Path("data/tb2_leaderboard")
trials = load_all_trials(data_dir)
print(f"Total valid trials loaded: {len(trials)}")

cohorts = [
    # 1. Frontier: GPT-5.3-Codex
    ("gpt-5.3-codex", ["SageAgent", "Droid", "Mux"], "GPT-5.3-Codex Vendor Triplet (Sage, Droid, Mux)"),
    ("gpt-5.3-codex", ["SageAgent", "Droid"], "GPT-5.3-Codex Vendor Pair (Sage, Droid)"),
    ("gpt-5.3-codex", None, "GPT-5.3-Codex (All 6 Agents)"),
    # 2. Frontier: Gemini 3.1 Pro
    ("gemini-3.1-pro-preview", ["TongAgents", "Forge Code"], "Gemini 3.1 Pro Pair (TongAgents + Forge Code)"),
    # 3. Frontier: Claude Opus 4.7
    ("claude-opus-4.7", ["vix", "0error Ledger"], "Claude Opus 4.7 Pair (vix + 0error Ledger)"),
    # 4. Frontier: Claude Opus 4.6
    ("claude-opus-4.6", ["Meta-Harness", "Mux"], "Claude Opus 4.6 Pair (Meta-Harness + Mux)"),
    # 5. Lower Baseline Cohorts (Hunting for 30-60% bracket)
    ("gemini-3-flash-preview", ["Dirac", "Gemini CLI"], "Gemini 3 Flash Preview Pair (Dirac + Gemini CLI)"),
    ("gemini-3-pro-preview", ["Ante", "CodeBrain-1"], "Gemini 3 Pro Preview Pair (Ante + CodeBrain-1)"),
]

for model, agents, label in cohorts:
    res = analyze_cohort_three_bounds(trials, model, agents)
    if not res:
        print(f"Skipping {label}: insufficient common tasks.")
        continue
    print("=" * 80)
    print(f"COHORT: {label}")
    print(f"Model: `{res.model}` | Agents (m={res.m_agents}): {res.agents} | Tasks (N={res.n_tasks})")
    print(f"\n[BOUND 1: Single Best Fixed Agent Baseline]")
    print(f"  • In-Sample Best Agent: {res.best_agent_in_sample} -> {res.best_agent_in_sample_rate*100:.2f}% (1 attempt)")
    print(f"  • Out-of-Sample Best Agent (Seeds 3-5): {res.best_agent_oos_rate*100:.2f}% (Winner's Curse check)")
    print(f"  • Matched Best-of-{res.m_agents} Null: {res.best_agent_best_of_m_null*100:.2f}% ({res.m_agents} attempts on single best agent)")
    print(f"\n[BOUND 2: Per-Task Routing Oracle (Pre-Run Selection)]")
    print(f"  • Routing Oracle Ceiling (1 attempt max per task): {res.routing_oracle_rate*100:.2f}%")
    print(f"  • Routing Oracle Headroom over Best Fixed: +{res.routing_oracle_headroom*100:.2f}pp")
    print(f"  • 5-Fold Cross-Validated Task Router: {res.routing_cv_rate*100:.2f}%")
    print(f"\n[BOUND 3: Verify-and-Fallback Cascade / Union ({res.m_agents} attempts)]")
    print(f"  • Cascade Union Oracle: {res.cascade_union_oracle_rate*100:.2f}%")
    print(f"  • Net Headroom over Matched Null: {res.cascade_net_headroom_over_null*100:+.2f}pp")
    print(f"  • 95% Bootstrap CI: [{res.cascade_ci95[0]*100:+.2f}pp, {res.cascade_ci95[1]*100:+.2f}pp] (SE = {res.cascade_se*100:.2f}pp)")
    print(f"\n[BRANCH A: Cost Economics & Cheap-First Cascade]")
    print(f"  • Single Best Fixed Agent Cost: ${res.mean_cost_best_fixed:.4f} / task")
    print(f"  • Matched Null (Best-of-{res.m_agents}) Cost: ${res.mean_cost_null_m:.4f} / task")
    print(f"  • Cheap-First Cascade Expected Cost: ${res.mean_cost_cascade:.4f} / task")
    print(f"  • Cost Savings at Equal/Superior Success: {res.cost_savings_pct:.1f}% reduction")
    print(f"\n[TASK COMPLEMENTARITY & FAILURE PROFILE]")
    print(f"  • All-Pass Tasks: {res.all_pass_tasks}/{res.n_tasks} ({res.all_pass_tasks/res.n_tasks*100:.1f}%)")
    print(f"  • All-Fail Tasks: {res.all_fail_tasks}/{res.n_tasks} ({res.all_fail_tasks/res.n_tasks*100:.1f}%)")
    print(f"  • Disjoint Solve (Complementary) Tasks: {res.disjoint_solve_tasks}/{res.n_tasks} ({res.disjoint_solve_tasks/res.n_tasks*100:.1f}%)")
    if res.disjoint_task_names:
        print(f"  • Sample complementary tasks ({len(res.disjoint_task_names)} total): {res.disjoint_task_names[:6]}")
