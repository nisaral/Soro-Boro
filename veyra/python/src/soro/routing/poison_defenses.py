"""Non-oracle stuffing + cheap defenses. Stuffing text comes from synthetic_examples, never the test queries."""

from __future__ import annotations

from typing import Any

from soro.routing.eval_v2 import _rank_bm25, _rank_encoder
from soro.routing.expand import synthetic_examples
from soro.routing.scale import ToolSpec


def heldout_stuff_text(specs: list[ToolSpec], decoy: str) -> str:
    chunks = []
    for s in specs:
        if s.name == decoy:
            continue
        chunks.extend(synthetic_examples(s)[:2])
    return " ".join(chunks)[:1500]


def apply_stuff(specs: list[ToolSpec], decoy: str, payload: str) -> list[ToolSpec]:
    out = []
    for s in specs:
        desc = s.description + (" " + payload if s.name == decoy else "")
        out.append(ToolSpec(name=s.name, description=desc, protocol=s.protocol))
    return out


def defense_length(specs: list[ToolSpec]) -> set[str]:
    lens = [len(s.description) for s in specs]
    mean = sum(lens) / max(len(lens), 1)
    var = sum((x - mean) ** 2 for x in lens) / max(len(lens), 1)
    sd = var ** 0.5
    flagged = set()
    for s, L in zip(specs, lens):
        if L > mean + 2 * sd:
            flagged.add(s.name)
    return flagged


def defense_agreement(dense_lists, bm25_lists, decoy: str) -> list[bool]:
    """True if both arms top-1 the decoy (would-be hijack under agreement rule)."""
    out = []
    for d, b in zip(dense_lists, bm25_lists):
        out.append(bool(d and b and d[0][0] == decoy and b[0][0] == decoy))
    return out


def hijack_rate(lists, decoy: str) -> float:
    if not lists:
        return 0.0
    return sum(1 for row in lists if row and row[0][0] == decoy) / len(lists)


def run_poison_with_defenses(specs, queries, minilm, decoy: str = "diceRoll") -> dict[str, Any]:
    payload = heldout_stuff_text(specs, decoy)
    stuffed = apply_stuff(specs, decoy, payload)
    texts = [q["text"] for q in queries if q["gold"] != decoy]
    bm = _rank_bm25(stuffed, texts)
    ml, _ = _rank_encoder(minilm, stuffed, texts)
    clean_ml, _ = _rank_encoder(minilm, specs, texts)
    golds = [q["gold"] for q in queries if q["gold"] != decoy]
    clean_r1 = sum(1 for row, g in zip(clean_ml, golds) if row and row[0][0] == g) / max(len(golds), 1)
    flagged = defense_length(stuffed)
    agree = defense_agreement(ml, bm, decoy)
    # agreement defense: hijack only if both agree
    hijack_agree = sum(agree) / max(len(agree), 1)
    # length defense: ignore decoy if flagged
    def rerank_drop(lists):
        h = 0
        for row in lists:
            top = row[0][0] if row else ""
            if top == decoy and decoy in flagged:
                top = row[1][0] if len(row) > 1 else ""
            if top == decoy:
                h += 1
        return h / max(len(lists), 1)

    # clean recall after dropping flagged tools from consideration
    def recall_drop(lists):
        ok = 0
        for row, g in zip(lists, golds):
            names = [n for n, _ in row if n not in flagged]
            if names and names[0] == g:
                ok += 1
        return ok / max(len(golds), 1)

    return {
        "decoy": decoy,
        "payload_source": "synthetic_examples of other tools (not test queries)",
        "n": len(texts),
        "hijack": {
            "minilm": round(hijack_rate(ml, decoy), 4),
            "bm25": round(hijack_rate(bm, decoy), 4),
            "both_agree": round(hijack_agree, 4),
            "minilm_after_length_flag": round(rerank_drop(ml), 4),
        },
        "length_flagged_decoy": decoy in flagged,
        "clean_minilm_r1": round(clean_r1, 4),
        "clean_minilm_r1_after_length_drop": round(recall_drop(ml), 4),
    }
