"""Example 3: Adaptive History (TAGE) and Beta-Bernoulli Health Tracking.

Demonstrates Veyra's lightweight, zero-LLM adaptive execution layer:
1. Online Execution Memory records successful resolutions.
2. TAGE-style multi-history predictor with 3-bit saturating counters (H0, H1, H2, H4, H8).
3. Beta-Bernoulli conjugate reliability updates track real-time tool health.
4. Dynamically chooses the healthiest candidate within the declared equivalence set.
"""

import sys
from pathlib import Path

# Add python/src to sys.path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from veyra import (
    AdaptiveHistoryRoutePolicy,
    ExecutableAction,
    ExecutionState,
    OnlineExecutionMemory,
    ReliabilityAwareRoutePolicy,
    ToolDefinition,
    ToolRegistry,
    ToolReliabilityTracker,
    Veyra,
)


def main():
    print("--- 1. TAGE Multi-History Adaptive Learning ---")
    memory = OnlineExecutionMemory(history_lengths=[0, 1, 2, 4, 8])
    tage_policy = AdaptiveHistoryRoutePolicy(memory=memory)

    state = ExecutionState(history=["login", "authenticate"])
    cand_primary = ExecutableAction(tool="endpoint_v1", arguments={"token": "abc"})
    cand_replica = ExecutableAction(tool="endpoint_v2", arguments={"token": "abc"})

    # Prior to learning: neutral selection
    dec_initial = tage_policy.resolve(state, [cand_primary, cand_replica])
    print(f"Initial policy decision: {dec_initial.action.tool} ({dec_initial.reason})")

    # Record successful executions of endpoint_v2 under this context
    trace = {
        "proposal": {"tool": "endpoint_v1", "arguments": {"token": "abc"}},
        "resolved_tool": "endpoint_v2",
        "outcome": "success",
        "previous_tools": ["login", "authenticate"],
    }
    # Observe successful traces to train saturating counters
    for _ in range(4):
        memory.observe(trace)

    dec_learned = tage_policy.resolve(state, [cand_primary, cand_replica])
    print(f"Learned policy decision: {dec_learned.action.tool} ({dec_learned.reason})")

    print("\n--- 2. Beta-Bernoulli Conjugate Tool Health Tracking ---")
    tracker = ToolReliabilityTracker()

    stats_a = tracker.get_or_create("api_server_a")
    stats_b = tracker.get_or_create("api_server_b")

    # Tool A suffers consecutive rate limits and timeouts
    stats_a.observe(success=False, latency_ms=2500.0, provenance="RATE_LIMIT")
    stats_a.observe(success=False, latency_ms=5000.0, provenance="TIMEOUT")

    # Tool B executes reliably
    stats_b.observe(success=True, latency_ms=80.0)
    stats_b.observe(success=True, latency_ms=70.0)

    print(f"api_server_a: Beta({stats_a.alpha_prior + stats_a.success_count:.1f}, {stats_a.beta_prior + stats_a.failure_count:.1f}) -> Mean: {stats_a.beta_mean:.2%}, RateLimit: {stats_a.rate_limit_rate:.1%}")
    print(f"api_server_b: Beta({stats_b.alpha_prior + stats_b.success_count:.1f}, {stats_b.beta_prior + stats_b.failure_count:.1f}) -> Mean: {stats_b.beta_mean:.2%}, RateLimit: {stats_b.rate_limit_rate:.1%}")

    rel_policy = ReliabilityAwareRoutePolicy(tracker=tracker)
    cand_a = ExecutableAction(tool="api_server_a")
    cand_b = ExecutableAction(tool="api_server_b")

    health_decision = rel_policy.resolve(state, [cand_a, cand_b])
    print(f"Health-aware resolution chooses: {health_decision.action.tool} ({health_decision.reason})")


if __name__ == "__main__":
    main()
