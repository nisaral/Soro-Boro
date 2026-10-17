---
license: apache-2.0
task_categories:
  - text-classification
tags:
  - tool-calling
  - mcp
  - conformal-prediction
size_categories:
  - 10K<n<100K
---

# Soro universal tool harness

Routing rows for a pointer model. Each line is one state plus System-One questions. The model does not emit a tool-call string. It points at a listed option.

## Files

| File | Rows | Delexicalized `op_N` rows |
|---|---|---|
| `train.jsonl` | 23,192 | 5,853 (25.2%) |
| `val_zeroshot.jsonl` | 2,220 | 693 (31.2%) |
| `val_external_human.jsonl` | 1,200 | 0 |

`val_external_human.jsonl` is held-out human tool text (tau2 and MCP-style sources). It is not the delexicalized catalog.

## Formats

`mcp_json`, `agent_skill`, `rest_openapi`, `python_sig`, `graphql_rpc`, `mixed_heterogeneous`.

Train counts: REST 3,821, GraphQL 3,754, Python 3,865, agent skill 4,008, MCP JSON 3,876, mixed 3,868.

## Questions

- `tool_route`: one listed tool, or `__abstain__`
- `tool_route_perm`: the same choice with options reordered
- `arg_mapping`: which schema field a stray argument name fills
- `missing_required`: yes/no
- `is_mutation`: yes/no
- `intent`: `single`, `multi`, or `none` when the row has that field

Zero-shot val rows are tools that do not appear as the training target. That is a tool-identity split, not a claim that no string is shared with train.
