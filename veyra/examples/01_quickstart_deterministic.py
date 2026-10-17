"""Example 1: Quickstart Deterministic Resolution.

Demonstrates Veyra's core capability:
Agent proposes -> Veyra resolves -> Tool executes.

When the agent proposes an action with:
1. An aliased parameter name (e.g., 'uid' instead of 'customer_id')
2. A type mismatch (string "1002" instead of integer 1002)
3. A failed primary tool that cascades to a declared equivalent replica

Veyra resolves the call transparently with zero agent replanning and zero LLM calls.
"""

import sys
from pathlib import Path

# Add python/src to sys.path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from veyra import ToolDefinition, ToolRegistry, Veyra


def main():
    registry = ToolRegistry()

    # 1. Define and register tool implementations
    def primary_customer_service(customer_id: int):
        # Simulating primary service outage (e.g. 503 Service Unavailable)
        raise ConnectionError("Primary CRM endpoint timeout (HTTP 503)")

    def backup_customer_service(customer_id: int):
        # Healthy equivalent fallback replica
        return {
            "customer_id": customer_id,
            "name": "Jane Doe",
            "tier": "enterprise",
            "status": "active",
        }

    # Register both tools in the registry
    registry.register(
        ToolDefinition(
            name="primary_customer_service",
            executable=primary_customer_service,
            idempotent=True,
            retryable=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="backup_customer_service",
            executable=backup_customer_service,
            idempotent=True,
            retryable=True,
        )
    )

    # 2. Declare equivalence, parameter aliases, and fallback chain
    registry.register_equivalence(
        canonical_name="primary_customer_service",
        equivalent_names=["backup_customer_service"],
    )
    # Map agent's alias 'uid' to canonical 'customer_id' for both tools
    registry.register_parameter_aliases(
        "primary_customer_service",
        {"uid": "customer_id"},
    )
    registry.register_parameter_aliases(
        "backup_customer_service",
        {"uid": "customer_id"},
    )
    # Declare primary -> backup fallback chain
    registry.register_fallback_chain(
        "primary_customer_service",
        ["backup_customer_service"],
    )

    # 3. Initialize Veyra boundary middleware
    veyra = Veyra(registry=registry)

    # 4. Agent proposes call to primary with parameter alias 'uid': "1002"
    print("Agent proposes: primary_customer_service(uid='1002')")
    result = veyra.call(
        tool_name="primary_customer_service",
        arguments={"uid": "1002"},
        idempotent=True,
    )

    print("\nVeyra Resolved & Executed Successfully!")
    print(f"Result: {result}")

    # Inspect execution trace
    traces = veyra.trace_sink.traces
    if traces:
        last_trace = traces[-1]
        print(f"\nTrace Details:")
        print(f"  Proposed Tool:   {last_trace.tool_proposed}")
        print(f"  Resolved Tool:   {last_trace.tool_resolved}")
        print(f"  Outcome:         {last_trace.outcome}")
        print(f"  Latency:         {last_trace.latency_ms:.2f} ms")
        print(f"  Agent Replans:   0 (Continuity preserved!)")


if __name__ == "__main__":
    main()
