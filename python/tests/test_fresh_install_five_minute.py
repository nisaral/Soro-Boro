"""Fresh-install 5-minute path: wrap a payment tool, UNKNOWN_ACK, VERIFY, no duplicate."""

from __future__ import annotations

from soro import SideEffectClass, Soro


class _Ledger:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def charge(self, transfer_id: str, amount: float) -> dict:
        self.entries.append({"id": transfer_id, "amount": amount})
        raise TimeoutError("ACK lost after commit")

    def verify_charge(self, transfer_id: str, amount: float | None = None, **kwargs) -> dict:
        committed = any(item["id"] == transfer_id for item in self.entries)
        return {"committed": committed, "transfer_id": transfer_id}


def test_five_minute_wrap_unknown_ack_verify():
    ledger = _Ledger()
    mw = Soro()
    charge = mw.wrap(
        ledger.charge,
        name="charge",
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
        verify=ledger.verify_charge,
    )
    result = charge(transfer_id="tx_5min", amount=42.0)
    assert result["status"] == "VERIFIED_COMMITTED"
    assert result["replayed"] is False
    assert ledger.entries == [{"id": "tx_5min", "amount": 42.0}]
    assert "VERIFIED" in result["status"]
