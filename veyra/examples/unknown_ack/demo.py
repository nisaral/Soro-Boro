r"""Veyra Working Example: UNKNOWN_ACK & Zero Blind Replay (Section 29).

Demonstrates:
- Naive Retry -> Duplicate side effect (2 credit card charges!)
- Veyra -> UNKNOWN_ACK -> VERIFY / IDEMPOTENCY -> ZERO unsafe replay (1 charge!)

Run from fresh checkout:
python examples/unknown_ack/demo.py
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


class StatefulPaymentBackend:
    """Mock stateful payment service."""

    def __init__(self):
        self.charges: list[dict] = []

    def charge_card(self, customer_id: str, amount: float) -> dict:
        record = {"customer_id": customer_id, "amount": amount}
        self.charges.append(record)
        return {"status": "PAID", "charge_id": f"chg_{len(self.charges)}"}

    def verify_charge(self, customer_id: str) -> bool:
        return any(c["customer_id"] == customer_id for c in self.charges)


def run_demo():
    print("=" * 60)
    print("VEYRA DEMO: UNKNOWN_ACK & ZERO BLIND REPLAY")
    print("=" * 60)

    # 1. NAIVE RETRY DEMONSTRATION
    print("\n--- 1. NAIVE RETRY (NO VEYRA) ---")
    backend_naive = StatefulPaymentBackend()
    
    # Mutation succeeds on backend
    backend_naive.charge_card("cust_42", 100.0)
    print("1st Call: Mutation committed on backend (Charge #1 created).")
    print("Network fault injected: Response ACK lost / Timeout!")

    # Naive retry blindly replays
    print("Naive Retry Action: Replaying charge_card(...)")
    backend_naive.charge_card("cust_42", 100.0)
    print(f"Result: DUPLICATE WRITES CREATED! Total charges on backend: {len(backend_naive.charges)}")

    # 2. VEYRA INTERCEPTED DEMONSTRATION
    print("\n--- 2. VEYRA INTERCEPTED ---")
    backend_veyra = StatefulPaymentBackend()
    backend_veyra.charge_card("cust_42", 100.0)
    print("1st Call: Mutation committed on backend (Charge #1 created).")
    print("Network fault injected: Response ACK lost / Timeout!")

    reg = ToolRegistry()
    reg.register(ToolDefinition(name="charge_card", idempotent=False, side_effect_class="non_idempotent_mutation"))
    resolver = VeyraResolver(reg)

    state = ExecutionState(agent="payment_agent", context={"tx_state": "unknown_ack"})
    proposal = ExecutableAction(tool="charge_card", arguments={"customer_id": "cust_42", "amount": 100.0}, metadata={"side_effect_class": "non_idempotent_mutation", "is_idempotent": False})

    print("Veyra Interception: Evaluating execution contract under UNKNOWN_ACK...")
    res = resolver.resolve(proposal, state)

    if res.decision == "deny" or res.selected_candidate is None:
        print(f"Veyra Decision: DENY ({res.reason})")
        print("Veyra Safety Invariant: UNKNOWN_ACK + non-idempotent mutation = NO BLIND REPLAY")
        print("Executing verification probe instead...")
        is_verified = backend_veyra.verify_charge("cust_42")
        print(f"Verification Probe Result: Charge verified = {is_verified}")
        print(f"Final Backend State: ZERO DUPLICATE WRITES! Total charges on backend: {len(backend_veyra.charges)}")


if __name__ == "__main__":
    run_demo()
