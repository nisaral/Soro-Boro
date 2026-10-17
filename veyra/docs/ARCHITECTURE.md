# Architecture

## The one invariant

```
DecisionModel predicts   →   Policy constrains   →   Executor acts   →   Verifier validates
```

- **DecisionModel** scores a candidate set. It cannot invent an action, call a tool, or touch a
  workspace.
- **Policy** (`go/internal/policy`) removes anything unsafe, unaffordable or illegal *before* a
  backend sees it: missing permission, retry streak, budget fraction, "no second harness".
- **Executor** is a harness adapter. It performs exactly the one approved action and returns the
  updated portable state.
- **Verifier** is a deterministic grader, routed by the kernel the moment a harness claims
  success. It is not a candidate, so no backend can skip it.

If a backend names a candidate outside the allowed set, the kernel emits `decision_rejected`,
falls back to the deterministic heuristic, and continues. If a backend errors, it emits
`decision_fallback`. Neither is a silent failure; both are in the event log.

## Why Go for the kernel

The kernel is a state machine with hard budgets and a durable log. Go gives that concurrency and
a single static binary for the demo, plus it is the part of the system that must not be clever.
The kernel owns exactly five things:

```
task lifecycle · checkpoint · budget (ledger) · event log · gRPC
```

Everything else is Python:

```
DecisionModel · HarnessAdapter · Veyra policy · benchmark · graders · LangGraph · native ReAct · RL/bandit
```

This split is deliberate: in a 2–3 month project the largest risk is spending six weeks making
the kernel beautiful while the experiment does not work.

## State contract

`CommonExecutionState` is what makes harness switching implementable without serializing anyone's
internals:

| field | why it is portable |
|---|---|
| `messages`, `observations`, `tool_results` | the model-visible history, harness-agnostic |
| `variables` | includes `veyra.tried_harnesses` (prevents oscillation) and `oracle.prefer_harness` |
| `artifacts`, `workspace` | what was produced and where |
| `usage` | cumulative model usage; the kernel charges deltas from it |
| `step`, `done`, `failed`, `failure_kind` | the control signal the policy reads |
| `checkpoint_id` | set by the kernel when a switch is recorded |

Switching is `checkpoint → interrupt old harness → start new harness with the state`. A switch
leaves a real checkpoint on disk, replayable with no database.

## Ledger

`budget.Ledger` is charged for every dispatched action:

```
charge = harness_overhead_per_step + max(0, state_usage_delta)
```

Using a **delta** (not the cumulative state usage) is what stops a switch from double-charging the
run. It also means the harness plane cannot under-report cost: a harness that reports zero model
usage still pays its overhead. `Fraction()` feeds the policy soft limit, above which switching and
expensive model calls stop being allowed.

## Event log

`runs/<run-id>/events.jsonl` is the authoritative record: `task_started`, `decision`, `action`,
`observation`, `checkpoint`, `harness_switch`, `failure`, `verify`, `decision_fallback`,
`decision_rejected`, `run_finished`. Every event carries the current ledger usage.

This is also the training corpus: decision events embed the exact candidate set (id, type,
provider, estimated cost, expected success, risk), so an offline learner is fit on the features the
policy actually saw rather than a reconstruction.

## Benchmark

`python/src/veyra/bench/tasks.py` defines 30 deterministic tasks (6 categories × 5, split 3 dev /
3 test per category). Each task carries a seed workspace, a grader spec, a budget, and per-harness
scripts for the offline model. `runner.py` submits one run per (task, arm) over gRPC and records
the aggregate; `report.py` renders the tables and applies the pre-registered verdict.

## Next steps

1. Live-model headline run (`--model-mode ollama`) with the same protocol, and a variance check
   across seeds.
2. `repair` is the third harness: it diagnoses before the model call. The kernel clears
   `failed` on a switch so the new harness gets one step before another switch is scored.
   A real LangGraph package, rather than MiniGraph, is still future work.
3. More candidates for the decision model (model tier, tool choice, checkpoint timing) so the
   learned policy has room to beat the heuristic.
4. SWE-bench adapter, kept separate from the bundled suite (its harness is expensive; it should
   not be the first development loop).
5. Optional: a Jev-style decision backend served locally (Von / Kev-0.8B) with calibration
   reporting.
