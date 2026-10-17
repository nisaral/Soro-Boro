"""Example 3: Dynamic State Recovery and Candidate Fallback.

Runnable from fresh checkout.
Demonstrates:
- Automatic fallback from degraded primary tool to healthy replica
- Circuit breaker trip protection
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.core.action import ExecutableAction
from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware


def primary_failing_endpoint(**kwargs):
    raise ConnectionResetError("Primary service degraded")


def backup_healthy_replica(**kwargs):
    return {"status": "SUCCESS", "source": "backup_replica", "data": "recovered_payload"}


def main():
    print("=== Veyra Drop-In Middleware: Recovery Example ===\n")

    middleware = VeyraMiddleware()

    # Declare candidate fallback action
    fallback_candidate = ExecutableAction(
        tool="backup_healthy_replica",
        arguments={},
        executable=backup_healthy_replica,
        metadata={"capability": "data_fetch", "side_effect_class": "read_only", "idempotent": True},
    )

    # Trip the circuit breaker on primary to simulate real-world failure
    cb = middleware.get_circuit_breaker("primary_failing_endpoint")
    for _ in range(5):
        cb.record_failure()
    print(f"Primary endpoint circuit breaker state: {cb.state} (Tripped)")

    # Wrap the function with declared fallback candidate
    fetch_tool = middleware.wrap_function(
        primary_failing_endpoint,
        name="primary_failing_endpoint",
        capability="data_fetch",
        fallback_candidates=[fallback_candidate],
    )

    print("Executing tool through Veyra boundary...")
    result = fetch_tool()
    print(f"Result returned to agent: {result}")

    explanation = middleware.audit_trail[-1]["explanation"]
    print("\nVeyra Resolution Explanation:")
    print(f"  Decision: {explanation['decision']}")
    print(f"  Selected: {explanation['selected_tool']}")
    print(f"  Rejected: {explanation['rejected_candidates']}")
    print("\n=== Recovery Example Completed Successfully ===")


if __name__ == "__main__":
    main()
