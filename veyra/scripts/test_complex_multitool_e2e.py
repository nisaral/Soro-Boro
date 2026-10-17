"""Three multi-tool jobs on the 0.8B and 4B checkpoints.

Run on the laptop GPU:
  python scripts/test_complex_multitool_e2e.py
"""
from __future__ import annotations

import json
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


def catalog(harness: SoroHarness) -> None:
    def reg(name, desc, params, side="mutation"):
        harness.register_action(name, desc, params, lambda **kwargs: dict(kwargs), side_effect=side)

    reg("create_incident", "Open a sev1 incident ticket with a title", {"title": str, "severity": str})
    reg("rollback_deployment", "Roll back a deployment to a target version", {"service": str, "version": str})
    reg("slack_send_message", "Post an alert to the engineering Slack channel", {"channel": str, "text": str})
    reg("get_order_status", "Look up a customer order", {"order_id": str}, side="read_only")
    reg("cancel_shipment", "Cancel a pending warehouse shipment", {"order_id": str})
    reg("issue_order_refund", "Issue a monetary refund to the customer", {"order_id": str, "amount": float})
    reg("send_confirmation_email", "Send a confirmation email to the customer", {"to": str, "subject": str})
    reg("github_create_issue", "Open an engineering ticket in GitHub", {"title": str, "body": str})
    reg("jira_create_issue", "Open an engineering ticket in Jira", {"title": str, "body": str})
    reg("linear_create_issue", "Open an engineering ticket in Linear", {"title": str, "body": str})
    reg("query_weather_forecast", "Query the weather forecast for a city", {"city": str}, side="read_only")
    reg("get_invoice", "Fetch an invoice pdf by invoice id", {"invoice_id": str}, side="read_only")
    reg("delete_file", "Delete a file from the filesystem", {"path": str})
    reg("deploy_service", "Deploy a service version to production", {"service": str, "version": str})
    reg("reset_password", "Reset a user password and email a link", {"user": str})
    reg("query_metrics", "Query CPU metrics for a hostname", {"host": str}, side="read_only")


def tools_of(trace: list[dict]) -> list[str]:
    return [step["tool"] for step in trace if step.get("tool")]


def run_job(harness: SoroHarness, title: str, query: str, required: list[str]) -> dict:
    print(f"\n=== {title} ===", flush=True)
    trace = harness.run_workflow(query, max_steps=5)
    picked = tools_of(trace)
    print("picked", picked, flush=True)
    print(json.dumps(trace, default=str)[:2500], flush=True)
    missing = [name for name in required if name not in picked]
    extra = [name for name in picked if name not in required]
    ok = not missing and not extra
    print("ok", ok, "missing", missing, "extra", extra, flush=True)
    return {"title": title, "picked": picked, "ok": ok, "missing": missing, "extra": extra}


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit(f"CUDA is not available. torch={torch.__version__}")
    print("device", torch.cuda.get_device_name(0), flush=True)
    report = []
    for name, path in CKPTS.items():
        if not (path / "head.pt").exists():
            print("missing checkpoint", name, path, flush=True)
            continue
        print(f"\n##### {name} {path} #####", flush=True)
        scorer = LocalKevScorer(run=str(path), backend="neural", device="cuda")
        if not scorer.load():
            print("load failed", scorer.error, flush=True)
            continue
        report.append(name)
        jobs = [
            (
                "job1 devops",
                "We have a critical P0 outage on payments-api: open a sev1 incident ticket, roll back staging deployment to v2.3.0, and post an alert to the engineering Slack channel.",
                ["create_incident", "rollback_deployment", "slack_send_message"],
            ),
            (
                "job2 order",
                "Look up order ORD-774, cancel its pending warehouse shipment, issue a $129.00 refund to the customer, and send a confirmation email.",
                ["get_order_status", "cancel_shipment", "issue_order_refund", "send_confirmation_email"],
            ),
            (
                "job3 decoy",
                "Open a GitHub ticket for the auth memory leak. Do not file it in Jira or Linear.",
                ["github_create_issue"],
            ),
        ]
        for label, query, required in jobs:
            db = ROOT / "runs" / f"claims_{name}_{label.split()[0]}.db"
            wal = ROOT / "runs" / f"wal_{name}_{label.split()[0]}.jsonl"
            harness = SoroHarness(
                scorer=scorer,
                dedupe_mode="loop_guard",
                window_sec=120.0,
                claims_db_path=str(db),
                wal_path=str(wal),
            )
            catalog(harness)
            run_job(harness, f"{name} {label}", query, required)
        del scorer
        torch.cuda.empty_cache()
    print("DONE", report, flush=True)


if __name__ == "__main__":
    main()
