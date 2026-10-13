"""Unique-gold tool catalog. Each tool owns a private token that appears in no other description."""

from __future__ import annotations

import random
from dataclasses import dataclass

from soro.routing.scale import ToolSpec

VERBS = [
    ("charge", "Charge a card for"),
    ("refund", "Refund payment on"),
    ("capture", "Capture authorized hold for"),
    ("void", "Void authorization on"),
    ("lookup", "Look up record"),
    ("close", "Close ticket"),
    ("rename", "Rename file"),
    ("merge", "Merge pull request"),
]


@dataclass
class GoldQuery:
    text: str
    gold: str
    unique_token: str
    kind: str  # "easy" | "hard_negative"


def build_unique_catalog(n: int, *, opaque: bool = False, poison_index: int | None = None, poison_phrase: str = "") -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for i in range(n):
        verb, lead = VERBS[i % len(VERBS)]
        token = f"ZXQ{i:04d}"
        public = f"{verb}_{token.lower()}"
        name = f"tool_{i:04d}" if opaque else public
        desc = f"{lead} entity {token}. Unique handle {token} only."
        if poison_index is not None and i == poison_index:
            desc = poison_phrase + " " + desc
        specs.append(
            ToolSpec(
                name=name,
                description=desc,
                protocol=("python", "mcp", "http")[i % 3],
                side_effect_class="read_only" if verb in {"lookup"} else "non_idempotent_mutation",
            )
        )
    return specs


def make_queries(specs: list[ToolSpec], rng: random.Random, hard_negative_frac: float = 0.25) -> list[GoldQuery]:
    queries: list[GoldQuery] = []
    tokens = []
    for spec in specs:
        tok = _token(spec)
        tokens.append((spec, tok))
        queries.append(GoldQuery(text=f"Please {spec.name.replace('_', ' ')} for {tok}", gold=spec.name, unique_token=tok, kind="easy"))
        queries.append(GoldQuery(text=f"Operate on unique handle {tok}", gold=spec.name, unique_token=tok, kind="easy"))
    n_hard = int(len(specs) * hard_negative_frac)
    for spec, tok in tokens[:n_hard]:
        # same entity, a different verb that exists in the catalog
        others = [s for s, _ in tokens if s.name != spec.name]
        if not others:
            continue
        distractor = rng.choice(others)
        queries.append(
            GoldQuery(
                text=f"{_verb(distractor)} the record whose unique handle is {tok}",
                gold=spec.name,
                unique_token=tok,
                kind="hard_negative",
            )
        )
    rng.shuffle(queries)
    return queries


def oracle_ceiling(specs: list[ToolSpec], queries: list[GoldQuery]) -> dict:
    """Share of queries whose unique token occurs in exactly one tool description/name."""
    sole = 0
    multi = 0
    none = 0
    for q in queries:
        hits = [s.name for s in specs if q.unique_token in s.name or q.unique_token in s.description]
        if len(hits) == 1 and hits[0] == q.gold:
            sole += 1
        elif len(hits) == 0:
            none += 1
        else:
            multi += 1
    n = max(len(queries), 1)
    return {
        "n": len(queries),
        "unique_gold": round(sole / n, 4),
        "multi_match": round(multi / n, 4),
        "no_match": round(none / n, 4),
        "oracle_ceiling": round(sole / n, 4),
    }


def _token(spec: ToolSpec) -> str:
    for part in spec.description.replace(".", " ").split():
        if part.startswith("ZXQ"):
            return part
    return spec.name


def _verb(spec: ToolSpec) -> str:
    return spec.name.split("_")[0]
