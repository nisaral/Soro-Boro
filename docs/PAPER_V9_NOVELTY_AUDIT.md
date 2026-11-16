# V9 protected coverage: primary-source novelty and validity audit

Audit cutoff: **16 November 2026**. Target: `docs/EXEC_PLAN_V9.md`. This supplements `docs/PAPER_LITERATURE_NOTES.md`; it is not an experiment report or a replacement execution plan.

## 1. Verdict

**V9 is more coherent than V8, but the first-discovery pitch for its central coverage observation does not survive this audit.** There is direct prior wording about distractor-invariant conformal coverage, older pointwise conformal retrieval constructions, prior conformal pruning followed by interaction on the retained options, and prior singleton-act/otherwise-defer policies. Their composition can be useful for tool security, but an elementary consequence should not be sold as new foundational conformal theory.

This does **not** establish that somebody already published the identical compact, multimodal, adversarial-tool-selection system. The remaining candidate contribution is an efficient implementation and a convincing, controlled security--utility study against the closest constructions, with a carefully scoped tool-identity risk corollary. No identical end-to-end system was established by the inspected sources; absence from this search is not proof of novelty.

There is also a policy ambiguity to fix before implementation: **the alpha wrong-action bound applies to a singleton of the original protected set, not to a singleton obtained by untrusted stage-two narrowing.** The latter gives containment only.

The research recommendation is **conditional continuation of E0, E1, and a small text attack pilot**, not abandonment and not an A* acceptance prediction. Do not spend on all size/modality rows before demonstrating an advantage over ordinary pointwise scoring plus conformal calibration at matched utility and compute.

### 1.1 The decisive source

