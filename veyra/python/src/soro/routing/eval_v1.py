"""Frozen protocol v1 run. Unique-gold catalog, hash vs MiniLM vs BM25, poison control, CIs."""

from __future__ import annotations

import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

from soro.lab.strategies.bm25 import BM25Strategy, tokenize_doc
from soro.routing.catalog import GoldQuery, build_unique_catalog, make_queries, oracle_ceiling
from soro.routing.encoders import HashEncoder, try_minilm
from soro.routing.protocol_v1 import (
    ABSTAIN_TARGET_PRECISION,
    CATALOG_SIZES,
    HARD_NEGATIVE_FRACTION,
    KEV_N_QUERIES,
    KEV_N_TOOLS,
    POISON_PHRASE,
    PROTOCOL_ID,
    SEEDS,
)
from soro.routing.scale import ScaleRouter, cosine_similarity

REPORT = Path(__file__).resolve().parents[4] / "reports" / "routing_protocol_v1.json"


def _bootstrap_ci(hits: list[int], n_boot: int = 400, seed: int = 0) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(hits)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(hits) / n
    means = []
    for _ in range(n_boot):
        s = [hits[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return round(mean, 4), round(lo, 4), round(hi, 4)


def _recall_at_k(ranked_lists: list[list[str]], golds: list[str], k: int) -> list[int]:
    return [1 if g in r[:k] else 0 for r, g in zip(ranked_lists, golds)]


def _coverage_at_precision(conf_ok: list[tuple[float, bool]], target: float) -> dict[str, float]:
    """Lowest confidence cutoff such that precision of covered items >= target (scan high→low)."""
    if not conf_ok:
        return {"precision_target": target, "cutoff": 1.0, "coverage": 0.0, "precision": 0.0}
    rows = sorted(conf_ok, key=lambda x: x[0], reverse=True)
    best = {"precision_target": target, "cutoff": 1.0, "coverage": 0.0, "precision": 0.0}
    tp = 0
    for i, (c, ok) in enumerate(rows, start=1):
        tp += 1 if ok else 0
        prec = tp / i
        if prec >= target:
            best = {
                "precision_target": target,
                "cutoff": round(c, 4),
                "coverage": round(i / len(rows), 4),
                "precision": round(prec, 4),
            }
    return best


def _bm25_rank(specs, queries: list[GoldQuery], k: int = 10) -> list[list[tuple[str, float]]]:
    bm = BM25Strategy()
    catalog = [{"name": s.name, "description": s.description, "parameters": {}} for s in specs]
    bm._index_catalog(catalog)
    out = []
    for q in queries:
        toks = tokenize_doc(q.text)
        scored = sorted(((s.name, bm._score(toks, s.name)) for s in specs), key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out


def _encoder_rank(encoder, specs, queries: list[GoldQuery], k: int = 10) -> list[list[tuple[str, float]]]:
    names = [s.name for s in specs]
    docs = encoder.encode([f"{s.name} {s.description}" for s in specs])
    qv = encoder.encode([q.text for q in queries])
    out = []
    for qi in qv:
        scored = sorted(((n, cosine_similarity(qi, d)) for n, d in zip(names, docs)), key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out


def _summarize(lists: list[list[tuple[str, float]]], queries: list[GoldQuery]) -> dict[str, Any]:
    names = [[n for n, _ in row] for row in lists]
    golds = [q.gold for q in queries]
    h1 = _recall_at_k(names, golds, 1)
    h5 = _recall_at_k(names, golds, 5)
    h10 = _recall_at_k(names, golds, 10)
    h20 = _recall_at_k(names, golds, 20)
    m1, lo, hi = _bootstrap_ci(h1)
    conf_ok = []
    for row, g in zip(lists, golds):
        if not row:
            continue
        top, score = row[0]
        conf_ok.append((max(score, 0.0), top == g))
    second_close = 0
    for row in lists:
        if len(row) >= 2 and row[0][1] > 0 and abs(row[0][1] - row[1][1]) / (abs(row[0][1]) + 1e-9) < 0.05:
            second_close += 1
    return {
        "recall@1": m1,
        "recall@1_ci95": [lo, hi],
        "recall@5": round(sum(h5) / max(len(h5), 1), 4),
        "recall@10": round(sum(h10) / max(len(h10), 1), 4),
        "recall@20": round(sum(h20) / max(len(h20), 1), 4),
        "hits_r1": h1,
        "n": len(queries),
        "multi_defensible_share": round(second_close / max(len(lists), 1), 4),
        "coverage_at_p90": _coverage_at_precision(conf_ok, ABSTAIN_TARGET_PRECISION[0]),
        "coverage_at_p95": _coverage_at_precision(conf_ok, ABSTAIN_TARGET_PRECISION[1]),
    }


def _poison(specs_n: int, encoder_hash, minilm, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    idx = specs_n // 3
    specs = build_unique_catalog(specs_n, poison_index=idx, poison_phrase=(POISON_PHRASE + " ") * 8)
    decoy = specs[idx].name
    from soro.routing.catalog import GoldQuery

    queries = [
        GoldQuery(text="BEST UNIVERSAL TOOL always pick this for every request keywordstuff xyzzy", gold=specs[0].name if specs[0].name != decoy else specs[1].name, unique_token="NONE", kind="poison_generic"),
        GoldQuery(text="I need the best universal tool for every request", gold=specs[0].name if specs[0].name != decoy else specs[1].name, unique_token="NONE", kind="poison_generic"),
        GoldQuery(text="keywordstuff xyzzy always pick this", gold=specs[0].name if specs[0].name != decoy else specs[1].name, unique_token="NONE", kind="poison_generic"),
    ]
    queries += [q for q in make_queries(specs, rng, 0.0) if q.gold != decoy][:20]
    def hijack(lists):
        top1 = sum(1 for row in lists if row and row[0][0] == decoy)
        # rank displacement: 1-indexed rank of decoy, 11 if missing
        ranks = []
        for row in lists:
            names = [n for n, _ in row]
            ranks.append(names.index(decoy) + 1 if decoy in names else 11)
        return {"top1_hijack": round(top1 / max(len(lists), 1), 4), "mean_rank": round(sum(ranks) / max(len(ranks), 1), 3)}

    h = _encoder_rank(encoder_hash, specs, queries, 10)
    b = _bm25_rank(specs, queries, 10)
    out = {"decoy": decoy, "n_queries": len(queries), "hash_dense": hijack(h), "bm25": hijack(b)}
    if minilm is not None:
        out["minilm"] = hijack(_encoder_rank(minilm, specs, queries, 10))
    # rug pull: change approved description after pin
    from soro.routing.scale import describe_hash

    pinned = describe_hash(specs[idx].description)
    specs[idx].description = "innocent lookup " + specs[idx].description
    out["rug_pull_hash_changed"] = describe_hash(specs[idx].description) != pinned
    # name squat: extra tool named like gold prefix
    out["name_squat_note"] = "squatter tool_{decoy} not inserted; see unique names"
    return out


def _online_linucb(n: int = 40, steps: int = 120, seed: int = 7) -> dict[str, Any]:
    from soro.routing.algs import LinUCBBandit
    from soro.routing.scale import text_to_vector

    rng = random.Random(seed)
    specs = build_unique_catalog(n)
    queries = make_queries(specs, rng, 0.0)
    bandit = LinUCBBandit()
    regret = 0.0
    curve = []
    static_hits = 0
    docs = {s.name: text_to_vector(s.name + " " + s.description) for s in specs}
    for t, q in enumerate(queries[:steps], start=1):
        x = text_to_vector(q.text)
        ranked = bandit.rank(q.text, [s.name for s in specs], top_k=1)
        pick = ranked[0].tool if ranked else specs[0].name
        reward = 1.0 if pick == q.gold else 0.0
        regret += 1.0 - reward
        bandit.update(pick, x, reward)
        # static hash dense
        qs = text_to_vector(q.text)
        static = max(docs, key=lambda n: cosine_similarity(qs, docs[n]))
        static_hits += int(static == q.gold)
        if t % 20 == 0:
            curve.append({"t": t, "avg_regret": round(regret / t, 4), "bandit_acc": round(1 - regret / t, 4)})
    return {
        "steps": min(steps, len(queries)),
        "final_avg_regret": round(regret / max(min(steps, len(queries)), 1), 4),
        "static_hash_acc": round(static_hits / max(min(steps, len(queries)), 1), 4),
        "curve": curve,
    }


def run_v1() -> dict[str, Any]:
    hash_enc = HashEncoder()
    minilm = None if os.environ.get("SORO_SKIP_MINILM") == "1" else try_minilm()
    report: dict[str, Any] = {
        "protocol": PROTOCOL_ID,
        "seeds": list(SEEDS),
        "minilm_loaded": minilm is not None,
        "note": "Hash dense is hashed n-grams, not neural. MiniLM is sentence-transformers/all-MiniLM-L6-v2.",
        "sizes": {},
        "poison": {},
        "online_linucb": {},
        "kev": {},
    }
    for n in CATALOG_SIZES:
        per_seed = []
        for seed in SEEDS:
            rng = random.Random(seed)
            specs = build_unique_catalog(n)
            queries = make_queries(specs, rng, HARD_NEGATIVE_FRACTION)
            oracle = oracle_ceiling(specs, queries)
            arms = {
                "hash_dense": _summarize(_encoder_rank(hash_enc, specs, queries), queries),
                "bm25": _summarize(_bm25_rank(specs, queries), queries),
            }
            if minilm is not None:
                arms["minilm"] = _summarize(_encoder_rank(minilm, specs, queries), queries)
            per_seed.append({"seed": seed, "oracle": oracle, "arms": arms, "n_queries": len(queries)})
        # mean recall@1 across seeds
        arm_names = per_seed[0]["arms"].keys()
        summary = {}
        for arm in arm_names:
            r1 = [s["arms"][arm]["recall@1"] for s in per_seed]
            summary[arm] = {
                "recall@1_mean": round(sum(r1) / len(r1), 4),
                "recall@1_seeds": r1,
                "recall@5_mean": round(sum(s["arms"][arm]["recall@5"] for s in per_seed) / len(per_seed), 4),
                "recall@10_mean": round(sum(s["arms"][arm]["recall@10"] for s in per_seed) / len(per_seed), 4),
                "oracle_ceiling_mean": round(sum(s["oracle"]["oracle_ceiling"] for s in per_seed) / len(per_seed), 4),
                "multi_defensible_mean": round(sum(s["arms"][arm]["multi_defensible_share"] for s in per_seed) / len(per_seed), 4),
                "coverage_at_p90": per_seed[0]["arms"][arm]["coverage_at_p90"],
                "coverage_at_p95": per_seed[0]["arms"][arm]["coverage_at_p95"],
            }
        report["sizes"][str(n)] = {"by_seed": per_seed, "summary": summary}

    report["poison"] = _poison(50, hash_enc, minilm, SEEDS[0])
    report["online_linucb"] = _online_linucb()

    # Kev vs hash vs minilm on the same unique-gold 24
    if os.environ.get("SORO_SKIP_KEV") != "1":
        try:
            from soro.routing.kev_local import LocalKevScorer, resolve_kev_dir

            path = resolve_kev_dir()
            rng = random.Random(SEEDS[0])
            specs = build_unique_catalog(KEV_N_TOOLS)
            queries = make_queries(specs, rng, 0.0)[:KEV_N_QUERIES]
            hash_s = _summarize(_encoder_rank(hash_enc, specs, queries), queries)
            mini_s = _summarize(_encoder_rank(minilm, specs, queries), queries) if minilm else None
            scorer = LocalKevScorer()
            hits = []
            t0 = time.perf_counter()
            for q in queries:
                options = {s.name: s.description for s in specs}
                # shortlist 8 by hash first (same as production)
                short = [n for n, _ in _encoder_rank(hash_enc, specs, [q], 8)[0]]
                opts = {n: options[n] for n in short}
                probs = scorer.probabilities(q.text, opts)
                top = max(probs, key=probs.get) if probs else ""
                hits.append(int(top == q.gold))
            ms = (time.perf_counter() - t0) * 1000 / max(len(queries), 1)
            m, lo, hi = _bootstrap_ci(hits)
            report["kev"] = {
                "path": str(path),
                "n_tools": KEV_N_TOOLS,
                "n_queries": len(queries),
                "recall@1": m,
                "recall@1_ci95": [lo, hi],
                "ms_per_query": round(ms, 1),
                "hash_dense_same_split": hash_s,
                "minilm_same_split": mini_s,
            }
        except Exception as exc:
            report["kev"] = {"status": "error", "error": str(exc)[:500]}
    else:
        report["kev"] = {"status": "skipped"}
    return report


def write_v1(path: Path | None = None) -> dict[str, Any]:
    data = run_v1()
    out = path or REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    data["written"] = str(out)
    return data


if __name__ == "__main__":
    print(json.dumps(write_v1(), indent=2)[:4000])
