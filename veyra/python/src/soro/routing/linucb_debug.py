"""Synthetic linear bandit sanity: if wiring is correct, regret must fall."""

from __future__ import annotations

import random
from typing import Any

import numpy as np


def run_linear_sanity(steps: int = 800, n_arms: int = 5, dim: int = 4, seed: int = 0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    true_theta = rng.normal(size=(n_arms, dim))
    A = [np.eye(dim) for _ in range(n_arms)]
    b = [np.zeros(dim) for _ in range(n_arms)]
    updates = 0
    regret = 0.0
    curve = []
    alpha = 0.4
    for t in range(1, steps + 1):
        x = rng.normal(size=dim)
        x /= np.linalg.norm(x) + 1e-9
        means = true_theta @ x
        opt = int(np.argmax(means))
        ucb = []
        for a in range(n_arms):
            Ainv = np.linalg.inv(A[a])
            theta = Ainv @ b[a]
            ucb.append(float(theta @ x + alpha * np.sqrt(x @ Ainv @ x)))
        pick = int(np.argmax(ucb))
        reward = float(means[pick] + rng.normal() * 0.05)
        A[pick] += np.outer(x, x)
        b[pick] += reward * x
        updates += 1
        regret += float(means[opt] - means[pick])
        if t in (50, 200, 400, 800):
            curve.append({"t": t, "avg_regret": round(regret / t, 4), "updates": updates})
    return {
        "updates": updates,
        "final_avg_regret": round(regret / steps, 4),
        "curve": curve,
        "learned": curve[-1]["avg_regret"] < curve[0]["avg_regret"] * 0.7,
    }


def run_epsilon_greedy(steps: int = 800, n_arms: int = 5, dim: int = 4, seed: int = 0, eps: float = 0.1) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    py = random.Random(seed)
    true_theta = rng.normal(size=(n_arms, dim))
    counts = np.zeros(n_arms)
    sums = np.zeros(n_arms)
    regret = 0.0
    for t in range(1, steps + 1):
        x = rng.normal(size=dim)
        x /= np.linalg.norm(x) + 1e-9
        means = true_theta @ x
        opt = int(np.argmax(means))
        if py.random() < eps:
            pick = py.randrange(n_arms)
        else:
            avg = np.divide(sums, np.maximum(counts, 1))
            pick = int(np.argmax(avg))
        reward = float(means[pick] + rng.normal() * 0.05)
        counts[pick] += 1
        sums[pick] += reward
        regret += float(means[opt] - means[pick])
    return {"final_avg_regret": round(regret / steps, 4), "updates": steps}


def run_thompson(steps: int = 800, n_arms: int = 5, seed: int = 0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    true = rng.uniform(0.1, 0.9, size=n_arms)
    alpha = np.ones(n_arms)
    beta = np.ones(n_arms)
    regret = 0.0
    opt = int(np.argmax(true))
    for t in range(1, steps + 1):
        sample = rng.beta(alpha, beta)
        pick = int(np.argmax(sample))
        r = 1.0 if rng.random() < true[pick] else 0.0
        alpha[pick] += r
        beta[pick] += 1 - r
        regret += float(true[opt] - true[pick])
    return {"final_avg_regret": round(regret / steps, 4), "updates": steps}
