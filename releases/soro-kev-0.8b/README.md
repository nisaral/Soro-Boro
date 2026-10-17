---
license: apache-2.0
base_model: Qwen/Qwen3.5-0.8B-Base
tags:
  - tool-calling
  - mcp
  - agent-harness
  - pointer-network
  - conformal-prediction
  - system-one
---

# Soro-Kev-0.8B

Edge System-One pointer on `Qwen/Qwen3.5-0.8B-Base`. One prefill, no generated JSON.

`calibrated_q_hat` here is **0.9518** from the seed-42 `val_zeroshot` slice (100 calibration / 200 test). The training quantile was 0.5813. A separate unshuffled run on 1,920 test rows scored 80.99% route accuracy, 96.56% argument mapping, 3.33% permutation flip, mean set size 1.16, and q_hat 0.9457. That full file is not the same split as the 200-row table below.

Windows runs this Qwen3.5 checkpoint on the slow DeltaNet fallback. The 80 ms median below is that fallback, not a Linux `causal_conv1d` kernel.

## Shared seed-42 slices

| | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| Zero-shot route, 200 rows | 47.50% | 84.50% | 89.00% |
| External human route, 200 rows | 60.50% | 89.00% | 94.50% |
| BFCL multiple, 34 rows | 97.06% | 100% | 100% |
| BFCL live multiple, 33 rows | 75.76% | 96.97% | 96.97% |
| BFCL irrelevance abstain, 33 rows | 3.03% | 57.58% | 75.76% |

Peak VRAM on the decision-model pass was 1,563 MB. Median latency was 80 ms.

```python
from soro.harness.pipeline import SoroHarness
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-0.8b")
```
