"""Protocol v2 runner. Query table and harvest are frozen; this file only scores."""

from __future__ import annotations

import json
import math
import os
import random
import re
import time
from pathlib import Path
from typing import Any

from soro.lab.strategies.bm25 import BM25Strategy, tokenize_doc
from soro.routing.encoders import HashEncoder, try_minilm
from soro.routing.eval_v1 import _bootstrap_ci, _coverage_at_precision, _summarize
from soro.routing.overlap import illegal_overlap
from soro.routing.protocol_v2 import (
    CLUSTERS,
    KEV_K,
    KEV_MAX_P50_MS,
    NAME_SQUAT_PAIRS,
    PREFERENCE_PHRASES,
    PROTOCOL_ID,
    PUBLIC_BENCH_EXPECTED,
    SEEDS,
)
from soro.routing.scale import ToolSpec, cosine_similarity, rrf_fuse, text_to_vector

DATA = Path(__file__).resolve().parent / "data"
REPORT = Path(__file__).resolve().parents[4] / "reports" / "routing_protocol_v2.json"


def load_frozen() -> tuple[list[ToolSpec], list[dict[str, str]], dict[str, str]]:
    harvest = json.loads((DATA / "mcp_tools_harvest.json").read_text(encoding="utf-8"))
    queries = json.loads((DATA / "semantic_hard_queries_v2.json").read_text(encoding="utf-8"))
    gold_b = json.loads((DATA / "annotator_b_v2.json").read_text(encoding="utf-8"))["labels"]
    specs = [ToolSpec(name=t["name"], description=t["description"][:500], protocol="mcp") for t in harvest]
    return specs, queries, gold_b


def validate_frozen(queries: list[dict[str, str]]) -> dict[str, Any]:
    illegal = []
    for q in queries:
        ov = illegal_overlap(q["gold"], q["text"])
        if ov:
            illegal.append({"id": q["id"], "overlap": sorted(ov)})
    missing = []
    golds = {q["gold"] for q in queries}
    for a, b in CLUSTERS:
        ca = sum(1 for q in queries if q["gold"] == a)
        cb = sum(1 for q in queries if q["gold"] == b)
        if ca < 2 or cb < 2:
            missing.append({"cluster": [a, b], "counts": [ca, cb]})
    return {"n_queries": len(queries), "illegal_overlap": illegal, "cluster_gaps": missing}


def agreement(queries, gold_b: dict[str, str]) -> dict[str, Any]:
    n = 0
    agree = 0
    multi = 0
    for q in queries:
        b = gold_b.get(q["id"])
        if not b:
            continue
        n += 1
        if b == q["gold"]:
            agree += 1
        else:
            multi += 1
    return {
        "n": n,
        "raw_agreement": round(agree / max(n, 1), 4),
        "disagreement_share": round(multi / max(n, 1), 4),
        "disagreements": [
            {"id": q["id"], "gold_a": q["gold"], "gold_b": gold_b[q["id"]]}
            for q in queries
            if gold_b.get(q["id"]) and gold_b[q["id"]] != q["gold"]
        ],
    }


