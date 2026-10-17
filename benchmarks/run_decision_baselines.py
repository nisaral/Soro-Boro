"""
Soro-Kev Decision Model Baseline Evaluation Harness
Evaluates competitive decision and retrieval baselines under identical fairness rules:
- Uniform conformal calibration (same calibration split, identical alpha=0.10)
- Cluster bootstrap by package for 95% confidence intervals
- Stratification across clean vs collision distractors
- When2Call 4-way behavioral adapter
"""

import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


# =============================================================================
# 1. Dataset Loading and State Normalization
# =============================================================================

def extract_query(state: str) -> str:
    """Extract clean user request from state prompt."""
    match = re.search(r"User Request:\s*(.+?)(?:\nAgent:|\nPrior tool observation:|\nUser:|$)", state, re.DOTALL)
    if match:
        return match.group(1).strip()
    return state.strip()


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenization."""
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def load_dataset(filepath: str, limit: int | None = None) -> List[Dict[str, Any]]:
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if limit and idx >= limit:
                break
            if line.strip():
                records.append(json.loads(line))
    return records


# =============================================================================
# 2. Baseline Decision Scorers
# =============================================================================

class BM25Scorer:
    """Standalone pure-python BM25Okapi scorer."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_tokens = tokenize(query)
        doc_tokens = {name: tokenize(f"{name} {desc}") for name, desc in candidates.items()}
        N = len(candidates)
        avgdl = sum(len(d) for d in doc_tokens.values()) / max(N, 1)

        # Document frequencies
        df = Counter()
        for d in doc_tokens.values():
            df.update(set(d))

        scores = {}
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
            # Small prior penalty for __abstain__ unless query explicitly signals none
            if name == "__abstain__":
                score = score * 0.5 if score > 0 else 0.1
            scores[name] = max(score, 0.001)

        # Softmax over scores with temperature
        max_s = max(scores.values())
        exp_s = {k: math.exp((v - max_s) / 1.5) for k, v in scores.items()}
        sum_exp = sum(exp_s.values())
        return {k: v / sum_exp for k, v in exp_s.items()}


class DenseCosineScorer:
    """TF-IDF character/word n-gram cosine similarity vector scorer."""

    def __init__(self, num_dims: int = 512):
        self.num_dims = num_dims

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
        scores = {}
        for name, desc in candidates.items():
            if name == "__abstain__":
                c_vec = self._embed("None of the listed tools fit.")
                sim = sum(a * b for a, b in zip(q_vec, c_vec)) * 0.6  # calibration offset
            else:
                c_vec = self._embed(f"{name} {desc}")
                sim = sum(a * b for a, b in zip(q_vec, c_vec))
            scores[name] = max(sim, 0.001)

        max_s = max(scores.values())
        exp_s = {k: math.exp((v - max_s) / 0.15) for k, v in scores.items()}
        sum_exp = sum(exp_s.values())
        return {k: v / sum_exp for k, v in exp_s.items()}


class CrossEncoderScorer:
    """Simulated cross-encoder joint query-tool interaction scorer."""

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        q_tokens = set(tokenize(query))
        scores = {}
        for name, desc in candidates.items():
            if name == "__abstain__":
                scores[name] = 0.2
                continue
            desc_tokens = set(tokenize(f"{name} {desc}"))
            overlap = len(q_tokens & desc_tokens)
            jaccard = overlap / max(len(q_tokens | desc_tokens), 1)
            # Name bonus if token appears in tool name
            name_bonus = 1.5 if any(qt in name.lower() for qt in q_tokens if len(qt) > 3) else 1.0
            score = (overlap * 1.2 + jaccard * 5.0) * name_bonus
            scores[name] = max(score, 0.01)

        max_s = max(scores.values())
        exp_s = {k: math.exp((v - max_s) / 2.0) for k, v in scores.items()}
        sum_exp = sum(exp_s.values())
        return {k: v / sum_exp for k, v in exp_s.items()}


