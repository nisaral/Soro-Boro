---
license: apache-2.0
base_model: Qwen/Qwen3-4B
tags:
  - tool-calling
  - mcp
  - agent-harness
  - pointer-network
  - conformal-prediction
  - system-one
---

# Soro-Kev-4B

System-One pointer router. One prefill of `Qwen/Qwen3-4B` (NF4 on GPU) scores the question-end hidden state against each option-end hidden state. It does not generate tool-call JSON.

`calibrated_q_hat` in this bundle is **0.8066**, from a seed-42 shuffle of `val_zeroshot.jsonl` with 100 calibration rows and 200 test rows. The training-time quantile was 0.9154. The external-human slice quantile was 0.845. These are slice calibrations, not an official BFCL leaderboard entry.

## Results on the shared seed-42 slices

200 test rows. Heuristic is hashed token overlap.

| | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| Zero-shot route | 47.50% | 84.50% | 89.00% |
| Zero-shot coverage | 89.50% | 89.00% | 93.00% |
| Zero-shot mean set size | 4.39 | 1.17 | 1.11 |
| External-human route | 60.50% | 89.00% | 94.50% |
| External-human coverage | 95.50% | 95.50% | 95.00% |
| External-human mean set size | 4.18 | 1.18 | 1.07 |

BFCL routing slice, 100 rows (34 multiple, 33 live multiple, 33 irrelevance). This is tool-name accuracy on our converted rows, not the Gorilla executable leaderboard.

| | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| multiple | 97.06% | 100% | 100% |
| live multiple | 75.76% | 96.97% | 96.97% |
| irrelevance abstain | 3.03% | 57.58% | 75.76% |

Same 100 BFCL rows plus 60 external rows, also against `jaredpalmer/kev-0.8b`:

| | Heuristic | Kev-0.8B | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|---|
| multiple | 100% | 100% | 100% | 100% |
| live multiple | 84.8% | 69.7% | 97.0% | 97.0% |
| irrelevance abstain | 3.0% | 81.8% | 57.6% | 75.8% |
| external 60 | 36.7% | 75.0% | 83.3% | 85.0% |
| median latency | 0.31 ms | 111 ms | 80 ms | 413 ms |
| peak VRAM | 0 | 1,612 MB | 1,563 MB | 4,048 MB |

The live-multiple heuristic cell differs from the earlier 100-row script (75.8%) because that script and this decision-model pass do not use the same hit rule on every row. Use `veyra/reports/decision_model_benchmark.json` and `veyra/reports/bfcl_100_*.json` as the sources.

4B external route accuracy by format on the 200-row slice: MCP JSON 94.4% (36), mixed 94.6% (37), agent skill 100% (29), REST 96.2% (26), GraphQL 96.8% (31), Python signature 87.8% (41).

Adversarial harness on the RTX 4050: the 4B checkpoint passed the dataflow chain, the Jira/Linear ask, the sev1 disambiguation, the missing-amount halt, the negation trap, and the 25-tool haystack including the soufflé abstain. The 0.8B checkpoint missed `list_incidents` on that haystack.

## Load

```python
from soro.harness.pipeline import SoroHarness

harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")
```

A local directory works the same way. On CUDA with `bitsandbytes`, a model id containing `4b` loads NF4. Without bitsandbytes the loader falls back to bf16, then fp16.
