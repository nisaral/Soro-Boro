"""Static Resolution Baselines: Weak Static & Fair Static (Phases 12 & 44 Specification).

Resolves the baseline parity contradiction by establishing two explicit baseline families:

1. WeakStaticResolutionMiddleware:
   - Does NOT perform dynamic contract enforcement or strict side-effect compatibility.
   - Simply picks the first declared equivalent or fallback in catalog order.
   - May commit side-effect widenings if an incompatible tool is listed in catalog.

2. FairStaticResolutionMiddleware (Fair Baseline):
   - Receives EXACTLY the same hard safety information and declarations available to Veyra:
     1. Equivalence declarations
     2. Argument alias maps
     3. Fallback candidate chains
     4. Shared hard safety primitives (is_authorized, is_side_effect_compatible, is_idempotent)
   - Uses a simple deterministic strategy:
     1. First valid candidate in fixed configured priority order
     2. Sequential fallback to next candidate if primary fails
   - GUARANTEES 0 side-effect widenings and 0 unauthorized actions.
   - LACKS only Veyra's distinctive dynamic capabilities:
     1. Dynamic runtime environment state assertions (tenant, session)
     2. Dynamic data freshness thresholds (max_freshness_sec)
     3. Adaptive execution history (Case Memory & TAGE)
     4. Real-time Beta-Bernoulli / CUSUM health tracking
"""

from __future__ import annotations

import time
from typing import Any, Callable

from soro.baseline.competent import coerce_argument_types
from soro.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from soro.core.action import ExecutableAction
from soro.core.contract_evaluator import (
    is_authorized,
    is_idempotent,
    is_side_effect_compatible,
    validate_candidate_shared,
)
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState
from soro.registry.tool_registry import ToolRegistry


class WeakStaticResolutionMiddleware:
    """Weak static baseline: picks first declared candidate without hard safety contract checks."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        state: ExecutionState | None = None,
    ) -> Any:
        candidate_names = [tool_name] + self.registry.get_equivalents(tool_name) + self.registry.get_fallback_chain(tool_name)
        for cand_name in candidate_names:
            tool_def = self.registry.get(cand_name)
            if tool_def and tool_def.executable:
                try:
                    return tool_def.executable(**arguments)
                except Exception:
                    continue
        raise VeyraBoundaryError(FailureClassification(
            kind=FailureKind.PRECONDITION_ERROR,
            provenance=FailureProvenance.PRECONDITION_ERROR,
            message="Weak static resolution failed",
        ))


class FairStaticResolutionMiddleware:
    """Fair static resolution middleware using shared hard safety primitives and fixed priority."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        idempotent: bool | None = None,
        state: ExecutionState | None = None,
        contract: ExecutionContract | None = None,
    ) -> Any:
        exec_state = state or ExecutionState()

        # Build candidate chain: primary tool followed by declared equivalents and fallbacks
        candidate_names = [tool_name]
        for eq in self.registry.get_equivalents(tool_name):
            if eq not in candidate_names:
                candidate_names.append(eq)

        for fb in self.registry.get_fallback_chain(tool_name):
            if fb not in candidate_names:
                candidate_names.append(fb)

        # Policy-allowed filter
        allowed = exec_state.context.get("allowed_tools")
        if allowed is not None:
            candidate_names = [c for c in candidate_names if c in allowed]

        if not candidate_names:
            clf = FailureClassification(
                kind=FailureKind.AUTHORIZATION_ERROR,
                provenance=FailureProvenance.AUTHORIZATION_ERROR,
                retryable=False,
                repairable=False,
                requires_agent=True,
                safe_to_retry=False,
                message=f"No permitted candidates for '{tool_name}'",
            )
            raise VeyraBoundaryError(clf)

        last_error: Exception | None = None

        # Build default hard safety contract if none provided
        eff_contract = contract or ExecutionContract(
            capability=tool_name,
            side_effect_class=SideEffectClass.READ_ONLY if idempotent else SideEffectClass.NON_IDEMPOTENT_MUTATION,
            idempotent_required=bool(idempotent),
        )

        for cand_name in candidate_names:
            tool_def = self.registry.get(cand_name)
            if tool_def is None or tool_def.executable is None:
                continue

            cand_action = ExecutableAction(
                tool=cand_name,
                arguments=arguments,
                metadata={
                    "permissions": tool_def.permissions,
                    "idempotent": tool_def.idempotent,
                    "side_effect_class": getattr(tool_def, "side_effect_class", "read_only" if tool_def.idempotent else "mutation"),
                },
            )

            # Shared Hard Safety Check (Parity with Veyra on hard constraints, enforce_dynamic_state=False)
            is_valid, _ = validate_candidate_shared(
                candidate=cand_action,
                contract=eff_contract,
                state=exec_state,
                enforce_dynamic_state=False,
            )
            if not is_valid:
                continue

            # Argument alias remapping
            alias_map = self.registry.get_parameter_aliases(cand_name)
            remapped_args = dict(arguments)
            for prop_arg, canon_arg in alias_map.items():
                if prop_arg in remapped_args and canon_arg not in remapped_args:
                    remapped_args[canon_arg] = remapped_args.pop(prop_arg)

            # Schema coercion
            schema = tool_def.schema
            coerced_args = coerce_argument_types(remapped_args, schema)
            if schema:
                required = schema.get("required") or schema.get("parameters", {}).get("required", [])
                if any(req not in coerced_args for req in required):
                    continue

            # Execute candidate
            try:
                result = tool_def.executable(**coerced_args)
                return result
            except Exception as exc:
                last_error = exc
                cand_idempotent = tool_def.idempotent if idempotent is None else idempotent
                if not cand_idempotent:
                    clf = classify_exception(exc, safe=False)
                    raise VeyraBoundaryError(clf, original_exc=exc) from exc

        if last_error is not None:
            clf = classify_exception(last_error, safe=True)
            raise VeyraBoundaryError(clf, original_exc=last_error) from last_error

        clf = FailureClassification(
            kind=FailureKind.PRECONDITION_ERROR,
            provenance=FailureProvenance.PRECONDITION_ERROR,
            retryable=False,
            repairable=False,
            requires_agent=True,
            safe_to_retry=False,
            message="All declared fair static candidates failed or invalid",
        )
        raise VeyraBoundaryError(clf)


# Backward compatibility alias
StaticResolutionMiddleware = FairStaticResolutionMiddleware

__all__ = [
    "WeakStaticResolutionMiddleware",
    "FairStaticResolutionMiddleware",
    "StaticResolutionMiddleware",
]
