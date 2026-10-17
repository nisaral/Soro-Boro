---
license: apache-2.0
base_model: Qwen/Qwen3-4B
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
  - qwen
datasets:
  - nisaralll/soro-universal-tool-harness
pipeline_tag: text-classification
---

# Soro-Kev-4B

## Model summary

Soro-Kev-4B is a flagship decision model for AI agent tool routing, multi-protocol schema normalization, and execution boundary control. It reads one document (the state: user prompt, conversational history, and registered tool schemas) and a set of typed questions about it, and returns a calibrated probability distribution over the options supplied with each question, in a single forward pass and without generating text.

It is built directly on top of Jared Palmer's Kev pointer architecture, addressing an explicit limitation documented in the original Kev model cards (*"Tool-call routing: its When2Call accuracy is below chance (0.133). Do not use it for tool-call routing"*). Soro-Kev-4B is fine-tuned specifically on the multi-protocol Universal Tool Harness, raising tool routing accuracy to 89.00% zero-shot and 94.50% on external human holdouts.

It consists of a LoRA adapter ($r=16, \alpha=32$) and a pointer head on `Qwen/Qwen3-4B`. In 4-bit NF4 quantization, it operates in ~4,048 MB VRAM with a median prefill latency of ~413 ms on an RTX 4050 Laptop GPU or Kaggle T4 GPU. It is intended for production AI agents, complex Model Context Protocol (MCP) tool catalogs (50+ tools), and backend API routing engines where generative LLM JSON hallucinations and latency overhead cannot be tolerated.

---

## Model details

