---
license: apache-2.0
task_categories:
  - text-classification
tags:
  - tool-calling
  - function-calling
  - mcp
  - model-context-protocol
  - agent-harness
  - conformal-prediction
  - pointer-network
  - decision-model
size_categories:
  - 10K<n<100K
---

# Soro Universal Tool Harness Dataset

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Models](https://img.shields.io/badge/Trained_Models-Soro--Kev--4B_&_0.8B-purple.svg)](https://huggingface.co/nisaralll/soro-kev-4b)
[![GitHub](https://img.shields.io/badge/GitHub-Soro--Boro-black.svg)](https://github.com/nisaral/Soro-Boro)

The Soro Universal Tool Harness dataset contains high-quality, multi-format routing, argument repair, and safety classification records designed for training and calibrating System-One pointer routers.

Unlike standard function-calling datasets that train models to emit token-by-token JSON strings, this dataset formats agent tasks as System-One Pointer Queries over explicit option lists, enabling zero-hallucination routing and split-conformal coverage guarantees.

---

## Files & Split Breakdown

| Split File | Rows | Delexicalized (`op_N`) | Real-World & Human Held-Out |
| :--- | :--- | :--- | :--- |
| **`train.jsonl`** | 23,192 | 5,853 (25.2%) | Real MCP, REST, GraphQL, Agent Skills, Python |
| **`val_zeroshot.jsonl`** | 2,220 | 693 (31.2%) | Tools never seen during training (strict tool-identity split) |
| **`val_external_human.jsonl`** | 1,200 | 0 (0.0%) | Completely held-out human user queries (Tau-2 & live MCP benchmarks) |

---

## Supported Schema Formats

The dataset balances 6 diverse tool declaration formats to prevent syntactic overfitting:

1. **`mcp_json`**: Model Context Protocol JSON-RPC tool schemas.
2. **`agent_skill`**: Agent Skills and `SKILL.md` plugin definitions with command formats and triggers.
3. **`rest_openapi`**: OpenAPI v3 REST endpoints (HTTP methods + path templates).
4. **`python_sig`**: Standard Python function signatures and type annotations.
5. **`graphql_rpc`**: GraphQL query/mutation RPC schemas.
6. **`mixed_heterogeneous`**: Real-world catalogs combining multiple formats simultaneously.

---

## Task Questions in Each Row

Each row provides a user state and query alongside options for:

1. **`tool_route`**: Pointer choice selecting the correct candidate tool, or `__abstain__` when the request cannot be fulfilled.
2. **`tool_route_perm`**: Permuted order of the same tool candidates to enforce order-invariance.
3. **`arg_mapping`**: Maps misnamed or stray argument keys back to canonical schema fields.
4. **`missing_required`**: Binary prediction of whether mandatory arguments are missing from user context.
5. **`is_mutation`**: Side-effect classification (whether the tool performs non-idempotent state mutations).
6. **`intent`**: Multi-tool intent detection (`single`, `multi`, or `none`).

---

## Loading with Hugging Face Datasets

```python
from datasets import load_dataset

dataset = load_dataset("nisaralll/soro-universal-tool-harness")
print(dataset["train"][0])
```

Or read directly with `json` in Python:

```python
import json
from huggingface_hub import hf_hub_download

file_path = hf_hub_download(
    repo_id="nisaralll/soro-universal-tool-harness",
    filename="val_external_human.jsonl",
    repo_type="dataset"
)

with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        print("Query:", row["state"])
        print("Gold Tool:", row["gold_tool"])
        break
```

---

## Citation & License

Released under the Apache-2.0 License.
