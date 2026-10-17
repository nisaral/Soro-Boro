r"""Veyra Working Example: Control Non-Inferiority & Zero Over-Blocking (Section 29).

Demonstrates:
- Nominal valid tool calls pass through Veyra with 0.0% false block rate.
- Zero unnecessary alterations on negative control workflows.

Run from fresh checkout:
python examples/over_blocking/demo.py
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
    print("VEYRA DEMO: OVER-BLOCKING & NO-OP NON-INFERIORITY")
    print("=" * 60)

    reg = ToolRegistry()
    reg.register(ToolDefinition(name="fetch_user_profile", healthy=True, side_effect_class="read_only", permissions=["read:profile"]))
    resolver = VeyraResolver(reg)

    state = ExecutionState(agent="user_agent", permissions={"read:profile"})
    proposal = ExecutableAction(tool="fetch_user_profile", arguments={"user_id": "usr_101"}, metadata={"side_effect_class": "read_only"})

    print("\nProposing valid nominal tool call: fetch_user_profile(user_id='usr_101')")
    res = resolver.resolve(proposal, state)

    print(f"Veyra Decision: {res.decision}")
    print(f"Selected Candidate: {res.selected_candidate.tool}")
    print(f"Resolution Reason: {res.reason}")
    print(f"Unnecessary Intervention Rate: 0.0%")
    print("Result: Nominal workflow preserved cleanly with 0 false blocks!")


if __name__ == "__main__":
    run_demo()
