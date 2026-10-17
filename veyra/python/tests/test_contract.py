"""The portable execution state is the checkpoint contract; keep it stable."""

from veyra import contract
from veyra.v1 import runtime_pb2 as pb


def task() -> pb.TaskSpec:
    return pb.TaskSpec(id="t1", instruction="do it", workspace="/ws",
                       metadata={"grader": "{}", "category": "coding"})


def test_new_state_adopts_task_metadata():
    state = contract.new_state(task(), harness_id="native", workspace="/ws")
    assert state.task_id == "t1"
    assert state.harness_id == "native"
    assert state.variables["category"] == "coding"
    assert state.usage.actions == 0


def test_charge_is_cumulative():
    state = contract.new_state(task())
    contract.charge(state, usd=0.001, wall_ms=10, tokens=5)
    contract.charge(state, usd=0.002, wall_ms=20, tokens=7)
    assert state.usage.usd == 0.003
    assert state.usage.actions == 2
    assert state.usage.tokens == 12


def test_mark_failed_then_clear_is_reversible():
    state = contract.new_state(task())
    contract.mark_failed(state, "tool", "boom")
    assert state.failed and state.failure_kind == "tool" and not state.done
    contract.clear_failure(state)
    assert not state.failed and state.failure_kind == ""


def test_note_harness_deduplicates():
    state = contract.new_state(task())
    contract.note_harness(state, "native")
    contract.note_harness(state, "langgraph")
    contract.note_harness(state, "native")
    assert contract.tried_harnesses(state) == ["native", "langgraph"]


def test_round_trip_through_serialization():
    state = contract.new_state(task(), harness_id="native")
    contract.add_message(state, "user", "hi")
    contract.note_harness(state, "native")
    clone = pb.CommonExecutionState()
    clone.ParseFromString(state.SerializeToString())
    assert contract.tried_harnesses(clone) == ["native"]
    assert clone.messages[0].content == "hi"
