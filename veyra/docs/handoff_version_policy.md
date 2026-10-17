# Handoff Schema Version Policy

**Current Version: `HandoffV1` (`version: "1"`)**  
**Schema Path: `schemas/handoff.v1.json`**  
**Status: Frozen**

---

## 1. Scope & Objective

`HandoffV1` specifies the portable, harness-agnostic state payload compiled from runtime event logs when the Veyra kernel executes or simulates a harness switch. It adheres to the spirit of Harbor ATIF while enforcing strict field boundaries to prevent context pollution across harnesses.

## 2. Invariants & Immutability

1. **`version: "1"` is immutable.**  
   The schema definition in `schemas/handoff.v1.json` is strictly version-locked to `"const": "1"`. Any parser or validator seeing a document where `version != "1"` MUST reject the payload.
2. **Backwards Compatibility:**  
   - Any modifications to the `1.x` schema must be strictly additive and backward-compatible (e.g. optional fields with default values).
   - Existing fields (`version`, `task_id`, `from_harness`, `to_harness`, `shadow`, `budget`, `items`) cannot be renamed, removed, or made required if previously optional.
3. **Breaking Changes (V2 Policy):**  
   Any change that breaks backward compatibility—such as redefining the `kind` enum, restructuring the `budget` block, or removing required fields—mandates a major version bump to `schemas/handoff.v2.json` with `version: "2"`.

## 3. Allowed Item Kinds

The `items` array carries granular context distilled from prior execution attempts. Only the following 5 enumerated kinds are valid in `HandoffV1`:

| Kind | Purpose |
| :--- | :--- |
| `decision` | Record of a controller action decision and rationale (e.g. switch, retry, verify). |
| `failed_action` | Explicit description or kind of a failed tool/command action that prompted remediation. |
| `open_subgoal` | Extracted goal or instruction slice still pending completion. |
| `verification` | Status or outcome from an active verification pass (e.g. syntax check, test suite assertion). |
| `observation` | Salient observation or log extract passed to the successor harness. |

## 4. Shadow Mode Semantics

- When `shadow: true`, the handoff document represents a counterfactual event log: the controller identified an opportunity to switch harnesses or retry, but allowed the primary harness to continue executing.
- Shadow handoffs MUST NEVER mutate environment files, consume external budget, or trigger execution in another agent harness.
- In Harbor integrations, shadow mode backfills telemetry to `context.metadata["veyra_shadow"] = True` without altering the default execution flow.

## 5. Kev Scoring Boundary

- The `keep_score` field (`null` or `float` $\in [0.0, 1.0]$) allows model-based scorers (such as Kev-0.8B) to assign salience weights to extracted items.
- **Strict Boundary**: Kev scores items; Kev DOES NOT author or construct `HandoffV1` documents. The compiler (`veyra.handoff:compile_handoff`) generates the document from deterministic event traces.
