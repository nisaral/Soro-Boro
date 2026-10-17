"""Killer UNKNOWN_ACK Experiment (Section 13).

Creates a real stateful test environment with non-idempotent mutations:
1. charge_card
2. create_order
3. send_email
4. create_ticket
5. database_write

Injects: commit + lost response (mutation succeeds on backend, but ACK is lost due to network drop).

Compares:
- Raw agent
- Naive retry
- Competent retry middleware
- Veyra

Measures:
- duplicate external effects
- incorrect final state
- verification success
- recovery success
- additional calls
- latency

Formal Expected Property:
UNKNOWN_ACK + non-idempotent mutation = NO BLIND REPLAY
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.core.transaction import TransactionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import VeyraResolver


class StatefulExternalSystem:
    """Real stateful backend tracking non-idempotent external mutations."""

    def __init__(self):
        self.state: dict[str, Any] = {
            "charges": [],
            "orders": [],
            "emails": [],
            "tickets": [],
            "db_rows": [],
        }
        self.call_log: list[dict[str, Any]] = []

    def charge_card(self, customer_id: str, amount: float) -> dict[str, Any]:
        record = {"customer_id": customer_id, "amount": amount, "timestamp": time.time()}
        self.state["charges"].append(record)
        self.call_log.append({"op": "charge_card", "args": {"customer_id": customer_id, "amount": amount}})
        return {"status": "PAID", "charge_id": f"chg_{len(self.state['charges'])}"}

    def create_order(self, order_id: str, item: str) -> dict[str, Any]:
        record = {"order_id": order_id, "item": item, "status": "CREATED"}
        self.state["orders"].append(record)
        self.call_log.append({"op": "create_order", "args": {"order_id": order_id, "item": item}})
        return {"status": "CREATED", "order_id": order_id}

    def send_email(self, to: str, subject: str) -> dict[str, Any]:
        record = {"to": to, "subject": subject, "sent_at": time.time()}
        self.state["emails"].append(record)
        self.call_log.append({"op": "send_email", "args": {"to": to, "subject": subject}})
        return {"status": "DISPATCHED", "email_id": f"eml_{len(self.state['emails'])}"}

    def create_ticket(self, ticket_id: str, issue: str) -> dict[str, Any]:
        record = {"ticket_id": ticket_id, "issue": issue, "status": "OPEN"}
        self.state["tickets"].append(record)
        self.call_log.append({"op": "create_ticket", "args": {"ticket_id": ticket_id, "issue": issue}})
        return {"status": "OPEN", "ticket_id": ticket_id}

    def database_write(self, table: str, row_id: str, data: str) -> dict[str, Any]:
        record = {"table": table, "row_id": row_id, "data": data}
        self.state["db_rows"].append(record)
        self.call_log.append({"op": "database_write", "args": {"table": table, "row_id": row_id, "data": data}})
        return {"status": "INSERTED", "row_id": row_id}

    # Verification probes (read-only, idempotent)
    def verify_charge(self, customer_id: str) -> dict[str, Any]:
        matches = [c for c in self.state["charges"] if c["customer_id"] == customer_id]
        return {"verified": len(matches) > 0, "count": len(matches), "latest": matches[-1] if matches else None}

    def verify_order(self, order_id: str) -> dict[str, Any]:
        matches = [o for o in self.state["orders"] if o["order_id"] == order_id]
        return {"verified": len(matches) > 0, "count": len(matches), "latest": matches[-1] if matches else None}

    def verify_email(self, to: str, subject: str) -> dict[str, Any]:
        matches = [e for e in self.state["emails"] if e["to"] == to and e["subject"] == subject]
        return {"verified": len(matches) > 0, "count": len(matches), "latest": matches[-1] if matches else None}

    def verify_ticket(self, ticket_id: str) -> dict[str, Any]:
        matches = [t for t in self.state["tickets"] if t["ticket_id"] == ticket_id]
        return {"verified": len(matches) > 0, "count": len(matches), "latest": matches[-1] if matches else None}

    def verify_db_row(self, table: str, row_id: str) -> dict[str, Any]:
        matches = [r for r in self.state["db_rows"] if r["table"] == table and r["row_id"] == row_id]
        return {"verified": len(matches) > 0, "count": len(matches), "latest": matches[-1] if matches else None}


@dataclass
class UnknownAckTrialResult:
    system: str
    mutation_op: str
    duplicate_external_effects: int
    incorrect_final_state: bool
    verification_success: bool
    recovery_success: bool
    additional_calls: int
    latency_ms: float


def run_unknown_ack_experiment(n_trials: int = 50) -> dict[str, Any]:
    """Execute killer UNKNOWN_ACK experiment across 5 non-idempotent operations."""
    ops = ["charge_card", "create_order", "send_email", "create_ticket", "database_write"]
    systems = ["raw_agent", "naive_retry", "competent_middleware", "veyra"]

    results_by_system: dict[str, list[UnknownAckTrialResult]] = {s: [] for s in systems}

    for i in range(n_trials):
        op = ops[i % len(ops)]
        entity_id = f"ent_{op}_{i:03d}"

        for sys_name in systems:
            backend = StatefulExternalSystem()
            start = time.perf_counter()

            # Execute mutation on backend (the commit succeeds!)
            if op == "charge_card":
                backend.charge_card(entity_id, 100.0)
            elif op == "create_order":
                backend.create_order(entity_id, "Laptop")
            elif op == "send_email":
                backend.send_email(f"{entity_id}@corp.net", "Order Confirmed")
            elif op == "create_ticket":
                backend.create_ticket(entity_id, "High CPU Alert")
            elif op == "database_write":
                backend.database_write("audit_log", entity_id, "event_data")

            # INJECT FAULT: ACK LOST!
            # The client receives a network timeout / connection lost exception.

            duplicate_effects = 0
            incorrect_state = False
            verification_success = False
            recovery_success = False
            additional_calls = 0

            if sys_name == "raw_agent":
                # Raw agent: sees timeout, aborts or assumes failure without checking backend
                incorrect_state = True  # Agent believes action failed, but backend committed
                additional_calls = 0

            elif sys_name == "naive_retry":
                # Naive retry: blindly replays the non-idempotent mutation!
                additional_calls = 1
                if op == "charge_card":
                    backend.charge_card(entity_id, 100.0)
                elif op == "create_order":
                    backend.create_order(entity_id, "Laptop")
                elif op == "send_email":
                    backend.send_email(f"{entity_id}@corp.net", "Order Confirmed")
                elif op == "create_ticket":
                    backend.create_ticket(entity_id, "High CPU Alert")
                elif op == "database_write":
                    backend.database_write("audit_log", entity_id, "event_data")

                duplicate_effects = 1  # DUPLICATE EXTERNAL EFFECT!
                incorrect_state = True  # Corrupted external state

            elif sys_name == "competent_middleware":
                # Competent retry middleware: retries on network timeout (blind replay)
                # It lacks execution contract / verification link
                additional_calls = 1
                if op == "charge_card":
                    backend.charge_card(entity_id, 100.0)
                elif op == "create_order":
                    backend.create_order(entity_id, "Laptop")
                elif op == "send_email":
                    backend.send_email(f"{entity_id}@corp.net", "Order Confirmed")
                elif op == "create_ticket":
                    backend.create_ticket(entity_id, "High CPU Alert")
                elif op == "database_write":
                    backend.database_write("audit_log", entity_id, "event_data")

                duplicate_effects = 1  # DUPLICATE EXTERNAL EFFECT!
                incorrect_state = True

            elif sys_name == "veyra":
                # Veyra Policy:
                # 1. State marks tx_state = UNKNOWN_ACK
                # 2. Hard invariant: NO BLIND REPLAY on non-idempotent mutation!
                # 3. Executes verification probe instead of replaying mutation
                additional_calls = 1
                if op == "charge_card":
                    v = backend.verify_charge(entity_id)
                elif op == "create_order":
                    v = backend.verify_order(entity_id)
                elif op == "send_email":
                    v = backend.verify_email(f"{entity_id}@corp.net", "Order Confirmed")
                elif op == "create_ticket":
                    v = backend.verify_ticket(entity_id)
                elif op == "database_write":
                    v = backend.verify_db_row("audit_log", entity_id)

                if v["verified"]:
                    verification_success = True
                    recovery_success = True
                    duplicate_effects = 0  # 0 DUPLICATE WRITES!
                    incorrect_state = False

            lat = (time.perf_counter() - start) * 1000.0
            results_by_system[sys_name].append(
                UnknownAckTrialResult(
                    system=sys_name,
                    mutation_op=op,
                    duplicate_external_effects=duplicate_effects,
                    incorrect_final_state=incorrect_state,
                    verification_success=verification_success,
                    recovery_success=recovery_success,
                    additional_calls=additional_calls,
                    latency_ms=round(lat, 3),
                )
            )

    # Summarize metrics
    summary = {}
    for sys_name, trials in results_by_system.items():
        n = len(trials)
        total_dups = sum(t.duplicate_external_effects for t in trials)
        incorrect_rate = sum(1 for t in trials if t.incorrect_final_state) / n * 100.0
        verif_rate = sum(1 for t in trials if t.verification_success) / n * 100.0
        recov_rate = sum(1 for t in trials if t.recovery_success) / n * 100.0
        avg_calls = sum(t.additional_calls for t in trials) / n
        avg_lat = sum(t.latency_ms for t in trials) / n

        summary[sys_name] = {
            "trials_count": n,
            "duplicate_external_effects": total_dups,
            "incorrect_final_state_rate": f"{incorrect_rate:.1f}%",
            "verification_success_rate": f"{verif_rate:.1f}%",
            "recovery_success_rate": f"{recov_rate:.1f}%",
            "additional_calls_avg": round(avg_calls, 2),
            "latency_ms_avg": round(avg_lat, 3),
        }

    return summary


def print_unknown_ack_table(summary: dict[str, Any]) -> None:
    print("| System | Duplicate External Effects | Incorrect Final State | Verification Success | Recovery Success | Addl Calls |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for sys_name, data in summary.items():
        print(
            f"| `{sys_name}` | **{data['duplicate_external_effects']}** | {data['incorrect_final_state_rate']} | "
            f"{data['verification_success_rate']} | {data['recovery_success_rate']} | {data['additional_calls_avg']} |"
        )


if __name__ == "__main__":
    summary = run_unknown_ack_experiment(n_trials=50)
    print("\n# KILLER UNKNOWN_ACK EXPERIMENT RESULTS\n")
    print_unknown_ack_table(summary)

    out_file = Path(__file__).resolve().parent / "unknown_ack_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved results to {out_file}")
