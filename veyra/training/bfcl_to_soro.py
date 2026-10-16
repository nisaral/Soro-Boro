"""Convert official BFCL JSONL into Soro pointer records.

Reads the Berkeley Function-Calling Leaderboard files as published
(gorilla-llm/Berkeley-Function-Calling-Leaderboard). Each row keeps the
human question and the published function schemas. No queries are invented.

Single-function files are copied but flagged trivial: a pointer with one
option cannot be wrong. Routing scores should use the multiple-tool files
and the irrelevance file.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BFCL = ROOT / "data" / "bfcl"
DEFAULT_OUT = ROOT / "data" / "bfcl" / "soro"


def _user_text(question: Any) -> str:
    turns = question or []
    if turns and isinstance(turns[0], list):
        turns = turns[0]
    parts = []
    for turn in turns:
        if isinstance(turn, dict) and turn.get("role") == "user":
            parts.append(str(turn.get("content") or "").strip())
    return "\n".join(p for p in parts if p)


def compact_option_spec(fn: dict[str, Any]) -> str:
    """Dense signature. Keeps every parameter name, type, required mark, enum, and a short description."""
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    required = set(params.get("required") or [])
    bits = []
    for name, info in props.items():
        info = info if isinstance(info, dict) else {}
        typ = str(info.get("type") or "string")
        enum = info.get("enum")
        if enum:
            typ = "|".join(str(x) for x in list(enum)[:6])
        star = "*" if name in required else ""
        default = info.get("default")
        slot = f"{name}: {typ}{star}"
        if default is not None and name not in required:
            slot += f"={default}"
        bits.append(slot)
    desc = re.sub(r"\s+", " ", str(fn.get("description") or "")).strip()[:200]
    sig = ", ".join(bits)
    return f"{fn.get('name')}({sig}) — {desc}"


def _render_fn(fn: dict[str, Any]) -> str:
    return compact_option_spec(fn)


def _gold_names(row: dict[str, Any], answers: dict[str, list[str]]) -> list[str]:
    names: list[str] = []
    for call in answers.get(row.get("id", ""), []):
        if isinstance(call, dict) and call:
            names.append(next(iter(call)))
        elif isinstance(call, str):
            match = re.match(r"([A-Za-z0-9_\.]+)\s*(?:\(|$)", call)
            if match:
                names.append(match.group(1))
    if names:
        return names
    for raw in row.get("ground_truth") or []:
        if isinstance(raw, str):
            match = re.match(r"([A-Za-z0-9_\.]+)\s*\(", raw)
            if match:
                names.append(match.group(1))
    return names


def _load_answers(path: Path | None) -> dict[str, list[str]]:
    if path is None or not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        golds = []
        for item in row.get("ground_truth") or []:
            if isinstance(item, dict) and item:
                golds.append(next(iter(item)))
            elif isinstance(item, str):
                golds.append(item)
        out[row["id"]] = golds
    return out


def convert_file(path: Path, answers: dict[str, list[str]], irrelevance: bool) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        functions = row.get("function") or []
        criteria = {}
        for fn in functions:
            name = fn.get("name")
            if name and name not in criteria:
                criteria[name] = _render_fn(fn)
        if not criteria:
            continue
        golds = [] if irrelevance else _gold_names(row, answers)
        golds = [g for g in golds if g in criteria]
        if irrelevance or not golds:
            label = "__abstain__"
            criteria["__abstain__"] = "None of the listed tools fit the user request."
            golds = []
        else:
            label = golds[0]
            criteria["__abstain__"] = "None of the listed tools fit the user request."
        text = _user_text(row.get("question"))
        if not text:
            continue
        records.append(
            {
                "id": f"bfcl_{row.get('id')}",
                "package": f"bfcl/{path.stem}",
                "server_name": "bfcl",
                "format": "mcp_json",
                "delexicalized": False,
                "is_multi_turn": False,
                "has_collision_distractor": False,
                "source": "BFCL",
                "provenance": "bfcl_official",
                "bfcl_file": path.name,
                "trivial_single_tool": len(functions) <= 1 and not irrelevance,
                "gold_functions": golds,
                "state": f"User Request: {text}",
                "questions": {
                    "tool_route": {
                        "type": "choice",
                        "instructions": "Which single tool should run for this request? Use only the listed candidates.",
                        "criteria": criteria,
                        "label": label,
                    },
                    "tool_route_perm": {
                        "type": "choice",
                        "instructions": "Which single tool should run for this request? Use only the listed candidates.",
                        "criteria": criteria,
                        "label": label,
                    },
                    "arg_mapping": {
                        "type": "choice",
                        "instructions": "BFCL does not define a perturbed argument key. This head is not scored here.",
                        "criteria": {"__drop__": "No argument-key repair item in this benchmark row."},
                        "label": "__drop__",
                    },
                    "missing_required": {
                        "type": "noul",
                        "instructions": "Not labeled by BFCL for this converter.",
                        "label": "no",
                    },
                    "is_mutation": {
                        "type": "noul",
                        "instructions": "Not labeled by BFCL for this converter.",
                        "label": "no",
                    },
                },
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert official BFCL files into Soro records")
    parser.add_argument("--bfcl-dir", type=str, default=str(DEFAULT_BFCL))
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUT / "bfcl_routing.jsonl"))
    args = parser.parse_args()
    src = Path(args.bfcl_dir)
    files = [
        ("BFCL_v3_multiple.json", False),
        ("BFCL_v3_live_multiple.json", False),
        ("BFCL_v3_irrelevance.json", True),
        ("BFCL_v3_simple.json", False),
        ("BFCL_v3_live_simple.json", False),
    ]
    rows: list[dict[str, Any]] = []
    for name, irrelevant in files:
        path = src / name
        if not path.exists():
            print(f"skip missing {name}")
            continue
        answers = _load_answers(src / "possible_answer" / name)
        converted = convert_file(path, answers, irrelevant)
        print(f"{name}: {len(converted)} rows")
        rows.extend(converted)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
