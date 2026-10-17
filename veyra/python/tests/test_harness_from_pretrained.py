"""Local checkpoint load through SoroHarness.from_pretrained."""
from pathlib import Path

import pytest

from soro.harness.pipeline import SoroHarness

CKPT = Path(__file__).resolve().parents[2] / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b"


@pytest.mark.skipif(not (CKPT / "head.pt").exists(), reason="0.8B checkpoint is not in runs/")
def test_from_pretrained_local_checkpoint_routes():
    harness = SoroHarness.from_pretrained(str(CKPT), device="auto")
    harness.register_action(
        "get_order_status",
        "Check whether a customer order has shipped",
        {"order_id": str},
        lambda **kwargs: kwargs,
        side_effect="read_only",
    )
    harness.register_action(
        "issue_order_refund",
        "Issue a monetary refund for a customer order",
        {"order_id": str, "amount": float},
        lambda **kwargs: kwargs,
        side_effect="mutation",
    )
    route = harness.route("look up order ORD-100", top_k=4)
    assert route.selected_tool in {"get_order_status", "issue_order_refund", None}
    assert route.action in {"EXECUTE", "ASK", "ABSTAIN"}
