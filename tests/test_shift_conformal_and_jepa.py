"""Unit tests for shift-adaptive conformal calibration and JEPA energy heads."""

from __future__ import annotations

import numpy as np
import torch

from soro.routing.shift_conformal import (
    ContextTargetJEPAHead,
    MenuShiftEstimator,
    weighted_conformal_quantile,
)


def _split_conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Standard finite-sample split-conformal quantile: ceil((n+1)*(1-alpha))/n."""
    n = len(scores)
    q_level = min(1.0, np.ceil((n + 1) * (1.0 - alpha)) / n)
    sorted_s = np.sort(scores)
    idx = int(np.ceil(q_level * n)) - 1
    idx = max(0, min(n - 1, idx))
    return float(sorted_s[idx])


def test_tibshirani_infinite_deferral_on_high_shift() -> None:
    """When p_{n+1} > alpha, weighted_conformal_quantile must return +inf (full P retained)."""
    cal_scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    cal_weights = np.ones_like(cal_scores)
    # sum(cal_weights) = 10. With test_weight = 2.0, p_{n+1} = 2 / 12 = 0.1667 > alpha=0.10
    tau_w = weighted_conformal_quantile(cal_scores, cal_weights, test_weight=2.0, alpha=0.10)
    assert tau_w == float("inf"), f"Expected +inf on high shift, got {tau_w}"

    # Verify Stage 2 retains full protected set P when tau_w = +inf
    cand_energies = np.array([0.15, 0.45, 2.3, 9.8])
    protected_set = [i for i, e in enumerate(cand_energies) if e <= tau_w]
    assert protected_set == [0, 1, 2, 3], "Full protected set P must be retained on +inf deferral."


def test_tibshirani_reduces_to_split_conformal_when_weights_equal() -> None:
    """When all weights == 1.0, weighted_conformal_quantile equals standard split-conformal."""
    rng = np.random.default_rng(42)
    for alpha in (0.05, 0.10, 0.20):
        cal_scores = rng.uniform(0.0, 5.0, size=99)
        cal_weights = np.ones_like(cal_scores)
        tau_w = weighted_conformal_quantile(cal_scores, cal_weights, test_weight=1.0, alpha=alpha)
        tau_split = _split_conformal_quantile(cal_scores, alpha=alpha)
        assert abs(tau_w - tau_split) < 1e-12, (
            f"Mismatch at alpha={alpha}: weighted={tau_w} vs split={tau_split}"
        )


def test_menu_shift_detects_squatter_crowding() -> None:
    """MenuShiftEstimator assigns higher shift weights when lookalikes crowd the menu."""
    rng = np.random.default_rng(7)
    # Clean menus: 1 clear winner, 3 low-scoring distractors
    cal_menus = [
        np.array([5.0, 0.2, -0.5, -1.2]) + rng.normal(0, 0.15, size=4)
        for _ in range(100)
    ]
    # Shifted / squatter-crowded menus: 3 near-duplicate high-scoring candidates
    shift_menus = [
        np.array([4.9, 4.8, 4.75, -1.0]) + rng.normal(0, 0.15, size=4)
        for _ in range(100)
    ]

    est = MenuShiftEstimator(delta=1.0, steps=400).fit(cal_menus, shift_menus)
    w_clean = est.predict_weights([np.array([5.1, 0.1, -0.6, -1.3])])[0]
    w_crowded = est.predict_weights([np.array([4.95, 4.85, 4.80, -0.9])])[0]
    assert w_crowded > w_clean * 2.0, (
        f"Expected crowded menu weight ({w_crowded:.3f}) >> clean ({w_clean:.3f})"
    )


def test_jepa_energy_shapes_and_stopgrad() -> None:
    """Verify JEPA energy shapes and zero gradient leakage into frozen candidate/vision encoders."""
    torch.manual_seed(0)
    head = ContextTargetJEPAHead.create(query_dim=16, cand_dim=12, vis_dim=8, hidden_dim=32)

    h_q = torch.randn(4, 16, requires_grad=True)
    z_cands = torch.randn(4, 5, 12, requires_grad=True)
    z_gold = torch.randn(4, 12, requires_grad=True)
    z_img = torch.randn(4, 8, requires_grad=True)

    # Stage 1 energy & loss
    e1 = head.stage1.energy(h_q, z_cands)
    assert e1.shape == (4, 5)
    loss1 = head.stage1.loss(h_q, z_gold)
    loss1.backward()
    assert z_gold.grad is None, "Stop-gradient violated on Stage 1 gold target!"

    # Stage 2 visual surprise energy
    e_vis = head.stage2.energy(h_q, z_cands, z_img)
    assert e_vis.shape == (4, 5)
    e_vis.sum().backward()
    assert z_cands.grad is None, "Stop-gradient violated on Stage 2 candidate embedding!"
    assert z_img.grad is None, "Stop-gradient violated on Stage 2 vision embedding!"
