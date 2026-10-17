r"""Veyra Working Example: Policy-Aware Candidate Resolution (Section 29).

Demonstrates:
- Automatic candidate resolution across healthy, degraded, and policy-restricted tool replicas.

Run from fresh checkout:
python examples/routing/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import VeyraResolver


def run_demo():
    print("=" * 60)
    print("VEYRA DEMO: POLICY-AWARE RESOLUTION & REPLICA SELECTION")
    print("=" * 60)

    reg = ToolRegistry()
    # Primary tool is degraded/unhealthy
    reg.register(ToolDefinition(name="sql_query_v1", healthy=False, latency_ms=100.0, permissions=["read:db"], side_effect_class="read_only"))
    # Healthy replica
    reg.register(ToolDefinition(name="sql_query_v2", healthy=True, latency_ms=12.0, permissions=["read:db"], side_effect_class="read_only"))
    # Unauthorized replica
    reg.register(ToolDefinition(name="sql_query_root", healthy=True, latency_ms=1.0, permissions=["admin:root"], side_effect_class="read_only"))

    reg.register_equivalence("sql_query_v1", ["sql_query_v1", "sql_query_v2", "sql_query_root"])
    resolver = VeyraResolver(reg)

    state = ExecutionState(agent="analytics_agent", permissions={"read:db"})
    proposal = ExecutableAction(tool="sql_query_v1", arguments={"sql": "SELECT 1;"}, metadata={"side_effect_class": "read_only"})

    print("\nAgent proposed degraded tool: sql_query_v1")
    res = resolver.resolve(proposal, state)

    print(f"Veyra Decision: {res.decision}")
    print(f"Selected Candidate: {res.selected_candidate.tool}")
    print(f"Rejected Candidates: {res.rejected_candidates}")
    print(f"Resolution Reason: {res.reason}")
    print("Result: Resolved to healthy, authorized replica sql_query_v2 while blocking unauthorized sql_query_root!")


if __name__ == "__main__":
    run_demo()
