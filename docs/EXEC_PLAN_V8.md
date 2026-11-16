# Execution plan v8: the final leg (15 Nov 2026)

Adds two tracks to v7: **injection robustness** and **adaptive coverage**. Keeps everything else (text, speech, images, size rows, benchmark). Where this conflicts with v7, this wins. Background and labelled results are in `PAPER_KT.md`.

## 1. The paper this plan produces

**A ladder of guarantees for decision models.** Drex states that its order robustness and calibration are empirical and that images are an injection risk, and offers no mechanism for any of them. We answer each one.

| Step | Property | Condition | Status |
|---|---|---|---|
| G1 | Same answer for every menu order | None (up to rounding) | Measured at 0.6B |
| G1b | One option's text cannot change another option's score | None, with the refiner off | Follows from the mask; to be stated and tested |
| G2a | Coverage set contains the right option at the target rate | Deployment data like calibration data | Measured, sets too large on hard splits |
| G2b | Coverage on speech bounded from coverage on text | Paired text and speech; penalty term needs no labels | To prove and test |
| G2c | Long-run coverage at the target rate under any shift | Outcome feedback | To implement (inference only) |
| G3 | Untrusted content can refine a decision but not redirect it | Rule on top of G2 | New design, to test |

Plus: tool choice separated from readiness, selective deferral, speech and screenshots on one backbone, small size.

## 2. Prior work found for the two new tracks

Read through search summaries only. Each must be read before it is cited or before novelty is claimed.

### 2.1 Injection

| Work | ID | What it is | Relevance |
|---|---|---|---|
| ToolHijacker | 2504.19793 | A crafted tool document that hijacks retrieval and selection; tested on 8 LLMs; reports StruQ, SecAlign and detection defences as insufficient | The main attack to run against us. Source of attack documents |
| MCPTox | 2508.14925 | Benchmark of poisoned tool metadata on 45 real MCP servers, 353 tools | Realistic poisoned descriptions |
| MCP-SafetyBench | 2512.15163 | 20 attack types; finds defence success trades off against task success | Shows the trade-off we must report |
| MCP-TDP benchmark | 2605.24069 | 32 tool-description poisoning cases; "reactive self-correction" defence | Comparison defence |
| ToolTweak, Attractive Metadata Attack, MalTool | (find IDs) | Further attacks on tool metadata | Check for overlap |
| VPI-Bench | 2506.02456 | 306 visual injection cases rendered into interfaces for computer-use agents | Source for screenshot attacks |
| MELON | 2502.05174 | Re-runs the agent with the user prompt masked and compares tool calls; evaluated on AgentDojo | Closest to our two-pass check. Cite and state the difference |
| CaMeL | 2503.18813 | System layer that keeps untrusted data out of control flow | The "by design" defence for generative agents |
| StruQ, SecAlign | 2410.05451 (SecAlign) | Fine-tuning defences; a later re-evaluation found gains overstated | Baseline defences |

Gap as far as these searches show: no defence designed for tool selection specifically, none for a non-generative decision model, none tied to a coverage set, none covering spoken injection.

### 2.2 Adaptive coverage

| Work | ID | What it is | Relevance |
|---|---|---|---|
| Adaptive conformal inference | 2106.00170 (from memory) | Updates the threshold after each outcome; long-run coverage for any sequence | The method we adopt |
| CCPO | 2511.11828 | Online conformal prediction plus a policy routing between a small and a large LLM, with a reliability guarantee | **Closest to our deferral + adaptive coverage. Read first** |
| ToolChain-CRC | 2606.18467 | Conformal risk control over tool-using agent trajectories | Closest on tools |
| PACE | NeurIPS 2026 | Adds a proactive signal from the incoming query to adaptive conformal, for LLM factuality | Prior art for using a label-free signal |
| Domain-shift-aware conformal | 2510.05566 | Reweights calibration data near the test prompt | Baseline |
| Conformity Breaks Conformal Prediction | 2609.04445 | An adversary breaks split-conformal validity | Motivates G2c and the attack stream |
| Verifiably robust conformal | 2405.18942 | Inflates sets to keep coverage under bounded perturbations | Related; norm-bounded, not injection |
| Pitfalls of conformal under attack | 2405.08886 | Coverage survives attacks but sets grow to nearly everything | The failure mode to measure |

Gap as far as these searches show: no adaptive coverage for a decision model with a changing tool catalog or a change of modality, and none that uses deferral as its source of feedback.

## 3. Architecture changes

Each is one variable and gets its own run or its own evaluation. None changes the locked tool pointer.

1. **Non-interference mode (G1b).** With isolation and no refiner, the raw score of option i does not depend on the text of option j. Add an absolute per-option fit score (a sigmoid, not only the softmax over the menu) so that a poisoned option can raise only its own score. Report results with the refiner on and off; the refiner trades some of this property for collision accuracy.
2. **Trust-ordered layout.** Order the sequence as `[prefix] [user request] [untrusted content: tool output, document, image, audio from others] [options]`. Attention is causal, so the request vector read at the end of the request cannot see the untrusted content. That is by construction.
3. **Two-pass containment (G3).** Score the options twice: with the untrusted content visible, and with it masked. The request is encoded once and reused, so the second pass costs only the option tokens. Rule: the final decision must lie inside the request-only coverage set taken at a loose level (for example 99%). Untrusted content may narrow the choice within that set. If it points outside, defer. The reverse pass (request masked, untrusted content only) flags content that confidently selects an action on its own.
4. **Injection hard negatives.** Add poisoned tool descriptions and injected state text to training as negatives, in the same way as near-duplicate tools.
5. **Readiness on the locked pointer.** As already planned.
6. **Adaptive threshold.** After each decision with a known outcome, move the coverage threshold by a small step toward the target miss rate. No training. Feedback sources: a deferred request returns the larger model's answer; an executed call returns success or failure.
7. **Proactive signal.** Use the label-free disagreement between the text set and the speech set (and between the two passes in item 3) to widen the threshold before errors arrive. Compare with PACE.

