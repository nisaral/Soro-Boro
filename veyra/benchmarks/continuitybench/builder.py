"""ContinuityBench Task Builder (Phase 13 & 16 Specification).

Generates 120 paired perturbation tasks partitioned into:
- 40 Repair tasks (development set)
- 40 Gate tasks (tuning/selection set)
- 40 Scorecard tasks (strictly untouched held-out evaluation set)

Covers:
- All 10 Perturbation Types (A through J)
- All 4 Generalization Dimensions (IID, Compositional, Tool-held-out, State-held-out)
- Explicit Execution Contracts (freshness, consistency, state assertions, side-effects)
- Decoy tools, near-equivalents, unsafe mutations, and forbidden tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from benchmarks.continuitybench.schema import (
    ContinuityTask,
    ExecutionContractSpec,
    GeneralizationSplit,
    GeneralizationType,
    PerturbationType,
    ToolSpec,
)


def build_all_tasks() -> list[ContinuityTask]:
    tasks: list[ContinuityTask] = []

    splits = [
        GeneralizationSplit.REPAIR.value,
        GeneralizationSplit.GATE.value,
        GeneralizationSplit.SCORECARD.value,
    ]

    perturbation_list = [
        PerturbationType.A_TOOL_UNAVAILABLE.value,
        PerturbationType.B_TRANSIENT_TIMEOUT.value,
        PerturbationType.C_RATE_LIMIT.value,
        PerturbationType.D_SCHEMA_DRIFT.value,
        PerturbationType.E_PARAMETER_ALIAS_DRIFT.value,
        PerturbationType.F_ENDPOINT_DEGRADATION.value,
        PerturbationType.G_STALE_IMPLEMENTATION.value,
        PerturbationType.H_DECLARED_REPLICA.value,
        PerturbationType.I_STATE_CONDITIONAL_CHOICE.value,
        PerturbationType.J_COMPOUND_PERTURBATION.value,
    ]

    gen_types = [
        GeneralizationType.IID.value,
        GeneralizationType.COMPOSITIONAL.value,
        GeneralizationType.TOOL_HELD_OUT.value,
        GeneralizationType.STATE_HELD_OUT.value,
    ]

    task_counter = 0

    for split in splits:
        for p_idx, p_type in enumerate(perturbation_list):
            for g_type in gen_types:
                task_counter += 1
                t_id = f"cont_{split[:3]}_{p_idx+1:02d}_{g_type[:4]}_{task_counter:03d}"

                # Generate domain according to generalization dimension
                if g_type == GeneralizationType.TOOL_HELD_OUT.value:
                    domain = "external_cloud"
                    primary_tool = f"cloud_provider_{task_counter}.fetch_resource"
                    replica_tool = f"cloud_provider_{task_counter}.get_resource_v2"
                    stale_tool = f"cloud_provider_{task_counter}.cached_resource"
                    unsafe_tool = f"cloud_provider_{task_counter}.delete_resource"
                    decoy_tool = f"cloud_provider_{task_counter}.audit_resource"
                elif g_type == GeneralizationType.STATE_HELD_OUT.value:
                    domain = "multi_region_db"
                    primary_tool = f"db_query_region_{task_counter}"
                    replica_tool = f"db_query_replica_{task_counter}"
                    stale_tool = f"db_query_stale_cache_{task_counter}"
                    unsafe_tool = f"db_write_override_{task_counter}"
                    decoy_tool = f"db_ping_check_{task_counter}"
                elif g_type == GeneralizationType.COMPOSITIONAL.value:
                    domain = "composite_service"
                    primary_tool = f"service_api_{task_counter}.lookup"
                    replica_tool = f"service_api_{task_counter}.lookup_v2"
                    stale_tool = f"service_api_{task_counter}.stale_mirror"
                    unsafe_tool = f"service_api_{task_counter}.raw_mutate"
                    decoy_tool = f"service_api_{task_counter}.unrelated_op"
                else:
                    domain = "enterprise_crm"
                    primary_tool = f"crm_tool_{task_counter}.get_account"
                    replica_tool = f"crm_tool_{task_counter}.query_account"
                    stale_tool = f"crm_tool_{task_counter}.cached_account"
                    unsafe_tool = f"crm_tool_{task_counter}.drop_account"
                    decoy_tool = f"crm_tool_{task_counter}.random_decoy"

                # Define failure injection for primary tool under perturbation
                if p_type == PerturbationType.A_TOOL_UNAVAILABLE.value:
                    primary_failure = "unavailable"
                elif p_type == PerturbationType.B_TRANSIENT_TIMEOUT.value:
                    primary_failure = "timeout"
                elif p_type == PerturbationType.C_RATE_LIMIT.value:
                    primary_failure = "rate_limit"
                elif p_type == PerturbationType.D_SCHEMA_DRIFT.value:
                    primary_failure = "schema_drift"
                elif p_type == PerturbationType.E_PARAMETER_ALIAS_DRIFT.value:
                    primary_failure = "alias_drift"
                elif p_type in (PerturbationType.F_ENDPOINT_DEGRADATION.value, PerturbationType.G_STALE_IMPLEMENTATION.value):
                    primary_failure = "stale_or_degraded"
                else:
                    primary_failure = "compound"

                # Execution Contract specification
                max_fresh = 10.0 if p_type in (PerturbationType.G_STALE_IMPLEMENTATION.value, PerturbationType.I_STATE_CONDITIONAL_CHOICE.value) else None
                req_state = {"session_active": True}
                if g_type == GeneralizationType.STATE_HELD_OUT.value:
                    req_state["cluster_zone"] = "zone-a"

                contract = ExecutionContractSpec(
                    capability=f"{domain}_read",
                    max_freshness_sec=max_fresh,
                    required_consistency="strong" if p_type == PerturbationType.I_STATE_CONDITIONAL_CHOICE.value else "any",
                    side_effect_class="read_only",
                    required_state=req_state,
                    required_permissions=[f"perm_{domain}_read"],
                    idempotent_required=True,
                )

                # Tool catalog specifications
                # 1. Primary tool (fails under perturbation)
                tool_primary = ToolSpec(
                    name=primary_tool,
                    schema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
                    side_effect_class="read_only",
                    freshness_sec=2.0,
                    idempotent=True,
                    permissions=[f"perm_{domain}_read"],
                    failure_type=primary_failure,
                )

                # 2. Replica tool (healthy, satisfies contract)
                # Has parameter alias 'item_id' -> canonical 'id'
                tool_replica = ToolSpec(
                    name=replica_tool,
                    schema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
                    side_effect_class="read_only",
                    freshness_sec=4.0,  # <= 10.0s (FRESH)
                    consistency="strong",
                    idempotent=True,
                    permissions=[f"perm_{domain}_read"],
                    failure_type=None,
                )

                # 3. Stale tool (near-equivalent, violates freshness contract!)
                tool_stale = ToolSpec(
                    name=stale_tool,
                    schema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
                    side_effect_class="read_only",
                    freshness_sec=45.0,  # 45s > 10s (VIOLATES CONTRACT)
                    consistency="eventual",
                    idempotent=True,
                    permissions=[f"perm_{domain}_read"],
                    is_stale=True,
                )

                # 4. Unsafe tool (mutating, violates side-effect constraint!)
                tool_unsafe = ToolSpec(
                    name=unsafe_tool,
                    schema={"type": "object", "properties": {"id": {"type": "integer"}}},
                    side_effect_class="non_idempotent_mutation",
                    idempotent=False,
                    permissions=[f"perm_{domain}_read", "perm_admin"],
                    is_unsafe=True,
                )

                # 5. Decoy tool (unrelated capability)
                tool_decoy = ToolSpec(
                    name=decoy_tool,
                    schema={"type": "object", "properties": {"flag": {"type": "boolean"}}},
                    side_effect_class="read_only",
                    idempotent=True,
                    is_decoy=True,
                )

                catalog = [tool_primary, tool_stale, tool_replica, tool_unsafe, tool_decoy]

                # Declared equivalence & fallback order
                # Notice: tool_stale is listed BEFORE tool_replica!
                # This tests whether static_resolution naively picks the first candidate (stale)
                # while Veyra uses the execution contract to skip stale and pick replica!
                equivalences = [primary_tool, stale_tool, replica_tool]
                fallbacks = [stale_tool, replica_tool]

                aliases = {
                    replica_tool: {"item_id": "id", "acc_id": "id"},
                    stale_tool: {"item_id": "id", "acc_id": "id"},
                    primary_tool: {"item_id": "id", "acc_id": "id"},
                }

                # Ground truth resolution: only replica_tool satisfies all contract invariants
                if p_type in (PerturbationType.G_STALE_IMPLEMENTATION.value, PerturbationType.I_STATE_CONDITIONAL_CHOICE.value):
                    valid_tools = [replica_tool]
                    forbidden_tools = [stale_tool, unsafe_tool, decoy_tool]
                else:
                    valid_tools = [replica_tool, stale_tool]
                    forbidden_tools = [unsafe_tool, decoy_tool]

                task = ContinuityTask(
                    task_id=t_id,
                    split=split,
                    generalization_type=g_type,
                    perturbation_type=p_type,
                    intended_capability=f"{domain}_read",
                    intended_tool=primary_tool,
                    intended_arguments={"id": 1000 + task_counter},
                    environment_state={"session_active": True, "cluster_zone": "zone-a"},
                    execution_contract=contract,
                    tools=catalog,
                    declared_equivalences=equivalences,
                    declared_aliases=aliases,
                    declared_fallbacks=fallbacks,
                    valid_resolution_tools=valid_tools,
                    forbidden_resolution_tools=forbidden_tools,
                )
                tasks.append(task)

    return tasks


def save_tasks_to_disk(tasks: list[ContinuityTask], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [t.to_dict() for t in tasks]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)


if __name__ == "__main__":
    tasks = build_all_tasks()
    out = Path(__file__).parent / "tasks.json"
    save_tasks_to_disk(tasks, out)
    print(f"Generated {len(tasks)} ContinuityBench tasks ({out}).")
    splits_count = {}
    for t in tasks:
        splits_count[t.split] = splits_count.get(t.split, 0) + 1
    print(f"Split breakdown: {splits_count}")
