"""Turn ToolACE, xLAM, and Toucan trajectories into Soro rows.

Output is external_intent.jsonl. The trainer loads it beside train.jsonl.
Toucan is sampled. xLAM is included only when the json file is already on disk,
because that dataset download is gated. NESTFUL is not read.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "external_raw"
OUT = ROOT / "data" / "soro_kev_dataset" / "external_intent.jsonl"

TOOLACE_URL = "https://huggingface.co/datasets/Team-ACE/ToolACE/resolve/main/data.json"
TOUCAN_URL = "https://huggingface.co/datasets/Agent-Ark/Toucan-1.5M/resolve/main/Kimi-K2/train-00000-of-00040.parquet"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"have {dest.name} ({dest.stat().st_size} bytes)")
        return
    print(f"downloading {dest.name}", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f"saved {dest.name} ({dest.stat().st_size} bytes)", flush=True)


def compact_fn(fn: dict) -> str:
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    required = set(params.get("required") or [])
    bits = []
    for name, info in list(props.items())[:8]:
        info = info if isinstance(info, dict) else {}
        typ = str(info.get("type") or "string")
        star = "*" if name in required else ""
        bits.append(f"{name}: {typ}{star}")
    desc = re.sub(r"\s+", " ", str(fn.get("description") or "")).strip()[:160]
    return f"{fn.get('name')}({', '.join(bits)}) — {desc}"


def record(state: str, tools: list[dict], label: str, intent: str, source: str, rec_id: str) -> dict | None:
    criteria = {}
    for fn in tools:
        name = str(fn.get("name") or "").strip()
        if not name or name in criteria:
            continue
        criteria[name] = compact_fn(fn)
    if not criteria:
        return None
    if label not in criteria and label not in ("__abstain__", "__done__"):
        return None
    if label == "__abstain__":
        criteria["__abstain__"] = "None of the listed tools fit the user request."
    if label == "__done__":
        criteria["__done__"] = "The requested work is finished. Do not call another tool."
    return {
        "id": rec_id,
        "package": f"external/{source}",
        "server_name": source,
        "format": "mcp_json",
        "delexicalized": False,
        "is_multi_turn": "Prior tool observation" in state,
        "source": source,
        "provenance": "external_tool_trajectory",
        "intent": intent,
        "state": state if state.startswith("User Request:") else f"User Request: {state}",
        "questions": {
            "tool_route": {
                "type": "choice",
                "instructions": "Which single tool should run next? Use only the listed candidates.",
                "criteria": criteria,
                "label": label,
            },
            "tool_route_perm": {
                "type": "choice",
                "instructions": "Which single tool should run next? Use only the listed candidates.",
                "criteria": criteria,
                "label": label,
            },
            "arg_mapping": {
                "type": "choice",
                "instructions": "No perturbed key in this external row.",
                "criteria": {"__drop__": "No argument-key repair item."},
                "label": "__drop__",
            },
            "missing_required": {
                "type": "choice",
                "instructions": "Is any required parameter value missing from the user request?",
                "criteria": {
                    "yes": "A required parameter value is missing from the user request.",
                    "no": "All required parameter values are present in the user request.",
                },
                "label": "no",
            },
            "is_mutation": {
                "type": "choice",
                "instructions": "Does the next tool mutate external state?",
                "criteria": {
                    "yes": "This tool writes, updates, deletes, or moves external state.",
                    "no": "This tool only reads external state.",
                },
                "label": "no",
            },
        },
    }


def parse_calls(text: str) -> list[str]:
    return re.findall(r"([A-Za-z0-9_][A-Za-z0-9_ .+\-]{0,80})\(", text or "")


def tools_from_system(system: str) -> list[dict]:
    start = system.find("[{")
    if start < 0:
        return []
    try:
        parsed, _ = json.JSONDecoder().raw_decode(system[start:])
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict) and item.get("name")]


def from_toolace(path: Path, limit: int) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for i, row in enumerate(rows):
        if limit and len(out) >= limit:
            break
        tools = tools_from_system(row.get("system") or "")
        if len(tools) < 2:
            continue
        prior = []
        user = ""
        for turn in row.get("conversations") or []:
            who = turn.get("from")
            text = turn.get("value") or ""
            if who == "user":
                user = text.strip()
            elif who == "tool":
                prior.append(text[:240])
            elif who == "assistant":
                calls = [c.strip() for c in parse_calls(text) if c.strip() in {t["name"] for t in tools}]
                if not user:
                    continue
                state = user
                if prior:
                    state += "\nPrior tool observation: " + " | ".join(prior[-2:])
                if len(calls) >= 2:
                    rec = record(state, tools, calls[0], "multi", "ToolACE", f"toolace_{i}")
                elif len(calls) == 1:
                    rec = record(state, tools, calls[0], "single", "ToolACE", f"toolace_{i}")
                else:
                    rec = record(state, tools, "__abstain__", "none", "ToolACE", f"toolace_{i}")
                if rec:
                    out.append(rec)
                break
    return out


def from_xlam(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        print("xLAM file missing. The Hub download is gated. Put xlam_function_calling_60k.json in data/external_raw to include it.")
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for i, row in enumerate(rows):
        if limit and len(out) >= limit:
            break
        tools = row.get("tools") or row.get("functions") or []
        if isinstance(tools, str):
            try:
                tools = json.loads(tools)
            except json.JSONDecodeError:
                tools = []
        query = row.get("query") or row.get("question") or ""
        answers = row.get("answers") or row.get("answer") or []
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except json.JSONDecodeError:
                answers = []
        names = []
        for ans in answers if isinstance(answers, list) else []:
            if isinstance(ans, dict):
                names.append(ans.get("name") or ans.get("function"))
        names = [n for n in names if n]
        if not query or not tools or not names:
            continue
        intent = "multi" if len(names) > 1 else "single"
        rec = record(query, tools, names[0], intent, "xLAM", f"xlam_{i}")
        if rec:
            out.append(rec)
    return out


def from_toucan(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        print("Toucan parquet missing")
        return []
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=None)
    # Read only the first `limit` rows worth of columns we need.
    cols = set(table.column_names)
    want = [c for c in ("question", "available_tools", "target_tools", "messages") if c in cols]
    table = table.select(want).slice(0, max(limit * 3, limit))
    out = []
    for i in range(table.num_rows):
        if len(out) >= limit:
            break
        question = table.column("question")[i].as_py() if "question" in want else ""
        raw_tools = table.column("available_tools")[i].as_py() if "available_tools" in want else "[]"
        raw_target = table.column("target_tools")[i].as_py() if "target_tools" in want else "[]"
        try:
            tools = json.loads(raw_tools) if isinstance(raw_tools, str) else raw_tools
        except json.JSONDecodeError:
            tools = []
        names = []
        if isinstance(raw_target, str) and raw_target.strip().startswith("["):
            try:
                target = json.loads(raw_target)
            except json.JSONDecodeError:
                target = []
        elif isinstance(raw_target, str):
            target = [part.strip() for part in raw_target.split(",") if part.strip()]
        else:
            target = raw_target or []
        if isinstance(target, list):
            for item in target:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    names.append(item.get("name") or item.get("tool"))
        names = [n for n in names if n]
        flat_tools = []
        if isinstance(tools, list):
            for item in tools:
                if isinstance(item, dict) and "function" in item and isinstance(item["function"], dict):
                    flat_tools.append(item["function"])
                elif isinstance(item, dict) and item.get("name"):
                    flat_tools.append(item)
        resolved = []
        catalog_names = [fn.get("name") or "" for fn in flat_tools]
        for short in names:
            match = next((full for full in catalog_names if full == short or full.endswith("-" + short) or full.endswith("_" + short)), None)
            if match:
                resolved.append(match)
        if not question or not resolved:
            continue
        intent = "multi" if len(resolved) > 1 else "single"
        rec = record(str(question), flat_tools, resolved[0], intent, "Toucan", f"toucan_{i}")
        if rec:
            out.append(rec)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolace-limit", type=int, default=8000)
    parser.add_argument("--xlam-limit", type=int, default=8000)
    parser.add_argument("--toucan-limit", type=int, default=8000)
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if not args.skip_download:
        download(TOOLACE_URL, RAW / "toolace_data.json")
        try:
            download(TOUCAN_URL, RAW / "toucan_shard0.parquet")
        except Exception as exc:
            print("toucan download failed", exc)
    rows = []
    rows.extend(from_toolace(RAW / "toolace_data.json", args.toolace_limit))
    rows.extend(from_xlam(RAW / "xlam_function_calling_60k.json", args.xlam_limit))
    rows.extend(from_toucan(RAW / "toucan_shard0.parquet", args.toucan_limit))
    rng = random.Random(2026)
    rng.shuffle(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = {}
    for row in rows:
        key = (row["source"], row["intent"])
        counts[key] = counts.get(key, 0) + 1
    print("wrote", len(rows), "to", out)
    for key, n in sorted(counts.items()):
        print(f"  {key[0]} {key[1]}: {n}")


if __name__ == "__main__":
    main()
