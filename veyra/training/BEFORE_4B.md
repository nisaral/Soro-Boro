# Before the 4B run

Measured on `soro_kev_0.8b` (PeftModel, CPU) with 8 hand-written prompts and the harness route path. This is a probe, not a benchmark.

Multi-intent prompts that auto-executed a mutation: **3/4**.

| Prompt kind | Action | Tool | Auto mutation |
| --- | --- | --- | --- |
| check order, then cancel, then refund | EXECUTE | issue_order_refund | yes |
| open a ticket and notify the channel | EXECUTE | github_create_issue | yes |
| weather in Berlin and also refund | EXECUTE | query_weather_forecast | no (ignored the refund) |
| if not shipped, cancel, else do nothing | EXECUTE | cancel_order | yes |
| single refund | EXECUTE | issue_order_refund | yes (correct single intent) |
| weather only | EXECUTE | query_weather_forecast | no |
| search salt and pepper | EXECUTE | search_products | no |
| souffle | ABSTAIN | none | no |

`append_intent_rows.py` has been run. `train.jsonl` is now 23,192 rows: 18,555 single, 2,494 multi, 2,143 none. `val_zeroshot.jsonl` is 2,220 rows: 1,811 single, 200 multi, 209 none. The intent head (`single` / `multi` / `none`) is in the training loss at weight 0.40. Sequential rows and `__done__` rows are included. `external_intent.jsonl` is loaded automatically beside `train.jsonl`. The committed file has 7,770 ToolACE rows (3,182 multi, 3,606 single, 982 none) and 8,000 Toucan rows labeled multi, from one public shard. xLAM is CC-BY-4.0 and the Hub file is gated, so it is not in the jsonl. Put `xlam_function_calling_60k.json` in `data/external_raw` and rerun `python training/convert_external_tools.py --skip-download` to add it. NESTFUL stays held out.

## Datasets to pull on Kaggle before a multi-intent 4B run

Use these. Do not train on all of Toucan.

| Dataset | Hub id | License | What to take |
| --- | --- | --- | --- |
| Toucan-1.5M | `Agent-Ark/Toucan-1.5M` | Apache-2.0 | A sample only. Synthetic tasks over real MCP servers, with parallel and sequential trajectories. Convert each trajectory to `(goal + results so far) -> next tool`, last step `__done__`. |
| ToolACE | `Team-ACE/ToolACE` | Apache-2.0 | The released file is about 11k dialogs, not 26,507 rows. 26,507 is the paper's API pool. Use it to label single vs parallel vs dependent. |
| xLAM-60k | `Salesforce/xlam-function-calling-60k` | CC-BY-4.0 | Parallel calls. Attribute Salesforce in the model card. |
| NESTFUL | `ibm-research/nestful` | Apache-2.0 | About 1,800 nested eval sequences, mostly math and code. Hold out. Do not train on it. |

Do not start the 4B job for multi-intent until those rows exist. The NF4 trainer is ready for the current 18k set, and that run will not fix the 3/4 auto-mutation rate.
