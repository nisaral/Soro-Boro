"""Routing Evaluation Harness Scenarios (Section 4 & 5).

Generates 240 controlled test scenarios covering all 20 required categories:
1. healthy replica selection
2. unhealthy replica
3. stale replica
4. authorization mismatch
5. tenant mismatch
6. capability mismatch
7. schema mismatch
8. degraded latency
9. idempotent vs non-idempotent actions
10. UNKNOWN_ACK
11. partial mutation
12. verification available
13. verification unavailable
14. all candidates unsafe
15. no eligible candidate
16. conflicting soft preferences
17. Case Memory recommending an invalid candidate
18. valid candidate with poor historical performance
19. equivalent candidates
20. adversarial candidate metadata

Includes explicit negative controls where original action is already correct
to measure unnecessary interventions and no-op behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


@dataclass
class ResolutionScenario:
    """A controlled resolution evaluation scenario with ground truth expected outcome."""

    scenario_id: str
    category: str
    description: str
    proposal: ExecutableAction
    state: ExecutionState
    registry_tools: list[ToolDefinition]
    equivalences: dict[str, list[str]] = field(default_factory=dict)
    expected_decision: str = "select"  # "select" | "deny" | "defer"
    expected_selected_tool: str | None = None
    expected_rejected_tools: list[str] = field(default_factory=list)
    is_negative_control: bool = False
    hard_violation_types: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def build_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        for t in self.registry_tools:
            reg.register(t)
        for canon, equivs in self.equivalences.items():
            reg.register_equivalence(canon, equivs)
        return reg


CATEGORIES = [
    "healthy_replica_selection",
    "unhealthy_replica",
    "stale_replica",
    "authorization_mismatch",
    "tenant_mismatch",
    "capability_mismatch",
    "schema_mismatch",
    "degraded_latency",
    "idempotent_vs_non_idempotent",
    "unknown_ack",
    "partial_mutation",
    "verification_available",
    "verification_unavailable",
    "all_candidates_unsafe",
    "no_eligible_candidate",
    "conflicting_soft_preferences",
    "case_memory_recommending_invalid",
    "valid_candidate_poor_historical",
    "equivalent_candidates",
    "adversarial_candidate_metadata",
]


def generate_resolution_scenarios(n_per_category: int = 12) -> list[ResolutionScenario]:
    """Generate 240 controlled test scenarios covering all 20 categories."""
    scenarios: list[ResolutionScenario] = []

    for cat_idx, cat in enumerate(CATEGORIES):
        for i in range(1, n_per_category + 1):
            scen_id = f"res_{cat}_{i:02d}"
            # Half of category 1, 8, 16, 19 are pure negative controls (agent action already optimal)
            is_neg_ctrl = cat in ("healthy_replica_selection", "equivalent_candidates") and (i % 2 == 0)

            # Standard tools setup for each scenario
            primary_name = f"{cat}_tool_primary"
            replica_a = f"{cat}_replica_a"
            replica_b = f"{cat}_replica_b"

            tools: list[ToolDefinition] = []
            equivs = {primary_name: [primary_name, replica_a, replica_b]}
            state_ctx: dict[str, Any] = {"tenant": f"tenant_{i % 3 + 1}"}
            state_perms = {"read:data", "write:data"}
            hard_violations: list[str] = []

            # 1. healthy replica selection
            if cat == "healthy_replica_selection":
                tools.append(ToolDefinition(name=primary_name, healthy=True, latency_ms=10.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, latency_ms=15.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, latency_ms=25.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = primary_name

            # 2. unhealthy replica
            elif cat == "unhealthy_replica":
                tools.append(ToolDefinition(name=primary_name, healthy=False, latency_ms=5.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, latency_ms=12.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=False, latency_ms=8.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("unhealthy_replica")

            # 3. stale replica
            elif cat == "stale_replica":
                state_ctx["max_freshness_sec"] = 5.0
                tools.append(ToolDefinition(name=primary_name, healthy=True, freshness_sec=60.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, freshness_sec=1.5, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, freshness_sec=120.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only", "max_freshness_sec": 5.0})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("stale_data")

            # 4. authorization mismatch
            elif cat == "authorization_mismatch":
                state_perms = {"read:public"}
                tools.append(ToolDefinition(name=primary_name, healthy=True, permissions=["admin:delete"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, permissions=["read:public"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, permissions=["admin:write"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only", "permissions": ["admin:delete"]})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("authorization")

            # 5. tenant mismatch
            elif cat == "tenant_mismatch":
                state_ctx["tenant"] = "tenant_alpha"
                tools.append(ToolDefinition(name=primary_name, healthy=True, side_effect_class="read_only", metadata={"tenant": "tenant_beta"}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, side_effect_class="read_only", metadata={"tenant": "tenant_alpha"}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, side_effect_class="read_only", metadata={"tenant": "tenant_gamma"}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only", "tenant": "tenant_beta"})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("tenant")

            # 6. capability mismatch
            elif cat == "capability_mismatch":
                state_ctx["required_capabilities"] = ["vector_search", "filter"]
                tools.append(ToolDefinition(name=primary_name, healthy=True, capabilities=["keyword_search"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, capabilities=["vector_search", "filter", "aggregate"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, capabilities=["vector_search"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only", "capabilities": ["keyword_search"]})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("capability")

            # 7. schema mismatch
            elif cat == "schema_mismatch":
                schema_strict = {"type": "object", "required": ["query_str"], "properties": {"query_str": {"type": "string"}}}
                tools.append(ToolDefinition(name=primary_name, healthy=True, schema=schema_strict, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, schema={"type": "object", "properties": {"q": {"type": "string"}}}, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                # Primary tool missing required argument 'query_str' in proposal
                proposal = ExecutableAction(tool=primary_name, arguments={"wrong_arg": 123}, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("schema")

            # 8. degraded latency
            elif cat == "degraded_latency":
                tools.append(ToolDefinition(name=primary_name, healthy=True, latency_ms=850.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, latency_ms=12.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, latency_ms=450.0, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a  # selects lowest latency replica

            # 9. idempotent vs non-idempotent actions
            elif cat == "idempotent_vs_non_idempotent":
                # Agent proposed mutation action, but replica_a is read-only, replica_b is undeclared mutation
                tools.append(ToolDefinition(name=primary_name, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, idempotent=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("side_effect")

            # 10. UNKNOWN_ACK
            elif cat == "unknown_ack":
                state_ctx["tx_state"] = "unknown_ack"
                tools.append(ToolDefinition(name=primary_name, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, idempotent=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "non_idempotent_mutation", "is_idempotent": False})
                # Non-idempotent blind replay must be DENIED!
                expected_dec = "deny"
                expected_tool = None
                hard_violations.append("unknown_ack_blind_replay")

            # 11. partial mutation
            elif cat == "partial_mutation":
                state_ctx["tx_state"] = "partial_mutation"
                tools.append(ToolDefinition(name=primary_name, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, idempotent=False, side_effect_class="non_idempotent_mutation", metadata={"tenant": state_ctx["tenant"], "can_compensate": True}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "non_idempotent_mutation", "is_idempotent": False})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("partial_mutation")

            # 12. verification available
            elif cat == "verification_available":
                tools.append(ToolDefinition(name=primary_name, healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"], "verification_tool": "verify_order"}))
                tools.append(ToolDefinition(name="verify_order", healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = primary_name

            # 13. verification unavailable
            elif cat == "verification_unavailable":
                tools.append(ToolDefinition(name=primary_name, healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = primary_name

            # 14. all candidates unsafe
            elif cat == "all_candidates_unsafe":
                tools.append(ToolDefinition(name=primary_name, healthy=False, permissions=["admin:forbidden"], side_effect_class="destructive", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=False, permissions=["admin:forbidden"], side_effect_class="destructive", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "deny"
                expected_tool = None
                hard_violations.append("all_unsafe")

            # 15. no eligible candidate
            elif cat == "no_eligible_candidate":
                state_ctx["blocked_tools"] = [primary_name, replica_a, replica_b]
                tools.append(ToolDefinition(name=primary_name, healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "deny"
                expected_tool = None
                hard_violations.append("blocked_tools")

            # 16. conflicting soft preferences
            elif cat == "conflicting_soft_preferences":
                # replica_a has low latency but slightly higher cost; replica_b has lowest latency and high reliability
                tools.append(ToolDefinition(name=primary_name, healthy=True, latency_ms=100.0, reliability=0.80, cost=0.01, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, latency_ms=10.0, reliability=0.99, cost=0.05, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_b, healthy=True, latency_ms=150.0, reliability=0.99, cost=0.001, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a

            # 17. Case Memory recommending an invalid candidate
            elif cat == "case_memory_recommending_invalid":
                # Case memory recommends an unauthorized candidate
                tools.append(ToolDefinition(name=primary_name, healthy=True, permissions=["admin:super"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, permissions=["read:data"], side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a
                hard_violations.append("case_memory_invalid")

            # 18. valid candidate with poor historical performance
            elif cat == "valid_candidate_poor_historical":
                state_ctx["history_success_rates"] = {primary_name: 0.10, replica_a: 0.98}
                tools.append(ToolDefinition(name=primary_name, healthy=True, reliability=0.20, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, reliability=0.99, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = replica_a

            # 19. equivalent candidates
            elif cat == "equivalent_candidates":
                tools.append(ToolDefinition(name=primary_name, healthy=True, latency_ms=10.0, reliability=0.99, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, latency_ms=10.0, reliability=0.99, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = primary_name

            # 20. adversarial candidate metadata
            elif cat == "adversarial_candidate_metadata":
                # Adversarial replica claims fake risk="low" but has destructive side effect
                tools.append(ToolDefinition(name=primary_name, healthy=True, side_effect_class="read_only", metadata={"tenant": state_ctx["tenant"]}))
                tools.append(ToolDefinition(name=replica_a, healthy=True, risk_class="low", side_effect_class="destructive", metadata={"tenant": state_ctx["tenant"]}))
                proposal = ExecutableAction(tool=primary_name, metadata={"side_effect_class": "read_only"})
                expected_dec = "select"
                expected_tool = primary_name
                hard_violations.append("adversarial_metadata")

            scenarios.append(
                ResolutionScenario(
                    scenario_id=scen_id,
                    category=cat,
                    description=f"{cat} controlled test scenario #{i:02d}",
                    proposal=proposal,
                    state=ExecutionState(agent="bench_agent", permissions=set(state_perms), context=state_ctx),
                    registry_tools=tools,
                    equivalences=equivs,
                    expected_decision=expected_dec,
                    expected_selected_tool=expected_tool,
                    is_negative_control=is_neg_ctrl,
                    hard_violation_types=hard_violations,
                )
            )

    return scenarios