def _rank_bm25(specs, texts: list[str], k=20):
    bm = BM25Strategy()
    bm._index_catalog([{"name": s.name, "description": s.description, "parameters": {}} for s in specs])
    out = []
    for t in texts:
        scored = sorted(((s.name, bm._score(tokenize_doc(t), s.name)) for s in specs), key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out


def _rank_encoder(encoder, specs, texts, k=20, cached_docs=None):
    names = [s.name for s in specs]
    docs = cached_docs if cached_docs is not None else encoder.encode([f"{s.name} {s.description}" for s in specs])
    qv = encoder.encode(texts)
    out = []
    for qi in qv:
        scored = sorted(((n, cosine_similarity(qi, d)) for n, d in zip(names, docs)), key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out, docs


def _rank_tfidf(specs, texts, k=20):
    def toks(s):
        return tokenize_doc(s)
    docs = [toks(s.name + " " + s.description) for s in specs]
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

    def vec(tokens):
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        return {t: (tf[t] / max(len(tokens), 1)) * idf.get(t, 0.0) for t in tf}

    dvecs = [vec(d) for d in docs]
    out = []
    for text in texts:
        qv = vec(toks(text))
        scored = []
        for s, dv in zip(specs, dvecs):
            keys = set(qv) | set(dv)
            num = sum(qv.get(t, 0) * dv.get(t, 0) for t in keys)
            nq = math.sqrt(sum(x * x for x in qv.values())) or 1
            nd = math.sqrt(sum(x * x for x in dv.values())) or 1
            scored.append((s.name, num / (nq * nd)))
        scored.sort(key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out


def _rank_hybrid(dense, bm25, k=20):
    out = []
    for d, b in zip(dense, bm25):
        fused = rrf_fuse([[n for n, _ in d], [n for n, _ in b]])
        scored = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        out.append(scored[:k])
    return out


def _as_query_objs(queries):
    class Q:
        def __init__(self, gold, text):
            self.gold = gold
            self.text = text
    return [Q(q["gold"], q["text"]) for q in queries]


def _hybrid_linucb(dense, bm25, golds, alpha=0.3, shortlist=8):
    """Shared theta; UCB over shortlist. Features [1, dense_s, bm25_s, rank]. Updates every step."""
    dim = 4
    A = [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]
    bvec = [0.0] * dim
    updates = 0

    def feat(ds, bs, rank):
        return [1.0, float(ds), float(bs), float(rank)]

    def ucb(x):
        theta = [bvec[i] / max(A[i][i], 1e-6) for i in range(dim)]
        mean = sum(theta[i] * x[i] for i in range(dim))
        var = sum((x[i] * x[i]) / max(A[i][i], 1e-6) for i in range(dim))
        return mean + alpha * math.sqrt(max(var, 0.0))

    def update(x, r):
        nonlocal updates
        updates += 1
        for i in range(dim):
            bvec[i] += r * x[i]
            for j in range(dim):
                A[i][j] += x[i] * x[j]

    static_reg = 0.0
    adapt_reg = 0.0
    curve = []
    for i, (drow, brow, gold) in enumerate(zip(dense, bm25, golds)):
        bm = {n: s for n, s in brow}
        cands = drow[:shortlist]
        scored = []
        for rank, (name, ds) in enumerate(cands):
            x = feat(ds, bm.get(name, 0.0), rank)
            scored.append((ucb(x), name, x))
        scored.sort(key=lambda t: t[0], reverse=True)
        pick, xpick = scored[0][1], scored[0][2]
        if i < 20:
            pick, xpick = cands[0][0], feat(cands[0][1], bm.get(cands[0][0], 0.0), 0)
        dense_pick = cands[0][0] if cands else ""
        static_reg += 0.0 if dense_pick == gold else 1.0
        adapt_reg += 0.0 if pick == gold else 1.0
        update(xpick, 1.0 if pick == gold else 0.0)
        t = i + 1
        if t % 20 == 0:
            curve.append({"t": t, "static_avg_regret": round(static_reg / t, 4), "adapt_avg_regret": round(adapt_reg / t, 4), "updates": updates})
    n = max(len(golds), 1)
    return {"n": n, "updates": updates, "static_avg_regret": round(static_reg / n, 4), "adapt_avg_regret": round(adapt_reg / n, 4), "curve": curve}


def _strip_superlatives(text: str) -> str:
    ban = r"\b(best|always|must|official|recommended|ignore|every request|universal)\b"
    return re.sub(ban, " ", text, flags=re.I)


def _security(specs, queries, minilm):
    from soro.routing.catalog import GoldQuery

    # preference stuffing on a decoy
    decoy = next(s for s in specs if s.name == "diceRoll")
    stuffed = ToolSpec(name=decoy.name, description=" ".join(PREFERENCE_PHRASES) + " " + decoy.description, protocol="mcp")
    others = [s for s in specs if s.name != decoy.name]
    poisoned = others + [stuffed]
    texts = [q["text"] for q in queries if q["gold"] != decoy.name][:40]

    def hijack(lists):
        h = sum(1 for row in lists if row and row[0][0] == decoy.name)
        return round(h / max(len(lists), 1), 4)

    bm = _rank_bm25(poisoned, texts)
    hsh, _ = _rank_encoder(HashEncoder(), poisoned, texts)
    out = {"preference_hijack": {"bm25": hijack(bm), "hash_dense": hijack(hsh)}}
    if minilm:
        ml, _ = _rank_encoder(minilm, poisoned, texts)
        out["preference_hijack"]["minilm"] = hijack(ml)
    # defense: strip then re-score BM25
    cleaned = [ToolSpec(name=s.name, description=_strip_superlatives(s.description), protocol="mcp") for s in poisoned]
    out["preference_hijack_after_strip"] = {"bm25": hijack(_rank_bm25(cleaned, texts))}
    # name squat
    squat_hits = {}
    for gold, fake in NAME_SQUAT_PAIRS:
        if not any(s.name == gold for s in specs):
            continue
        gold_spec = next(s for s in specs if s.name == gold)
        fake_spec = ToolSpec(name=fake, description=gold_spec.description, protocol="mcp")
        cat = specs + [fake_spec]
        qs = [q["text"] for q in queries if q["gold"] == gold]
        if not qs:
            continue
        rows = _rank_bm25(cat, qs)
        squat_hits[f"{gold}->{fake}"] = round(sum(1 for r in rows if r and r[0][0] == fake) / len(rows), 4)
    out["name_squat_bm25_top1"] = squat_hits
    return out


def try_public_bench() -> dict[str, Any]:
    return {
        "status": "skipped",
        "reason": "amrittmishra/mcp-semantic-tool-routing-benchmark not vendored; no network fetch in this run",
        "literature_expected": PUBLIC_BENCH_EXPECTED,
    }


def run_v2() -> dict[str, Any]:
    specs, queries, gold_b = load_frozen()
    gate = validate_frozen(queries)
    if gate["illegal_overlap"] or gate["cluster_gaps"]:
        return {"protocol": PROTOCOL_ID, "status": "refused", "gate": gate}
    texts = [q["text"] for q in queries]
    qobjs = _as_query_objs(queries)
    golds = [q["gold"] for q in queries]
    minilm = None if os.environ.get("SORO_SKIP_MINILM") == "1" else try_minilm()
    t0 = time.perf_counter()
    bm25 = _rank_bm25(specs, texts)
    t_bm25 = (time.perf_counter() - t0) * 1000 / max(len(texts), 1)
    t0 = time.perf_counter()
    hash_r, _ = _rank_encoder(HashEncoder(), specs, texts)
    t_hash = (time.perf_counter() - t0) * 1000 / max(len(texts), 1)
    tfidf = _rank_tfidf(specs, texts)
    mini = None
    t_mini = None
    if minilm:
        t0 = time.perf_counter()
        mini, _ = _rank_encoder(minilm, specs, texts)
        t_mini = (time.perf_counter() - t0) * 1000 / max(len(texts), 1)
    hybrid = _rank_hybrid(mini or hash_r, bm25) if (mini or hash_r) else bm25
    # opaque names: keep descriptions, rename tools
    opaque_map = {s.name: f"tool_{i:04d}" for i, s in enumerate(specs)}
    rev = {v: k for k, v in opaque_map.items()}
    opaque_specs = [ToolSpec(name=opaque_map[s.name], description=s.description, protocol="mcp") for s in specs]
    opaque_q = [{"gold": opaque_map[q["gold"]], "text": q["text"]} for q in queries]
    opaque_bm = _rank_bm25(opaque_specs, texts)
    # map back
    def remap(lists):
        return [[(rev.get(n, n), s) for n, s in row] for row in lists]

    report: dict[str, Any] = {
        "protocol": PROTOCOL_ID,
        "status": "ok",
        "gate": gate,
        "n_tools": len(specs),
        "n_queries": len(queries),
        "annotator_agreement": agreement(queries, gold_b),
        "minilm_loaded": minilm is not None,
        "arms": {
            "bm25": {**_summarize(bm25, qobjs), "p50_ms": round(t_bm25, 3)},
            "hash_dense": {**_summarize(hash_r, qobjs), "p50_ms": round(t_hash, 3)},
            "tfidf_linear": _summarize(tfidf, qobjs),
            "hybrid_rrf": _summarize(hybrid, qobjs),
        },
        "invariance_opaque_bm25_r1": _summarize(remap(opaque_bm), qobjs)["recall@1"],
        "linucb_hybrid": _hybrid_linucb(mini or hash_r, bm25, golds),
        "security": _security(specs, queries, minilm),
        "public_benchmark": try_public_bench(),
        "kev_gate": {
            "status": "not_hot_path",
            "reason": f"CPU Kev p50 was 6590ms in v1; gate is p50<={KEV_MAX_P50_MS}ms and beat MiniLM on hard subset. k={list(KEV_K)}. Skipped unless SORO_RUN_KEV=1.",
        },
    }
    if mini:
        report["arms"]["minilm"] = {**_summarize(mini, qobjs), "p50_ms": round(t_mini or 0, 3)}
    # hard-negative subset = cluster queries
    cluster_ids = {a for pair in CLUSTERS for a in pair}
    hard_idx = [i for i, q in enumerate(queries) if q["gold"] in cluster_ids]
    if hard_idx and mini:
        def subset(lists):
            return [lists[i] for i in hard_idx]
        hq = [qobjs[i] for i in hard_idx]
        report["hard_cluster_subset"] = {
            "n": len(hard_idx),
            "bm25": _summarize(subset(bm25), hq)["recall@1"],
            "minilm": _summarize(subset(mini), hq)["recall@1"],
            "hybrid_rrf": _summarize(subset(hybrid), hq)["recall@1"],
        }
    return report


def write_v2(path: Path | None = None) -> dict[str, Any]:
    data = run_v2()
    out = path or REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    data["written"] = str(out)
    return data


if __name__ == "__main__":
    print(json.dumps(write_v2(), indent=2)[:5000])
