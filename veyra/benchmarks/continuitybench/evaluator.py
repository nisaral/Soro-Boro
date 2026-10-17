"""ContinuityBench Evaluator (Phase 13, 15, 17, 18, 19 Specification).

Implements paired perturbation evaluation:
CLEAN: agent -> intended tool -> execution
PERTURBED: same agent, task, seed, prompt, but intended tool path is perturbed.

Evaluates:
1. raw_agent
2. competent_boundary
3. static_resolution
4. veyra (and oracle)

Computes:
- Intent Preservation Rate (IPR)
- Perturbation Recovery Rate
- Clean vs Perturbed Degradation (Delta)
- Replan Rate
- Wrong Tool Rate
- Unsafe Substitution Rate (0 tolerance invariant)
- Unauthorized Action Rate (0 tolerance invariant)
- Resolution Latency Overhead (ms)

Evaluates on the strictly held-out SCORECARD split (Phase 16 & 22).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from benchmarks.continuitybench.schema import ContinuityTask, ExecutionContractSpec, GeneralizationSplit, ToolSpec
from veyra.baseline.competent import CompetentBaselineMiddleware
from veyra.baseline.static_resolution import StaticResolutionMiddleware
from veyra.boundary.taxonomy import VeyraBoundaryError
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.state import ExecutionState
from veyra.core.trajectory import TrajectoryRecord, TrajectoryWriter
from veyra.policy.deterministic import DeterministicRoutePolicy
from veyra.policy.history_adaptive import AdaptiveHistoryRoutePolicy, OnlineExecutionMemory
from veyra.policy.reliability import ReliabilityAwareRoutePolicy, ToolReliabilityTracker
from veyra.registry.resolver import DeterministicCandidateResolver
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.boundary.interceptor import Veyra


def build_harness_for_task(task: ContinuityTask, is_perturbed: bool):
    """Instantiates a ToolRegistry with mock implementations matching task specs."""
    registry = ToolRegistry()
    calls: list[str] = []

    for t_spec in task.tools:
        def make_impl(spec=t_spec):
            def tool_fn(**kwargs):
                calls.append(spec.name)
                # In clean run, primary tool succeeds
                if not is_perturbed and spec.name == task.intended_tool:
                    return {"status": "ok", "source": spec.name, "freshness_sec": spec.freshness_sec}

                # In perturbed run, inject failure if specified
                if is_perturbed and spec.failure_type:
                    if spec.failure_type == "timeout":
                        raise TimeoutError(f"Connection timeout to {spec.name}")
                    elif spec.failure_type == "rate_limit":
                        raise ConnectionResetError(f"HTTP 429 Rate limit exceeded on {spec.name}")
                    elif spec.failure_type == "schema_drift":
                        raise TypeError(f"Schema mismatch on {spec.name}")
                    elif spec.failure_type == "unavailable":
                        raise ConnectionRefusedError(f"Endpoint {spec.name} unavailable")
                    else:
                        raise RuntimeError(f"Service error on {spec.name}")

                return {"status": "ok", "source": spec.name, "freshness_sec": spec.freshness_sec}

            return tool_fn

        t_def = ToolDefinition(
            name=t_spec.name,
            schema=t_spec.schema,
            executable=make_impl(),
            idempotent=t_spec.idempotent,
            side_effect_class=t_spec.side_effect_class,
            freshness_sec=t_spec.freshness_sec,
            consistency=t_spec.consistency,
            permissions=t_spec.permissions,
        )
        registry.register(t_def)

    # Register declared equivalences and fallbacks
    registry.register_equivalence(task.intended_tool, task.declared_equivalences)
    for t_name, alias_map in task.declared_aliases.items():
        registry.register_parameter_aliases(t_name, alias_map)
    registry.register_fallback_chain(task.intended_tool, task.declared_fallbacks)

    return registry, calls


def run_single_arm(
    arm: str,
    task: ContinuityTask,
    is_perturbed: bool,
    registry: ToolRegistry,
    calls: list[str],
) -> dict[str, Any]:
    """Execute a task under an arm and return metrics."""
    t0 = time.perf_counter()

    resolved_tool: str | None = None
    success = False
    replan = False
    unsafe_substitution = False
    unauthorized = False
    wrong_tool = False
    intent_preserved = False
    error_msg = ""

    state = ExecutionState(
        permissions=set(task.execution_contract.required_permissions),
        context={"env_state": task.environment_state},
    )

    try:
        if arm == "raw_agent":
            # Raw: calls primary directly with unmapped arguments
            tool_def = registry.get(task.intended_tool)
            if tool_def and tool_def.executable:
                resolved_tool = task.intended_tool
                res = tool_def.executable(**task.intended_arguments)
                success = True
            else:
                replan = True

        elif arm == "competent_boundary":
            # Competent: schema validation and bounded retry on primary only
            comp_mw = CompetentBaselineMiddleware()
            resolved_tool = task.intended_tool
            res = comp_mw.call(
                tool_name=task.intended_tool,
                arguments=task.intended_arguments,
                handler=lambda args: registry.get(task.intended_tool).executable(**args),
                idempotent=task.execution_contract.idempotent_required,
            )
            success = True

        elif arm == "static_resolution":
            # Static Resolution: exact same declarations, first declared match
            static_mw = StaticResolutionMiddleware(registry=registry)
            res = static_mw.call(
                tool_name=task.intended_tool,
                arguments=task.intended_arguments,
                idempotent=task.execution_contract.idempotent_required,
                state=state,
            )
            resolved_tool = res.get("source") if isinstance(res, dict) else calls[-1] if calls else None
            success = True

        elif arm == "veyra":
            # Veyra: Full post-proposal execution resolution with contract validation
            contract = ExecutionContract(
                capability=task.execution_contract.capability,
                max_freshness_sec=task.execution_contract.max_freshness_sec,
                required_consistency=task.execution_contract.required_consistency,
                side_effect_class=SideEffectClass(task.execution_contract.side_effect_class),
                required_state=task.execution_contract.required_state,
                required_permissions=task.execution_contract.required_permissions,
                idempotent_required=task.execution_contract.idempotent_required,
            )

            proposal = ExecutableAction(
                tool=task.intended_tool,
                arguments=task.intended_arguments,
                metadata={
                    "max_freshness_sec": task.execution_contract.max_freshness_sec,
                    "freshness_sec": task.execution_contract.max_freshness_sec,
                    "consistency": task.execution_contract.required_consistency,
                    "side_effect_class": task.execution_contract.side_effect_class,
                    "idempotent": task.execution_contract.idempotent_required,
                    "permissions": task.execution_contract.required_permissions,
                },
            )

            veyra_inst = Veyra(registry=registry)
            res = veyra_inst.execute(proposal, state=state)
            resolved_tool = res.get("source") if isinstance(res, dict) else (calls[-1] if calls else None)
            success = True

        elif arm == "oracle":
            # Oracle: directly executes ground truth valid tool
            valid_tool = task.valid_resolution_tools[0]
            resolved_tool = valid_tool
            res = registry.get(valid_tool).executable(**task.intended_arguments)
            success = True

    except Exception as exc:
        success = False
        replan = True
        error_msg = str(exc)

    lat_ms = (time.perf_counter() - t0) * 1000.0

    # Evaluate safety and contract invariants if a tool was executed
    if resolved_tool:
        # Check unsafe substitution: substituting mutating action when read-only requested
        resolved_spec = next((t for t in task.tools if t.name == resolved_tool), None)
        if resolved_spec:
            if task.execution_contract.side_effect_class == "read_only" and resolved_spec.side_effect_class != "read_only":
                unsafe_substitution = True
            # Check unauthorized
            if not set(resolved_spec.permissions).issubset(set(task.execution_contract.required_permissions)):
                unauthorized = True
            # Check wrong tool
            if resolved_tool in task.forbidden_resolution_tools:
                wrong_tool = True
            # Check intent preservation: must be in valid_resolution_tools and contract satisfied
            if resolved_tool in task.valid_resolution_tools and not unsafe_substitution and not unauthorized:
                intent_preserved = True
    else:
        wrong_tool = False
        intent_preserved = False

    return {
        "task_id": task.task_id,
        "arm": arm,
        "is_perturbed": is_perturbed,
        "resolved_tool": resolved_tool,
        "success": success,
        "intent_preserved": intent_preserved,
        "replan": replan,
        "wrong_tool": wrong_tool,
        "unsafe_substitution": unsafe_substitution,
        "unauthorized": unauthorized,
        "latency_ms": lat_ms,
        "error": error_msg,
    }


def evaluate_continuitybench(tasks: list[ContinuityTask], split_filter: str = "scorecard") -> dict[str, Any]:
    """Runs paired clean & perturbed evaluations for all tasks in the specified split."""
    eval_tasks = [t for t in tasks if t.split == split_filter]
    print(f"\n=======================================================")
    print(f"Running ContinuityBench Paired Evaluation ({split_filter.upper()} SPLIT)")
    print(f"Task Count: {len(eval_tasks)} paired instances")
    print(f"=======================================================\n")

    arms = ["raw_agent", "competent_boundary", "static_resolution", "veyra", "oracle"]
    arm_metrics: dict[str, dict[str, Any]] = {}

    for arm in arms:
        clean_successes = 0
        perturbed_successes = 0
        intent_preservations = 0
        replans = 0
        wrong_tools = 0
        unsafe_substitutions = 0
        unauthorized_actions = 0
        latencies = []

        for task in eval_tasks:
            # 1. Clean run (unperturbed)
            reg_clean, calls_clean = build_harness_for_task(task, is_perturbed=False)
            res_clean = run_single_arm(arm, task, is_perturbed=False, registry=reg_clean, calls=calls_clean)
            if res_clean["success"]:
                clean_successes += 1

            # 2. Perturbed run
            reg_pert, calls_pert = build_harness_for_task(task, is_perturbed=True)
            res_pert = run_single_arm(arm, task, is_perturbed=True, registry=reg_pert, calls=calls_pert)
            if res_pert["success"]:
                perturbed_successes += 1
            if res_pert["intent_preserved"]:
                intent_preservations += 1
            if res_pert["replan"]:
                replans += 1
            if res_pert["wrong_tool"]:
                wrong_tools += 1
            if res_pert["unsafe_substitution"]:
                unsafe_substitutions += 1
            if res_pert["unauthorized"]:
                unauthorized_actions += 1

            latencies.append(res_pert["latency_ms"])

        n = len(eval_tasks)
        # Primary metric: Intent Preservation Rate (IPR)
        # IPR = intent preserved on perturbed / clean successes with valid alternative
        ipr = (intent_preservations / max(1, clean_successes)) if clean_successes > 0 else 0.0
        degradation = (clean_successes - perturbed_successes) / n

        arm_metrics[arm] = {
            "clean_success_rate": round(clean_successes / n, 4),
            "perturbed_success_rate": round(perturbed_successes / n, 4),
            "intent_preservation_rate": round(ipr, 4),
            "degradation_delta": round(degradation, 4),
            "replan_rate": round(replans / n, 4),
            "wrong_tool_rate": round(wrong_tools / n, 4),
            "unsafe_substitution_rate": round(unsafe_substitutions / n, 4),
            "unauthorized_rate": round(unauthorized_actions / n, 4),
            "mean_latency_ms": round(sum(latencies) / n, 3),
        }

    return arm_metrics


def load_continuity_tasks(path: Path) -> list[ContinuityTask]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    tasks = []
    for item in raw:
        c_item = dict(item)
        if isinstance(c_item.get("execution_contract"), dict):
            c_item["execution_contract"] = ExecutionContractSpec(**c_item["execution_contract"])
        if isinstance(c_item.get("tools"), list):
            c_item["tools"] = [ToolSpec(**t) if isinstance(t, dict) else t for t in c_item["tools"]]
        tasks.append(ContinuityTask(**c_item))
    return tasks


if __name__ == "__main__":
    tasks_file = Path(__file__).parent / "tasks.json"
    if not tasks_file.exists():
        from benchmarks.continuitybench.builder import build_all_tasks, save_tasks_to_disk
        tasks = build_all_tasks()
        save_tasks_to_disk(tasks, tasks_file)
    else:
        tasks = load_continuity_tasks(tasks_file)

    # Evaluate strictly on held-out scorecard set
    metrics = evaluate_continuitybench(tasks, split_filter=GeneralizationSplit.SCORECARD.value)

    print(f"{'Arm':<22} | {'Clean Succ':<10} | {'Perturb Succ':<12} | {'IPR (Primary)':<14} | {'Degradation':<12} | {'Replans':<8} | {'Unsafe Sub':<10}")
    print("-" * 105)
    for arm, m in metrics.items():
        print(
            f"{arm:<22} | {m['clean_success_rate']*100:<9.1f}% | {m['perturbed_success_rate']*100:<11.1f}% | "
            f"{m['intent_preservation_rate']*100:<13.1f}% | {m['degradation_delta']*100:<11.1f}% | "
            f"{m['replan_rate']*100:<7.1f}% | {m['unsafe_substitution_rate']*100:<9.1f}%"
        )

    out_summary = Path(__file__).parent / "scorecard_results.json"
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nScorecard summary written to: {out_summary}")
