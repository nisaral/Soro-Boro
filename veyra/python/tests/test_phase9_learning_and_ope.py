"""Unit tests for Phase 9: Risk Partitioning, Contextual Bandits, Pairwise Ranking, and OPE."""

import numpy as np
import pytest

from veyra.boundary.taxonomy import FailureProvenance
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.state import ExecutionState
from veyra.policy.learning import (
    FEATURE_DIM,
    BanditRoutePolicy,
    ContextFeatureExtractor,
    LoggedStep,
    OffPolicyEvaluator,
    PairwiseRankingModel,
    RiskLevel,
    RiskPartitionedContextualBandit,
    classify_risk,
)


def test_risk_partition_classification():
    """Verify that mutating operations are strictly classified as SIDE_EFFECTING."""
    # Read-only verbs
    assert classify_risk("get_customer") == RiskLevel.READ_ONLY
    assert classify_risk("read_file_content") == RiskLevel.READ_ONLY
    assert classify_risk("query_order") == RiskLevel.READ_ONLY
    assert classify_risk("search_logs") == RiskLevel.READ_ONLY

    # Side-effecting verbs
    assert classify_risk("write_file") == RiskLevel.SIDE_EFFECTING
    assert classify_risk("patch_file") == RiskLevel.SIDE_EFFECTING
    assert classify_risk("delete_order") == RiskLevel.SIDE_EFFECTING
    assert classify_risk("insert_customer") == RiskLevel.SIDE_EFFECTING
    assert classify_risk("execute_sql") == RiskLevel.SIDE_EFFECTING

    # Metadata overrides
    safe_action = ExecutableAction(tool="custom_op", metadata={"idempotent": True, "read_only": True})
    assert classify_risk(safe_action) == RiskLevel.READ_ONLY

    dangerous_action = ExecutableAction(tool="custom_lookup", metadata={"is_mutation": True})
    assert classify_risk(dangerous_action) == RiskLevel.SIDE_EFFECTING


def test_feature_extractor_shape_and_provenance():
    """Verify ContextFeatureExtractor outputs correct 18-dim vectors with failure provenance."""
    state = ExecutionState(
        step=3,
        context={
            "failure_provenance": FailureProvenance.TOOL_IMPLEMENTATION_ERROR,
            "proposed_tool": "fetch_user",
            "equivalence_group": "user_lookup",
        },
    )
    cand = ExecutableAction(
        tool="get_user",
        arguments={"uid": "123"},
        metadata={"equivalence_group": "user_lookup", "expected_success": 0.9},
    )

    feat = ContextFeatureExtractor.extract(state, cand)
    assert feat.shape == (FEATURE_DIM,)
    assert feat[0] == 1.0  # Bias
    # Index 3 is TOOL_IMPLEMENTATION_ERROR
    assert feat[3] == 1.0
    # Equivalence group match
    assert feat[13] == 1.0
    # Read-only risk level -> 0.0
    assert feat[14] == 0.0


def test_bandit_risk_partition_zero_exploration_invariant():
    """Safety Invariant: Side-effecting mutations MUST have zero exploration bonus."""
    bandit = RiskPartitionedContextualBandit(dimension=FEATURE_DIM, alpha=1.5, enforce_risk_partition=True)
    x = np.ones(FEATURE_DIM)

    # 1. Read-only action should receive positive exploration bonus
    read_cand = ExecutableAction(tool="read_data")
    score_read, mean_read, unc_read = bandit.score_candidate(read_cand, x, allow_exploration=True)
    assert unc_read > 0.0
    assert score_read > mean_read  # alpha * unc > 0

    # 2. Side-effecting action MUST receive ZERO exploration bonus
    write_cand = ExecutableAction(tool="write_data")
    score_write, mean_write, unc_write = bandit.score_candidate(write_cand, x, allow_exploration=True)
    assert unc_write > 0.0
    # Under risk partition, effective_alpha is 0.0!
    assert score_write == mean_write


def test_bandit_route_policy_respects_allowed_tools():
    """BanditRoutePolicy must never pick an action forbidden by policy."""
    policy = BanditRoutePolicy(alpha=0.5)
    state = ExecutionState(context={"allowed_tools": ["fetch_user"]})

    allowed = ExecutableAction(tool="fetch_user")
    forbidden = ExecutableAction(tool="admin_delete")

    dec = policy.resolve(state, [forbidden, allowed])
    assert dec.kind == DecisionKind.SELECT
    assert dec.action.tool == "fetch_user"

    # If all candidates are forbidden -> DENY
    dec_deny = policy.resolve(state, [forbidden])
    assert dec_deny.kind == DecisionKind.DENY


def test_pairwise_ranking_learning():
    """Bradley-Terry model should learn preference from pairwise comparison pairs."""
    model = PairwiseRankingModel(dimension=FEATURE_DIM, l2_reg=0.01, lr=0.2)

    # Feature indicates high quality vs inferior tool
    x_good = np.zeros(FEATURE_DIM)
    x_good[0] = 1.0  # bias
    x_good[12] = 1.0  # tool match
    x_good[16] = 0.95  # reliability

    x_bad = np.zeros(FEATURE_DIM)
    x_bad[0] = 1.0
    x_bad[12] = 0.0
    x_bad[16] = 0.1

    pairs = [(x_good, x_bad, 1.0)] * 50
    metrics = model.fit_pairs(pairs, epochs=100)

    assert metrics["final_loss"] < metrics["initial_loss"]
    assert model.score(x_good) > model.score(x_bad)

    # Ranking test
    c1 = ExecutableAction(tool="cand_bad", metadata={"expected_success": 0.1})
    c2 = ExecutableAction(tool="cand_good", metadata={"expected_success": 0.95})

    state = ExecutionState()
    ranked = model.rank(state, [c1, c2])
    assert len(ranked) == 2
    assert ranked[0][0].tool == "cand_good"


def test_off_policy_evaluator_ips_dm_dr():
    """Verify OPE computes IPS, DM, and DR on logged steps."""
    evaluator = OffPolicyEvaluator(clip_max=5.0)

    # Generate synthetic logged steps
    dataset = []
    rng = np.random.RandomState(42)

    for i in range(100):
        # Feature with bias term
        x = np.zeros(FEATURE_DIM)
        x[0] = 1.0
        x[1:] = rng.randn(FEATURE_DIM - 1) * 0.1

        # Logging policy took "tool_a" with prob 0.7, "tool_b" with prob 0.3
        action = "tool_a" if rng.rand() < 0.7 else "tool_b"
        prob0 = 0.7 if action == "tool_a" else 0.3
        # Reward is 1.0 if tool_a, 0.0 if tool_b
        reward = 1.0 if action == "tool_a" else 0.0

        step = LoggedStep(
            state_features=x,
            action_taken=action,
            reward=reward,
            logging_prob=prob0,
            candidate_features={"tool_a": x, "tool_b": x},
        )
        dataset.append(step)

    # Target policy: always prefers tool_a (1.0)
    def target_policy(cand_feats: dict[str, np.ndarray]) -> dict[str, float]:
        return {"tool_a": 1.0, "tool_b": 0.0}

    ips_res = evaluator.evaluate_ips(dataset, target_policy)
    dm_res = evaluator.evaluate_direct_method(dataset, target_policy)
    dr_res = evaluator.evaluate_doubly_robust(dataset, target_policy)

    assert ips_res.sample_count == 100
    assert ips_res.effective_sample_size > 50
    assert ips_res.estimated_value > 0.8  # Target prefers optimal tool_a

    assert dm_res.estimated_value > 0.8
    assert dr_res.estimated_value > 0.8
