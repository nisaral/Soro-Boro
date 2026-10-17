"""Tests for Veyra Execution Contract Analyzer (VEC v1alpha1)."""

from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))
sys.path.insert(0, str(REPO_ROOT))

from veyra.core.contract_analyzer import ExecutionContractAnalyzer


def test_payment_charge_contract_analysis():
    contract_path = Path(__file__).resolve().parents[2] / "examples" / "execution_contracts" / "payment_charge.yaml"
    assert contract_path.exists()
    manifest = ExecutionContractAnalyzer.load_from_yaml(contract_path)
    report = ExecutionContractAnalyzer.analyze(manifest)

    assert report.operation == "payments.create_charge"
    assert report.certification_grade == "Grade A"
    assert report.idempotency_supported is True
    assert report.status_lookup_supported is True
    assert report.read_back_consistency == "strong"
    assert "IDEMPOTENCY_REPLAY" in report.permissible_recovery_actions
    assert "VERIFY" in report.permissible_recovery_actions
    assert "COMPENSATE" in report.permissible_recovery_actions
    assert "RETRY" in report.prohibited_recovery_actions or len(report.prohibited_recovery_actions) == 0


def test_legacy_billing_contract_analysis():
    contract_path = Path(__file__).resolve().parents[2] / "examples" / "execution_contracts" / "legacy_billing.yaml"
    assert contract_path.exists()
    manifest = ExecutionContractAnalyzer.load_from_yaml(contract_path)
    report = ExecutionContractAnalyzer.analyze(manifest)

    assert report.operation == "legacy_billing.send_invoice"
    assert report.certification_grade == "Grade F"
    assert report.idempotency_supported is False
    assert report.status_lookup_supported is False
    assert "AUTONOMOUS EXECUTION PROHIBITED" in report.autonomous_recommendation
    assert "RETRY" in report.prohibited_recovery_actions
    assert "IDEMPOTENCY_REPLAY" in report.prohibited_recovery_actions
    assert report.permissible_recovery_actions == ["DEFER", "DENY"]
