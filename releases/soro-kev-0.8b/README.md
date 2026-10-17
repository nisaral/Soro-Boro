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

# Soro-Kev-0.8B

[![Interactive Space Demo](https://img.shields.io/badge/Hugging%20Face-Interactive%20Space%20Demo-blue)](https://huggingface.co/spaces/nisaralll/soro-kev-router)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Soro--Boro-black)](https://github.com/nisaral/Soro-Boro)
[![Dataset](https://img.shields.io/badge/Dataset-Universal%20Tool%20Harness-green)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)

## Model summary

Soro-Kev-0.8B is a specialized decision model for AI agent tool routing, schema normalization, and execution boundary control. It reads one document (the state: user prompt, conversational history, and available tool schemas) and a set of typed questions about it, and returns a calibrated probability distribution over the options supplied with each question, in a single forward pass and without generating text.

It is built directly on top of Jared Palmer's Kev pointer architecture, addressing an explicit limitation documented in the original Kev-0.8B model card (*"Tool-call routing: its When2Call accuracy is below chance (0.133). Do not use it for tool-call routing"*). Soro-Kev-0.8B is trained specifically on multi-protocol tool catalogs (Model Context Protocol, REST/OpenAPI, Agent Skills, and Python signatures), raising tool routing accuracy to 84.50% zero-shot and 89.00% on external human holdouts.

It consists of a LoRA adapter ($r=16, \alpha=32$) and a pointer head on `Qwen/Qwen3.5-0.8B-Base`. It runs in ~80 ms on a laptop GPU or 4 GB GPU (1,563 MB peak VRAM). It is intended for edge deployment, local MCP desktop sidecars, and high-frequency routing pipelines where generative LLM token generation latency is prohibitive.

---

## Model details

| Field | Detail |
| :--- | :--- |
| **Developer** | Keyush Nisar ([github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro)) |
| **Model type** | Decision model: causal language-model backbone run prefill-only, with a pointer head over candidate options |
| **Backbone** | `Qwen/Qwen3.5-0.8B-Base`: 24 layers (18 Gated DeltaNet linear attention, 6 full attention); frozen |
| **Adapter** | LoRA, rank 16, $\alpha$ 32, on attention, MLP, and DeltaNet projections (11.3M parameters) |
| **Head** | Pointer head: hidden-state projections score each option's closing token against the question's final token ($h_{query} \cdot h_{option} / T$) |
| **Precision** | Trained in bf16/fp16; served in bf16 (merged at load) or fp32; evaluated in fp32 |
| **Context length** | States of up to 32,768 tokens; training states were at most 4,096 tokens |
| **Validated context** | 8,192 tokens |
| **Calibration** | One temperature ($T = 1.84$) and split-conformal threshold ($q_{hat} = 0.9518$ at $1 - \alpha = 0.90$) |
| **Languages** | English (prose, tool descriptions, OpenAPI schemas, JSON-RPC, Python docstrings) |
| **License** | Apache-2.0 |
| **Version** | Soro-Kev 1.0 (release `v0.2.0`, 2026-10-17) |
| **Base Kev Ancestor** | Derived from pointer network methodology of [jaredpalmer/kev-0.8b](https://huggingface.co/jaredpalmer/kev-0.8b) |

---

## Input and Question Types

Soro-Kev-0.8B evaluates a state and any number of named questions across three typed categories:

| Type | Options | Output | Intended Purpose |
| :--- | :--- | :--- | :--- |
| **choice (`tool_route`)** | 1–255 candidate tool schemas + `__abstain__` | Probability per tool, top tool, and conformal prediction set $S$ | Selects the single correct tool to execute, or abstains |
| **choice (`arg_mapping`)** | Schema property keys + `__drop__` | Probability distribution over candidate property names | Maps unrecognized LLM argument keys to target schema parameters |
| **noul (`missing_required`)** | `yes` / `no` with descriptions | Probability that required arguments are missing | Determines whether harness must ask user before calling tool |
| **noul (`is_mutation`)** | `yes` / `no` with descriptions | Probability that action mutates external state | Classifies side-effect tier when MCP tool annotations are absent |

Each question is evaluated as its own forward path branching from the shared state hidden representation; questions cannot cross-contaminate one another, and the state prefix is computed once and cached.

---

## Intended Uses

- **AI Agent Tool Routing**: Selecting tools from catalogs of 10 to 100+ schemas in sub-100ms without consuming context tokens on JSON generation.
- **Model Context Protocol (MCP) Sidecars**: Routing queries to local tools exposed by MCP servers over stdio or SSE.
- **Conformal Action Boundary**: Generating calibrated prediction sets ($S$) where $|S| = 1$ triggers `EXECUTE`, $|S| \in [2, 8]$ triggers targeted `ASK` clarification, and `__abstain__` safely halts execution.
- **On-Device & Edge Routing**: Running alongside small edge LLMs on consumer laptops, Apple Silicon, or 4 GB GPUs.
- **Duplicate Mutation Protection**: When integrated with the Soro-Boro execution boundary, enforcing the 0-duplicate execution invariant under network dropouts.

## Out-of-Scope Uses

- **Text generation, conversation, or creative writing**: The model runs in prefill-only mode and has no generative token decode loop.
- **Arbitrary general classification without tools**: Out of domain on tasks unlike its training families (e.g. sentiment classification or narrative analysis), where general models like Kev-0.8B or Kev-4B should be used.
- **Fully autonomous execution of high-risk actions**: Financial transfers, database drops, or administrative actions should always require operator confirmation (`ASK` / human-in-the-loop).
- **Languages other than English**: Non-English tool descriptions and prompts are not validated.

---

## How to Use

### 1. High-Level Python SDK (Soro Harness)

```python
from soro.harness.pipeline import SoroHarness

# Load checkpoint from Hugging Face
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-0.8b")

@harness.tool(description="Check account balance for customer", side_effect="read_only")
def get_balance(customer_id: str) -> dict:
    return {"customer_id": customer_id, "balance_usd": 1420.50}

@harness.tool(description="Issue partial or full refund for settled order", side_effect="mutation")
def refund_order(order_id: str, amount: float) -> dict:
    return {"order_id": order_id, "refunded": amount}

# Sub-100ms Conformal Routing
decision = harness.route("Refund customer $45.00 for order ORD-9921")
print(decision.action)          # "EXECUTE"
print(decision.selected_tool)   # "refund_order"
print(decision.candidates)      # ["refund_order"] (Prediction set |S| = 1)
```

### 2. Low-Level In-Process Scorer

```python
from soro.routing.kev_local import LocalKevScorer

scorer = LocalKevScorer(run="nisaralll/soro-kev-0.8b", backend="neural")
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
print(result["probabilities"]["tool_route"])
```

---

## Training Data

Soro-Kev-0.8B was trained on the `nisaralll/soro-universal-tool-harness` collection across four distinct protocol domains:

| Stage | Records | Content & Protocol Families |
| :--- | :--- | :--- |
| **Stage 1: Multi-Protocol Tool Routing** | 24,180 | Real and synthetic tool catalogs: MCP JSON-RPC schemas (System, Filesystem, Memory, Fetch, SQLite), OpenAPI v3 / REST operations (Stripe, GitHub REST, Petstore), Agent Skills (`SKILL.md` format from Tau2 Telecom), and Python signatures. Option orders shuffled with negative `__abstain__` distractors. |
| **Stage 2: Schema Repair & Argument Mapping** | 8,450 | Mapping malformed or unrecognized LLM parameter keys (`client_id`, `usr`, `key`) to ground truth schema property names, plus `__drop__` targets for hallucinated parameters. |
| **Stage 3: Side-Effect & Mutation Classification** | 5,200 | Binary classification of mutating vs read-only operations across unannotated tools to verify execution safety boundaries. |

Evaluation suites (BFCL converted holdout, external human queries, and 200-row zero-shot holdouts) were strictly excluded from training.

---

## Evaluation Results

Every benchmark was evaluated on an NVIDIA GeForce RTX 4050 Laptop GPU (6GB) and Kaggle T4 GPUs in fp32 mode at the calibrated temperature ($T = 1.84$).

### Tool Routing Accuracy & Conformal Efficiency

| Benchmark Split | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Route Accuracy (200 rows)** | 47.50% | — | **84.50%** |
| **Zero-Shot Conformal Coverage** (Nominal: 90%) | 89.50% | — | **89.00%** |
| **Zero-Shot Mean Prediction Set Size** | 4.39 | — | **1.17** |
| **External Human Route Accuracy (200 rows)** | 60.50% | 75.00% | **89.00%** |
| **External Human Conformal Coverage** | 95.50% | — | **95.50%** |
| **External Human Mean Prediction Set Size** | 4.18 | — | **1.18** |
| **Argument Key Normalization Rate** | 42.50% | — | **99.00%** |
| **Median Inference Latency (Prefill Only)** | 0.31 ms | 110.95 ms | **80.01 ms** |
| **Peak GPU VRAM** | 0 MB | 1,612 MB | **1,563 MB** |

### Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B |
| :--- | :--- | :--- | :--- |
| **BFCL Multiple Tools (34 rows)** | 97.06% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | **96.97%** |
| **BFCL Irrelevance Abstention (33 rows)** | 3.03% | 81.82% | **57.58%** |

---

## Limitations and Trade-Offs

- **Edge model capacity**: With 0.8B parameters, out-of-domain transfer on complex multi-hop semantic reasoning is lower than Soro-Kev-4B (89.0% vs 94.5% on external holdouts).
- **Abstention on ambiguous tools**: On BFCL irrelevance slices where queries closely resemble registered tools, Soro-Kev-0.8B abstains 57.58% of the time, compared to 75.76% for Soro-Kev-4B. For strict zero-tolerance out-of-domain rejection, use Soro-Kev-4B.
- **No generative argument synthesis**: Soro-Kev extracts and normalizes existing argument keys; it does not synthesize free-form open-ended text strings from scratch.
- **Option order sensitivity**: While option order is shuffled during training, slight probability variations ($< 2\%$) can occur depending on option presentation order.

---

## Provenance and Reproducibility

- **Repository**: [github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro) (release tag `v0.2.0`)
- **Trained Checkpoint**: Adapter weights and `head.pt` with learned temperature ($T = 1.84$)
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
