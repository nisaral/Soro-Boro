"""In-process Kev-0.8B (Apache-2.0). Not Jev. Uses the local HF snapshot + kev.LocalPredictor."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any

if sys.platform == "win32" and "fcntl" not in sys.modules:
    sys.modules["fcntl"] = types.ModuleType("fcntl")

DEFAULT_KEV = os.environ.get(
    "SORO_KEV_PATH",
    str(Path.home() / ".cache" / "huggingface" / "hub" / "models--jaredpalmer--kev-0.8b" / "snapshots"),
)


def resolve_kev_dir(path: str | None = None) -> Path | None:
    root = Path(path or DEFAULT_KEV)
    if root.is_dir() and (root / "head.pt").exists():
        return root
    if root.is_dir():
        snaps = sorted(root.glob("*/head.pt"))
        if snaps:
            return snaps[-1].parent
    hub = Path.home() / ".cache" / "huggingface" / "hub" / "models--jaredpalmer--kev-0.8b" / "snapshots"
    snaps = sorted(hub.glob("*/head.pt"))
    return snaps[-1].parent if snaps else None


class LocalKevScorer:
    """Typed choice over a shortlist. Loads once. CPU by default."""

    def __init__(self, run: str | None = None, device: str | None = None) -> None:
        self.run = str(resolve_kev_dir(run) or "jaredpalmer/kev-0.8b")
        self.device = device or os.environ.get("SORO_KEV_DEVICE", "cpu")
        self._pred = None
        self.error: str | None = None

    def load(self) -> bool:
        if self._pred is not None:
            return True
        try:
            from kev.checkpoint import LoadOptions
            from kev.predictors import LocalPredictor

            self._pred = LocalPredictor(self.run, self.device, LoadOptions())
            return True
        except Exception as exc:
            self.error = str(exc)
            self._pred = None
            return False

    def probabilities(self, query: str, options: dict[str, str]) -> dict[str, float]:
        if not options:
            return {}
        if not self.load() or self._pred is None:
            raise RuntimeError(self.error or "kev failed to load")
        keys = list(options)
        record = {
            "state": query,
            "questions": {
                "tool": {
                    "type": "choice",
                    "instructions": "Which single tool should run for this request? Use only the listed tools.",
                    "criteria": options,
                    "label": keys[0],
                    "src": "soro_router",
                }
            },
        }
        out = self._pred(record)
        probs = (out.get("probabilities") or {}).get("tool") or {}
        return {k: float(probs.get(k, 0.0)) for k in keys}