| Field | Detail |
| :--- | :--- |
| **Developer** | Keyush Nisar ([github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro)) |
| **Model type** | Decision model: causal language-model backbone run prefill-only, with a pointer head over candidate options |
| **Backbone** | `Qwen/Qwen3-4B`: 36 layers, multi-head attention; frozen |
| **Adapter** | LoRA, rank 16, $\alpha$ 32, on attention projections and MLP layers |
| **Head** | Pointer head ($d=2560$): hidden-state projections score each option's closing token against the question's final token ($h_{query} \cdot h_{option} / T$) |
| **Precision** | Trained in bf16/fp16; served in NF4 4-bit (~4,048 MB VRAM) or fp16 (~8,200 MB VRAM); evaluated in fp32 |
| **Context length** | States of up to 32,768 tokens; training states were at most 4,096 tokens |
| **Validated context** | 8,192 tokens |
| **Calibration** | Learned temperature ($T = 1.62$) and split-conformal quantile ($q_{hat} = 0.8066$ at $1 - \alpha = 0.90$) |
| **Languages** | English (tool schemas, OpenAPI specs, MCP JSON-RPC, Python docstrings) |
| **License** | Apache-2.0 |
| **Version** | Soro-Kev 1.0 (release `v0.2.0`, 2026-10-17) |
| **Base Kev Ancestor** | Derived from pointer network methodology of [jaredpalmer/kev-0.8b](https://huggingface.co/jaredpalmer/kev-0.8b) |

---

## Input and Question Types

Soro-Kev-4B evaluates a state and any number of named questions across three typed categories:

| Type | Options | Output | Intended Purpose |
| :--- | :--- | :--- | :--- |
| **choice (`tool_route`)** | 1–255 candidate tool schemas + `__abstain__` | Probability per tool, top tool, and conformal prediction set $S$ | Selects the single correct tool to execute, or abstains |
| **choice (`arg_mapping`)** | Schema property keys + `__drop__` | Probability distribution over candidate property names | Maps unrecognized LLM argument keys to target schema parameters |
| **noul (`missing_required`)** | `yes` / `no` with descriptions | Probability that required arguments are missing | Determines whether harness must ask user before calling tool |
| **noul (`is_mutation`)** | `yes` / `no` with descriptions | Probability that action mutates external state | Classifies side-effect tier when MCP tool annotations are absent |

Each question is evaluated as its own forward path branching from the shared state hidden representation; questions cannot cross-contaminate one another, and the state prefix is computed once and cached.

---

## Intended Uses

- **Production AI Agent Tool Routing**: Selecting tools from large catalogs (50+ schemas) in single-pass inference without prompt token generation bloat.
- **Model Context Protocol (MCP) Server Gateways**: High-accuracy routing across heterogeneous tool protocols (MCP JSON, REST APIs, GraphQL, Python callables).
- **Conformal Action Boundary**: Generating calibrated prediction sets ($S$) where $|S| = 1$ triggers `EXECUTE`, $|S| \in [2, 8]$ triggers targeted `ASK` clarification, and `__abstain__` safely halts execution.
- **Out-of-Domain Rejection**: Calibrated abstention (75.76% on BFCL irrelevance slices) preventing agents from forcing tool executions on conversational or irrelevant queries.
- **Duplicate Mutation Protection**: Enforcing the 0-duplicate execution invariant under network transport faults when paired with the Soro-Boro execution boundary.

## Out-of-Scope Uses

- **Text generation, conversation, or creative writing**: The model runs in prefill-only mode and has no generative token decode loop.
- **Open-ended text synthesis**: The model selects and normalizes schemas; it does not author free-form documents.
- **Fully autonomous execution of high-risk actions**: Critical financial or destructive operations should always require operator confirmation (`ASK` / human-in-the-loop).
- **Languages other than English**: Non-English tool descriptions and prompts are not validated.

---

## How to Use

### 1. High-Level Python SDK (Soro Harness)

```python
from soro.harness.pipeline import SoroHarness

# Loads directly from Hugging Face in NF4 quantization (4 GB VRAM)
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up customer order details", side_effect="read_only")
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

# Execute with Automatic Argument Coercion
result = harness.execute("get_order_status", {"order_id": "ORD-1092"})
print("Execution Result:", result.data)
```

### 2. Low-Level In-Process Scorer

```python
from soro.routing.kev_local import LocalKevScorer

scorer = LocalKevScorer(run="nisaralll/soro-kev-4b", backend="neural")
scorer.load()

state = "User Request: Check available disk storage in /var/log"
questions = {
    "tool_route": {
        "type": "choice",
        "instructions": "Which tool should execute for this request?",
        "criteria": {
            "get_disk_usage": "Return total, used, and available disk storage for path.",
            "list_processes": "List active system processes and PIDs.",
            "__abstain__": "None of the listed tools fit."
        }
    }
}

result = scorer.evaluate_turn(state, questions)
print(result["answers"]["tool_route"])  # "get_disk_usage"
```

---

## Training Data

Soro-Kev-4B was trained on the `nisaralll/soro-universal-tool-harness` collection across four distinct protocol domains:

| Stage | Records | Content & Protocol Families |
| :--- | :--- | :--- |
| **Stage 1: Multi-Protocol Tool Routing** | 24,180 | Real and synthetic tool catalogs: MCP JSON-RPC schemas (System, Filesystem, Memory, Fetch, SQLite), OpenAPI v3 / REST operations (Stripe, GitHub REST, Petstore), Agent Skills (`SKILL.md` format from Tau2 Telecom), and Python signatures. Option orders shuffled with negative `__abstain__` distractors. |
| **Stage 2: Schema Repair & Argument Mapping** | 8,450 | Mapping malformed or unrecognized LLM parameter keys (`client_id`, `usr`, `key`) to ground truth schema property names, plus `__drop__` targets for hallucinated parameters. |
| **Stage 3: Side-Effect & Mutation Classification** | 5,200 | Binary classification of mutating vs read-only operations across unannotated tools to verify execution safety boundaries. |

Evaluation suites (BFCL converted holdout, external human queries, and 200-row zero-shot holdouts) were strictly excluded from training.

---

## Evaluation Results

Evaluated on an NVIDIA GeForce RTX 4050 Laptop GPU (6GB) and Kaggle T4 GPUs in fp32 mode at the calibrated temperature ($T = 1.62$).

### Tool Routing Accuracy & Conformal Efficiency

| Benchmark Split | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-4B (Flagship) |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Route Accuracy (200 rows)** | 47.50% | — | **89.00%** |
| **Zero-Shot Conformal Coverage** (Nominal: 90%) | 89.50% | — | **93.00%** |
| **Zero-Shot Mean Prediction Set Size** | 4.39 | — | **1.11** |
| **External Human Route Accuracy (200 rows)** | 60.50% | 75.00% | **94.50%** |
| **External Human Conformal Coverage** | 95.50% | — | **95.00%** |
| **External Human Mean Prediction Set Size** | 4.18 | — | **1.07** |
| **Argument Key Normalization Rate** | 42.50% | — | **100.0%** |
| **Median Inference Latency (Prefill Only)** | 0.31 ms | 110.95 ms | **413.18 ms** (NF4) |
| **Peak GPU VRAM** | 0 MB | 1,612 MB | **4,048 MB** (NF4) |

### Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-4B (Flagship) |
| :--- | :--- | :--- | :--- |
| **BFCL Multiple Tools (34 rows)** | 97.06% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | **96.97%** |
| **BFCL Irrelevance Abstention (33 rows)** | 3.03% | 81.82% | **75.76%** |

### Accuracy by Schema Format (200-Row External Human Slice)

- **Agent Skills (`SKILL.md`)**: 100.0% (29/29)
- **GraphQL RPC**: 96.8% (30/31)
- **REST / OpenAPI**: 96.2% (25/26)
- **Mixed / Heterogeneous Catalogs**: 94.6% (35/37)
- **MCP JSON-RPC**: 94.4% (34/36)
- **Python Signatures**: 87.8% (36/41)

---

## Limitations and Trade-Offs

- **Higher VRAM than 0.8B**: Soro-Kev-4B requires ~4,048 MB in NF4 4-bit quantization, making Soro-Kev-0.8B preferable for memory-constrained edge devices (<2 GB VRAM).
- **Prefill Latency**: Median prefill latency is ~413 ms in NF4 on laptop hardware; for sub-100ms ultra-low latency, use Soro-Kev-0.8B (~80 ms).
- **No generative argument synthesis**: Soro-Kev normalizes and routes arguments; it does not author free-form open-ended text strings.
- **Option order sensitivity**: While option order is randomized during training, slight score variances ($< 1.5\%$) can occur based on option presentation order.

---

## Provenance and Reproducibility

- **Repository**: [github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro) (release tag `v0.2.0`)
- **Trained Checkpoint**: Adapter weights and `head.pt` with learned temperature ($T = 1.62$)
- **Harness Dataset**: [huggingface.co/datasets/nisaralll/soro-universal-tool-harness](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)

---

## Citations

If you use Soro-Kev in your research or production systems, please cite both Soro-Kev and the underlying Kev decision model architecture:

```bibtex
@software{nisar2026sorokev,
  author = {Nisar, Keyush},
  title = {Soro-Kev: System-One Conformal Tool Router and Execution Boundary},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/nisaral/Soro-Boro}},
  note = {Release v0.2.0}
}

@misc{palmer2026kev08b,
  author = {Palmer, Jared},
  title = {Kev-0.8B: a calibrated decision model on Qwen3.5-0.8B},
  year = {2026},
  howpublished = {\url{https://huggingface.co/jaredpalmer/kev-0.8b}},
  note = {Kev 1.0}
}
```
