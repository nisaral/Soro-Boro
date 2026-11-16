# Task board (plan v11)

Companion to `MASTER_STATUS.md`. Update the Status column when a task moves. Status values: todo, running, done, blocked, dropped.

Owners: **Run** = the agent that runs Kaggle and Colab jobs. **Audit** = the agent that reads primary sources. **Keyush** = you. **Review** = Claude in this session, checks each report against the gate.

## Today and tomorrow: hygiene

| ID | Task | Owner | Done when | Status |
|---|---|---|---|---|
| H1 | Move Phase A generators and result files out of `scratch/` (git-ignored) into a tracked folder; add ledger rows | Run | Files tracked, ledger has A1, A2, A3 and the recalibration control | done |
| H2 | One conformal implementation everywhere (`soro/routing/conformal.py`); ties broken by a hash of the option key | Run | `eval_conformal_action.py` no longer clips | done |
| H3 | Reconcile 321 request groups against the "115 base queries" on the public 4B card | Run | One number, explained in the ledger | done |
| H4 | Reconcile 4B flips: 23/5,007 against 2/1,200 | Run | One row in the ledger with dtype and score spread | done |
| H5 | Read 20 lookalike rows by hand | Keyush | Note in the ledger: valid or not | todo |
| H6 | Decide whether to commit the docs and the two modified eval scripts | Keyush | Committed or deliberately left | todo |
| H7 | Revoke the Kaggle token after the current runs; confirm ICML and NeurIPS 2027 dates | Keyush | Done | todo |

## Track 1: the deciding experiments (by 20 Nov)

All in fp32 on the locked 0.6B, 100 group-aware splits, target coverage 90%.

| ID | Task | Owner | Done when | Status |
|---|---|---|---|---|
| E1 | Attack suite v2. Lookalikes in the same JSON card format as real tools, no `fake_` in names. Two versions: request-aware, and request-blind (clone catalog tools with promotional metadata) | Run | Two files, generator tracked | done |
| E2 | Same-score comparison: softmax over pre-refiner scores, softmax after refiner, and per-option on pre-refiner scores | Run | Table isolates normalisation from the refiner | todo |
| E3 | Absolute-score head: per-option yes/no loss on frozen pre-refiner features, lookalikes excluded from training | Run | Clean and attacked tables; full curve of wrong-action rate against share acted on | todo |
| E4 | Baseline: MiniLM cosine with conformal threshold, clean and attacked | Run | Same table columns as E3 | todo |
| E5 | Baseline: CROQ (conformal prune, then rescore the kept options) | Run | Same columns | todo |
| E6 | Trust-priority rule on existing outputs; include the case where the correct tool is third-party | Run | Share acted on and wrong actions, both cases, beside a plain allowlist | todo |
| E7 | Hammer-1.5B and xLAM-1B on attack suite v2: how often each picks the injected tool | Run | Two rows | todo |
| R1 | Check E1 to E7 against gate B and write the 20 Nov call | Review | Go, analysis paper, or release only | todo |

## Track 2: generality across decision models (20 Nov to 5 Dec)

| ID | Task | Owner | Done when | Status |
|---|---|---|---|---|
| B1 | Backend interface: `score(request, options, media) -> one score and one probability per option`. Start from `benchmark_decision_models.py` | Run | Soro and Kev-0.8b pass the same smoke test | todo |
| B2 | Add open-weight backends in this order: Clef, Drex v1.5, D3-edge, Smaug-Decisions, then Valen, OneJev, Jeva if weights exist | Run | Each reproduces one published number within 2 points before any other use | todo |
| B3 | Run attack suite v2 on every validated backend; build act/ask sets from each model's own probabilities | Run | Gate A table | todo |
| B4 | Published attacks: ToolHijacker, Attractive Metadata, MCPTox descriptions | Run | Added as streams; each audited by a second party | todo |
| B5 | Three true seeds for every row that involves our training | Run | Seeds 42, 43, 44, no duplicates | todo |
| R2 | Check gate A and write the 5 Dec call | Review | Method paper, analysis paper, or release only | todo |

## Track 3: literature audits

Each returns quoted passages with section numbers.

| ID | Question | Owner | Status |
|---|---|---|---|
| L1 | DecisionRobust (2610.19118), full text: any attack that adds or edits options? any tool tasks? any abstention or selective metrics? | Audit | done |
| L2 | Jeva (2610.18773), full text: is each option's score independent of the others? how is the "some option fits" estimate computed? are weights released? | Audit | done |
| L3 | Is resolving by tool origin published? ETDI, FIDES, CaMeL, MCP registry signing. Does any allow a third-party tool to win over a trusted one? | Audit | done |
| L4 | What do the Jev Decision Index and the Artificial Analysis Decision Index v2 test on robustness? Also SHIFT-JEV and the ordinal-scale bias paper (2609.38827) | Audit | todo |
| L5 | Smaug-Audio-Decisions-0.7B and Clef-Omni: any spoken tool-routing or audio-injection result? | Audit | todo |
| L6 | Outcome evidence for tool choice (bandit and experience methods, BaRP): is "no verified outcome, no solo action" published? | Audit | todo |

## Track 4: speech and screenshots (after the 5 Dec call)

| ID | Task | Owner | Done when | Status |
|---|---|---|---|---|
| M1 | Trust-split packing: stage 1 sees request and options only; stage 2 adds screenshot or tool output for the kept options | Run | Unit test: changing the image cannot change the stage 1 set | todo |
| M2 | Repeat the speech quality check with a strong recogniser on 500 clips; whisper-tiny may be the cause of the 30% | Run | Word error rate and a keep/regenerate decision | todo |
| M3 | Gemma abstain repair (40.74% on abstain rows) | Run | Within 5 points of Qwen on abstain rows | todo |
| M4 | Speech as trusted request: stage 1 sets and act/ask accounting; cascade baseline; Smaug-Audio as comparator | Run | Gate C table | todo |
| M5 | Screenshot as evidence: minimal pairs and rendered-text attacks on stage 2 | Run | Gate C table | todo |

## Parked (product track, not in the paper)

| Item | Why parked |
|---|---|
| 8B, 27B and MoE sizes | Size is not our argument; D3 and Clef already span it |
| Video input | No paper question needs it |
| Unified tool registry across Python, REST and MCP | Product work; start after the preprint |
| Argument construction and execution verification | Outside what any guarantee here covers |
| Outcome cards (old G5) | Waits on audit L6 |
| Canonical When2Call catch-up | Needs new training data; revisit after gate A |

## Dropped

Order-invariance theorem as a contribution; "ladder of guarantees"; "protected coverage" as a new guarantee; 4-card action router; "first multimodal decision model with guarantees".
