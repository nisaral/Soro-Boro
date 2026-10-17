"""The MiniGraph fallback must behave like the slice of LangGraph the adapter uses."""

from veyra.harness.langgraph_harness import END_SENTINEL, START_SENTINEL, MiniGraph


def test_conditional_dispatch_reaches_end():
    g = MiniGraph()
    g.add_node("reason", lambda s: {"out": "reasoned"})
    g.add_node("act", lambda s: {"out": "acted"})
    g.add_conditional_edges(START_SENTINEL, lambda s: s["pick"], {"r": "reason", "a": "act"})
    g.add_edge("reason", END_SENTINEL)
    g.add_edge("act", END_SENTINEL)
    graph = g.compile()
    assert graph.invoke({"pick": "r"})["out"] == "reasoned"
    assert graph.invoke({"pick": "a"})["out"] == "acted"


def test_unmapped_node_stops_instead_of_looping_forever():
    g = MiniGraph()
    g.add_node("only", lambda s: {"seen": True})
    g.add_conditional_edges(START_SENTINEL, lambda s: "only", {"only": "only"})
    out = g.compile().invoke({})
    assert out.get("seen") is True
