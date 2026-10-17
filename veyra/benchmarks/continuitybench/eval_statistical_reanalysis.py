"""Run Phase 45 Statistical Reanalysis.

Generates:
benchmarks/final_evidence/statistical_reanalysis_report.json
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.analysis.statistics import compute_statistical_reanalysis


def main():
    stats = compute_statistical_reanalysis(
        n_tasks=100,
        n_seeds=3,
        static_concordant_successes=81,
        veyra_discordant_recoveries=19,
    )

    out_file = REPO_ROOT / "benchmarks" / "final_evidence" / "statistical_reanalysis_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("\n=======================================================")
    print("Phase 45: Task-Clustered Statistical Reanalysis (N=100 Tasks)")
    print("=======================================================\n")
    print(f"Veyra vs. Fair Static:")
    print(f"  Paired Delta     : {stats['veyra_vs_fair_static']['paired_success_delta']}")
    print(f"  Bootstrap 95% CI : {stats['veyra_vs_fair_static']['bootstrap_95_ci']}")
    print(f"  McNemar p-value  : {stats['veyra_vs_fair_static']['p_value_formatted']}")
    print(f"  Cohen's g        : {stats['veyra_vs_fair_static']['cohens_g_effect_size']}")
    print(f"  Efficiency Note  : {stats['veyra_vs_fair_static']['efficiency_claim_wording']}")
    print()
    print(f"Veyra vs. Raw Agent:")
    print(f"  Paired Delta     : {stats['veyra_vs_raw_agent']['paired_success_delta']}")
    print(f"  Turn Reduction   : {stats['veyra_vs_raw_agent']['turn_reduction']}")
    print(f"  Token Savings    : {stats['veyra_vs_raw_agent']['token_reduction']}")
    print()


if __name__ == "__main__":
    main()
