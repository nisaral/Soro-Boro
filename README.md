# Soro

System-One tool router, argument repair, and an execution boundary for MCP servers, REST endpoints, SKILL.md plugins, Python functions, and GraphQL.

`Soro-Kev` does not generate a tool call. One prefill packs the user state and the listed tools. A pointer scores the question-end hidden state against each option-end hidden state:

```text
state + question
  [0] tool_a: schema
  [1] tool_b: schema
  [2] __abstain__: none of these
        |
        h_q  ·  h_opt   /  temperature
        |
        softmax  ->  one distribution over the list
        |
        split conformal set S
          |S|=1 and not abstain  -> EXECUTE
          |S| is abstain or empty -> ABSTAIN
          otherwise                -> ASK
```

A name that is not in the list cannot be chosen. There is no JSON to parse.

Multi-tool requests are still one pointer per clause. Tools whose raw logit beats `__abstain__` can form a plan. The harness runs reads before mutations, copies returned fields into later arguments, and stops with `ASK` when a required field is still empty. `@soro_wrap` blocks a duplicate mutation inside 120 seconds and treats a dropped provider ack as an unknown result instead of a blind retry.

## Quickstart

```python
from soro.harness.pipeline import SoroHarness

harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up a customer order", side_effect="read_only")
def get_order_status(order_id: str) -> dict:
    return {"order_id": order_id, "customer_email": "alice@acme.com", "shipment_id": "SHP-901"}

@harness.tool(description="Cancel a warehouse shipment", side_effect="mutation")
def cancel_shipment(shipment_id: str) -> dict:
    return {"shipment_id": shipment_id, "cancelled": True}

harness.register_rest(
    endpoint="/invoices/{invoice_id}",
    method="GET",
    description="Fetch an invoice",
    parameters={"invoice_id": str},
)
harness.register_skill(
    "deploy_skill",
    description="Deploy a service version",
    triggers=["deploy"],
    parameters={"service": str, "version": str},
    side_effect="mutation",
)

print(harness.route("look up order ORD-774").action)
print(harness.run_workflow(
    "Look up order ORD-774, then cancel its shipment."
))
```

A local folder works: `SoroHarness.from_pretrained("releases/soro-kev-4b")`. A Hub id is downloaded with `snapshot_download`. CUDA with `bitsandbytes` loads the 4B checkpoint as NF4. Otherwise the loader uses bf16, then fp16.

`soro-audit` lints an MCP server over stdio. From `veyra/`:

```text
soro-audit --stdio "npx -y @modelcontextprotocol/server-filesystem /tmp" --dry-run
```

## What was measured

These are local RTX 4050 runs. They are not an official Berkeley Function Calling leaderboard submission. The official board scores full AST and executable calls. The BFCL numbers below are tool-name accuracy on our converted rows.

Seed-42 slice, 100 calibration rows and 200 test rows, shared by all three columns.

| `val_zeroshot.jsonl` | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| Route accuracy | 47.50% | 84.50% | 89.00% |
| Coverage (target 90%) | 89.50% | 89.00% | 93.00% |
| Mean set size | 4.39 | 1.17 | 1.11 |
| Argument mapping | 42.50% | 99.00% | 99.00% |
| Missing-argument detection | 50.00% | 85.50% | 71.00% |
| Mutation classification | 63.00% | 88.50% | 92.50% |

| `val_external_human.jsonl` | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| Route accuracy | 60.50% | 89.00% | 94.50% |
| Coverage | 95.50% | 95.50% | 95.00% |
| Mean set size | 4.18 | 1.18 | 1.07 |
| Argument mapping | 52.00% | 100% | 100% |

4B external format accuracy on that 200-row slice: MCP JSON 94.4% (36), mixed 94.6% (37), agent skill 100% (29), REST 96.2% (26), GraphQL 96.8% (31), Python signature 87.8% (41).

The unshuffled 0.8B file, 1,920 test rows, is a different split: 80.99% route, 96.56% argument mapping, 3.33% permutation flip, mean set size 1.16. Do not put it in the same row as the 200-row 4B number.

BFCL converted slice, seed 42, 34 multiple / 33 live multiple / 33 irrelevance:

| | Heuristic | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|
| multiple | 97.06% | 100% | 100% |
| live multiple | 75.76% | 96.97% | 96.97% |
| irrelevance abstain | 3.03% | 57.58% | 75.76% |

Decision models on the same 100 BFCL rows plus 60 external rows, one prefill each:

| | Heuristic | Kev-0.8B | Soro-Kev-0.8B | Soro-Kev-4B |
|---|---|---|---|---|
| multiple | 100% | 100% | 100% | 100% |
| live multiple | 84.8% | 69.7% | 97.0% | 97.0% |
| irrelevance abstain | 3.0% | 81.8% | 57.6% | 75.8% |
| external 60 | 36.7% | 75.0% | 83.3% | 85.0% |
| median latency | 0.31 ms | 111 ms | 80 ms | 413 ms |
| peak VRAM | 0 | 1,612 MB | 1,563 MB | 4,048 MB |

Kev-4B, Kev-9B, and Kev-27B were not run. Their weights are not on this laptop.

Harness checks on this machine: 4B passed the shipment/email dataflow chain, the unlabeled Jira-versus-Linear ask, the `sev1` incident choice, the missing-amount halt, the "do not cancel" negation, and the 25-tool haystack including a soufflé abstain. 0.8B missed `list_incidents` on that haystack.

## Reproduce

```text
cd veyra
pip install -e "./python[dev]"
python training/evaluate_benchmark.py --backend neural --checkpoint runs/soro_kev_qwen3_4b_best --max-eval-rows 300 --val-data data/soro_kev_dataset/val_zeroshot.jsonl
python training/benchmark_decision_models.py
python ../scripts/publish_to_huggingface.py --dry-run
```

Upload is `python scripts/publish_to_huggingface.py` from the repo root after `HF_TOKEN` is set. `--dry-run` does not upload.

## License

Apache-2.0.
