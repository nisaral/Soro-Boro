"""Non-idempotent payment tool for UNKNOWN_ACK lab runs."""

from __future__ import annotations


class PaymentLedger:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def charge(self, transfer_id: str, amount: float) -> dict:
        self.entries.append({"id": transfer_id, "amount": amount})
        raise TimeoutError("ACK lost after commit")

    def verify_charge(self, transfer_id: str, amount: float | None = None, **kwargs) -> dict:
        committed = any(item["id"] == transfer_id for item in self.entries)
        return {"committed": committed, "transfer_id": transfer_id, "count": len(self.entries)}
