"""Score pointer models against generative tool callers on frozen rows.

The BFCL rows are the seed-42 stratified 100 used by compare_tool_models.py.
The external slice is the first 60 rows of val_external_human.jsonl after the
same seed.
"""
from __future__ import annotations

import json
import random
import statistics
import time
from pathlib import Path

import torch

from compare_tool_models import load_rows, stratified_sample

ROOT = Path(__file__).resolve().parents[1]
BFCL = ROOT / "data" / "bfcl" / "soro" / "bfcl_routing.jsonl"
EXTERNAL = ROOT / "data" / "soro_kev_dataset" / "val_external_human.jsonl"
FILES = {
    "BFCL_v3_multiple.json",
    "BFCL_v3_live_multiple.json",
    "BFCL_v3_irrelevance.json",
}
CKPT_08 = ROOT / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b"
CKPT_4B = ROOT / "runs" / "soro_kev_qwen3_4b_best"
GENERATORS = (
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
)
OUT = ROOT / "reports" / "competitor_llm_benchmark.json"


def external_rows(n: int = 60, seed: int = 42) -> list[dict]:
    rows = []
    with EXTERNAL.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    random.Random(seed).shuffle(rows)
    return rows[:n]


def bfcl_rows() -> list[dict]:
    rows = load_rows(BFCL, FILES, 0, 0)
    return stratified_sample(rows, 100, 42)


def prompt_for(row: dict) -> str:
    question = row["questions"]["tool_route"]
    lines = [
        "You are a tool router. Choose exactly one listed tool.",
        'If no tool fits, reply with {"tool": "__abstain__", "arguments": {}}. ',
        "Reply with one JSON object only.",
        row["state"],
        "Tools:",
    ]
    for key, spec in question["criteria"].items():
        if key == "__abstain__":
            continue
        lines.append(f"- {key}: {spec}")
    return "\n".join(lines)


def parse_tool(text: str, allowed: set[str]) -> tuple[str | None, bool]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None, True
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, True
    name = obj.get("tool", obj.get("name"))
    if not isinstance(name, str) or name not in allowed:
        return None, True
    return name, False


def gold_hit(row: dict, pred: str | None) -> bool:
    question = row["questions"]["tool_route"]
    golds = row.get("gold_functions") or []
    label = question["label"]
    if golds:
        return pred in golds
    return pred == label


def file_rates(rows: list[dict], preds: list[str | None]) -> dict:
    buckets: dict[str, list[int]] = {}
    for row, pred in zip(rows, preds):
        name = row.get("bfcl_file") or "external_human"
        hit, total = buckets.setdefault(name, [0, 0])
        label = row["questions"]["tool_route"]["label"]
        if name == "BFCL_v3_irrelevance.json" or label == "__abstain__":
            ok = pred == "__abstain__"
        else:
            ok = gold_hit(row, pred)
        buckets[name] = [hit + int(ok), total + 1]
    return {key: {"correct": value[0], "n": value[1], "accuracy": value[0] / value[1]} for key, value in buckets.items()}


def median_ms(samples: list[float]) -> float:
    return float(statistics.median(samples)) if samples else 0.0


def score_pointer(name: str, ckpt: Path, rows: list[dict]) -> dict:
    from soro.routing.kev_local import LocalKevScorer

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    scorer = LocalKevScorer(run=str(ckpt), backend="neural", device="cuda")
    if not scorer.load():
        return {"name": name, "error": scorer.error or "load failed"}
    model = scorer._neural_model
    preds: list[str | None] = []
    bad = 0
    times: list[float] = []
    for index, row in enumerate(rows):
        question = row["questions"]["tool_route"]
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            logits, keys = model.score_choice_sequence(
                row["state"], question.get("instructions", ""), question["criteria"], max_seq_len=1024
            )
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        if index >= 3:
            times.append(elapsed)
        if logits.numel() == 0 or not keys:
            preds.append(None)
            bad += 1
        else:
            preds.append(keys[int(torch.argmax(logits).item())])
    peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
    del scorer, model
    torch.cuda.empty_cache()
    return {
        "name": name,
        "kind": "pointer",
        "by_file": file_rates(rows, preds),
        "malformed_rate": bad / max(len(rows), 1),
        "mean_forward_passes": 1,
        "mean_generated_tokens": 0,
        "median_latency_ms": median_ms(times),
        "peak_vram_mb": round(peak, 1),
    }


