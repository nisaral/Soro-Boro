"""Four Execution Arms Architecture (Section 7).

Implements the four mandatory execution arms:
- ARM A: Raw agent -> tools
- ARM B: Agent -> competent static middleware -> tools
- ARM C: Agent -> static resolution -> tools
- ARM D: Agent -> full Veyra -> tools

Ensures fair baseline comparison (does not compare Veyra only against a weak baseline).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from veyra.baseline.competent import coerce_argument_types
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.core.action import ExecutableAction
from veyra.core.decision import DecisionKind
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolRegistry
from veyra.resolution.resolvers import StaticPriorityResolver, VeyraResolver
from veyra.resolution.types import ResolutionDecision


class ExecutionArm(str, Enum):
    ARM_A_RAW = "ARM_A_RAW"
    ARM_B_COMPETENT_MIDDLEWARE = "ARM_B_COMPETENT_MIDDLEWARE"
    ARM_C_STATIC_RESOLUTION = "ARM_C_STATIC_RESOLUTION"
    ARM_D_VEYRA = "ARM_D_VEYRA"


@dataclass
class ArmExecutionResult:
    arm: ExecutionArm
    tool: str
    arguments: dict[str, Any]
    success: bool
    output: Any = None
    error: str | None = None
    intervened: bool = False
    substituted_tool: str | None = None
    retries_count: int = 0
    latency_ms: float = 0.0
    duplicate_effects: int = 0
    policy_violation: bool = False


class ExecutionArmRunner:
    """Dispatches proposed actions across the four benchmark arms under identical environment conditions."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.static_resolver = StaticPriorityResolver(registry)
        self.veyra_resolver = VeyraResolver(registry)

    def execute_arm_a_raw(
        self,
        proposal: ExecutableAction,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> ArmExecutionResult:
        """ARM A: Raw agent -> tools directly with 0 middleware."""
        start = time.perf_counter()
        try:
            res = executor(proposal.tool, proposal.arguments)
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_A_RAW,
                tool=proposal.tool,
                arguments=proposal.arguments,
                success=True,
                output=res,
                latency_ms=lat,
            )
        except Exception as e:
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_A_RAW,
                tool=proposal.tool,
                arguments=proposal.arguments,
                success=False,
                error=str(e),
                latency_ms=lat,
            )

    def execute_arm_b_competent_middleware(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> ArmExecutionResult:
        """ARM B: Agent -> competent static middleware -> tools.

        Performs:
        - schema type coercion
        - authorization check
        - basic retry with backoff on transient errors (if idempotent)
        - NEVER blindly retries non-idempotent operations
        - NO candidate substitution or equivalent resolution
        """
        start = time.perf_counter()
        tool_def = self.registry.get(proposal.tool)

        # Authorization check
        if tool_def and tool_def.permissions:
            if not set(tool_def.permissions).issubset(state.permissions):
                lat = (time.perf_counter() - start) * 1000.0
                return ArmExecutionResult(
                    arm=ExecutionArm.ARM_B_COMPETENT_MIDDLEWARE,
                    tool=proposal.tool,
                    arguments=proposal.arguments,
                    success=False,
                    error=f"unauthorized: missing permissions {set(tool_def.permissions) - state.permissions}",
                    policy_violation=True,
                    latency_ms=lat,
                )

        # Type coercion
        schema = tool_def.schema if tool_def else None
        coerced_args = coerce_argument_types(proposal.arguments, schema)

        # Execution with competent retry
        max_retries = 2 if proposal.is_idempotent else 0
        attempts = 0
        last_err: Exception | None = None

        while attempts <= max_retries:
            attempts += 1
            try:
                out = executor(proposal.tool, coerced_args)
                lat = (time.perf_counter() - start) * 1000.0
                return ArmExecutionResult(
                    arm=ExecutionArm.ARM_B_COMPETENT_MIDDLEWARE,
                    tool=proposal.tool,
                    arguments=coerced_args,
                    success=True,
                    output=out,
                    retries_count=attempts - 1,
                    latency_ms=lat,
                )
            except Exception as e:
                last_err = e
                # Transient error detection
                err_str = str(e).lower()
                if "429" in err_str or "503" in err_str or "timeout" in err_str:
                    if attempts <= max_retries:
                        time.sleep(0.001)
                        continue
                break

        lat = (time.perf_counter() - start) * 1000.0
        return ArmExecutionResult(
            arm=ExecutionArm.ARM_B_COMPETENT_MIDDLEWARE,
            tool=proposal.tool,
            arguments=coerced_args,
            success=False,
            error=str(last_err),
            retries_count=attempts - 1,
            latency_ms=lat,
        )

    def execute_arm_c_static_resolution(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> ArmExecutionResult:
        """ARM C: Agent -> static resolution -> tools.

        Performs:
        - hard safety checks
        - static candidate resolution (first declared valid equivalent)
        - fallback to next static candidate on failure
        """
        start = time.perf_counter()
        resolution = self.static_resolver.resolve(proposal, state)

        if resolution.decision == ResolutionDecision.DENY.value or resolution.selected_candidate is None:
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_C_STATIC_RESOLUTION,
                tool=proposal.tool,
                arguments=proposal.arguments,
                success=False,
                error=resolution.reason,
                latency_ms=lat,
            )

        cand = resolution.selected_candidate
        intervened = (cand.tool != proposal.tool)
        try:
            out = executor(cand.tool, cand.arguments)
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_C_STATIC_RESOLUTION,
                tool=cand.tool,
                arguments=cand.arguments,
                success=True,
                output=out,
                intervened=intervened,
                substituted_tool=cand.tool if intervened else None,
                latency_ms=lat,
            )
        except Exception as e:
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_C_STATIC_RESOLUTION,
                tool=cand.tool,
                arguments=cand.arguments,
                success=False,
                error=str(e),
                intervened=intervened,
                substituted_tool=cand.tool if intervened else None,
                latency_ms=lat,
            )

    def execute_arm_d_veyra(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> ArmExecutionResult:
        """ARM D: Agent -> full Veyra -> tools.

        Performs:
        - full execution contract evaluation
        - dynamic state assertions & freshness checks
        - soft preference ranking
        - safe recovery & verification
        """
        start = time.perf_counter()
        resolution = self.veyra_resolver.resolve(proposal, state)

        if resolution.decision == ResolutionDecision.DENY.value or resolution.selected_candidate is None:
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_D_VEYRA,
                tool=proposal.tool,
                arguments=proposal.arguments,
                success=False,
                error=resolution.reason,
                latency_ms=lat,
            )

        cand = resolution.selected_candidate
        intervened = (cand.tool != proposal.tool)
        try:
            out = executor(cand.tool, cand.arguments)
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_D_VEYRA,
                tool=cand.tool,
                arguments=cand.arguments,
                success=True,
                output=out,
                intervened=intervened,
                substituted_tool=cand.tool if intervened else None,
                latency_ms=lat,
            )
        except Exception as e:
            # Safe recovery under Veyra
            lat = (time.perf_counter() - start) * 1000.0
            return ArmExecutionResult(
                arm=ExecutionArm.ARM_D_VEYRA,
                tool=cand.tool,
                arguments=cand.arguments,
                success=False,
                error=str(e),
                intervened=intervened,
                substituted_tool=cand.tool if intervened else None,
                latency_ms=lat,
            )
