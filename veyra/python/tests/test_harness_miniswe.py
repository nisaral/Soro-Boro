"""mini-swe-agent adapter: one upstream step, portable state, honest absence."""

from veyra.harness.miniswe import MiniSweHarness, available
from veyra.v1 import runtime_pb2 as pb


class _FakeAgent:
    def __init__(self):
        self.messages: list[dict] = []
        self.calls = 0

    def step(self):
        self.calls += 1
        if self.calls == 1:
            row = {"role": "assistant", "content": "ls"}
            self.messages.append(row)
            return [row]
        row = {"role": "exit", "content": "Submitted", "extra": {"exit_status": "Submitted"}}
        self.messages.append(row)
        return [row]


def test_miniswe_step_copies_messages_and_can_finish(tmp_path):
    agent = _FakeAgent()
    h = MiniSweHarness({"workspace": str(tmp_path), "agent": agent})
    task = pb.TaskSpec(id="t", instruction="fix the bug", workspace=str(tmp_path))
    state = h.start(task, None)
    assert state.variables["miniswe.engine"] == "injected"
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert any(m.content == "ls" for m in state.messages)
    assert not state.done
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert state.done
    assert agent.calls == 2


def test_miniswe_without_the_package_fails_visibly(tmp_path, monkeypatch):
    monkeypatch.setattr("veyra.harness.miniswe.available", lambda: (False, "not installed"))
    h = MiniSweHarness({"workspace": str(tmp_path)})
    task = pb.TaskSpec(id="t", instruction="fix", workspace=str(tmp_path))
    state = h.start(task, None)
    assert state.failed and state.failure_kind == "harness_error"
    assert any("not installed" in o for o in state.observations)


def test_available_reports_a_boolean():
    ok, detail = available()
    assert isinstance(ok, bool)
    assert detail
