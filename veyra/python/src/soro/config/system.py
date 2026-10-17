"""Veyra Configuration System (Phase 3).

Supports human-readable YAML/JSON configuration files with validation and explanation:
veyra config validate
veyra config explain
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VeyraPolicyConfig:
    tenant_isolation: bool = True
    authorization: bool = True
    freshness: bool = True
    health: bool = True


@dataclass
class VeyraRecoveryConfig:
    unknown_ack: str = "verify_then_defer"  # verify_then_defer | abstain | deny
    retries_enabled: bool = True
    max_attempts: int = 2


@dataclass
class VeyraTransactionConfig:
    idempotency: str = "required_when_supported"
    compensation: str = "declared_only"


@dataclass
class VeyraObservabilityConfig:
    tracing: bool = True
    audit_chain: bool = True
    export_format: str = "jsonl"  # jsonl | otel


@dataclass
class VeyraConfig:
    mode: str = "fail_closed"  # normal | shadow | dry_run | fail_closed | fail_open
    routing_strategy: str = "policy_aware"
    policy: VeyraPolicyConfig = field(default_factory=VeyraPolicyConfig)
    recovery: VeyraRecoveryConfig = field(default_factory=VeyraRecoveryConfig)
    transactions: VeyraTransactionConfig = field(default_factory=VeyraTransactionConfig)
    observability: VeyraObservabilityConfig = field(default_factory=VeyraObservabilityConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VeyraConfig:
        policy_data = data.get("policy", {})
        rec_data = data.get("recovery", {})
        tx_data = data.get("transactions", {})
        obs_data = data.get("observability", {})

        return cls(
            mode=data.get("mode", "fail_closed"),
            routing_strategy=data.get("routing_strategy", "policy_aware"),
            policy=VeyraPolicyConfig(**policy_data) if isinstance(policy_data, dict) else VeyraPolicyConfig(),
            recovery=VeyraRecoveryConfig(
                unknown_ack=rec_data.get("unknown_ack", "verify_then_defer"),
                retries_enabled=rec_data.get("retries_enabled", True) if "retries_enabled" in rec_data else rec_data.get("retries", {}).get("enabled", True),
                max_attempts=rec_data.get("max_attempts", 2) if "max_attempts" in rec_data else rec_data.get("retries", {}).get("max_attempts", 2),
            ),
            transactions=VeyraTransactionConfig(**tx_data) if isinstance(tx_data, dict) else VeyraTransactionConfig(),
            observability=VeyraObservabilityConfig(**obs_data) if isinstance(obs_data, dict) else VeyraObservabilityConfig(),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate config constraints and return (is_valid, errors)."""
        errors = []
        valid_modes = {"normal", "shadow", "dry_run", "fail_closed", "fail_open"}
        if self.mode not in valid_modes:
            errors.append(f"Invalid mode '{self.mode}'. Must be one of {valid_modes}")

        if self.recovery.max_attempts < 0:
            errors.append("max_attempts must be >= 0")

        return len(errors) == 0, errors

    def explain(self) -> str:
        """Return human-readable explanation of active configuration policies."""
        lines = [
            f"Veyra Configuration (Mode: {self.mode.upper()})",
            "--------------------------------------------------",
            f"Routing Strategy:      {self.routing_strategy}",
            f"Tenant Isolation:      {'ENABLED' if self.policy.tenant_isolation else 'DISABLED'}",
            f"Authorization:         {'ENABLED' if self.policy.authorization else 'DISABLED'}",
            f"Freshness Validation:  {'ENABLED' if self.policy.freshness else 'DISABLED'}",
            f"Health Monitoring:     {'ENABLED' if self.policy.health else 'DISABLED'}",
            f"UNKNOWN_ACK Recovery:  {self.recovery.unknown_ack}",
            f"Max Retries Allowed:   {self.recovery.max_attempts if self.recovery.retries_enabled else 0}",
            f"Idempotency Policy:    {self.transactions.idempotency}",
            f"Compensation Policy:   {self.transactions.compensation}",
            f"Audit Hash-Chain:      {'ACTIVE' if self.observability.audit_chain else 'INACTIVE'}",
        ]
        return "\n".join(lines)


def load_config(path: str | Path | None = None) -> VeyraConfig:
    """Load configuration from file path or return default VeyraConfig."""
    if not path:
        return VeyraConfig()

    p = Path(path)
    if not p.exists():
        return VeyraConfig()

    content = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            data = {}
    else:
        data = json.loads(content)

    veyra_section = data.get("veyra", data) if isinstance(data, dict) else {}
    return VeyraConfig.from_dict(veyra_section)


class VeyraConfigManager:
    """Config manager for loading, validating, and explaining Veyra configs."""

    @classmethod
    def load(cls, path: str | Path | None = None) -> VeyraConfig:
        return load_config(path)

    @classmethod
    def validate(cls, config: VeyraConfig) -> dict[str, Any]:
        is_valid, errors = config.validate()
        return {"valid": is_valid, "errors": errors}

    @classmethod
    def explain(cls, config: VeyraConfig) -> dict[str, Any]:
        return {
            "mode": config.mode,
            "text": config.explain(),
            "active_policies": {
                "tenant_isolation": config.policy.tenant_isolation,
                "authorization": config.policy.authorization,
                "freshness": config.policy.freshness,
                "health": config.policy.health,
            },
        }
