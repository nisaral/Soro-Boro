"""Veyra Policy: Learning, Risk Partitioning, Contextual Bandits & Off-Policy Evaluation (Phase 9 Specification).

Implements risk-partitioned exploration and offline ranking/evaluation:
1. Risk Partitioning:
   - READ_ONLY: Safe for cautious exploration (LinUCB alpha > 0, epsilon exploration).
   - SIDE_EFFECTING: Zero exploration allowed (alpha = 0, epsilon = 0). Pure greedy / deterministic.
2. Contextual Bandits:
   - Feature extractor for execution context and candidate actions.
   - LinUCB / Thompson Sampling with strict risk partitioning.
3. Pairwise Ranking:
   - Bradley-Terry logistic preference model fit on logged pairwise comparisons.
4. Off-Policy Evaluation (OPE):
   - Inverse Propensity Scoring (IPS), Direct Method (DM), and Doubly Robust (DR) estimation.
5. Falsification Evaluation:
   - Compares learned policies against deterministic and TAGE-style baselines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import numpy as np

from soro.boundary.taxonomy import FailureProvenance
from soro.core.action import ExecutableAction
from soro.core.decision import Decision, DecisionKind
from soro.core.state import ExecutionState
from soro.policy.base import RoutePolicy


class RiskLevel(str, Enum):
    """Execution risk classification for tool operations."""

    READ_ONLY = "read_only"
    SIDE_EFFECTING = "side_effecting"


# Recognized mutating/side-effecting verb prefixes
MUTATING_PREFIXES = (
    "write",
    "update",
    "delete",
    "post",
    "patch",
    "create",
    "drop",
    "insert",
    "set",
    "send",
    "modify",
    "exec",
    "remove",
    "destroy",
    "kill",
    "truncate",
)

READ_ONLY_PREFIXES = (
    "read",
    "get",
    "fetch",
    "query",
    "search",
    "lookup",
    "find",
    "list",
    "check",
    "inspect",
    "count",
    "describe",
    "view",
    "cat",
)


def classify_risk(
    action: ExecutableAction | str,
    metadata: dict[str, Any] | None = None,
) -> RiskLevel:
    """Classify an action into READ_ONLY or SIDE_EFFECTING.

    Defensive principle: If unknown or ambiguous, default to SIDE_EFFECTING.
    """
    if isinstance(action, ExecutableAction):
        tool_name = action.tool.lower()
        meta = action.metadata
    else:
        tool_name = str(action).lower()
        meta = metadata or {}

    # Explicit metadata overrides
    if meta.get("idempotent") is True or meta.get("read_only") is True:
        return RiskLevel.READ_ONLY
    if meta.get("is_mutation") is True or meta.get("mutating") is True:
        return RiskLevel.SIDE_EFFECTING
    if meta.get("risk_class") in ("high", "critical", "mutating"):
        return RiskLevel.SIDE_EFFECTING
    if meta.get("risk_class") in ("read_only", "safe", "zero"):
        return RiskLevel.READ_ONLY

    # Verb prefix heuristics
    for prefix in MUTATING_PREFIXES:
        if tool_name.startswith(prefix) or f"_{prefix}" in tool_name:
            return RiskLevel.SIDE_EFFECTING

    for prefix in READ_ONLY_PREFIXES:
        if tool_name.startswith(prefix) or f"_{prefix}" in tool_name:
            return RiskLevel.READ_ONLY

    # Fallback default: defensive side-effecting
    return RiskLevel.SIDE_EFFECTING


# Feature representation dimension
FEATURE_DIM = 18

ALL_PROVENANCES = [
    FailureProvenance.AGENT_ARGUMENT_ERROR.value,
    FailureProvenance.SCHEMA_VALIDATION_ERROR.value,
    FailureProvenance.TOOL_IMPLEMENTATION_ERROR.value,
    FailureProvenance.NETWORK_ERROR.value,
    FailureProvenance.RATE_LIMIT.value,
    FailureProvenance.TIMEOUT.value,
    FailureProvenance.AUTHORIZATION_ERROR.value,
    FailureProvenance.PRECONDITION_ERROR.value,
    FailureProvenance.UNKNOWN_STATE.value,
    FailureProvenance.UNKNOWN.value,
]


class ContextFeatureExtractor:
    """Extracts a fixed-size normalized feature vector from execution context and candidates."""

    @staticmethod
    def extract(
        state: ExecutionState,
        candidate: ExecutableAction,
        proposal: ExecutableAction | None = None,
    ) -> np.ndarray:
        """Constructs an 18-dimensional feature vector.

        Features:
        [0]: Bias term (1.0)
        [1-10]: One-hot encoding of failure provenance (10 frozen values)
        [11]: Turn index normalized (turn / 10.0)
        [12]: Exact tool name match with proposal (0 or 1)
        [13]: In same equivalence group (0 or 1)
        [14]: Candidate risk class (0 for READ_ONLY, 1 for SIDE_EFFECTING)
        [15]: Candidate is idempotent (0 or 1)
        [16]: Prior reliability estimate (from metadata or default 0.5)
        [17]: Latency estimate normalized (est_sec / 5.0)
        """
        vec = np.zeros(FEATURE_DIM, dtype=float)
        vec[0] = 1.0  # Bias

        # 1-10: Failure provenance one-hot
        prov = state.context.get("failure_provenance")
        if prov:
            prov_str = prov.value if hasattr(prov, "value") else str(prov)
            for idx, p_name in enumerate(ALL_PROVENANCES):
                if prov_str == p_name:
                    vec[1 + idx] = 1.0
                    break

        # 11: Turn index
        step = getattr(state, "step", 1) or 1
        vec[11] = min(float(step) / 10.0, 1.0)

        # 12: Exact tool match
        p_tool = proposal.tool if proposal else state.context.get("proposed_tool", "")
        if p_tool and candidate.tool == p_tool:
            vec[12] = 1.0

        # 13: Same equivalence group
        c_eq = candidate.equivalence_group or candidate.metadata.get("equivalence_group")
        p_eq = proposal.equivalence_group if proposal else state.context.get("equivalence_group")
        if c_eq and p_eq and c_eq == p_eq:
            vec[13] = 1.0

        # 14: Risk level
        risk = classify_risk(candidate)
        vec[14] = 1.0 if risk == RiskLevel.SIDE_EFFECTING else 0.0

        # 15: Idempotency
        vec[15] = 1.0 if candidate.is_idempotent else 0.0

        # 16: Prior reliability
        rel = candidate.metadata.get("expected_success") or candidate.metadata.get("reliability", 0.5)
        vec[16] = float(rel)

        # 17: Latency estimate
        lat = candidate.metadata.get("est_latency", 0.1)
        vec[17] = min(float(lat) / 5.0, 1.0)

        return vec


class RiskPartitionedContextualBandit:
    """Contextual Linear Bandit (LinUCB) with strict risk partitioning.

    Safety Invariant:
    - READ_ONLY actions: Upper Confidence Bound exploration (alpha > 0).
    - SIDE_EFFECTING actions: Zero exploration bonus (alpha = 0). Pure greedy/deterministic.
    """

    def __init__(
        self,
        dimension: int = FEATURE_DIM,
        alpha: float = 0.5,
        ridge: float = 1.0,
        enforce_risk_partition: bool = True,
    ):
        self.d = dimension
        self.alpha = alpha
        self.ridge = ridge
        self.enforce_risk_partition = enforce_risk_partition

        # Per-tool model parameters: tool_name -> (A: d x d, b: d)
        self.A: dict[str, np.ndarray] = {}
        self.b: dict[str, np.ndarray] = {}

    def _init_arm(self, tool: str) -> None:
        if tool not in self.A:
            self.A[tool] = self.ridge * np.eye(self.d)
            self.b[tool] = np.zeros(self.d)

    def score_candidate(
        self,
        candidate: ExecutableAction,
        x: np.ndarray,
        allow_exploration: bool = True,
    ) -> tuple[float, float, float]:
        """Returns (score, mean, uncertainty).

        For SIDE_EFFECTING actions, exploration bonus is clamped to 0 when enforce_risk_partition is True.
        """
        tool = candidate.tool
        self._init_arm(tool)

        A_inv = np.linalg.pinv(self.A[tool])
        theta = A_inv @ self.b[tool]

        mean = float(theta @ x)
        uncertainty = float(math.sqrt(max(0.0, float(x.T @ A_inv @ x))))

        risk = classify_risk(candidate)
        if self.enforce_risk_partition and risk == RiskLevel.SIDE_EFFECTING:
            # STRICT INVARIANT: ZERO EXPLORATION FOR MUTATIONS
            effective_alpha = 0.0
        elif not allow_exploration:
            effective_alpha = 0.0
        else:
            effective_alpha = self.alpha

        score = mean + effective_alpha * uncertainty
        return score, mean, uncertainty

    def update(
        self,
        tool: str,
        x: np.ndarray,
        reward: float,
    ) -> None:
        """Online Sherman-Morrison / outer-product update."""
        self._init_arm(tool)
        self.A[tool] += np.outer(x, x)
        self.b[tool] += reward * x


class BanditRoutePolicy(RoutePolicy):
    """RoutePolicy powered by RiskPartitionedContextualBandit."""

    def __init__(
        self,
        bandit: RiskPartitionedContextualBandit | None = None,
        alpha: float = 0.5,
        enforce_risk_partition: bool = True,
        exploration_enabled: bool = True,
    ):
        self.bandit = bandit or RiskPartitionedContextualBandit(
            alpha=alpha,
            enforce_risk_partition=enforce_risk_partition,
        )
        self.exploration_enabled = exploration_enabled

    def resolve(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> Decision:
        if not candidates:
            return Decision.deny("no candidate actions available")

        # Filter strictly forbidden actions (policy constraint)
        allowed_tools = state.context.get("allowed_tools")
        valid_candidates = []
        for c in candidates:
            if allowed_tools is not None and c.tool not in allowed_tools:
                continue
            valid_candidates.append(c)

        if not valid_candidates:
            return Decision.deny("all candidates disallowed by policy")

        # Score candidates
        best_candidate: ExecutableAction | None = None
        best_score = -float("inf")
        scores: dict[str, float] = {}

        for c in valid_candidates:
            x = ContextFeatureExtractor.extract(state, c)
            score, mean, unc = self.bandit.score_candidate(
                c,
                x,
                allow_exploration=self.exploration_enabled,
            )
            scores[c.tool] = score
            if score > best_score:
                best_score = score
                best_candidate = c

        if best_candidate is None:
            return Decision.defer("unable to score candidates")

        return Decision.select(
            best_candidate,
            reason=f"selected by contextual bandit (score={best_score:.3f})",
        )


class PairwiseRankingModel:
    """Bradley-Terry logistic pairwise ranking model.

    Model: P(c1 > c2 | x) = sigma(w^T (f(x, c1) - f(x, c2)))
    """

    def __init__(self, dimension: int = FEATURE_DIM, l2_reg: float = 0.1, lr: float = 0.05):
        self.d = dimension
        self.l2_reg = l2_reg
        self.lr = lr
        self.weights = np.zeros(self.d, dtype=float)

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        else:
            exp_z = math.exp(z)
            return exp_z / (1.0 + exp_z)

    def fit_pairs(
        self,
        pairs: list[tuple[np.ndarray, np.ndarray, float]],
        epochs: int = 50,
    ) -> dict[str, float]:
        """Fit weights on pairwise comparisons (x_preferred, x_inferior, preference_weight)."""
        if not pairs:
            return {"loss": 0.0, "epochs": 0}

        losses = []
        for _ in range(epochs):
            total_loss = 0.0
            grad = np.zeros(self.d, dtype=float)

            for x_win, x_lose, target in pairs:
                diff = x_win - x_lose
                margin = float(np.dot(self.weights, diff))
                prob = self._sigmoid(margin)

                # Cross-entropy loss: -log(prob)
                loss = -math.log(max(1e-12, prob)) if target >= 0.5 else -math.log(max(1e-12, 1.0 - prob))
                total_loss += loss

                # Gradient
                error = prob - target
                grad += error * diff

            # L2 regularization
            grad += self.l2_reg * self.weights
            total_loss += 0.5 * self.l2_reg * float(np.dot(self.weights, self.weights))

            self.weights -= self.lr * (grad / max(1, len(pairs)))
            losses.append(total_loss / len(pairs))

        return {"initial_loss": losses[0], "final_loss": losses[-1], "epochs": epochs}

    def score(self, x: np.ndarray) -> float:
        """Utility score for candidate representation."""
        return float(np.dot(self.weights, x))

    def rank(
        self,
        state: ExecutionState,
        candidates: list[ExecutableAction],
    ) -> list[tuple[ExecutableAction, float]]:
        """Rank candidates descending by utility score."""
        scored = []
        for c in candidates:
            x = ContextFeatureExtractor.extract(state, c)
            s = self.score(x)
            scored.append((c, s))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored


@dataclass
class LoggedStep:
    """Single logged execution trace step for off-policy evaluation."""

    state_features: np.ndarray
    action_taken: str
    reward: float  # +1 for success, 0 or -1 for failure
    logging_prob: float  # Propensity p0(a | x)
    candidate_features: dict[str, np.ndarray]  # arm -> feature vector
    is_mutation: bool = False


@dataclass
class OPEResult:
    """Results from Off-Policy Evaluation."""

    method: str
    estimated_value: float
    std_error: float
    effective_sample_size: float
    sample_count: int


class OffPolicyEvaluator:
    """Off-Policy Evaluation (OPE) engine for tool resolution policies.

    Supports:
    - Inverse Propensity Scoring (IPS) with weight clipping
    - Direct Method (DM) with linear Q-model
    - Doubly Robust (DR) estimation combining IPS and DM
    """

    def __init__(self, clip_max: float = 10.0):
        self.clip_max = clip_max

    def evaluate_ips(
        self,
        dataset: list[LoggedStep],
        target_policy_fn: Callable[[dict[str, np.ndarray]], dict[str, float]],
    ) -> OPEResult:
        """Evaluate target policy using Inverse Propensity Scoring (IPS).

        target_policy_fn takes candidate_features dict and returns {action: prob}.
        """
        if not dataset:
            return OPEResult("IPS", 0.0, 0.0, 0.0, 0)

        weights = []
        weighted_rewards = []

        for step in dataset:
            target_probs = target_policy_fn(step.candidate_features)
            pi_a = target_probs.get(step.action_taken, 0.0)
            p0_a = max(1e-6, step.logging_prob)

            w = min(self.clip_max, pi_a / p0_a)
            weights.append(w)
            weighted_rewards.append(w * step.reward)

        n = len(dataset)
        v_ips = float(np.mean(weighted_rewards))
        variance = float(np.var(weighted_rewards)) if n > 1 else 0.0
        stderr = math.sqrt(variance / n) if n > 0 else 0.0

        # Effective Sample Size
        sum_w = sum(weights)
        sum_w_sq = sum(w**2 for w in weights)
        ess = (sum_w**2) / sum_w_sq if sum_w_sq > 0 else 0.0

        return OPEResult(
            method="IPS",
            estimated_value=v_ips,
            std_error=stderr,
            effective_sample_size=ess,
            sample_count=n,
        )

    def _fit_q_models(self, dataset: list[LoggedStep]) -> dict[str, tuple[np.ndarray, float]]:
        """Fit per-arm linear Q-model: Q(x, a) = w_a^T x. Returns {arm: (w_a, mean_reward)}."""
        by_arm_X: dict[str, list[np.ndarray]] = {}
        by_arm_y: dict[str, list[float]] = {}
        all_rewards: list[float] = []

        for step in dataset:
            arm = step.action_taken
            x_arm = step.candidate_features.get(arm)
            if x_arm is not None:
                by_arm_X.setdefault(arm, []).append(x_arm)
                by_arm_y.setdefault(arm, []).append(step.reward)
                all_rewards.append(step.reward)

        global_mean = float(np.mean(all_rewards)) if all_rewards else 0.0
        q_models: dict[str, tuple[np.ndarray, float]] = {}

        for arm, X_list in by_arm_X.items():
            y_list = by_arm_y[arm]
            X = np.array(X_list)
            y = np.array(y_list)
            d = X.shape[1]
            reg = 1.0 * np.eye(d)
            try:
                w_a = np.linalg.solve(X.T @ X + reg, X.T @ y)
            except np.linalg.LinAlgError:
                w_a = np.zeros(d)
            q_models[arm] = (w_a, float(np.mean(y_list)))

        return q_models

    def _predict_q(self, q_models: dict[str, tuple[np.ndarray, float]], arm: str, x: np.ndarray | None) -> float:
        if arm in q_models and x is not None:
            w_a, arm_mean = q_models[arm]
            pred = float(np.dot(w_a, x))
            return pred
        return 0.0

    def evaluate_direct_method(
        self,
        dataset: list[LoggedStep],
        target_policy_fn: Callable[[dict[str, np.ndarray]], dict[str, float]],
    ) -> OPEResult:
        """Evaluate target policy using Direct Method (DM).

        Fits per-arm Q(x, a) models on logged rewards.
        """
        if not dataset:
            return OPEResult("DM", 0.0, 0.0, 0.0, 0)

        q_models = self._fit_q_models(dataset)
        predicted_values = []

        for step in dataset:
            target_probs = target_policy_fn(step.candidate_features)
            expected_val = 0.0
            for arm, p in target_probs.items():
                x_arm = step.candidate_features.get(arm)
                q_val = self._predict_q(q_models, arm, x_arm)
                expected_val += p * q_val
            predicted_values.append(expected_val)

        n = len(dataset)
        v_dm = float(np.mean(predicted_values))
        variance = float(np.var(predicted_values)) if n > 1 else 0.0
        stderr = math.sqrt(variance / n) if n > 0 else 0.0

        return OPEResult(
            method="Direct_Method",
            estimated_value=v_dm,
            std_error=stderr,
            effective_sample_size=float(n),
            sample_count=n,
        )

    def evaluate_doubly_robust(
        self,
        dataset: list[LoggedStep],
        target_policy_fn: Callable[[dict[str, np.ndarray]], dict[str, float]],
    ) -> OPEResult:
        """Evaluate target policy using Doubly Robust (DR) estimation."""
        if not dataset:
            return OPEResult("DR", 0.0, 0.0, 0.0, 0)

        q_models = self._fit_q_models(dataset)
        dr_values = []
        weights = []

        for step in dataset:
            target_probs = target_policy_fn(step.candidate_features)
            pi_a = target_probs.get(step.action_taken, 0.0)
            p0_a = max(1e-6, step.logging_prob)
            w = min(self.clip_max, pi_a / p0_a)
            weights.append(w)

            # Direct method baseline: sum_a pi(a | x) Q(x, a)
            q_expected = 0.0
            for arm, p in target_probs.items():
                x_arm = step.candidate_features.get(arm)
                q_val = self._predict_q(q_models, arm, x_arm)
                q_expected += p * q_val

            # Observed Q(x, a_taken)
            x_taken = step.candidate_features.get(step.action_taken)
            q_taken = self._predict_q(q_models, step.action_taken, x_taken)

            # DR estimate: Q_expected + w * (r - Q_taken)
            val = q_expected + w * (step.reward - q_taken)
            dr_values.append(val)

        n = len(dataset)
        v_dr = float(np.mean(dr_values))
        variance = float(np.var(dr_values)) if n > 1 else 0.0
        stderr = math.sqrt(variance / n) if n > 0 else 0.0

        sum_w = sum(weights)
        sum_w_sq = sum(w**2 for w in weights)
        ess = (sum_w**2) / sum_w_sq if sum_w_sq > 0 else 0.0

        return OPEResult(
            method="Doubly_Robust",
            estimated_value=v_dr,
            std_error=stderr,
            effective_sample_size=ess,
            sample_count=n,
        )
