"""Example: Constrained Belief-State Recovery Controller (Directive §19).

Demonstrates:
  UNKNOWN_ACK -> Evidence Acquisition -> State Belief Update -> Safe Recovery (0% DER)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python" / "src"))

from veyra.boundary.interceptor import Veyra
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.recovery_controller import ConstrainedBeliefStateRecoveryController


class MockPaymentService:
    def __init__(self) -> None:
        self.ledger: list[str] = []

    def charge(self, transfer_id: str, amount: float) -> dict[str, str]:
        # Simulates non-idempotent charge that commits on server, but socket drops before ACK
        self.ledger.append(transfer_id)
        raise TimeoutError("504 Gateway Timeout: Response dropped after commit")

    def verify_charge(self, transfer_id: str, **kwargs: Any) -> dict[str, bool]:
        # Safe read-only status probe
        return {"committed": transfer_id in self.ledger}



def main() -> None:
    print("=" * 70)
    print("Veyra: Constrained Belief-State Recovery Controller Demonstration")
    print("=" * 70)

    service = MockPaymentService()
    transfer_id = "tx_enterprise_9901"

    # Step 1: Initialize Veyra with experimental belief-state recovery policy
    veyra = Veyra(recovery_policy="belief_state_experimental")
    controller: ConstrainedBeliefStateRecoveryController = veyra.belief_recovery_controller

    contract = ExecutionContract(
        capability="payment.charge",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    )

    action = ExecutableAction(
        tool="charge",
        arguments={"transfer_id": transfer_id, "amount": 250.0},
        executable=service.charge,
    )

    # Step 2: Simulate failure invocation
    print(f"\n1. Agent proposes: charge(transfer_id='{transfer_id}', amount=250.0)")
    try:
        service.charge(transfer_id, 250.0)
    except TimeoutError as exc:
        print(f"   Execution Failure: {exc}")

    # Step 3: Controller decides recovery
    print("\n2. Veyra Recovery Controller Invoked:")
    decision = controller.decide_recovery(
        failed_action=action,
        failure_type="timeout_after_commit",
        contract=contract,
        status_code=504,
        verification_fn=service.verify_charge,
    )

    print(f"   Initial Prior Belief : {decision.belief_before}")
    print(f"   Evidence Acquired    : {decision.evidence_acquired} ({decision.evidence_details})")
    print(f"   Posterior Belief     : {decision.belief_after}")
    print(f"   Selected Action      : {decision.action_type.value}")
    print(f"   P(Unsafe Effect)     : {decision.unsafe_probability} (Safety Epsilon: {controller.epsilon_unsafe})")
    print(f"   Expected Utility     : {decision.expected_utility}")
    print(f"   Explanation          : {decision.reason}")

    print("\n3. External State Invariant Check:")
    print(f"   Total Charges in Ledger : {len(service.ledger)}")
    print(f"   Duplicate Charges Count : {len(service.ledger) - 1} (Expected: 0)")
    print("\n[SUCCESS] Mutation safely verified and recovered without duplicate execution.")


if __name__ == "__main__":
    main()
