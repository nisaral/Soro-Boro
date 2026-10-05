"""Unit tests for Gate 1 leaderboard analysis and MDE calibration."""

from __future__ import annotations

import math
from veyra.analysis.gate1_leaderboard import (
    calculate_matched_headroom,
    is_valid_submission,
    normalize_model_name,
    normalize_task_name,
)


def test_task_name_normalization():
    assert normalize_task_name("terminal-bench/fix-git-rebase") == "fix-git-rebase"
    assert normalize_task_name("terminal-bench/fix-git-rebase.json") == "fix-git-rebase"
    assert normalize_task_name("click-button") == "click-button"


def test_model_name_normalization():
    assert normalize_model_name("openai/gpt-5.3-codex") == "gpt-5.3-codex"
    assert normalize_model_name("google/gemini-3.1-pro") == "gemini-3.1-pro"
    assert normalize_model_name("GPT-5.3-Codex") == "gpt-5.3-codex"


def test_submission_filtering():
    # Valid
    assert is_valid_submission({"agent": "SageAgent", "model": "gpt-5.3-codex", "timeout_multiplier": 1.0})
    # Overridden timeout_multiplier
    assert not is_valid_submission({"agent": "SageAgent", "model": "gpt-5.3-codex", "timeout_multiplier": 2.0})
    # Resource override
    assert not is_valid_submission({"agent": "SageAgent", "model": "gpt-5.3-codex", "resource_limits": {"cpu": "16"}})
    # Setup timeout override
    assert not is_valid_submission({"agent": "SageAgent", "model": "gpt-5.3-codex", "override_setup_timeout_sec": 300})
    # Multi-model
    assert not is_valid_submission({"agent": "SageAgent", "model": ["gpt-4o", "claude-3-5-sonnet"]})


def test_identical_agents_trigger_stop_rule():
    # 2 agents with identical 50% pass rate on 20 tasks
    tasks = [f"task_{i:02d}" for i in range(20)]
    trials_by_agent = {
        "agent_a": {t: [True, False, True, False, True] for t in tasks},
        "agent_b": {t: [True, False, True, False, True] for t in tasks},
    }
    cost_by_agent = {
        "agent_a": {t: [0.1] * 5 for t in tasks},
        "agent_b": {t: [0.1] * 5 for t in tasks},
    }

    res = calculate_matched_headroom(trials_by_agent, cost_by_agent, model="gpt-5.3-codex")
    assert res is not None
    # Identical agents have 0 net headroom over best-of-2
    assert abs(res.mean_net_headroom) < 1e-6
    assert res.gate1_decision == "STOP"


def test_complementary_agents_clear_margin():
    # Agent A solves tasks 0..9, fails tasks 10..19
    # Agent B fails tasks 0..9, solves tasks 10..19
    tasks = [f"task_{i:02d}" for i in range(20)]
    trials_by_agent = {
        "agent_a": {t: ([True] * 5 if int(t.split("_")[1]) < 10 else [False] * 5) for t in tasks},
        "agent_b": {t: ([False] * 5 if int(t.split("_")[1]) < 10 else [True] * 5) for t in tasks},
    }
    cost_by_agent = {
        "agent_a": {t: [0.1] * 5 for t in tasks},
        "agent_b": {t: [0.1] * 5 for t in tasks},
    }

    res = calculate_matched_headroom(trials_by_agent, cost_by_agent, model="gemini-3.1-pro")
    assert res is not None
    # Oracle = 1.0 (100%), Null (best of 2 for single agent) = 0.5 (50%), net = 0.5 (+50pp)
    assert abs(res.oracle_mean_rate - 1.0) < 1e-6
    assert abs(res.null_best_of_m_rate - 0.5) < 1e-6
    assert abs(res.mean_net_headroom - 0.5) < 1e-6
    assert res.gate1_decision == "CLEAR"
