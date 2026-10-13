"""v2 addendum: public cached-embedding score, LinUCB sanity, paired tests, margin calib, QL-poison.

Does not edit frozen v2 query golds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soro.routing.eval_v1 import _coverage_at_precision, _summarize
from soro.routing.eval_v2 import (
    _as_query_objs,
    _hybrid_linucb,
    _rank_bm25,
    _rank_encoder,
    _rank_hybrid,
    load_frozen,
)
from soro.routing.encoders import HashEncoder, try_minilm
from soro.routing.linucb_debug import run_epsilon_greedy, run_linear_sanity, run_thompson
from soro.routing.public_bench import mcnemar, run_cached_dense
from soro.routing.scale import ToolSpec

OUT = Path(__file__).resolve().parents[4] / "reports" / "routing_v2_addendum.json"


def _hits(lists, golds, k=1):
    return [1 if g in [n for n, _ in row[:k]] else 0 for row, g in zip(lists, golds)]


def _margin_rows(lists, golds):
    out = []
    for row, g in zip(lists, golds):
        if not row:
            continue
        m = row[0][1] - (row[1][1] if len(row) > 1 else 0.0)
        out.append((m, row[0][0] == g))
    return out


def _fit_cutoff(dev: list[tuple[float, bool]], target: float) -> float:
    rows = sorted(dev, key=lambda x: x[0], reverse=True)
    best = 1e9
    tp = 0
    for i, (c, ok) in enumerate(rows, start=1):
        tp += int(ok)
        if tp / i >= target:
            best = c
    return best


def _ql_poison(specs, queries, minilm) -> dict[str, Any]:
    decoy_name = "diceRoll"
    stuff = " ".join(q["text"] for q in queries if q["gold"] != decoy_name)[:1200]
    poisoned = []
    for s in specs:
        desc = s.description + (" " + stuff if s.name == decoy_name else "")
        poisoned.append(ToolSpec(name=s.name, description=desc, protocol="mcp"))
    texts = [q["text"] for q in queries if q["gold"] != decoy_name]
    golds = [q["gold"] for q in queries if q["gold"] != decoy_name]

    def hijack(lists):
        h = sum(1 for row in lists if row and row[0][0] == decoy_name)
        return round(h / max(len(lists), 1), 4)

    bm = _rank_bm25(poisoned, texts)
    hsh, _ = _rank_encoder(HashEncoder(), poisoned, texts)
    out = {"attack": "query_likelihood_stuffing", "decoy": decoy_name, "n": len(texts), "bm25": hijack(bm), "hash_dense": hijack(hsh)}
    if minilm:
        ml, _ = _rank_encoder(minilm, poisoned, texts)
        out["minilm"] = hijack(ml)
    return out


def run_addendum() -> dict[str, Any]:
    public = run_cached_dense()
    sanity = {
        "linucb_linear": run_linear_sanity(),
        "eps_greedy": run_epsilon_greedy(),
        "thompson": run_thompson(),
    }
    specs, queries, _ = load_frozen()
    texts = [q["text"] for q in queries]
    golds = [q["gold"] for q in queries]
    qobjs = _as_query_objs(queries)
    minilm = try_minilm()
    bm25 = _rank_bm25(specs, texts)
    hash_r, _ = _rank_encoder(HashEncoder(), specs, texts)
    mini, _ = _rank_encoder(minilm, specs, texts)
    hybrid = _rank_hybrid(mini, bm25)
    arms = {
        "bm25": _summarize(bm25, qobjs),
        "hash_dense": _summarize(hash_r, qobjs),
        "minilm": _summarize(mini, qobjs),
        "hybrid_rrf": _summarize(hybrid, qobjs),
    }
    # strip bulky hits from dump except for tests
    paired = {
        "minilm_vs_bm25": mcnemar(_hits(mini, golds), _hits(bm25, golds)),
        "minilm_vs_hybrid": mcnemar(_hits(mini, golds), _hits(hybrid, golds)),
        "hybrid_vs_bm25": mcnemar(_hits(hybrid, golds), _hits(bm25, golds)),
    }
    # margin calib: first 40 dev, last 40 test (locked split, not shuffled after seeing scores)
    dev_m = _margin_rows(mini[:40], golds[:40])
    test_m = _margin_rows(mini[40:], golds[40:])
    cut90 = _fit_cutoff(dev_m, 0.90)
    cut95 = _fit_cutoff(dev_m, 0.95)
    test_cov = {
        "dev_n": 40,
        "test_n": 40,
        "margin_cutoff_p90": round(cut90, 4),
        "margin_cutoff_p95": round(cut95, 4),
    }
    # proper coverage on test using frozen cutoff
    covered90 = [(m, ok) for m, ok in test_m if m >= cut90]
    covered95 = [(m, ok) for m, ok in test_m if m >= cut95]
    test_cov["test_at_frozen_p90"] = {
        "coverage": round(len(covered90) / 40, 4),
        "precision": round(sum(ok for _, ok in covered90) / max(len(covered90), 1), 4),
    }
    test_cov["test_at_frozen_p95"] = {
        "coverage": round(len(covered95) / 40, 4),
        "precision": round(sum(ok for _, ok in covered95) / max(len(covered95), 1), 4),
    }
    for a in arms.values():
        a.pop("hits_r1", None)
    return {
        "public_cached_embeddings": public,
        "linucb_sanity": sanity,
        "v2_rerun_k20": {k: {kk: vv for kk, vv in v.items() if kk != "hits_r1"} for k, v in arms.items()},
        "paired_mcnemar": paired,
        "margin_calibration": test_cov,
        "query_likelihood_poison": _ql_poison(specs, queries, minilm),
        "linucb_v2_fixed": _hybrid_linucb(mini, bm25, golds),
        "kev": {"status": "run separately; 80 * ~6.6s CPU"},
        "not_done": [
            "independent second annotator (~100 queries)",
            "v2b 300-query set from two writers",
            "bge/e5/gte downloads",
            "cross-encoder rerank (cached model is NLI, not MS MARCO)",
            "held-out-tool contrastive fine-tune",
            "Kev vs Qwen zero-shot on v2 (optional long CPU run)",
        ],
    }


def write_addendum(path: Path | None = None) -> dict[str, Any]:
    data = run_addendum()
    out = path or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    data["written"] = str(out)
    return data
