"""Zero-Shot Cross-Format Benchmark Suite for Soro-Kev with Split Conformal Calibration.

Evaluates trained Soro-Kev / LocalKevScorer across held-out zero-shot product APIs
in data/soro_kev_dataset/val_zeroshot.jsonl using mathematically sound Split Conformal Calibration:
- Calibration Split (first 300 records): computes exact order-statistic quantile q_hat.
- Test Split (remaining 900 records): evaluates empirical coverage, Wilson 95% CI, and average set size |S|.

Explicitly displays backend identity: [Backend: Neural SoroKevModel (<path>)] vs [Backend: Heuristic Fallback].
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from soro.routing.conformal import conformal_quantile, _wilson
from soro.routing.kev_local import LocalKevScorer

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VAL_DATA = ROOT_DIR / "data" / "soro_kev_dataset" / "val_zeroshot.jsonl"
DEFAULT_REPORT_OUT = ROOT_DIR / "reports" / "soro_kev_zeroshot_benchmark.json"


def calibrate_split(
    cal_records: list[dict[str, Any]],
    scorer: LocalKevScorer,
    alpha: float = 0.10,
) -> tuple[float, float]:
    """Compute exact non-conformity order-statistic quantile on calibration records."""
    nonconf_scores: list[float] = []

    for r in cal_records:
        state = r["state"]
        q_dict = r["questions"]
        route_gold = q_dict["tool_route"]["label"]

        turn_res = scorer.evaluate_turn(state, q_dict)
        route_probs = turn_res.get("probabilities", {}).get("tool_route", {})

        p_gold = float(route_probs.get(route_gold, 0.0))
        # Non-conformity in score-threshold / LAC: 1 - p(gold)
        s_i = 1.0 - p_gold
        nonconf_scores.append(s_i)

    nonconf_arr = np.array(nonconf_scores, dtype=np.float64)
    q_hat = conformal_quantile(nonconf_arr, alpha=alpha)
    # Threshold for inclusion: p >= 1 - q_hat
    threshold = max(0.0, 1.0 - q_hat)
    return q_hat, threshold


def evaluate_test_split(
    test_records: list[dict[str, Any]],
    scorer: LocalKevScorer,
    q_hat: float,
    threshold: float,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Evaluate empirical coverage, set size |S|, and accuracy metrics on test split."""
    n_test = len(test_records)
    if n_test == 0:
        return {}

    correct_route = 0
    flips = 0

    # Format tracking
    by_format: dict[str, dict[str, int]] = {}
    by_delex: dict[str, dict[str, int]] = {
        "delexicalized": {"total": 0, "correct": 0},
        "named": {"total": 0, "correct": 0},
    }

    # Conformal tracking
    conformal_covered = 0
    set_sizes: list[int] = []
    actions_count: dict[str, int] = {"EXECUTE": 0, "ASK": 0, "ABSTAIN": 0}

    # Aux tasks tracking
    arg_correct = 0
    missing_correct = 0
    mut_correct = 0
    aux_totals: dict[str, int] = {"arg": 0, "missing": 0, "mut": 0}

    for r in test_records:
        state = r["state"]
        fmt = r.get("format", "mcp_json")
        is_delex = r.get("delexicalized", False)
        q_dict = r["questions"]

        if fmt not in by_format:
            by_format[fmt] = {"total": 0, "correct": 0}

        by_format[fmt]["total"] += 1
        delex_key = "delexicalized" if is_delex else "named"
        by_delex[delex_key]["total"] += 1

        turn_res = scorer.evaluate_turn(state, q_dict)
        probs_dict = turn_res.get("probabilities", {})
        answers_dict = turn_res.get("answers", {})

        # 1. Tool Route (Top-1 Argmax)
        route_gold = q_dict["tool_route"]["label"]
        route_probs = probs_dict.get("tool_route", {})
        route_choice = answers_dict.get("tool_route") or (
            max(route_probs.keys(), key=lambda k: route_probs[k]) if route_probs else None
        )

        is_route_hit = (route_choice == route_gold)
        if is_route_hit:
            correct_route += 1
            by_format[fmt]["correct"] += 1
            by_delex[delex_key]["correct"] += 1

        # 2. Permutation Flip Rate
        perm_probs = probs_dict.get("tool_route_perm", {})
        perm_choice = answers_dict.get("tool_route_perm") or (
            max(perm_probs.keys(), key=lambda k: perm_probs[k]) if perm_probs else None
        )
        if route_choice != perm_choice:
            flips += 1

        # 3. Exact Split Conformal Prediction Set: S = { c | p(c) >= threshold }
        prediction_set = [cand_k for cand_k, p in route_probs.items() if p >= threshold]
        sz = len(prediction_set)
        set_sizes.append(sz)

        if route_gold in prediction_set:
            conformal_covered += 1

        # Action mapping
        if sz == 1:
            actions_count["EXECUTE"] += 1
        elif 2 <= sz <= 8:
            actions_count["ASK"] += 1
        else:
            actions_count["ABSTAIN"] += 1

        # 4. Arg Mapping
        if "arg_mapping" in q_dict:
            aux_totals["arg"] += 1
            arg_gold = q_dict["arg_mapping"]["label"]
            arg_choice = answers_dict.get("arg_mapping")
            if arg_choice == arg_gold:
                arg_correct += 1

        # 5. Missing Required
        if "missing_required" in q_dict:
            aux_totals["missing"] += 1
            miss_gold = q_dict["missing_required"]["label"]
            miss_choice = answers_dict.get("missing_required")
            if miss_choice == miss_gold:
                missing_correct += 1

        # 6. Is Mutation
        if "is_mutation" in q_dict:
            aux_totals["mut"] += 1
            mut_gold = q_dict["is_mutation"]["label"]
            mut_choice = answers_dict.get("is_mutation")
            if mut_choice == mut_gold:
                mut_correct += 1

    lo_ci, hi_ci = _wilson(conformal_covered, n_test)

    format_summary = {
        fmt: {
            "total": stats["total"],
            "accuracy": round(stats["correct"] / max(stats["total"], 1), 4),
        }
        for fmt, stats in by_format.items()
    }

    report = {
        "backend": scorer.backend_name,
        "n_cal_samples": len(test_records) and 300,
        "n_test_samples": n_test,
        "overall_route_accuracy": round(correct_route / n_test, 4),
        "permutation_flip_rate": round(flips / n_test, 4),
        "by_format": format_summary,
        "by_delexicalized": {
            "delexicalized_accuracy": round(by_delex["delexicalized"]["correct"] / max(by_delex["delexicalized"]["total"], 1), 4),
            "named_accuracy": round(by_delex["named"]["correct"] / max(by_delex["named"]["total"], 1), 4),
        },
        "conformal_calibration": {
            "target_coverage": round(1.0 - alpha, 2),
            "calibrated_q_hat": round(float(q_hat), 4),
            "inclusion_threshold": round(float(threshold), 4),
            "empirical_coverage": round(conformal_covered / n_test, 4),
            "wilson_95_ci": [round(lo_ci, 4), round(hi_ci, 4)],
            "mean_set_size": round(float(np.mean(set_sizes)), 2),
            "median_set_size": float(np.median(set_sizes)),
            "singleton_rate": round(sum(1 for s in set_sizes if s == 1) / n_test, 4),
            "action_distribution": {
                "EXECUTE_share": round(actions_count["EXECUTE"] / n_test, 4),
                "ASK_share": round(actions_count["ASK"] / n_test, 4),
                "ABSTAIN_share": round(actions_count["ABSTAIN"] / n_test, 4),
            },
        },
        "auxiliary_tasks": {
            "arg_mapping_accuracy": round(arg_correct / max(aux_totals["arg"], 1), 4),
            "missing_required_detection_accuracy": round(missing_correct / max(aux_totals["missing"], 1), 4),
            "is_mutation_detection_accuracy": round(mut_correct / max(aux_totals["mut"], 1), 4),
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate Zero-Shot Benchmark for Soro-Kev with Split Conformal Calibration")
    parser.add_argument("--val-data", type=str, default=str(DEFAULT_VAL_DATA))
    parser.add_argument("--output-report", type=str, default=str(DEFAULT_REPORT_OUT))
    parser.add_argument("--alpha", type=float, default=0.10)
    parser.add_argument("--cal-size", type=int, default=300)
    parser.add_argument("--backend", type=str, default="auto", choices=["auto", "neural", "heuristic"])
    parser.add_argument("--checkpoint", type=str, default=None)
    args = parser.parse_args()

    val_path = Path(args.val_data)
    if not val_path.exists():
        raise FileNotFoundError(f"Validation dataset not found at {val_path}. Run build_universal_dataset.py first.")

    val_records = []
    with val_path.open(encoding="utf-8") as f:
        for line in f:
            val_records.append(json.loads(line))

    total_records = len(val_records)
    cal_size = min(args.cal_size, total_records // 4) if total_records < args.cal_size * 2 else args.cal_size
    cal_records = val_records[:cal_size]
    test_records = val_records[cal_size:]

    scorer = LocalKevScorer(run=args.checkpoint, backend=args.backend)

    # Prominent Backend Identification Banner
    print("\n" + "=" * 70)
    print(f" [Backend: {scorer.backend_name}]")
    print("=" * 70)
    print(f"Loaded {total_records} records: Split into {len(cal_records)} Calibration / {len(test_records)} Test records.")

    print(f"Calibrating non-conformity quantile q_hat on {len(cal_records)} calibration records (alpha = {args.alpha:.2f})...")
    q_hat, threshold = calibrate_split(cal_records, scorer, alpha=args.alpha)
    print(f"Calibration Complete: q_hat = {q_hat:.4f} | Inclusion Threshold = {threshold:.4f} (p >= {threshold:.4f})")

    print(f"Evaluating test split across {len(test_records)} records...")
    report = evaluate_test_split(test_records, scorer, q_hat, threshold, alpha=args.alpha)
    report["n_cal_samples"] = len(cal_records)

    # Print clean summary table
    print("\n" + "=" * 70)
    print(f"        SORO-KEV ZERO-SHOT BENCHMARK REPORT: {scorer.backend_name}")
    print("=" * 70)
    print(f"Overall Route Accuracy:       {report['overall_route_accuracy'] * 100:.2f}%")
    print(f"Permutation Flip Rate:        {report['permutation_flip_rate'] * 100:.2f}%")
    print(f"Conformal Empirical Coverage: {report['conformal_calibration']['empirical_coverage'] * 100:.2f}% (Target: {report['conformal_calibration']['target_coverage'] * 100:.0f}%)")
    ci = report['conformal_calibration']['wilson_95_ci']
    print(f"Wilson 95% Confidence Int:    [{ci[0] * 100:.2f}%, {ci[1] * 100:.2f}%]")
    print(f"Average Set Size |S|:         {report['conformal_calibration']['mean_set_size']:.2f} candidates")
    print(f"Singleton Rate (|S|=1):       {report['conformal_calibration']['singleton_rate'] * 100:.2f}%")
    print("-" * 70)
    print("Action Distribution:")
    act = report['conformal_calibration']['action_distribution']
    print(f"  - EXECUTE: {act['EXECUTE_share'] * 100:.2f}% | ASK: {act['ASK_share'] * 100:.2f}% | ABSTAIN: {act['ABSTAIN_share'] * 100:.2f}%")
    print("-" * 70)
    print("Breakdown Across 5 Developer Formats:")
    for fmt, data in report["by_format"].items():
        print(f"  - {fmt:<15} : {data['accuracy'] * 100:.2f}% (N={data['total']})")
    print("-" * 70)
    print("Auxiliary Task Accuracies:")
    print(f"  - Arg Mapping:              {report['auxiliary_tasks']['arg_mapping_accuracy'] * 100:.2f}%")
    print(f"  - Missing Arg Detection:    {report['auxiliary_tasks']['missing_required_detection_accuracy'] * 100:.2f}%")
    print(f"  - Mutation Classification:  {report['auxiliary_tasks']['is_mutation_detection_accuracy'] * 100:.2f}%")
    print("=" * 70 + "\n")

    out_file = Path(args.output_report)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Detailed scorecard saved to: {out_file}")


if __name__ == "__main__":
    main()
