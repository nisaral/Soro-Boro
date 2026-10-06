"""LLM Agent Benchmark Package.

Evaluates true LLM agent execution under three tool-boundary layers:
1. RAW: Agent proposals dispatched directly to real MCP server.
2. COMPETENT_BASELINE: Standard engineering baseline (basic coercion, safe idempotent retry).
3. VEYRA: Full Veyra resolution layer (candidate resolution, multi-type coercion, provenance classification, safe retry).

Architecture:
Real LLM Agent -> proposed tool call -> System Arm -> Real MCP Server -> real observation
"""

from veyra.bench.llm_agent.agent import DeterministicSimulatedAgentDriver, LiveAgentDriver
from veyra.bench.llm_agent.harness import LLMAgentHarness, AgentArm
from veyra.bench.llm_agent.scenarios import AgentBenchmarkTask, get_llm_agent_tasks
from veyra.bench.llm_agent.runner import run_llm_agent_benchmark, LLMAgentBenchmarkResult

__all__ = [
    "LLMAgentHarness",
    "AgentArm",
    "AgentBenchmarkTask",
    "get_llm_agent_tasks",
    "run_llm_agent_benchmark",
    "LLMAgentBenchmarkResult",
    "DeterministicSimulatedAgentDriver",
    "LiveAgentDriver",
]
