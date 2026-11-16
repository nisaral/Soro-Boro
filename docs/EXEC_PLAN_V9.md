# Execution plan v9: protected coverage (16 Nov 2026)

Written after the primary-source register (`PAPER_LITERATURE_NOTES.md`) narrowed what can be claimed. Replaces the "ladder of guarantees" pitch of v8. Multimodal and conformal stay; they are now organised around one result.

**Status of the core idea: candidate.** It is my proposal. Prior-art check so far is four searches and two abstracts (section 3). It must pass the same primary-source audit as everything else before it is built on.

## 1. The core idea

### 1.1 Observation
In a model that scores each option from the request and that option alone, the score of the correct option does not depend on what else is on the menu, or on any untrusted content the score never reads. A coverage set calibrated on that score therefore keeps its guarantee whatever an attacker does to the rest of the menu or to the evidence.

Listwise models do not have this property. In Drex, in any softmax-over-menu scorer, and in our own model with the refiner on, a poisoned option can lower the correct option's score and push it out of the set.

### 1.2 Statements to prove (all elementary; the value is in the property and its measurement)

Setting: a trusted request x, a menu M containing the correct option y, optional untrusted context u. A score a(x, c) that depends only on x and c. A threshold fitted by split conformal on clean, exchangeable (x, y) pairs. Protected set P(x, M) = options whose score passes the threshold.

1. **Menu-agnostic coverage.** For a clean test pair, y is in P(x, M) with probability at least 1 − α for *any* menu containing y, including one chosen by an adversary after seeing x and the model, and for any u.
2. **Integrity under the act-on-singleton policy.** If the system executes only when P is a single option and otherwise defers or asks, the probability of executing a wrong option is at most α, under any manipulation of the other options and of u.
3. **Attacks cost availability, not integrity.** Adding options can only enlarge P. So an attacker can turn "act" into "defer"; it cannot turn "act on y" into "act on something else" beyond the α budget.
4. **Catalog change needs no recalibration.** Adding, removing or renaming non-correct tools leaves coverage unchanged with a static threshold.

### 1.3 What it does not cover (state all of these in the paper)

- **No correct tool on the menu.** A poisoned tool that alone passes the threshold is executed. Coverage controls missing the right option, not admitting a wrong one. Residual, handled empirically.
- **The correct tool's own text is tampered with.**
- **The request itself is attacked**, including a second voice mixed into the user's audio.
- **Shift in clean requests.** Needs adaptive calibration (section 2.4).
- **Guarantee is marginal**, not per request, and joint (wrong-and-acted), not conditional on acting.
- **An ordinary independent scorer has the same property.** Our claim is not a new scorer. It is: the property identified and proved for decision models, an architecture that gets it at single-pass cost with interaction restored inside the protected set, the measured cost, and the multimodal setting.

### 1.4 Why this is a paper and not a remark
It makes three testable predictions that separate non-interfering models from listwise ones:

- Under injected distractors, protected sets keep coverage and listwise sets lose it.
- Under catalog growth with a static threshold, the same.
- Wrong-action rate under attack stays at or below α for the singleton policy, while the price shows up as deferral.

The open empirical question, and the main risk, is the price: how often the protected set is a singleton on clean traffic, and how cheaply an attacker can force deferral.

## 2. How the tracks hang off it

### 2.1 Architecture: two stages
- **Stage 1, protected.** Request read before any untrusted content. Each option scored against the request alone: refiner off, no softmax, no evidence. Conformal threshold gives P.
- **Stage 2, contained.** Inside P only: refiner on, evidence visible, readiness judged. Stage 2 may choose within P or ask. It cannot leave P.
- **Actions fall out of the sets.** P is one ready option: call. P has several, or one that lacks information: ask. P is empty: abstain or defer.
- Code facts from the register that must change first: the current packing puts state and media before the user's question; the refiner also updates the request vector; ties are broken by menu position.

