# Veyra comparison

- model: `offline` (scripted model)
- split: `test`  tasks: 15
- generated: 2026-10-03 17:25:25 UTC

| arm | success | mean $ | mean wall ms | mean actions | switches/run |
|---|---:|---:|---:|---:|---:|
| fixed:repair | 100.0% | $0.0096 | 2140 | 4.8 | 0.00 |
| veyra:heuristic | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| veyra:von | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| veyra:bandit | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| oracle | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |

## Caveats

- model_mode=offline: the scripted model proves the kernel/harness/decision plumbing and the wire protocol, not model behaviour. Headline numbers require a live model (--model-mode ollama).
- Harness cost is charged as a per-step overhead on top of measured model usage, so harness selection is an economic decision rather than a free one.
- veyra:von ran as `von-surrogate` (no --von-endpoint): it is NOT a real Jev-style model and must not be reported as one.

## Decision backends observed

| arm | backends reported by the kernel |
|---|---|
| fixed:repair | heuristic |
| oracle | oracle |
| veyra:bandit | bandit |
| veyra:heuristic | heuristic |
| veyra:von | von-surrogate |

## Pre-registered verdict

- claim: On the held-out test split, an adaptive arm is non-inferior to the best fixed harness selected on dev (fixed:repair) within 5 points and has lower mean cost per task.
- selected on dev: `fixed:repair`
- test baseline: 100.0% / $0.0096
- outcome: NOT SUPPORTED

| arm | test success | mean $ | cost reduction vs fixed | non-inferior | supported |
|---|---:|---:|---:|---|---|
| oracle | 100.0% | $0.0096 | -0.0% | yes | no |
| veyra:bandit | 100.0% | $0.0096 | -0.0% | yes | no |
| veyra:heuristic | 100.0% | $0.0096 | -0.0% | yes | no |
| veyra:von | 100.0% | $0.0096 | -0.0% | yes | no |

> The pre-registered hypothesis was **not supported** under this task distribution.

## By category

| category | arm | success | mean $ |
|---|---|---:|---:|
| coding | fixed:repair | 100% | $0.0056 |
| coding | oracle | 100% | $0.0050 |
| coding | veyra:bandit | 100% | $0.0050 |
| coding | veyra:heuristic | 100% | $0.0050 |
| coding | veyra:von | 100% | $0.0050 |
| long_horizon | fixed:repair | 100% | $0.0144 |
| long_horizon | oracle | 100% | $0.0130 |
| long_horizon | veyra:bandit | 100% | $0.0130 |
| long_horizon | veyra:heuristic | 100% | $0.0130 |
| long_horizon | veyra:von | 100% | $0.0130 |
| migration | fixed:repair | 100% | $0.0100 |
| migration | oracle | 100% | $0.0090 |
| migration | veyra:bandit | 100% | $0.0090 |
| migration | veyra:heuristic | 100% | $0.0090 |
| migration | veyra:von | 100% | $0.0090 |
| recovery | fixed:repair | 100% | $0.0078 |
| recovery | oracle | 100% | $0.0118 |
| recovery | veyra:bandit | 100% | $0.0118 |
| recovery | veyra:heuristic | 100% | $0.0118 |
| recovery | veyra:von | 100% | $0.0118 |
| terminal | fixed:repair | 100% | $0.0100 |
| terminal | oracle | 100% | $0.0090 |
| terminal | veyra:bandit | 100% | $0.0090 |
| terminal | veyra:heuristic | 100% | $0.0090 |
| terminal | veyra:von | 100% | $0.0090 |
