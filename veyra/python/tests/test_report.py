"""The verdict must implement the pre-registered claim, including null results."""

from veyra.bench import report


def res(arm, status, usd, category="coding"):
    return {"arm": arm, "status": status, "usd": usd, "wall_ms": 1, "actions": 1,
            "switches": 0, "category": category, "backends": ["heuristic"]}


def test_pick_best_fixed_prefers_success_over_cost():
    dev = [res("fixed:native", "SUCCEEDED", 0.01), res("fixed:native", "SUCCEEDED", 0.01),
           res("fixed:langgraph", "SUCCEEDED", 0.02), res("fixed:langgraph", "FAILED", 0.02)]
    assert report.pick_best_fixed(dev)[0] == "native"


def test_pick_best_fixed_breaks_ties_on_cost():
    dev = [res("fixed:native", "SUCCEEDED", 0.05), res("fixed:langgraph", "SUCCEEDED", 0.01)]
    assert report.pick_best_fixed(dev)[0] == "langgraph"


def test_pick_best_fixed_with_no_fixed_arms():
    assert report.pick_best_fixed([res("veyra:heuristic", "SUCCEEDED", 0.01)]) == ("", {})


def test_verdict_supported_when_adaptive_is_cheaper_and_not_worse():
    dev = [res("fixed:langgraph", "SUCCEEDED", 0.02), res("fixed:native", "FAILED", 0.01)]
    test = [res("fixed:langgraph", "SUCCEEDED", 0.02), res("fixed:langgraph", "SUCCEEDED", 0.02),
            res("veyra:heuristic", "SUCCEEDED", 0.01), res("veyra:heuristic", "SUCCEEDED", 0.01)]
    v = report.verdict(dev, test)
    assert v["outcome"] == "SUPPORTED"
    assert v["selected_on_dev"] == "langgraph"
    assert v["rows"][0]["cost_cut_pct"] > 0


def test_verdict_reports_a_null_result():
    dev = [res("fixed:langgraph", "SUCCEEDED", 0.02), res("fixed:langgraph", "SUCCEEDED", 0.02)]
    test = [res("fixed:langgraph", "SUCCEEDED", 0.02), res("fixed:langgraph", "SUCCEEDED", 0.02),
            res("veyra:heuristic", "FAILED", 0.01), res("veyra:heuristic", "FAILED", 0.01)]
    v = report.verdict(dev, test)
    assert v["outcome"] == "NOT SUPPORTED"
    assert v["supported"] == []


def test_markdown_includes_verdict_and_caveats():
    dev = [res("fixed:langgraph", "SUCCEEDED", 0.02)]
    test = [res("fixed:langgraph", "SUCCEEDED", 0.02), res("veyra:heuristic", "SUCCEEDED", 0.01)]
    md = report.markdown(test, {"caveats": ["scripted model"], "split": "test"}, dev)
    assert "Pre-registered verdict" in md
    assert "scripted model" in md
