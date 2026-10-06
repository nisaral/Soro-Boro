"""Tests for Real MCP Catalogs Validation (Milestone V0.1 -> V0.2).

Validates:
1. Loading 3 real MCP environments (Filesystem, Database, API Services).
2. Transparent boundary execution on real FastMCP tools.
3. 4-way comparative evaluation.
4. Exact reproduction denominator tracking.
5. Invariant: 0 unsafe retries on real non-idempotent operations.
"""

import pytest
from veyra.bench.mcp_real.catalogs import RealMCPCatalogManager
from veyra.bench.mcp_real.runner import RealMCPArm, run_real_mcp_benchmark
from veyra.bench.mcp_real.scenarios import get_real_mcp_scenarios


class TestRealMCPCatalogsBenchmark:
    @pytest.fixture(scope="class")
    def catalog_mgr(self):
        return RealMCPCatalogManager()

    def test_catalogs_loading(self, catalog_mgr):
        tools = catalog_mgr.list_tools()
        tool_names = {t.name for t in tools}
        assert "search_and_read_files" in tool_names
        assert "patch_file" in tool_names
        assert "connect_database" in tool_names
        assert "Connect_SQL_Server" in tool_names
        assert "make_api_request" in tool_names
        assert "weather_data_retriever" in tool_names

        # Verify catalogs
        catalogs = {t.catalog for t in tools}
        assert catalogs == {"filesystem", "database", "api"}

    def test_run_real_mcp_benchmark_comparative_arms(self, catalog_mgr):
        scenarios = get_real_mcp_scenarios()
        results = run_real_mcp_benchmark(scenarios=scenarios, catalog_mgr=catalog_mgr)

        assert RealMCPArm.RAW_AGENT.value in results
        assert RealMCPArm.NAIVE_RETRY.value in results
        assert RealMCPArm.STRUCTURED_FEEDBACK.value in results
        assert RealMCPArm.VEYRA.value in results

        raw = results[RealMCPArm.RAW_AGENT.value]
        naive = results[RealMCPArm.NAIVE_RETRY.value]
        feedback = results[RealMCPArm.STRUCTURED_FEEDBACK.value]
        veyra = results[RealMCPArm.VEYRA.value]

        # Veyra beats raw agent substantially
        assert veyra.task_success_rate > raw.task_success_rate
        assert veyra.task_success_count >= 25
        assert veyra.agent_replans < raw.agent_replans

        # Critical Safety Invariant: 0 unsafe retries for Veyra
        assert veyra.unsafe_retries == 0
        assert veyra.harmful_interventions == 0

        # Naive retry must have recorded unsafe retries on non-idempotent writes
        assert naive.unsafe_retries > 0

        # Exact denominator reproducibility
        assert veyra.eligible_injected_failures == 16
        assert veyra.successful_safe_recoveries == 16
        assert veyra.boundary_recovery_rate == 100.0
        assert veyra.non_recoverable_failures == 14