## 4. Evaluations to build (CPU)

### 4.1 Injection suite
For each row of the external 1,200 and a When2Call subset, build attacked twins:

| Attack | How | Where it enters |
|---|---|---|
| Poisoned distractor | An extra tool whose description says to always choose it; ToolHijacker and MCPTox style text | An option |
| Poisoned gold-adjacent | Injection inside a plausible near-duplicate | An option |
| State injection | Instruction inside a tool output or document | Untrusted content |
| Rendered text | Instruction drawn into a screenshot (VPI-Bench style) | Image |
| Spoken injection | A second voice or background speech giving an instruction | Audio |

Metrics: attack success rate, accuracy under attack, false deferral rate on clean rows. Systems: ours with isolation, ours without isolation (the controlled comparison), ours with containment, Drex v1.5, Hammer, xLAM. For images, a generative vision model as reference, since Drex Max is gated.

### 4.2 Shift streams for adaptive coverage
Ordered streams of about 5,000 decisions each:

1. Text, then speech, then noisy speech.
2. A catalog that changes: tools added, removed and renamed.
3. Clean traffic with a burst of injected rows.
4. In-domain tools, then unseen tools.

Metrics: rolling coverage, set size, deferral rate, and time to recover. Methods: static split conformal, weighted conformal, adaptive, adaptive with the proactive signal.

## 5. Schedule

Dates are targets. Conference deadlines are still unconfirmed.

### Phase 0, to 18 Nov: close the open gates
| Task | Gate |
|---|---|
| Gemma 4 E2B evaluation in **fp32** (the queued job says bfloat16; fix it) | 0 flips, spread ≤ 1e-4; within 2 points of locked 0.6B on external 1,200 |
| 4B evaluation, saved per split | 0 flips; When2Call number recorded |
| Original-format When2Call on an action-trained model (the locked pointer alone has no ask action; label its score as zero-shot) | First number comparable with Drex's 89.7 |
| Readiness on locked pointer, on the correct backbone | Ask and call separated on tool-disjoint pairs |
| Drex v1.5 on our external 1,200 and collisions, five orders, fp32 where possible | Its accuracy and flips on our rows |
| Risk-coverage curve on the locked model | Starts at 86.00% |
| Resolve the two different tool/abstain breakdowns of 86.00% | One breakdown in the ledger |

### Phase 1, 18 to 28 Nov: data and suites (mostly CPU), speech starts
- Action data build, at least 300k menus: natural asks, about 30% abstain, menus up to 40, several tool sources, injection negatives.
- Injection suite (4.1) for text; shift streams (4.2).
- Speech quality check on 500 clips with a larger Whisper model.
- Gemma text parity, then speech twins on all 42,057 clips. Cascade baseline.
- Adaptive threshold and static baselines on the text streams (no training needed, so results arrive this phase).
- Refiner test: three seeds on 1,641 collision rows, with the max-pool variant.

### Phase 2, 28 Nov to 10 Dec: final models and the new results
- Final recipe (locked pointer + readiness + injection negatives) on 0.6B, 4B and Gemma. Three seeds on the rows that go in tables.
- Injection results: isolation on and off, containment on and off, against Drex v1.5, Hammer, xLAM.
- Cross-modal bound: proof, then test on text and speech twins. Adaptive coverage on the speech stream.
- Spoken injection and the first rendered-text attacks on Gemma.
- Distil 4B to 0.6B. Embedding-initialised 0.6B test.

### Phase 3, 10 to 20 Dec: write and post
- Ablations, limitations, proofs. All cited papers read.
- arXiv v1 and Hugging Face release: 0.6B, 4B, Gemma speech model, injection suite, streams.

### Phase 4, January: full scope for the conference version
- Screenshot track complete: cross-modal minimal pairs, VPI-Bench style attacks, speech plus screenshot.
- Early commit on streaming speech with the coverage rule.
- 8B row on rented compute. Learning from outcomes on the changing-catalog stream.
- Tri-modal benchmark release. Submission.

## 6. What decides acceptance

1. **The controlled comparison.** Same backbone and data, isolation on and off: flips, attack success, accuracy. Drex itself says its comparisons are confounded.
2. **Drex v1.5 run by us on our rows.** Measured flips and attack success, not quoted numbers.
3. **The trade-offs stated.** Refiner against non-interference; containment against false deferral; adaptive coverage against set size.
4. **At least one multimodal result with a guarantee attached.** Speech coverage with the cross-modal bound is the nearest.

## 7. Risks

| Risk | Response |
|---|---|
| Containment defers too often when the image legitimately carries the needed value | Loosen the request-only level; report the curve; fall back to "flag" instead of "defer" |
| A poisoned option still promotes itself | Injection negatives in training; report the residual honestly |
| Adaptive coverage keeps the rate by inflating sets | Report set size and deferral beside coverage; this is the known failure mode |
| CCPO or ToolChain-CRC already covers the adaptive deferral idea | Read both this week; position on the decision-model and modality-shift setting |
| Gemma does not reach 0 flips in fp32 | The mask is wrong on Gemma; fix before any speech run |
| Compute | A rented 24 to 48 GB GPU for Phase 2. The plan does not depend on pooling free accounts |

## 8. Standing rules (unchanged)

One variable per run; explicit seed; local 100-step smoke test; results saved per split; fp32 five-order evaluation with the spread reported; paired tests; no result described before it exists; no number about another paper until it has been read there.