class OptionSFTLogitScorer:
    """Option token logit scorer (simulating plain causal SFT predicting option letters A, B, C, D...)."""

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        # Evaluates candidates in order, applying token length normalization
        q_tokens = set(tokenize(query))
        keys = list(candidates.keys())
        raw_logits = {}
        for idx, k in enumerate(keys):
            if k == "__abstain__":
                raw_logits[k] = 1.0
                continue
            d_tokens = set(tokenize(f"{k} {candidates[k]}"))
            match_count = len(q_tokens & d_tokens)
            # Position-independent logit projection
            raw_logits[k] = match_count * 1.8 + (1.2 if any(qt in k.lower() for qt in q_tokens) else 0.0)

        max_l = max(raw_logits.values())
        exp_l = {k: math.exp((v - max_l) / 1.8) for k, v in raw_logits.items()}
        sum_exp = sum(exp_l.values())
        return {k: v / sum_exp for k, v in exp_l.items()}


class LocalKevWrapper:
    """Wrapper loading the LocalKevScorer from the repository."""

    def __init__(self, backend: str = "deterministic"):
        self.backend = backend
        self.scorer = None
        repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(repo_root / "veyra" / "python" / "src"))
        try:
            from soro.routing.kev_local import LocalKevScorer
            self.scorer = LocalKevScorer(backend=self.backend)
            self.scorer.load()
        except Exception as e:
            print(f"[Warning] Failed to load neural LocalKevScorer ({e}). Falling back to deterministic mode.")
            from soro.routing.kev_local import LocalKevScorer
            self.scorer = LocalKevScorer(backend="deterministic")
            self.scorer.load()

    def score(self, query: str, candidates: Dict[str, str]) -> Dict[str, float]:
        state = f"User Request: {query}"
        questions = {
            "tool_route": {
                "type": "choice",
                "instructions": "Which tool should execute?",
                "criteria": candidates
            }
        }
        res = self.scorer.evaluate_turn(state, questions)
        return res["probabilities"]["tool_route"]


# =============================================================================
# 3. Conformal Calibration Wrapper (Applied Uniformly to ALL Arms)
# =============================================================================

class SplitConformalCalibrator:
    """Split-conformal prediction calibrator."""

    def __init__(self, alpha: float = 0.10):
        self.alpha = alpha
        self.q_hat = 1.0

    def fit(self, probs_list: List[Dict[str, float]], labels: List[str]) -> float:
        """Compute conformal quantile q_hat on calibration set."""
        non_conformity_scores = []
        for probs, label in zip(probs_list, labels):
            p_true = probs.get(label, 1e-6)
            score = 1.0 - p_true
            non_conformity_scores.append(score)

        if not non_conformity_scores:
            self.q_hat = 1.0
            return 1.0

        n = len(non_conformity_scores)
        k = math.ceil((n + 1) * (1.0 - self.alpha)) / n
        k = min(max(k, 0.0), 1.0)
        sorted_scores = sorted(non_conformity_scores)
        idx = min(int(k * n), n - 1)
        self.q_hat = sorted_scores[idx]
        return self.q_hat

    def predict_set(self, probs: Dict[str, float]) -> List[str]:
        """Return prediction set S = {c | p(c) >= 1 - q_hat}."""
        threshold = 1.0 - self.q_hat
        p_set = [c for c, p in probs.items() if p >= threshold]
        if not p_set:
            # Fallback to Top-1 candidate if threshold is strict
            top_candidate = max(probs.items(), key=lambda x: x[1])[0]
            p_set = [top_candidate]
        return p_set

    def classify_action(self, p_set: List[str], top_tool: str) -> str:
        """Classify action boundary: EXECUTE, ASK, ABSTAIN."""
        if top_tool == "__abstain__":
            return "ABSTAIN"
        if len(p_set) == 1:
            return "EXECUTE"
        if 2 <= len(p_set) <= 8:
            return "ASK"
        return "ABSTAIN"


# =============================================================================
# 4. Statistical Evaluation & Cluster Bootstrap by Package
# =============================================================================

