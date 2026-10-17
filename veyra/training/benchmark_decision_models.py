"""Score decision models on the frozen seed-42 rows.

Arms: lexical heuristic, jaredpalmer/kev-0.8b (its own special-token encoder),
Soro-Kev-0.8B, and Soro-Kev-4B. No text generation.
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
KEV = Path.home() / ".cache/huggingface/hub/models--jaredpalmer--kev-0.8b/snapshots/bf75a6a8848ea6960ff2ed108d9ed44c2941174f"
CKPT_08 = ROOT / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b"
CKPT_4B = ROOT / "runs" / "soro_kev_qwen3_4b_best"
OUT = ROOT / "reports" / "decision_model_benchmark.json"
SPECIAL = ["<|fim_prefix|>", "<|fim_middle|>", "<|box_start|>", "<|box_end|>", "<|fim_suffix|>"]


def rows() -> list[dict]:
    bfcl = stratified_sample(load_rows(BFCL, FILES, 0, 0), 100, 42)
    external = []
    with EXTERNAL.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                external.append(json.loads(line))
    random.Random(42).shuffle(external)
    tagged = []
    for row in external[:60]:
        copied = dict(row)
        copied["bfcl_file"] = "external_human"
        tagged.append(copied)
    return bfcl + tagged


def hit(row: dict, pred: str | None) -> bool:
    label = row["questions"]["tool_route"]["label"]
    name = row.get("bfcl_file") or ""
    if name == "BFCL_v3_irrelevance.json" or label == "__abstain__":
        return pred == "__abstain__"
    golds = row.get("gold_functions") or []
    return pred in golds if golds else pred == label


def rates(items: list[dict], preds: list[str | None]) -> dict:
    buckets: dict[str, list[int]] = {}
    for row, pred in zip(items, preds):
        key = row.get("bfcl_file") or "external_human"
        correct, total = buckets.setdefault(key, [0, 0])
        buckets[key] = [correct + int(hit(row, pred)), total + 1]
    return {key: {"correct": value[0], "n": value[1], "accuracy": round(value[0] / value[1], 4)} for key, value in buckets.items()}


def median_ms(samples: list[float]) -> float:
    return round(float(statistics.median(samples)), 2) if samples else 0.0


def summarize(name: str, items: list[dict], preds: list[str | None], times: list[float], peak: float, note: str) -> dict:
    return {
        "name": name,
        "kind": "decision",
        "by_file": rates(items, preds),
        "malformed_rate": round(sum(pred is None for pred in preds) / max(len(preds), 1), 4),
        "mean_forward_passes": 1,
        "median_latency_ms": median_ms(times),
        "peak_vram_mb": round(peak, 1),
        "note": note,
    }


def score_heuristic(items: list[dict]) -> dict:
    from soro.routing.kev_local import LocalKevScorer

    scorer = LocalKevScorer(backend="heuristic")
    preds, times = [], []
    for index, row in enumerate(items):
        question = row["questions"]["tool_route"]
        started = time.perf_counter()
        probs = scorer.probabilities(row["state"], question["criteria"])
        if index >= 3:
            times.append((time.perf_counter() - started) * 1000)
        preds.append(max(probs, key=probs.get) if probs else None)
    return summarize("heuristic", items, preds, times, 0.0, "Hashed token overlap. No neural forward.")


def score_soro(name: str, ckpt: Path, items: list[dict], note: str) -> dict:
    from soro.routing.kev_local import LocalKevScorer

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    scorer = LocalKevScorer(run=str(ckpt), backend="neural", device="cuda")
    if not scorer.load():
        return {"name": name, "error": scorer.error or "load failed"}
    model = scorer._neural_model
    preds, times = [], []
    for index, row in enumerate(items):
        question = row["questions"]["tool_route"]
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            logits, keys = model.score_choice_sequence(
                row["state"], question.get("instructions", ""), question["criteria"], max_seq_len=1024
            )
        torch.cuda.synchronize()
        if index >= 3:
            times.append((time.perf_counter() - started) * 1000)
        preds.append(None if logits.numel() == 0 or not keys else keys[int(torch.argmax(logits).item())])
    peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
    del scorer, model
    torch.cuda.empty_cache()
    return summarize(name, items, preds, times, peak, note)


def load_original_kev():
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-0.8B-Base", trust_remote_code=True)
    try:
        base = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3.5-0.8B-Base",
            dtype=torch.float16,
            attn_implementation="sdpa",
            trust_remote_code=True,
        ).model
    except TypeError:
        base = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3.5-0.8B-Base", dtype=torch.float16, trust_remote_code=True
        ).model
    if hasattr(base, "language_model"):
        base = base.language_model
    backbone = PeftModel.from_pretrained(base, str(KEV))
    weights = torch.load(KEV / "head.pt", map_location="cpu", weights_only=False)
    head = weights["head"]
    query = torch.nn.Linear(1024, 256)
    key = torch.nn.Linear(1024, 256)
    query.load_state_dict({"weight": head["q.weight"], "bias": head["q.bias"]})
    key.load_state_dict({"weight": head["k.weight"], "bias": head["k.bias"]})
    temperature = float(weights.get("temperature", 1.0))
    backbone.cuda().eval()
    query.cuda().eval()
    key.cuda().eval()
    return tokenizer, backbone, query, key, temperature


def kev_encode(tokenizer, state: str, instruction: str, criteria: dict[str, str]) -> tuple[list[int], int, list[int], list[str]]:
    keys = list(criteria)
    ids_of = [tokenizer.convert_tokens_to_ids(token) for token in SPECIAL]
    state_ids = tokenizer.encode(state[:1200], add_special_tokens=False)[:380]
    sequence = [ids_of[0]] + state_ids
    state_len = len(sequence)
    branch = [ids_of[1]] + tokenizer.encode(instruction[:240], add_special_tokens=False)
    opt_ends = []
    for key in keys:
        text = f"{key}: {criteria[key]}"
        text = text[:240]
        span = [ids_of[2]] + tokenizer.encode(text, add_special_tokens=False)[:80] + [ids_of[3]]
        branch.extend(span)
        opt_ends.append(state_len + len(branch) - 1)
    branch.append(ids_of[4])
    sequence.extend(branch)
    decide = len(sequence) - 1
    return sequence, decide, opt_ends, keys


def score_original_kev(items: list[dict]) -> dict:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer, backbone, query, key, temperature = load_original_kev()
    preds, times = [], []
    scale = 1.0 / (256 ** 0.5)
    for index, row in enumerate(items):
        question = row["questions"]["tool_route"]
        sequence, decide, opt_ends, keys = kev_encode(
            tokenizer, row["state"], question.get("instructions", "Which option?"), question["criteria"]
        )
        input_ids = torch.tensor([sequence], device="cuda")
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            hidden = backbone(input_ids=input_ids).last_hidden_state[0].float()
            logits = (key(hidden[opt_ends]) @ query(hidden[decide])) * scale / max(temperature, 1e-4)
        torch.cuda.synchronize()
        if index >= 3:
            times.append((time.perf_counter() - started) * 1000)
        preds.append(keys[int(torch.argmax(logits).item())])
    peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
    del backbone, query, key
    torch.cuda.empty_cache()
    return summarize(
        "jaredpalmer/kev-0.8b",
        items,
        preds,
        times,
        peak,
        "Original Kev pointer on Qwen3.5-0.8B-Base. Special-token boundaries, temperature "
        f"{temperature:.3f}. Windows still uses the slow DeltaNet fallback.",
    )


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required")
    items = rows()
    print(f"rows {len(items)} device {torch.cuda.get_device_name(0)}", flush=True)
    report = {
        "device": torch.cuda.get_device_name(0),
        "n": len(items),
        "seed": 42,
        "models": [
            score_heuristic(items),
        ],
    }
    print("heuristic", report["models"][-1]["by_file"], flush=True)
    report["models"].append(score_original_kev(items))
    print("kev", report["models"][-1].get("by_file") or report["models"][-1], flush=True)
    report["models"].append(score_soro(
        "soro-kev-0.8b",
        CKPT_08,
        items,
        "Qwen3.5-0.8B pointer. Windows PyTorch fallback for DeltaNet, so latency is not the Linux kernel time.",
    ))
    print("0.8b", report["models"][-1]["by_file"], flush=True)
    report["models"].append(score_soro(
        "soro-kev-4b",
        CKPT_4B,
        items,
        "Qwen3-4B NF4 pointer with SDPA. One prefill. Not a Qwen3.5 hybrid.",
    ))
    print("4b", report["models"][-1]["by_file"], flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
