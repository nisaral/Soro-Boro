"""Add multi-intent, sequential, and __done__ rows to the existing Soro jsonl files.

Reads the current train and val files. Does not download Toucan or ToolACE.
Those can be converted later into the same record shape and dropped in
data/soro_kev_dataset/external_intent.jsonl, which this script also appends
when the file exists.

Each new row has intent in {single, multi, none}. Sequential rows put the
first tool result in the state and label the next tool, or __done__.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "soro_kev_dataset"

CONNECTORS = (
    "and then",
    "after that",
    "once that finishes",
    "and also",
    "and if that works",
)
HARD_SINGLE = (
    "Search for salt and pepper grinders.",
    "Book a table for me and my friend.",
    "Show the status of order ORD-14.",
)


def load(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def tool_of(row: dict) -> tuple[str, str]:
    q = row["questions"]["tool_route"]
    label = q["label"]
    if label in q["criteria"]:
        return label, q["criteria"][label]
    for key, spec in q["criteria"].items():
        if key != "__abstain__":
            return key, spec
    return "__abstain__", "None of the listed tools fit."


def clone(row: dict, state: str, label: str, intent: str, extra: dict | None = None) -> dict:
    out = json.loads(json.dumps(row))
    out["intent"] = intent
    out["state"] = state
    criteria = dict(out["questions"]["tool_route"]["criteria"])
    if label not in criteria:
        criteria[label] = "The task is finished. Do not call another tool."
    out["questions"]["tool_route"]["criteria"] = criteria
    out["questions"]["tool_route"]["label"] = label
    out["questions"]["tool_route_perm"]["criteria"] = criteria
    out["questions"]["tool_route_perm"]["label"] = label
    if extra:
        out.update(extra)
    return out


def build(rows: list[dict], n_multi: int, n_seq: int, n_done: int, n_hard: int, rng: random.Random) -> list[dict]:
    usable = [r for r in rows if r["questions"]["tool_route"]["label"] != "__abstain__"]
    if len(usable) < 2:
        return []
    made = []
    for i in range(n_multi):
        a, b = rng.sample(usable, 2)
        ka, sa = tool_of(a)
        kb, sb = tool_of(b)
        if ka == kb:
            continue
        qa = a["state"].replace("User Request: ", "")
        qb = b["state"].replace("User Request: ", "")
        conj = CONNECTORS[i % len(CONNECTORS)]
        state = f"User Request: {qa} {conj} {qb}"
        rec = clone(a, state, ka, "multi", {"id": f"multi_{i}", "intent_pair": [ka, kb]})
        rec["questions"]["tool_route"]["criteria"][kb] = sb
        rec["questions"]["tool_route_perm"]["criteria"][kb] = sb
        made.append(rec)
    for i in range(n_seq):
        a, b = rng.sample(usable, 2)
        ka, _ = tool_of(a)
        kb, sb = tool_of(b)
        if ka == kb:
            continue
        goal = a["state"].replace("User Request: ", "")
        state = (
            f"User Request: {goal}\n"
            f"Prior tool observation: {ka} returned {{\"status\": \"ok\"}}.\n"
            "Do the next required action."
        )
        rec = clone(b, state, kb, "single", {"id": f"seq_{i}", "prior_tool": ka})
        rec["questions"]["tool_route"]["criteria"][kb] = sb
        made.append(rec)
    for i in range(n_done):
        a = rng.choice(usable)
        ka, _ = tool_of(a)
        state = (
            f"{a['state']}\n"
            f"Prior tool observation: {ka} returned {{\"status\": \"ok\"}}.\n"
            "The requested work is finished."
        )
        made.append(clone(a, state, "__done__", "single", {"id": f"done_{i}"}))
    for i, text in enumerate(HARD_SINGLE * (n_hard // max(len(HARD_SINGLE), 1) + 1)):
        if i >= n_hard:
            break
        a = rng.choice(usable)
        made.append(clone(a, f"User Request: {text}", tool_of(a)[0], "single", {"id": f"hard_{i}"}))
    for row in made:
        if row["questions"]["tool_route"]["label"] == "__abstain__":
            row["intent"] = "none"
    return made


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DATA))
    args = parser.parse_args()
    root = Path(args.data_dir)
    rng = random.Random(2026)
    train = load(root / "train.jsonl")
    val = load(root / "val_zeroshot.jsonl")
    for row in train + val:
        row.setdefault("intent", "none" if row["questions"]["tool_route"]["label"] == "__abstain__" else "single")
    extra_train = build(train, 2500, 1500, 800, 400, rng)
    extra_val = build(val, 200, 120, 60, 40, rng)
    ext = root / "external_intent.jsonl"
    if ext.exists():
        extra_train.extend(load(ext))
    out_train = train + extra_train
    out_val = val + extra_val
    rng.shuffle(out_train)
    rng.shuffle(out_val)
    for name, rows in (("train.jsonl", out_train), ("val_zeroshot.jsonl", out_val)):
        path = root / name
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        intents = {}
        for row in rows:
            intents[row.get("intent", "single")] = intents.get(row.get("intent", "single"), 0) + 1
        print(name, len(rows), intents)


if __name__ == "__main__":
    main()