def cluster_bootstrap_ci(
    records: List[Dict[str, Any]],
    preds: List[str],
    correct_mask: List[bool],
    set_sizes: List[int],
    n_resamples: int = 1000,
    seed: int = 42
) -> Dict[str, Tuple[float, float]]:
    """Compute 95% confidence intervals via cluster bootstrap resampled by package."""
    random.seed(seed)
    pkg_to_indices = defaultdict(list)
    for idx, r in enumerate(records):
        pkg = r.get("package", "default_pkg")
        pkg_to_indices[pkg].append(idx)

    unique_pkgs = list(pkg_to_indices.keys())
    n_pkgs = len(unique_pkgs)

    acc_samples = []
    set_size_samples = []

    for _ in range(n_resamples):
        sampled_pkgs = random.choices(unique_pkgs, k=n_pkgs)
        sample_indices = []
        for p in sampled_pkgs:
            sample_indices.extend(pkg_to_indices[p])

        if not sample_indices:
            continue

        acc = sum(correct_mask[i] for i in sample_indices) / len(sample_indices)
        mean_set = sum(set_sizes[i] for i in sample_indices) / len(sample_indices)
        acc_samples.append(acc)
        set_size_samples.append(mean_set)

    acc_samples.sort()
    set_size_samples.sort()

    low_idx = int(0.025 * len(acc_samples))
    high_idx = int(0.975 * len(acc_samples))

    return {
        "accuracy_95ci": (round(acc_samples[low_idx], 4), round(acc_samples[high_idx], 4)),
        "mean_set_size_95ci": (round(set_size_samples[low_idx], 4), round(set_size_samples[high_idx], 4))
    }


# =============================================================================
# 5. When2Call 4-Way Behavioral Adapter
# =============================================================================

def when2call_adapter(true_behavior: str, predicted_action: str) -> bool:
    """
    Validates When2Call behavioral alignment:
    - TOOL_CALL <-> EXECUTE
    - FOLLOW_UP <-> ASK
    - UNABLE_TO_ANSWER <-> ABSTAIN
    - DIRECT_ANSWER <-> ABSTAIN (tool router abstains to let conversational LLM handle)
    """
    mapping = {
        "TOOL_CALL": "EXECUTE",
        "FOLLOW_UP": "ASK",
        "UNABLE_TO_ANSWER": "ABSTAIN",
        "DIRECT_ANSWER": "ABSTAIN"
    }
    return mapping.get(true_behavior) == predicted_action


# =============================================================================
# 6. Main Benchmark Runner
# =============================================================================

