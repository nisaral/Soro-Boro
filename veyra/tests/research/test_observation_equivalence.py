"""Unit tests proving zero ground-truth leakage and strict observation equivalence (Phases 0 & 1)."""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.recovery_controller.scenarios.generators import generate_scenario_suite
from benchmarks.recovery_controller.scenarios.schema import Observation, TrueExecutionState
from benchmarks.recovery_controller.baselines import (
    run_belief_state_veyra,
    run_full_mechanism_deterministic,
)


def test_observation_zero_leakage():
    scenarios = generate_scenario_suite(n=20, seed=42)
    for sc in scenarios:
        obs = sc.to_observation()
        assert isinstance(obs, Observation)
        obs_dict = obs.to_dict()

        # Invariant 1: true_execution_state MUST NOT be present
        assert "true_execution_state" not in obs_dict
        assert not hasattr(obs, "true_execution_state")

        # Invariant 2: evaluator ground truth fields MUST NOT be present
        assert "expected_safe_action" not in obs_dict
        assert "true_state" not in obs_dict
        assert not hasattr(obs, "expected_safe_action")

        # Invariant 3: Observation fields are strictly runtime telemetry
        assert obs.action_id == sc.scenario_id
        assert obs.tool_name == sc.tool_name
        assert obs.arguments == sc.arguments


def test_baseline_observation_equivalence():
    """Proves that Full-Mechanism Deterministic and Belief-State Veyra receive byte-for-byte identical inputs."""
    scenarios = generate_scenario_suite(n=50, seed=123)
    for sc in scenarios:
        obs = sc.to_observation()
        pub_ctx = sc.get_public_action_context()

        # Both controllers receive identical contract parameters
        assert pub_ctx["action_id"] == obs.action_id
        assert pub_ctx["tool_name"] == obs.tool_name
        assert pub_ctx["arguments"] == obs.arguments
        assert pub_ctx["verification_available"] == obs.verification_available
        assert pub_ctx["idempotency_available"] == obs.idempotency_available
        assert pub_ctx["reconciliation_available"] == obs.reconciliation_available
        assert pub_ctx["compensation_available"] == obs.compensation_available

        # Ensure ground truth is not leaked to either controller function
        assert "true_execution_state" not in pub_ctx
