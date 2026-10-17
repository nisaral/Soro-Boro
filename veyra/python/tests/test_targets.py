from veyra.bench.targets import ARMS, METRICS, SHIFTS, TARGETS


def test_harbor_public_is_the_zero_cost_first_step():
    main = next(t for t in TARGETS if t.id == "harbor-public")
    assert main.status == "not_run"


def test_mcpagentbench_is_smoke_only():
    smoke = next(t for t in TARGETS if t.id == "mcpagentbench")
    assert smoke.status == "smoke"


def test_no_target_is_marked_measured():
    assert all(t.status in {"not_run", "specified", "not_scheduled", "smoke"} for t in TARGETS)


def test_shiftbench_covers_the_seven_environment_changes():
    assert SHIFTS == (
        "unavailable", "expensive", "unreliable", "schema",
        "permission", "new_tool", "misleading",
    )


def test_the_five_arms_and_the_metrics_are_fixed():
    assert ARMS[0] == "fixed-react"
    assert "wasted_tool_calls" in METRICS
    assert "abstentions" in METRICS
