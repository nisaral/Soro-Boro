from pathlib import Path

from veyra.analysis.headroom import Trial, summarize


def test_identical_harnesses_have_zero_net_headroom():
    trials = []
    for h in ("a", "b"):
        for seed in ("1", "2", "3"):
            trials.append(Trial("t1", h, seed, passed=seed == "3", cost=1.0))
    s = summarize(trials)
    # Both harnesses pass on seed 3 only, so oracle = 1 and same-harness best-of-3 = 1.
    assert s["net_headroom_mean"] == 0.0
    assert s["gate1_stop"] is True


def test_true_switch_headroom_is_the_excess_over_resampling():
    trials = [
        Trial("t1", "h1", "1", False, 1.0),
        Trial("t1", "h1", "2", False, 1.0),
        Trial("t1", "h1", "3", False, 1.0),
        Trial("t1", "h2", "1", True, 1.0),
        Trial("t1", "h2", "2", True, 1.0),
        Trial("t1", "h2", "3", True, 1.0),
    ]
    s = summarize(trials)
    # Oracle 1, mean same-harness (0 + 1) / 2 = 0.5, net = 0.5
    assert abs(s["net_headroom_mean"] - 0.5) < 1e-9
    assert s["gate1_stop"] is False
