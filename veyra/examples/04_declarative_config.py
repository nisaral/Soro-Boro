"""Example 4: Declarative Tool Equivalence and Fallback Configuration.

Demonstrates configuring Veyra without code modifications using a YAML file:
1. Loads capabilities, equivalence groups, parameter aliases, and fallback chains from YAML.
2. Applies them directly to Veyra's ToolRegistry.
3. Automatically maps parameter aliases and executes declared fallback chains.
"""

import sys
from pathlib import Path

# Add python/src to sys.path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from veyra import ToolDefinition, ToolRegistry, Veyra, load_equivalence_config


def main():
    yaml_path = Path(__file__).parent / "04_declarative_config.yaml"
    print(f"Loading declarative configuration from: {yaml_path.name}")

    # 1. Load declarative configuration
    cfg = load_equivalence_config(yaml_path)
    print(f"Loaded {len(cfg.capabilities)} declared capabilities (version {cfg.version}):")
    for cap in cfg.capabilities:
        print(f"  - {cap.name}: tools={cap.tools}, fallbacks={cap.fallback_chains}")

    # 2. Build registry and apply config
    registry = ToolRegistry()
    cfg.apply_to_registry(registry)

    # 3. Register real tool executables
    def crm_primary(user_id: int):
        # Simulating endpoint failure
        raise TimeoutError("CRM API gateway timeout (HTTP 504)")

    def legacy_backup(user_id: int):
        return {"user_id": user_id, "username": "ada_lovelace", "source": "legacy_crm"}

    registry.register(ToolDefinition(name="crm_fetch_user", executable=crm_primary, idempotent=True))
    registry.register(ToolDefinition(name="legacy_get_customer", executable=legacy_backup, idempotent=True))

    # 4. Initialize Veyra boundary
    veyra = Veyra(registry=registry)

    # 5. Agent calls primary with aliased parameter 'account_id'
    print("\nAgent calls: crm_fetch_user(account_id='42')")
    result = veyra.call(
        tool_name="crm_fetch_user",
        arguments={"account_id": "42"},
        idempotent=True,
    )

    print("\nVeyra Resolved via Declarative Fallback Chain:")
    print(f"Result: {result}")

    last_trace = veyra.trace_sink.traces[-1]
    print(f"\nTrace Verification:")
    print(f"  Proposed:  {last_trace.tool_proposed}")
    print(f"  Resolved:  {last_trace.tool_resolved}")
    print(f"  Arguments: {last_trace.arguments_resolved}")
    print(f"  Outcome:   {last_trace.outcome}")


if __name__ == "__main__":
    main()
