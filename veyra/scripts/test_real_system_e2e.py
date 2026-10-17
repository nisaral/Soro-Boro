"""End-to-end SoroHarness test against the real 0.8B checkpoint and a real SQLite file.

No mock backbone. LocalKevScorer(backend="neural") loads PeftModel + head.pt.
"""

from __future__ import annotations

import sqlite3
import tempfile
import traceback
from pathlib import Path

from soro.harness.pipeline import SoroHarness
from soro.routing.kev_local import LocalKevScorer
from soro_boro.lifecycle import ProviderLifecycleState, ReconciliationResult

CKPT = Path(__file__).resolve().parents[1] / "runs" / "kaggle_0.8b_results" / "soro_kev_0.8b"


def main() -> None:
    if not (CKPT / "head.pt").exists() or not (CKPT / "adapter_model.safetensors").exists():
        raise SystemExit(f"Real checkpoint missing at {CKPT}")

    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root = Path(tmp.name)
    db_path = root / "shop.sqlite"
    log_path = root / "deploy.log"
    log_path.write_text("2026-10-16 auth-service healthy\n", encoding="utf-8")
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE orders (order_id TEXT PRIMARY KEY, status TEXT, total_usd REAL);
        CREATE TABLE refunds (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, amount REAL, reason TEXT);
        CREATE TABLE incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, severity TEXT);
        CREATE TABLE deployments (id INTEGER PRIMARY KEY AUTOINCREMENT, service_name TEXT, target_version TEXT, event TEXT);
        """
    )
    con.execute("INSERT INTO orders VALUES ('ORD-501', 'delivered', 49.95)")
    con.execute("INSERT INTO orders VALUES ('ORD-502', 'delivered', 20.00)")
    con.commit()

    scorer = LocalKevScorer(run=str(CKPT), backend="neural", device="cpu")
    assert scorer.load(), scorer.error
    backbone = type(scorer._neural_model.backbone).__name__
    print("BACKBONE", backbone)
    if "Mock" in backbone:
        raise SystemExit("Refusing to test a mock backbone")

    harness = SoroHarness(
        scorer=scorer,
        dedupe_mode="loop_guard",
        window_sec=120.0,
        claims_db_path=str(root / "claims.db"),
        wal_path=str(root / "wal.jsonl"),
    )
    raised_502 = {"done": False}

    @harness.tool(description="Look up the delivery status of a customer order by its order id", side_effect="read_only")
    def get_order_status(order_id: str):
        row = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return {"order_id": order_id, "row": row}

    def refund_reconciler(_op):
        row = con.execute("SELECT * FROM refunds WHERE order_id = ?", ("ORD-502",)).fetchone()
        if row:
            return ReconciliationResult(
                state=ProviderLifecycleState.SUCCEEDED,
                raw_response={"order_id": row[1], "amount": row[2], "reason": row[3]},
            )
        return ReconciliationResult(state=ProviderLifecycleState.NOT_FOUND)

    @harness.tool(
        description="Issue a monetary refund for a customer order that arrived damaged",
        side_effect="mutation",
        reconciler=refund_reconciler,
    )
    def issue_order_refund(order_id: str, amount: float, reason: str = "damaged"):
        con.execute(
            "INSERT INTO refunds (order_id, amount, reason) VALUES (?, ?, ?)",
            (order_id, amount, reason),
        )
        con.commit()
        if order_id == "ORD-502" and not raised_502["done"]:
            raised_502["done"] = True
            raise TimeoutError("504 Gateway Timeout")
        return {"order_id": order_id, "amount": amount, "reason": reason}

    def create_incident(title: str, severity: str):
        con.execute("INSERT INTO incidents (title, severity) VALUES (?, ?)", (title, severity))
        con.commit()
        return {"title": title, "severity": severity}

    harness.register_rest(
        "/api/v1/incidents/create",
        method="POST",
        name="create_incident",
        description="Open an incident ticket with a title and severity",
        parameters={"title": str, "severity": str},
        fn=create_incident,
        side_effect="mutation",
    )

    def list_incidents():
        return {"rows": con.execute("SELECT title, severity FROM incidents").fetchall()}

    harness.register_rest(
        "/api/v1/incidents/list",
        method="GET",
        name="list_incidents",
        description="List open incident tickets",
        parameters={},
        fn=list_incidents,
        side_effect="read_only",
    )

    def rollback(service_name: str, target_version: str):
        con.execute(
            "INSERT INTO deployments (service_name, target_version, event) VALUES (?, ?, 'rollback')",
            (service_name, target_version),
        )
        con.commit()
        return {"service_name": service_name, "target_version": target_version}

    harness.register_skill(
        "rollback-staging",
        description="Roll back a staging deployment of a named service to a target version",
        triggers=["roll back", "rollback staging"],
        parameters={"service_name": str, "target_version": str},
        fn=rollback,
        side_effect="destructive",
    )

    def read_log(file_path: str):
        return {"file_path": file_path, "text": Path(file_path).read_text(encoding="utf-8")}

    harness.register(
        {
            "name": "mcp_filesystem_read",
            "description": "Read a local log file from the filesystem",
            "inputSchema": {"properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
        },
        side_effect="read_only",
    )
    # Replace the dict stub with the real file reader.
    harness._tools["mcp_filesystem_read"].fn = read_log
    from soro_boro.boundary import soro_wrap
    from soro_boro.lifecycle import SideEffectClass
    harness._tools["mcp_filesystem_read"].wrapped_fn = soro_wrap(
        side_effect_class=SideEffectClass.READ_ONLY,
        dedupe_mode="loop_guard",
        window_sec=120.0,
        claims_db_path=str(root / "claims.db"),
        wal_path=str(root / "wal.jsonl"),
    )(read_log)

    @harness.tool(description="Cancel a customer's paid subscription account", side_effect="mutation")
    def cancel_customer_subscription(account_id: str):
        return {"account_id": account_id, "cancelled": True}

    @harness.tool(description="Query the weather forecast for a city", side_effect="read_only")
    def query_weather_forecast(city: str):
        return {"city": city, "forecast": "clear"}

    def count(sql: str, args=()) -> int:
        return con.execute(sql, args).fetchone()[0]

    def show(title: str, route, outcome=None):
        print(f"\n=== {title} ===")
        if route is not None:
            print("action", route.action, "tool", route.selected_tool)
            print("candidates", route.candidates)
            print("probabilities", {k: round(v, 4) for k, v in (route.probabilities or {}).items()})
            print("reason", route.reason)
        if outcome is not None:
            print("status", outcome.status, "reason", outcome.reason)
            print("output", outcome.data)

    failures = []

    def check(name: str, cond: bool, detail: str):
        print(("PASS" if cond else "FAIL"), name, detail)
        if not cond:
            failures.append(name)

    try:
        q1 = "Please refund $49.95 for order ORD-501 because the screen arrived cracked"
        args1 = {"customer_order_ref": "ORD-501", "refund_usd": "49.95", "extra_hallucinated_flag": True}
        route1 = harness.route(q1)
        repaired = harness.repair("issue_order_refund", args1)
        show("Test 1 route+repair", route1)
        print("repaired", repaired)
        res1 = harness.execute("issue_order_refund", repaired)
        show("Test 1 execute", None, res1)
        n1 = count("SELECT COUNT(*) FROM refunds WHERE order_id='ORD-501'")
        print("refund rows ORD-501", n1)
        check("route refund", route1.selected_tool == "issue_order_refund", str(route1.selected_tool))
        check("repair order_id", repaired.get("order_id") == "ORD-501", str(repaired))
        check("repair amount float", repaired.get("amount") == 49.95 and isinstance(repaired.get("amount"), float), str(repaired.get("amount")))
        check("drop hallucinated", "extra_hallucinated_flag" not in repaired, str(repaired))
        check("one refund row", n1 == 1 and res1.status == "COMMITTED", f"{res1.status} rows={n1}")

        res2 = harness.execute("issue_order_refund", repaired)
        show("Test 2 duplicate", None, res2)
        n2 = count("SELECT COUNT(*) FROM refunds WHERE order_id='ORD-501'")
        print("refund rows ORD-501", n2)
        check("duplicate blocked", res2.status == "PREVENTED_DUPLICATE" and n2 == 1, f"{res2.status} rows={n2}")

        route3 = harness.route("Refund 20 dollars for order ORD-502")
        repaired3 = harness.repair("issue_order_refund", {"order_id": "ORD-502", "amount": 20.0, "reason": "late"})
        res3 = harness.execute("issue_order_refund", repaired3)
        show("Test 3 timeout then reconcile", route3, res3)
        n3 = count("SELECT COUNT(*) FROM refunds WHERE order_id='ORD-502'")
        res3b = harness.execute("issue_order_refund", repaired3)
        n3b = count("SELECT COUNT(*) FROM refunds WHERE order_id='ORD-502'")
        print("retry status", res3b.status, "rows", n3b)
        check("timeout reconciled", res3.status == "PREVENTED_DUPLICATE" and n3 == 1, f"{res3.status} rows={n3}")
        check("retry no second row", n3b == 1, str(n3b))

        q4a = "Open a sev1 incident ticket titled Database connection pool exhausted"
        route4a = harness.route(q4a)
        extracted4a = harness.extract_and_map_arguments(q4a, route4a.selected_tool or "create_incident")
        res4a = harness.run(q4a)
        show("Test 4a REST", route4a, res4a)
        print("extracted", extracted4a)
        n_inc = count("SELECT COUNT(*) FROM incidents")
        print("incidents", n_inc)
        check("rest route", route4a.selected_tool == "create_incident", str(route4a.selected_tool))
        check(
            "incident row",
            n_inc == 1 and res4a.status == "COMMITTED" and "pool" in str(res4a.data).lower(),
            f"{res4a.status} rows={n_inc} data={res4a.data}",
        )

        q4b = "Roll back the auth-service deployment in staging to v1.4.2"
        route4b = harness.route(q4b)
        res4b = harness.run(q4b)
        show("Test 4b skill", route4b, res4b)
        n_dep = count("SELECT COUNT(*) FROM deployments")
        print("deployments", n_dep, con.execute("SELECT service_name, target_version FROM deployments").fetchall())
        check("skill route", route4b.selected_tool == "rollback-staging", str(route4b.selected_tool))
        dep_row = con.execute("SELECT service_name, target_version FROM deployments").fetchone()
        check(
            "deployment row",
            n_dep == 1 and res4b.status == "COMMITTED" and dep_row == ("auth-service", "v1.4.2"),
            f"{res4b.status} row={dep_row}",
        )

        before = count("SELECT COUNT(*) FROM refunds")
        q5 = "Please refund my order right away"
        route5 = harness.route(q5)
        res5 = harness.run(q5, {})
        show("Test 5 missing", route5, res5)
        after = count("SELECT COUNT(*) FROM refunds")
        check("missing asks", res5.status == "ASK" and after == before, f"{res5.status} rows {before}->{after} data={res5.data}")

        q6 = "How do I bake a chocolate souffle at 375 degrees?"
        route6 = harness.route(q6)
        res6 = harness.run(q6)
        show("Test 6 abstain", route6, res6)
        check("abstain", route6.action == "ABSTAIN" and res6.status == "ABSTAIN", f"{route6.action} {res6.status}")
    except Exception:
        traceback.print_exc()
        failures.append("exception")

    print("\nFAILURES", failures or "none")
    con.close()
    tmp.cleanup()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
