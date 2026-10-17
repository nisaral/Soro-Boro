"""Agent wrapper middleware for generic AI agent runtimes."""

from __future__ import annotations

from typing import Any, Callable

class AgentWrapper:
    """Wraps an AI agent instance to interpose Veyra execution control."""

    def __init__(self, veyra_instance: Any, agent: Any):
        self.veyra = veyra_instance
        self.agent = agent

    def run(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.agent, "run"):
            return self.agent.run(*args, **kwargs)
        elif callable(self.agent):
            return self.agent(*args, **kwargs)
        raise AttributeError("Wrapped agent object is neither callable nor possesses a .run() method.")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.run(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.agent, name)