### 2.2 Speech
The user's spoken request is the trusted channel. Stage 1 runs on speech alone; calibration is on speech, or on text with the measured coupling penalty. The paired-set inequality stays as a corollary, not a headline.

### 2.3 Screenshots
The screenshot is untrusted evidence. It enters only in stage 2. The cross-modal minimal pairs (a required value shown or absent on screen) measure the utility cost: when the screen legitimately carries the needed value, P is large and stage 2 must narrow it.

### 2.4 Adaptive calibration
Applied to the protected score only. The menu-agnostic property means feedback is needed for request and modality shift, not for catalog change. Feedback is limited to labelled or deferred requests; the register's caution about proxy labels applies.

### 2.5 Injection evaluation
Attacked twins as in v8, now with a specific hypothesis to confirm or refute per attack class:

| Attack | Predicted by the statements | Measured |
|---|---|---|
| Poisoned distractor, correct tool present | Wrong-action ≤ α; deferral rises | Wrong-action rate, deferral rate |
| Attractive-metadata distractor | Same; tests how cheaply the set is entered | Attacker cost to force deferral |
| Evidence injection (tool output, rendered text) | No effect on stage 1 | Stage 2 redirection inside P |
| Poisoned tool, no correct tool on menu | Not covered | Residual wrong-action rate |
| Second voice in the audio | Not covered | Empirical, with the concurrent-audio prior cited |

## 3. Prior-art check so far

Searched 16 Nov. Summaries and abstracts only unless marked.

| Work | ID | What it is | Why it does not already do this (to verify) |
|---|---|---|---|
| RobustRAG | 2405.15556 | Answers from each passage in isolation, then secure aggregation; certifies against a bounded number of corrupted passages | Closest in spirit: isolation gives a certificate. Generative RAG, bounded corruption, no coverage set |
| Quantitative Certification of Agentic Tool Selection (LLMCert-T) | 2510.03992 | Statistical certificate (Clopper-Pearson) measuring how fragile tool selection is under inserted tools | Measurement, not a defence. Abstract read |
| CAGE | 2607.29190 | Certifies that an action stays authorised across a neighbourhood of tool returns | Different object (returns, not menus). Abstract read |
| Design patterns for securing agents | 2506.08837 | Plan-then-execute: injected text cannot add tools outside a fixed plan | Same integrity-versus-availability framing, by system design; no statistical guarantee |
| CaMeL, Task Shield, ClawGuard, ARGUS (2605.03378), AttriGuard (2603.10749) | see register | System-level or auditor defences | Need the comparison; none found tying a coverage set to menu manipulation |
| Robust conformal sets under evasion and poisoning | 2407.09165, 2410.09878 | Coverage under bounded input perturbation or poisoned calibration data | Norm-bounded or calibration attacks, not menu manipulation |
| Conformal inference for open-set classification | 2510.13037 | Coverage when unseen labels appear | Label space changes, but not adversarial distractors with per-option scores |
| Conformal retrieval (for example TRAQ) | to find | Thresholds per-passage scores for retrieval coverage | **Most likely place for an existing statement of 1.2(1). Check first** |

### 3.1 Wide search, 16 Nov (second pass: 12 more searches, 5 pages fetched)

These are closer than anything in the first pass. They reduce what can be claimed.

