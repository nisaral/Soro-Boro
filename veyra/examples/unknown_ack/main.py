"""Example 4: Unknown-State Safety (Section 5 & 22 Killer Demo).

Runnable from fresh checkout.
Demonstrates:
- Tool times out after mutation committed (UNKNOWN_ACK).
- Naive agent replays, causing duplicate external mutation (e.g. double financial transfer).
- Veyra intercepts UNKNOWN_ACK, invokes verification oracle, discovers commit, and prevents duplicate write!
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.production.production_layer import VeyraMiddleware


class DatabaseEnv:
    def __init__(self):
        self.ledger = []

    def commit_transfer(self, transfer_id: str, amount: float):
        self.ledger.append({"id": transfer_id, "amount": amount})
        # Network fails after commit
        raise TimeoutError("Socket timeout: ACK lost in flight")

    def verify_transfer_status(self, transfer_id: str, **kwargs):
        committed = any(item["id"] == transfer_id for item in self.ledger)
        return {"committed": committed, "transfer_id": transfer_id}


def run_killer_demo():
    print("=====================================================================")
    print(" KILLER PRODUCT DEMO: UNKNOWN-STATE SAFETY (UNKNOWN_ACK)")
    print("=====================================================================\n")

    db = DatabaseEnv()
    middleware = VeyraMiddleware()

    transfer_id = "tx_corp_999"
    amount = 50_000.00

    print(f"Scenario: Transferring ${amount:,.2f} with transaction ID '{transfer_id}'")
    print("Step 1: Agent dispatches non-idempotent mutation to banking tool...")

    try:
        db.commit_transfer(transfer_id, amount)
    except TimeoutError as err:
        print(f"  --> NETWORK TIMEOUT DETECTED: '{err}'")
        print(f"  --> Real ledger state: {len(db.ledger)} write committed to database.")

    print("\n--- NAIVE RETRY BEHAVIOR ---")
    print("Standard retry / naive agent retries the call...")
    db.ledger.append({"id": transfer_id, "amount": amount})  # Simulating blind replay
    print(f"Result: DUPLICATE MUTATION! Ledger has {len(db.ledger)} entries totaling ${sum(x['amount'] for x in db.ledger):,.2f}!")

    # Reset ledger for Veyra demonstration
    db.ledger = [{"id": transfer_id, "amount": amount}]
    print("\n--- VEYRA SAFETY MIDDLEWARE BEHAVIOR ---")
    print("Veyra detects UNKNOWN_ACK on non-idempotent mutation.")
    print("Veyra Invariant: Blind replay strictly prohibited. Invoking VERIFY strategy...")

    res = middleware.handle_unknown_ack(
        tool_name="commit_transfer",
        arguments={"transfer_id": transfer_id, "amount": amount},
        verification_fn=db.verify_transfer_status,
        is_idempotent=False,
    )

    print(f"\nVeyra Execution Receipt:")
    print(f"  Status: {res['status']}")
    print(f"  Replayed: {res['replayed']}")
    print(f"  Verified Result: {res['verified_result']}")
    print(f"  Final Database Ledger Entries: {len(db.ledger)} (ZERO duplicate mutations!)")
    print("\n=====================================================================")
    print(" Killer Demo Finished: State-conditional verification preserved safety!")
    print("=====================================================================\n")


if __name__ == "__main__":
    run_killer_demo()
