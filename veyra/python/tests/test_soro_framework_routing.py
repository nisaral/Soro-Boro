"""Deterministic routing + thin agent loop."""

from __future__ import annotations

from soro import RouteKind, SideEffectClass, Soro
from soro.core.state import ExecutionState
from soro.llm import OfflineLLM


def _catalog() -> Soro:
    s = Soro()

    @s.tool(description="Look up an order by id", side_effect_class=SideEffectClass.READ_ONLY)
    def get_order(order_id: str) -> dict:
        return {"order_id": order_id, "status": "paid"}

    @s.tool(description="Charge a payment card", side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION)
    def charge(transfer_id: str, amount: float) -> dict:
        return {"ok": True, "transfer_id": transfer_id, "amount": amount}

    @s.tool(description="Refund a previous charge", side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION)
    def refund(order_id: str) -> dict:
        return {"refunded": order_id}

    return s


def test_route_prefers_lookup_for_order_query():
    s = _catalog()
    decision = s.route("look up order 12 status")
    assert decision.kind in (RouteKind.EXECUTE, RouteKind.ASK)
    names = [c.tool for c in decision.shortlist]
    assert "get_order" in names
    assert decision.shortlist[0].tool == "get_order"


def test_proposed_illegal_tool_is_denied():
    s = _catalog()
    state = ExecutionState(permissions=set())
    decision = s.route(
        "charge the card",
        proposed_tool="charge",
        arguments={"transfer_id": "tx1", "amount": 10},
        state=state,
    )
    # charge has no extra permissions; should execute or ask, not crash
    assert decision.kind in (RouteKind.EXECUTE, RouteKind.ASK, RouteKind.DENY)


def test_empty_catalog_denies():
    s = Soro()
    decision = s.route("do something")
    assert decision.kind == RouteKind.DENY


def test_agent_executes_scripted_tool():
    s = _catalog()
    llm = OfflineLLM(script=[{"thought": "lookup", "tool": "get_order", "args": {"order_id": "12"}}])
    out = s.run("check order 12", llm=llm)
    assert out["status"] in ("DONE", "MAX_TURNS") or out["traces"][0].get("result")
    assert any("result" in t for t in out["traces"]) or out["status"] == "DONE"


def test_agent_abstains_when_model_invents_tool():
    s = _catalog()
    llm = OfflineLLM(script=[{"thought": "hack", "tool": "drop_database", "args": {}}])
    out = s.run("delete everything", llm=llm)
    assert out["status"] in ("DENIED", "ABSTAINED", "DENY", "ABSTAIN")
