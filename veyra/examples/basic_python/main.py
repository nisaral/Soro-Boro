"""Example 1: Basic Python Tool Wrapping with Veyra Drop-In Middleware.

Runnable from fresh checkout in <1 minute.
Demonstrates:
- Wrapping an existing Python function
- Enforcing ExecutionContract (read-only vs destructive)
- Inspecting the structured decision explanation and audit trail
"""

import sys
from pathlib import Path

# Ensure veyra is on path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.core.execution_contract import SideEffectClass
from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware


def delete_user_record(user_id: int):
    """Destructive action."""
    return {"status": "DELETED", "user_id": user_id}


def read_user_profile(user_id: int):
    """Read-only action."""
    return {"status": "OK", "user_id": user_id, "name": "Alice"}


def main():
    print("=== Veyra Drop-In Middleware: Basic Python Example ===\n")
    middleware = VeyraMiddleware(ProductionConfig(mode=Mode.NORMAL))

    # Wrap a safe read-only tool
    safe_reader = middleware.wrap_function(
        read_user_profile,
        name="read_user_profile",
        side_effect_class=SideEffectClass.READ_ONLY,
    )

    print("1. Calling read_user_profile(user_id=42)...")
    result = safe_reader(user_id=42)
    print(f"Result: {result}")

    # Inspect decision audit
    latest_decision = middleware.audit_trail[-1]["explanation"]
    print(f"Decision: {latest_decision['decision']}")
    print(f"Selected Tool: {latest_decision['selected_tool']}")
    print(f"Checks passed: {latest_decision['checks']}\n")

    print("=== Example Completed Successfully ===")


if __name__ == "__main__":
    main()