Ben Jenkins and Mihaela Cardei, [*Two-Sided Conformal Evidence Sets for Retrieval-Augmented Generation*, arXiv:2611.10335v1](https://arxiv.org/html/2611.10335v1), submitted **7 November 2026**. Inspected: Sections IV-B--IV-E, Propositions 1--2 and their arguments, Remarks 1--2, Section V-I, and transfer/limitation sections.

Section V-I explicitly states:

> Because distractors add candidates without removing gold evidence, coverage is invariant by construction

CES thresholds independently scored claim--passage pairs and covers available gold evidence, not downstream verdict correctness. It tests random/BM25 distractors, not adversarial tool metadata. The observation is explicit prior art; extending nuisance candidates to hostile text is a useful application, not by itself substantial new statistical theory. This does not establish an identical V9 system.

### 1.2 Claim-by-claim disposition

| V9 component | Closest inspected prior | Disposition |
|---|---|---|
| Clean calibration on a request--candidate score | TRAQ, Section 3.2, Eq. (3), Lemma 2.1; conformal IR score-refinement paper, Section 2.2 | Existing construction. |
| Adding distractors leaves gold membership/coverage unchanged | Conformal Evidence Sets, Section V-I, backed by its pairwise construction | Explicit prior observation; treat adversarial-menu version as a scoped corollary/application. |
| Act only on a singleton; otherwise seek help | KnowNo; CICC Algorithm 1; Conformal Cascade Section 3.4 | Existing policy and joint accepted-error reasoning. |
| Conformal prune, then restore interaction within the retained set | Prune 'n Predict/CROQ, Section 3.1, Remark 3.3, ToolAlpaca and NL2SQL evaluations | Existing two-stage construction, including cheap pairwise first-stage alternatives. |
| Trusted reference set before untrusted evidence | PlanGuard Section IV-B; design-pattern paper; CaMeL-NOVA Section 3 | Existing trust-boundary design. Statistical candidate inclusion is a different object, not a first reference-set architecture. |
| Isolation/shared positions in one packed backbone pass | Set-LLM; PCW; Drex Appendix C.2 | Existing architecture ingredients. An attention mask is not automatically a cheap sparse implementation. |
| Conformal risk plus noninterference for tool calls | Role-Stratified Per-Field CRC, method and Proposition 3 | Already related explicitly, but for argument-role violations and detector-relative influence, not V9's menu-preserving gold score. |
| Certified abstention/adaptation for small decision models under candidate-set shift | SHIFT-JEV, Sections 3.4--3.6 and Appendix B | Prior setting and mechanisms exist; its guarantees are regime-conditional, not arbitrary menu invariance. |
| Limited-feedback online conformal selection | Efficient Online Conformal Selection with Limited Feedback; capacity-aware OCRC | Prior art exists. V9 still needs the correct feedback object and update, not a plain censored ACI transplant. |
| Spoken requests / screenshots | Concurrent audio injection/CADV; CaMeL-NOVA; VPI-Bench in the earlier register | Potential evaluation contribution, not an empty security literature or a new theorem merely by changing modality. |

## 2. The mathematical statement that actually holds

The following is an independently checked derivation from the V9 setting and standard split conformal prediction. It is **not** a claim of a new conformal theorem.

### 2.1 Assumptions and admissible attacks

Use a low-is-good nonconformity score `s(x,c)`. Fix its model/training/preprocessing independently of calibration and test data. Let the `n` clean calibration pairs and the clean test pair `(X,Y)` be exchangeable. The trusted request and the correct candidate's scored representation must be unchanged by an attack.

An admissible attack may choose the other candidates after seeing the request, model, or threshold, and may change arbitrary evidence that this scorer never reads. Its menu must still contain the same correct candidate. This requires more than a nominal attention mask:

- The request representation cannot read untrusted state, tool outputs, screenshots, or other speakers' audio.
- The correct option retains its identity, text/tokens, positions, and computation. Candidate edits cannot trigger whole-menu truncation, top-K ejection, changed tokenization boundaries, menu normalization, or global/sequence-dependent preprocessing.
- Structural delimiters, option identity resolution, and the mask itself are controlled by the host, not by injected content.
- No sequence/batch-level expert capacity, token dropping, shared dynamic scaling, or other cross-candidate computation can affect the protected score.
- Correctness labels are preserved. Adding a genuinely better tool, changing the gold tool's semantics/backend, or changing the actual task is not merely a non-gold catalog edit.

Ordinary independent encoders/cross-encoders can meet the same assumptions. A model brand, pointer head, or isolation flag alone does not establish them.

### 2.2 Calibration and pathwise invariance

Let `S_i = s(X_i,Y_i)` and `k = ceil((n+1)*(1-alpha))`. Set `q = S_(k)` if `k <= n`, and **`q = +infinity` if `k = n+1`**. Do not clip that out-of-range rank to the largest observed score. Retain all threshold ties with `<=`.

Define the candidate-universe set and its menu restriction by

`C(x) = {c : s(x,c) <= q}`

`P(x,M) = M intersect C(x)`.

For every admissible attacked menu `M_A` containing the unchanged gold candidate,

`1{Y in P(X,M_A)} = 1{s(X,Y) <= q}`.

Thus gold membership is unchanged **for each paired row**, not merely similar on average. Standard split-conformal coverage gives

`Pr[Y in P(X,M_A)] >= 1-alpha`.

The probability is over the clean calibration/test experiment, conditional on independently fixing the scorer. Exchangeability of the attacked menus is unnecessary because they disappear from the gold-score event. This is not per-request, calibration-conditional, class-conditional, or validity after an attacker selects an easier-to-break request population.

For additions only, `P(x,M) subseteq P(x,M union A)`. Removing/renaming only non-gold tools also preserves gold membership, although it can shrink or otherwise change the set and the acceptance rate. Recalibration is unnecessary for those **label-preserving, computation-preserving** edits, not for arbitrary new gold tools or deployment shifts.

### 2.3 Certified singleton mode

Permit a call only when the **original** `P` contains exactly one tool and a readiness check allows it. Readiness may veto the call; it cannot replace its identity. Otherwise ask/defer without executing a substitute.

Then, pathwise,

`{wrong tool identity AND acted} subseteq {Y not in P}`,

so `Pr[wrong tool identity AND acted] <= alpha` under the assumptions above.

If an allowed addition starts from a covered correct singleton, it cannot produce a wrong singleton: the gold stays in the set. It may add accepted distractors and cause deferral. Wrong singleton calls remain possible on the miscoverage rows. Consequently, an attacker cannot redirect must be qualified by the protected-coverage event and the policy, not stated unconditionally.

Let `p_act = Pr[acted]`. The implied conditional error bound is only

`Pr[wrong identity | acted] <= min(1, alpha / p_act)`.

For example, alpha `0.10` with acceptance `0.50` permits a conditional-error upper bound of `0.20`; sufficiently severe deferral can make this bound vacuous. This is an illustration of the theorem, not a measured Soro result.

### 2.4 What this does not certify

It does not certify tool arguments, destinations, authorization, readiness, side effects, successful execution, human/teacher correctness, or a missing correct tool. A singleton containing the right tool ID can still execute an unsafe call. A no-tool/ask/call label space is possible, but requires its own semantic labels, scorer, and calibration; it is not supplied by a tool-only set.

Exact computational independence and floating-point measurement are different. If one had a verified uniform bound `s_attack(x,y) <= s_clean(x,y) + epsilon`, an inflated threshold `q + epsilon` would preserve clean inclusion. Measured spread on a finite menu audit is not such a uniform certificate. A fixed sigmoid is monotone and does not change conformal sets when its threshold is transformed consistently; only a genuinely different learned score/normalization can improve efficiency.

## 3. Stage two: containment is not correct execution

V9 Section 2.1 allows stage two to choose within `P`, but also says that several options imply ask. Keep the latter execution rule explicit. If narrowing a multi-option set is allowed to authorize a call, Section 1.2's singleton integrity argument no longer applies.

Counterexample: on every query the protected set is `P = {gold, malicious}`. Coverage is **100%**. Untrusted evidence makes the refiner select `malicious` and execute it on every query. Wrong-action rate is **100%**. Set coverage alone cannot bound this selector's error.

Two separately reported modes are therefore required:

1. **Certified singleton mode:** the original protected set is singleton; refinement/readiness may veto but cannot change tool identity. The joint identity-error bound applies.
2. **Contained interaction mode:** stage two ranks/selects within a multi-option protected set. Membership containment holds; correctness, readiness, and argument safety need independent evidence, trusted confirmation, or a separately justified certificate.

For screenshots, identifying the tool from the request and filling its arguments from an image may be useful even with a singleton. The identity bound does not certify the image-derived values. If the image genuinely determines which tool is correct, excluding it from stage one can force ambiguity; arbitrary hostile evidence cannot also be trusted to resolve that ambiguity correctly without additional assumptions. CaMeL-NOVA's branch-steering discussion is a close prior warning about unintended choices within preauthorized control flow.

For speech, calling the user channel trusted is an explicit assumption, not authentication. Concurrent background/second-speaker injection attacks the request representation itself and is outside the unchanged-request theorem. Source separation or speaker similarity does not establish an adversary-proof trusted channel.

## 4. Primary-source reading register

**Targeted primary reading** means the named sections, definitions, algorithms, or proofs were examined, not that every page and appendix was read. Reading performed before this continuation and recorded in the inherited audit is included. **Carry-over** below means the earlier literature register's targeted reading, not a fresh full-paper reread. Public performance claims are not replications. These supplemental sources have not all been added to the manuscript bibliography; its existing 66-entry count is unchanged.

### 4.1 Conformal retrieval, pruning, and decisions

| Work and primary source | Reading depth | What matters for V9 |
|---|---|---|
| [Conformal Evidence Sets, 2611.10335v1](https://arxiv.org/html/2611.10335v1) | See Section 1.1. | Direct overlap with the distractor-invariance observation. |
| [TRAQ, NAACL 2024](https://aclanthology.org/2024.naacl-long.210.pdf), [2307.04642](https://arxiv.org/html/2307.04642) | Assumptions in Section 3.1; Section 3.2, Eq. (3), Lemma 2.1, and aggregation. | Already calibrates negative query--passage inner products on gold pairs and thresholds candidates pointwise. Top-K gold inclusion is an explicit premise; retrieval saturation can break it. |
| [Streamlining Conformal Information Retrieval via Score Refinement, 2410.02914](https://arxiv.org/html/2410.02914) | Sections 2--4, score transformations and appendix. | Vanilla conformal retrieval is pointwise. The proposed max-score normalization and rank weights are candidate-dependent; compare both, rather than treating all conformal retrieval as protected. |
| [Two-stage Risk Control with Application to Ranked Retrieval, 2404.17769](https://arxiv.org/html/2404.17769) | Sections 2--3.2, risk definitions and two-stage construction. | Retrieval/ranking risk control is prior art. Exchangeability and the calibrated loss procedure do not give arbitrary attacked stage-two correctness. Earlier versions used a different ranked-retrieval title. |
| [Prune 'n Predict, ICML 2025](https://proceedings.mlr.press/v267/vishwakarma25b.html), [2501.00555v2](https://arxiv.org/html/2501.00555v2) | Sections 2--3.2, Remark 3.3, Appendices C.3/C.4 and ToolAlpaca results. | CROQ conformally prunes and then re-prompts using retained choices; cheap pairwise first-stage scores are explicitly allowed. CP-OPT improves set efficiency. Its original-answer boundary/fallback behavior is not V9's strict singleton gate, but two-stage pruning is not new. |
| [KnowNo, 2307.01928v2](https://arxiv.org/abs/2307.01928v2) | Cached primary text: system formulation, singleton/help steps, statistical task-success premises. | Acts on singleton plans and asks a supervisor otherwise. Its guarantees involve the help/execution assumptions, not arbitrary tool-metadata poisoning. |
| [Conformal Intent Classification and Clarification, 2403.18973v1](https://arxiv.org/html/2403.18973) | Section 3, Algorithm 1, uncertainty/size and OOS discussion. | Singleton intent -> normal bot response; small multi-intent set -> clarification; very large set -> ambiguity response. Neither asking on a set nor set-to-action policies are new. |
| [Conformal Cascade, 2607.25018v3](https://arxiv.org/abs/2607.25018v3) | Cached primary text: Sections 3.3--3.5, Algorithm 1, Theorem 2, selection-preservation assumption and fallback limits. | Explicit joint wrong-and-accepted bound; K-tier composition needs error budgeting, and an alpha-level selected-risk conclusion needs an additional selection assumption. Fallback answers do not inherit the singleton guarantee. |
| [IDCR, UAI 2026](https://proceedings.mlr.press/v337/nanivadekar26a.html) | Official PDF pages 2--3, complete Proposition 2.1 and volume/log-det construction. | A fixed retrieval policy and composite score calibrated on an independent split yield coverage of a downstream target ellipsoid. Not an assertion that a gold document's membership is invariant to arbitrary hostile candidate edits. |
| [CiteGuard: Conformal False-Discovery Control, ICML 2026](https://proceedings.mlr.press/v306/jiang26f.html) | Official PDF pages 2--4, null p-values, BH/BY method, Assumption 5.1 and Theorem 5.3. | Controls FDR among selected claims under null-score exchangeability and the dependence conditions. Postprocessing is outside that guarantee. Do not confuse it with the different citation-attribution paper named CiteGuard at 2510.17853. |
| [Conformal Robustness Control, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/file/a80188f9b1246d4b95d396165cf99207-Paper-Conference.pdf) | Introduction/CRO formulation and calibration procedure, Algorithm 2 and Theorem 4.1. | Decisions are checked via losses over a set of plausible outcomes, not merely chosen as a member of that set. This is robust optimization under outcome uncertainty, not an adversarial tool-menu theorem. |
| [CAS: Conformalized Agentic Search, 2608.20771v1](https://arxiv.org/html/2608.20771) | Sections 2--3.2. | Retrieval softmax/APS and adaptive-conformal training signals are candidate-dependent; adaptive conformal for agentic retrieval is already a studied combination. |

### 4.2 Isolation, authorization, and certified robustness

| Work and primary source | Reading depth | Actual comparison boundary |
|---|---|---|
| [Drex, 2611.07854v2](https://arxiv.org/abs/2611.07854v2) | Earlier deep register audit; fresh cached Appendix C.2 reading for option isolation, decide readout and MoE assumptions. | Optional option isolation/shared positions are described for attention-only backbones. The decide token still reads all options; isolated option states do not imply a request-only final raw score. Hybrid recurrence, not MoE as a category, prevents arbitrary masking. No native Drex replication is produced here. |
| [Set-LLM, 2505.15433v1](https://arxiv.org/abs/2505.15433v1); [PCW, 2212.10947v3](https://arxiv.org/abs/2212.10947v3) | Carry-over: Set-LLM Sections 3.1--3.3 and MCQ evaluation; PCW mask/position reuse. | Isolation, shared positions and causal-window reuse are prior architecture ingredients. Neither should be omitted in a single-pass/order-stability comparison. |
| [Certifiably Robust RAG against Retrieval Corruption, 2405.15556v2](https://arxiv.org/html/2405.15556v2) | Threat/robustness definitions in Section II; isolation and secure aggregation in III--IV. | Bounded corrupted-passage budget plus certified aggregation. Includes finite-classification warm-ups, so dismissing it merely as generative RAG is inaccurate. Different certificate from unbounded distractor additions preserving a gold candidate. |
| [LLMCert-T, 2510.03992v2](https://arxiv.org/html/2510.03992v2) | Sections 1--2.5, mitigation study in 4.5 and parts of the attack generator. | Binomial confidence bounds concern outcomes under a specified inserted-tool attack process, with trial-unit assumptions. A measurement certificate over that attack distribution is not a defense valid against every adaptive menu. |
| [CAGE, 2607.29190v1](https://arxiv.org/html/2607.29190v1) | Setup, threat model and authorization object; backend soundness proofs not fully reread. | Certifies authorization over a joint neighborhood of typed tool returns, including categorical binding faults/numeric drift. Safe-for-all-return authorization differs from selecting any member of a set of plausible correct tools. |
| [PlanGuard, 2604.10134v1](https://arxiv.org/html/2604.10134) | Sections III--IV; experiments/cost discussion V--VI. | Reference actions derive from user instructions **and tool definitions**, not user text alone. Hard checks and an intent verifier are prior two-stage design. Reported zero-ASR results use InjecAgent with a compliance-inducing prompt; they are not a uniform theorem covering poisoned tool definitions. |
| [Tool-Guard, 2606.20922v1](https://arxiv.org/html/2606.20922) | Cross-tool poisoning setting; Section 4.2 algorithm/validation/list updates and 5.2 overhead. | Quarantines influential tool descriptions into separate planning lists, then validates alignment and arguments. It explicitly targets cross-tool description poisoning. Its reported latency ratio is specific to GPT-4o-mini/AgentDojo, not a universal cost multiplier. |
| [Design Patterns for Securing LLM Agents, 2506.08837v3](https://arxiv.org/html/2506.08837v3) | Action-selector, plan-then-execute and dual-LLM patterns. | Fixed pre-evidence control flow/allowlists are prior system designs. Argument/data-flow hazards remain, even when no new tool can enter a plan. |
| [CaMeLs Can Use Computers Too, 2601.09923v3](https://arxiv.org/html/2601.09923) | Section 3.1, beginning of 3.2, trusted planning and branch-steering discussion. | CaMeL-NOVA plans before screenshots; quarantined perception supplies values/branch tests. A malicious image can steer an unintended but preauthorized branch. Relevant to V9's within-set residual and vision utility. |
| [ARGUS, 2605.03378v2](https://arxiv.org/html/2605.03378v2) | Sections 4.1--4.3, workflow/components and threat context. | Influence/provenance graph, grounding and request-invariant checks; no pointwise menu-invariance conformal mechanism established by those sections. |
| [AttriGuard, 2603.10749v2](https://arxiv.org/html/2603.10749v2) | Sections 2.2--2.3, causal definitions in 3, shadow replay in 4.1--4.2. | Replays attenuated observations and gates calls by survival. Distinguishes control-flow from same-tool malicious-argument attacks; restricting tool IDs alone is insufficient for the latter. |
| [Role-Stratified Per-Field CRC, 2607.24343v2](https://arxiv.org/html/2607.24343) | Role-specific loss/calibration, runtime enforcement, Proposition 3 and its proof, simultaneous certificate and shift scope. | Already ties conformal risk to detector-relative noninterference and risk/utility at the argument-role level. Requires role-field exchangeability or fresh calibration; not clean-score immunity to every possible new poison. Multiple correlated fields need careful statistical units. |
| [Brain-Prompt Injection, 2606.09315v1](https://arxiv.org/html/2606.09315) | Section 4.1, Proposition 2/Corollary 3 and unchanged-channel argument; non-controllability boundary in 4.2. | An isolated confirmer transfers a false-accept bound to attacked routes because its score is unchanged: close proof pattern, not menu sets. Its displayed inclusive `>=` test/uniform-rank proof needs a no-ties or tie-handling qualification; constant tied scores would violate the displayed tail bound. Do not copy that boundary convention into V9. |
| [Robust Yet Efficient Conformal Prediction Sets, 2407.09165](https://arxiv.org/html/2407.09165) | Sections 2--3.2, Definition 3.1 and Proposition 3.1. | Coverage through verified score bounds and robust-set inclusion. Threat models include discrete/sparse cases as well as continuous perturbations; not merely norm-bounded images. Zero influence on the gold score is a special robustness case. |
| [Reliable Conformal Sets under Data Poisoning, 2410.09878v4](https://arxiv.org/html/2410.09878) | Sections 3--5 and coverage/size reliability definitions. | Bounded training/calibration edits, including insert/delete/label changes and arbitrary-magnitude features; partitioned classifiers/calibrators. Not inference-time menu edits. |
| [Open-Set and Imbalanced Conformal Classification, 2510.13037v1](https://arxiv.org/html/2510.13037) | Sections 2, 3.4 and 4.1. | Infinite/countable label dictionary and unseen-label treatment under exchangeable examples. Changing the true label space is different from adding non-gold nuisance candidates while preserving the gold representation. |

### 4.3 Attacks, filtering, and availability

| Work and primary source | Reading depth | Evaluation consequence |
|---|---|---|
| [ToolHijacker / Prompt Injection Attack to Tool Selection in LLM Agents, NDSS 2026](https://www.ndss-symposium.org/ndss-paper/prompt-injection-attack-to-tool-selection-in-llm-agents/), [2504.19793](https://arxiv.org/abs/2504.19793) | Fresh cached threat model, Section III optimization/selection search; earlier register's evaluation/defense reading. | No-box malicious-tool documents target both retrieval and selection via shadow pipelines. A manually appended always-choose-me instruction is not a faithful reproduction of the optimized attack. Code/document availability must be checked; the official repository describes controlled release. |
| [Spoofing the Toolbox, 2610.33182v1](https://arxiv.org/html/2610.33182) | Sections 3--4, feedback categories and stealth/optimization objective. | Benign-looking malicious near-duplicates test self-promotion even without obvious imperative injection. Poisoned-candidate admission and deferral cost are necessary metrics. |
| [ToolFlood, 2603.13950v1](https://arxiv.org/html/2603.13950) | Sections 3.3--3.5 and 4.1--4.3, covering objective and greedy attack. | Attacks top-K retrieval to remove benign tools. This is outside the gold-preserved theorem but inside a realistic system threat model; test the residual rather than silently force gold inclusion everywhere. |
| [TrustDesc, 2604.07536v1](https://arxiv.org/html/2604.07536) | Threat/design overview; Section 4.2 code-grounded descriptions and dynamic verification design. | Trusted descriptions derived from implementations are a different defense and a relevant baseline where tool code is available. That extra source access must be disclosed in comparisons. |
| [Universal Defenses for Tool-Integrated LLM Agents, 2609.16098](https://arxiv.org/html/2609.16098) | Sections 3.1.1--3.1.2, embedding/Isolation-Forest filtering and normal-tool recalling. | Anomaly filtering is menu-dependent; restoring a known benign catalog assumes a trusted pre-attack snapshot. These are simpler comparisons, with their information privileges stated. |
| [Risk-Aware Reranking for Agentic Tool Retrieval, 2608.22751](https://arxiv.org/html/2608.22751) | Method overview and related work. | Relevance/risk heads on a frozen tool encoder are a close compact safety--utility comparator. Optional graph smoothing can reintroduce candidate interaction. A pointwise version plus CP belongs in the baseline set. |
| [GuardRAG, 2610.35071v1](https://arxiv.org/html/2610.35071) | Section 4 algorithm/stages. | Expanded retrieval, deduplication and suspicious-cluster pruning address coordinated poisoning empirically. Filtering can alter gold availability; no menu-agnostic CP theorem was established by this method reading. |
| [Ranked by Position, 2607.24869v1](https://arxiv.org/html/2607.24869) | Threat model and Section 6 encoder/pointwise controls, defense comparison. | Pointwise and architectural invariance already prevent order-only promotion in this evaluation, with quality trade-offs. It does not show immunity to metadata/content attacks or prove CP validity for listwise systems. |
| [Is Conformal Factuality for RAG-based LLMs Robust?, 2603.16817](https://arxiv.org/html/2603.16817) | Problem/scoring context and Sections 5.1--5.3. | Its distractor protocol modifies/replaces generated claims and shifts factuality-score distributions; it is not a pathwise experiment that merely adds candidates while preserving the gold score. Do not cite it as establishing that V9's listwise baseline must fail under the same attack. |
| [Beyond Perturbations, 2007.05145v3](https://arxiv.org/html/2007.05145) | Rejectron algorithm, Lemma 5.1, Theorems 5.2--5.3 and transductive framing. | Arbitrary test-example robustness with rejection is established under its learning-class/data assumptions. Both low error and rejection on genuine traffic matter; V9 is not the first integrity-versus-availability framing. |
| [Playing it Safe, 1911.11253](https://arxiv.org/html/1911.11253) | Section 3 definitions, natural/adversarial error and abstention trade-off. | Focuses on bounded input perturbations and counts wrong-and-not-abstained adversarial outcomes. It should not be grouped as if all these works cover arbitrary unbounded test examples. |
| [Robust Adversarial Classification via Abstaining, 2104.02334v2](https://arxiv.org/html/2104.02334) | Error definitions and Theorem III.1 trade-off. | Binary hypothesis-testing/abstention-region trade-off; not a conformal tool-menu construction. Availability costs cannot be hidden by reporting adversarial error alone. |

### 4.4 Online coverage and feedback

| Work and primary source | Reading depth | What can and cannot be inherited |
|---|---|---|
| [Adaptive Conformal Inference, 2106.00170](https://arxiv.org/abs/2106.00170) | Carry-over primary theory/update reading recorded in the earlier register; cached source available. | Standard ACI tracks the correct per-round inclusion loss with the appropriate boundary actions. It is not a new method here, nor an all-traffic guarantee from labels available only on deferrals. |
| [Efficient Online Conformal Selection with Limited Feedback, 2605.14953v4](https://arxiv.org/html/2605.14953) | Sections 2.1--2.3, Algorithm/update and Theorem 1 proof; threshold-instantiation context. | Bandit feedback supplies the chosen set's actual success indicator, not arbitrary execution proxies. Known always-success/always-fail boundary actions stabilize an unprojected update. Adversarial validity and stochastic efficiency are separate objectives. Do not claim that conformal selection necessarily needs every full label. |
| [Capacity-Constrained Delayed Feedback for Online Conformal Risk Control, 2611.17059v1](https://arxiv.org/html/2611.17059) | Sections IV-A/IV-B, Eq. (22) and Theorem 1/assumption context; submitted 12 November 2026. | Randomized feedback tracking and inverse-probability weighting compensate for missing/delayed outcomes under declared delay/capacity assumptions. Its risk-gap bound has extra terms; it does not justify dropping V9's selectively missing losses from a plain update. |
| [Online Conformal Prediction for Non-Exchangeable Panel Data, 2605.17705](https://arxiv.org/html/2605.17705) | Algorithm/theory framing and Appendix B.2.5, Proposition B.14 and proof. | Revealed-round updates differ from all-round coverage by a selection-bias term without MCAR. A deferral-dependent reveal policy is not automatically representative. This is a feedback warning, not an assertion that no valid selective-feedback method exists. |
| [SHIFT-JEV, 2610.34329v1](https://arxiv.org/html/2610.34329) | Sections 3.1--3.6, certification procedure, candidate-set perturbations and stated Appendix-B guarantee boundary. | Small decision models, distractors/gold removal, risk-based abstention and continual adaptation already share much of the setting. Fixed-sequence LTT certifies selected risk within exchangeable known regimes; unseen-shift outcomes remain empirical. No protected-gold pointwise score is supplied by its listwise/trie procedure. |
| [Conformal LLM Routing with Distribution-Free Safety Guarantees, ACL SRW 2026](https://aclanthology.org/2026.acl-srw.70.pdf) | Official full text: Section 3 gate/calibration setup and comparison of guarantee objects. | Input-embedding logistic safety gate with Clopper-Pearson calibration of routed-subset risk. **It is not the set-size/singleton router described in V9's search-summary row.** Conformal Cascade/KnowNo are the relevant sources for that policy. |
| [jev-certify, primary repository](https://github.com/nikkoxgonzales/jev-certify) | README loss, calibration/action design, scope/shift limits; no code execution or replication. | Public CP/CRC applied to a decision-model routing interface exists. The declared routing loss is joint wrong-and-auto-routed, not conditional routed risk. Repository evidence is not a peer-reviewed arbitrary-poisoning theorem or a verified release-priority date. |
| CCPO (2511.11828), ToolChain-CRC (2606.18467), PACE | Carry-over primary sections and premise checks in `PAPER_LITERATURE_NOTES.md`, Section 2.7. | Adaptive LLM routing, tool-trajectory risk control and proactive pre-outcome signals are not open ingredient-level gaps. These were not all reread cover to cover in this V9 pass. |
| [Safe Planning via Iterative Policy Updates and Adversarially Robust CP, 2511.10586v2](https://arxiv.org/html/2511.10586) | Section 3.1 policy-induced shift/ACP construction and premise context. | Interactive physical planning uses bounded trajectory perturbations to transfer certificates across policy updates. It is not an arbitrary injected-menu guarantee. |

### 4.5 Carried-over sources and unresolved items

- CaMeL (2503.18813), Task Shield (2412.16682), ClawGuard (2604.11790), MELON (2502.05174), StruQ, SecAlign, MCPTox, MCP-SafetyBench, MCP-TDP, VPI-Bench, and concurrent audio injection/CADV (2607.28165) retain their individually recorded primary-reading depth in the earlier register. Their complete appendices were not all freshly reread for this audit.
- The exact `conformal-tool-exposure` repository named in V9 was **not independently located** in the exact-name/GitHub/ToolRet searches. Require its owner/URL and commit history before citing its detailed API, results, or priority. The verified `jev-certify` repository is a different artifact, not a substitute identity for it.
- *Confidence on the focal: conformal prediction with selection-conditional coverage* (JRSSB 2025), *Auditing RAG Necessity* (EMNLP 2026), and *Adaptive Retrieval, Selective Answers* (2610.34872) were discovery/metadata leads, not full method audits. They cannot be used to assert detailed novelty exclusions or absence of overlap.
- CAGE's complete backend proofs, AttriGuard's full fuzzy-test analysis, all current author/version/venue metadata and implementation parity for prospective baselines remain pre-citation/pre-submission work when their detailed claims are used. This audit does not claim every result in every cited paper was independently verified.

## 5. Corrections to V9 before building on it

### 5.1 Claims and model boundaries

- Supersede V9 Section 3.2's moderate-confidence first-property conclusion: the expanded audit found direct wording and older constructions. An exact identical end-to-end tool system was not established, but that does not restore priority for the central observation.
- Replace listwise models lose coverage with **candidate-dependent scores can lose coverage under specified attacks**. Noninterference is sufficient, not necessary, for robustness. Training, robust conformal sets, special score constructions or uninformatively full sets can preserve coverage in other models.
- Softmax is not itself an impossibility result: with independent raw candidate/anchor scores, a fixed-anchor probability ratio can cancel the menu denominator. Compare the actual score procedure, not just a model label.
- Every protected raw score must come from the trusted request readout and the isolated option. Archived softmax probabilities or scores using a refined/menu-dependent query vector cannot be reinterpreted as those scores after the fact.
- Drex already describes optional isolation. Its all-option decide readout is a distinct issue from the option mask. MoE routing can preserve independence when it is token-local and has no shared capacity/drop behavior; a fixed menu order does not repair capacity interference. Active parameter count is not a VRAM or latency guarantee.

### 5.2 Feedback and proactive thresholds

For a plain protected-score ACI update, the required feedback is the **correct inclusion loss of the chosen set** on each update round, not necessarily the entire gold label. A teacher label can supply it only when that label is correct. An executed tool returning success is not automatically evidence that the intended task/action was correct or that the protected set covered the true label.

Updating only on labelled/deferred requests generally controls a selected feedback stream, not all traffic. Valid alternatives with restricted feedback exist, but require their own assumptions, exploration/tracking policy, propensity correction, boundary actions and proof. Compare complete true inclusion feedback, delayed feedback, randomized audits, deferral-only teacher feedback and execution proxies separately. Do not attach the same theorem to all of them.

A proactive rule that only **widens** a valid reference set preserves its inclusion guarantee by set containment, but may worsen availability. Shrinking or replacing it needs new calibration. If future thresholds depend on menu-induced deferrals, attacks can also change later feedback/thresholds: instantaneous score independence does not establish independence of the whole adaptive controller.

## 6. Experiments that can decide the remaining contribution

All entries here are recommendations, not results. Preserve one-variable runs, explicit seeds, checkpoint IDs and per-split artifacts.

| Gate / experiment | Required change to the V9 question |
|---|---|
| E0: validity | Define the independent calibration/test unit and keep source/request groups disjoint. Fix finite-sample rank/infinity and identity-based selection in implementation later; authenticate checkpoints and native baseline protocols. These are not fixed by this audit. |
| E1: no-training pilot | Obtain fresh genuinely request-only, pre-refiner scores and recalibrate that procedure. Report coverage, size, original-singleton rate and readiness-vetoed acceptance across prespecified levels. Do not tune head/gates on the final external test. |
| E2: attacked twins | First test **pathwise identical gold membership**, fixed threshold and unchanged gold computation. Then compare joint wrong-identity actions, conditional accepted risk, deferral and actual attack objectives. Include optimized/stealthy distractors, not only obvious imperative text. |
| E3: catalog growth | Separate gold-preserving additions/edits from new gold tools, top-K ejection and gold removal. The static-threshold claim concerns only the first category. Report utility/size beside unchanged coverage. |
| E4: contained interaction | Compare collision/ask quality in multi-option sets, but label those autonomous stage-two selections as empirical containment mode. Do not apply the original-singleton alpha bound to a narrowed singleton. |
| E5: residuals/availability | Missing gold, gold-text tampering, misleading near-clones, unsafe arguments and the minimum attacker effort to cause deferral are main outcomes, not appendix-only exceptions. State identity/registry privileges of each attacker. |
| E6: speech/online | Establish trusted-channel/label-preserving twins and actual speech calibration. Text--speech coupling is a corollary with target-distribution premises. Distinguish genuine inclusion feedback from proxies/selective streams. |
| E7: screenshot evidence | Separate tool-ID containment from value/argument authorization, readiness and task success. Include benign evidence-required minimal pairs and malicious branch/within-set steering. |
| E8: closest baselines | Add TRAQ-style pointwise CP, an independent encoder/cross-encoder scorer, CROQ, native validated Drex, PlanGuard/Tool-Guard, Task Shield/MELON adaptations, and simple allowlist/deferral controls. Include a stable sorted-menu control without presenting it as noninterference. |

### 6.1 Match utility, information, and compute

The important comparator is **an ordinary pointwise scorer with the same CP rule**, not just unprotected Drex. If it achieves the same safety/availability at equal or lower cost, the special architecture needs another measured advantage. Match training data, clean utility/acceptance, menu sizes and attack budget; separately label baselines with trusted catalog snapshots, tool implementations or extra model calls.

Required outputs include gold inclusion, empty/set-size distributions, original-singleton rate, wrong-and-acted rate, error conditional on acting, benign and attacked deferral, task success and unsafe arguments. Also report paired correct-singleton -> wrong-action transitions, attacker queries/tokens/injected-candidate count, latency/VRAM and attack-conditioned denominators. Large sets or defer-everything controls must be visible on the same frontier.

The earlier register recounts **1,200 rows, 115 inferred parent IDs and 321 request-text groups**; these are not 1,200 established independent tasks. Choose and justify a sampling unit rather than only adding clustered confidence intervals. A 90%-coverage/50%-singleton development gate is a feasibility diagnostic, not a strong security certificate. At alpha `0.01`, at least `99` calibration units are needed even to permit a finite standard threshold; useful efficiency and tight test uncertainty require substantially more evidence. Do not multiply effective sample size by repeated menus or seeds.

If a distinct attacker-controlled identity can use the same scored representation as an accepted gold tool, both enter the protected set and singleton execution stops. When scored identities/registry rules prevent exact cloning, near-clone admission is an empirical question. **No availability guarantee follows from noninterference.** Measure that failure cost before claiming useful robustness.

## 7. Paper positioning and go/no-go criteria

A defensible candidate pitch is:

> We study the security--availability trade-off of conformal candidate filtering for compact tool-decision models. A noninterfering request--option score inherits a gold-inclusion guarantee under label-preserving distractor attacks; an original-singleton execution policy converts it into a joint tool-identity error bound. We evaluate an efficient implementation and contained evidence-aware refinement against prior pointwise, conformal-pruning and runtime defenses.

This is a **proposed research framing**, not a claim that the implementation or experiments already satisfy it. Credit the retrieval, pruning, selective-execution and system-isolation priors explicitly. The theorem belongs as an attributed/scoped security corollary; the main paper must earn its contribution through efficiency, learned scoring, rigorous threat coverage and empirical separation.

Recommended decisions:

1. **Priority gate:** fail the strong first-observation/first-guarantee pitch now, rather than retaining it until 19 November. The identical full-system novelty question remains narrower and unresolved.
2. **Feasibility gate:** complete E0/E1 on development data and compare the ordinary pointwise baseline before scaling training or renting a large-model GPU.
3. **Contribution gate:** continue a method paper only if it improves the security--utility--compute frontier, or exposes a substantial previously unmeasured failure with a reproducible benchmark. Merely preserving coverage through very large sets is insufficient.
4. **Multimodal gate:** include speech/screenshots when they test the declared trust boundary and utility cost. Do not use modality count or MoE size as a replacement for a clear contribution.
5. **Submission gate:** revise the manuscript deliberately, update citation versions and run the native controlled evaluations. An internal 20 December preprint target is not an official conference deadline or an acceptance indication.

A good paper remains possible; **A* strength is not established by this plan or this audit**. A small-model security/availability result with strong closest-prior comparisons could be compelling. Combining known components and an elementary inclusion argument without nontrivial results is not enough to justify a top-tier prediction.

### 7.1 Read-only addendum: V10 appeared during the audit

`docs/EXEC_PLAN_V10.md` appeared after the initial repository snapshot and was subsequently read, not edited. Its explicit refusal to claim a new theorem and its emphasis on a measured security--utility comparison move in the right direction. It does not erase the remaining issues:

- Its headline that today's menu-normalized sets lose their guarantee is still too universal. The absence of a menu-invariance theorem does not prove that every pipeline will empirically under-cover. Specify attack classes and measured systems; benign growth changes the claim only when it preserves the gold/task and the relevant computation.
- Keep original-singleton execution explicit in B5/C4. Stage-two refinement inside a larger set has no inherited alpha correctness bound, even though it is contained.
- Three pipelines with a 15-point drop and 60% singleton acceptance are internal feasibility targets, **not conference acceptance rules**. At alpha `0.10` and acceptance `0.60`, the elementary conditional-error upper bound is about `0.167`. Add stricter levels, uncertainty and matching utility rather than describing those targets as sufficient for a main-track paper.
- A3's Qwen-bfloat16 spread is a numerical control, not a logical test of Gemma's mask. Different backbones/weights/scales can have different rounding amplification. Similar spreads do not prove a correct mask; dissimilar spreads do not prove a leak. Compare Gemma against its own fp32/order/other-candidate perturbation behavior and inspect actual dependency paths.
- B2 still names the unlocated `conformal-tool-exposure` artifact. Authenticate that identity before using it. B3 also needs the TRAQ-style pointwise-CP and CROQ comparisons, not only a bare cross-encoder and runtime guards.
- Section 7's trusted/untrusted competition idea remains unaudited, as V10 states. Even if untrusted tools cannot affect trusted-group scores, adding trusted tools can still change those scores. Its menu-growth guarantee would need a different, explicitly partitioned threat model.

No new primary-source novelty clearance is implied for V10 Section 7. The preprint/conference dates there remain targets to verify against official calls, not claims of submission readiness.

## 8. Search coverage, provenance, and limits

### 8.1 Search and reading scope

The continued audit used targeted searches across conformal retrieval/reranking, adversarial candidates/catalogs, singleton/selective risk, isolate-then-aggregate RAG, authorization/reference plans, small decision-model calibration, and restricted-feedback online CP. It followed references and inspected primary methods/theorems rather than accepting search summaries as novelty evidence.

Representative exact queries from the continuation include:

- `conformal tool poisoning reference`
- `PlanGuard 2604.10134` and `Tool-Guard 2606.20922`
- `conformal-tool-exposure`, including GitHub/ToolRet and Jev variants
- `Conformal LLM Routing 2026 SRW`
- `adaptive conformal selective feedback`
- `conformal prediction missing feedback`
- `adaptive conformal inference bandit feedback`
- `online conformal selective labels`

Earlier audit queries covered pointwise retrieval thresholds, adversarial distractor invariance, candidate-set/reranking attacks, singleton execution, secure aggregation and the primary identities in V9 Section 3. No exact grand total is asserted: search output was sometimes merged/truncated, and result retrieval is not full screening. Likewise, downloading/extracting a PDF is not recorded as cover-to-cover reading.

**No literature search can certify that no unpublished, unindexed, newly revised or future paper will overlap.** This audit can falsify broad claims already contradicted by located priors, identify the closest mandatory baselines, and record what narrower distinction still needs evidence. It cannot promise no later novelty objections.

Before submission, freeze cited versions and recheck the claim-to-prior matrix. Every proposed novelty statement needs a precise object, threat model, assumption set, closest construction and measured difference. Unread leads cannot support a first claim, and incomplete reading should remain visible rather than be described as a completed review.

### 8.2 Local scope and verification record

Research was read-only. Documentation implementation is restricted to:

- `docs/PAPER_V9_NOVELTY_AUDIT.md`
- A companion link/warning in `docs/PAPER_LITERATURE_NOTES.md`

No training/evaluation code, results ledger, execution plan, manuscript, bibliography, figures or run configuration is changed. No tests, builds, experiments, model calls or GPU jobs are run. Official PMLR PDF theorem pages were fetched and text-extracted in memory; that is source reading, not a model evaluation. Existing cached primary texts were used for the targeted Drex/KnowNo/Cascade/ToolHijacker rereads.

Planning-policy record for this documentation deliverable:

`planning=deep; context_depth=dependency; verification_depth=structural; delegation=none; reasons=novelty-audit, security-claim-boundaries, documentation-only-user-scope`.

Decision: create a supplemental audit and index it, because a primary source contradicts the candidate first-property framing and the singleton execution boundary needs explicit repair. Risk is limited to research documentation. The original plan/draft remain intact for the user's deliberate revision.
