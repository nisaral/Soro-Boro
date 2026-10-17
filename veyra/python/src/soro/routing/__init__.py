"""Routing package. Heavy imports stay lazy so training can load conformal without soro.core."""

__all__ = ["ScaleRouter", "ToolSpec", "describe_hash"]


def __getattr__(name: str):
    if name in __all__:
        from soro.routing.scale import ScaleRouter, ToolSpec, describe_hash

        return {"ScaleRouter": ScaleRouter, "ToolSpec": ToolSpec, "describe_hash": describe_hash}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