| Work | ID | What it already does | What is left for us |
|---|---|---|---|
| **PlanGuard** | 2604.10134 | An isolated planner builds a reference action set from the user instruction and tool definitions only; actions outside it are blocked; an LLM verifier handles near-misses. 0% attack success on InjecAgent; hard rule alone gives 27 to 38% false positives | **The two-stage "reference from the request, evidence cannot leave it" structure is theirs.** No statistical bound, two extra LLM calls, and the planner still reads tool descriptions, so a poisoned description can reach it |
| **Tool-Guard** ("Think Twice Before You Act") | 2606.20922 | Splits tools into two lists planned separately so a poisoned description cannot steer the other list; LLM alignment and suspicion checks | Partitioning, not per-tool scoring; no guarantee; 3.7x latency |
| **conformal-tool-exposure** | GitHub repo, no paper | Split conformal and adaptive conformal sets over decision-model scores (a Jev-compatible API) for tool selection on ToolRet; poisoning listed but unmeasured | **Conformal sets on decision-model tool scores exist publicly.** No invariance statement, no attack results, no singleton policy |
| Conformal intent classification and clarification | 2403.18973 | Conformal sets over intents; ask a clarifying question when the set has several | "Ask when the set is large" for intents is prior art |
| Conformal LLM routing with distribution-free safety | ACL SRW 2026 | Set size as the routing signal | Singleton-acts routing is prior art |
| Order sensitivity as an attack surface | 2607.24869 | Reordering attacks on listwise rerankers; pointwise and position-invariant scoring stay at zero attack success, with lower ranking quality | Pointwise immunity to order attacks is documented |
| Beyond Perturbations; Playing it Safe; Robust classification via abstaining | 2007.05145, 1911.11253, 2104.02334 | Selective classifiers with error and rejection bounds under arbitrary adversarial test examples | "Attacks buy rejections, not errors" is an established framing in adversarial learning |
| Brain-Prompt Injection audit | 2606.09315 | Split-conformal bound on a confirmation channel; holds under channel isolation, breaks when the channel is attacker-controlled | The dependence of a conformal bound on a trusted channel has been observed |
| Conformal factuality for RAG under distractors | 2603.16817 | Conformal filtering is fragile under distractors and shift | Supports the contrast we want to measure |
| Adversarially robust conformal planning | 2511.10586 | Robust conformal for planners under bounded perturbation | Bounded, not menu manipulation |
| Spoofing the Toolbox; ToolFlood; TRUSTDESC; Attacker Tool Filtering | 2610.33182, 2603.13950, 2604.07536, 2609.16098 | Newer attacks on tool descriptions and retrieval, and defences by trusted descriptions or outlier filtering | Attacks to include; defences to compare |

### 3.2 Verdict after the wide search

- **Not found:** a statement that a coverage set built on per-option, request-only scores keeps its guarantee under arbitrary manipulation of the other options and of evidence, with the resulting wrong-action bound, for a decision model. Also not found: any such result for spoken requests or screenshot evidence.
- **Found:** every ingredient separately. The reference-set structure (PlanGuard), conformal sets on decision-model scores (the repo), ask-on-large-set (intent clarification), abstention under attack (adversarial learning), pointwise immunity to order attacks.
- **So the honest claim is narrower than section 1 first read.** We are not proposing the two-stage structure or conformal tool sets. The candidate contribution is: (a) the statistical version of the reference set, with a provable wrong-action bound that also covers poisoned tool descriptions, which PlanGuard's planner does not; (b) at single-pass cost in one small model, against PlanGuard's two extra LLM calls and Tool-Guard's 3.7x latency; (c) the measured separation between non-interfering and listwise decision models under attack and catalog change; (d) the same on speech and screenshots.
- **Confidence: moderate, not certain.** A search cannot prove absence. All of this is from search summaries and fetched abstracts or pages, not full reads. The field moved monthly in 2026.
- **New baselines this forces:** PlanGuard and Tool-Guard adapted to fixed menus, the conformal-tool-exposure pipeline, and an independent pointwise scorer.
- **What would still kill it:** a paper giving a coverage or risk bound for a request-only reference set under tool poisoning. Search terms not yet exhausted: "conformal" with PlanGuard-style reference plans; certified tool filtering; reranker security with calibrated thresholds.

## 4. Experiments

