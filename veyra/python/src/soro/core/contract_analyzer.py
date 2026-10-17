"""Veyra Execution Contract (VEC) v1alpha1 Parser and Static Analyzer.

Implements Phase 8 capability model & automated certification analyzer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass(frozen=True)
class ContractAnalysisReport:
    operation: str
    version: str
    side_effect_class: str
    reversibility: str
    idempotency_supported: bool
    status_lookup_supported: bool
    read_back_consistency: str
    compensation_supported: bool
    reconciliation_supported: bool
    in_flight_timeout_ms: Optional[int]
    permissible_recovery_actions: List[str]
    prohibited_recovery_actions: List[str]
    certification_grade: str
    autonomous_recommendation: str
    missing_guarantees: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ExecutionContractAnalyzer:
    """Audits tool manifests against Veyra Execution Contract v1alpha1."""

    @classmethod
    def load_from_yaml(cls, yaml_path_or_str: str | Path) -> Dict[str, Any]:
        path = Path(yaml_path_or_str)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(yaml_path_or_str)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML manifest: expected dict, got {type(data)}")
        return data

    @classmethod
    def analyze(cls, manifest: Dict[str, Any]) -> ContractAnalysisReport:
        version = manifest.get("version", "soro.spec/v1alpha1")
        operation = manifest.get("operation", "unknown_operation")
        side_effect_class = manifest.get("side_effect_class", "non_idempotent_mutation")
        reversibility = manifest.get("reversibility", "irreversible")

        idempotency = manifest.get("idempotency", {}) or {}
        idempotency_supported = bool(idempotency.get("supported", False))

        evidence = manifest.get("evidence_probes", {}) or {}
        status_lookup = evidence.get("status_lookup", {}) or {}
        status_lookup_supported = bool(status_lookup.get("supported", False))
        read_back_consistency = str(evidence.get("read_back_consistency", "none"))

        compensation = manifest.get("compensation", {}) or {}
        compensation_supported = bool(compensation.get("supported", False))

        reconciliation = manifest.get("reconciliation", {}) or {}
        reconciliation_supported = bool(reconciliation.get("supported", False))

        bounds = manifest.get("execution_bounds", {}) or {}
        in_flight_timeout_ms = bounds.get("max_in_flight_timeout_ms")

        # 1. Compute Permissible Recovery Actions
        permissible = ["DEFER", "DENY"]
        prohibited = []

        if side_effect_class == "read_only":
            permissible = ["RETRY", "FALLBACK", "DEFER"]
            prohibited = []
        else:
            # Mutations
            if idempotency_supported:
                permissible.append("IDEMPOTENCY_REPLAY")
                permissible.append("VERIFY")
            if status_lookup_supported:
                if "VERIFY" not in permissible:
                    permissible.append("VERIFY")
            if compensation_supported:
                permissible.append("COMPENSATE")
            if reconciliation_supported:
                permissible.append("RECONCILE")

            # Prohibitions
            if not idempotency_supported and not status_lookup_supported and not compensation_supported:
                prohibited = ["RETRY", "IDEMPOTENCY_REPLAY", "FALLBACK", "COMPENSATE", "RECONCILE"]
            elif not idempotency_supported:
                prohibited = ["RETRY", "IDEMPOTENCY_REPLAY"]

        # Deduplicate & preserve order
        permissible = sorted(list(set(permissible)))
        prohibited = sorted(list(set(prohibited)))

        # 2. Compute Certification Grade & Recommendations
        missing_guarantees: List[str] = []
        if not idempotency_supported:
            missing_guarantees.append("No server-side idempotency key support")
        if not status_lookup_supported:
            missing_guarantees.append("No dedicated verification / status probe")
        if read_back_consistency in ("none", "eventual"):
            missing_guarantees.append(f"Weak read consistency ({read_back_consistency})")
        if not compensation_supported:
            missing_guarantees.append("No compensation / refund / undo capability")
        if in_flight_timeout_ms is None:
            missing_guarantees.append("Unbounded in-flight duration")

        if side_effect_class == "read_only":
            grade = "Grade A"
            recommendation = "FULL AUTONOMOUS EXECUTION (Read-only operation)"
        elif idempotency_supported and status_lookup_supported and read_back_consistency == "strong":
            grade = "Grade A"
            recommendation = "FULL AUTONOMOUS EXECUTION (Certified Safe Recovery)"
        elif idempotency_supported or (status_lookup_supported and compensation_supported):
            grade = "Grade B"
            recommendation = "CONDITIONAL AUTONOMOUS EXECUTION (Probe / Idempotency Gated)"
        elif status_lookup_supported:
            grade = "Grade C"
            recommendation = "RESTRICTED EXECUTION (Requires synchronous verification post-dispatch)"
        else:
            grade = "Grade F"
            recommendation = "AUTONOMOUS EXECUTION PROHIBITED (High risk of unrecoverable duplicate harm)"

        return ContractAnalysisReport(
            operation=operation,
            version=version,
            side_effect_class=side_effect_class,
            reversibility=reversibility,
            idempotency_supported=idempotency_supported,
            status_lookup_supported=status_lookup_supported,
            read_back_consistency=read_back_consistency,
            compensation_supported=compensation_supported,
            reconciliation_supported=reconciliation_supported,
            in_flight_timeout_ms=in_flight_timeout_ms,
            permissible_recovery_actions=permissible,
            prohibited_recovery_actions=prohibited,
            certification_grade=grade,
            autonomous_recommendation=recommendation,
            missing_guarantees=missing_guarantees,
        )
