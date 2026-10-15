"""Next-wave eval: public MiniLM, expanded docs on v2, 5-fold margin, non-oracle poison, optional Kev."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

from soro.routing.encoders import MiniLMEncoder
from soro.routing.eval_v1 import _summarize
from soro.routing.eval_v2 import _as_query_objs, _rank_bm25, _rank_encoder, load_frozen
from soro.routing.expand import expand_document
from soro.routing.fold_calib import five_fold_margin
from soro.routing.poison_defenses import run_poison_with_defenses
from soro.routing.public_bench import mcnemar
from soro.routing.public_encoders import run_public_local_encoders
from soro.routing.scale import ToolSpec

OUT = Path(__file__).resolve().parents[4] / "reports" / "routing_next.json"


def _expanded_specs(specs: list[ToolSpec]) -> list[ToolSpec]:
    return [ToolSpec(name=s.name, description=expand_document(s), protocol=s.protocol) for s in specs]


def run_kev_block(specs, queries, mini_lists, k: int = 8) -> dict[str, Any]:
    from soro.routing.kev_local import LocalKevScorer

    scorer = LocalKevScorer()
    golds = [q["gold"] for q in queries]
    in_sl = []
    hits = []
    cond_hits = []
    flips = 0
    perm_n = 0
    t0 = time.perf_counter()
    rng = random.Random(0)
    for q, row, gold in zip(queries, mini_lists, golds):
        short = [n for n, _ in row[:k]]
        gold_in = gold in short
        in_sl.append(int(gold_in))
        opts = {n: next(s.description for s in specs if s.name == n) for n in short}
        probs = scorer.probabilities(q["text"], opts)
        top = max(probs, key=probs.get) if probs else ""
        hits.append(int(top == gold))
        if gold_in:
            cond_hits.append(int(top == gold))
        keys = list(opts)
        rng.shuffle(keys)
        shuffled = {k2: opts[k2] for k2 in keys}
        p2 = scorer.probabilities(q["text"], shuffled)
        t2 = max(p2, key=p2.get) if p2 else ""
        perm_n += 1
        if t2 != top:
            flips += 1
    ms = (time.perf_counter() - t0) * 1000 / max(len(queries), 1)
    mini_top = [int(row[0][0] == g) for row, g in zip(mini_lists, golds)]
    return {
        "n": len(queries),
        "k": k,
        "unconditional_r1": round(sum(hits) / max(len(hits), 1), 4),
        "shortlist_contains_gold": round(sum(in_sl) / max(len(in_sl), 1), 4),
        "r1_given_gold_in_shortlist": round(sum(cond_hits) / max(len(cond_hits), 1), 4),
        "minilm_top1": round(sum(mini_top) / max(len(mini_top), 1), 4),
        "mcnemar_vs_minilm_top1": mcnemar(hits, mini_top),
        "option_order_flip_rate": round(flips / max(perm_n, 1), 4),
        "perm_comparisons": perm_n,
        "ms_per_query": round(ms, 1),
        "hot_path": ms <= 100,
    }


def run_next() -> dict[str, Any]:
    public = run_public_local_encoders()
    specs, queries, _ = load_frozen()
    texts = [q["text"] for q in queries]
    qobjs = _as_query_objs(queries)
    mini = MiniLMEncoder()
    plain, _ = _rank_encoder(mini, specs, texts)
    expanded, _ = _rank_encoder(mini, _expanded_specs(specs), texts)
    bm25 = _rank_bm25(specs, texts)
    golds = [q["gold"] for q in queries]
    mini_hits = [int(row[0][0] == g) for row, g in zip(plain, golds)]
    exp_hits = [int(row[0][0] == g) for row, g in zip(expanded, golds)]
    margins = []
    correct = []
    for row, g in zip(plain, golds):
        m = row[0][1] - (row[1][1] if len(row) > 1 else 0.0)
        margins.append(m)
        correct.append(row[0][0] == g)
    report: dict[str, Any] = {
        "public_505_local_encoders": {k: v for k, v in public.items() if k != "minilm_vs_hash_mcnemar"}
        | {"minilm_vs_hash_mcnemar": public.get("minilm_vs_hash_mcnemar")},
        "v2_document_expansion": {
            "minilm_plain": {k: v for k, v in _summarize(plain, qobjs).items() if k != "hits_r1"},
            "minilm_expanded": {k: v for k, v in _summarize(expanded, qobjs).items() if k != "hits_r1"},
            "mcnemar_expanded_vs_plain": mcnemar(exp_hits, mini_hits),
            "provenance": "synthetic_examples from name/description templates; not test queries",
        },
        "five_fold_margin": {
            "p90": five_fold_margin(margins, correct, 0.90),
            "p95": five_fold_margin(margins, correct, 0.95),
        },
        "poison_heldout_templates": run_poison_with_defenses(specs, queries, mini),
        "not_done": [
            "bge/e5/gte (not in local HF cache; not downloaded this run unless SORO_DOWNLOAD_ENCODERS=1)",
            "MS MARCO cross-encoder (cached model is NLI)",
            "independent annotator / v2b 300-query two-writer set",
            "Qwen3.5-0.8B-Base TDM zero-shot (separate from Kev)",
            "LiveMCPBench 527-tool catalog",
        ],
    }
    if os.environ.get("SORO_RUN_KEV") == "1":
        report["kev"] = run_kev_block(specs, queries, plain, k=8)
    else:
        report["kev"] = {"status": "set SORO_RUN_KEV=1 to run ~9 min CPU"}
    return report


def write_next(path: Path | None = None) -> dict[str, Any]:
    data = run_next()
    out = path or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    data["written"] = str(out)
    return data
