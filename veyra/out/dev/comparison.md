# Veyra comparison

- model: `offline` (scripted model)
- split: `dev`  tasks: 15
- generated: 2026-10-03 17:24:04 UTC

| arm | success | mean $ | mean wall ms | mean actions | switches/run |
|---|---:|---:|---:|---:|---:|
| fixed:repair | 100.0% | $0.0096 | 2140 | 4.8 | 0.00 |
| veyra:heuristic | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| veyra:von | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| veyra:bandit | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| oracle | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| fixed:langgraph | 100.0% | $0.0190 | 2756 | 5.0 | 0.00 |
| fixed:native | 80.0% | $0.0078 | 1920 | 4.4 | 0.00 |

## Caveats

- model_mode=offline: the scripted model proves the kernel/harness/decision plumbing and the wire protocol, not model behaviour. Headline numbers require a live model (--model-mode ollama).
- Harness cost is charged as a per-step overhead on top of measured model usage, so harness selection is an economic decision rather than a free one.
- veyra:von ran as `von-surrogate` (no --von-endpoint): it is NOT a real Jev-style model and must not be reported as one.
- veyra:bandit ran untrained (no --bandit-state): it defers to the heuristic baseline and is labelled `bandit-untrained` in the event log.
- the `langgraph` arm used the in-repo MiniGraph fallback (LangGraph unavailable in this environment), reported as engine:builtin-graph.

## Decision backends observed

| arm | backends reported by the kernel |
|---|---|
| fixed:langgraph | heuristic |
| fixed:native | heuristic |
| fixed:repair | heuristic |
| oracle | oracle |
| veyra:bandit | bandit-untrained |
| veyra:heuristic | heuristic |
| veyra:von | von-surrogate |

## By category

| category | arm | success | mean $ |
|---|---|---:|---:|
| coding | fixed:langgraph | 100% | $0.0110 |
| coding | fixed:native | 100% | $0.0050 |
| coding | fixed:repair | 100% | $0.0056 |
| coding | oracle | 100% | $0.0050 |
| coding | veyra:bandit | 100% | $0.0050 |
| coding | veyra:heuristic | 100% | $0.0050 |
| coding | veyra:von | 100% | $0.0050 |
| long_horizon | fixed:langgraph | 100% | $0.0270 |
| long_horizon | fixed:native | 100% | $0.0130 |
| long_horizon | fixed:repair | 100% | $0.0144 |
| long_horizon | oracle | 100% | $0.0130 |
| long_horizon | veyra:bandit | 100% | $0.0130 |
| long_horizon | veyra:heuristic | 100% | $0.0130 |
| long_horizon | veyra:von | 100% | $0.0130 |
| migration | fixed:langgraph | 100% | $0.0190 |
| migration | fixed:native | 100% | $0.0090 |
| migration | fixed:repair | 100% | $0.0100 |
| migration | oracle | 100% | $0.0090 |
| migration | veyra:bandit | 100% | $0.0090 |
| migration | veyra:heuristic | 100% | $0.0090 |
| migration | veyra:von | 100% | $0.0090 |
| recovery | fixed:langgraph | 100% | $0.0190 |
| recovery | fixed:native | 0% | $0.0030 |
| recovery | fixed:repair | 100% | $0.0078 |
| recovery | oracle | 100% | $0.0118 |
| recovery | veyra:bandit | 100% | $0.0118 |
| recovery | veyra:heuristic | 100% | $0.0118 |
| recovery | veyra:von | 100% | $0.0118 |
| terminal | fixed:langgraph | 100% | $0.0190 |
| terminal | fixed:native | 100% | $0.0090 |
| terminal | fixed:repair | 100% | $0.0100 |
| terminal | oracle | 100% | $0.0090 |
| terminal | veyra:bandit | 100% | $0.0090 |
| terminal | veyra:heuristic | 100% | $0.0090 |
| terminal | veyra:von | 100% | $0.0090 |
