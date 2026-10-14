"""Harness adapters and unified Soro pipeline."""

from soro.harness.pipeline import SoroHarness

__all__ = ["SoroHarness", "HarnessAdapter", "HarnessError"]


def __getattr__(name: str):
    if name in ("HarnessAdapter", "HarnessError"):
        from soro.harness.base import HarnessAdapter, HarnessError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")