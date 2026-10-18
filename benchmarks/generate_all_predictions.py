"""
Generate Per-Row Predictions for All Systems and Splits.

Outputs per-row JSONL predictions to benchmarks/predictions/<split>/<model>.jsonl
Each line contains:
{
  "id": int,
  "package": str,
  "label": str,
  "top_tool": str,
  "is_correct": bool,
  "is_abstain_row": bool,
  "is_shared_tool": bool,
  "has_collision": bool,
  "bfcl_file": str,
  "probabilities": dict[str, float]
}

Strictly single-source: all benchmark tables in README and model cards
are computed directly from these prediction files by reconcile_and_verify.py.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import torch
import torch.nn.functional as F

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "veyra" / "python" / "src"))

from soro.routing.kev_local import LocalKevScorer

SHARED_TOOLS = {
    "check_service_status",
    "list_processes",
    "reverse_geocode",
    "transfer_to_human_agents",
}

BFCL_FILES = {
    "BFCL_v3_multiple.json",
    "BFCL_v3_live_multiple.json",
    "BFCL_v3_irrelevance.json",
}


def extract_query(state: str) -> str:
    match = re.search(r"User Request:\s*(.+?)(?:\nAgent:|\nPrior tool observation:|\nUser:|$)", state, re.DOTALL)
    if match:
        return match.group(1).strip()
    return state.strip()


def parse_candidate_text(name: str, desc: str) -> str:
    if name == "__abstain__":
        return "None of the listed tools or skills fit the user request."
    if desc.startswith("{") and desc.endswith("}"):
        try:
            data = json.loads(desc)
            t_name = data.get("name", name)
            t_desc = data.get("description", "")
            props = list(data.get("inputSchema", {}).get("properties", {}).keys()) if "inputSchema" in data else []
            return f"{t_name} {t_desc} {' '.join(props)}".strip()
        except Exception:
            pass
    clean = re.sub(r"[^a-zA-Z0-9_\s\.\-]", " ", desc)
    clean = re.sub(r"\s+", " ", clean).strip()
    return f"{name} {clean}"


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


# ---------------------------------------------------------
# Baseline Scorers
# ---------------------------------------------------------

class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75, abstain_threshold: float = 0.5):
        self.k1 = k1
        self.b = b
        self.abstain_threshold = abstain_threshold

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_tokens = tokenize(query)
        tool_candidates = {k: v for k, v in candidates.items() if k != "__abstain__"}
        if not tool_candidates:
            return {"__abstain__": 1.0}

        doc_tokens = {name: tokenize(parse_candidate_text(name, desc)) for name, desc in tool_candidates.items()}
        N = len(tool_candidates)
        avgdl = sum(len(d) for d in doc_tokens.values()) / max(N, 1)

        df = Counter()
        for d in doc_tokens.values():
            df.update(set(d))

        raw_scores = {}
        for name, d in doc_tokens.items():
            doc_len = len(d)
            tf = Counter(d)
            score = 0.0
            for qt in q_tokens:
                if qt in tf:
                    n_qt = df[qt]
                    idf = math.log(1.0 + (N - n_qt + 0.5) / (n_qt + 0.5))
                    f = tf[qt]
                    denom = f + self.k1 * (1.0 - self.b + self.b * (doc_len / max(avgdl, 1e-6)))
                    score += idf * (f * (self.k1 + 1.0)) / max(denom, 1e-6)
            raw_scores[name] = score

        max_raw = max(raw_scores.values()) if raw_scores else 0.0
        exp_s = {k: math.exp(v / 1.5) for k, v in raw_scores.items()}
        sum_exp = sum(exp_s.values())
        tool_probs = {k: v / sum_exp for k, v in exp_s.items()}

        if max_raw < self.abstain_threshold:
            p_abstain = min(0.95, (self.abstain_threshold - max_raw) / self.abstain_threshold * 0.8 + 0.2)
            scale = 1.0 - p_abstain
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        else:
            p_abstain = 0.02
            scale = 0.98
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        return res


class DenseCosineScorer:
    def __init__(self, num_dims: int = 512, abstain_threshold: float = 0.25):
        self.num_dims = num_dims
        self.abstain_threshold = abstain_threshold

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.num_dims
        tokens = tokenize(text)
        for t in tokens:
            h = abs(hash(t)) % self.num_dims
            vec[h] += 1.0
            if len(t) >= 3:
                for i in range(len(t) - 2):
                    sub_h = abs(hash(t[i:i+3])) % self.num_dims
                    vec[sub_h] += 0.5
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0.0 else vec

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_vec = self._embed(query)
        tool_candidates = {k: v for k, v in candidates.items() if k != "__abstain__"}
        if not tool_candidates:
            return {"__abstain__": 1.0}

        raw_sims = {}
        for name, desc in tool_candidates.items():
            c_vec = self._embed(parse_candidate_text(name, desc))
            sim = sum(a * b for a, b in zip(q_vec, c_vec))
            raw_sims[name] = max(sim, 0.0001)

        max_sim = max(raw_sims.values()) if raw_sims else 0.0
        exp_s = {k: math.exp(v / 0.12) for k, v in raw_sims.items()}
        sum_exp = sum(exp_s.values())
        tool_probs = {k: v / sum_exp for k, v in exp_s.items()}

        if max_sim < self.abstain_threshold:
            p_abstain = min(0.95, (self.abstain_threshold - max_sim) / self.abstain_threshold * 0.8 + 0.2)
            scale = 1.0 - p_abstain
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        else:
            p_abstain = 0.02
            scale = 0.98
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        return res


class CrossEncoderScorer:
    def __init__(self, abstain_threshold: float = 2.0):
        self.abstain_threshold = abstain_threshold

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_tokens = set(tokenize(query))
        tool_candidates = {k: v for k, v in candidates.items() if k != "__abstain__"}
        if not tool_candidates:
            return {"__abstain__": 1.0}

        raw_scores = {}
        for name, desc in tool_candidates.items():
            parsed = parse_candidate_text(name, desc)
            d_tokens = set(tokenize(parsed))
            overlap = len(q_tokens & d_tokens)
            jaccard = overlap / max(len(q_tokens | d_tokens), 1)
            name_bonus = 1.5 if any(qt in name.lower() for qt in q_tokens if len(qt) > 3) else 1.0
            score = (overlap * 1.5 + jaccard * 6.0) * name_bonus
            raw_scores[name] = score

        max_score = max(raw_scores.values()) if raw_scores else 0.0
        exp_s = {k: math.exp(v / 2.0) for k, v in raw_scores.items()}
        sum_exp = sum(exp_s.values())
        tool_probs = {k: v / sum_exp for k, v in exp_s.items()}

        if max_score < self.abstain_threshold:
            p_abstain = min(0.95, (self.abstain_threshold - max_score) / self.abstain_threshold * 0.8 + 0.2)
            scale = 1.0 - p_abstain
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        else:
            p_abstain = 0.02
            scale = 0.98
            res = {k: v * scale for k, v in tool_probs.items()}
            res["__abstain__"] = p_abstain
        return res


class UntrainedOptionLogitsScorer:
    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_tokens = set(tokenize(query))
        raw_logits = {}
        for idx, (k, desc) in enumerate(candidates.items()):
            if k == "__abstain__":
                raw_logits[k] = 1.5
                continue
            parsed = parse_candidate_text(k, desc)
            d_tokens = set(tokenize(parsed))
            matches = len(q_tokens & d_tokens)
            raw_logits[k] = matches * 1.4 + (1.0 if any(qt in k.lower() for qt in q_tokens) else 0.0)

        max_l = max(raw_logits.values()) if raw_logits else 0.0
        exp_l = {k: math.exp((v - max_l) / 1.6) for k, v in raw_logits.items()}
        sum_exp = sum(exp_l.values())
        return {k: v / sum_exp for k, v in exp_l.items()}


# ---------------------------------------------------------
# Soro-Kev Wrapper
# ---------------------------------------------------------

class SoroKevEvaluator:
    def __init__(self, checkpoint_path: str, device: str = "cuda"):
        self.scorer = LocalKevScorer(run=checkpoint_path, backend="neural", device=device)
        loaded = self.scorer.load()
        if not loaded:
            raise RuntimeError(f"Could not load neural SoroKev checkpoint from {checkpoint_path}")

    def score(self, state: str, candidates: Dict[str, str]) -> Dict[str, float]:
        with torch.inference_mode():
            return self.scorer.probabilities(state, candidates)


# ---------------------------------------------------------
# Dataset Loading
# ---------------------------------------------------------

def load_external_dataset() -> List[Dict[str, Any]]:
    path = REPO_ROOT / "releases" / "soro-universal-tool-harness" / "val_external_heldout.jsonl"
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                r = json.loads(line)
                r["_row_id"] = idx
                records.append(r)
    return records


def load_zeroshot_dataset() -> List[Dict[str, Any]]:
    path = REPO_ROOT / "releases" / "soro-universal-tool-harness" / "val_zeroshot.jsonl"
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                r = json.loads(line)
                r["_row_id"] = idx
                records.append(r)
    return records


def load_bfcl_slice() -> List[Dict[str, Any]]:
    path = REPO_ROOT / "veyra" / "data" / "bfcl" / "soro" / "bfcl_routing.jsonl"
    all_rows = []
    seen: dict[str, int] = defaultdict(int)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            name = r.get("bfcl_file") or ""
            if name not in BFCL_FILES or r.get("trivial_single_tool"):
                continue
            all_rows.append(r)

    # Deterministic stratified sample matching benchmark_decision_models.py (n=100, seed=42)
    rng = random.Random(42)
    by_file = defaultdict(list)
    for r in all_rows:
        by_file[r.get("bfcl_file")].append(r)

    sampled = []
    # 34 multiple, 33 live_multiple, 33 irrelevance
    counts = {"BFCL_v3_multiple.json": 34, "BFCL_v3_live_multiple.json": 33, "BFCL_v3_irrelevance.json": 33}
    for fname, target_n in counts.items():
        sub = by_file[fname]
        rng.shuffle(sub)
        sampled.extend(sub[:target_n])

    for idx, r in enumerate(sampled):
        r["_row_id"] = idx
    return sampled


# ---------------------------------------------------------
# Prediction Evaluation Pipeline
# ---------------------------------------------------------

def evaluate_system_on_dataset(
    system_name: str,
    system_obj: Any,
    records: List[Dict[str, Any]],
    split_name: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_preds = []
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        existing_preds.append(json.loads(line))
                    except Exception:
                        pass

    start_idx = len(existing_preds)
    n_correct = sum(1 for p in existing_preds if p.get("is_correct", False))
    predictions = list(existing_preds)

    if start_idx >= len(records):
        print(f"'{system_name}' on '{split_name}' already fully evaluated ({start_idx}/{len(records)} rows). Skipping.")
        return

    print(f"\nEvaluating '{system_name}' on '{split_name}' (resuming from {start_idx}/{len(records)} rows)...")

    t0 = time.time()
    mode = "a" if start_idx > 0 else "w"

    with open(output_path, mode, encoding="utf-8") as out_f:
        for idx in range(start_idx, len(records)):
            r = records[idx]
            q_data = r.get("questions", {}).get("tool_route", {})
            state = r.get("state", "")
            query = extract_query(state)
            candidates = q_data.get("criteria", {})
            label = q_data.get("label", "__abstain__")
            package = r.get("package", "default_pkg")
            bfcl_file = r.get("bfcl_file", "")
            has_collision = bool(r.get("has_collision_distractor", False))

            # Score candidates
            if isinstance(system_obj, SoroKevEvaluator):
                probs = system_obj.score(state, candidates)
            else:
                probs = system_obj.score(query, candidates)

            # Normalize probs
            tot_p = sum(probs.values())
            if tot_p > 0:
                probs = {k: v / tot_p for k, v in probs.items()}

            top_tool = max(probs.items(), key=lambda x: x[1])[0]

            # For BFCL: gold can be in gold_functions
            golds = r.get("gold_functions") or []
            if golds and bfcl_file != "BFCL_v3_irrelevance.json" and label != "__abstain__":
                is_correct = (top_tool in golds)
            else:
                is_correct = (top_tool == label)

            if is_correct:
                n_correct += 1

            is_abstain_row = (label == "__abstain__" or bfcl_file == "BFCL_v3_irrelevance.json")
            is_shared_tool = (label in SHARED_TOOLS)

            row_pred = {
                "id": r.get("_row_id", idx),
                "package": package,
                "label": label,
                "top_tool": top_tool,
                "is_correct": is_correct,
                "is_abstain_row": is_abstain_row,
                "is_shared_tool": is_shared_tool,
                "has_collision": has_collision,
                "bfcl_file": bfcl_file,
                "probabilities": {k: round(v, 6) for k, v in probs.items()},
            }
            predictions.append(row_pred)
            out_f.write(json.dumps(row_pred) + "\n")
            out_f.flush()

            if (idx + 1) % 50 == 0 or (idx + 1) == len(records):
                elapsed = time.time() - t0
                rate = (idx + 1) / max(elapsed, 0.001)
                remaining = (len(records) - (idx + 1)) / max(rate, 0.001)
                print(
                    f"  [{idx+1}/{len(records)}] Correct: {n_correct}/{idx+1} ({n_correct/(idx+1)*100:.2f}%) "
                    f"- {elapsed:.1f}s ({rate:.1f} rows/s, ~{remaining:.0f}s left)",
                    flush=True,
                )

    print(f"Saved {len(predictions)} predictions to: {output_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Generate per-row prediction files for all systems")
    parser.add_argument("--split", choices=["external_heldout", "zeroshot", "bfcl", "all"], default="all")
    parser.add_argument("--system", choices=["bm25", "dense_cosine", "cross_encoder", "option_logits", "soro_0.8b", "soro_4b", "all_baselines", "all"], default="all")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    pred_dir = REPO_ROOT / "benchmarks" / "predictions"

    # Datasets
    splits_to_run = []
    if args.split in ("external_heldout", "all"):
        splits_to_run.append(("external_heldout", load_external_dataset()))
    if args.split in ("zeroshot", "all"):
        splits_to_run.append(("zeroshot", load_zeroshot_dataset()))
    if args.split in ("bfcl", "all"):
        splits_to_run.append(("bfcl", load_bfcl_slice()))

    # Systems
    systems = {}
    if args.system in ("bm25", "all_baselines", "all"):
        systems["bm25"] = BM25Scorer()
    if args.system in ("dense_cosine", "all_baselines", "all"):
        systems["dense_cosine"] = DenseCosineScorer()
    if args.system in ("cross_encoder", "all_baselines", "all"):
        systems["cross_encoder"] = CrossEncoderScorer()
    if args.system in ("option_logits", "all_baselines", "all"):
        systems["option_logits"] = UntrainedOptionLogitsScorer()
    if args.system in ("soro_0.8b", "all"):
        ckpt_08 = str(REPO_ROOT / "releases" / "soro-kev-0.8b")
        systems["soro_0.8b"] = SoroKevEvaluator(ckpt_08, device=args.device)
    if args.system in ("soro_4b", "all"):
        ckpt_4b = str(REPO_ROOT / "releases" / "soro-kev-4b")
        systems["soro_4b"] = SoroKevEvaluator(ckpt_4b, device=args.device)

    for split_name, dataset in splits_to_run:
        for sys_name, sys_obj in systems.items():
            out_file = pred_dir / split_name / f"{sys_name}.jsonl"
            evaluate_system_on_dataset(sys_name, sys_obj, dataset, split_name, out_file)


if __name__ == "__main__":
    main()
