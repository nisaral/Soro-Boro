---
license: apache-2.0
base_model: Qwen/Qwen3-4B
tags:
  - tool-calling
  - function-calling
  - mcp
  - model-context-protocol
  - agent-harness
  - pointer-network
  - conformal-prediction
  - system-one
  - edge-ai
  - qwen
datasets:
  - nisaralll/soro-universal-tool-harness
pipeline_tag: text-classification
---

# 🦅 Soro-Kev-4B: System-One Conformal Tool Router

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Base Model](https://img.shields.io/badge/Base_Model-Qwen3--4B-purple.svg)](https://huggingface.co/Qwen/Qwen3-4B)
[![Dataset](https://img.shields.io/badge/Dataset-soro--universal--tool--harness-green.svg)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
[![GitHub](https://img.shields.io/badge/GitHub-Soro--Boro-black.svg)](https://github.com/nisaral/Soro-Boro)

**Soro-Kev-4B** is a high-accuracy, ultra-fast **System-One Pointer Model** for AI agents, Model Context Protocol (MCP) servers, REST APIs, and developer toolchains.

Instead of generating slow, token-by-token JSON strings that consume large context windows and hallucinate tool names, Soro-Kev uses a **single forward prefill pass** over the candidate tools. It computes dot-product attention between question-end hidden states and option-end hidden states, applying **split conformal prediction** to guarantee calibrated decision-making.

```text
User Request + Registered Tool Schemas
            │
            ▼  [Single Forward Prefill — 413ms on Laptop GPU]
    Hidden State Dot-Product: h_query · h_tool / T
            │
            ▼
    Softmax-LAC Conformal Prediction Set S:
    ├── |S| = 1 and tool != __abstain__  ──▶  EXECUTE (Immediate safe action)
    ├── |S| ∈ [2, 8]                     ──▶  ASK     (Ambiguity / clarification)
    └── |S| is empty or __abstain__      ──▶  ABSTAIN (Out-of-domain safe rejection)
```

---

## ⚡ Why Use Soro-Kev Instead of LLM Tool Generation?

| Feature | Standard Autoregressive LLM | **Soro-Kev-4B** |
| :--- | :--- | :--- |
| **Inference Mechanism** | Multi-token JSON generation | **Single prefill pointer pass** |
| **Latency** | 1,500 ms – 4,000 ms | **~413 ms** (NF4 on RTX 4050 / T4) |
| **Tool Name Hallucinations** | Common (invents fictional tools) | **0% Mathematically Impossible** (points to listed set) |
| **50+ Tool Scalability** | Severe prompt-bloat & accuracy drop | **Pre-filters + scores without degradation** |
| **Out-of-Domain Safety** | Frequently triggers wrong tools | **Calibrated Abstention (`__abstain__`)** |
| **Duplicate Mutation Loop Guard**| None (relies on agent self-control)| **120s Deduplication & Idempotency Store** |
| **Memory Footprint** | 8 GB – 16 GB VRAM | **~4,048 MB VRAM** (NF4 with bitsandbytes) |

---

## 📦 Quick Installation

Install Soro with the lightweight developer extras:

```bash
pip install "git+https://github.com/nisaral/Soro-Boro.git#subdirectory=veyra/python"
# or install dependencies directly:
pip install torch transformers peft bitsandbytes accelerate
```

---

## 🚀 Practical Use Cases

### 1. Python Agent Tool Routing & Execution

Define standard Python functions with side-effect annotations. Soro routes natural language to the right tool, auto-coerces argument types, and executes safely:

```python
from soro.harness.pipeline import SoroHarness

# Loads directly from Hugging Face in NF4 quantization
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up a customer order details", side_effect="read_only")
def get_order_status(order_id: str) -> dict:
    return {"order_id": order_id, "status": "shipped", "tracking": "TRK-9810"}

@harness.tool(description="Cancel a warehouse shipment", side_effect="mutation")
def cancel_shipment(order_id: str) -> dict:
    return {"order_id": order_id, "cancelled": True}

# Fast Conformal Routing
decision = harness.route("Where is my package for order ORD-1092?")
print("Decision Action:", decision.action)          # "EXECUTE"
print("Selected Tool:", decision.selected_tool)     # "get_order_status"
print("Confidence:", decision.probabilities.get("get_order_status"))

# Execute with Automatic Argument Coercion (strings, casing, types)
result = harness.execute("get_order_status", {"order_id": "ORD-1092"})
print("Execution Result:", result.data)
```

---

### 2. Out-of-Domain Abstention & Ambiguity Clarification

Prevent catastrophic tool execution when the user asks something completely outside your toolset or when two tools are equally valid:

```python
# Query outside the catalog (e.g., cooking query when tools are shipping-related)
decision = harness.route("Can you give me a recipe for chocolate soufflé?")

print(decision.action)          # "ABSTAIN"
print(decision.selected_tool)   # None
print(decision.reason)          # "Neural scorer abstained (p=0.89)"

# Ambiguous query matching multiple tools (e.g. Jira vs Linear)
harness.register_action("jira_create_issue", "Create issue ticket in Jira", {"title": str})
harness.register_action("linear_create_issue", "Create issue ticket in Linear", {"title": str})

ambiguous_decision = harness.route("Create a bug ticket for login error")
print(ambiguous_decision.action)       # "ASK"
print(ambiguous_decision.candidates)   # ["jira_create_issue", "linear_create_issue"]
```

---

### 3. Model Context Protocol (MCP) Server Integration

Audit and route tools exposed by any standard MCP server over stdio or HTTP:

```python
from soro.harness.pipeline import SoroHarness

harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

# Register tools directly from an MCP JSON Schema definition
mcp_tool_schema = {
    "name": "filesystem_read_file",
    "description": "Read complete content of a file from filesystem",
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"]
    }
}

harness.register_mcp_tool(
    name=mcp_tool_schema["name"],
    description=mcp_tool_schema["description"],
    parameters=mcp_tool_schema["parameters"],
    fn=lambda path: {"content": f"Mock file content of {path}"},
    side_effect="read_only"
)

res = harness.route("Read the configuration from /etc/hosts")
print(res.selected_tool)  # "filesystem_read_file"
```

---

### 4. Multi-Tool Workflow Chaining with Context Dataflow

Chain multi-clause queries automatically. Soro extracts outputs from read operations and feeds them forward into subsequent mutations:

```python
# Multi-clause query: read order, then cancel shipment
trace = harness.run_workflow(
    "Check order ORD-774, and if pending cancel its warehouse shipment."
)

for step in trace:
    print(f"[{step['action']}] Tool: {step.get('tool')} -> Output: {step.get('data')}")
```

---

### 5. Pure PyTorch & Transformers Loading (No Harness Required)

If you prefer to inspect raw logits or integrate directly into your own runtime:

```python
import torch
from transformers import AutoTokenizer, AutoModel, BitsAndBytesConfig
from peft import PeftModel
from huggingface_hub import snapshot_download

repo_id = "nisaralll/soro-kev-4b"
weights_dir = snapshot_download(repo_id)

# 1. Load backbone in 4-bit NF4
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B", trust_remote_code=True)
base_model = AutoModel.from_pretrained("Qwen/Qwen3-4B", quantization_config=bnb_config, device_map="auto")

# 2. Attach PEFT LoRA adapter
model = PeftModel.from_pretrained(base_model, weights_dir)

# 3. Load Pointer Scoring Head
head_weights = torch.load(f"{weights_dir}/head.pt", map_location="cuda")
print("Soro-Kev-4B initialized successfully!")
```

---

## 📊 Evaluation & Benchmark Results

Evaluated on an **NVIDIA GeForce RTX 4050 Laptop GPU (6GB)** and **Kaggle T4 GPUs** using seed-42 slices (100 calibration / 200 test rows).

### Zero-Shot & External Human Benchmark

| Benchmark Split | Heuristic Baseline | Jared Palmer Kev-0.8B | **Soro-Kev-4B** |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Routing Accuracy** | 47.50% | — | **89.00%** |
| **Zero-Shot Conformal Coverage** (Target: 90%) | 89.50% | — | **93.00%** |
| **Zero-Shot Mean Set Size** | 4.39 | — | **1.11** |
| **External Human Routing Accuracy** | 60.50% | 75.0% | **94.50%** |
| **External Human Conformal Coverage** | 95.50% | — | **95.00%** |
| **External Human Mean Set Size** | 4.18 | — | **1.07** |
| **Argument Key Normalization** | 42.50% | — | **100.0%** |

### BFCL Routing Benchmark (Berkeley Function Calling Converted Slice)

| Category (100 rows total) | Heuristic | Jared Palmer Kev-0.8B | **Soro-Kev-4B** |
| :--- | :--- | :--- | :--- |
| **Multiple Tools (34 rows)** | 97.06% | 100.0% | **100.0%** |
| **Live Multiple (33 rows)** | 75.76% | 69.70% | **96.97%** |
| **Irrelevance / Out-of-Domain (33 rows)** | 3.03% | 81.82% | **75.76%** |

### Accuracy by Schema Format (200-row External Slice)

- **Agent Skills (`SKILL.md`)**: `100.0%` (29/29)
- **GraphQL RPC**: `96.8%` (30/31)
- **REST / OpenAPI**: `96.2%` (25/26)
- **Mixed / Heterogeneous**: `94.6%` (35/37)
- **MCP JSON-RPC**: `94.4%` (34/36)
- **Python Signatures**: `87.8%` (36/41)

---

## ⚙️ Model Details & Calibration

- **Base Architecture**: `Qwen/Qwen3-4B`
- **Adapter**: LoRA ($r=16, \alpha=32$) trained on Universal Tool Harness
- **Scoring Head**: Question-to-Option pointer network ($d=2560$)
- **Conformal Calibration**: Split-conformal quantile `calibrated_q_hat = 0.8066` ($1 - \alpha = 0.90$)
- **Inference Latency**: Median **413 ms** (RTX 4050 NF4)
- **VRAM Requirements**: **4,048 MB** (NF4) / 8,200 MB (FP16)

---

## 📜 Citation & License

Released under the **Apache-2.0 License**.

```bibtex
@software{soro_kev_2026,
  author = {Keyush Nisar},
  title = {Soro-Kev: System-One Conformal Tool Router and Execution Boundary},
  year = {2026},
  url = {https://github.com/nisaral/Soro-Boro}
}
```
