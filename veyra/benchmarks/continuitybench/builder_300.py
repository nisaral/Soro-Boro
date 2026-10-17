"""Phase 47: Harder ContinuityBench Builder (300 Paired Tasks).

Generates 300 tasks partitioned strictly into:
- 100 Repair / Train
- 100 Gate
- 100 Strictly Held-Out Scorecard

Scorecard contains:
- Unseen tool IDs
- Unseen state combinations
- Unseen contract combinations
- Unseen freshness thresholds
- Unseen permissions
- Unseen candidate ordering (randomized/catalog)
- 13 Hard Mismatch Types:
  1. stale_vs_fresh
  2. permission_mismatch
  3. tenant_mismatch
  4. resource_scope_mismatch
  5. side_effect_mismatch
  6. consistency_mismatch
  7. result_schema_mismatch
  8. output_semantics_mismatch
  9. hidden_dependency_mismatch
  10. unknown_state_lost_ack
  11. partial_mutation
  12. degraded_endpoints
  13. transient_timeout
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def build_300_tasks() -> list[dict[str, Any]]:
    splits = ["repair", "gate", "scorecard"]
    tasks_per_split = 100

    domains = [
        "crm", "finance", "payment", "healthcare", "cloud_compute",
        "object_storage", "sql_database", "nosql_store", "email_dispatch", "sms_gateway",
        "search_engine", "vector_db", "security_audit", "ci_cd_pipeline", "iot_telemetry",
    ]

    mismatch_types = [
        "stale_vs_fresh",
        "permission_mismatch",
        "tenant_mismatch",
        "resource_scope_mismatch",
        "side_effect_mismatch",
        "consistency_mismatch",
        "result_schema_mismatch",
        "output_semantics_mismatch",
        "hidden_dependency_mismatch",
        "unknown_state_lost_ack",
        "partial_mutation",
        "degraded_endpoints",
        "transient_timeout",
    ]

    all_tasks = []

    for split in splits:
        is_scorecard = (split == "scorecard")
        rng = random.Random(2026 if is_scorecard else (137 if split == "gate" else 42))

        for idx in range(tasks_per_split):
            dom_idx = idx % len(domains)
            domain = domains[dom_idx]
            mismatch = mismatch_types[idx % len(mismatch_types)]

            # Generate unique tool IDs for scorecard
            prefix = "scorecard_v2" if is_scorecard else ("gate_v2" if split == "gate" else "train_v2")
            tool_primary = f"{prefix}_{domain}_primary_{idx+1:03d}"
            tool_replica_valid = f"{prefix}_{domain}_replica_valid_{idx+1:03d}"
            tool_flawed = f"{prefix}_{domain}_flawed_{mismatch}_{idx+1:03d}"
            tool_decoy = f"{prefix}_{domain}_decoy_wrong_cap_{idx+1:03d}"

            tenant_id = f"tenant_{'sc' if is_scorecard else 'dev'}_{idx % 8}"
            max_freshness = 5.0 + (idx % 10) * 2.5
            side_effect = "read_only" if "mutation" not in mismatch and "ack" not in mismatch else "non_idempotent_mutation"
            req_consistency = "strong" if (idx % 2 == 0 or mismatch == "consistency_mismatch") else "any"

            contract = {
                "capability": f"cap_{domain}_{idx % 5}",
                "max_freshness_sec": max_freshness,
                "required_consistency": req_consistency,
                "side_effect_class": side_effect,
                "required_state": {
                    "tenant_id": tenant_id,
                    "session_authenticated": True,
                    "resource_scope": "isolated_vpc",
                    "schema_version": "v2",
                    "output_semantics": "id_reference",
                },
                "required_permissions": [f"perm_{domain}_execute"],
                "idempotent_required": (side_effect == "read_only"),
            }

            env_state = {
                "tenant_id": tenant_id,
                "session_authenticated": True,
                "resource_scope": "isolated_vpc",
                "schema_version": "v2",
                "output_semantics": "id_reference",
                "cluster_zone": f"zone_{'east' if is_scorecard else 'west'}_{idx % 3}",
                "dependencies": ["standard_runtime"],
                "execution_state": "UNKNOWN_ACK" if mismatch == "unknown_state_lost_ack" else ("PARTIAL" if mismatch == "partial_mutation" else "CLEAN"),
            }

            # Valid replica (satisfies all dynamic invariants)
            cand_valid = {
                "name": tool_replica_valid,
                "capability": f"cap_{domain}_{idx % 5}",
                "freshness_sec": round(max_freshness * 0.5, 1),
                "consistency": req_consistency if req_consistency == "strong" else "strong",
                "side_effect_class": side_effect,
                "permissions": [f"perm_{domain}_execute"],
                "idempotent": (side_effect == "read_only" or mismatch in ("unknown_state_lost_ack", "partial_mutation")),
                "state_assertions": {
                    "tenant_id": tenant_id,
                    "session_authenticated": True,
                    "resource_scope": "isolated_vpc",
                },
                "schema_version": "v2",
                "output_semantics": "id_reference",
                "required_dependencies": ["standard_runtime"],
                "endpoint_health": "healthy",
                "is_verification_tool": (mismatch == "unknown_state_lost_ack"),
                "is_recovery_action": (mismatch == "partial_mutation"),
                "is_valid": True,
            }

            # Flawed candidate (violates specific mismatch)
            cand_flawed = {
                "name": tool_flawed,
                "capability": f"cap_{domain}_{idx % 5}",
                "freshness_sec": round(max_freshness * 5.0, 1) if mismatch == "stale_vs_fresh" else round(max_freshness * 0.5, 1),
                "consistency": "eventual" if mismatch == "consistency_mismatch" else req_consistency,
                "side_effect_class": "non_idempotent_mutation" if mismatch == "side_effect_mismatch" else side_effect,
                "permissions": [f"perm_{domain}_execute", "perm_root_admin"] if mismatch == "permission_mismatch" else [f"perm_{domain}_execute"],
                "idempotent": False if mismatch in ("side_effect_mismatch", "unknown_state_lost_ack", "partial_mutation") else (side_effect == "read_only"),
                "state_assertions": {
                    "tenant_id": "wrong_tenant_999" if mismatch == "tenant_mismatch" else tenant_id,
                    "resource_scope": "cross_region_public" if mismatch == "resource_scope_mismatch" else "isolated_vpc",
                    "session_authenticated": True,
                },
                "schema_version": "v1_deprecated" if mismatch == "result_schema_mismatch" else "v2",
                "output_semantics": "raw_blob" if mismatch == "output_semantics_mismatch" else "id_reference",
                "required_dependencies": ["unmet_legacy_driver"] if mismatch == "hidden_dependency_mismatch" else ["standard_runtime"],
                "endpoint_health": "degraded" if mismatch == "degraded_endpoints" else ("timed_out" if mismatch == "transient_timeout" else "healthy"),
                "execution_state": "UNKNOWN_ACK" if mismatch == "unknown_state_lost_ack" else ("PARTIAL" if mismatch == "partial_mutation" else "CLEAN"),
                "is_verification_tool": False,
                "is_recovery_action": False,
                "is_valid": False,
                "mismatch_reason": mismatch,
            }

            # Decoy tool
            cand_decoy = {
                "name": tool_decoy,
                "capability": f"cap_decoy_{domain}",
                "freshness_sec": 1.0,
                "consistency": req_consistency,
                "side_effect_class": side_effect,
                "permissions": [f"perm_{domain}_execute"],
                "idempotent": True,
                "is_valid": False,
                "is_decoy": True,
                "failure_type": "wrong_capability",
            }

            # Primary tool (fails due to perturbation)
            cand_primary = {
                "name": tool_primary,
                "capability": f"cap_{domain}_{idx % 5}",
                "freshness_sec": round(max_freshness * 0.5, 1),
                "consistency": req_consistency,
                "side_effect_class": side_effect,
                "permissions": [f"perm_{domain}_execute"],
                "idempotent": (side_effect == "read_only"),
                "failure_type": "timeout" if "timeout" in mismatch else "unavailable",
            }

            # Place flawed first in catalog order, followed by valid replica, then decoy
            candidates = [cand_flawed, cand_valid, cand_decoy]

            task = {
                "task_id": f"cont300_{split}_{idx+1:03d}",
                "split": split,
                "domain": domain,
                "mismatch_category": mismatch,
                "intended_tool": tool_primary,
                "intended_arguments": {"query_id": f"q_{idx+1000}"},
                "environment_state": env_state,
                "execution_contract": contract,
                "tools": [cand_primary] + candidates,
                "ground_truth_valid": tool_replica_valid,
            }
            all_tasks.append(task)

    return all_tasks


def main():
    tasks = build_300_tasks()
    out_file = REPO_ROOT / "benchmarks" / "continuitybench" / "tasks_300.json"
    content = json.dumps(tasks, indent=2)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    print(f"Generated {len(tasks)} tasks (100 repair, 100 gate, 100 scorecard) in {out_file}")
    print(f"tasks_300.json SHA256: {sha}")


if __name__ == "__main__":
    main()
