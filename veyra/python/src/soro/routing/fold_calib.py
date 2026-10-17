"""5-fold margin calibration. Cutoff fit on train folds only."""

from __future__ import annotations

from typing import Any


def _cutoff(dev: list[tuple[float, bool]], target: float) -> float:
    rows = sorted(dev, key=lambda x: x[0], reverse=True)
    best = max((c for c, _ in rows), default=1.0)
    tp = 0
    found = False
    for i, (c, ok) in enumerate(rows, start=1):
        tp += int(ok)
        if tp / i >= target:
            best = c
            found = True
    return best if found else 1e9


def five_fold_margin(margins: list[float], correct: list[bool], target: float = 0.90) -> dict[str, Any]:
    n = len(margins)
    fold = n // 5
    covered_ok = []
    covered_n = 0
    test_n = 0
    for f in range(5):
        te = list(range(f * fold, n if f == 4 else (f + 1) * fold))
        tr = [i for i in range(n) if i not in te]
        dev = [(margins[i], correct[i]) for i in tr]
        cut = _cutoff(dev, target)
        for i in te:
            test_n += 1
            if margins[i] >= cut:
                covered_n += 1
                covered_ok.append(int(correct[i]))
    cov = covered_n / max(test_n, 1)
    prec = sum(covered_ok) / max(len(covered_ok), 1)
    # Wilson-ish via bootstrap-on-covered would be better; binomial on coverage
    return {
        "target_precision": target,
        "pooled_coverage": round(cov, 4),
        "pooled_precision": round(prec, 4),
        "n_test_pooled": test_n,
        "n_covered": covered_n,
        "n_correct_when_covered": int(sum(covered_ok)),
    }