def run_benchmarks(
    dataset_path: str,
    cal_size: int = 200,
    alpha: float = 0.10,
    limit: int | None = None
) -> Dict[str, Any]:
    print(f"Loading benchmark dataset: {dataset_path}")
    records = load_dataset(dataset_path, limit=limit)
    print(f"Total rows loaded: {len(records)}")

    if len(records) <= cal_size:
        cal_size = int(len(records) * 0.3)
        print(f"Adjusted calibration size to: {cal_size}")

    cal_records = records[:cal_size]
    test_records = records[cal_size:]
    print(f"Split: Calibration = {len(cal_records)} rows | Test = {len(test_records)} rows")

    scorers = {
        "BM25": BM25Scorer(),
        "Dense_Cosine": DenseCosineScorer(),
        "Cross_Encoder": CrossEncoderScorer(),
        "Option_SFT_Logits": OptionSFTLogitScorer(),
        "Soro_Kev_SystemOne": LocalKevWrapper(backend="deterministic")
    }

    results = {}

    for arm_name, scorer in scorers.items():
        print(f"\n--- Running Arm: {arm_name} ---")

        # 1. Calibration Phase
        cal_probs = []
        cal_labels = []
        for r in cal_records:
            q_data = r.get("questions", {}).get("tool_route", {})
            query = extract_query(r.get("state", ""))
            candidates = q_data.get("criteria", {})
            label = q_data.get("label", "__abstain__")
            probs = scorer.score(query, candidates)
            cal_probs.append(probs)
            cal_labels.append(label)

        calibrator = SplitConformalCalibrator(alpha=alpha)
        q_hat = calibrator.fit(cal_probs, cal_labels)
        print(f"[{arm_name}] Calibrated q_hat at alpha={alpha}: {q_hat:.4f}")

        # 2. Test Phase
        test_preds = []
        test_correct = []
        test_covered = []
        test_set_sizes = []
        test_actions = Counter()

        # Stratified buckets
        clean_correct, clean_total = 0, 0
        collision_correct, collision_total = 0, 0

        for r in test_records:
            q_data = r.get("questions", {}).get("tool_route", {})
            query = extract_query(r.get("state", ""))
            candidates = q_data.get("criteria", {})
            label = q_data.get("label", "__abstain__")
            has_col = r.get("has_collision_distractor", False)

            probs = scorer.score(query, candidates)
            top_tool = max(probs.items(), key=lambda x: x[1])[0]
            p_set = calibrator.predict_set(probs)
            action = calibrator.classify_action(p_set, top_tool)

            is_correct = (top_tool == label)
            is_covered = (label in p_set)

            test_preds.append(top_tool)
            test_correct.append(is_correct)
            test_covered.append(is_covered)
            test_set_sizes.append(len(p_set))
            test_actions[action] += 1

            if has_col:
                collision_total += 1
                if is_correct:
                    collision_correct += 1
            else:
                clean_total += 1
                if is_correct:
                    clean_correct += 1

        n_test = len(test_records)
        acc = sum(test_correct) / max(n_test, 1)
        cov = sum(test_covered) / max(n_test, 1)
        mean_set = sum(test_set_sizes) / max(n_test, 1)

        clean_acc = clean_correct / max(clean_total, 1) if clean_total > 0 else 0.0
        collision_acc = collision_correct / max(collision_total, 1) if collision_total > 0 else 0.0

        # Cluster bootstrap CIs by package
        bootstrap_ci = cluster_bootstrap_ci(test_records, test_preds, test_correct, test_set_sizes)

        arm_summary = {
            "top1_accuracy": round(acc, 4),
            "conformal_coverage": round(cov, 4),
            "mean_prediction_set_size": round(mean_set, 4),
            "conformal_q_hat": round(q_hat, 4),
            "misclassification_rate": round(1.0 - acc, 4),
            "actions_breakdown": dict(test_actions),
            "stratification": {
                "clean_rows": {"count": clean_total, "accuracy": round(clean_acc, 4)},
                "collision_rows": {"count": collision_total, "accuracy": round(collision_acc, 4)}
            },
            "cluster_bootstrap_95ci": bootstrap_ci
        }

        print(f"[{arm_name}] Accuracy: {acc*100:.2f}% (95% CI: {bootstrap_ci['accuracy_95ci']})")
        print(f"[{arm_name}] Coverage: {cov*100:.2f}% | Mean Set Size: {mean_set:.2f}")
        print(f"[{arm_name}] Clean Acc: {clean_acc*100:.2f}% vs Collision Acc: {collision_acc*100:.2f}%")
        results[arm_name] = arm_summary

    return results


def main():
    parser = argparse.ArgumentParser(description="Soro-Kev Decision Baseline Benchmark Suite")
    parser.add_argument("--dataset", type=str, default="releases/soro-universal-tool-harness/val_external_human.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to evaluate (default: full)")
    parser.add_argument("--cal_size", type=int, default=300, help="Number of calibration rows")
    parser.add_argument("--alpha", type=float, default=0.10, help="Conformal significance level")
    parser.add_argument("--output", type=str, default="benchmarks/decision_baselines_results.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    ds_path = repo_root / args.dataset if not os.path.isabs(args.dataset) else Path(args.dataset)
    out_path = repo_root / args.output if not os.path.isabs(args.output) else Path(args.output)

    results = run_benchmarks(str(ds_path), cal_size=args.cal_size, alpha=args.alpha, limit=args.limit)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nBenchmark suite complete. Results saved to: {out_path}")


if __name__ == "__main__":
    main()
