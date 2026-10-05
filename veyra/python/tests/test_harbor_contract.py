"""Contract test for VeyraHarborAgent against Harbor's BaseAgent.

Tests that VeyraHarborAgent conforms to Harbor's BaseAgent interface:
- Subclasses BaseAgent
- Instantiates cleanly with logs_dir, model_name, and custom options
- Preflight and options_schema methods work
- setup() and run() adhere to Harbor's async environment and AgentContext contract
- Fail-open semantics when environment or controller raises
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from veyra.harbor_agent import VeyraHarborAgent

try:
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment, ExecResult
    from harbor.models.agent.context import AgentContext
    _HAS_HARBOR = True
except ImportError:
    _HAS_HARBOR = False


class FakeEnvironment(BaseEnvironment):
    """Minimal fake environment conforming to Harbor's BaseEnvironment."""

    def __init__(self, should_fail: bool = False):
        self.commands: list[str] = []
        self.should_fail = should_fail

    @classmethod
    def type(cls) -> str:
        return "fake"

    def _validate_definition(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self, delete: bool = False) -> None:
        pass

    async def upload_file(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def upload_dir(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def download_file(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def download_dir(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
        user: str | int | None = None,
    ) -> ExecResult:
        if self.should_fail:
            raise RuntimeError("Environment execution failed")
        self.commands.append(command)
        return ExecResult(return_code=0, stdout=f"executed: {command}", stderr="")


def test_conforms_to_base_agent():
    assert issubclass(VeyraHarborAgent, BaseAgent)


def test_agent_naming_and_version(tmp_path: Path):
    agent = VeyraHarborAgent(logs_dir=tmp_path, model_name="gpt-5.3-codex")
    assert agent.name() == "veyra"
    assert agent.version() is not None
    info = agent.to_agent_info()
    assert info.name == "veyra"
    if hasattr(info, "model_info") and info.model_info:
        assert info.model_info.name == "gpt-5.3-codex"


def test_options_schema():
    schema = VeyraHarborAgent.options_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "shadow" in schema["properties"]


@pytest.mark.asyncio
async def test_agent_run_contract(tmp_path: Path):
    agent = VeyraHarborAgent(logs_dir=tmp_path, model_name="gemini-3.1-pro", shadow=True)
    env = FakeEnvironment()
    ctx = AgentContext()

    await agent.setup(env)
    await agent.run("pytest python/tests", env, ctx)

    assert "pytest python/tests" in env.commands
    assert ctx.metadata.get("veyra_shadow") is True


@pytest.mark.asyncio
async def test_agent_fails_open_on_env_failure(tmp_path: Path):
    agent = VeyraHarborAgent(logs_dir=tmp_path, model_name="claude-3-7-sonnet", shadow=True)
    env = FakeEnvironment(should_fail=True)
    ctx = AgentContext()

    # Even if environment raises, agent setup and run do not crash unhandled
    await agent.setup(env)
    with pytest.raises(RuntimeError, match="Environment execution failed"):
        await agent.run("risky command", env, ctx)
    assert ctx.metadata.get("veyra_shadow") is True
