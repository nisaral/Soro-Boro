"""Result tables, the pre-registered verdict, and honest caveats.

Markdown first, PNG when matplotlib is available.

The report is written so a reader can tell three things apart at a glance:

1. what was measured (success, cost, switches) under a fixed model and tool set;
2. which decision backend actually answered (``bandit-untrained`` and
   ``von-surrogate`` are visible, never implied away);
3. whether the pre-registered claim survived the held-out split.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def aggregate(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    arms: dict[str, dict[str, Any]] = {}
    for r in results:
        row = arms.setdefault(
            r["arm"],
            {"runs": 0, "success": 0, "usd": 0.0, "wall_ms": 0, "actions": 0, "switches": 0, "backends": set()},
        )
        row["runs"] += 1
        row["success"] += 1 if r["status"] == "SUCCEEDED" else 0
        row["usd"] += float(r["usd"])
        row["wall_ms"] += int(r["wall_ms"])
        row["actions"] += int(r["actions"])
        row["switches"] += int(r["switches"])
        for backend in r.get("backends") or []:
            row["backends"].add(backend)
    for row in arms.values():
        n = max(row["runs"], 1)
        row["success_rate"] = row["success"] / n
        row["mean_usd"] = row["usd"] / n
        row["mean_wall_ms"] = row["wall_ms"] / n
        row["mean_actions"] = row["actions"] / n
        row["switches_per_run"] = row["switches"] / n
        row["backends"] = sorted(row["backends"])
    return arms


def pick_best_fixed(results: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Pick the winner among the fixed arms on dev, before the test split is read.

    Success first, then cost, so a tie never silently favours the expensive arm.
    """
    arms = aggregate(results)
    fixed = {name: row for name, row in arms.items() if name.startswith("fixed:")}
    if not fixed:
        return "", {}
    name, row = sorted(fixed.items(), key=lambda kv: (-kv[1]["success_rate"], kv[1]["mean_usd"]))[0]
    return name.split(":", 1)[1], {"arm": name, **{k: v for k, v in row.items() if k != "backends"}}


def verdict(dev_results: list[dict[str, Any]], test_results: list[dict[str, Any]],
            margin_pp: float = 5.0) -> dict[str, Any]:
    """Apply the pre-registered claim to the held-out results.

    Non-inferiority to the *dev-selected* best fixed harness within ``margin_pp``
    percentage points, with lower mean cost. A null result is a result: it is
    reported as NOT SUPPORTED rather than buried.
    """
    harness, dev_best = pick_best_fixed(dev_results)
    arms = aggregate(test_results)
    baseline = arms.get(f"fixed:{harness}", {})
    base_succ = baseline.get("success_rate", 0.0) * 100.0
    base_cost = baseline.get("mean_usd", 0.0)

    rows: list[dict[str, Any]] = []
    for name in sorted(arms):
        if name.startswith("fixed:"):
            continue
        row = arms[name]
        succ = row["success_rate"] * 100.0
        cost = row["mean_usd"]
        rows.append(
            {
                "arm": name,
                "success_pct": succ,
                "mean_usd": cost,
                "cost_cut_pct": (1.0 - cost / base_cost) * 100.0 if base_cost else 0.0,
                "non_inferior": succ >= base_succ - margin_pp,
                "cheaper": cost < base_cost,
                "backends": row["backends"],
            }
        )
    supported = [r["arm"] for r in rows if r["non_inferior"] and r["cheaper"]]
    return {
        "claim": (
            f"On the held-out test split, an adaptive arm is non-inferior to the best fixed "
            f"harness selected on dev (fixed:{harness}) within {margin_pp:.0f} points and has "
            f"lower mean cost per task."
        ),
        "margin_pp": margin_pp,
        "selected_on_dev": harness,
        "dev_best": dev_best,
        "test_baseline": {"arm": f"fixed:{harness}", "success_pct": base_succ, "mean_usd": base_cost},
        "rows": rows,
        "supported": supported,
        "outcome": "SUPPORTED" if supported else "NOT SUPPORTED",
    }


def _backends_table(results: list[dict[str, Any]]) -> list[str]:
    arms = aggregate(results)
    lines = ["## Decision backends observed", "",
             "| arm | backends reported by the kernel |", "|---|---|"]
    for name in sorted(arms):
        lines.append(f"| {name} | {', '.join(arms[name]['backends']) or '(none)'} |")
    lines.append("")
    return lines