def score_heuristic(rows: list[dict]) -> dict:
    from soro.routing.kev_local import LocalKevScorer

    scorer = LocalKevScorer(backend="heuristic")
    preds = []
    times = []
    for index, row in enumerate(rows):
        question = row["questions"]["tool_route"]
        started = time.perf_counter()
        probs = scorer.probabilities(row["state"], question["criteria"])
        elapsed = (time.perf_counter() - started) * 1000
        if index >= 3:
            times.append(elapsed)
        preds.append(max(probs, key=probs.get) if probs else None)
    return {
        "name": "heuristic",
        "kind": "lexical",
        "by_file": file_rates(rows, preds),
        "malformed_rate": 0.0,
        "mean_forward_passes": 0,
        "mean_generated_tokens": 0,
        "median_latency_ms": median_ms(times),
        "peak_vram_mb": 0.0,
    }


def score_generator(model_id: str, rows: list[dict]) -> dict:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch.float16, device_map="cuda", trust_remote_code=True
    )
    model.eval()
    preds: list[str | None] = []
    bad = 0
    times: list[float] = []
    new_tokens: list[int] = []
    for index, row in enumerate(rows):
        allowed = set(row["questions"]["tool_route"]["criteria"])
        ids = tokenizer(prompt_for(row), return_tensors="pt", truncation=True, max_length=1024).to("cuda")
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            out = model.generate(**ids, max_new_tokens=64, do_sample=False)
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        generated = out.shape[1] - ids["input_ids"].shape[1]
        text = tokenizer.decode(out[0, ids["input_ids"].shape[1] :], skip_special_tokens=True)
        pred, malformed = parse_tool(text, allowed)
        if index >= 3:
            times.append(elapsed)
            new_tokens.append(generated)
        preds.append(pred)
        bad += int(malformed)
    peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
    del model
    torch.cuda.empty_cache()
    return {
        "name": model_id,
        "kind": "generative",
        "by_file": file_rates(rows, preds),
        "malformed_rate": bad / max(len(rows), 1),
        "mean_forward_passes": round(sum(new_tokens) / max(len(new_tokens), 1), 2),
        "mean_generated_tokens": round(sum(new_tokens) / max(len(new_tokens), 1), 2),
        "median_latency_ms": median_ms(times),
        "peak_vram_mb": round(peak, 1),
    }


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required")
    bfcl = bfcl_rows()
    external = external_rows()
    tagged_external = []
    for row in external:
        copied = dict(row)
        copied["bfcl_file"] = "external_human"
        tagged_external.append(copied)
    rows = bfcl + tagged_external
    print(f"rows bfcl={len(bfcl)} external={len(external)}", flush=True)
    report = {
        "device": torch.cuda.get_device_name(0),
        "bfcl_n": len(bfcl),
        "external_n": len(external),
        "seed": 42,
        "note": (
            "Soro-Kev-0.8B is Qwen3.5 and uses the PyTorch reference kernels for "
            "causal_conv1d and chunk_gated_delta_rule on Windows. "
            "Soro-Kev-4B is Qwen3 NF4 with SDPA. "
            "Generative mean_forward_passes is the mean number of new tokens."
        ),
        "models": [],
    }
    report["models"].append(score_heuristic(rows))
    print("heuristic done", report["models"][-1]["median_latency_ms"], flush=True)
    for model_id in GENERATORS:
        print("generating", model_id, flush=True)
        report["models"].append(score_generator(model_id, rows))
        print(model_id, report["models"][-1]["by_file"], flush=True)
    report["models"].append(score_pointer("soro-kev-0.8b", CKPT_08, rows))
    print("0.8b", report["models"][-1].get("by_file") or report["models"][-1], flush=True)
    report["models"].append(score_pointer("soro-kev-4b", CKPT_4B, rows))
    print("4b", report["models"][-1].get("by_file") or report["models"][-1], flush=True)
    kev = Path.home() / ".cache/huggingface/hub/models--jaredpalmer--kev-0.8b/snapshots"
    snaps = sorted(kev.glob("*/head.pt")) if kev.exists() else []
    if snaps:
        print("og kev", snaps[-1].parent, flush=True)
        report["models"].append(score_pointer("jaredpalmer/kev-0.8b", snaps[-1].parent, rows))
        print("og", report["models"][-1].get("by_file") or report["models"][-1], flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
