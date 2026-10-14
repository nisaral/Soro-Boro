"""Tests for Soro Unified Harness Pipeline: Route -> Repair -> Guard."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from soro import SoroHarness
from soro.routing.kev_local import LocalKevScorer


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

        # 1. Test ROUTING (Conformal 2-stage)
        best_tools = harness.route("I need to refund order 992")
        assert len(best_tools) > 0
        assert best_tools[0] == "refund_order"
        assert best_tools.action == "EXECUTE"
        assert best_tools.selected_tool == "refund_order"

        user_tools = harness.route("Find user profile")
        assert len(user_tools) > 0
        assert user_tools[0] == "get_user"
        assert user_tools.action == "EXECUTE"

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


def test_semantic_argument_mapping():
    """Verify semantic misnomers are mapped to schema properties."""
    harness = SoroHarness()

    @harness.tool(description="Refund customer order")
    def refund_order(order_id: str, amount: float, reason: str = "customer_request"):
        return {"order_id": order_id, "amount": amount, "reason": reason}

    # LLM passed semantic synonyms instead of schema names:
    # customer_order_identifier -> order_id
    # refund_value -> amount
    # explanation -> reason
    misnamed_args = {
        "customer_order_identifier": "TX-8841",
        "refund_value": "99.50",
        "explanation": "Defective item",
    }
    repaired = harness.repair("refund_order", misnamed_args)
    assert repaired["order_id"] == "TX-8841"
    assert repaired["amount"] == 99.50
    assert repaired["reason"] == "Defective item"


def test_conformal_route_actions():
    """Verify EXECUTE, ASK, and ABSTAIN decisions under conformal routing."""
    harness = SoroHarness(default_alpha=0.10)

    @harness.tool(description="Query billing invoices and statements")
    def get_invoice(invoice_id: str):
        return {}

    @harness.tool(description="Search user account and billing profile")
    def get_billing_account(user_id: str):
        return {}

    # Clear single intent -> EXECUTE
    res_exec = harness.route("Download my billing invoice statement")
    assert res_exec.action in ("EXECUTE", "ASK")
    assert "get_invoice" in res_exec.candidates

    # Unrelated query -> ABSTAIN
    res_abstain = harness.route("bake a chocolate strawberry birthday cake in the oven")
    assert res_abstain.action == "ABSTAIN"


def test_local_kev_multi_question_evaluation():
    """Verify LocalKevScorer multi-question single forward pass evaluation."""
    scorer = LocalKevScorer()

    query = "delete customer order record 501"
    questions = {
        "tool_route": {
            "type": "choice",
            "criteria": {
                "delete_order": "Delete a customer order by ID",
                "view_order": "View an order by ID",
                "__abstain__": "Abstain",
            },
        },
        "is_mutation": {
            "type": "noul",
        },
        "arg_mapping": {
            "type": "choice",
            "criteria": {
                "order_id": "The target order ID",
                "customer_name": "The customer's name",
            },
        },
    }

    turn_res = scorer.evaluate_turn(query, questions)
    probs = turn_res["probabilities"]
    answers = turn_res["answers"]

    assert "tool_route" in probs
    assert answers["tool_route"] == "delete_order"
    assert answers["is_mutation"] == "yes"
    assert probs["is_mutation"]["yes"] > 0.90


def test_polymorphic_registration_rest_and_skills():
    """Verify SoroHarness seamlessly registers REST endpoints and Agent Skills."""
    harness = SoroHarness()

    # 1. Register REST endpoint
    harness.register_rest(
        endpoint="/v1/payments/refund",
        method="POST",
        description="Issue a full or partial refund for a transaction",
        parameters={"payment_id": {"type": str}, "amount": {"type": float}},
    )

    # 2. Register Agent Skill
    harness.register_skill(
        skill_name="deploy_staging",
        description="Deploys container image to staging cluster",
        triggers=["deploy staging", "release staging"],
        command_format="/deploy --env staging --image <tag>",
        parameters={"image_tag": {"type": str}},
    )

    # 3. Register raw OpenAPI/MCP dictionary
    harness.register({
        "name": "lookup_customer",
        "description": "Fetch customer profile by email address",
        "parameters": {"email": {"type": str}},
        "side_effect": "read_only",
    })

    assert len(harness.tools) == 3

    # Route to REST tool
    res_rest = harness.route("Please refund transaction txn_409")
    assert "POST_v1_payments_refund" in res_rest.candidates

    # Route to Skill
    res_skill = harness.route("Deploy image v2.4 to staging cluster")
    assert "deploy_staging" in res_skill.candidates

    # Execute REST action with argument repair
    exec_res = harness.execute("POST_v1_payments_refund", {"payment_id": "txn_409", "amount": "85.20"})
    assert exec_res.status == "COMMITTED"
    assert exec_res.data["parameters"]["amount"] == 85.20

