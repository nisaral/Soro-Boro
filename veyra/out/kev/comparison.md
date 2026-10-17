# Veyra comparison — SYNTHETIC / SCRIPTED

This table is an internal smoke test. The harness model is the scripted offline
model. Kev only scored the next-action choice. Do not quote it as MCPAgentBench,
as a live-model result, or as evidence that Veyra improves real tool use.

- model: `offline` (scripted model)
- split: `dev`  tasks: 15
- label: `synthetic/scripted`
- generated: 2026-10-04 07:33:34 UTC

| arm | success | mean $ | mean wall ms | mean actions | switches/run |
|---|---:|---:|---:|---:|---:|
| veyra:heuristic | 100.0% | $0.0096 | 2160 | 5.2 | 0.20 |
| fixed:native | 80.0% | $0.0078 | 1920 | 4.4 | 0.00 |
| veyra:kev | 80.0% | $0.0386 | 4140 | 4.6 | 0.00 |

## Caveats

- model_mode=offline: the scripted model proves the kernel/harness/decision plumbing and the wire protocol, not model behaviour. Headline numbers require a live model (--model-mode ollama).
- Harness cost is charged as a per-step overhead on top of measured model usage, so harness selection is an economic decision rather than a free one.

## Decision backends observed

| arm | backends reported by the kernel |
|---|---|
| fixed:native | heuristic |
| veyra:heuristic | heuristic |
| veyra:kev | kev |

## By category

| category | arm | success | mean $ |
|---|---|---:|---:|
| coding | fixed:native | 100% | $0.0050 |
| coding | veyra:heuristic | 100% | $0.0050 |
| coding | veyra:kev | 100% | $0.0230 |
| long_horizon | fixed:native | 100% | $0.0130 |
| long_horizon | veyra:heuristic | 100% | $0.0130 |
| long_horizon | veyra:kev | 100% | $0.0670 |
| migration | fixed:native | 100% | $0.0090 |
| migration | veyra:heuristic | 100% | $0.0090 |
| migration | veyra:kev | 100% | $0.0450 |
| recovery | fixed:native | 0% | $0.0030 |
| recovery | veyra:heuristic | 100% | $0.0118 |
| recovery | veyra:kev | 0% | $0.0130 |
| terminal | fixed:native | 100% | $0.0090 |
| terminal | veyra:heuristic | 100% | $0.0090 |
| terminal | veyra:kev | 100% | $0.0450 |
