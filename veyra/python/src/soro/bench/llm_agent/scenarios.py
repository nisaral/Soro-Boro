"""Evaluation Tasks for True LLM Agent Benchmark.

Multi-turn scenarios exercising real MCP servers (Weather, API Services, Filesystem, Database)
with 5 reproducible seeds for robust empirical measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentBenchmarkTask:
    """A multi-turn task definition evaluated on real MCP tools."""

    task_id: str
    seed: int
    instruction: str
    target_servers: list[str]
    allowed_tools: list[str]
    tool_aliases: dict[str, str] = field(default_factory=dict)
    max_turns: int = 5
    injected_transient: bool = False
    injected_schema_mismatch: bool = False
    verifier: Callable[[str, list[dict[str, Any]]], bool] | None = None


def get_llm_agent_tasks(seed: int = 1) -> list[AgentBenchmarkTask]:
    """Generate canonical multi-turn agent tasks parameterized by seed (1 to 5)."""
    cities = ["Tokyo", "London", "Paris", "Berlin", "Sydney"]
    paths = ["src/config.json", "docs/api.md", "README.md", "scripts/deploy.sh", "package.json"]
    db_names = ["production_db", "analytics_db", "users_db", "inventory_db", "finance_db"]
    
    city = "London"
    target_path = paths[(seed - 1) % len(paths)]
    target_db = db_names[(seed - 1) % len(db_names)]

    tasks = [
        # Task 1: Weather data retrieval with natural language tool alias (get_weather -> weather_data_retriever)
        AgentBenchmarkTask(
            task_id=f"agent_weather_alias_s{seed}",
            seed=seed,
            instruction=(
                f"Retrieve the historical weather data for {city} between 03/01 and 03/10 for year 2020. "
                "Report the conditions and average temperature."
            ),
            target_servers=["weather_data_retriever"],
            allowed_tools=["weather_data_retriever"],
            tool_aliases={"get_weather": "weather_data_retriever", "fetch_weather": "weather_data_retriever"},
            injected_schema_mismatch=True,
            verifier=lambda answer, history: (
                len(history) >= 1
                and any("temperature" in str(h.get("observation", "")).lower() or "temp" in str(h.get("observation", "")).lower() for h in history)
                and len(answer) > 0
            ),
        ),

        # Task 2: Weather retrieval with transient upstream timeout on attempt 1
        AgentBenchmarkTask(
            task_id=f"agent_weather_transient_s{seed}",
            seed=seed,
            instruction=(
                f"Query weather observations for {city} over 03/01 to 03/05 for range 2021-2022."
            ),
            target_servers=["weather_data_retriever"],
            allowed_tools=["weather_data_retriever"],
            tool_aliases={"get_weather": "weather_data_retriever"},
            injected_transient=True,  # Transient 503 on first call: tests safe boundary retry
            verifier=lambda answer, history: len(history) >= 1 and len(answer) > 0,
        ),

        # Task 3: API Request with alias (http_get -> make_api_request)
        AgentBenchmarkTask(
            task_id=f"agent_api_request_s{seed}",
            seed=seed,
            instruction=(
                f"Make an API request to the service 'metrics-api' at 'https://api.internal' endpoint '/v{seed}/health'."
            ),
            target_servers=["make_api_request"],
            allowed_tools=["make_api_request"],
            tool_aliases={"http_get": "make_api_request", "api_call": "make_api_request"},
            injected_schema_mismatch=False,
            verifier=lambda answer, history: len(history) >= 1 and len(answer) > 0,
        ),

        # Task 4: File search & read with alias (find_files -> search_and_read_files)
        AgentBenchmarkTask(
            task_id=f"agent_fs_read_s{seed}",
            seed=seed,
            instruction=(
                f"Inspect the project file located at '{target_path}' and report its contents."
            ),
            target_servers=["search_and_read_files"],
            allowed_tools=["search_and_read_files"],
            tool_aliases={"find_files": "search_and_read_files", "read_file": "search_and_read_files"},
            injected_transient=False,
            verifier=lambda answer, history: len(history) >= 1 and len(answer) > 0,
        ),
    ]

    return tasks
