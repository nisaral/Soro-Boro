"""Context compaction keeps the ends of the history and records what it dropped."""

from veyra.harness.native import NativeHarness
from veyra.v1 import runtime_pb2 as pb


def test_compact_keeps_first_and_last_messages(tmp_path):
    h = NativeHarness({"workspace": str(tmp_path)})
    state = pb.CommonExecutionState()
    for i in range(10):
        state.messages.append(pb.Message(role="user" if i % 2 == 0 else "assistant", content=f"message-{i}"))
    h.do_compact(state, keep_first=1, keep_last=2)
    roles = [m.content for m in state.messages]
    assert roles[0] == "message-0"
    assert "compacted 7 messages" in roles[1]
    assert roles[-2] == "message-8"
    assert roles[-1] == "message-9"
    assert any(o.startswith("compacted 7") for o in state.observations)


def test_compact_skips_a_short_history(tmp_path):
    h = NativeHarness({"workspace": str(tmp_path)})
    state = pb.CommonExecutionState()
    state.messages.append(pb.Message(role="system", content="sys"))
    h.do_compact(state)
    assert len(state.messages) == 1
    assert state.observations[0].startswith("compact skipped")
