"""Run local encoders on the public 505-query / 101-op catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from soro.routing.encoders import HashEncoder, MiniLMEncoder
from soro.routing.public_bench import ROOT, mcnemar, recall_at_k
from soro.routing.scale import cosine_similarity


def _load_public() -> tuple[list[str], list[str], list[int], list[str]]:
    tools_json = json.loads((ROOT / "data" / "tools.json").read_text(encoding="utf-8"))
    docs: list[str] = []
    ops: list[str] = []
    for server in tools_json["servers"]:
        for tool in server["tools"]:
            ops.append(tool["operation_id"])
            lines = [
                f"Capability: {tool['name']}",
                "",
                "Taxonomy:",
                f"{tool['taxonomy']['class']} > {tool['taxonomy']['type']} > {tool['operation_id']}",
                "",
                "Purpose:",
                tool["description"],
            ]
            if tool.get("positive_examples"):
                lines += ["", "Typical user requests:"]
                lines += [f"- {e}" for e in tool["positive_examples"]]
            if tool.get("negative_examples"):
                lines += ["", "Do not use this capability for:"]
                lines += [f"- {e}" for e in tool["negative_examples"]]
            docs.append("\n".join(lines))
    rows = []
    with (ROOT / "benchmark" / "dataset.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    op_to_i = {op: i for i, op in enumerate(ops)}
    gold = [op_to_i[r["expected_operation"]] for r in rows]
    queries = [r["query"] for r in rows]
    return docs, queries, gold, ops


def _rank(q_vecs: list[list[float]], d_vecs: list[list[float]], k: int = 20) -> np.ndarray:
    pred = []
    for q in q_vecs:
        scores = [cosine_similarity(q, d) for d in d_vecs]
        order = np.argsort(scores)[::-1][:k]
        pred.append(order)
    return np.array(pred)


def _pack(pred: np.ndarray, gold: list[int], n: int) -> dict[str, Any]:
    hits1 = [1 if gold[i] == pred[i, 0] else 0 for i in range(n)]
    return {
        "recall@1": round(sum(hits1) / n, 6),
        "recall@1_count": int(sum(hits1)),
        "recall@5": round(recall_at_k(pred, gold, 5), 6),
        "recall@10": round(recall_at_k(pred, gold, 10), 6),
        "recall@20": round(recall_at_k(pred, gold, 20), 6),
        "hits_r1": hits1,
    }


def run_public_local_encoders() -> dict[str, Any]:
    docs, queries, gold, _ops = _load_public()
    n = len(queries)
    out: dict[str, Any] = {"n": n, "n_tools": len(docs)}
    hash_enc = HashEncoder()
    h_docs = hash_enc.encode(docs)
    h_q = hash_enc.encode(queries)
    h_pred = _rank(h_q, h_docs)
    out["hash_dense"] = _pack(h_pred, gold, n)
    mini = MiniLMEncoder()
    m_docs = mini.encode(docs)
    m_q = mini.encode(queries)
    m_pred = _rank(m_q, m_docs)
    out["minilm"] = _pack(m_pred, gold, n)
    out["minilm_vs_hash_mcnemar"] = mcnemar(out["minilm"]["hits_r1"], out["hash_dense"]["hits_r1"])
    # drop bulky hits from later dump
    out["minilm"].pop("hits_r1", None)
    out["hash_dense"].pop("hits_r1", None)
    out["note"] = (
        "Same embedding_document layout as the paper (name, taxonomy, purpose, examples). "
        "MiniLM is not gemini-embedding-001; a gap vs 95.6% is an encoder gap."
    )
    return out
