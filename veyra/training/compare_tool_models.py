"""Score Soro-Kev and optional generative tool-callers on the same rows.

Soro reads one sequence of the user text plus the candidate schemas and
points at a candidate. A generative model is prompted with the same text
and the same schemas and must emit {"name": "...", "arguments": {...}}.

Only tool choice is compared. BFCL argument values are not a Soro output.
Generative argument exact-match is reported only when that model emits JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from soro.routing.kev_model import SoroKevModel  # noqa: E402


def load_rows(path: Path, files: set[str] | None, limit: int, per_file: int) -> list[dict]:
    rows = []
    seen: dict[str, int] = defaultdict(int)
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            name = row.get("bfcl_file") or ""
            if files and name not in files:
                continue
            if row.get("trivial_single_tool"):
                continue
            if per_file and seen[name] >= per_file:
                continue
            rows.append(row)
            seen[name] += 1
            if limit and len(rows) >= limit:
                break
    return rows


def load_soro(ckpt: Path) -> SoroKevModel:
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file

    cfg = json.loads((ckpt / "config.json").read_text(encoding="utf-8"))
    model = SoroKevModel(
        model_name=cfg["model_name"],
        hidden_size=cfg.get("hidden_size", 1024),
        proj_dim=cfg.get("proj_dim", 256),
        use_mock=False,
        allow_mock_fallback=False,
        torch_dtype=torch.float32,
    )
    set_peft_model_state_dict(model.backbone, load_file(str(ckpt / "adapter_model.safetensors")))
    head = torch.load(ckpt / "head.pt", map_location="cpu", weights_only=False)
    model.q_proj_head.load_state_dict(head["q_proj_head"])
    model.opt_proj_head.load_state_dict(head["opt_proj_head"])
    model.binary_head.load_state_dict(head["binary_head"])
    if "log_temp" in head:
        model.log_temp.data = head["log_temp"]
    model.eval()
    return model


def score_soro(model: SoroKevModel, rows: list[dict]) -> dict:
    hit = 0
    abstain_hit = 0
    abstain_n = 0
    by_file: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    with torch.no_grad():
        for i, row in enumerate(rows, 1):
            q = row["questions"]["tool_route"]
            keys_logits, keys = model.score_choice_sequence(
                row["state"], q.get("instructions", ""), q["criteria"], max_seq_len=4096
            )
            golds = row.get("gold_functions") or []
            label = q["label"]
            if keys_logits.numel() == 0:
                pred = None
            else:
                pred = keys[int(torch.argmax(keys_logits).item())]
            ok = pred in golds if golds else pred == label
            hit += int(ok)
            by_file[row["bfcl_file"]][0] += int(ok)
            by_file[row["bfcl_file"]][1] += 1
            if label == "__abstain__":
                abstain_n += 1
                abstain_hit += int(pred == "__abstain__")
            if i % 10 == 0 or i == len(rows):
                print(f"soro {i}/{len(rows)} running {hit/i:.3f}", flush=True)
    return {
        "n": len(rows),
        "tool_accuracy": hit / max(len(rows), 1),
        "abstain_accuracy": abstain_hit / abstain_n if abstain_n else None,
        "by_file": {k: v[0] / v[1] for k, v in by_file.items()},
        "by_file_counts": {k: v for k, v in by_file.items()},
    }


def generative_prompt(row: dict) -> str:
    q = row["questions"]["tool_route"]
    lines = [row["state"], "Tools:"]
    for key, spec in q["criteria"].items():
        if key == "__abstain__":
            continue
        lines.append(spec)
    lines.append(
        'Reply with one JSON object only: {"name": "<tool name or __abstain__>", "arguments": {}}'
    )
    return "\n".join(lines)


def parse_name(text: str, allowed: set[str]) -> str | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    name = obj.get("name")
    return name if name in allowed or name == "__abstain__" else None


def score_generative(model_name: str, rows: list[dict]) -> dict:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32, trust_remote_code=True)
    model.eval()
    hit = 0
    for i, row in enumerate(rows, 1):
        prompt = generative_prompt(row)
        ids = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).input_ids
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=64, do_sample=False)
        text = tok.decode(out[0, ids.shape[1] :], skip_special_tokens=True)
        allowed = set(row["questions"]["tool_route"]["criteria"])
        pred = parse_name(text, allowed)
        golds = row.get("gold_functions") or []
        label = row["questions"]["tool_route"]["label"]
        hit += int(pred in golds if golds else pred == label)
        print(f"{model_name} {i}/{len(rows)}", flush=True)
    return {"n": len(rows), "tool_accuracy": hit / max(len(rows), 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Soro to generative tool callers on the same rows")
    parser.add_argument("--data", type=str, default=str(ROOT / "data" / "bfcl" / "soro" / "bfcl_routing.jsonl"))
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--limit", type=int, default=0, help="Max routing rows after dropping single-tool files. 0 means all.")
    parser.add_argument("--per-file", type=int, default=0, help="Cap rows from each BFCL file. 0 means no per-file cap.")
    parser.add_argument("--files", type=str, default="BFCL_v3_multiple.json,BFCL_v3_live_multiple.json,BFCL_v3_irrelevance.json")
    parser.add_argument("--generative", type=str, default="", help="Comma-separated HF model ids to generate tool calls.")
    parser.add_argument("--report", type=str, default=str(ROOT / "reports" / "bfcl_compare.json"))
    args = parser.parse_args()
    files = {part.strip() for part in args.files.split(",") if part.strip()}
    rows = load_rows(Path(args.data), files, args.limit, args.per_file)
    print(f"scoring {len(rows)} non-trivial BFCL rows", flush=True)
    report = {"soro": score_soro(load_soro(Path(args.checkpoint)), rows)}
    for name in [part.strip() for part in args.generative.split(",") if part.strip()]:
        report[name] = score_generative(name, rows)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
