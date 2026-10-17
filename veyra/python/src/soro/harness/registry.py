"""Harness discovery and construction."""

from __future__ import annotations

from typing import Any

from soro.harness.base import HarnessAdapter
from soro.harness.langgraph_harness import ENGINE, LangGraphHarness, available as langgraph_available
from soro.harness.miniswe import MiniSweHarness, available as miniswe_available
from soro.harness.native import NativeHarness
from soro.harness.repair import RepairHarness
from soro.v1 import runtime_pb2 as pb

CLASSES: dict[str, type[HarnessAdapter]] = {
    NativeHarness.id: NativeHarness,
    RepairHarness.id: RepairHarness,
    LangGraphHarness.id: LangGraphHarness,
    MiniSweHarness.id: MiniSweHarness,
}


class HarnessRegistry:
    def __init__(self, base_opts: dict[str, Any] | None = None):
        self.base_opts = dict(base_opts or {})

    def create(self, harness_id: str, opts: dict[str, Any] | None = None) -> HarnessAdapter:
        cls = CLASSES.get(harness_id)
        if cls is None:
            raise KeyError(f"unknown harness {harness_id!r}; known: {sorted(CLASSES)}")
        merged = {**self.base_opts, **(opts or {})}
        return cls(merged)

    def infos(self) -> list[pb.HarnessInfo]:
        out: list[pb.HarnessInfo] = []
        for hid, cls in CLASSES.items():
            probe = cls.__new__(cls)
            probe.opts = {}
            engine = ENGINE
            out.append(
                pb.HarnessInfo(
                    id=hid,
                    kind=cls.kind,
                    capabilities=list(getattr(probe, "capabilities", [])),
                    est_cost_usd_per_step=cls.est_cost_usd_per_step,
                    est_latency_ms=cls.est_latency_ms,
                    supports_checkpoint=cls.supports_checkpoint,
                    required_permissions=list(cls.required_permissions),
                )
            )
        return out

    def triage(self) -> list[dict[str, Any]]:
        available, detail = langgraph_available()
        mini_ok, mini_detail = miniswe_available()
        return [
            {"id": NativeHarness.id, "available": True, "detail": "built in"},
            {"id": RepairHarness.id, "available": True, "detail": "built in; diagnoses before the model call"},
            {"id": LangGraphHarness.id, "available": available, "detail": detail or "ok"},
            {"id": MiniSweHarness.id, "available": mini_ok, "detail": mini_detail},
        ]