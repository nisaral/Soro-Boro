"""Tools must stay inside the task workspace and inside the command allowlist."""

from pathlib import Path

from veyra import tools


def ctx(tmp_path: Path) -> tools.ToolContext:
    return tools.ToolContext(workspace=tmp_path)


def test_write_then_read_round_trip(tmp_path):
    ok, detail = tools.call_tool("write_file", {"path": "a/b.txt", "content": "hello"}, ctx(tmp_path))
    assert ok, detail
    ok, got = tools.call_tool("read_file", {"path": "a/b.txt"}, ctx(tmp_path))
    assert ok and got == "hello"


def test_path_escape_is_refused(tmp_path):
    ok, detail = tools.call_tool("read_file", {"path": "../../etc/passwd"}, ctx(tmp_path))
    assert not ok
    assert "escapes the workspace" in detail


def test_absolute_path_outside_workspace_is_refused(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    ok, detail = tools.call_tool("read_file", {"path": str(outside)}, ctx(tmp_path))
    assert not ok
    assert "escapes the workspace" in detail


def test_shell_allowlist_refuses_unknown_command(tmp_path):
    ok, detail = tools.call_tool("run_command", {"command": "rm -rf /"}, ctx(tmp_path))
    assert not ok
    assert "allowlist" in detail


def test_shell_refused_when_disabled(tmp_path):
    c = tools.ToolContext(workspace=tmp_path, allow_shell=False)
    ok, detail = tools.call_tool("run_command", {"command": "echo hi"}, c)
    assert not ok and "disabled" in detail


def test_unknown_tool_is_a_refusal_not_a_crash(tmp_path):
    ok, detail = tools.call_tool("nope", {}, ctx(tmp_path))
    assert not ok and "unknown tool" in detail
