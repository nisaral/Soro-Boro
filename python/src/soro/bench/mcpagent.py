"""Run official MCPAgentBench without changing its tasks or evaluator.

The checkout lives in ``third_party/MCPAgentBench``. ReAct mode calls their
``run_experiment`` as-is. Veyra modes wrap each MCP tool so the same LLM still
proposes the call, then a policy may drop a wasted retry before the tool runs.

A result is only a public score when a real chat LLM finishes the run. Local
OpenAI-compatible servers (LM Studio) are supported by temporarily injecting a
model entry into their llm_config for the duration of the run, then restoring
the file.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


def bench_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "third_party" / "MCPAgentBench"
        if (candidate / "runbenchmark.py").is_file():
            return candidate
    raise FileNotFoundError(
        "MCPAgentBench is missing. From the repo root: "
        "git submodule update --init third_party/MCPAgentBench"
    )


def require_llm(*, base_url: str | None = None, api_key: str | None = None) -> str:
    if base_url:
        return api_key or "local"
    key = (
        api_key
        or os.environ.get("ROUTER_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("API_KEY")
    )
    if not key:
        raise RuntimeError(
            "No LLM configured. Either set ROUTER_API_KEY, or pass "
            "--base-url http://127.0.0.1:1234/v1 --api-key local for LM Studio."
        )
    return key


@contextmanager
def temporary_llm_entry(*, model: str, base_url: str | None, api_key: str, limit: int | None):
    """Inject a local model into llm_config.json and optionally truncate the task file."""
    root = bench_root()
    cfg_path = root / "configs" / "llm_config.json"
    cfg_backup = cfg_path.read_text(encoding="utf-8")
    task_backups: list[tuple[Path, str]] = []

    if base_url:
        entry = {
            "model": model,
            "base_url": base_url.rstrip("/"),
            "api_key_env_name": "VEYRA_LOCAL_LLM_KEY",
            "model_info": {
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": "local",
                "structured_output": True,
            },
        }
        # Only the local client for this run. Cloud entries without keys create noise.
        cfg_path.write_text(json.dumps([entry], indent=2), encoding="utf-8")
        os.environ["VEYRA_LOCAL_LLM_KEY"] = api_key

    if limit is not None and limit > 0:
        mapping = {
            "day": "data/daytasks.json",
            "pro": "data/protasks.json",
            "general_test": "data/tasks.json",
        }
        # Truncation is only for plumbing smoke. Callers must label the output.
        for rel in mapping.values():
            path = root / rel
            original = path.read_text(encoding="utf-8")
            task_backups.append((path, original))
            data = json.loads(original)
            path.write_text(json.dumps(data[:limit], indent=2), encoding="utf-8")

    try:
        yield
    finally:
        cfg_path.write_text(cfg_backup, encoding="utf-8")
        for path, original in task_backups:
            path.write_text(original, encoding="utf-8")


async def run_official(*, model: str, tasks_type: str, concurrency: int | None,
                       num_servers: int | None, output_name: str | None,
                       base_url: str | None = None, api_key: str | None = None,
                       limit: int | None = None) -> float:
    """Vanilla ReAct: the benchmark's own AutoGen agent, unchanged."""
    key = require_llm(base_url=base_url, api_key=api_key)
    root = bench_root()
    cwd = os.getcwd()
    with temporary_llm_entry(model=model, base_url=base_url, api_key=key, limit=limit):
        os.chdir(root)
        sys.path.insert(0, str(root))
        try:
            from src.experiment import run_experiment

            return await run_experiment(
                model=model,
                tasks_type=tasks_type,
                concurrency=concurrency,
                num_servers=num_servers,
                output_name=output_name,
            )
        finally:
            os.chdir(cwd)


def wrap_tools_with_policy(tools: list, policy: str) -> list:
    """Gate MCP tools. The LLM still proposes the call; the policy may refuse it.

    ``react`` leaves the list untouched. ``heuristic`` drops a tool after two
    consecutive failures of the same name. Gold labels are never consulted.
    """
    if policy in {"react", "none", ""}:
        return tools
    fails: dict[str, int] = {}
    return [_gate_one(tool, fails, policy) for tool in tools]


def _gate_one(tool, fails: dict[str, int], policy: str):
    name = getattr(tool, "name", None) or (tool.schema.get("name") if hasattr(tool, "schema") else "tool")
    original = tool.run if hasattr(tool, "run") else tool

    async def run(*args, **kwargs):
        if policy == "heuristic" and fails.get(name, 0) >= 2:
            return f"veyra policy dropped {name}: two consecutive failures"
        try:
            out = original(*args, **kwargs)
            if hasattr(out, "__await__"):
                out = await out
            fails[name] = 0
            return out
        except Exception:
            fails[name] = fails.get(name, 0) + 1
            raise

    if hasattr(tool, "run"):
        tool.run = run  # type: ignore[method-assign]
        return tool
    return run


async def run_veyra(*, model: str, tasks_type: str, policy: str,
                    concurrency: int | None, num_servers: int | None,
                    output_name: str | None,
                    base_url: str | None = None, api_key: str | None = None,
                    limit: int | None = None) -> float:
    """Same experiment, tools gated by a Veyra policy. Evaluator is theirs."""
    key = require_llm(base_url=base_url, api_key=api_key)
    root = bench_root()
    cwd = os.getcwd()
    with temporary_llm_entry(model=model, base_url=base_url, api_key=key, limit=limit):
        os.chdir(root)
        sys.path.insert(0, str(root))
        try:
            import src.agenttest as agenttest
            from src.experiment import run_experiment

            original = agenttest.construct_agent

            async def construct_agent(client, task_correct_tools, num_servers, num_tools):
                assistant = await original(client, task_correct_tools, num_servers, num_tools)
                tools = getattr(assistant, "_tools", None) or getattr(assistant, "tools", None)
                if tools:
                    gated = wrap_tools_with_policy(list(tools), policy)
                    if hasattr(assistant, "_tools"):
                        assistant._tools = gated
                    elif hasattr(assistant, "tools"):
                        assistant.tools = gated
                return assistant

            agenttest.construct_agent = construct_agent
            try:
                return await run_experiment(
                    model=model,
                    tasks_type=tasks_type,
                    concurrency=concurrency,
                    num_servers=num_servers,
                    output_name=output_name,
                )
            finally:
                agenttest.construct_agent = original
        finally:
            os.chdir(cwd)
