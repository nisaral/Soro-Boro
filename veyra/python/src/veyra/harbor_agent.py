"""Harbor custom agent: Veyra as an *external* loop.

Harbor loads this with::

    harbor run -d terminal-bench@2.0 -a veyra.harbor_agent:VeyraHarborAgent

The class subclasses Harbor's BaseAgent when ``harbor`` is installed. Without
Harbor, it is still importable so the rest of the package and tests stay green.

This agent does not reimplement Terminus-2. It execs through BaseEnvironment
and fails open (continues) if the controller raises. Shadow mode logs a
would-have-switched HandoffV1 without changing the environment.
"""

from __future__ import annotations

from typing import Any

import logging
from pathlib import Path
from typing import Any, Mapping

try:
    from pydantic import BaseModel, Field
    _HAS_PYDANTIC = True
except ImportError:
    BaseModel = object  # type: ignore
    Field = lambda **kwargs: None  # type: ignore
    _HAS_PYDANTIC = False

try:
    from harbor.agents.base import BaseAgent  # type: ignore
    from harbor.environments.base import BaseEnvironment  # type: ignore
    from harbor.models.agent.context import AgentContext  # type: ignore
    _HAS_HARBOR = True
except ImportError:  # Harbor is optional until a paid eval.
    class BaseAgent:  # type: ignore[no-redef]
        options_model = None

        def __init__(
            self,
            logs_dir: Path | str | None = None,
            model_name: str | None = None,
            logger: logging.Logger | None = None,
            **kwargs: Any,
        ) -> None:
            self.logs_dir = Path(logs_dir) if logs_dir is not None else Path(".")
            self.model_name = model_name
            self.logger = logger
            self._extra_env: dict[str, str] = {}
            self.kwargs = kwargs

        @classmethod
        def parse_options(cls, kwargs: dict[str, Any] | None = None, env: Mapping[str, str] | None = None) -> Any:
            return None

        @classmethod
        def options_schema(cls) -> dict[str, Any]:
            return {}

        def to_agent_info(self) -> Any:
            return {"name": self.name(), "version": self.version(), "model": self.model_name}

    class BaseEnvironment:  # type: ignore[no-redef]
        pass

    class AgentContext:  # type: ignore[no-redef]
        def __init__(self, metadata: dict[str, Any] | None = None) -> None:
            self.metadata = metadata or {}

    _HAS_HARBOR = False


if _HAS_PYDANTIC:
    class VeyraOptions(BaseModel):
        shadow: bool = Field(default=True, description="Shadow mode: record HandoffV1 without modifying environment")
        backend: str = Field(default="heuristic", description="Decision backend to use")
else:
    class VeyraOptions:  # type: ignore
        pass


class VeyraHarborAgent(BaseAgent):
    options_model = VeyraOptions if _HAS_PYDANTIC else None

    def __init__(
        self,
        logs_dir: Path | str | None = None,
        model_name: str | None = None,
        shadow: bool = True,
        **kwargs: Any,
    ):
        p_logs = Path(logs_dir) if logs_dir is not None else Path(".")
        if _HAS_HARBOR:
            super().__init__(logs_dir=p_logs, model_name=model_name, **kwargs)
        else:
            self.logs_dir = p_logs
            self.model_name = model_name
            self.kwargs = kwargs
            self._extra_env = {}

        if hasattr(self, "options") and self.options and hasattr(self.options, "shadow"):
            self.shadow = self.options.shadow
        else:
            self.shadow = shadow

    @staticmethod
    def name() -> str:
        return "veyra"

    def version(self) -> str | None:
        from veyra import __version__

        return __version__

    async def setup(self, environment: BaseEnvironment | Any) -> None:
        return None

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment | Any,
        context: AgentContext | Any = None,
    ) -> None:
        """Fail-open: environment work happens even if the controller errors."""
        try:
            from veyra.handoff import shadow_record

            if self.shadow:
                shadow_record(instruction, reason="harbor-agent-shadow")
                if context is not None and hasattr(context, "metadata"):
                    if context.metadata is None:
                        context.metadata = {}
                    context.metadata["veyra_shadow"] = True
        except Exception:
            pass

        exec_fn = getattr(environment, "exec", None)
        if callable(exec_fn):
            result = exec_fn(instruction)
            if hasattr(result, "__await__"):
                await result
