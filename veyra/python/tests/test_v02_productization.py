"""Tests for Veyra v0.2 productization, framework integrations, plugins, CLI, and replay."""

import json
import pytest
from veyra import Veyra
from veyra.config import VeyraConfigManager
from veyra.integrations.openai_agents import VeyraOpenAIAgentsAdapter
from veyra.integrations.langgraph import VeyraLangGraphNode
from veyra.integrations.autogen import VeyraAutoGenAdapter
from veyra.integrations.microsoft_agent_framework import VeyraMicrosoftAgentMiddleware
from veyra.plugins import default_plugins, veyra_plugin, PluginMetadata
from veyra.replay import TrajectoryReplayer, TrajectoryDiff


def test_veyra_instantiation_and_wrappers():
    veyra = Veyra(policy="default", mode="fail_closed")
    assert veyra.mode == "fail_closed"

    @veyra.wrap
    def add(a: int, b: int) -> int:
        return a + b

    res = add(a=2, b=3)
    assert res == 5


def test_openai_agents_integration():
    veyra = Veyra()
    adapter = VeyraOpenAIAgentsAdapter(veyra)

    def sample_tool(x: int) -> int:
        return x * 2

    wrapped = adapter.wrap_tool(sample_tool)
    assert wrapped(x=5) == 10


def test_langgraph_integration():
    veyra = Veyra()

    def my_tool(val: str) -> str:
        return f"hello_{val}"

    lg_node = VeyraLangGraphNode(veyra, [my_tool])
    res_state = lg_node({"proposed_action": {"tool": "my_tool", "arguments": {"val": "world"}}})
    assert res_state.get("tool_result") == "hello_world"


def test_autogen_integration():
    veyra = Veyra()
    adapter = VeyraAutoGenAdapter(veyra)

    def echo(msg: str) -> str:
        return msg

    fn = adapter.register_function(echo)
    assert fn(msg="autogen") == "autogen"


def test_microsoft_agent_integration():
    veyra = Veyra()
    middleware = VeyraMicrosoftAgentMiddleware(veyra)

    def calc(x: int) -> int:
        return x + 10

    res = middleware("calc", {"x": 5}, calc)
    assert res == 15


def test_plugin_system():
    @veyra_plugin(name="test_plugin", version="1.0.0", capabilities=["custom_policy"])
    class CustomPolicyPlugin:
        pass

    assert "test_plugin" in default_plugins.list_plugins()
    meta = default_plugins.inspect("test_plugin")
    assert meta["version"] == "1.0.0"
    val = default_plugins.validate("test_plugin")
    assert val["valid"] is True


def test_config_system():
    cfg = VeyraConfigManager.load()
    val = VeyraConfigManager.validate(cfg)
    assert val["valid"] is True
    exp = VeyraConfigManager.explain(cfg)
    assert "active_policies" in exp


def test_replay_and_diff(tmp_path):
    veyra = Veyra()
    replayer = TrajectoryReplayer(veyra, mode="DRY_RUN")

    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps({
        "traces": [
            {"proposed_tool": "test_tool", "arguments": {"a": 1}}
        ]
    }))

    res = replayer.replay_file(str(run_file))
    assert res["mode"] == "DRY_RUN"
    assert len(res["step_results"]) == 1

    diff = TrajectoryDiff.compare_files(str(run_file), str(run_file))
    assert len(diff["diffs"]) == 1
    assert diff["diffs"][0]["tool_changed"] is False
