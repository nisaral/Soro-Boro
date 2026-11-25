"""Shift-adaptive conformal calibration and non-generative JEPA energy heads.

Implements:
1. Exact Tibshirani et al. (2019) weighted split-conformal quantile.
2. MenuShiftEstimator for detecting menu-level crowding / squatter attacks.
3. ContextTargetJEPAHead (RequestToToolJEPA + CrossModalVisualJEPA) for
   non-generative predictive energy with strict stop-gradient targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def weighted_conformal_quantile(
    cal_scores: Sequence[float] | np.ndarray,
    cal_weights: Sequence[float] | np.ndarray,
    test_weight: float,
    alpha: float = 0.10,
) -> float:
    """Exact Tibshirani et al. (2019) weighted split-conformal quantile.

    Computes normalized weights:
        p_j = w_j / (sum_m w_m + w_test)
        p_{n+1} = w_test / (sum_m w_m + w_test)

    Returns Quantile_{1 - alpha}(sum_j p_j delta_{s_j} + p_{n+1} delta_{+inf}).
    When p_{n+1} > alpha (high covariate/menu shift), returns float("inf")
    so the full protected set P is retained intact (safe ASK/DEFER).
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    scores = np.asarray(cal_scores, dtype=np.float64)
    weights = np.asarray(cal_weights, dtype=np.float64)

    if scores.ndim != 1 or weights.ndim != 1 or len(scores) != len(weights):
        raise ValueError("cal_scores and cal_weights must be 1D arrays of equal length.")
    if len(scores) == 0:
        return float("inf")
    if np.any(weights < 0) or test_weight < 0:
        raise ValueError("Weights must be non-negative.")

    total_weight = float(np.sum(weights)) + float(test_weight)
    if total_weight <= 0.0:
        return float("inf")

    p_test = float(test_weight) / total_weight
    if p_test > alpha:
        return float("inf")

    p_cal = weights / total_weight
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_p = p_cal[order]

    cum_p = np.cumsum(sorted_p)
    target = 1.0 - alpha
    # Small tolerance for floating-point accumulation
    idx = int(np.searchsorted(cum_p, target - 1e-12, side="left"))
    if idx >= len(sorted_scores):
        return float("inf")
    return float(sorted_scores[idx])


def extract_menu_features(
    logits: Sequence[float] | np.ndarray,
    delta: float = 1.0,
) -> np.ndarray:
    """Extract menu-level crowding & uncertainty features from isolated logits.

    Features (4D):
        0: top1 - top2 logit margin (0.0 if K < 2)
        1: number of candidates within `delta` of max logit (cluster crowding)
        2: softmax logit entropy
        3: max pre-refiner logit score
    """
    arr = np.asarray(logits, dtype=np.float64)
    if arr.ndim != 1 or len(arr) == 0:
        return np.zeros(4, dtype=np.float64)

    max_val = float(np.max(arr))
    if len(arr) >= 2:
        sorted_vals = np.sort(arr)[::-1]
        margin = float(sorted_vals[0] - sorted_vals[1])
    else:
        margin = 0.0

    crowding = float(np.sum(arr >= (max_val - delta)))

    shifted = arr - max_val
    exp_s = np.exp(shifted)
    probs = exp_s / np.sum(exp_s)
    entropy = float(-np.sum(probs * np.log(np.clip(probs, 1e-12, 1.0))))

    return np.array([margin, crowding, entropy, max_val], dtype=np.float64)


class MenuShiftEstimator:
    """Lightweight logistic density-ratio shift estimator on menu-level features.

    Estimates importance weights w_menu(q, C) = P_target(x) / P_source(x)
    from menu-level features (margin, crowding, entropy, max_logit) without
    requiring any query prefix shift.
    """

    def __init__(
        self,
        delta: float = 1.0,
        l2_reg: float = 1.0,
        lr: float = 0.1,
        steps: int = 300,
        w_min: float = 0.1,
        w_max: float = 50.0,
    ) -> None:
        self.delta = delta
        self.l2_reg = l2_reg
        self.lr = lr
        self.steps = steps
        self.w_min = w_min
        self.w_max = w_max
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.prior_ratio_: float = 1.0

    def featurize_batch(self, menus: Sequence[Sequence[float] | np.ndarray]) -> np.ndarray:
        """Convert a list of per-menu logit arrays into an (N, 4) feature matrix."""
        return np.vstack([extract_menu_features(m, delta=self.delta) for m in menus])

    def fit(
        self,
        cal_menus: Sequence[Sequence[float] | np.ndarray],
        shift_menus: Sequence[Sequence[float] | np.ndarray],
    ) -> "MenuShiftEstimator":
        """Fit binary logistic classifier distinguishing shifted menus (y=1) from cal (y=0)."""
        x_cal = self.featurize_batch(cal_menus)
        x_shift = self.featurize_batch(shift_menus)
        x = np.vstack([x_cal, x_shift])
        y = np.concatenate([np.zeros(len(x_cal)), np.ones(len(x_shift))])

        self.mean_ = np.mean(x, axis=0)
        self.std_ = np.where(np.std(x, axis=0) > 1e-6, np.std(x, axis=0), 1.0)
        x_norm = (x - self.mean_) / self.std_

        self.prior_ratio_ = float(len(x_cal)) / max(1.0, float(len(x_shift)))

        w = np.zeros(x_norm.shape[1], dtype=np.float64)
        b = 0.0
        n = float(len(y))
        for _ in range(self.steps):
            logits = x_norm @ w + b
            probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
            diff = probs - y
            grad_w = (x_norm.T @ diff) / n + (self.l2_reg / n) * w
            grad_b = float(np.mean(diff))
            w -= self.lr * grad_w
            b -= self.lr * grad_b

        self.coef_ = w
        self.intercept_ = b
        return self

    def predict_weights(
        self,
        menus: Sequence[Sequence[float] | np.ndarray],
    ) -> np.ndarray:
        """Return calibrated non-negative importance weights w_menu(q, C)."""
        if self.coef_ is None or self.mean_ is None or self.std_ is None:
            raise RuntimeError("MenuShiftEstimator must be fitted before calling predict_weights.")
        x = self.featurize_batch(menus)
        x_norm = (x - self.mean_) / self.std_
        logits = x_norm @ self.coef_ + self.intercept_
        p_shift = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        p_shift = np.clip(p_shift, 1e-4, 1.0 - 1e-4)
        odds = (p_shift / (1.0 - p_shift)) * self.prior_ratio_
        return np.clip(odds, self.w_min, self.w_max)


