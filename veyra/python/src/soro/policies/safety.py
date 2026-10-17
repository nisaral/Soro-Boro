"""Veyra Policy Packs & Composable PolicySet (Phase 8).

Built-in policy packs:
- default
- strict
- read_only
- production
- development
- unknown_ack_safe

Composable PolicySet API:
policy = PolicySet(
    authorization=StrictAuthorization(),
    tenant=TenantIsolation(),
    transaction=UnknownAckSafe(),
)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState


class PolicyPackKind(str, enum.Enum):
    DEFAULT = "default"
    STRICT = "strict"
    READ_ONLY = "read_only"
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    UNKNOWN_ACK_SAFE = "unknown_ack_safe"


@dataclass
class PolicySet:
    """Composable policy set evaluated in strict deterministic order."""

    name: str = "default_policy_set"
    enforce_authorization: bool = True
    enforce_tenant_isolation: bool = True
    enforce_freshness: bool = True
    enforce_health: bool = True
    read_only_only: bool = False
    unknown_ack_strict: bool = True
    max_risk_allowed: str = "high"  # low | medium | high | destructive

    def evaluate(self, proposal: ExecutableAction, state: ExecutionState) -> tuple[bool, str]:
        """Evaluate proposal against all active policies in deterministic order."""
        tool_name = proposal.tool

        # 1. Read-only policy
        if self.read_only_only:
            sec = proposal.metadata.get("side_effect_class", "read_only")
            if sec in ("non_idempotent_mutation", "destructive") or not proposal.is_idempotent:
                return False, f"Policy pack '{self.name}' enforces read_only; mutating action '{tool_name}' denied."

        # 2. Authorization policy
        if self.enforce_authorization and proposal.required_permissions:
            if not set(proposal.required_permissions).issubset(state.permissions):
                unauth = set(proposal.required_permissions) - state.permissions
                return False, f"Authorization policy denied action '{tool_name}': missing permissions {unauth}."

        # 3. Tenant isolation policy
        if self.enforce_tenant_isolation:
            state_tenant = state.context.get("tenant")
            prop_tenant = proposal.metadata.get("tenant")
            if state_tenant is not None and prop_tenant is not None and state_tenant != prop_tenant:
                return False, f"Tenant isolation policy denied action '{tool_name}': expected {state_tenant}, got {prop_tenant}."

        # 4. Transaction UNKNOWN_ACK safety policy
        if self.unknown_ack_strict:
            if state.context.get("tx_state") == "unknown_ack" and not proposal.is_idempotent:
                return False, f"UNKNOWN_ACK transaction policy denied action '{tool_name}': blind replay forbidden."

        # 5. Risk threshold policy
        risk_ranks = {"low": 1, "medium": 2, "high": 3, "destructive": 4}
        action_risk = risk_ranks.get(proposal.risk_class, 1)
        max_allowed = risk_ranks.get(self.max_risk_allowed, 3)
        if action_risk > max_allowed:
            return False, f"Risk policy denied action '{tool_name}': risk {proposal.risk_class} exceeds max allowed {self.max_risk_allowed}."

        return True, "Passed all policies in PolicySet"


def get_policy_pack(pack: str | PolicyPackKind) -> PolicySet:
    """Retrieve pre-configured built-in policy pack."""
    pack_name = pack.value if isinstance(pack, PolicyPackKind) else str(pack).lower()

    if pack_name == "strict":
        return PolicySet(name="strict", max_risk_allowed="low", unknown_ack_strict=True)
    elif pack_name == "read_only":
        return PolicySet(name="read_only", read_only_only=True)
    elif pack_name == "production":
        return PolicySet(name="production", max_risk_allowed="medium", unknown_ack_strict=True)
    elif pack_name == "development":
        return PolicySet(name="development", max_risk_allowed="destructive", unknown_ack_strict=False)
    elif pack_name == "unknown_ack_safe":
        return PolicySet(name="unknown_ack_safe", unknown_ack_strict=True)
    else:
        return PolicySet(name="default")
