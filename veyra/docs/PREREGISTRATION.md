# Pre-registration (v0.1)

Written **before** the held-out split was run: 2026-10-03.

The point of pre-registering this is that the interesting question is not "did the demo work"
but "was the claim falsifiable, and did it survive". A null result is an acceptable outcome and
is reported as one.

## The claim

> On the held-out test split, at least one adaptive arm (`veyra:*`) is **non-inferior** to the
> **best fixed harness selected on the dev split** within a **5 percentage-point** success
> margin, **and** has a lower mean charged cost per task.

Non-inferiority is measured against the fixed baseline *chosen on dev*, not against the most
expensive arm. This matters: comparing against the worst or most expensive baseline can be passed
by a system that is still worse than the relevant fixed baseline.

## Falsification bar

The claim is **NOT SUPPORTED** if, on the held-out split, every adaptive arm either:

- loses more than 5 points of success relative to the dev-selected fixed baseline, or
- is not cheaper than that baseline.

No post-hoc re-selection is allowed: the baseline is fixed by dev results before test runs, and
only the dev-selected baseline plus the adaptive arms plus the offline oracle are run on test.

## Protocol

1. **Development split** (15 tasks): run `fixed:native`, `fixed:langgraph` and every adaptive arm.
   Choose the fixed arm with the highest success rate; break ties on lower mean cost.
2. **Freeze** the selected baseline. Fit the bandit policy on dev run traces **only**.
3. **Held-out split** (15 tasks): run only the frozen baseline, `veyra:heuristic`, `veyra:von`,
   `veyra:bandit` and the offline `oracle`.
4. Compute success, charged cost, switches and the verdict mechanically
   (`veyra.bench.report.verdict`). Publish the outcome, including a null result.

Reproduce:

```bash
make bench-dev      # select on dev
make train          # fit the bandit on dev traces only
make bench-test     # evaluate on the held-out split, writes verdict.json
```

## Arms

| arm | kind | role |
|---|---|---|
| `fixed:native` | fixed | control condition: imperative ReAct loop, never switches |
| `fixed:langgraph` | fixed | control condition: graph runtime, never switches |
| `veyra:heuristic` | adaptive | hand-written failure-triggered switching |
| `veyra:von` | adaptive | Jev-style typed decision model, or a labelled surrogate |
| `veyra:bandit` | adaptive | LinUCB fit offline on dev traces |
| `oracle` | offline ceiling | sees realized outcomes; an upper bound, never deployable |

## Metrics

- **Success**: deterministic grader in the task workspace. Graders never call a model.
- **Cost**: charged USD from the kernel ledger — measured model usage **plus** a per-step harness
  overhead. Harness choice therefore has a price.
- **Switches per run**: 1.00 means the arm switched on every task; 0.20 means 1 in 5.
- **Decision backend actually used**: taken from the kernel's decision events, so an untrained or
  surrogate backend cannot be silently reported as a real one.

## Threats to validity

1. **Scripted model.** The committed numbers use `model_mode=offline`. The scripted model replays
   fixed per-harness scripts, so it validates the kernel/contract/ledger but cannot demonstrate
   anything about model behaviour. The claim needs `--model-mode ollama` (or another live
   endpoint) to be read as a statement about real agents.
2. **Suite size.** 30 tasks total, 15 per split. Success-rate differences of one or two tasks are
   inside noise; per-category cells have 3 tasks each.
3. **Harness asymmetry.** `langgraph` here is a two-node-per-action graph, not a large production
   graph. It is a genuinely *different* runtime (different state container, transitions and
   failure surface) but it is not a strong LangGraph implementation.
4. **Graph fallback.** If `langgraph` is unavailable, the arm uses `MiniGraph` and reports
   `engine:builtin-graph`. Results are then about "a graph harness", not specifically LangGraph.
5. **Surrogate decision model.** `veyra:von` with no endpoint is a hand-tuned scorer, labelled
   `von-surrogate`. Any number attributed to it describes the surrogate.
6. **Offline policy fitting.** The bandit is fit on logged decisions with shaped rewards. This is
   offline policy fitting, not causal/off-policy evaluation, and it can inherit the behaviour of
   the logging policy.
7. **Single run, no seeds.** The scripted model is deterministic and temperature is 0, so there is
   one run per (task, arm). Variance across seeds is unmeasured.
8. **Harness overhead is an assumption.** Per-step overheads (`native` $0.001, `langgraph`
   $0.003) are declared constants used to make the economics non-trivial. A different assumption
   changes the cost column; the success column is unaffected.

## v0.2 addition (repair harness)

v0.1 compared native and langgraph only. v0.2 adds `repair`, a harness that
loads the failing file before the model call and, on the scripted suite, edits
before it executes. The v0.1 verdict below is unchanged and is not comparable
to a run that includes `fixed:repair`. Re-run `bench-dev` / `bench-test` for
the three-harness numbers.

## Recorded outcome

- dev-selected baseline: `fixed:langgraph`
- held-out test: adaptive arms 100.0% / $0.0118 vs baseline 100.0% / $0.0190
- **verdict: SUPPORTED** (non-inferior, 37.9% cheaper)
- secondary finding: the offline oracle ceiling did **not** exceed the heuristic on this suite, so
  the learned policy is not distinguishable from the hand-written rule here. Reported as a null
  result for the "does learning help?" sub-question.