class RequestToToolJEPA(nn.Module):
    """Stage 1 JEPA predictor: P_phi(h_q) -> z_hat_q with stop-grad candidate target."""

    def __init__(self, query_dim: int, cand_dim: int, hidden_dim: int = 256) -> None:
        super().__init__()
        self.predictor = nn.Sequential(
            nn.Linear(query_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, cand_dim),
        )

    def forward(self, h_q: torch.Tensor) -> torch.Tensor:
        """Predict target candidate embedding z_hat_q from query hidden state h_q."""
        return self.predictor(h_q)

    def energy(self, h_q: torch.Tensor, z_cands: torch.Tensor) -> torch.Tensor:
        """Compute nonconformity energy E_1(q, c_i) = ||z_hat_q - sg(z_c_i)||_2^2.

        Supports h_q of shape (D,) or (B, D) and z_cands of shape (K, D_c) or (B, K, D_c).
        """
        z_hat = self.forward(h_q)
        z_target = z_cands.detach()
        if z_hat.ndim == 1 and z_target.ndim == 2:
            z_hat = z_hat.unsqueeze(0)
        elif z_hat.ndim == 2 and z_target.ndim == 3:
            z_hat = z_hat.unsqueeze(1)
        return torch.sum((z_hat - z_target) ** 2, dim=-1)

    def loss(self, h_q: torch.Tensor, z_gold: torch.Tensor) -> torch.Tensor:
        """MSE loss against stop-gradient gold candidate embedding sg(z_{c*})."""
        z_hat = self.forward(h_q)
        return F.mse_loss(z_hat, z_gold.detach())


class CrossModalVisualJEPA(nn.Module):
    """Stage 2 JEPA predictor: P_vis(h_q, z_c) -> z_hat_vis vs sg(z_img)."""

    def __init__(
        self,
        query_dim: int,
        cand_dim: int,
        vis_dim: int,
        hidden_dim: int = 256,
    ) -> None:
        super().__init__()
        self.predictor = nn.Sequential(
            nn.Linear(query_dim + cand_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, vis_dim),
        )

    def forward(self, h_q: torch.Tensor, z_cand: torch.Tensor) -> torch.Tensor:
        """Predict expected visual latent z_hat_vis from (h_q, sg(z_cand))."""
        zc = z_cand.detach()
        if h_q.ndim == 1 and zc.ndim == 2:
            hq_exp = h_q.unsqueeze(0).expand(zc.shape[0], -1)
        elif h_q.ndim == 2 and zc.ndim == 3:
            hq_exp = h_q.unsqueeze(1).expand(-1, zc.shape[1], -1)
        else:
            hq_exp = h_q
        return self.predictor(torch.cat([hq_exp, zc], dim=-1))

    def energy(
        self,
        h_q: torch.Tensor,
        z_cand: torch.Tensor,
        z_img: torch.Tensor,
    ) -> torch.Tensor:
        """Compute visual surprise energy E_vis = ||z_hat_vis - sg(z_img)||_2^2."""
        z_hat_vis = self.forward(h_q, z_cand)
        z_img_sg = z_img.detach()
        if z_hat_vis.ndim == 2 and z_img_sg.ndim == 1:
            z_img_sg = z_img_sg.unsqueeze(0)
        elif z_hat_vis.ndim == 3 and z_img_sg.ndim == 2:
            z_img_sg = z_img_sg.unsqueeze(1)
        return torch.sum((z_hat_vis - z_img_sg) ** 2, dim=-1)


@dataclass
class ContextTargetJEPAHead:
    """Combined Stage 1 + Stage 2 non-generative predictive energy head."""

    stage1: RequestToToolJEPA
    stage2: CrossModalVisualJEPA

    @classmethod
    def create(
        cls,
        query_dim: int,
        cand_dim: int,
        vis_dim: int,
        hidden_dim: int = 256,
    ) -> "ContextTargetJEPAHead":
        return cls(
            stage1=RequestToToolJEPA(query_dim, cand_dim, hidden_dim=hidden_dim),
            stage2=CrossModalVisualJEPA(query_dim, cand_dim, vis_dim, hidden_dim=hidden_dim),
        )