def _verdict_block(dev_results: list[dict[str, Any]], test_results: list[dict[str, Any]],
                   margin_pp: float) -> list[str]:
    v = verdict(dev_results, test_results, margin_pp)
    lines = [
        "## Pre-registered verdict",
        "",
        f"- claim: {v['claim']}",
        f"- selected on dev: `fixed:{v['selected_on_dev']}`",
        f"- test baseline: {v['test_baseline']['success_pct']:.1f}% / ${v['test_baseline']['mean_usd']:.4f}",
        f"- outcome: {v['outcome']}",
        "",
        "| arm | test success | mean $ | cost reduction vs fixed | non-inferior | supported |",
        "|---|---:|---:|---:|---|---|",
    ]
    for r in v["rows"]:
        lines.append(
            f"| {r['arm']} | {r['success_pct']:.1f}% | ${r['mean_usd']:.4f} | "
            f"{r['cost_cut_pct']:+.1f}% | {'yes' if r['non_inferior'] else 'no'} | "
            f"{'yes' if (r['non_inferior'] and r['cheaper']) else 'no'} |"
        )
    if not v["supported"]:
        lines += ["", "> The pre-registered hypothesis was **not supported** under this task distribution."]
    lines.append("")
    return lines


def markdown(results: list[dict[str, Any]], meta: dict[str, Any],
             dev_results: list[dict[str, Any]] | None = None) -> str:
    arms = aggregate(results)
    lines = [
        "# Veyra comparison",
        "",
        f"- model: `{meta.get('model_mode', 'offline')}` ({meta.get('model_detail', 'scripted')})",
        f"- split: `{meta.get('split', 'dev')}`  tasks: {meta.get('tasks', '?')}",
        f"- generated: {meta.get('generated', '')}",
        "",
        "| arm | success | mean $ | mean wall ms | mean actions | switches/run |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in sorted(arms, key=lambda a: (-arms[a]["success_rate"], arms[a]["mean_usd"])):
        row = arms[name]
        lines.append(
            f"| {name} | {row['success_rate'] * 100:.1f}% | ${row['mean_usd']:.4f} | "
            f"{row['mean_wall_ms']:.0f} | {row['mean_actions']:.1f} | {row['switches_per_run']:.2f} |"
        )
    lines.append("")
    if meta.get("caveats"):
        lines += ["## Caveats", ""] + [f"- {c}" for c in meta["caveats"]] + [""]
    lines += _backends_table(results)
    if dev_results:
        lines += _verdict_block(dev_results, results, float(meta.get("margin_pp", 5.0)))

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)
    lines += ["## By category", "", "| category | arm | success | mean $ |", "|---|---|---:|---:|"]
    for cat in sorted(by_cat):
        for arm, row in sorted(aggregate(by_cat[cat]).items()):
            lines.append(f"| {cat} | {arm} | {row['success_rate'] * 100:.0f}% | ${row['mean_usd']:.4f} |")
    lines.append("")
    return "\n".join(lines)


def figure(results: list[dict[str, Any]], out_png: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    arms = aggregate(results)
    names = sorted(arms, key=lambda a: arms[a]["mean_usd"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax1.bar(names, [arms[n]["success_rate"] * 100 for n in names], color="#2b6cb0")
    ax1.set_ylabel("task success (%)")
    ax1.set_ylim(0, 105)
    ax1.set_title("Success at fixed model and tools")
    ax2.bar(names, [arms[n]["mean_usd"] for n in names], color="#c05621")
    ax2.set_ylabel("mean cost per task ($)")
    ax2.set_title("Cost of execution")
    for ax in (ax1, ax2):
        ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    return True


def write(results: list[dict[str, Any]], meta: dict[str, Any], out_dir: Path,
          dev_results: list[dict[str, Any]] | None = None) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"meta": meta, "results": results, "aggregate": aggregate(results)}
    v = None
    if dev_results:
        v = verdict(dev_results, results, float(meta.get("margin_pp", 5.0)))
        payload["verdict"] = v
    (out_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md = markdown(results, meta, dev_results)
    (out_dir / "comparison.md").write_text(md, encoding="utf-8")
    paths = {"markdown": str(out_dir / "comparison.md"), "json": str(out_dir / "results.json"),
             "png": "", "verdict": ""}
    if v is not None:
        (out_dir / "verdict.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
        paths["verdict"] = str(out_dir / "verdict.json")
    png_ok = figure(results, out_dir / "comparison.png")
    if png_ok:
        paths["png"] = str(out_dir / "comparison.png")
    return paths
