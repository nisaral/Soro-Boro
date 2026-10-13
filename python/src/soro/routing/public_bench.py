"""Score the authors' cached embeddings with our harness. Offline, no API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[5] / "third_party" / "mcp-semantic-tool-routing-benchmark"

EXPECTED = {"flat_dense_top1": 483, "n": 505, "bm25_top1": 318}


def recall_at_k(pred: np.ndarray, gold: list[int], k: int) -> float:
    hits = sum(1 for i, g in enumerate(gold) if g in pred[i, :k])
    return hits / max(len(gold), 1)


def run_cached_dense() -> dict[str, Any]:
    import faiss

    q = np.load(ROOT / "data" / "cache" / "benchmark_query_vectors_9d876b0b187348ce.npy")
    index = faiss.read_index(str(ROOT / "data" / "cache" / "tools.faiss"))
    meta = json.loads((ROOT / "data" / "cache" / "tools_metadata.json").read_text(encoding="utf-8"))
    rows = []
    with (ROOT / "benchmark" / "dataset.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    if q.shape[0] != len(rows):
        raise ValueError(f"query vectors {q.shape[0]} != dataset {len(rows)}")
    op_to_row = {}
    for i in range(index.ntotal):
        op_to_row[meta[str(i)]["operation_id"]] = i
    gold = [op_to_row[r["expected_operation"]] for r in rows]
    scores, idxs = index.search(q.astype(np.float32), 20)
    pred = idxs
    n = len(rows)
    top1 = sum(1 for i, g in enumerate(gold) if g == pred[i, 0])
    return {
        "status": "ok",
        "n": n,
        "source": "authors cached gemini-embedding-001 + FAISS inner_product",
        "recall@1": round(top1 / n, 6),
        "recall@1_count": top1,
        "recall@5": round(recall_at_k(pred, gold, 5), 6),
        "recall@10": round(recall_at_k(pred, gold, 10), 6),
        "recall@20": round(recall_at_k(pred, gold, 20), 6),
        "paper_table1_flat_top1_count": EXPECTED["flat_dense_top1"],
        "delta_vs_paper_top1_count": top1 - EXPECTED["flat_dense_top1"],
        "match_paper": top1 == EXPECTED["flat_dense_top1"],
    }


def mcnemar(a_hits: list[int], b_hits: list[int]) -> dict[str, Any]:
    b = sum(1 for x, y in zip(a_hits, b_hits) if x and not y)
    c = sum(1 for x, y in zip(a_hits, b_hits) if y and not x)
    n_disc = b + c
    if n_disc == 0:
        p = 1.0
        chi2 = 0.0
    else:
        chi2 = (abs(b - c) - 1) ** 2 / n_disc  # continuity correction
        # two-sided exact binomial on min(b,c)
        from math import comb

        k = min(b, c)
        p = min(1.0, 2 * sum(comb(n_disc, i) for i in range(k + 1)) / (2 ** n_disc))
    return {"b_a_correct_b_wrong": b, "c_b_correct_a_wrong": c, "chi2_cc": round(chi2, 4), "exact_p_approx": round(p, 6)}
