"""Veyra Strategy Lab: Offline Benchmark Evaluator (Phase 3 Specification).

Evaluates and compares the 7 resolution strategies offline:
1. exact/cache
2. structural matching
3. BM25
4. dense embedding
5. case-based execution memory
6. TAGE-style variable-history policy
7. process-mined routing

Computes standard ranking & operational metrics:
- Recall@1
- Recall@3
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- wrong_tool_rate
- deferral_rate
- coverage
- latency (ms)
- memory footprint (KB)
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from soro.lab.interface import ResolutionQuery, ResolutionStrategy, StrategyMetrics
from soro.lab.strategies.bm25 import BM25Strategy
from soro.lab.strategies.case_memory import CaseBasedMemoryStrategy
from soro.lab.strategies.dense_embedding import DenseEmbeddingStrategy
from soro.lab.strategies.exact_cache import ExactCacheStrategy
from soro.lab.strategies.process_mined import ProcessMinedStrategy
from soro.lab.strategies.structural import StructuralMatchingStrategy
from soro.lab.strategies.tage import TageHistoryStrategy


def evaluate_strategy_on_dataset(
    strategy: ResolutionStrategy,
    cases: list[dict[str, Any]],
    training_traces: list[dict[str, Any]] | None = None,
    deferral_threshold: float = 0.40,
) -> StrategyMetrics:
    """Evaluate a single strategy plugin across all test cases."""
    if training_traces:
        strategy.fit(training_traces)

    total_queries = len(cases)
    r1_hits = 0
    r3_hits = 0
    mrr_sum = 0.0
    ndcg_sum = 0.0
    wrong_tool_count = 0
    deferred_count = 0
    covered_count = 0
    latencies = []

    for case in cases:
        target_tool = case["expected_valid_resolution"]["tool"]
        forbidden_tools = {f.get("tool") for f in case.get("forbidden_resolutions", [])}

        query = ResolutionQuery(
            proposed_tool=case["proposed_tool"],
            proposed_arguments=case["proposed_arguments"],
            candidate_tools=case.get("available_tools", []),
            history=[case.get("previous_tool")] if case.get("previous_tool") else [],
            query_text=case.get("instruction", ""),
        )

        t0 = time.perf_counter()
        ranked = strategy.rank(query, top_k=5)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt_ms)

        if ranked and ranked[0].score > 0.0:
            covered_count += 1

        # Check deferral
        top_conf = ranked[0].confidence if ranked else 0.0
        if not ranked or top_conf < deferral_threshold:
            deferred_count += 1

        # Check wrong tool
        if ranked and ranked[0].tool in forbidden_tools:
            wrong_tool_count += 1

        # Ranking metrics
        tools_ranked = [r.tool for r in ranked]
        if target_tool in tools_ranked:
            rank_idx = tools_ranked.index(target_tool) + 1  # 1-based rank
            if rank_idx == 1:
                r1_hits += 1
            if rank_idx <= 3:
                r3_hits += 1
            mrr_sum += 1.0 / rank_idx
            ndcg_sum += 1.0 / math.log2(rank_idx + 1.0)

    n = max(1, total_queries)
    return StrategyMetrics(
        strategy_name=strategy.name,
        recall_at_1=r1_hits / n,
        recall_at_3=r3_hits / n,
        mrr=mrr_sum / n,
        ndcg=ndcg_sum / n,
        wrong_tool_rate=wrong_tool_count / n,
        deferral_rate=deferred_count / n,
        coverage=covered_count / n,
        mean_latency_ms=sum(latencies) / n,
        memory_footprint_bytes=strategy.estimate_memory_bytes(),
    )


def run_strategy_lab_benchmark(
    cases_path: str | Path = "benchmarks/resolutionbench/cases.json",
    traces_path: str | Path = "benchmarks/resolutionbench/out/traces.jsonl",
    out_path: str | Path = "benchmarks/resolutionbench/out/strategy_lab_summary.json",
) -> list[dict[str, Any]]:
    """Run comparative evaluation of all 7 required offline resolution strategies."""
    with open(cases_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)
    cases = cases_data["cases"]

    # Load historical successful traces for fitting
    training_traces: list[dict[str, Any]] = []
    t_path = Path(traces_path)
    if t_path.exists():
        with open(t_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    training_traces.append(json.loads(line))

    strategies: list[ResolutionStrategy] = [
        ExactCacheStrategy(),
        StructuralMatchingStrategy(),
        BM25Strategy(),
        DenseEmbeddingStrategy(),
        CaseBasedMemoryStrategy(),
        TageHistoryStrategy(),
        ProcessMinedStrategy(),
    ]

    results = []
    print(f"=== Veyra Strategy Lab: Evaluating {len(strategies)} Strategies across {len(cases)} Cases ===")

    for strat in strategies:
        metrics = evaluate_strategy_on_dataset(strat, cases, training_traces)
        results.append(metrics.to_dict())
        print(f"[{metrics.strategy_name:22s}] R@1: {metrics.recall_at_1:.2f} | R@3: {metrics.recall_at_3:.2f} | MRR: {metrics.mrr:.2f} | Latency: {metrics.mean_latency_ms:.3f}ms | Mem: {metrics.memory_footprint_bytes/1024:.1f}KB")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"benchmark": "ResolutionStrategyLab", "results": results}, f, indent=2)

    return results


if __name__ == "__main__":
    run_strategy_lab_benchmark()
