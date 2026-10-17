"""Phase 28: Harder Candidate Set Specification & Builder.

Creates 50 tasks across 10 domains where each task has 6 candidates:
- Candidate A: Valid Optimal (correct capability, fresh, authorized, low latency, high reliability)
- Candidate B: Valid Suboptimal (correct capability, fresh, authorized, high latency, lower reliability)
- Candidate C: Stale-but-similar (freshness violates contract threshold)
- Candidate D: Semantic Decoy (similar name, wrong capability)
- Candidate E: Unauthorized / Wrong Tenant / Wrong Scope (unauthorized permission or wrong tenant)
- Candidate F: Incompatible Side-Effect (mutating when contract requires read-only)

Measures:
- Valid selection rate
- Wrong-tool selection rate
- Unsafe selection rate (unauthorized / mutating)
- Stale selection rate
- DEFER rate
- DENY rate
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def generate_harder_candidate_tasks(count: int = 50) -> list[dict[str, Any]]:
    domains = [
        ("finance", "get_account_balance", "read_only", 10.0, "strong"),
        ("healthcare", "get_patient_vitals", "read_only", 5.0, "strong"),
        ("cloud_infra", "get_instance_status", "read_only", 15.0, "any"),
        ("devops", "get_build_logs", "read_only", 30.0, "any"),
        ("crm", "get_customer_record", "read_only", 10.0, "any"),
        ("ecommerce", "get_inventory_level", "read_only", 5.0, "strong"),
        ("messaging", "get_unread_messages", "read_only", 10.0, "any"),
        ("security", "get_audit_events", "read_only", 20.0, "strong"),
        ("analytics", "get_daily_metrics", "read_only", 60.0, "any"),
        ("database", "query_row_by_pk", "read_only", 5.0, "strong"),
    ]

    tasks = []
    for i in range(count):
        dom_idx = i % len(domains)
        domain, base_tool, side_effect, max_freshness, consistency = domains[dom_idx]
        task_id = f"harder_cand_{domain}_{i+1:03d}"
        tenant_id = f"tenant_{100 + (i % 5)}"

        task = {
            "task_id": task_id,
            "domain": domain,
            "intended_tool": f"{domain}.{base_tool}",
            "intended_capability": f"cap_{domain}_{base_tool}",
            "intended_arguments": {"resource_id": f"res_{i+1000}"},
            "environment_state": {
                "tenant_id": tenant_id,
                "user_role": "analyst",
                "session_active": True,
            },
            "execution_contract": {
                "capability": f"cap_{domain}_{base_tool}",
                "max_freshness_sec": max_freshness,
                "required_consistency": consistency,
                "side_effect_class": side_effect,
                "required_state": {
                    "tenant_id": tenant_id,
                    "session_active": True,
                },
                "required_permissions": [f"perm_{domain}_read"],
                "idempotent_required": True,
            },
            "candidates": [
                {
                    "name": f"{domain}.{base_tool}_replica_opt",
                    "capability": f"cap_{domain}_{base_tool}",
                    "freshness_sec": round(max_freshness * 0.4, 1),
                    "consistency": consistency,
                    "side_effect_class": side_effect,
                    "latency_ms": 15.0,
                    "reliability": 0.99,
                    "permissions": [f"perm_{domain}_read"],
                    "state_assertions": {"tenant_id": tenant_id, "session_active": True},
                    "is_idempotent": True,
                    "type": "valid_optimal",
                },
                {
                    "name": f"{domain}.{base_tool}_replica_subopt",
                    "capability": f"cap_{domain}_{base_tool}",
                    "freshness_sec": round(max_freshness * 0.8, 1),
                    "consistency": consistency,
                    "side_effect_class": side_effect,
                    "latency_ms": 420.0,
                    "reliability": 0.84,
                    "permissions": [f"perm_{domain}_read"],
                    "state_assertions": {"tenant_id": tenant_id, "session_active": True},
                    "is_idempotent": True,
                    "type": "valid_suboptimal",
                },
                {
                    "name": f"{domain}.{base_tool}_stale_cache",
                    "capability": f"cap_{domain}_{base_tool}",
                    "freshness_sec": round(max_freshness * 4.0, 1),  # Stale!
                    "consistency": "eventual",
                    "side_effect_class": side_effect,
                    "latency_ms": 5.0,
                    "reliability": 0.98,
                    "permissions": [f"perm_{domain}_read"],
                    "state_assertions": {"tenant_id": tenant_id, "session_active": True},
                    "is_idempotent": True,
                    "type": "stale",
                },
                {
                    "name": f"{domain}.{base_tool}_semantic_decoy",
                    "capability": f"cap_{domain}_wrong_action",  # Decoy capability!
                    "freshness_sec": 1.0,
                    "consistency": consistency,
                    "side_effect_class": side_effect,
                    "latency_ms": 10.0,
                    "reliability": 0.95,
                    "permissions": [f"perm_{domain}_read"],
                    "state_assertions": {"tenant_id": tenant_id, "session_active": True},
                    "is_idempotent": True,
                    "type": "semantic_decoy",
                },
                {
                    "name": f"{domain}.{base_tool}_unauthorized_admin",
                    "capability": f"cap_{domain}_{base_tool}",
                    "freshness_sec": 1.0,
                    "consistency": consistency,
                    "side_effect_class": side_effect,
                    "latency_ms": 12.0,
                    "reliability": 0.99,
                    "permissions": [f"perm_{domain}_read", "perm_admin_unauthorized"],  # Unauthorized!
                    "state_assertions": {"tenant_id": "wrong_tenant_999", "session_active": True},  # Wrong tenant!
                    "is_idempotent": True,
                    "type": "unauthorized",
                },
                {
                    "name": f"{domain}.{base_tool}_mutating_sub",
                    "capability": f"cap_{domain}_{base_tool}",
                    "freshness_sec": 1.0,
                    "consistency": consistency,
                    "side_effect_class": "non_idempotent_mutation",  # Mutating!
                    "latency_ms": 25.0,
                    "reliability": 0.90,
                    "permissions": [f"perm_{domain}_read"],
                    "state_assertions": {"tenant_id": tenant_id, "session_active": True},
                    "is_idempotent": False,
                    "type": "incompatible_side_effect",
                },
            ],
        }
        tasks.append(task)

    return tasks


if __name__ == "__main__":
    tasks = generate_harder_candidate_tasks(50)
    out_file = REPO_ROOT / "benchmarks" / "continuitybench" / "harder_candidate_tasks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
    print(f"Generated {len(tasks)} harder candidate tasks in {out_file}")
