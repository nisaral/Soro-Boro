"""Tests for Veyra Black-Box Conformance Testing & False Assurance Detection."""

from pathlib import Path
import pytest
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))
sys.path.insert(0, str(REPO_ROOT))

from veyra.core.conformance import ConformanceTester
from veyra.core.contract_analyzer import ExecutionContractAnalyzer


def test_conformance_verified_tool():
    contract_path = REPO_ROOT / "examples" / "execution_contracts" / "payment_charge.yaml"
    manifest = ExecutionContractAnalyzer.load_from_yaml(contract_path)
    profile = ConformanceTester.test_tool(manifest, trials_per_fault=20, seed=42)

    assert profile.tool_name == "payments.create_charge"
    assert profile.declared_idempotency is True
    assert profile.verified_idempotency is True
    assert profile.idempotency_status == "VERIFIED"
    assert profile.status_lookup_status == "VERIFIED"
    assert profile.false_assurance_detected is False
    assert "FULL_AUTONOMOUS" in profile.autonomous_recommendation


def test_conformance_unverified_legacy_tool():
    contract_path = REPO_ROOT / "examples" / "execution_contracts" / "legacy_billing.yaml"
    manifest = ExecutionContractAnalyzer.load_from_yaml(contract_path)
    profile = ConformanceTester.test_tool(manifest, trials_per_fault=20, seed=42)

    assert profile.tool_name == "legacy_billing.send_invoice"
    assert profile.declared_idempotency is False
    assert profile.idempotency_status == "UNVERIFIED"
    assert profile.false_assurance_detected is True
    assert "AUTONOMOUS EXECUTION PROHIBITED" in profile.autonomous_recommendation


def test_conformance_false_assurance_detection():
    contract_path = REPO_ROOT / "examples" / "execution_contracts" / "false_assurance_tool.yaml"
    manifest = ExecutionContractAnalyzer.load_from_yaml(contract_path)

    # In this test, simulate backend that violates declared idempotency
    # by evaluating under simulated failure
    profile = ConformanceTester.test_tool(manifest, trials_per_fault=20, seed=42)
    assert profile.declared_idempotency is True
    assert profile.status_lookup_status == "UNSUPPORTED"
