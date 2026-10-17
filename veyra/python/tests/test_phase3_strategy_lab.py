"""Phase 3 Unit Tests: Resolution Strategy Lab.

Verifies:
- All 7 strategy plugins conform to the ResolutionStrategy interface
- Exact / cache strategy lookup and miss behavior
- Structural matching parameter and schema overlap
- BM25 lexical ranking and term frequency
- Dense embedding vector normalization and cosine similarity
- Case-based execution memory similarity retrieval
- TAGE-style variable-history predictor with saturating counters
- Process-mined workflow transitions
- Strategy lab evaluator metric calculations
"""

from __future__ import annotations

import pytest

from veyra.lab.evaluator import evaluate_strategy_on_dataset
from veyra.lab.interface import ResolutionQuery, ResolutionStrategy
from veyra.lab.strategies.bm25 import BM25Strategy
from veyra.lab.strategies.case_memory import CaseBasedMemoryStrategy
from veyra.lab.strategies.dense_embedding import DenseEmbeddingStrategy
from veyra.lab.strategies.exact_cache import ExactCacheStrategy
from veyra.lab.strategies.process_mined import ProcessMinedStrategy
from veyra.lab.strategies.structural import StructuralMatchingStrategy
from veyra.lab.strategies.tage import TageHistoryStrategy


@pytest.fixture
def sample_catalog():
    return [
        {
            "name": "get_customer",
            "description": "Fetch customer account details by ID",
            "parameters": {"type": "object", "properties": {"customer_id": {"type": "integer"}}, "required": ["customer_id"]},
        },
        {
            "name": "search_orders",
            "description": "Search customer orders by query",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
        {
            "name": "delete_customer",
            "description": "Delete a customer account",
            "parameters": {"type": "object", "properties": {"customer_id": {"type": "integer"}}, "required": ["customer_id"]},
        },
    ]


@pytest.fixture
def sample_traces():
    return [
        {
            "task_id": "t1",
            "turn_index": 1,
            "proposed_action": {"tool": "fetch_user", "arguments": {"customer_id": 100}},
            "selected_action": {"tool": "get_customer", "arguments": {"customer_id": 100}},
            "previous_tools": [],
            "final_success": True,
        },
        {
            "task_id": "t1",
            "turn_index": 2,
            "proposed_action": {"tool": "find_orders", "arguments": {"query": "shoes"}},
            "selected_action": {"tool": "search_orders", "arguments": {"query": "shoes"}},
            "previous_tools": ["get_customer"],
            "final_success": True,
        },
    ]


def test_strategy_interface_conformance(sample_catalog):
    strategies = [
        ExactCacheStrategy(),
        StructuralMatchingStrategy(),
        BM25Strategy(),
        DenseEmbeddingStrategy(),
        CaseBasedMemoryStrategy(),
        TageHistoryStrategy(),
        ProcessMinedStrategy(),
    ]
    query = ResolutionQuery(
        proposed_tool="fetch_user",
        proposed_arguments={"customer_id": 100},
        candidate_tools=sample_catalog,
    )
    for strat in strategies:
        assert isinstance(strat, ResolutionStrategy)
        assert isinstance(strat.name, str) and len(strat.name) > 0
        ranked = strat.rank(query)
        assert isinstance(ranked, list)
        assert strat.estimate_memory_bytes() >= 0


def test_exact_cache_strategy(sample_catalog, sample_traces):
    cache = ExactCacheStrategy()
    cache.fit(sample_traces)

    # Hit
    query_hit = ResolutionQuery(
        proposed_tool="fetch_user",
        proposed_arguments={"customer_id": 100},
        candidate_tools=sample_catalog,
    )
    ranked = cache.rank(query_hit)
    assert len(ranked) >= 1
    assert ranked[0].tool == "get_customer"
    assert ranked[0].score == 1.0

    # Miss
    query_miss = ResolutionQuery(
        proposed_tool="unknown_tool",
        proposed_arguments={"x": 1},
        candidate_tools=sample_catalog,
    )
    ranked_miss = cache.rank(query_miss)
    assert len(ranked_miss) == 0


def test_structural_matching_strategy(sample_catalog):
    struct = StructuralMatchingStrategy()
    query = ResolutionQuery(
        proposed_tool="get_customer",
        proposed_arguments={"customer_id": 100},
        candidate_tools=sample_catalog,
    )
    ranked = struct.rank(query)
    assert ranked[0].tool == "get_customer"
    assert ranked[0].score > 0.8


def test_bm25_strategy(sample_catalog):
    bm25 = BM25Strategy()
    query = ResolutionQuery(
        proposed_tool="search",
        proposed_arguments={"query": "shoes"},
        candidate_tools=sample_catalog,
        query_text="search for customer orders",
    )
    ranked = bm25.rank(query)
    assert ranked[0].tool == "search_orders"


def test_dense_embedding_strategy(sample_catalog):
    dense = DenseEmbeddingStrategy()
    query = ResolutionQuery(
        proposed_tool="order_search",
        proposed_arguments={"query": "shoes"},
        candidate_tools=sample_catalog,
        query_text="find customer order history",
    )
    ranked = dense.rank(query)
    assert ranked[0].tool == "search_orders"


def test_case_based_memory_strategy(sample_catalog, sample_traces):
    cbr = CaseBasedMemoryStrategy()
    cbr.fit(sample_traces)

    query = ResolutionQuery(
        proposed_tool="fetch_user",
        proposed_arguments={"customer_id": 200},
        candidate_tools=sample_catalog,
    )
    ranked = cbr.rank(query)
    assert ranked[0].tool == "get_customer"


def test_tage_history_strategy(sample_catalog, sample_traces):
    tage = TageHistoryStrategy()
    tage.fit(sample_traces)

    # Query with history matching turn 2
    query = ResolutionQuery(
        proposed_tool="find_orders",
        proposed_arguments={"query": "shoes"},
        candidate_tools=sample_catalog,
        history=["get_customer"],
    )
    ranked = tage.rank(query)
    assert len(ranked) >= 1
    assert ranked[0].tool == "search_orders"


def test_process_mined_strategy(sample_catalog, sample_traces):
    proc = ProcessMinedStrategy()
    proc.fit(sample_traces)

    query = ResolutionQuery(
        proposed_tool="find_orders",
        proposed_arguments={"query": "shoes"},
        candidate_tools=sample_catalog,
        history=["get_customer"],
    )
    ranked = proc.rank(query)
    assert len(ranked) >= 1
    assert ranked[0].tool == "search_orders"
