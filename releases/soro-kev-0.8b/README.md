---
license: apache-2.0
base_model: Qwen/Qwen3.5-0.8B-Base
tags:
  - decision-model
  - tool-calling
  - function-calling
  - mcp
  - model-context-protocol
  - pointer-network
  - conformal-prediction
  - system-one
  - multiple-choice
  - calibration
  - typesafe
  - agent-harness
  - edge-ai
  - qwen3.5
datasets:
  - nisaralll/soro-universal-tool-harness
pipeline_tag: text-classification
---

# Soro-Kev-0.8B: Ultra-Fast Edge Tool Router

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Base Model](https://img.shields.io/badge/Base_Model-Qwen3.5--0.8B-purple.svg)](https://huggingface.co/Qwen/Qwen3.5-0.8B-Base)
[![Dataset](https://img.shields.io/badge/Dataset-soro--universal--tool--harness-green.svg)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
[![GitHub](https://img.shields.io/badge/GitHub-Soro--Boro-black.svg)](https://github.com/nisaral/Soro-Boro)

Soro-Kev-0.8B is an ultra-fast, sub-100ms System-One Pointer Model designed for edge devices, local AI assistants, MCP servers, and high-throughput routing pipelines.

Built on `Qwen/Qwen3.5-0.8B-Base`, it predicts tool selections and resolves schema arguments in a single forward prefill pass using hidden-state pointer attention, without generating text or slow JSON tokens.

```text
User Request + Candidate Tool Schemas
            │
            ▼  [Single Forward Prefill — 80ms on Laptop GPU / Edge]
    Hidden State Pointer Scoring: h_query · h_tool / T
            │
            ▼
    Softmax-LAC Conformal Prediction Set:
    ├── |S| = 1  ──▶  EXECUTE (Immediate safe action)
    ├── |S| > 1  ──▶  ASK     (Targeted clarification)
    └── Abstain  ──▶  ABSTAIN (Safe rejection)
```

---

## Technical Specifications

- **Edge Latency**: ~80 ms on consumer laptop GPU (sub-30ms on Linux kernels).
- **VRAM Footprint**: ~1,563 MB peak VRAM. Runs effortlessly alongside small LLMs on single GPUs or edge devices.
- **Zero Hallucination**: Points directly to registered tool candidates; cannot generate fictional names.
- **Calibrated Decision Set**: Uses split conformal prediction (`calibrated_q_hat = 0.9518`).
- **Universal Schema Support**: Compatible with MCP tools, Python signatures, REST/OpenAPI, and Agent Skills (`SKILL.md`).

---

## Quickstart

```python
from soro.harness.pipeline import SoroHarness

# Load 0.8B model directly from Hugging Face
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-0.8b")

@harness.tool(description="Check account balance for customer", side_effect="read_only")
def get_balance(customer_id: str) -> dict:
    return {"customer_id": customer_id, "balance_usd": 1420.50}

@harness.tool(description="Send payment transfer to recipient", side_effect="mutation")
def transfer_funds(to_user: str, amount: float) -> dict:
    return {"to_user": to_user, "amount": amount, "status": "transferred"}

# 80ms Fast Routing
decision = harness.route("Check how much money Alice has in her account")
print("Action:", decision.action)          # "EXECUTE"
print("Tool:", decision.selected_tool)     # "get_balance"

# Automatic argument normalization & execution
res = harness.execute("get_balance", {"customerId": "usr_992"})
print("Result:", res.data)
```

---

## Benchmark Results

Evaluated on an NVIDIA GeForce RTX 4050 Laptop GPU and Kaggle T4 GPUs using seed-42 slices (100 calibration / 200 test rows).

| Benchmark Split | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Routing Accuracy** | 47.50% | — | **84.50%** |
| **Zero-Shot Conformal Coverage** (Target: 90%) | 89.50% | — | **89.00%** |
| **Zero-Shot Mean Set Size** | 4.39 | — | **1.17** |
| **External Human Routing Accuracy** | 60.50% | 75.00% | **89.00%** |
| **BFCL Multiple (34 rows)** | 97.06% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | **96.97%** |
| **BFCL Irrelevance Abstain (33 rows)** | 3.03% | 81.82% | **57.58%** |
| **Argument Key Normalization** | 42.50% | — | **99.00%** |
| **Median Latency** | 0.31 ms | 110.95 ms | **80.01 ms** |
| **Peak VRAM** | 0 MB | 1,612 MB | **1,563 MB** |

---

## Citation & License

Released under the Apache-2.0 License.

```bibtex
@software{soro_kev_2026,
  author = {Keyush Nisar},
  title = {Soro-Kev: System-One Conformal Tool Router and Execution Boundary},
  year = {2026},
  url = {https://github.com/nisaral/Soro-Boro}
}
```
