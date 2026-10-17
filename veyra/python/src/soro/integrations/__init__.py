"""First-party framework integrations for OpenAI Agents SDK, LangGraph, AutoGen, and Microsoft Agent Framework."""

from soro.integrations.openai_agents import VeyraOpenAIAgentsAdapter
from soro.integrations.langgraph import VeyraLangGraphNode
from soro.integrations.autogen import VeyraAutoGenAdapter
from soro.integrations.microsoft_agent_framework import VeyraMicrosoftAgentMiddleware

__all__ = [
    "VeyraOpenAIAgentsAdapter",
    "VeyraLangGraphNode",
    "VeyraAutoGenAdapter",
    "VeyraMicrosoftAgentMiddleware",
]
