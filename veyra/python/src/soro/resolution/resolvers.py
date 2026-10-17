"""Veyra Deterministic Resolvers (Section 3).

Implements deterministic resolution layers without LLMs, embeddings, or bandits in the core execution path:
- StaticPriorityResolver
- HealthAwareResolver
- FreshnessAwareResolver
- PolicyAwareResolver
- VeyraResolver

Formal Invariant (Section 2 & 3):
- Routing may select only from policy-allowed candidates.
- Routing must never widen the policy-allowed action space.
- Hard constraints MUST NOT be overridden by soft preference ranking.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from soro.baseline.competent import coerce_argument_types
from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState
from soro.core.transaction import TransactionSafetyPolicy, TransactionState
from soro.registry.tool_registry import ToolDefinition, ToolRegistry
from soro.resolution.types import (
    CandidateEvaluation,
    ResolutionDecision,
    ResolutionResult,
    RiskLevel,
)


class BaseResolver(ABC):
    """Abstract base resolver with standard candidate generation and evaluation helpers."""

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or ToolRegistry()

    def generate_candidates(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
    ) -> list[ExecutableAction]:
        """Generate candidate actions from primary tool, declared equivalents, and declared fallbacks."""
        equivs = list(self.registry.get_equivalents(proposal.tool))
        if self.registry.get(proposal.tool) is not None:
            names = [proposal.tool] + [e for e in equivs if e != proposal.tool]
        else:
            names = list(equivs)
            if proposal.executable is not None or not equivs:
                names.append(proposal.tool)

        fallbacks = self.registry.get_fallback_chain(proposal.tool)
        for fb in fallbacks:
            if fb not in names:
                names.append(fb)

        candidates: list[ExecutableAction] = []
        for name in names:
            tool_def = self.registry.get(name)
            if tool_def is not None:
                # Map arguments using declared alias mappings
                alias_map = self.registry.get_parameter_aliases(name)
                remapped_args = dict(proposal.arguments)
                for prop_arg, canon_arg in alias_map.items():
                    if prop_arg in remapped_args and canon_arg not in remapped_args:
                        remapped_args[canon_arg] = remapped_args.pop(prop_arg)

                # Schema type coercion
                coerced_args = coerce_argument_types(remapped_args, tool_def.schema)

                metadata = {
                    "idempotent": tool_def.idempotent,
                    "retryable": tool_def.retryable,
                    "risk_class": tool_def.risk_class,
                    "capabilities": list(tool_def.capabilities),
                    "permissions": list(tool_def.permissions),
                    "protocol": tool_def.protocol,
                    "schema": tool_def.schema,
                    "healthy": tool_def.healthy,
                    "freshness_sec": tool_def.freshness_sec,
                    "consistency": tool_def.consistency,
                    "side_effect_class": tool_def.side_effect_class,
                    "cost": tool_def.cost,
                    "latency_ms": tool_def.latency_ms,
                    "reliability": tool_def.reliability,
                    "tenant": tool_def.metadata.get("tenant"),
                    "replica_id": tool_def.metadata.get("replica_id", name),
                }
                metadata.update(tool_def.metadata)
                cand = ExecutableAction(
                    tool=name,
                    arguments=coerced_args,
                    metadata=metadata,
                    executable=tool_def.executable,
                )
            else:
                meta = dict(proposal.metadata)
                if "healthy" not in meta:
                    meta["healthy"] = True
                cand = ExecutableAction(
                    tool=name,
                    arguments=dict(proposal.arguments),
                    metadata=meta,
                    executable=proposal.executable,
                )
            candidates.append(cand)
        return candidates

    def evaluate_hard_constraints(
        self,
        candidate: ExecutableAction,
        proposal: ExecutableAction,
        state: ExecutionState,
        contract: ExecutionContract,
    ) -> tuple[bool, str]:
        """Strict evaluation of all Hard Constraints (Section 2):
        - authorization
        - tenant isolation
        - capability compatibility
        - contract validity
        - side-effect safety
        - transaction invariants
        - explicit policy denial
        """
        tool_name = candidate.tool

        # 0. Explicit policy denial / blocked tools
        blocked_tools = set(state.context.get("blocked_tools", []))
        if tool_name in blocked_tools:
            return False, "explicit policy denial: tool is blocked"

        # 1. Tenant isolation
        state_tenant = state.context.get("tenant")
        cand_tenant = candidate.metadata.get("tenant")
        if state_tenant is not None and cand_tenant is not None and state_tenant != cand_tenant:
            return False, f"tenant mismatch: expected {state_tenant}, got {cand_tenant}"

        # 2. Authorization / permissions
        if candidate.required_permissions:
            if not set(candidate.required_permissions).issubset(state.permissions):
                unauth = set(candidate.required_permissions) - state.permissions
                return False, f"authorization error: missing permissions {unauth}"

        # 3. Capability compatibility
        req_capabilities = set(state.context.get("required_capabilities", []))
        cand_caps = set(candidate.metadata.get("capabilities", []))
        if req_capabilities and not req_capabilities.issubset(cand_caps):
            missing = req_capabilities - cand_caps
            return False, f"capability mismatch: missing required {missing}"

        # 4. Side-effect safety
        cand_sec = candidate.metadata.get("side_effect_class", "read_only")
        if contract.side_effect_class == SideEffectClass.READ_ONLY:
            if cand_sec in ("non_idempotent_mutation", "destructive"):
                return False, "side-effect violation: mutating candidate for read action"

        if not candidate.is_idempotent and candidate.tool != proposal.tool:
            equivs = self.registry.get_equivalents(proposal.tool)
            if candidate.tool not in equivs:
                return False, "side-effect violation: undeclared mutation substitution"

        # 5. Transaction safety invariants
        tx_state = state.context.get("tx_state")
        if tx_state == "unknown_ack" and not candidate.is_idempotent:
            return False, "transaction safety violation: blind replay forbidden under UNKNOWN_ACK"

        if tx_state == "partial_mutation" and not candidate.is_idempotent and not candidate.metadata.get("can_compensate"):
            return False, "transaction safety violation: uncompensated retry under partial mutation"

        # 6. Max risk class threshold
        max_risk = state.context.get("max_risk")
        if max_risk == "low" and candidate.risk_class in ("medium", "high", "destructive"):
            return False, f"risk threshold exceeded: {candidate.risk_class} > {max_risk}"

        # 7. Contract & Schema validity
        is_valid, reason = contract.validate_candidate(candidate, state)
        if not is_valid:
            return False, reason

        return True, "passed hard constraints"

    @abstractmethod
    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        """Resolve proposed action into a validated executable candidate."""
        pass


class StaticPriorityResolver(BaseResolver):
    """Static Priority Resolver.

    Selects the first valid candidate in static priority/registration order.
    Does not evaluate dynamic health, freshness, or adaptive historical learning.
    """

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        cands = candidates if candidates is not None else self.generate_candidates(proposal, state)
        rejected: dict[str, str] = {}
        contract = ExecutionContract.from_action(proposal)

        for cand in cands:
            is_valid, reason = self.evaluate_hard_constraints(cand, proposal, state, contract)
            if not is_valid:
                rejected[cand.tool] = reason
                continue

            return ResolutionResult(
                selected_candidate=cand,
                rejected_candidates=rejected,
                decision=ResolutionDecision.SELECT.value,
                reason=f"selected first statically valid candidate '{cand.tool}'",
                confidence=1.0,
                risk_level=cand.risk_class or RiskLevel.LOW.value,
            )

        return ResolutionResult(
            selected_candidate=None,
            rejected_candidates=rejected,
            decision=ResolutionDecision.DENY.value,
            reason="all candidates failed static validation",
            confidence=1.0,
            risk_level=proposal.risk_class or RiskLevel.LOW.value,
        )


class HealthAwareResolver(BaseResolver):
    """Health-Aware Resolver.

    Enforces hard safety constraints and filters out unhealthy or degraded replicas.
    """

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        cands = candidates if candidates is not None else self.generate_candidates(proposal, state)
        rejected: dict[str, str] = {}
        contract = ExecutionContract.from_action(proposal)
        healthy_candidates: list[ExecutableAction] = []

        for cand in cands:
            is_valid, reason = self.evaluate_hard_constraints(cand, proposal, state, contract)
            if not is_valid:
                rejected[cand.tool] = reason
                continue

            # Health check
            is_healthy = cand.metadata.get("healthy", True)
            tool_def = self.registry.get(cand.tool)
            if tool_def is not None and not tool_def.healthy:
                is_healthy = False

            if not is_healthy:
                rejected[cand.tool] = "candidate replica is unhealthy or degraded"
                continue

            healthy_candidates.append(cand)

        if healthy_candidates:
            selected = healthy_candidates[0]
            return ResolutionResult(
                selected_candidate=selected,
                rejected_candidates=rejected,
                decision=ResolutionDecision.SELECT.value,
                reason=f"selected healthy candidate '{selected.tool}'",
                confidence=1.0,
                risk_level=selected.risk_class or RiskLevel.LOW.value,
            )

        return ResolutionResult(
            selected_candidate=None,
            rejected_candidates=rejected,
            decision=ResolutionDecision.DENY.value if rejected else ResolutionDecision.DEFER.value,
            reason="no healthy candidate available",
            confidence=1.0,
            risk_level=proposal.risk_class or RiskLevel.LOW.value,
        )


class FreshnessAwareResolver(BaseResolver):
    """Freshness-Aware Resolver.

    Enforces hard safety constraints and selects candidates meeting required data freshness thresholds.
    """

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        cands = candidates if candidates is not None else self.generate_candidates(proposal, state)
        rejected: dict[str, str] = {}
        contract = ExecutionContract.from_action(proposal)
        max_freshness = (
            proposal.metadata.get("max_freshness_sec")
            or state.context.get("max_freshness_sec")
            or contract.max_freshness_sec
        )

        valid_cands: list[tuple[ExecutableAction, float]] = []
        for cand in cands:
            is_valid, reason = self.evaluate_hard_constraints(cand, proposal, state, contract)
            if not is_valid:
                rejected[cand.tool] = reason
                continue

            cand_freshness = cand.metadata.get("freshness_sec")
            if cand_freshness is None:
                cand_freshness = 0.0
            else:
                cand_freshness = float(cand_freshness)

            if max_freshness is not None and cand_freshness > float(max_freshness):
                rejected[cand.tool] = (
                    f"freshness violated: {cand_freshness}s exceeds max threshold {max_freshness}s"
                )
                continue

            valid_cands.append((cand, cand_freshness))

        if valid_cands:
            valid_cands.sort(key=lambda x: x[1])
            selected = valid_cands[0][0]
            return ResolutionResult(
                selected_candidate=selected,
                rejected_candidates=rejected,
                decision=ResolutionDecision.SELECT.value,
                reason=f"selected freshest candidate '{selected.tool}' ({valid_cands[0][1]}s)",
                confidence=1.0,
                risk_level=selected.risk_class or RiskLevel.LOW.value,
            )

        return ResolutionResult(
            selected_candidate=None,
            rejected_candidates=rejected,
            decision=ResolutionDecision.DENY.value if rejected else ResolutionDecision.DEFER.value,
            reason="no candidate satisfied freshness constraints",
            confidence=1.0,
            risk_level=proposal.risk_class or RiskLevel.LOW.value,
        )


class PolicyAwareResolver(BaseResolver):
    """Policy-Aware Resolver.

    Enforces strict hard constraints:
    - Authorization (state.permissions vs tool permissions)
    - Tenant isolation (state.tenant == candidate.tenant)
    - Capability compatibility (state required capabilities)
    - Contract validity (schema, parameter requirements)
    - Side-effect safety (cannot substitute mutation for read or undeclared side-effects)
    - Transaction invariants (TransactionState, active tx consistency)
    - Explicit policy denial (blocked tools or forbidden actions)

    Negative Control: If the proposed action is policy-allowed and satisfies all constraints,
    it is preserved directly (0 unnecessary interventions).
    """

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        cands = candidates if candidates is not None else self.generate_candidates(proposal, state)
        rejected: dict[str, str] = {}
        allowed_cands: list[ExecutableAction] = []

        # 1. Tenant check context
        state_tenant = state.context.get("tenant") or state.agent

        # 2. Blocked tools context
        blocked_tools = set(state.context.get("blocked_tools", []))

        # 3. Required capabilities context
        req_capabilities = set(state.context.get("required_capabilities", []))

        # 4. Transaction state context
        tx_state = state.context.get("tx_state")
        in_tx = state.context.get("in_transaction", False)

        contract = ExecutionContract.from_action(proposal)

        for cand in cands:
            tool_name = cand.tool

            # Hard Constraint 0: Explicit policy denial
            if tool_name in blocked_tools:
                rejected[tool_name] = "explicit policy denial: tool is blocked"
                continue

            # Hard Constraint 1: Tenant isolation
            cand_tenant = cand.metadata.get("tenant")
            if cand_tenant is not None and state_tenant is not None and cand_tenant != state_tenant:
                rejected[tool_name] = f"tenant mismatch: expected {state_tenant}, got {cand_tenant}"
                continue

            # Hard Constraint 2: Authorization / Permissions
            if cand.required_permissions:
                if not set(cand.required_permissions).issubset(state.permissions):
                    unauth = set(cand.required_permissions) - state.permissions
                    rejected[tool_name] = f"authorization error: missing permissions {unauth}"
                    continue

            # Hard Constraint 3: Capability compatibility
            cand_caps = set(cand.metadata.get("capabilities", []))
            if req_capabilities and not req_capabilities.issubset(cand_caps):
                missing_caps = req_capabilities - cand_caps
                rejected[tool_name] = f"capability mismatch: missing required {missing_caps}"
                continue

            # Hard Constraint 4: Side-effect safety
            cand_sec = cand.metadata.get("side_effect_class", "read_only")
            if contract.side_effect_class == SideEffectClass.READ_ONLY:
                if cand_sec in ("non_idempotent_mutation", "destructive"):
                    rejected[tool_name] = f"side-effect safety violation: mutating candidate for read action"
                    continue

            if not cand.is_idempotent and cand.tool != proposal.tool:
                # Disallow undeclared mutation substitutions
                equivs = self.registry.get_equivalents(proposal.tool)
                if cand.tool not in equivs:
                    rejected[tool_name] = "side-effect safety violation: undeclared mutation substitution"
                    continue

            # Hard Constraint 5: Transaction safety invariants
            if tx_state == "unknown_ack" and not cand.is_idempotent:
                # Invariant: UNKNOWN_ACK + non-idempotent mutation = NO BLIND REPLAY
                rejected[tool_name] = "transaction safety violation: blind replay forbidden under UNKNOWN_ACK"
                continue

            if tx_state == "partial_mutation" and not cand.is_idempotent and not cand.metadata.get("can_compensate"):
                rejected[tool_name] = "transaction safety violation: uncompensated retry under partial mutation"
                continue

            # Hard Constraint 6: Contract & Schema validity
            is_valid, reason = contract.validate_candidate(cand, state)
            if not is_valid:
                rejected[tool_name] = reason
                continue

            allowed_cands.append(cand)

        # Negative control: if original proposed tool is allowed, preserve it
        for cand in allowed_cands:
            if cand.tool == proposal.tool:
                return ResolutionResult(
                    selected_candidate=cand,
                    rejected_candidates=rejected,
                    decision=ResolutionDecision.SELECT.value,
                    reason="preserved valid proposed action (negative control: no intervention needed)",
                    confidence=1.0,
                    risk_level=cand.risk_class or RiskLevel.LOW.value,
                )

        if allowed_cands:
            selected = allowed_cands[0]
            return ResolutionResult(
                selected_candidate=selected,
                rejected_candidates=rejected,
                decision=ResolutionDecision.SELECT.value,
                reason=f"selected policy-compliant equivalent candidate '{selected.tool}'",
                confidence=1.0,
                risk_level=selected.risk_class or RiskLevel.LOW.value,
            )

        return ResolutionResult(
            selected_candidate=None,
            rejected_candidates=rejected,
            decision=ResolutionDecision.DENY.value,
            reason="no candidate satisfied hard policy constraints",
            confidence=1.0,
            risk_level=proposal.risk_class or RiskLevel.LOW.value,
        )


class VeyraResolver(BaseResolver):
    """Complete Veyra Resolution Layer (Sections 2 & 3).

    Pipeline:
    Agent Proposed Action
            ↓
    Candidate Generation
            ↓
    Hard Constraint Filtering (authorization, tenant, capability, contract, side-effects, transaction, explicit denial)
            ↓
    Policy Resolution
            ↓
    State / Health / Freshness Checks
            ↓
    Preference Ranking (health, latency, freshness, reliability, history, cost, Case Memory)
            ↓
    Execution Decision

    Formal Invariant:
    - Routing may select ONLY from policy-allowed candidates.
    - Routing must NEVER widen the policy-allowed action space.
    - Soft preferences (including Case Memory) must NEVER override hard constraints.
    - Negative control: If original action is safe and valid, zero unnecessary intervention.
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        case_memory: Any | None = None,
        enable_case_memory: bool = False,
    ):
        super().__init__(registry)
        self.case_memory = case_memory
        self.enable_case_memory = enable_case_memory

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        candidates: list[ExecutableAction] | None = None,
    ) -> ResolutionResult:
        start_time = time.perf_counter()

        # Step 1: Candidate Generation
        all_candidates = candidates if candidates is not None else self.generate_candidates(proposal, state)

        rejected: dict[str, str] = {}
        evaluations: list[CandidateEvaluation] = []
        policy_allowed_candidates: list[tuple[ExecutableAction, CandidateEvaluation]] = []

        # Context constraints
        state_tenant = state.context.get("tenant") or state.agent
        blocked_tools = set(state.context.get("blocked_tools", []))
        req_capabilities = set(state.context.get("required_capabilities", []))
        tx_state = state.context.get("tx_state")
        max_risk = state.context.get("max_risk")
        contract = ExecutionContract.from_action(proposal)

        # Step 2: Hard Constraint Filtering
        for cand in all_candidates:
            tool_name = cand.tool
            eval_record = CandidateEvaluation(candidate=cand)

            # Hard Constraint: Explicit policy denial
            if tool_name in blocked_tools:
                eval_record.is_valid = False
                eval_record.policy_allowed = False
                eval_record.rejection_reason = "explicit policy denial: tool is blocked"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            # Hard Constraint: Tenant isolation
            cand_tenant = cand.metadata.get("tenant")
            if cand_tenant is not None and state_tenant is not None and cand_tenant != state_tenant:
                eval_record.is_valid = False
                eval_record.tenant_matched = False
                eval_record.rejection_reason = f"tenant mismatch: expected {state_tenant}, got {cand_tenant}"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            # Hard Constraint: Authorization & Permissions
            if cand.required_permissions:
                if not set(cand.required_permissions).issubset(state.permissions):
                    eval_record.is_valid = False
                    eval_record.authorized = False
                    unauth = set(cand.required_permissions) - state.permissions
                    eval_record.rejection_reason = f"unauthorized: missing permissions {unauth}"
                    rejected[tool_name] = eval_record.rejection_reason
                    evaluations.append(eval_record)
                    continue

            # Hard Constraint: Capability compatibility
            cand_caps = set(cand.metadata.get("capabilities", []))
            if req_capabilities and not req_capabilities.issubset(cand_caps):
                eval_record.is_valid = False
                eval_record.capability_compatible = False
                missing = req_capabilities - cand_caps
                eval_record.rejection_reason = f"capability mismatch: missing {missing}"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            # Hard Constraint: Risk class threshold
            if max_risk == "low" and cand.risk_class in ("medium", "high", "destructive"):
                eval_record.is_valid = False
                eval_record.policy_allowed = False
                eval_record.rejection_reason = f"risk threshold exceeded: {cand.risk_class} > {max_risk}"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            # Hard Constraint: Side-effect safety
            cand_sec = cand.metadata.get("side_effect_class", "read_only")
            if contract.side_effect_class == SideEffectClass.READ_ONLY:
                if cand_sec in ("non_idempotent_mutation", "destructive"):
                    eval_record.is_valid = False
                    eval_record.side_effect_safe = False
                    eval_record.rejection_reason = "side-effect violation: mutating candidate for read action"
                    rejected[tool_name] = eval_record.rejection_reason
                    evaluations.append(eval_record)
                    continue

            if not cand.is_idempotent and cand.tool != proposal.tool:
                equivs = self.registry.get_equivalents(proposal.tool)
                if cand.tool not in equivs:
                    eval_record.is_valid = False
                    eval_record.side_effect_safe = False
                    eval_record.rejection_reason = "side-effect violation: undeclared mutation substitution"
                    rejected[tool_name] = eval_record.rejection_reason
                    evaluations.append(eval_record)
                    continue

            # Hard Constraint: Transaction safety invariants
            if tx_state == "unknown_ack" and not cand.is_idempotent:
                eval_record.is_valid = False
                eval_record.transaction_safe = False
                eval_record.rejection_reason = "transaction safety: blind replay forbidden under UNKNOWN_ACK"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            if tx_state == "partial_mutation" and not cand.is_idempotent and not cand.metadata.get("can_compensate"):
                eval_record.is_valid = False
                eval_record.transaction_safe = False
                eval_record.rejection_reason = "transaction safety: uncompensated retry under partial mutation"
                rejected[tool_name] = eval_record.rejection_reason
                evaluations.append(eval_record)
                continue

            # Hard Constraint: Schema & ExecutionContract validity
            is_valid, reason = contract.validate_candidate(cand, state)
            if not is_valid:
                eval_record.is_valid = False
                eval_record.contract_valid = False
                eval_record.rejection_reason = reason
                rejected[tool_name] = reason
                evaluations.append(eval_record)
                continue

            # Passed all hard constraints: candidate is policy-allowed!
            policy_allowed_candidates.append((cand, eval_record))

        if not policy_allowed_candidates:
            latency_us = (time.perf_counter() - start_time) * 1_000_000.0
            return ResolutionResult(
                selected_candidate=None,
                rejected_candidates=rejected,
                decision=ResolutionDecision.DENY.value,
                reason="all candidates rejected by hard constraints or policy",
                confidence=1.0,
                risk_level=proposal.risk_class or RiskLevel.LOW.value,
                evaluations=evaluations,
                metadata={"latency_us": latency_us, "candidates_count": len(all_candidates)},
            )

        # Step 3 & 4: State / Health / Freshness Checks & Soft Preference Ranking
        # Soft preferences:
        # - Health (healthy = 1.0, degraded = 0.0)
        # - Latency (lower latency = higher score)
        # - Freshness (lower freshness_sec = higher score)
        # - Reliability (0.0 to 1.0)
        # - Historical success (from state or history)
        # - Case Memory evidence (influences ranking ONLY, never overrides hard constraints)

        ranked_candidates: list[tuple[float, ExecutableAction, CandidateEvaluation]] = []

        max_freshness = (
            proposal.metadata.get("max_freshness_sec")
            or state.context.get("max_freshness_sec")
            or contract.max_freshness_sec
        )

        for cand, eval_record in policy_allowed_candidates:
            # 1. Health score
            is_healthy = cand.metadata.get("healthy", True)
            tool_def = self.registry.get(cand.tool)
            if tool_def is not None and not tool_def.healthy:
                is_healthy = False
            health_score = 100.0 if is_healthy else 0.0
            eval_record.health_score = health_score

            # 2. Freshness score
            cand_freshness = cand.metadata.get("freshness_sec")
            if cand_freshness is None:
                freshness_score = 50.0
            else:
                f_sec = float(cand_freshness)
                if max_freshness is not None and f_sec > float(max_freshness):
                    # Penalize stale candidate heavily in ranking
                    freshness_score = 0.0
                else:
                    freshness_score = max(0.0, 50.0 - f_sec)
            eval_record.freshness_score = freshness_score

            # 3. Reliability score (0.0 to 1.0 -> 0 to 50)
            rel = float(cand.metadata.get("reliability", 1.0))
            rel_score = rel * 50.0
            eval_record.reliability_score = rel_score

            # 4. Latency score (lower ms -> higher score)
            lat = float(cand.metadata.get("latency_ms", 10.0))
            lat_score = max(0.0, 50.0 - (lat / 10.0))
            eval_record.latency_score = lat_score

            # 5. History / Evidence score
            hist_score = 0.0
            history_data = state.context.get("history_success_rates", {})
            if cand.tool in history_data:
                hist_score = float(history_data[cand.tool]) * 20.0
            eval_record.history_score = hist_score

            # 6. Case Memory evidence (if enabled)
            case_memory_score = 0.0
            if self.enable_case_memory and self.case_memory is not None:
                try:
                    case_memory_score = float(self.case_memory.query_score(cand.tool, state))
                except Exception:
                    case_memory_score = 0.0

            # 7. Proposal affinity bonus (Negative Control: preserve original proposal if healthy and valid)
            proposal_bonus = 25.0 if cand.tool == proposal.tool and is_healthy and freshness_score > 0 else 0.0

            total_score = (
                health_score
                + freshness_score
                + rel_score
                + lat_score
                + hist_score
                + case_memory_score
                + proposal_bonus
            )
            eval_record.total_score = total_score
            evaluations.append(eval_record)
            ranked_candidates.append((total_score, cand, eval_record))

        # Sort by total score descending
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, selected_cand, best_eval = ranked_candidates[0]

        # Calculate confidence
        if len(ranked_candidates) > 1 and ranked_candidates[0][0] > 0:
            confidence = min(1.0, 0.7 + (ranked_candidates[0][0] / 300.0) * 0.3)
        else:
            confidence = 1.0

        latency_us = (time.perf_counter() - start_time) * 1_000_000.0

        # Construct resolution reason
        if selected_cand.tool == proposal.tool:
            reason = "proposed action verified: policy-allowed, healthy, and optimal (negative control: 0 intervention)"
        else:
            reason = f"resolved to policy-valid candidate '{selected_cand.tool}' (score={best_score:.1f})"

        return ResolutionResult(
            selected_candidate=selected_cand,
            rejected_candidates=rejected,
            decision=ResolutionDecision.SELECT.value,
            reason=reason,
            confidence=confidence,
            risk_level=selected_cand.risk_class or RiskLevel.LOW.value,
            evaluations=evaluations,
            metadata={
                "latency_us": latency_us,
                "candidates_count": len(all_candidates),
                "policy_allowed_count": len(policy_allowed_candidates),
                "selected_score": best_score,
            },
        )
