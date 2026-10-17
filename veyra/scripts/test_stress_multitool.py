"""Stress the real 0.8B checkpoint on overlapping tools, a multi-step request, and a 30-tool haystack."""

from __future__ import annotations

import torch
from pathlib import Path

from soro.harness.pipeline import SoroHarness
from soro.routing.kev_local import LocalKevScorer

CKPT = Path(__file__).resolve().parents[1] / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b"


def show(title: str, route) -> None:
    probs = {k: round(v, 4) for k, v in (route.probabilities or {}).items() if v >= 0.01}
    print(f"\n=== {title} ===")
    print("action", route.action, "selected", route.selected_tool, "set", route.candidates, "size", len(route.candidates))
    print("probs>=0.01", probs)
    print("reason", route.reason)


def fresh(scorer) -> SoroHarness:
    return SoroHarness(scorer=scorer, dedupe_mode="loop_guard", window_sec=120.0)


def main() -> None:
    scorer = LocalKevScorer(run=str(CKPT), backend="neural", device="cpu")
    assert scorer.load()
    print("BACKBONE", type(scorer._neural_model.backbone).__name__)

    # A. Overlapping issue trackers plus Slack.
    harness = fresh(scorer)
    for name, desc in [
        ("github_create_issue", "Open an engineering ticket in the GitHub backlog for a bug or incident"),
        ("linear_create_issue", "Open an engineering ticket in the Linear backlog for a bug or incident"),
        ("jira_create_issue", "Open an engineering ticket in the Jira backlog for a bug or incident"),
        ("slack_send_message", "Send a notification message to a team chat channel"),
    ]:
        harness.register_action(name, desc, {"title": str, "body": str}, lambda **k: k, side_effect="mutation")

    prompt_a = "Hey team, we found a critical memory leak in the auth service. Open a ticket in our engineering backlog and notify the channel."
    route_a = harness.route(prompt_a, top_k=8)
    show("A overlapping names", route_a)
    allowed = {"github_create_issue", "linear_create_issue", "jira_create_issue", "slack_send_message"}
    print("set_is_subset_of_relevant", set(route_a.candidates).issubset(allowed))

    # B. Compound order request, one decision per turn.
    harness = fresh(scorer)
    status = {"ORD-992": "processing"}

    @harness.tool(description="Check whether a customer order has shipped", side_effect="read_only")
    def get_order_status(order_id: str):
        return {"order_id": order_id, "status": status[order_id]}

    @harness.tool(description="Cancel a customer order that has not shipped yet", side_effect="mutation")
    def cancel_order(order_id: str):
        status[order_id] = "cancelled"
        return {"order_id": order_id, "status": "cancelled"}

    @harness.tool(description="Issue a full monetary refund for a customer order", side_effect="mutation")
    def issue_order_refund(order_id: str, amount: float = 10.0):
        return {"order_id": order_id, "refunded": amount}

    @harness.tool(description="Query the weather forecast for a city", side_effect="read_only")
    def query_weather_forecast(city: str):
        return {"city": city}

    prompt_b = "First check the status of order ORD-992, and if it hasn't shipped yet, cancel it and issue a full refund."
    steps = []
    state = prompt_b
    for turn in range(3):
        route = harness.route(state, top_k=8)
        show(f"B turn {turn + 1}", route)
        tool = route.selected_tool
        steps.append((route.action, tool))
        if route.action == "ABSTAIN" or not tool:
            break
        if tool == "get_order_status":
            observed = harness.execute(tool, {"order_id": "ORD-992"})
            state = (
                f"{prompt_b}\nPrior tool observation: get_order_status returned {observed.data}. "
                "The order has not shipped. Do the next required action."
            )
        elif tool == "cancel_order":
            observed = harness.execute(tool, {"order_id": "ORD-992"})
            state = f"{prompt_b}\nPrior tool observation: cancel_order returned {observed.data}. Issue the refund next."
        elif tool == "issue_order_refund":
            observed = harness.execute(tool, {"order_id": "ORD-992", "amount": 10.0})
            print("refund output", observed.status, observed.data)
            break
        else:
            print("unexpected tool", tool)
            break
    print("B sequence", steps)

    # C. 30-tool haystack. Direct pointer over the full menu, plus the harness path.
    catalog = []
    golds = {
        "refund this customer's payment": "issue_order_refund",
        "open a sev1 incident titled disk full": "create_incident",
        "what is the weather in berlin": "query_weather_forecast",
        "read the deploy log file": "mcp_filesystem_read",
        "roll back the payments service to v2.1.0": "rollback-staging",
        "look up order ORD-100": "get_order_status",
        "cancel subscription for account A-9": "cancel_customer_subscription",
        "list the open incident tickets": "list_incidents",
    }
    decoys = [
        ("send_email", "Send an email message to a recipient"),
        ("send_sms", "Send a short text message to a phone"),
        ("send_slack", "Post a chat message in a channel"),
        ("send_webhook", "POST a notification payload to a webhook URL"),
        ("page_oncall", "Page the on-call engineer about an incident"),
        ("github_create_issue", "Open an engineering ticket in GitHub"),
        ("linear_create_issue", "Open an engineering ticket in Linear"),
        ("jira_create_issue", "Open an engineering ticket in Jira"),
        ("get_invoice", "Fetch an invoice pdf by invoice id"),
        ("list_invoices", "List invoices for an account"),
        ("update_address", "Change the shipping address on a customer account"),
        ("reset_password", "Reset a user password and email a link"),
        ("get_stock_price", "Look up a stock ticker price"),
        ("translate_text", "Translate a sentence into another language"),
        ("search_docs", "Search internal documentation"),
        ("create_calendar_event", "Create a meeting on the calendar"),
        ("get_user_profile", "Fetch a user profile by account id"),
        ("deploy_service", "Deploy a service version to production"),
        ("scale_replicas", "Change the replica count of a service"),
        ("query_metrics", "Query CPU metrics for a hostname"),
        ("delete_file", "Delete a file from the filesystem"),
        ("write_file", "Write text into a file"),
    ]
    targets = [
        ("issue_order_refund", "Issue a monetary refund for a customer order"),
        ("create_incident", "Open an incident ticket with a title and severity"),
        ("query_weather_forecast", "Query the weather forecast for a city"),
        ("mcp_filesystem_read", "Read a local log file from the filesystem"),
        ("rollback-staging", "Roll back a staging deployment to a target version"),
        ("get_order_status", "Check whether a customer order has shipped"),
        ("cancel_customer_subscription", "Cancel a customer paid subscription"),
        ("list_incidents", "List open incident tickets"),
    ]
    catalog = targets + decoys
    model = scorer._neural_model
    hits = 0
    sizes = []
    print("\n=== C haystack direct pointer ===")
    for query, gold in golds.items():
        criteria = {name: desc for name, desc in catalog}
        criteria["__abstain__"] = "None of the listed tools fit the user request."
        logits, keys = model.score_choice_sequence(
            f"User Request: {query}", "Which single tool should run?", criteria, max_seq_len=4096
        )
        probs = torch.softmax(logits, dim=-1)
        order = sorted(zip(keys, probs.tolist()), key=lambda kv: kv[1], reverse=True)
        pred = order[0][0]
        # Same singleton rule the harness uses: gap >= 0.20 and p >= 0.55, else mass 0.90.
        chosen = []
        if order[0][1] >= 0.55 and (len(order) == 1 or order[0][1] - order[1][1] >= 0.20):
            chosen = [pred]
        else:
            mass = 0.0
            for name, p in order:
                if name == "__abstain__":
                    continue
                chosen.append(name)
                mass += p
                if mass >= 0.90 or len(chosen) >= 8:
                    break
        ok = pred == gold
        hits += int(ok)
        sizes.append(len(chosen))
        print(f"  gold={gold:28} pred={pred:28} ok={ok} |S|={len(chosen)} p={order[0][1]:.3f}")
    n = len(golds)
    print(f"C top1 {hits}/{n} = {hits / n:.3f}  mean |S| = {sum(sizes) / n:.3f}")


if __name__ == "__main__":
    main()
