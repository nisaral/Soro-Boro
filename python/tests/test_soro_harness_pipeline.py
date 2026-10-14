"""Tests for Soro Unified Harness Pipeline: Route -> Repair -> Guard."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from soro import SoroHarness


def test_harness_route_repair_guard_pipeline():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        claims_path = str(Path(tmpdir) / "claims.db")
        wal_path = str(Path(tmpdir) / "wal.jsonl")

        harness = SoroHarness(
            dedupe_mode="loop_guard",
            window_sec=60.0,
            claims_db_path=claims_path,
            wal_path=wal_path,
        )

        refund_calls = 0

        @harness.tool(description="Refund customer order by order_id and amount", side_effect="mutation")
        def refund_order(order_id: str, amount: float, reason: str = "customer_request"):
            nonlocal refund_calls
            refund_calls += 1
            return {
                "status": "refunded",
                "order_id": order_id,
                "amount": amount,
                "reason": reason,
                "call_count": refund_calls,
            }

        @harness.tool(description="Look up user profile by user_id", side_effect="read_only")
        def get_user(user_id: int):
            return {"user_id": user_id, "name": "Alice"}

        # 1. Test ROUTING
        best_tools = harness.route("I need to refund order 992")
        assert len(best_tools) > 0
        assert best_tools[0] == "refund_order"

        user_tools = harness.route("Find user profile")
        assert len(user_tools) > 0
        assert user_tools[0] == "get_user"

        # 2. Test REPAIR (Argument Coercion & Normalization)
        # LLM passes string for float, camelCase key for snake_case
        raw_llm_args = {"orderId": "992", "amount": "49.99"}
        repaired = harness.repair("refund_order", raw_llm_args)
        assert repaired["order_id"] == "992"
        assert isinstance(repaired["amount"], float)
        assert repaired["amount"] == 49.99
        assert repaired["reason"] == "customer_request"

        # 3. Test GUARD (Loop Guard Execution)
        # First execution: succeeds and commits
        res1 = harness.execute("refund_order", raw_llm_args)
        assert res1.status == "COMMITTED"
        assert res1.data["call_count"] == 1
        assert refund_calls == 1

        # Second execution with exact same arguments within window:
        # Loop guard intercepts and returns PREVENTED_DUPLICATE without re-executing
        res2 = harness.execute("refund_order", raw_llm_args)
        assert res2.status == "PREVENTED_DUPLICATE"
        assert res2.data["call_count"] == 1
        assert refund_calls == 1  # Underlying tool was NOT re-dispatched!

        # 4. Test FULL PIPELINE: harness.run()
        # Chains Route -> Repair -> Guard
        pipeline_res = harness.run(
            query="Please issue refund for order 1005 with 15.50 dollars",
            arguments={"orderId": "1005", "amount": "15.50"},
        )
        assert pipeline_res.status == "COMMITTED"
        assert pipeline_res.data["order_id"] == "1005"
        assert pipeline_res.data["amount"] == 15.50
        assert refund_calls == 2
