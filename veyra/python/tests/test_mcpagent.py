import asyncio

import pytest

from veyra.bench.mcpagent import bench_root, require_llm, wrap_tools_with_policy


def test_official_checkout_is_present():
    root = bench_root()
    assert (root / "runbenchmark.py").is_file()
    assert (root / "src" / "evaluate.py").is_file()
    assert (root / "data" / "tasks.json").is_file()


def test_missing_api_key_is_an_error(monkeypatch):
    monkeypatch.delenv("ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No LLM configured"):
        require_llm()


def test_local_base_url_does_not_need_a_cloud_key():
    assert require_llm(base_url="http://127.0.0.1:1234/v1", api_key="local") == "local"


class _Tool:
    def __init__(self, name, fail_times=0):
        self.name = name
        self.schema = {"name": name}
        self.fail_times = fail_times
        self.calls = 0

    async def run(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("tool failed")
        return "ok"


def test_heuristic_drops_a_tool_after_two_failures():
    async def body():
        tool = _Tool("search", fail_times=5)
        gated = wrap_tools_with_policy([tool], "heuristic")[0]
        with pytest.raises(RuntimeError):
            await gated.run()
        with pytest.raises(RuntimeError):
            await gated.run()
        msg = await gated.run()
        assert "dropped" in msg
        assert tool.calls == 2

    asyncio.run(body())


def test_react_does_not_gate_tools():
    async def body():
        tool = _Tool("search", fail_times=5)
        gated = wrap_tools_with_policy([tool], "react")[0]
        with pytest.raises(RuntimeError):
            await gated.run()
        with pytest.raises(RuntimeError):
            await gated.run()
        with pytest.raises(RuntimeError):
            await gated.run()
        assert tool.calls == 3

    asyncio.run(body())
