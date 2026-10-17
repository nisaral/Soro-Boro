# Comparison study protocol

Layers: pre-inference routers, opaque retry, framework catch, Harbor coding agents, Veyra post-proposal middleware.

## Arms

| ID | Name | Notes |
|---|---|---|
| A0 | raw | no middleware |
| A1 | Tenacity / naive retry | blind timeout retry |
| A2 | verify-before-retry | |
| A3 | idempotency keys | |
| A4 | fair static | same equivalence lists as Veyra |
| A5-style | in-house MiniLM/BM25 top-k | **not** AgentWeave |
| A5-real | pinned `sauravsingla/agentweave` | RELATED SYSTEM until commit runs |
| A6 | A5 then Veyra | complement |
| A7 | Veyra-ZP | abstain without verify hook |
| A8 | Veyra-contract + TAGE | **production default** |
| A9 | Veyra-contract + case memory | optional flag `use_case_memory=True` |
| A10 | LinUCB | lab only, no live mutating exploration |

## Core metrics

`task, arm, seed, pass, tokens, cost, latency, steps, policy_violations, unsafe_retry`

## Per-suite extras

- UndoBench: DER, CRSR, control pass
- ContinuityBench: IPR, McNemar
- MCPMark: Pass@1, turns
- Harbor: reward, resampling, net headroom

Stop if 95% CI upper bound on lift < 2pp.

LLM: `os.environ["ODYSSEY_API_KEY"]`, `OpenAI(base_url="https://odysseyapi.tech/v1")`, model `openai/gpt-4o`. LM Studio fallback.

## Runs logged 2026-10-07

See `eval_lab/out/PLAN_RUN_RESULTS.json`.

- ContinuityBench frozen scorecard: Veyra IPR 100% vs fair_static 80% (SHA `6ef232dd…`).
- Local UndoBench 120 trials: Veyra 0 duplicates / 100% E2E; naive_retry 80 duplicates.
- Adapter 150 runs: B0 DER 100%; Veyra-ZP DER 0% recovery 0%; Veyra-contract DER 0% recovery 100%.
- Live Odyssey `openai/gpt-4o` UNKNOWN_ACK n=8: naive DER 1.0 pass 0; Veyra DER 0 pass 1.0.
- Ranking lab: TAGE Recall@1 50%, case memory 100%, LinUCB 100% at 23µs vs TAGE 3µs. Production default remains TAGE; case memory optional.
- Official UndoBench clone: doctor READY; smoke RB-PAY-003 control SUCCESS / fault FAILED. LangGraph arm skipped (host langchain-core mismatch).
- MCPMark cloned to `third_party/mcpmark`; official FS pipeline not run (Docker env download).

