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

It is built directly on top of Jared Palmer's Kev pointer architecture, addressing an explicit limitation documented in the original Kev-0.8B model card (*"Tool-call routing: its When2Call accuracy is below chance (0.133). Do not use it for tool-call routing"*). Soro-Kev-0.8B is trained specifically on multi-protocol tool catalogs (Model Context Protocol, REST/OpenAPI, Agent Skills, and Python signatures), raising tool routing accuracy to 84.50% zero-shot and 89.00% on held-out, independently authored holdouts.

It consists of a LoRA adapter ($r=16, \alpha=32$) and a pointer head on `Qwen/Qwen3.5-0.8B-Base`. It runs in ~80 ms on an NVIDIA GeForce RTX 4050 Laptop GPU (1,563 MB peak VRAM, PyTorch 2.6.0). It is intended for edge deployment, local MCP desktop sidecars, and high-frequency routing pipelines where generative LLM token generation latency is prohibitive.

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

Soro-Kev-0.8B was trained on the `nisaralll/soro-universal-tool-harness` dataset (`train.jsonl`), consisting of exactly **23,192 multi-task state rows** representing **115,960 question-level supervision targets** across its 5 concurrent heads:

| Stage / Curriculum Focus | Question Targets | Content & Protocol Families |
| :--- | :--- | :--- |
| **Stage 1: Multi-Protocol Tool Routing** | 24,180 | Real and synthetic tool catalogs: MCP JSON-RPC schemas (System, Filesystem, Memory, Fetch, SQLite), OpenAPI v3 / REST operations (Stripe, GitHub REST, Petstore), Agent Skills (`SKILL.md` format), and Python signatures. 23,192 primary states + 988 permutation augmentations with negative `__abstain__` distractors. |
| **Stage 2: Schema Repair & Argument Mapping** | 8,450 | Active question instances filtered to tools with parameter structures. Maps malformed or unrecognized LLM parameter keys (`client_id`, `usr`, `key`) to ground truth schema property names, plus `__drop__` targets for hallucinated parameters. |
| **Stage 3: Side-Effect & Mutation Classification** | 5,200 | Balanced 50/50 binary classification of mutating vs read-only operations across unannotated tools to verify execution safety boundaries. |

Evaluation suites (`val_external_human.jsonl` with 1,200 independently authored holdout queries, and `val_zeroshot.jsonl` with 2,220 queries across 54 unseen packages) are strictly disjoint and excluded from training, as verified by `scripts/verify_dataset_disjointness.py` and documented in `benchmarks/disjointness_audit.json`.

---

## Evaluation Results

Evaluated on an NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM, PCIe 4.0 x4, PyTorch 2.6.0, CUDA 12.4) in fp32 mode at the calibrated temperature ($T = 1.84$).

### Tool Routing Accuracy & Conformal Efficiency

| Benchmark Split | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Route Accuracy (200 rows)** | 47.50% | — | **84.50%** |
| **Zero-Shot Conformal Coverage** (Nominal: 90%) | 89.50% | — | **89.00%** |
| **Zero-Shot Mean Prediction Set Size** | 4.39 | — | **1.17** |
| **Independently Sourced Holdout Accuracy (200 rows)** | 60.50% | 75.00% | **89.00%** |
| **Independently Sourced Conformal Coverage** | 95.50% | — | **95.50%** |
| **Independently Sourced Mean Prediction Set Size** | 4.18 | — | **1.18** |
| **Argument Key Normalization Rate** | 42.50% | — | **99.00%** |
| **Median Inference Latency (Prefill Only)** | 0.31 ms | 110.95 ms | **80.01 ms** |
| **Peak GPU VRAM** | 0 MB | 1,612 MB | **1,563 MB** |

> **Pointer Network Guarantee**: Restricts candidate selection strictly to the closed candidate set + `__abstain__` (0% invalid or invented tool-name generation). The empirical misclassification rate ($1 - \text{Top-1 Accuracy}$) is 11.00% on independently sourced holdouts and 15.50% on zero-shot holdouts.

### Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B |
| :--- | :--- | :--- | :--- |
| **BFCL Multiple Tools (34 rows)** | 97.06% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | **96.97%** |
| **BFCL Irrelevance Abstention (33 rows)** | 3.03% | 81.82% | **57.58%** |

---

## Limitations and Trade-Offs

- **No Generative Argument Synthesis**: Soro-Kev normalizes parameter keys and checks argument completeness; it does not author free-text string values. In production pipelines, arguments are drafted by a fast parameter extractor, normalized via `arg_mapping`, and guarded by `missing_required` before execution.
- **Single-Turn Model**: Soro-Kev evaluates single routing turns. Multi-tool sequential chaining ("call tool A, then tool B") is an architectural runtime design and has not yet been benchmarked on multi-step traces.
- **Edge Model Capacity**: With 0.8B parameters, out-of-domain transfer on complex multi-hop semantic reasoning is lower than Soro-Kev-4B (89.0% vs 94.5% on external holdouts).
- **Abstention Sensitivity**: On BFCL irrelevance slices where queries closely resemble registered tools, Soro-Kev-0.8B abstains 57.58% of the time, compared to 75.76% for Soro-Kev-4B. For strict zero-tolerance out-of-domain rejection, use Soro-Kev-4B.

---

## Provenance and Reproducibility

- **Repository**: [github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro) (release tag `v0.2.0`)
- **Trained Checkpoint**: Adapter weights and `head.pt` with learned temperature ($T = 1.84$) and global conformal quantile ($q_{hat} = 0.9518$)
- **Harness Dataset**: [huggingface.co/datasets/nisaralll/soro-universal-tool-harness](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
- **Disjointness Audit**: Committed in `benchmarks/disjointness_audit.json`

---

## Citations

If you use Soro-Kev or Universal Tool Harness in your research or production systems, please cite the following publications:

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

@inproceedings{shi2025toolret,
  author = {Shi, Jiahao and others},
  title = {ToolRet: A Benchmark for Tool Retrieval in Large Language Models},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2025},
  year = {2025}
}

@article{mo2025livemcpbench,
  author = {Mo, Guozhao and others},
  title = {LiveMCPBench: Can Agents Navigate an Ocean of MCP Tools?},
  journal = {arXiv preprint arXiv:2508.01780},
  year = {2025}
}

@inproceedings{ross2025when2call,
  author = {Ross, Hayley and Mahabaleshwarkar, Ameya Sunil and Suhara, Yoshi},
  title = {When2Call: When (not) to Call Tools},
  booktitle = {Proceedings of the 2025 Conference of the North American Chapter of the Association for Computational Linguistics (NAACL)},
  year = {2025}
}
```