| # | Experiment | Systems | Decides |
|---|---|---|---|
| E0 | Validity fixes: group-aware splits on the external set, correct conformal rank, identity-based tie-break, true multi-seed | All | Whether any later number is usable |
| E1 | **Pilot, no training.** Protected sets from the locked model's pre-refiner scores on the external rows: coverage, set size, singleton rate | Locked 0.6B | Whether the price is tolerable at all |
| E2 | Coverage and wrong-action rate under injected distractors | Protected stage 1; our model with refiner; softmax listwise; independent per-option scorer; Drex (native, validated) | Statements 1 to 3 |
| E3 | Catalog growth stream with a static threshold | Same | Statement 4 |
| E4 | Stage 2 utility: accuracy and ask quality inside P; refiner on/off; collisions | Ours | What interaction buys once integrity is fixed |
| E5 | Residuals: no-correct-tool attacks, tampered correct tool, attacker cost to force deferral | Ours, with and without injection negatives | Honest limits |
| E6 | Speech: stage 1 on spoken requests; coupling penalty; adaptive calibration across text to speech | Gemma | Whether the property survives a modality |
| E7 | Screenshot evidence: minimal pairs and rendered-text attacks in stage 2 | Gemma | Utility cost and containment with images |
| E8 | Baselines for the security claim: Task Shield and MELON-style filters adapted to fixed menus | | Whether we beat simpler defences at equal utility |

## 5. Gates

| Date | Gate | If it fails |
|---|---|---|
| 19 Nov | Prior-art audit of section 1.2 by primary reading | Reposition as an empirical study of the property; keep E2 to E5 |
| 21 Nov | E0 done; E1 pilot: singleton rate on clean external rows at 90% coverage | Below about 50%: train a dedicated absolute-score head before going further |
| 28 Nov | E2 and E3 on text | If listwise models also hold coverage under attack, the separation is not real; fall back to the benchmark route |
| 5 Dec | Gemma passes the flip gate; E6 first numbers | Speech moves to the second version |
| 12 Dec | E4, E5, E8; three seeds | |
| 20 Dec | Preprint | |
| January | E7, larger model row, benchmark release, submission | |

## 6. What stays, changes, goes

- **Stays:** exact order stability as a property (not a headline), the locked pointer, readiness on the chosen tool, speech and screenshots, adaptive calibration, the Drex comparison, small size.
- **Changes:** coverage is computed on a protected, non-interfering score; the refiner and evidence move inside the protected set; actions are read off the set.
- **Goes from the headline:** "six guarantees", "first isolated architecture", any "first defence" claim, early commit on streaming speech (parked until there is time-uniform calibration).

## 7. Larger models, including mixture-of-experts

Size rows: 0.6B, Gemma 4 E2B, 4B, then one larger model in January. A mixture-of-experts model is a good candidate for that row: it runs a few billion active parameters per token while holding many more, so the cost is nearer the 4B than a dense 27B.

Conditions it must meet, checked before any training:

| Condition | Why |
|---|---|
| Standard attention layers that accept an arbitrary mask | Drex's hybrid and mixture models use recurrent layers that cannot isolate options; that is why Drex never tested isolation |
| Expert routing decided per token from that token's own hidden state | Then an option's computation still depends only on the request and itself, and every statement in section 1.2 carries over |
| No batch-level or sequence-level capacity limit in the router | A shared capacity would let one option's tokens change which experts another option gets, breaking non-interference |
| Deterministic routing at inference | Expert choice is a hard top-k; rounding near a tie can switch experts and enlarge the numerical spread. Measure the spread and use a fixed menu order if needed |

Candidates to check against these conditions: `Qwen3-30B-A3B` (about 3B active) and any Gemma or Qwen mixture release with full attention. Memory is the constraint: a 30B model needs a 24 to 48 GB GPU even quantised, so this row depends on rented compute.

A cheaper variant on the small models: a mixture of adapters with the router reading the request only. Routing on the request alone keeps the protected score independent of the menu. One-variable test against the single adapter.

## 8. Rules carried over
One variable per run; explicit seeds; results saved per split; no number described before it exists; nothing claimed about another paper until read there. New: every novelty statement names the searches and readings behind it.
