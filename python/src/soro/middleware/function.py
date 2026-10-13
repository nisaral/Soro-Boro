"""Function wrapper middleware for soro."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

class FunctionWrapper:
    """Wraps Python callables with Veyra execution boundary policies and tracing."""

    def __init__(self, veyra_instance: Any, fn: Callable[..., Any], name: str | None = None, **kwargs: Any):
        self.veyra = veyra_instance
        self.fn = fn
        self.name = name or fn.__name__
        self.kwargs = kwargs
        functools.update_wrapper(self, fn)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        sig = inspect.signature(self.fn)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        proposed_args = dict(bound.arguments)
        for p_name, p in sig.parameters.items():
            if p.kind == inspect.Parameter.VAR_KEYWORD and p_name in proposed_args:
                var_kwargs = proposed_args.pop(p_name)
                if isinstance(var_kwargs, dict):
                    proposed_args.update(var_kwargs)

        return self.soro.call(
            tool_name=self.name,
            arguments=proposed_args,
            fn=self.fn,
            retryable=self.kwargs.get("retryable", False),
            idempotent=self.kwargs.get("idempotent", False),
            schema=self.kwargs.get("schema"),
        )
