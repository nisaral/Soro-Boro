"""Six harness stress tests for the 0.8B and 4B checkpoints on the local GPU."""
from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from soro.harness.pipeline import SoroHarness  # noqa: E402
from soro.routing.kev_local import LocalKevScorer  # noqa: E402

CKPTS = {
    "0.8b": ROOT / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b",
    "4b": ROOT / "runs" / "soro_kev_qwen3_4b_best",
}


def harness_for(scorer, tag: str) -> SoroHarness:
    return SoroHarness(
        scorer=scorer,
        dedupe_mode="loop_guard",
        window_sec=120.0,
        claims_db_path=str(ROOT / "runs" / f"claims_hard_{tag}.db"),
        wal_path=str(ROOT / "runs" / f"wal_hard_{tag}.jsonl"),
    )


def reg(harness: SoroHarness, name, desc, params, fn, side="mutation"):
    harness.register_action(name, desc, params, fn, side_effect=side)


def order_chain(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_chain")

    def get_order_status(order_id: str):
        return {
            "order_id": order_id,
            "customer_email": "alice@acme.com",
            "shipment_id": "SHP-901",
            "status": "processing",
        }

    def cancel_shipment(shipment_id: str):
        return {"shipment_id": shipment_id, "cancelled": True}

    def issue_order_refund(order_id: str, amount: float):
        return {"order_id": order_id, "amount": amount}

    def send_confirmation_email(to_email: str):
        return {"to_email": to_email, "sent": True}

    reg(harness, "get_order_status", "Look up a customer order and its shipment", {"order_id": str}, get_order_status, "read_only")
    reg(harness, "cancel_shipment", "Cancel a pending warehouse shipment", {"shipment_id": str}, cancel_shipment)
    reg(harness, "issue_order_refund", "Issue a monetary refund to the customer", {"order_id": str, "amount": float}, issue_order_refund)
    reg(harness, "send_confirmation_email", "Send a confirmation email to the customer", {"to_email": str}, send_confirmation_email)
    trace = harness.run_workflow(
        "Look up order ORD-774, cancel its pending warehouse shipment, issue a $129.00 refund to the customer, and send a confirmation email."
    )
    by_tool = {step.get("tool"): step for step in trace if step.get("tool")}
    cancel = (by_tool.get("cancel_shipment") or {}).get("data") or {}
    email = (by_tool.get("send_confirmation_email") or {}).get("data") or {}
    ok = cancel.get("shipment_id") == "SHP-901" and email.get("to_email") == "alice@acme.com"
    print("chain", ok, {name: step.get("data") for name, step in by_tool.items()}, flush=True)
    return {"ok": ok, "trace": trace}


def ambiguity(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_ask")
    reg(harness, "jira_create_issue", "Open an engineering ticket in Jira", {"title": str}, lambda **k: k)
    reg(harness, "linear_create_issue", "Open an engineering ticket in Linear", {"title": str}, lambda **k: k)
    reg(harness, "query_weather_forecast", "Query the weather forecast for a city", {"city": str}, lambda **k: k, "read_only")
    trace = harness.run_workflow("Open a bug ticket titled Login button misaligned")
    head = trace[0] if trace else {}
    candidates = set(head.get("candidates") or [])
    ok = head.get("status") == "ASK" and {"jira_create_issue", "linear_create_issue"} <= candidates
    print("ambiguity", ok, head.get("status"), head.get("candidates"), flush=True)
    return {"ok": ok, "trace": trace}


def severity(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_sev")
    reg(harness, "create_incident", "Open a sev1 incident ticket with a title and severity", {"title": str, "severity": str}, lambda **k: k)
    reg(harness, "jira_create_issue", "Open an engineering ticket in Jira", {"title": str}, lambda **k: k)
    trace = harness.run_workflow("Open a sev1 incident titled DB down")
    tools = [step.get("tool") for step in trace if step.get("tool")]
    ok = tools == ["create_incident"] or (tools and tools[0] == "create_incident" and "jira_create_issue" not in tools)
    print("severity", ok, tools, trace[0].get("data") if trace else None, flush=True)
    return {"ok": ok, "trace": trace}


def missing_amount(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_miss")

    def get_order_status(order_id: str):
        return {"order_id": order_id, "status": "processing"}

    def issue_order_refund(order_id: str, amount: float):
        return {"order_id": order_id, "amount": amount, "wrote": True}

    reg(harness, "get_order_status", "Look up a customer order", {"order_id": str}, get_order_status, "read_only")
    reg(harness, "issue_order_refund", "Issue a monetary refund to the customer", {"order_id": str, "amount": float}, issue_order_refund)
    trace = harness.run_workflow("Look up order ORD-774, then issue a refund to the customer.")
    ran = [step.get("tool") for step in trace if step.get("status") == "COMMITTED"]
    halt = next((step for step in trace if step.get("status") == "ASK"), {})
    missing = halt.get("missing") or halt.get("missing_required_fields") or []
    wrote = any(isinstance(step.get("data"), dict) and step["data"].get("wrote") for step in trace)
    ok = "get_order_status" in ran and "amount" in missing and not wrote
    print("missing", ok, ran, missing, flush=True)
    return {"ok": ok, "trace": trace}


def negation(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_neg")
    reg(harness, "get_order_status", "Check the current delivery status of a customer order", {"order_id": str}, lambda **k: {"order_id": k.get("order_id"), "status": "shipped"}, "read_only")
    reg(harness, "cancel_shipment", "Cancel a pending warehouse shipment", {"shipment_id": str}, lambda **k: {"cancelled": True})
    reg(harness, "issue_order_refund", "Issue a monetary refund", {"order_id": str, "amount": float}, lambda **k: {"refunded": True})
    trace = harness.run_workflow("Do NOT cancel or refund order ORD-774, just check its current delivery status")
    tools = [step.get("tool") for step in trace if step.get("status") == "COMMITTED"]
    ok = tools == ["get_order_status"]
    print("negation", ok, tools, flush=True)
    return {"ok": ok, "trace": trace}


def haystack(tag: str, scorer) -> dict:
    harness = harness_for(scorer, tag + "_hay")
    catalog = [
        ("query_weather_forecast", "Query the weather forecast for a city", "read_only"),
        ("issue_order_refund", "Issue a monetary refund for a customer order", "mutation"),
        ("get_order_status", "Check whether a customer order has shipped", "read_only"),
        ("mcp_filesystem_read", "Read a local log file from the filesystem", "read_only"),
        ("rollback_deployment", "Roll back a staging deployment to a target version", "mutation"),
        ("create_incident", "Open an incident ticket with a title and severity", "mutation"),
        ("slack_send_message", "Post an alert to the engineering Slack channel", "mutation"),
        ("send_confirmation_email", "Send a confirmation email", "mutation"),
        ("github_create_issue", "Open an engineering ticket in GitHub", "mutation"),
        ("jira_create_issue", "Open an engineering ticket in Jira", "mutation"),
        ("linear_create_issue", "Open an engineering ticket in Linear", "mutation"),
        ("get_invoice", "Fetch an invoice pdf by invoice id", "read_only"),
        ("delete_file", "Delete a file from the filesystem", "destructive"),
        ("deploy_service", "Deploy a service version to production", "mutation"),
        ("reset_password", "Reset a user password", "mutation"),
        ("query_metrics", "Query CPU metrics for a hostname", "read_only"),
        ("list_incidents", "List open incident tickets", "read_only"),
        ("translate_text", "Translate a sentence into another language", "read_only"),
        ("search_docs", "Search internal documentation", "read_only"),
        ("create_calendar_event", "Create a meeting on the calendar", "mutation"),
        ("get_stock_price", "Look up a stock ticker price", "read_only"),
        ("page_oncall", "Page the on-call engineer", "mutation"),
        ("update_address", "Change the shipping address on an account", "mutation"),
        ("get_user_profile", "Fetch a user profile by account id", "read_only"),
        ("write_file", "Write text into a file", "mutation"),
    ]
    assert len(catalog) == 25
    for name, desc, side in catalog:
        reg(harness, name, desc, {"value": {"type": str, "default": ""}}, lambda **k: k, side)
    golds = {
        "what is the weather in berlin": "query_weather_forecast",
        "refund this customer's payment": "issue_order_refund",
        "read the deploy log file": "mcp_filesystem_read",
        "list the open incident tickets": "list_incidents",
    }
    hits = 0
    for query, gold in golds.items():
        trace = harness.run_workflow(query)
        tools = [step.get("tool") for step in trace if step.get("status") == "COMMITTED"]
        ok = bool(tools) and tools[0] == gold
        hits += int(ok)
        print(f"hay {ok} gold={gold} got={tools[:3]}", flush=True)
    abstain_trace = harness.run_workflow("how do I bake a chocolate souffle")
    abstain_tools = [step.get("tool") for step in abstain_trace if step.get("status") == "COMMITTED"]
    abstain_ok = not abstain_tools
    print("hay abstain", abstain_ok, abstain_tools, flush=True)
    return {"ok": hits == len(golds) and abstain_ok, "hits": hits, "n": len(golds)}


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit(f"CUDA is not available. torch={torch.__version__}")
    print("device", torch.cuda.get_device_name(0), flush=True)
    summary = []
    for name, path in CKPTS.items():
        print(f"\n##### {name} #####", flush=True)
        scorer = LocalKevScorer(run=str(path), backend="neural", device="cuda")
        if not scorer.load():
            print("load failed", scorer.error, flush=True)
            continue
        results = {
            "chain": order_chain(name, scorer),
            "ambiguity": ambiguity(name, scorer),
            "severity": severity(name, scorer),
            "missing": missing_amount(name, scorer),
            "negation": negation(name, scorer),
            "haystack": haystack(name, scorer),
        }
        summary.append((name, {key: value["ok"] for key, value in results.items()}))
        del scorer
        torch.cuda.empty_cache()
    print("SUMMARY", summary, flush=True)


if __name__ == "__main__":
    main()
