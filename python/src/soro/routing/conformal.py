"""Conformal shortlists for tool routing.

Score-threshold (LAC on raw scores), rank-conformal, and softmax-LAC.
Includes Gemini overcoverage diagnostics (order-statistic quantile, 1000-split check).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

from soro.routing.public_bench import ROOT
from soro.routing.public_encoders import _load_public

OUT = Path(__file__).resolve().parents[4] / "reports" / "conformal_public_505.json"
OUT_DEBUG = Path(__file__).resolve().parents[4] / "reports" / "conformal_debug.json"


def _wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom, (centre + margin) / denom


def conformal_quantile(nonconf: np.ndarray, alpha: float) -> float:
    """⌈(n+1)(1-α)⌉-th smallest nonconformity (exact order statistic)."""
    n = len(nonconf)
    k = math.ceil((n + 1) * (1 - alpha))
    if k > n:
        return float("inf")
    return float(np.sort(nonconf)[k - 1])


def evaluate_sets(sets: list[list[int]], gold: np.ndarray) -> dict[str, Any]:
    covered = sum(1 for i, g in enumerate(gold) if int(g) in sets[i])
    n = len(gold)
    sizes = [len(s) for s in sets]
    lo, hi = _wilson(covered, n)
    n_empty = sum(1 for s in sizes if s == 0)
    n_single = sum(1 for s in sizes if s == 1)
    return {
        "n": n,
        "empirical_coverage": round(covered / n, 6),
        "coverage_wilson95": [round(lo, 6), round(hi, 6)],
        "n_covered": covered,
        "mean_set_size": round(float(np.mean(sizes)), 4),
        "median_set_size": float(np.median(sizes)),
        "p90_set_size": float(np.quantile(sizes, 0.9)),
        "max_set_size": int(max(sizes)) if sizes else 0,
        "empty_rate": round(n_empty / n, 4),
        "singleton_rate": round(n_single / n, 4),
        "singleton_precision": round(
            sum(1 for i, s in enumerate(sets) if len(s) == 1 and s[0] == int(gold[i]))
            / max(n_single, 1),
            4,
        ),
        "decision_map": {
            "EXECUTE_candidate_share": round(n_single / n, 4),
            "ASK_share_2_to_8": round(sum(1 for s in sizes if 2 <= s <= 8) / n, 4),
            "ABSTAIN_share_empty_or_gt8": round(sum(1 for s in sizes if s == 0 or s > 8) / n, 4),
        },
    }


def fixed_k_coverage(scores: np.ndarray, gold: np.ndarray, ks: tuple[int, ...] = (1, 5, 10, 20)) -> dict[str, Any]:
    out = {}
    for k in ks:
        hits = sum(1 for i, g in enumerate(gold) if int(g) in np.argsort(scores[i])[::-1][:k])
        n = len(gold)
        lo, hi = _wilson(hits, n)
        out[f"k={k}"] = {
            "empirical_coverage": round(hits / n, 6),
            "coverage_wilson95": [round(lo, 6), round(hi, 6)],
            "mean_set_size": float(k),
        }
    return out


def gold_ranks(scores: np.ndarray, gold: np.ndarray) -> np.ndarray:
    """1-indexed rank of gold (1=best). Ties: worst-case rank among equals (conservative)."""
    ranks = np.empty(len(gold), dtype=np.int64)
    for i, g in enumerate(gold):
        s = scores[i]
        sg = s[g]
        # number of tools strictly better + 1, then add ties-above-or-equal - 1 for worst case among ties
        better = int(np.sum(s > sg))
        tied = int(np.sum(s == sg))
        ranks[i] = better + tied  # worst rank among tied
    return ranks


def score_matrix_cached() -> tuple[np.ndarray, np.ndarray]:
    import faiss

    q = np.load(ROOT / "data" / "cache" / "benchmark_query_vectors_9d876b0b187348ce.npy")
    index = faiss.read_index(str(ROOT / "data" / "cache" / "tools.faiss"))
    meta = json.loads((ROOT / "data" / "cache" / "tools_metadata.json").read_text(encoding="utf-8"))
    rows = []
    with (ROOT / "benchmark" / "dataset.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    op_to_row = {meta[str(i)]["operation_id"]: i for i in range(index.ntotal)}
    gold = np.array([op_to_row[r["expected_operation"]] for r in rows], dtype=np.int64)
    tool_vecs = np.vstack([index.reconstruct(i) for i in range(index.ntotal)]).astype(np.float32)
    scores = q.astype(np.float32) @ tool_vecs.T
    # sanity: reconstructed argmax vs FAISS search
    _, idxs = index.search(q.astype(np.float32), 1)
    agree = float(np.mean(idxs[:, 0] == np.argmax(scores, axis=1)))
    return scores, gold, {"faiss_argmax_agree": round(agree, 6)}


def score_matrix_minilm() -> tuple[np.ndarray, np.ndarray]:
    from soro.routing.encoders import MiniLMEncoder

    docs, queries, gold_list, _ = _load_public()
    enc = MiniLMEncoder()
    d = np.array(enc.encode(docs), dtype=np.float32)
    q = np.array(enc.encode(queries), dtype=np.float32)
    return q @ d.T, np.array(gold_list, dtype=np.int64)


def _sets_score_threshold(scores: np.ndarray, q_hat: float) -> list[list[int]]:
    """Empty sets are allowed. Do NOT fall back to argmax — that inflates coverage
    by rescuing below-threshold top-1 golds (observed Gemini bug: 0.90 → 0.99)."""
    thresh = -q_hat
    return [np.where(row >= thresh)[0].tolist() for row in scores]


def _sets_rank(scores: np.ndarray, k_hat: int) -> list[list[int]]:
    k = max(1, int(k_hat))
    sets = []
    for row in scores:
        top = np.argsort(row)[::-1][:k]
        sets.append(top.tolist())
    return sets


def _softmax_temp(row: np.ndarray, temperature: float) -> np.ndarray:
    t = max(temperature, 1e-6)
    z = row / t
    z = z - np.max(z)
    e = np.exp(z)
    return e / e.sum()


def fit_temperature(scores: np.ndarray, gold: np.ndarray) -> float:
    """Grid-search T to minimize NLL on softmax(scores/T)."""
    best_t, best_nll = 1.0, float("inf")
    for t in np.geomspace(0.05, 5.0, 40):
        nll = 0.0
        for i, g in enumerate(gold):
            p = _softmax_temp(scores[i], float(t))
            nll -= math.log(max(float(p[g]), 1e-12))
        if nll < best_nll:
            best_nll, best_t = nll, float(t)
    return best_t


def _sets_lac_prob(probs: np.ndarray, q_hat: float) -> list[list[int]]:
    # nonconf = 1 - p; include if 1-p <= q_hat ⇔ p >= 1 - q_hat. Empty allowed.
    thresh = 1.0 - q_hat
    return [np.where(row >= thresh)[0].tolist() for row in probs]


def _split(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_cal = n // 2
    return perm[:n_cal], perm[n_cal:]


def run_methods_on_split(
    scores: np.ndarray,
    gold: np.ndarray,
    cal_idx: np.ndarray,
    test_idx: np.ndarray,
    *,
    alphas: tuple[float, ...] = (0.1, 0.05),
) -> dict[str, Any]:
    cal_s, cal_g = scores[cal_idx], gold[cal_idx]
    te_s, te_g = scores[test_idx], gold[test_idx]

    # --- score-threshold (raw cosine LAC) ---
    nonconf_score = -cal_s[np.arange(len(cal_g)), cal_g]
    # --- rank ---
    ranks = gold_ranks(cal_s, cal_g)
    # --- softmax LAC ---
    # nest: fit T on first half of cal, conformal on second half
    n_cal = len(cal_g)
    mid = n_cal // 2
    t_fit = fit_temperature(cal_s[:mid], cal_g[:mid]) if mid >= 10 else 1.0
    cal_probs = np.vstack([_softmax_temp(cal_s[i], t_fit) for i in range(n_cal)])
    te_probs = np.vstack([_softmax_temp(te_s[i], t_fit) for i in range(len(te_g))])
    nonconf_lac = 1.0 - cal_probs[np.arange(n_cal), cal_g]
    # use second half of cal for LAC quantile when possible
    lac_nc = nonconf_lac[mid:] if mid >= 10 else nonconf_lac

    out: dict[str, Any] = {
        "n_cal": int(len(cal_idx)),
        "n_test": int(len(test_idx)),
        "fixed_k_on_test": fixed_k_coverage(te_s, te_g),
        "temperature": round(t_fit, 4),
        "score_threshold": {},
        "rank_conformal": {},
        "softmax_lac": {},
    }
    for alpha in alphas:
        # score threshold
        q_s = conformal_quantile(nonconf_score, alpha)
        sets_s = _sets_score_threshold(te_s, q_s)
        m_s = evaluate_sets(sets_s, te_g)
        # calibration-set coverage for score method
        cal_sets = _sets_score_threshold(cal_s, q_s)
        cal_cov = sum(1 for i, g in enumerate(cal_g) if int(g) in cal_sets[i]) / max(len(cal_g), 1)
        m_s["cal_coverage"] = round(cal_cov, 6)
        m_s["q_hat"] = None if math.isinf(q_s) else round(q_s, 6)
        m_s["alpha"] = alpha
        m_s["target_coverage"] = round(1 - alpha, 4)
        out["score_threshold"][f"alpha={alpha}"] = m_s

        # rank
        q_r = conformal_quantile(ranks.astype(np.float64), alpha)
        k_hat = int(q_r) if not math.isinf(q_r) else int(cal_s.shape[1])
        sets_r = _sets_rank(te_s, k_hat)
        m_r = evaluate_sets(sets_r, te_g)
        m_r["k_hat"] = k_hat
        m_r["alpha"] = alpha
        m_r["target_coverage"] = round(1 - alpha, 4)
        out["rank_conformal"][f"alpha={alpha}"] = m_r

        # softmax LAC
        q_l = conformal_quantile(lac_nc, alpha)
        sets_l = _sets_lac_prob(te_probs, q_l)
        m_l = evaluate_sets(sets_l, te_g)
        m_l["q_hat"] = None if math.isinf(q_l) else round(q_l, 6)
        m_l["alpha"] = alpha
        m_l["target_coverage"] = round(1 - alpha, 4)
        out["softmax_lac"][f"alpha={alpha}"] = m_l

    return out


def diagnose_gemini(scores: np.ndarray, gold: np.ndarray, n_splits: int = 1000, alpha: float = 0.1) -> dict[str, Any]:
    n = len(gold)
    gold_scores = scores[np.arange(n), gold]
    # ties: other tools with same score as gold
    n_tie = sum(1 for i, g in enumerate(gold) if np.sum(np.isclose(scores[i], scores[i, g])) > 1)

    coverages = []
    sizes = []
    cal_coverages = []
    for seed in range(n_splits):
        cal_idx, test_idx = _split(n, seed)
        nonconf = -scores[cal_idx, gold[cal_idx]]
        q_hat = conformal_quantile(nonconf, alpha)
        sets = _sets_score_threshold(scores[test_idx], q_hat)
        te_g = gold[test_idx]
        cov = sum(1 for i, g in enumerate(te_g) if int(g) in sets[i]) / len(te_g)
        coverages.append(cov)
        sizes.append(float(np.mean([len(s) for s in sets])))
        cal_sets = _sets_score_threshold(scores[cal_idx], q_hat)
        cal_g = gold[cal_idx]
        cal_coverages.append(sum(1 for i, g in enumerate(cal_g) if int(g) in cal_sets[i]) / len(cal_g))

    expected = math.ceil((n // 2 + 1) * (1 - alpha)) / (n // 2 + 1)
    return {
        "alpha": alpha,
        "n_splits": n_splits,
        "expected_coverage_approx": round(expected, 6),
        "test_coverage_mean": round(float(np.mean(coverages)), 6),
        "test_coverage_std": round(float(np.std(coverages)), 6),
        "test_coverage_p05": round(float(np.quantile(coverages, 0.05)), 6),
        "test_coverage_p95": round(float(np.quantile(coverages, 0.95)), 6),
        "cal_coverage_mean": round(float(np.mean(cal_coverages)), 6),
        "mean_set_size_mean": round(float(np.mean(sizes)), 4),
        "gold_score_min": round(float(gold_scores.min()), 6),
        "gold_score_p10": round(float(np.quantile(gold_scores, 0.1)), 6),
        "gold_score_median": round(float(np.median(gold_scores)), 6),
        "n_queries_with_tied_gold_score": int(n_tie),
        "overcoverage_vs_nominal": round(float(np.mean(coverages)) - (1 - alpha), 6),
    }


def conditional_by_margin(scores: np.ndarray, gold: np.ndarray, sets: list[list[int]], n_bins: int = 4) -> dict[str, Any]:
    margins = []
    for i, g in enumerate(gold):
        row = scores[i]
        top2 = np.sort(row)[-2:]
        margins.append(float(top2[-1] - top2[-2]))
    margins = np.array(margins)
    qs = np.quantile(margins, np.linspace(0, 1, n_bins + 1))
    slices = {}
    for b in range(n_bins):
        lo, hi = qs[b], qs[b + 1]
        if b < n_bins - 1:
            mask = (margins >= lo) & (margins < hi)
        else:
            mask = (margins >= lo) & (margins <= hi)
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            continue
        cov = sum(1 for i in idxs if int(gold[i]) in sets[i]) / len(idxs)
        mean_sz = float(np.mean([len(sets[i]) for i in idxs]))
        slices[f"margin_bin_{b}"] = {
            "n": int(len(idxs)),
            "margin_range": [round(float(lo), 4), round(float(hi), 4)],
            "empirical_coverage": round(cov, 6),
            "mean_set_size": round(mean_sz, 4),
        }
    worst = min(slices.values(), key=lambda d: d["empirical_coverage"]) if slices else {}
    return {"slices": slices, "worst_slice_coverage": worst.get("empirical_coverage")}


def cross_dataset_v2(public_scores: np.ndarray, public_gold: np.ndarray, alpha: float = 0.1) -> dict[str, Any]:
    """Calibrate score-threshold + rank on full public 505; evaluate MiniLM on v2 (different catalog — expect break)."""
    try:
        from soro.routing.encoders import MiniLMEncoder
        from soro.routing.eval_v2 import load_frozen
        from soro.routing.expand import expand_document
        from soro.routing.scale import ToolSpec
    except Exception as exc:
        return {"status": "skipped", "error": str(exc)[:200]}

    # Calibrate on public MiniLM is wrong for cross-catalog; calibrate on public gemini rank k,
    # then on v2 use MiniLM ranks — still a shift. Better: calibrate rank-conformal on public MiniLM
    # doesn't transfer to v2 tools. Cross-dataset = cal on public MiniLM scores can't score v2 tools.
    # So: train quantile on public, apply same *rank* k_hat on v2 MiniLM rankings.
    nonconf_rank = gold_ranks(public_scores, public_gold).astype(np.float64)
    k_hat = int(conformal_quantile(nonconf_rank, alpha))
    specs, queries, _ = load_frozen()
    texts = [q["text"] for q in queries]
    gold_names = [q["gold"] for q in queries]
    name_to_i = {s.name: i for i, s in enumerate(specs)}
    gold_idx = np.array([name_to_i[g] for g in gold_names], dtype=np.int64)
    enc = MiniLMEncoder()
    docs = [expand_document(s) for s in specs]  # expanded; also try plain
    docs_plain = [f"{s.name} {s.description}" for s in specs]
    d = np.array(enc.encode(docs_plain), dtype=np.float32)
    q = np.array(enc.encode(texts), dtype=np.float32)
    scores = q @ d.T
    sets = _sets_rank(scores, k_hat)
    metrics = evaluate_sets(sets, gold_idx)
    metrics["k_hat_from_public"] = k_hat
    metrics["alpha"] = alpha
    metrics["note"] = "Rank k calibrated on public MiniLM (same encoder family), applied to v2 catalog — distribution shift expected."
    return metrics


def run_full() -> dict[str, Any]:
    gem_pack = score_matrix_cached()
    gem_scores, gem_gold, gem_meta = gem_pack
    mini_scores, mini_gold = score_matrix_minilm()

    cal_idx, test_idx = _split(len(gem_gold), seed=7)
    # use same indices for both encoders (aligned by query order)
    gem = run_methods_on_split(gem_scores, gem_gold, cal_idx, test_idx)
    mini = run_methods_on_split(mini_scores, mini_gold, cal_idx, test_idx)

    # conditional coverage for MiniLM rank-conformal α=0.1
    ranks_cal = gold_ranks(mini_scores[cal_idx], mini_gold[cal_idx])
    k_hat = int(conformal_quantile(ranks_cal.astype(np.float64), 0.1))
    mini_sets = _sets_rank(mini_scores[test_idx], k_hat)
    cond = conditional_by_margin(mini_scores[test_idx], mini_gold[test_idx], mini_sets)

    diag = diagnose_gemini(gem_scores, gem_gold, n_splits=1000, alpha=0.1)
    diag["faiss_reconstruct"] = gem_meta

    # calibration-curve: coverage vs n_cal for rank-conformal on MiniLM
    curve = []
    for n_cal in (25, 50, 100, 200):
        covs, szs = [], []
        for seed in range(50):
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(mini_gold))
            if n_cal >= len(mini_gold) - 50:
                continue
            c_idx, t_idx = perm[:n_cal], perm[n_cal:]
            r = gold_ranks(mini_scores[c_idx], mini_gold[c_idx]).astype(np.float64)
            k = int(conformal_quantile(r, 0.1))
            sets = _sets_rank(mini_scores[t_idx], k)
            m = evaluate_sets(sets, mini_gold[t_idx])
            covs.append(m["empirical_coverage"])
            szs.append(m["mean_set_size"])
        if covs:
            curve.append(
                {
                    "n_cal": n_cal,
                    "coverage_mean": round(float(np.mean(covs)), 4),
                    "coverage_std": round(float(np.std(covs)), 4),
                    "mean_set_size_mean": round(float(np.mean(szs)), 4),
                }
            )

    cross = cross_dataset_v2(mini_scores, mini_gold, alpha=0.1)

    # catalog growth: public MiniLM scores vs public+noise distractors (pad with random unit vectors)
    growth = []
    rng = np.random.default_rng(0)
    q_dim = mini_scores.shape  # (505, 101) — need query vecs. Recompute from scores only: can't add distractors without vecs.
    # approximate: add random score columns ~ N(mean distractor, std)
    for extra in (0, 50, 100, 200, 400):
        if extra == 0:
            s = mini_scores
        else:
            noise = rng.normal(loc=float(mini_scores.mean()), scale=float(mini_scores.std()) * 0.5, size=(mini_scores.shape[0], extra))
            s = np.hstack([mini_scores, noise.astype(np.float32)])
        c_idx, t_idx = _split(len(mini_gold), 7)
        r = gold_ranks(s[c_idx], mini_gold[c_idx]).astype(np.float64)
        k = int(conformal_quantile(r, 0.1))
        sets = _sets_rank(s[t_idx], k)
        m = evaluate_sets(sets, mini_gold[t_idx])
        growth.append({"n_tools": int(s.shape[1]), "k_hat": k, "coverage": m["empirical_coverage"], "mean_set_size": m["mean_set_size"]})

    return {
        "claim_scope": (
            "Bug fixed: empty→argmax fallback was rescuing below-threshold top-1 golds "
            "(Gemini cal coverage identity 0.90 vs set coverage 0.99). Empty sets now allowed (= miss / ABSTAIN). "
            "Rank-conformal is the efficient guaranteed baseline. Softmax-LAC often smaller sets. "
            "Fixed-k has no finite-sample guarantee on new data. Cross-dataset shift breaks coverage."
        ),
        "gemini_diagnostics_1000_splits": diag,
        "gemini_cached": gem,
        "minilm": mini,
        "minilm_rank_conditional_margin": cond,
        "minilm_rank_coverage_vs_n_cal": curve,
        "cross_dataset_public_rank_to_v2": cross,
        "catalog_growth_rank_conformal": growth,
    }


def write_full(path: Path | None = None) -> dict[str, Any]:
    data = run_full()
    out = path or OUT_DEBUG
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # also refresh summary path
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    data["written"] = str(out)
    return data
