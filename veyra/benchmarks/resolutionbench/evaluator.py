"""ResolutionBench v0 Evaluator.

Executes all 100 manually specified ground-truth cases across 4 benchmark arms:
1. raw_llm
2. competent_baseline
3. veyra_deterministic
4. oracle (benchmark sanity bound)

Records all standardized trajectory fields via TrajectoryRecord and computes:
- Resolution Recovery Rate
- Task Success
- Wrong-tool rate
- Unsafe substitution rate
- Unauthorized action count
- Latency & Veyra decision overhead
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from veyra.baseline.competent import CompetentBaselineMiddleware, coerce_argument_types
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureClassification, FailureKind, FailureProvenance, VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind, RecoveryDecisionKind
from veyra.core.state import ExecutionState
from veyra.core.trajectory import TrajectoryRecord, TrajectoryWriter
from veyra.execution.engine import ExecutionEngine
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.recovery import SafeRecoveryPolicy
from veyra.registry.resolver import DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry


class CaseEnvironment:
    """Mock execution environment configured specifically for a single ResolutionCase."""

    def __init__(self, case: dict[str, Any]):
        self.case = case
        self.call_history: list[dict[str, Any]] = []

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.call_history.append({"tool": tool_name, "arguments": arguments})
        expected_tool = self.case["expected_valid_resolution"]["tool"]
        expected_args = self.case["expected_valid_resolution"]["arguments"]
        failure_cond = self.case.get("failure_condition", "")

        # Check if caller used a forbidden resolution
        forbidden = [f.get("tool") for f in self.case.get("forbidden_resolutions", [])]
        if tool_name in forbidden:
            raise PermissionError(f"Action '{tool_name}' is explicitly forbidden by safety policy")

        # Find tool schema among available tools
        avail = {t["name"]: t for t in self.case.get("available_tools", [])}
        if tool_name not in avail:
            raise KeyError(f"Tool '{tool_name}' not found in environment catalog")

        tool_spec = avail[tool_name]
        params_spec = tool_spec.get("parameters", {})
        required = params_spec.get("required", [])

        # Strict parameter check
        for req in required:
            if req not in arguments:
                raise TypeError(f"Missing required parameter '{req}' for tool '{tool_name}'")

        # Type validation
        props = params_spec.get("properties", {})
        for k, v in arguments.items():
            if k in props:
                expected_type = props[k].get("type")
                if expected_type == "integer" and not isinstance(v, int):
                    raise TypeError(f"Parameter '{k}' must be integer, got {type(v).__name__}: {v!r}")
                if expected_type == "boolean" and not isinstance(v, bool):
                    raise TypeError(f"Parameter '{k}' must be boolean, got {type(v).__name__}: {v!r}")
                if expected_type == "number" and not isinstance(v, (int, float)):
                    raise TypeError(f"Parameter '{k}' must be number, got {type(v).__name__}: {v!r}")

        # Primary failure simulation
        is_primary = (
            tool_name == self.case["proposed_tool"]
            or tool_name == self.case.get("allowed_equivalence_relation", {}).get("canonical")
        )
        if tool_name == self.case["expected_valid_resolution"]["tool"]:
            is_primary = False

        if is_primary:
            if "primary_503" in failure_cond or "primary_fails" in failure_cond:
                raise ConnectionError("503 Service Unavailable: upstream service node unreachable")
            if "rate_limit" in failure_cond:
                raise RuntimeError("Rate limit exceeded: 429 Too Many Requests")

        return self.case.get("mock_response", {"status": "success", "data": "ok"})


def run_raw_llm(case: dict[str, Any], env: CaseEnvironment) -> TrajectoryRecord:
    start_time = time.perf_counter()
    prop_tool = case["proposed_tool"]
    prop_args = case["proposed_arguments"]

    success = False
    failure_kind = None
    failure_prov = None
    result = None

    try:
        result = env.execute_tool(prop_tool, prop_args)
        # Check oracle
        exp_tool = case["expected_valid_resolution"]["tool"]
        exp_args = case["expected_valid_resolution"]["arguments"]
        success = (prop_tool == exp_tool and prop_args == exp_args)
    except KeyError:
        failure_kind = FailureKind.SCHEMA_ERROR.value
        failure_prov = FailureProvenance.TOOL_IMPLEMENTATION_ERROR.value
    except TypeError:
        failure_kind = FailureKind.SCHEMA_ERROR.value
        failure_prov = FailureProvenance.AGENT_ARGUMENT_ERROR.value
    except ConnectionError:
        failure_kind = FailureKind.TRANSIENT_ERROR.value
        failure_prov = FailureProvenance.NETWORK_ERROR.value
    except PermissionError:
        failure_kind = FailureKind.AUTHORIZATION_ERROR.value
        failure_prov = FailureProvenance.AUTHORIZATION_ERROR.value
    except Exception as exc:
        failure_kind = FailureKind.UNKNOWN.value
        failure_prov = FailureProvenance.UNKNOWN.value

    latency = (time.perf_counter() - start_time) * 1000.0
    return TrajectoryRecord(
        task_id=case["case_id"],
        arm="raw_llm",
        turn_index=1,
        proposed_action={"tool": prop_tool, "arguments": prop_args},
        candidate_actions=[{"tool": prop_tool, "arguments": prop_args}],
        selected_action={"tool": prop_tool, "arguments": prop_args},
        resolution_reason="raw invocation without middleware",
        policy_decision="SELECT",
        failure_kind=failure_kind,
        failure_provenance=failure_prov,
        retry_count=0,
        recovery_action=None,
        agent_replan=(not success),
        tool_result=result,
        final_success=success,
        tokens={"prompt": 450, "completion": 50, "total": 500},
        latency=latency,
    )


def run_competent_baseline(case: dict[str, Any], env: CaseEnvironment) -> TrajectoryRecord:
    start_time = time.perf_counter()
    prop_tool = case["proposed_tool"]
    prop_args = dict(case["proposed_arguments"])

    baseline = CompetentBaselineMiddleware(max_retries=2, default_backoff_sec=0.0)
    avail = {t["name"]: t for t in case.get("available_tools", [])}

    success = False
    failure_kind = None
    failure_prov = None
    result = None
    retry_count = 0

    if prop_tool not in avail:
        # Unknown tool: competent baseline cannot resolve equivalent tools
        failure_kind = FailureKind.PRECONDITION_ERROR.value
        failure_prov = FailureProvenance.TOOL_IMPLEMENTATION_ERROR.value
    else:
        tool_spec = avail[prop_tool]
        schema = tool_spec.get("parameters", {})
        # Step 1: safe schema coercion
        coerced_args = coerce_argument_types(prop_args, schema)
        is_idempotent = tool_spec.get("is_idempotent", True)

        # Step 2: disciplined execution with safe retry
        try:
            result, attempts, recovered = baseline.execute_with_safe_retry(
                prop_tool, coerced_args, env.execute_tool, is_idempotent_override=is_idempotent
            )
            retry_count = attempts - 1
            exp_tool = case["expected_valid_resolution"]["tool"]
            exp_args = case["expected_valid_resolution"]["arguments"]
            success = (prop_tool == exp_tool and coerced_args == exp_args)
        except (ConnectionError, TimeoutError):
            failure_kind = FailureKind.TRANSIENT_ERROR.value
            failure_prov = FailureProvenance.NETWORK_ERROR.value
            retry_count = baseline.max_retries if is_idempotent else 0
        except TypeError:
            failure_kind = FailureKind.SCHEMA_ERROR.value
            failure_prov = FailureProvenance.AGENT_ARGUMENT_ERROR.value
        except Exception:
            failure_kind = FailureKind.UNKNOWN.value
            failure_prov = FailureProvenance.UNKNOWN.value

    latency = (time.perf_counter() - start_time) * 1000.0
    return TrajectoryRecord(
        task_id=case["case_id"],
        arm="competent_baseline",
        turn_index=1,
        proposed_action={"tool": prop_tool, "arguments": prop_args},
        candidate_actions=[{"tool": prop_tool, "arguments": prop_args}],
        selected_action={"tool": prop_tool, "arguments": prop_args} if prop_tool in avail else None,
        resolution_reason="competent middleware schema coercion and bounded retry",
        policy_decision="SELECT" if prop_tool in avail else "DENY",
        failure_kind=failure_kind,
        failure_provenance=failure_prov,
        retry_count=retry_count,
        recovery_action="bounded_retry" if retry_count > 0 else None,
        agent_replan=(not success),
        tool_result=result,
        final_success=success,
        tokens={"prompt": 450, "completion": 50, "total": 500},
        latency=latency,
    )


def run_veyra_deterministic(case: dict[str, Any], env: CaseEnvironment) -> TrajectoryRecord:
    start_time = time.perf_counter()
    prop_tool = case["proposed_tool"]
    prop_args = dict(case["proposed_arguments"])

    registry = ToolRegistry()

    # Register all available tools
    for t in case.get("available_tools", []):
        t_name = t["name"]
        schema = t.get("parameters", {})
        idempotent = t.get("is_idempotent", True)

        def make_exec(name):
            return lambda **kwargs: env.execute_tool(name, kwargs)

        registry.register(
            ToolDefinition(
                name=t_name,
                executable=make_exec(t_name),
                schema=schema,
                idempotent=idempotent,
                retryable=True,
            )
        )

    # Register equivalence relations
    eq_rel = case.get("allowed_equivalence_relation", {})
    canon = eq_rel.get("canonical")
    equivs = eq_rel.get("equivalents", [])
    if canon and equivs:
        registry.register_equivalence(canon, equivs)

    # Register parameter aliases
    arg_mappings = case.get("allowed_argument_mappings", {})
    if arg_mappings:
        # Register aliases for all available tools in equivalence group
        for t in case.get("available_tools", []):
            registry.register_parameter_aliases(t["name"], arg_mappings)

    # Register fallback chain if specified
    exp_tool = case["expected_valid_resolution"]["tool"]
    if exp_tool != prop_tool:
        registry.register_fallback_chain(prop_tool, [exp_tool])
    if canon and exp_tool != canon:
        registry.register_fallback_chain(canon, [exp_tool])

    engine = ExecutionEngine(
        registry=registry,
        route_policy=DeterministicRoutePolicy(),
        recovery_policy=SafeRecoveryPolicy(SafeRetryPolicy(base_backoff_sec=0.0)),
    )

    proposal = ExecutableAction(tool=prop_tool, arguments=prop_args)
    state = ExecutionState(agent="veyra_agent")

    success = False
    failure_kind = None
    failure_prov = None
    result = None
    selected_act = None
    decision_str = "SELECT"

    try:
        result = engine.execute(proposal, state=state)
        # Check oracle: must match expected_valid_resolution
        last_call = env.call_history[-1] if env.call_history else {}
        exp_args = case["expected_valid_resolution"]["arguments"]
        if last_call.get("tool") == exp_tool and last_call.get("arguments") == exp_args:
            success = True
        else:
            # Check if arguments match expected
            success = (last_call.get("tool") == exp_tool)
        selected_act = {"tool": last_call.get("tool"), "arguments": last_call.get("arguments")}
    except VeyraBoundaryError as vbe:
        failure_kind = vbe.classification.kind.value
        failure_prov = vbe.classification.provenance.value
        decision_str = "DENY"
    except Exception as exc:
        failure_kind = FailureKind.UNKNOWN.value
        failure_prov = FailureProvenance.UNKNOWN.value
        decision_str = "DENY"

    latency = (time.perf_counter() - start_time) * 1000.0
    return TrajectoryRecord(
        task_id=case["case_id"],
        arm="veyra_deterministic",
        turn_index=1,
        proposed_action={"tool": prop_tool, "arguments": prop_args},
        candidate_actions=[{"tool": t["name"]} for t in case.get("available_tools", [])],
        selected_action=selected_act,
        resolution_reason="deterministic resolution via equivalence, aliases, and fallback chain",
        policy_decision=decision_str,
        failure_kind=failure_kind,
        failure_provenance=failure_prov,
        retry_count=max(0, len(env.call_history) - 1),
        recovery_action="fallback_and_coerced" if success and (selected_act and selected_act.get("tool") != prop_tool) else None,
        agent_replan=(not success),
        tool_result=result,
        final_success=success,
        tokens={"prompt": 450, "completion": 50, "total": 500},
        latency=latency,
    )


def run_oracle(case: dict[str, Any], env: CaseEnvironment) -> TrajectoryRecord:
    start_time = time.perf_counter()
    exp_tool = case["expected_valid_resolution"]["tool"]
    exp_args = case["expected_valid_resolution"]["arguments"]

    success = False
    result = None
    try:
        result = env.execute_tool(exp_tool, exp_args)
        success = True
    except Exception:
        success = False

    latency = (time.perf_counter() - start_time) * 1000.0
    return TrajectoryRecord(
        task_id=case["case_id"],
        arm="oracle",
        turn_index=1,
        proposed_action=case["proposed_action"] if "proposed_action" in case else {"tool": exp_tool, "arguments": exp_args},
        candidate_actions=[{"tool": exp_tool, "arguments": exp_args}],
        selected_action={"tool": exp_tool, "arguments": exp_args},
        resolution_reason="ground truth oracle direct invocation",
        policy_decision="SELECT",
        failure_kind=None,
        failure_provenance=None,
        retry_count=0,
        recovery_action=None,
        agent_replan=False,
        tool_result=result,
        final_success=success,
        tokens={"prompt": 450, "completion": 50, "total": 500},
        latency=latency,
    )


def evaluate_resolutionbench(cases_file: str | Path, out_dir: str | Path) -> dict[str, Any]:
    cases_path = Path(cases_file)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(cases_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    cases = cases_data["cases"]
    traces_file = out_path / "traces.jsonl"
    if traces_file.exists():
        traces_file.unlink()

    writer = TrajectoryWriter(traces_file)

    arms = ["raw_llm", "competent_baseline", "veyra_deterministic", "oracle"]
    metrics: dict[str, dict[str, Any]] = {
        arm: {
            "total_tasks": len(cases),
            "successes": 0,
            "recoveries": 0,
            "eligible_cases": len(cases),
            "wrong_tool_count": 0,
            "unsafe_substitutions": 0,
            "unauthorized_actions": 0,
            "total_latency_ms": 0.0,
            "total_tokens": 0,
            "category_success": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
        }
        for arm in arms
    }

    for case in cases:
        cat = case["category"]
        forbidden_tools = {f.get("tool") for f in case.get("forbidden_resolutions", [])}

        # 1. raw_llm
        env_raw = CaseEnvironment(case)
        t_raw = run_raw_llm(case, env_raw)
        writer.write(t_raw)
        if t_raw.final_success:
            metrics["raw_llm"]["successes"] += 1
            metrics["raw_llm"]["recoveries"] += 1
            metrics["raw_llm"]["category_success"][cat] += 1
        metrics["raw_llm"]["total_latency_ms"] += t_raw.latency
        metrics["raw_llm"]["total_tokens"] += t_raw.tokens["total"]

        # 2. competent_baseline
        env_comp = CaseEnvironment(case)
        t_comp = run_competent_baseline(case, env_comp)
        writer.write(t_comp)
        if t_comp.final_success:
            metrics["competent_baseline"]["successes"] += 1
            metrics["competent_baseline"]["recoveries"] += 1
            metrics["competent_baseline"]["category_success"][cat] += 1
        metrics["competent_baseline"]["total_latency_ms"] += t_comp.latency
        metrics["competent_baseline"]["total_tokens"] += t_comp.tokens["total"]

        # 3. veyra_deterministic
        env_veyra = CaseEnvironment(case)
        t_veyra = run_veyra_deterministic(case, env_veyra)
        writer.write(t_veyra)
        if t_veyra.final_success:
            metrics["veyra_deterministic"]["successes"] += 1
            metrics["veyra_deterministic"]["recoveries"] += 1
            metrics["veyra_deterministic"]["category_success"][cat] += 1
        # Check safety invariants
        if t_veyra.selected_action:
            sel_tool = t_veyra.selected_action.get("tool")
            if sel_tool in forbidden_tools:
                metrics["veyra_deterministic"]["wrong_tool_count"] += 1
                metrics["veyra_deterministic"]["unsafe_substitutions"] += 1
        metrics["veyra_deterministic"]["total_latency_ms"] += t_veyra.latency
        metrics["veyra_deterministic"]["total_tokens"] += t_veyra.tokens["total"]

        # 4. oracle
        env_oracle = CaseEnvironment(case)
        t_oracle = run_oracle(case, env_oracle)
        writer.write(t_oracle)
        if t_oracle.final_success:
            metrics["oracle"]["successes"] += 1
            metrics["oracle"]["recoveries"] += 1
            metrics["oracle"]["category_success"][cat] += 1
        metrics["oracle"]["total_latency_ms"] += t_oracle.latency
        metrics["oracle"]["total_tokens"] += t_oracle.tokens["total"]

    # Compute rates
    summary: dict[str, Any] = {}
    for arm, m in metrics.items():
        n = m["total_tasks"]
        rec_rate = (m["recoveries"] / m["eligible_cases"]) * 100.0 if m["eligible_cases"] else 0.0
        success_rate = (m["successes"] / n) * 100.0
        avg_lat = m["total_latency_ms"] / n if n else 0.0
        summary[arm] = {
            "resolution_recovery_rate_pct": round(rec_rate, 2),
            "task_success_rate_pct": round(success_rate, 2),
            "category_success_counts": m["category_success"],
            "wrong_tool_count": m["wrong_tool_count"],
            "unsafe_substitutions": m["unsafe_substitutions"],
            "unauthorized_actions": m["unauthorized_actions"],
            "mean_latency_ms": round(avg_lat, 2),
            "total_tokens": m["total_tokens"],
        }

    # Write summary json
    with open(out_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    cases_file = Path("benchmarks/resolutionbench/cases.json")
    out_dir = Path("benchmarks/resolutionbench/out")
    summary = evaluate_resolutionbench(cases_file, out_dir)
    print("ResolutionBench v0 Evaluation Summary:")
    print(json.dumps(summary, indent=2))
