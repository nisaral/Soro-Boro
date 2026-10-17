"""Unit tests for Phase 10: Productization (EquivalenceConfig, Plugins, Trace Export)."""

import json
from pathlib import Path
import pytest

from veyra import (
    EquivalenceConfig,
    ExecutableAction,
    ExecutionState,
    PolicyPluginRegistry,
    RoutePolicy,
    StructuredTraceExporter,
    ToolDefinition,
    ToolRegistry,
    TrajectoryRecord,
    Veyra,
    load_equivalence_config,
)


def test_equivalence_config_parsing_yaml():
    """Verify loading declarative equivalence config from YAML."""
    yaml_content = """
version: "1.0"
capabilities:
  customer_ops:
    tools:
      - fetch_customer
      - get_customer
    primary_tool: fetch_customer
    parameter_aliases:
      fetch_customer:
        id: customer_id
      get_customer:
        id: customer_id
    fallbacks:
      fetch_customer:
        - get_customer
    idempotent: true
    risk_class: low
"""
    cfg = load_equivalence_config(yaml_content)
    assert cfg.version == "1.0"
    assert len(cfg.capabilities) == 1

    cap = cfg.capabilities[0]
    assert cap.name == "customer_ops"
    assert cap.primary_tool == "fetch_customer"
    assert "get_customer" in cap.tools
    assert cap.idempotent is True
    assert cap.fallback_chains["fetch_customer"] == ["get_customer"]


def test_equivalence_config_apply_to_registry():
    """Verify applying EquivalenceConfig to a ToolRegistry."""
    cfg_data = {
        "version": "1.0",
        "capabilities": {
            "search_capability": {
                "tools": ["primary_search", "backup_search"],
                "primary_tool": "primary_search",
                "parameter_aliases": {
                    "query": ["q", "search_term"],
                },
                "fallbacks": {
                    "primary_search": ["backup_search"],
                },
                "idempotent": True,
            }
        },
    }
    cfg = EquivalenceConfig.from_dict(cfg_data)
    registry = ToolRegistry()
    cfg.apply_to_registry(registry)

    # 1. Tools registered
    assert registry.has("primary_search")
    assert registry.has("backup_search")

    # 2. Equivalence registered
    equivs = registry.get_equivalents("primary_search")
    assert "backup_search" in equivs

    # 3. Fallbacks registered
    fallbacks = registry.get_fallback_chain("primary_search")
    assert fallbacks == ["backup_search"]

    # 4. Aliases registered
    aliases = registry.get_parameter_aliases("primary_search")
    assert aliases.get("q") == "query"
    assert aliases.get("search_term") == "query"


def test_structured_trace_exporter(tmp_path):
    """Verify StructuredTraceExporter exports JSONL, OTel spans, and metrics."""
    rec1 = TrajectoryRecord(
        task_id="task_1",
        arm="veyra",
        turn_index=1,
        proposed_action={"tool": "search_db", "arguments": {"q": "test"}},
        candidate_actions=[{"tool": "search_db"}],
        selected_action={"tool": "search_db", "arguments": {"query": "test"}},
        resolution_reason="resolved parameter alias",
        policy_decision="SELECT",
        failure_kind=None,
        failure_provenance=None,
        retry_count=0,
        recovery_action=None,
        agent_replan=False,
        tool_result={"count": 5},
        final_success=True,
        tokens={"prompt": 200, "completion": 50, "total": 250},
        latency=0.012,
    )

    rec2 = TrajectoryRecord(
        task_id="task_2",
        arm="competent_baseline",
        turn_index=1,
        proposed_action={"tool": "broken_op", "arguments": {}},
        candidate_actions=[],
        selected_action=None,
        resolution_reason="precondition failed",
        policy_decision="DENY",
        failure_kind="precondition_error",
        failure_provenance="PRECONDITION_ERROR",
        retry_count=0,
        recovery_action=None,
        agent_replan=True,
        tool_result=None,
        final_success=False,
        tokens={"prompt": 300, "completion": 50, "total": 350},
        latency=0.005,
    )

    exporter = StructuredTraceExporter([rec1, rec2])

    # 1. Export JSONL
    out_file = tmp_path / "traces.jsonl"
    exporter.export_jsonl(out_file)
    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # 2. Export OTel Spans
    spans = exporter.export_otel_spans()
    assert len(spans) == 2
    assert spans[0]["name"] in ("soro.resolution/search_db", "veyra.resolution/search_db")
    assert spans[0]["status"]["code"] == "OK"
    assert spans[1]["status"]["code"] == "ERROR"

    # 3. Summary metrics
    metrics = exporter.compute_summary_metrics()
    assert metrics["total_records"] == 2
    assert metrics["success_count"] == 1
    assert metrics["success_rate"] == 0.5
    assert metrics["replan_count"] == 1
    assert metrics["total_tokens"] == 600
    assert metrics["failure_provenance_breakdown"]["PRECONDITION_ERROR"] == 1


def test_policy_plugin_registry():
    """Verify listing and instantiating built-in and custom policy plugins."""
    plugins = PolicyPluginRegistry()

    # Built-in plugins
    builtins = plugins.list_plugins()
    for name in ["deterministic", "tage", "reliability", "selective", "bandit"]:
        assert name in builtins

    p_det = plugins.get("deterministic")
    assert isinstance(p_det, RoutePolicy)

    p_tage = plugins.get("tage")
    assert isinstance(p_tage, RoutePolicy)

    # Custom plugin registration
    class CustomPolicy(RoutePolicy):
        def resolve(self, state, candidates):
            from veyra.core.decision import Decision
            return Decision.deny("custom denial")

    plugins.register("custom_deny", lambda **kw: CustomPolicy())
    assert "custom_deny" in plugins.list_plugins()
    p_cust = plugins.get("custom_deny")
    assert isinstance(p_cust, CustomPolicy)


def test_end_to_end_declarative_resolution():
    """Verify full end-to-end Veyra resolution configured purely via EquivalenceConfig."""
    yaml_config = """
version: "1.0"
capabilities:
  customer_fetch:
    tools:
      - fetch_customer_primary
      - fetch_customer_backup
    primary_tool: fetch_customer_primary
    parameter_aliases:
      fetch_customer_primary:
        cid: customer_id
      fetch_customer_backup:
        cid: customer_id
    fallbacks:
      fetch_customer_primary:
        - fetch_customer_backup
    idempotent: true
"""
    cfg = load_equivalence_config(yaml_config)
    registry = ToolRegistry()
    cfg.apply_to_registry(registry)

    # Register executable for backup tool
    calls = []
    def backup_impl(customer_id: int):
        calls.append(customer_id)
        return {"status": "ok", "user": f"User_{customer_id}"}

    registry.register(
        ToolDefinition(
            name="fetch_customer_backup",
            executable=backup_impl,
            idempotent=True,
        )
    )

    # Veyra boundary with this registry
    veyra = Veyra(registry=registry)

    # Agent proposes primary with aliased parameter "cid" (as string "1001")
    # Primary fails (or is unexecutable), Veyra cascades to backup with repaired arg!
    res = veyra.call(
        tool_name="fetch_customer_primary",
        arguments={"cid": 1001},
        idempotent=True,
    )
    assert res["status"] == "ok"
    assert res["user"] == "User_1001"
    assert calls == [1001]
