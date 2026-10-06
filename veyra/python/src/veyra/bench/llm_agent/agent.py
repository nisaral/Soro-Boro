"""Agent Interface and Implementations for the Benchmark Harness.

Supports both live LLMs (OpenAI, Anthropic via gateway, Ollama, LM Studio)
and a deterministic simulated agent for offline, zero-spend reproducible evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from veyra.bench.llm_agent.scenarios import AgentBenchmarkTask
from veyra.llm import LLMClient


@dataclass
class AgentTurnOutput:
    """The output produced by an agent on a single turn."""

    thought: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None
    raw_response: str = ""


class AgentDriver(Protocol):
    """Protocol for driving an agent during a multi-turn benchmark task."""

    def act(
        self,
        task: AgentBenchmarkTask,
        conversation_history: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
    ) -> AgentTurnOutput: ...


class LiveAgentDriver:
    """Live LLM driver using an OpenAI-compatible endpoint."""

    def __init__(self, client: LLMClient, tier: str = "cheap"):
        self.client = client
        self.tier = tier

    def act(
        self,
        task: AgentBenchmarkTask,
        conversation_history: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
    ) -> AgentTurnOutput:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant solving a task using tools.\n"
                    "Available tools:\n"
                    + json.dumps(available_tools, indent=2)
                    + "\n\nRespond with JSON: {\"thought\": \"...\", \"tool\": \"<tool_name>\", \"args\": {...}}\n"
                    "or when finished: {\"thought\": \"...\", \"final\": \"<answer>\"}"
                ),
            },
            {"role": "user", "content": task.instruction},
        ]

        for turn in conversation_history:
            if "tool_call" in turn:
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "thought": turn.get("thought", ""),
                        "tool": turn["tool_call"].get("name"),
                        "args": turn["tool_call"].get("args", {}),
                    }),
                })
            if "observation" in turn:
                messages.append({
                    "role": "user",
                    "content": f"Observation: {turn['observation']}",
                })

        reply = self.client.complete(
            messages=messages,
            tier=self.tier,
            tools=[t["name"] for t in available_tools],
        )

        return AgentTurnOutput(
            thought=reply.text,
            tool_name=reply.tool,
            tool_args=reply.args or {},
            final_answer=reply.final,
            raw_response=reply.raw,
        )


class DeterministicSimulatedAgentDriver:
    """Deterministic simulated agent that replicates realistic LLM agent behaviors across seeds.
    
    Exhibits natural LLM patterns:
    1. Proposes natural language aliases (e.g. 'get_weather' instead of canonical 'weather_data_retriever').
    2. Responds to error feedback by re-planning on the next turn.
    3. Concludes with a final answer once observations are gathered.
    """

    def act(
        self,
        task: AgentBenchmarkTask,
        conversation_history: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
    ) -> AgentTurnOutput:
        has_error = False
        last_observation = ""

        if conversation_history:
            last_turn = conversation_history[-1]
            last_observation = str(last_turn.get("observation", ""))
            if "error" in last_observation.lower() or "exception" in last_observation.lower() or "resolution error" in last_observation.lower():
                has_error = True

        # Turn 0: initial proposal
        if not conversation_history:
            if "weather" in task.task_id:
                tool_name = "get_weather" if "get_weather" in task.tool_aliases else "weather_data_retriever"
                args = {
                    "location": "London",
                    "start_date": "03/01",
                    "end_date": "03/10",
                    "range": "2020-2020",
                }
                return AgentTurnOutput(
                    thought="I need to retrieve historical weather data for London.",
                    tool_name=tool_name,
                    tool_args=args,
                )
            elif "api_request" in task.task_id:
                tool_name = "http_get" if "http_get" in task.tool_aliases else "make_api_request"
                return AgentTurnOutput(
                    thought="I will invoke the API endpoint to check service health.",
                    tool_name=tool_name,
                    tool_args={
                        "apiName": "metrics-api",
                        "url": "https://api.internal",
                        "endpoint": f"/v{task.seed}/health",
                    },
                )
            elif "fs_read" in task.task_id:
                tool_name = "find_files" if "find_files" in task.tool_aliases else "search_and_read_files"
                return AgentTurnOutput(
                    thought="I will inspect the file using the search tool.",
                    tool_name=tool_name,
                    tool_args={"path": "README.md"},
                )

        # If previous turn produced an error, agent must re-plan!
        if has_error:
            canonical = task.allowed_tools[0]
            if "weather" in task.task_id:
                return AgentTurnOutput(
                    thought=f"My previous tool call failed with '{last_observation}'. Re-planning with canonical tool '{canonical}'.",
                    tool_name=canonical,
                    tool_args={
                        "location": "London",
                        "start_date": "03/01",
                        "end_date": "03/10",
                        "range": "2020-2020",
                    },
                )
            elif "api_request" in task.task_id:
                return AgentTurnOutput(
                    thought=f"Re-planning using canonical '{canonical}'.",
                    tool_name=canonical,
                    tool_args={
                        "apiName": "metrics-api",
                        "url": "https://api.internal",
                        "endpoint": f"/v{task.seed}/health",
                    },
                )
            elif "fs_read" in task.task_id:
                return AgentTurnOutput(
                    thought=f"Re-planning using canonical '{canonical}'.",
                    tool_name=canonical,
                    tool_args={"path": "README.md"},
                )

        # Final answer turn
        return AgentTurnOutput(
            thought="I have gathered the required observations and can now report the final answer.",
            final_answer=f"Task completed successfully for seed {task.seed}. Observations: {last_observation[:100]}",
        )
