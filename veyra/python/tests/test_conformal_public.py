import numpy as np

from soro.routing.conformal import (
    conformal_quantile,
    evaluate_sets,
    gold_ranks,
    run_methods_on_split,
    _sets_rank,
    _split,
)


def test_order_statistic_quantile():
    # 10 points 0..9; alpha=0.1 → ceil(11*0.9)=10 → 10th smallest = 9
    x = np.arange(10, dtype=np.float64)
    assert conformal_quantile(x, 0.1) == 9.0


def test_rank_conformal_matches_fixed_k_on_easy_data():
    n, m = 100, 10
    scores = np.zeros((n, m), dtype=np.float64)
    gold = np.arange(n) % m
    for i, g in enumerate(gold):
        scores[i, g] = 1.0
        # second place
        scores[i, (g + 1) % m] = 0.5
    cal, te = _split(n, 0)
    out = run_methods_on_split(scores, gold, cal, te, alphas=(0.1,))
    rank = out["rank_conformal"]["alpha=0.1"]
    assert rank["empirical_coverage"] >= 0.85
    assert rank["k_hat"] >= 1


def test_gold_ranks_best_is_one():
    scores = np.array([[0.1, 0.9, 0.2]], dtype=np.float64)
    gold = np.array([1])
    assert gold_ranks(scores, gold)[0] == 1


def test_no_argmax_fallback_inflates_coverage():
    """Below-threshold top-1 gold must NOT be rescued into the set."""
    from soro.routing.conformal import _sets_score_threshold

    # gold=0 has score 0.1; threshold requires >= 0.5 → empty set
    scores = np.array([[0.1, 0.05, 0.02]], dtype=np.float64)
    sets = _sets_score_threshold(scores, q_hat=-0.5)  # thresh=0.5
    assert sets[0] == []
