# Soro paper: literature and evidence register

Primary-source checks: **15–16 November 2026**; latest result/protocol and official-conference audit: **16 November 2026**. Companion draft: `paper/soro_decision.tex:1`; bibliography: `paper/soro_decision_refs.bib:1`.

**V9 update (16 November):** See [the protected-coverage novelty and validity audit](PAPER_V9_NOVELTY_AUDIT.md). It supersedes the first-property/moderate-confidence conclusion in `EXEC_PLAN_V9.md`, Section 3.2: direct distractor-invariance wording and older pointwise/prune-then-predict constructions were found. The wrong-action bound requires a singleton of the **original** protected set; stage-two narrowing gives containment only. The supplemental sources are not yet added to the 66-entry manuscript bibliography. Code, results, plan, and manuscript are unchanged by this audit.

## 1. Scope and reading status

This register supports the paper skeleton requested from `docs/PAPER_KT.md` and expanded for `docs/EXEC_PLAN_V8.md`. V8 supersedes conflicting V7 instructions while retaining text, readiness, speech, screenshots, streaming, size, distillation, and benchmark tracks. The register records what primary sources support, what the implementation actually does, and which results remain provisional. It does not replace or edit the user plans, knowledge-transfer note, or results ledger.

- **Targeted full text** means the named method, theorem, or evaluation sections were examined; it does not mean every page or appendix was read.
- **Abstract/metadata** means identity, title, authorship, and the high-level scope were checked. Detailed methodological claims still need a full-paper read before being expanded.
- **Implemented** means the relevant source path was inspected, not that a real-backbone experiment passed.
- **Reported** means an archived repository claim or artifact, not a fresh experimental replication.
- **Recounted** means counts/alignment were computed from available raw files in this drafting pass.
- **Proposed** means an experiment, integration, or policy that has no completed validation here.

The original bibliography covers all **32 arXiv identities plus Kev** in the KT list, including the resolved RLHN identity, and adds formal BFCL, Qwen3, and Gemma 4 sources: **36 references**. V8 added 22 references, giving 58. This update adds **eight primary-read references**, giving **66 total**: **63 distinct arXiv identities**, Kev, BFCL proceedings, and PACE proceedings. The additions are concurrent audio injection/CADV, Conformal Risk Control, conformal beyond exchangeability, Learning to Defer, SGR selective classification, CompRank, action-class calibration diagnostics, and the updated When2Tool paper. Checked refereed identities are used for CRC, beyond-exchangeability CP, and Learning to Defer; older entries retain their explicitly checked preprint dates rather than guessed venues. Very long original author lists use BibTeX's `and others`; Gemma uses its official corporate author. Complete authorship/version metadata remains in the three earlier snapshots and `scratch/paper_survey_2026_11_16/arxiv_new_metadata.xml` plus `arxiv_followup_metadata.xml`.

Primary PDFs for the previously cited 55 arXiv identities and the eight additions have been staged and text-extracted under `scratch/paper_survey_2026_11_16/`; BFCL's official full text is also cached, and PACE's checked full text remains in the V8 cache. **Downloaded/extracted does not mean read cover to cover.** The individually named methods, theorem premises, evaluations, and limitations below are the actual reading depth; complete appendix reading and author verification remain open.

The older, unrelated MGP manuscript at `paper/main.tex` and `paper/refs.bib` is preserved. Its catalogue-cache/scaling claims must not be inherited by the request-conditioned Soro pointer.

## 2. Primary-source reading register

### 2.1 Closest works: targeted full-text reading

| Bibliography key | Checked identity, first author(s), and year | Primary source and version | Reading depth / consequence |
|---|---|---|---|
| `dhankhar2026drex` | Nischay Dhankhar et al. (2026), *Towards Foundation Decision Models: Drex* | [2611.07854v2](https://arxiv.org/abs/2611.07854v2), revised 9 November 2026 | Targeted full text: native pointer/backbone design, supervised/consistency/RLAF training, calibration and order protocols, public-index results, limitations, and Appendices C, I, L. The native LM head is unused; optional isolation/shared positions are prior art. Mechanisms exist, but deployment robustness/calibration are empirical. See the detailed audit below. |
| `egressy2025setllm` | Beni Egressy and Jan Stuehmer (2025), *Set-LLM: A Permutation-Invariant LLM* | [2505.15433v1](https://arxiv.org/abs/2505.15433v1) | Targeted full text: sections 3.1-3.3 and MCQ evaluation. Shared positions plus cross-element isolation and an equivariance argument are prior art. The paper actually evaluates selection/MCQs on five backbones and four datasets. |
| `ratner2022pcw` | Nir Ratner et al. (2022 preprint), *Parallel Context Windows for Large Language Models* | [2212.10947v3](https://arxiv.org/abs/2212.10947v3) | Targeted full text: window mask and position reuse. Independently encoded causal windows; test/generated tokens can read across windows. ACL 2023 publication is distinct from the preprint year used here. |
| `bito2026invarirank` | Ethan Bito, Yongli Ren, and Estrid He (2026), *One Pass, Any Order: Position-Invariant Listwise Reranking for LLM-Based Recommendation* | [2604.27599v1](https://arxiv.org/abs/2604.27599v1) | Targeted full text: sections 3.3-3.5. Context-conditioned candidate isolation/shared RoPE is especially close. Recommendation menus use K=25, mean token-log-probability scoring, and ranking-oriented training. |
| `ross2025when2call` | Hayley Ross, Ameya Sunil Mahabaleshwarkar, and Yoshi Suhara (2025), *When2Call: When (not) to Call Tools* | [2504.18851v1](https://arxiv.org/abs/2504.18851v1) | Targeted full text: data construction, Table 2, metrics. Four response choices; direct answer is always wrong in the test construction. Publication training is APIGen-derived, testing is BFCL v2 Live-derived. Preserve system/tool context and official scoring. |
| `angelopoulos2021conformal` | Anastasios N. Angelopoulos and Stephen Bates (2021), *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification* | [2107.07511v6](https://arxiv.org/abs/2107.07511v6) | Targeted full text: section 1 and Appendix D. Standard marginal split-conformal proof and the infinite-quantile boundary; not a guarantee conditional on one arbitrary calibration sample. |
| `ren2023knowno` | Allen Z. Ren et al. (2023), *Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners* | [2307.01928v2](https://arxiv.org/abs/2307.01928v2) | Targeted full text: section 3.1 and help policy. Singleton act / non-singleton help is established. The paper also uses a calibration-conditional Beta-tail adjustment, stronger than the draft's standard marginal statement. |
| `dou2026cascade` | Yifan Dou, Shikan Lian, and Shibo Li (2026), *Conformal Cascade: Distribution-Free Accuracy Guarantees for Multi-Tier LLM Inference* | [2607.25018v3](https://arxiv.org/abs/2607.25018v3) | Targeted full text: routing and Theorem 2. Singleton acceptance and non-singleton/empty deferral are established. The generic bound concerns joint wrong-and-accepted events across tiers; stronger bounds require selection preservation. An uncertified final fallback is not thereby certified. |
| `rahman2026rolestratified` | Md Ashikur Rahman et al. (2026), *Beyond Aggregate Risk: Role-Stratified Conformal Risk Control for LLM Tool Calls* | [2607.24343v2](https://arxiv.org/abs/2607.24343v2) | Targeted full text: risk target and role construction. Security roles of argument fields, not classification coverage of tool identities. Complementary work, not an identical benchmark or guarantee. |
| `suri2025clarification` | Manan Suri et al. (2025), *Structured Uncertainty guided Clarification for LLM Agents* | [2511.08798v2](https://arxiv.org/abs/2511.08798v2) | Targeted full text: SAGE/ClarifyBench method. Already separates specification/model uncertainty, parameter beliefs, and cost-aware/EVPI-guided questions. The KT nickname is not the paper's title. |
| `zhou2026trust` | Yijin Zhou et al. (2026), *Exploring Agentic Tool-Calling Decisions via Uncertainty-Aligned Reinforcement Learning* | [2606.06976v1](https://arxiv.org/abs/2606.06976v1) | Targeted full text: action types and reward construction. TRUST uses four actions and perplexity-margin rewards, including generative payloads. A training comparator, not a pointer-equivariance or CP theorem. |
| `hu2026rassg` | Daijin Hu and Xi Wang (2026), *RASSG: Repair-Aware Semantic Survival Gating for Streaming Tool Execution* | [2610.14659v1](https://arxiv.org/abs/2610.14659v1) | Targeted full text: gating, invalidity calibration, and cancellation. Already uses calibrated argument-invalidity prediction and deadlines. Compare irreversible stale execution/repair, not just early launch latency. |

### 2.2 What the closest-paper comparison actually permits

The defensible working story is a **compact, auditable routing implementation and its stability/discrimination trade-off**, with a separate evaluation agenda for readiness and modalities. It is not "the first isolated-option architecture," "the first equivariant MCQ selector," "the first set-based deferral system," or "the first uncertainty-aware clarification model."

- Drex Appendix C.2 must be discussed explicitly. Request-readout isolation is a concrete architectural distinction, but the broader isolation idea is already acknowledged there and implemented in related set/reranking work.
- Set-LLM's random/adversarial MCQ permutation evaluation is relevant prior selection evidence. It evaluates all permutations except a cap of 24 for five-choice CommonsenseQA; do not characterize it as generative-only.
- The refiner's query row **also changes** and can depend on the entire menu as a set. Only pre-refinement option encodings are independent.
- A small controlled near-duplicate ablation could be useful evidence, but seven additional correct rows in one seed do not establish a new universal mechanism or a significant recovery.
- Drex's public robustness study uses 1,591 decisions from 1,040 common requests with original/reverse/random orders. Random-order flip rates (Max 4.3%, v2.0 5.9%, v1.5 5.3%) are not the same metric as being unstable over three orders or Soro's five-random-order event.
- Drex public-index When2Call uses 3,652 rows: v1.5 89.7%, v2.0 86.5%, Max 85.2%. Artificial Analysis scores, including Max 94.0%, use a different protocol. These are published context, not matched local baseline runs.

### 2.3 Remaining KT identities: reading depth retained individually

The 16 November pass deepens these previously abstract-only entries through the named primary method/protocol sections. These are targeted reads, not complete-paper or complete-appendix reads; published results are not reproduced. Earlier abstract-only status is superseded only where the concrete reading below is recorded.

| Bibliography key | Checked identity, first author(s), and preprint year | Primary source / checked version | Current use |
|---|---|---|---|
| `vinyals2015pointer` | Oriol Vinyals, Meire Fortunato, and Navdeep Jaitly (2015), *Pointer Networks* | [1506.03134v2](https://arxiv.org/abs/1506.03134v2) | Targeted full text: attention-pointer output construction and variable-size input/output setting. Prior distribution-over-inputs interface, not a guarantee of order invariance. |
| `zaheer2017deepsets` | Manzil Zaheer et al. (2017), *Deep Sets* | [1703.06114v3](https://arxiv.org/abs/1703.06114v3) | Targeted full text: invariant sum representation and equivariant-layer characterization. Set-function lineage; do not import universality beyond the stated domain/architecture conditions. |
| `lee2018settransformer` | Juho Lee et al. (2018 preprint), *Set Transformer: A Framework for Attention-based Permutation-Invariant Neural Networks* | [1810.00825v3](https://arxiv.org/abs/1810.00825v3) | Targeted full text: SAB/ISAB/PMA and equivariance/invariance argument. Set attention/refinement is prior art; published ICML 2019 identity remains distinct from the checked preprint-year entry. |
| `zheng2023mcq` | Chujie Zheng et al. (2023 preprint), *Large Language Models Are Not Robust Multiple Choice Selectors* | [2309.03882v4](https://arxiv.org/abs/2309.03882v4) | Targeted full text: option-order bias experiments and PriDe label-prior debiasing. Training/prompt averaging or label-prior correction is not architectural raw-score independence; no published flip rate is imported as a matched baseline. |
| `kumar2023conformalqa` | Bhawesh Kumar et al. (2023), *Conformal Prediction with Large Language Models for Multi-Choice Question Answering* | [2305.18404v3](https://arxiv.org/abs/2305.18404v3) | Targeted full text: MCQ nonconformity scores, calibration, and prediction-set evaluation. Standard classification-set construction; not conditional accepted-request risk or a tool-execution certificate. |
| `lin2025domainshift` | Zhexiao Lin et al. (2025), *Domain-Shift-Aware Conformal Prediction for Large Language Models* | [2510.05566v2](https://arxiv.org/abs/2510.05566v2) | Targeted full text in V8: sections 3-4. Embedding density-ratio weighting and regularized infinity mass; lower bound includes score-distribution total-variation correction. Prompt proximity is not arbitrary-shift or injection validity. |
| `lin2024hammer` | Qiqiang Lin et al. (2024), *Hammer: Robust Function-Calling for On-Device Language Models via Function Masking* | [2410.04587v2](https://arxiv.org/abs/2410.04587v2) | Targeted full text: function masking and augmentation, fitting data, and function-calling evaluation. Robustness to names is learned, not set equivariance. Generative schemas/arguments are outside our matched-menu metric. Both Jun Wang metadata entries remain retained. |
| `zhang2024xlam` | Jianguo Zhang et al. (2024), *xLAM: A Family of Large Action Models to Empower AI Agent Systems* | [2409.03215v1](https://arxiv.org/abs/2409.03215v1) | Targeted full text: action-model family, data/agent training pipeline, and function-calling evaluations. Broader generative action capability; must use a documented matched-menu scoring adapter. |
| `patil2023gorilla` | Shishir G. Patil et al. (2023), *Gorilla: Large Language Model Connected with Massive APIs* | [2305.15334v1](https://arxiv.org/abs/2305.15334v1) | Targeted full text: APIBench/API-grounded training, retrieval and call matching. Distinguish retrieval, correct API identity, and arguments; Gorilla is not a substitute for formal BFCL protocol attribution. |
| `shi2025toolret` | Zhengliang Shi et al. (2025), *Retrieval Models Aren't Tool-Savvy: Benchmarking Tool Retrieval for Large Language Models* | [2503.01763v2](https://arxiv.org/abs/2503.01763v2) | Targeted full text: task/tool collection, retrieval evaluation, and candidate-document setting. Retrieval quality is a separate stage from scoring a supplied complete menu; overlap manifests are required for benchmark use. |
| `liu2026agentabstain` | Xun Liu et al. (2026), *AgentAbstain: Do LLM Agents Know When Not to Act?* | [2607.10059v1](https://arxiv.org/abs/2607.10059v1) | Targeted full text: non-action task construction and abstention evaluation. Not acting appropriately is distinct from uncertainty-triggered deferral; source action labels must survive any local menu recast. |
| `menon2020logitadjustment` | Aditya Krishna Menon et al. (2020 preprint), *Long-tail learning via logit adjustment* | [2007.07314v2](https://arxiv.org/abs/2007.07314v2) | Targeted full text: prior-adjusted logits/loss and long-tail objective. Can rebalance class decisions, not restore omitted tool context or repair gold-action semantics. Checked preprint year is distinct from ICLR 2021 publication. |
| `pahwa2026audio2tool` | Ramit Pahwa et al. (2026), *Audio2Tool: Speak, Call, Act -- A Dataset for Benchmarking Speech Tool Use* | [2604.22821v2](https://arxiv.org/abs/2604.22821v2), [project](https://audio2tool.github.io/) | Targeted full text: benchmark domains, eight difficulty tiers, tool scoring, and Tier 8 primary/secondary intent blending. Speech attribution has prior art. Project lists Interspeech 2026 and DOI 10.21437/Interspeech.2026-2857; dataset permissions remain separately unverified. |
| `peng2026spokenfunction` | Yuezhang Peng et al. (2026), *Spoken Function Calling: A New Perspective on Spoken Language Understanding for Large Audio Language Models* | [2608.05126v2](https://arxiv.org/abs/2608.05126v2) | Targeted full text: spoken-function data construction, tool inventory, in/out-of-distribution evaluation, and speech/function scoring. Full function calls differ from tool-identity coverage; paper licence does not establish dataset reuse permission. |
| `lin2026fullduplex` | Guan-Ting Lin et al. (2026), *Full-Duplex-Bench-v3: Benchmarking Tool Use for Full-Duplex Voice Agents Under Real-World Disfluency* | [2604.04847v1](https://arxiv.org/abs/2604.04847v1) | Targeted full text: real speech/disfluency and full-duplex tool-use evaluation, including silent/non-call cases. Silence and incremental repair need distinct labels; this is not a guarantee for stopping-time action. |
| `radford2022whisper` | Alec Radford et al. (2022), *Robust Speech Recognition via Large-Scale Weak Supervision* | [2212.04356v1](https://arxiv.org/abs/2212.04356v1) | Targeted full text: weakly supervised training, decoding/ASR evaluation, and robustness limits. Suitable cascade/quality-audit reference; a transcript or WER is not an authenticated user-intent boundary. |
| `wu2025guiactor` | Qianhui Wu et al. (2025), *GUI-Actor: Coordinate-Free Visual Grounding for GUI Agents* | [2506.03143v1](https://arxiv.org/abs/2506.03143v1) | Targeted full text: attention-based visual grounding, pointer-style target readout, and training/evaluation. Visual-pointer prior, not evidence for current Soro screenshots or multimodal routing performance. |
| `prabhakar2026reranker` | Vignesh Prabhakar, Jialing Pan, and Anil Babu Ankisettipalli (2026), *On-Policy Distillation Meets Off-Policy GRPO: Training Compact Instruction-Following Rerankers* | [2609.01947v1](https://arxiv.org/abs/2609.01947v1) | Targeted full text: on-policy teacher distillation and off-policy GRPO recipe/evaluation. A possible one-variable compact-reranker training comparison; teacher superiority and routing transfer remain to be measured. |
| `thakur2025hardnegatives` | Nandan Thakur, Crystina Zhang, Xueguang Ma, and Jimmy Lin (2025), *Hard Negatives, Hard Lessons: Revisiting Training Data Quality for Robust Information Retrieval with LLMs* | [2505.16967v2](https://arxiv.org/abs/2505.16967v2) | Targeted full text: hard-negative false-positive diagnosis, LLM-based relabelling/filtering, and IR training comparisons. Keep semantically valid near-duplicates distinct from poisoned negatives; the checked title resolves the RLHN nickname. |
| `hu2021lora` | Edward J. Hu et al. (2021), *LoRA: Low-Rank Adaptation of Large Language Models* | [2106.09685v2](https://arxiv.org/abs/2106.09685v2) | Targeted full text: low-rank update parameterization, placement, and training/efficiency trade-offs. Adapter-method citation, not evidence that every new backbone linear module is PEFT-compatible; ICLR 2022 publication differs from the checked preprint year. |

### 2.4 Additional sources needed for the implementation/evaluation

| Bibliography key | Checked identity and year | Primary source | Reading depth / use |
|---|---|---|---|
| `palmer2026kev` | Jared Palmer, *Kev*; repository accessed in 2026 | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) | Primary repository README/interface and native decision-pointer attribution inspected; the originating revision remains to pin. Credit Jared Palmer, not Standhartinger. Access year is not a first-release date. |
| `patil2025bfcl` | Shishir G Patil, Huanzhi Mao, Fanjia Yan, Charlie Cheng-Jie Ji, Vishnu Suresh, Ion Stoica, and Joseph E. Gonzalez (2025), *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models* | [Official ICML/PMLR record](https://proceedings.mlr.press/v267/patil25a.html) | Official ICML/PMLR metadata/BibTeX and targeted full text: function-call/AST/execution scoring and multi-turn/agentic evaluation. ICML 2025, PMLR 267:48371–48392. Native schema, action, and state-grading conventions must survive local conversions. |
| `yang2025qwen3` | An Yang et al. (2025), *Qwen3 Technical Report* | [2505.09388v1](https://arxiv.org/abs/2505.09388v1), [0.6B-Base model card](https://huggingface.co/Qwen/Qwen3-0.6B-Base) | Targeted full text: dense/MoE architectures, training and evaluation settings; official 0.6B-Base identity checked. Nominal model family does not authenticate Soro adapters, head flags, dtype, or checkpoints. |
| `gemmateam2026gemma4` | Gemma Team (2026), *Gemma 4 Technical Report* | [2607.02770v2](https://arxiv.org/abs/2607.02770v2), [official model card/citation](https://gemma.ai/models/gemma-4/model-card/) | Targeted full text: effective/total parameters, multimodal encoders, and backbone design, plus official model card. E2B is 2.3B effective and 5.1B including embeddings; native audio/image capability is motivation, not a passed Soro fp32 port. |

### 2.5 Reading still to do

The additional papers in `docs/RESEARCH_GUIDE_V5.md` section 1 are a **follow-up queue**, not verified references silently added to this bibliography. CompRank, When2Tool, and the action-class diagnostic are now verified and targeted-read in Section 2.9; the other queued identities remain unread unless individually recorded here. Remaining priorities are full appendices and reproducibility assets, benchmark/audio permissions and native scoring, the originating Kev revision, and close block-reranking sources cited by CompRank. A literature search cannot establish a universal "first" claim.

### 2.6 V8 injection sources: targeted primary reading

| Bibliography key | Checked identity, first author(s), and year | Primary source and version | Reading depth / consequence |
|---|---|---|---|
| `shi2025toolhijacker` | Jiawen Shi et al. (2025), *Prompt Injection Attack to Tool Selection in LLM Agents* | [2504.19793v3](https://arxiv.org/abs/2504.19793v3) | Targeted full text: sections II-III and V. Shadow-system no-box retrieval/selection optimization; evaluated StruQ/SecAlign/detectors retain vulnerabilities in that setup. Fixed-menu adaptation tests selection only, not the retrieval attack or execution success. |
| `wang2025mcptox` | Zhiqiang Wang et al. (2025), *MCPTox: A Benchmark for Tool Poisoning Attack on Real-World MCP Servers* | [2508.14925v2](https://arxiv.org/abs/2508.14925v2) | Targeted full text: sections 3.1-3.4. 45 servers, 353 tools, 1,348 malicious cases. A poisoned tool can redirect use of a different legitimate tool without itself being called; parameter tampering is outside a label-only ASR. |
| `zong2025mcpsafety` | Xuanjun Zong et al. (2025), *MCP-SafetyBench: A Benchmark for Safety Evaluation of Large Language Models with Real-World MCP Servers* | [2512.15163v2](https://arxiv.org/abs/2512.15163v2) | Targeted full text: taxonomy, section 3.5, sections 4.2-4.3. Twenty attack types, server/host/user surfaces, separate task and attack evaluators. Cross-model safety/utility findings are empirical, not a universal trade-off theorem. |
| `liu2026mcptdp` | Shi Liu et al. (2026), *When the Manual Lies: A Realistic Benchmark to Evaluate MCP Poisoning Attacks for LLM Agents* | [2605.24069v1](https://arxiv.org/abs/2605.24069v1) | Targeted full text: sections II-V. Thirty-two cases, added-tool and compromised-existing-tool schemes, sandbox forensics. Reactive self-correction is qualitative post-execution recovery, not an established preventive comparator or undoing irreversible leakage. |
| `sneh2025tooltweak` | Jonathan Sneh et al. (2025), *ToolTweak: An Attack on Tool Selection in LLM-based Agents* | [2510.02554v1](https://arxiv.org/abs/2510.02554v1) | Targeted full text: sections 3 and 5. Feedback-driven names/description edits with schemas fixed. Functionally similar-tool preference is not necessarily incorrect routing; perplexity overlaps and paraphrasing does not confer immunity. |
| `mo2025ama` | Kanghua Mo et al. (2025), *Attractive Metadata Attack: Inducing LLM Agents to Invoke Malicious Tools* | [2508.02110v2](https://arxiv.org/abs/2508.02110v2), [official repository](https://github.com/SEAIC-M/AMA) | Targeted full text: sections 3.1-3.3. Plausible metadata/schema optimization need not contain explicit malicious instructions. Distinguish metadata persuasion from prompt injection and preserve the self-promotion residual. |
| `hu2026maltool` | Yuepeng Hu et al. (2026), *MalTool: Malicious Tool Attacks on LLM Agents* | [2602.12194v3](https://arxiv.org/abs/2602.12194v3) | Targeted full text: scope, section 2.2, threat discussion and section 5 overview. Malicious executable tool implementations, standalone/Trojan variants; not just metadata poisoning. Out of router-containment scope; do not execute this code for the scoring suite. |
| `cao2025vpibench` | Tri Cao et al. (2025), *VPI-Bench: Visual Prompt Injection Attacks for Computer-Use Agents* | [2506.02456v2](https://arxiv.org/abs/2506.02456v2) | Targeted full text: sections 3.1-3.3. 306 dynamic visual cases; attempted versus successful malicious execution. Rendered screenshot twins are an adaptation, not a multi-step CUA benchmark reproduction. |
| `zhu2025melon` | Kaijie Zhu et al. (2025), *MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents* | [2502.05174v4](https://arxiv.org/abs/2502.05174v4) | Targeted full text: sections 3.1-3.4 and failures. User/history-masked pass retains tool output and compares/cache-matches tool calls. Hoeffding ensemble result assumes bounded/appropriately independent similarities and benign/malicious mean separation; no arbitrary-attack detection guarantee. |
| `debenedetti2025camel` | Edoardo Debenedetti et al. (2025), *Defeating Prompt Injections by Design* | [2503.18813v2](https://arxiv.org/abs/2503.18813v2) | Targeted full text: sections 3-5 and scope. Trusted planner, quarantined parser, capability-based data-flow policies. Stronger/different system security object than a tool-label membership gate; acknowledged side-channel/scope limitations remain. |
| `chen2024struq` | Sizhe Chen et al. (2024), *StruQ: Defending Against Prompt Injection with Structured Queries* | [2402.06363v2](https://arxiv.org/abs/2402.06363v2) | Targeted full text: sections 4.1-4.4 and attack/ablation context. Secure reserved-token frontend plus structured instruction tuning on clean/attacked data, not a delimiter-only prompt defence. Prior trust-separation and negative-training mechanism. |
| `chen2024secalign` | Sizhe Chen et al. (2024), *SecAlign: Defending Against Prompt Injection with Preference Optimization* | [2410.05451v3](https://arxiv.org/abs/2410.05451v3) | Targeted full text: sections 2.1 and 3.1-3.3. Preference/DPO training distinguishes legitimate/injected outputs; white-box attack evaluation. Different training and threat object from a frozen non-generative pointer gate. |

### 2.7 V8 adaptive and adversarial coverage: targeted primary reading

| Bibliography key | Checked identity, first author(s), and year | Primary source and version | Reading depth / consequence |
|---|---|---|---|
| `gibbs2021aci` | Isaac Gibbs and Emmanuel Candès (2021), *Adaptive Conformal Inference Under Distribution Shift* | [2106.00170v3](https://arxiv.org/abs/2106.00170v3) | Targeted full text: sections 2 and 4.1. Constant-step feedback update, complete labels, full/empty conventions, bounded state and telescoping. Long-run empirical frequency for any sequence, not per-query marginal validity or fast rolling recovery. |
| `si2025ccpo` | Wenwen Si, Sooyong Jang, Insup Lee, and Osbert Bastani (2025), *Conformal Constrained Policy Optimization for Cost-Effective LLM Agents* | [2511.11828v2](https://arxiv.org/abs/2511.11828v2) | Targeted full text: sections 3-4, metrics and experiments. RL base/guide/next-round orchestration is prior adaptive deferral. Coverage counts desired-answer inclusion OR absence from all attainable sets, not unconditional answer correctness. Episode labels, policy-learning convergence, and adversarial threshold conditions must be distinguished. |
| `opoku2026toolchain` | Jeffery Opoku and David Banahene (2026), *ToolChain-CRC: Conformal Risk Control for Agentic AI Under Retrieval and Tool-Use Drift* | [2606.18467v1](https://arxiv.org/abs/2606.18467v1) | Targeted full text: sections 3-6. Controls joint expected failure-times-accept, not conditional accepted-trajectory error. Exchangeable trajectories/monotone losses; drift correction needs Lipschitz/Wasserstein discrepancy and concentration. Anytime alarm is a separate object. Explicit tool/retrieval-drift prior. |
| `liu2026pace` | Xinyu Liu and Jun Wu (2026), *Beyond Reactivity: Proactive Adaptive Conformal Inference for Online LLM Factuality* | [Official ICML / PMLR 306:79050-79072](https://proceedings.mlr.press/v306/liu26eu.html); full PDF/text saved in task scratch | Targeted full text: sections 4-5, including Theorem 4.2. Relative Mahalanobis embedding signal plus reactive sliding-window errors selects dynamic steps. The theorem controls step-weighted errors when cumulative weights diverge; tracking adds regularity. V8's NeurIPS attribution is incorrect. |
| `hu2026conformity` | Yibo Hu and Hanyu Su (2026), *Conformity Breaks Conformal Prediction* | [2609.04445v1](https://arxiv.org/abs/2609.04445v1) | Targeted full text: setup and sections 3-4. Malicious peer transcripts shift correct-label scoring after clean calibration; subgroup and singleton-action failures. This changes conformal premises, not a contradiction under satisfied exchangeability. Prompt-only weighting does not address the constructed shift. |
| `jeary2024vrcp` | Linus Jeary, Tom Kuipers, Mehran Hosseini, and Nicola Paoletti (2024), *Verifiably Robust Conformal Prediction* | [2405.18942v3](https://arxiv.org/abs/2405.18942v3) | Targeted full text: sections 4.1-4.3 and theorems. Verified score bounds at calibration/inference under supported norm-bounded perturbations. No certificate for arbitrary semantic/tool-metadata injection or modality change. |
| `liu2024pitfalls` | Ziquan Liu et al. (2024), *The Pitfalls and Promise of Conformal Inference Under Adversarial Attacks* | [2405.08886v1](https://arxiv.org/abs/2405.08886v1) | Targeted full text: sections 3-5. Norm-bounded image attacks, inflated/uninformative sets, uncertainty-reducing adversarial training. Report coverage with efficiency; do not assert that all conformal coverage survives attacks. |

### 2.8 Additional task-boundary priors and corrected gaps

| Bibliography key | Checked identity, first author(s), and year | Primary source and version | Reading depth / consequence |
|---|---|---|---|
| `debenedetti2024agentdojo` | Edoardo Debenedetti et al. (2024), *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents* | [2406.13352v3](https://arxiv.org/abs/2406.13352v3) | Targeted full text: sections 3 and 4.3. Trusted-task tool filtering already exists; within-permitted-tool/result manipulation still succeeds. Separate utility/security and adaptive attacks. Article licence is not dataset/code reuse permission. |
| `jia2024taskshield` | Feiran Jia, Tong Wu, Xin Qin, and Anna Squicciarini (2024 preprint), *The Task Shield: Enforcing Task Alignment to Defend Against Indirect Prompt Injection in LLM Agents* | [2412.16682v1](https://arxiv.org/abs/2412.16682v1) | Targeted full text: sections 3-4. Task-contribution checks for instructions/tool calls, feedback and retries. Counters "no tool-selection defence" claims. ACL 2025 publication exists; this bibliography consistently uses the checked preprint metadata. |
| `zhao2026clawguard` | Wei Zhao, Zhe Li, Peixin Zhang, and Jun Sun (2026), *ClawGuard: A Runtime Security Framework for Tool-Augmented LLM Agents Against Indirect Prompt Injection* | [2604.11790v2](https://arxiv.org/abs/2604.11790v2) | Targeted full text: sections II-III. User-confirmed task rules before external content, boundary authorization, sanitization, skill judge, ambiguity approval. Rule coverage and LLM-mediated components constrain enforcement; prior pre-content containment is real. |

The defensible V8 hypothesis is **a small, non-generative, structurally auditable decision boundary, evaluated with protected-reference sets and modality/catalog-shift feedback**, not "the first tool-selection defence," "the first adaptive deferral," "the first proactive conformal signal," or "unconditional injection safety." CCPO already addresses adaptive model routing; ToolChain-CRC already addresses tool drift; PACE already uses a pre-outcome signal. The new evaluation setting and architectural boundary must earn their contribution empirically.

The unnamed V8 claim that later re-evaluation found fine-tuning defence gains overstated remains **unresolved and uncited**. ToolHijacker's scoped defence evaluation is usable; it does not authorize a blanket statement. All-papers/full-appendix reading remains a pre-submission gate; targeted reads above are not claimed to cover every page.

### 2.9 Additional close priors and foundational risk/deferral sources

| Bibliography key | Checked identity, authors, and year | Primary source / revision | Targeted primary reading and consequence |
|---|---|---|---|
| `liu2026audioinjection` | Mingxiao Liu et al. (2026), *Piggybacking on Perception: Stealthy Concurrent Audio Prompt Injections against Multimodal LLM Agents* | [2607.28165v2](https://arxiv.org/abs/2607.28165v2), revised 31 July 2026 | Attack/threat model, CADV source separation/speaker consistency/semantic filtering, audio-agent evaluation, discussion/limitations. AudioAgentSecurity covers eight scenarios, ten concealment patterns, and eleven agents. Close prior for concurrent spoken injection and audio consistency defences; no set-containment theorem. Dense-background FPR and replay/cloning limits prevent treating source separation as authentication. |
| `angelopoulos2024crc` | Anastasios N. Angelopoulos, Stephen Bates, Adam Fisch, Lihua Lei, and Tal Schuster (ICLR 2024), *Conformal Risk Control* | [2208.02814v4](https://arxiv.org/abs/2208.02814v4), author revision 13 June 2025; [official record](https://openreview.net/forum?id=33XGfHLtZg) | Algorithm (4), Theorem 1, and nonmonotone counterexample in section 2.4. Exchangeable bounded non-increasing/right-continuous losses with an attainable safe boundary; calibrates `n/(n+1) * empirical risk + B/(n+1)`. Expected loss, not automatically high-probability conditional accepted-request risk. |
| `barber2023nexcp` | Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, and Ryan J. Tibshirani (2023), *Conformal prediction beyond exchangeability* | [2202.13415v5](https://arxiv.org/abs/2202.13415v5); *Annals of Statistics* 51(2):816–845, [DOI](https://doi.org/10.1214/23-AOS2276) | Weighted conformal construction, random swap for nonsymmetric fitting, and Theorem 2. Coverage lower bound subtracts weighted total variation between swapped residual vectors. Prompt embedding proximity alone is not a proof that this penalty is small. |
| `mozannar2020defer` | Hussein Mozannar and David Sontag (ICML 2020), *Consistent Estimators for Learning to Defer to an Expert* | [2006.01862v3](https://arxiv.org/abs/2006.01862v3); [PMLR 119:7076–7087](https://proceedings.mlr.press/v119/mozannar20b.html) | Sections 3–4: classifier/rejector cost, expert-error term, samples `(x,y,m)`, and consistent cost-sensitive surrogate. Requires true labels as well as expert decisions; the teacher/expert is not assumed infallible. Learned deferral differs from inference-only ACI. |
| `geifman2017selective` | Yonatan Geifman and Ran El-Yaniv (2017), *Selective Classification for Deep Neural Networks* | [1705.08500v2](https://arxiv.org/abs/1705.08500v2) | Risk/acceptance definitions, Algorithm 1 (SGR), Lemma 3.1/Theorem 3.2 and proof sketch, confidence-ranking discussion/evaluation. Labelled i.i.d. selective-risk thresholding with multiple-search correction; acceptance coverage is not prediction-set coverage. |
| `lu2026comprank` | Xuan Lu et al. (2026), *CompRank: Efficient LLM Reranking via Token-Level Compression and Decoding-Free Scoring* | [2606.11700v1](https://arxiv.org/abs/2606.11700v1) | Sections 3.1–3.4, experiment setup, and limitations: query-independent isolated document blocks/shared positions, later global query block, token compression, attention-mass scoring, CopyNet objective. Evaluated cache is not fully optimized/reused; single-run Mistral-7B results cannot be imported as Soro latency or cross-query catalog caching. |
| `zhao2026calibration` | Kangjia Zhao et al. (2026), *Calibration is the Bottleneck: An Action-Class Diagnostic of Multi-Turn Tool-Calling* | [2609.00949v2](https://arxiv.org/abs/2609.00949v2), revised 24 September 2026 | Sections 3.1–3.3, grading assumptions, and limitations. Any-turn Gold Action Recall versus state-graded conversation accuracy; `Acc <= GAR` needs a grader requiring the gold action. Calibration means action-class appropriateness, not ECE. Diagnostic SRI/CRI probes use gold/oracle gates, not deployment-known labels. |
| `sun2026when2tool` | Chung-En Sun, Linbo Liu, Ge Yan, Zimo Wang, and Tsui-Wei Weng (2026), *LLM Agents Already Know When to Call Tools -- Even Without Reasoning* | [2605.09252v4](https://arxiv.org/abs/2605.09252v4), revised 8 November 2026 | Benchmark, section 4 labels/probing, section 5 Probe&Prefill, evaluation/ablation discussion. Labels depend on the model's forced no-tool answer success; 900 probe training and 2,250 held-out examples. Necessity to use any tool is distinct from missing arguments/readiness on one chosen tool; an empirical probe is not a coverage guarantee. |

**Audio gap correction.** Spoken injection is not an empty prior-art space. CADV uses MossFormer2-style separation, CAM++ embeddings, and semantic filtering. The primary discussion reports false positives of 14% in DEMAND PCAFETER and 35% in OMEETING; sparse-environment results cannot be generalized to dense conversations. Its physical experiments cover selected devices/layouts, and its human study has 20 laboratory volunteers. Treat source authentication, user-voice replay, voice cloning, trusted transcript availability, and semantic containment as distinct questions. Audio2Tool's Tier 8 is an additional benign intent-attribution prior. No source attack audio or dataset redistribution rights were inferred from downloading papers.

**Deferral gap correction.** SGR, KnowNo, Learning to Defer, Conformal Cascade, and CCPO establish substantial prior deferral/routing mechanisms. The comparison must distinguish acceptance rate, conditional accepted risk, marginal label inclusion, expected bounded loss, joint accepted-error risk, and long-run inclusion frequency. Teacher answers and call-success flags are not automatically the true labels required by the latter guarantees.

### 2.10 Drex deep audit and source reconciliation

- **Architecture:** v2 primary text, native pointer/readout, hybrid backbones, and Appendix C. The final `<decide>` query follows all options; `</opt>` supplies keys, projection dimension 256, and LM head is unused. Attention-only option isolation/shared position IDs are explicitly described. Gated DeltaNet cannot support arbitrary option-block masks on the released hybrid rows. A global option-aware query defeats raw-score independence even if option states are isolated.
- **Training/calibration:** shuffled menus, permutation/state consistency, full-parameter v1.5 SFT, and RLAF proper-score optimization are genuine mechanisms. RLAF directly differentiates soft teacher/outcome scores, not a sampled-action deployment guarantee. The reported 1,150,460 records, contamination filters with acknowledged teacher/paraphrase leakage, and temperature tuning must be represented honestly. Deployed v1.5 ECE 4.54% versus tuned 1.17% is a held-out aggregate, not Soro coverage evidence or uniform per-domain calibration.
- **Evaluation unit/protocol:** calibration splits and bootstraps are request-level. The order appendix instead specifies decision bootstrap. Order audit filters 1,175 sampled requests to 1,040 supported common requests with 1,591 decisions (915 binary, 503 with K=3–5, 173 with K>=6). Original/reversed/one-random order differs from Soro's five sampled orders; v1.5 original-relative random flips 5.3% differ from any-of-three instability 9.2%. Public-index When2Call is 89.7% for v1.5, not the 84.8% quoted inside the local proxy notebook; neither is comparable with the context-incomplete response probe.
- **Limits/ablations:** Appendix I explicitly qualifies empirical robustness/calibration, low-precision/batch-shape variation, and image injection. Controlled Max objective/consistency/vision ablations exist; cross-backbone/head comparisons remain confounded for our isolation intervention. The paper does not offer unconditional security, but it does offer robustness/calibration mechanisms.
- **Unresolved denominator arithmetic:** primary Table 7 captions the K>=6 slice as 173 decisions, yet 14.1%, 17.8%, and 13.0% cannot each be an integer event count divided by 173 rounded to one decimal. A released 13.3% is compatible with 23/173. This might reflect averaging, another unstated denominator, or a typo; it is **not a confirmed erratum** and is not used to strengthen a superiority claim. The static checker records this reconciliation issue.
- **Reading scope:** architecture/training/calibration/order/ablations/limitations and relevant Appendices C, I, L were examined; not every page of the 52-page downloaded PDF was read. Primary files: `scratch/paper_survey_2026_11_16/drex_v2.pdf`, `drex_v2.txt`, and the official [v1.5 model card](https://huggingface.co/nace-ai/drex-v1.5), cached as `drex_model_card.md`.

## 3. Implementation and theorem audit

### 3.1 What the inspected routing path does

| Item | Code anchor | Paper consequence |
|---|---|---|
| Option rendering | `veyra/python/src/soro/routing/upp.py:464` | Stable key, independently clipped description (400 characters), newline. Disable positional option numbering with `option_index=False`; no index leakage is allowed by the theorem. |
| Request-first packing | `veyra/python/src/soro/routing/upp.py:529` | In the inspected request-first branch, **state/media come before the user question**, optional thinking slots, and `Options:\n`, then options. The final-prefix readout already sees state/media; it is not the proposed V8 immutable request-boundary readout. |
| Isolation mask | `veyra/python/src/soro/routing/upp.py:595` | Prefix sees only causal prefix; an option sees prefix and causal local option tokens. All isolated option spans share a starting position ID. The backbone must actually respect the mask. |
| Pool/readout | `veyra/python/src/soro/routing/upp.py:675` | The inspected configuration selects last-token option readout. Other pooling/readout/interaction configurations are not silently covered by the same implementation description. |
| Pointer member/refiner | `veyra/python/src/soro/routing/upp.py:139` | LayerNorm and linear query/key projections to 256 dimensions, then a joint query+option encoder: one layer, four heads, FFN 512, pre-norm, zero refiner dropout. Learned request/option types; all options share their type. |
| Refiner residual and score | `veyra/python/src/soro/routing/upp.py:172` | Refiner input is projected tokens plus type embeddings. Residual is `tanh(ref_gate) * LayerNorm(Encoder(tokens)-tokens)`. **Both** query and option vectors update. Dot scores divide by `sqrt(proj_dim)` and shared `exp(log_temp)+1e-4`. |
| Training length filtering | `veyra/python/src/soro/routing/upp.py:695` | Whole over-length rows are skipped; no suffix-truncation invariance claim. Record exclusions and retained data counts. |
| Training objective | `veyra/python/src/soro/routing/upp.py:759` | CE plus 0.25 times mean squared probability error in the inspected recipe. Optional cost/teacher terms must be reported per run. Isolated training skips the non-isolated second permutation-consistency forward. |
| Training recipe | `veyra/training/kaggle_s1_v3b.ipynb` | Requested 4,000 rows, 1,000 steps, batch 4, max length 832, seed 42; AdamW LR 2e-4, weight decay .01, warmup/cosine, clip 1; LoRA r16/alpha32/dropout .05 on Q/K/V/O. These settings are not authenticated completed-checkpoint history. |
| Existing targeted tests | `tests/test_upp.py` | Mock-backbone isolation/refiner tests are relevant structural checks. They were **not run in this drafting pass**, and would not alone establish a real-backbone dtype/kernel guarantee. |

### 3.2 Exact arithmetic is not unconditional selected-label invariance

The draft proves identity-aligned **score/probability equivariance**, with a fixed request, stable option identities/content/tokenization, identical local positions, the correct mask at every layer, deterministic inference, tokenwise other operations, and no order-dependent pruning/truncation or recurrent-state leakage. Refined request vectors are invariant to reordering but menu-dependent; refined option vectors are equivariant, not independent.

Selection follows only with a unique maximum or stable identity-based tie breaking. Current Python `max`/argmax uses insertion order at exact ties. Do not write an unconditional selected-option invariance theorem for that runtime.

Dense Gated DeltaNet/hybrid backbones cannot generally implement this attention-isolation premise; the loader rejects unsupported combinations. A successful load of an ordinary model does not by itself prove correct mask application at every layer. The proof also does not imply a request-independent tool cache or a sparse/linear-time kernel.

The reported spread is **maximum per-identity probability difference relative to the first evaluated order**, not a logit spread. The historical `eval_upp_full.py` audit samples five random orders, including the reference. For this tested family, a sufficient winner-stability condition is a reference top-two probability margin **greater than twice** the maximum reference-relative perturbation. There is no universal fp32 tolerance theorem, and head float casts or `amp:false` do not establish full-backbone fp32 execution.

### 3.3 Coverage and action semantics

- Use the standard finite-sample rank `ceil((n+1)*(1-alpha))`, with an **infinite threshold when the rank exceeds n**. `veyra/training/eval_conformal_action.py:55` clips the rank to n. That boundary is not generally valid for alpha below `1/(n+1)`; the manuscript states the correct theory and does not fix the helper in this task.
- `veyra/training/p0_upp_ablation.py:208` averages 50 repeated random within-split 50/50 calibration/test halves. This is exploratory resampling, not one locked deployment calibration. Its NumPy higher-quantile convention also needs to be aligned with the stated order statistic.
- Marginal coverage averages over calibration and test randomness, conditional on independently fitting/fixing the model. It is not automatically calibration-conditional coverage, class-conditional coverage, or coverage under arbitrary distribution shift.
- Variable menus are acceptable when the complete request/menu/gold records and score procedure meet exchangeability. Gold must be in the menu, and multiple-admissible-gold conventions must be explicit. Repeated query views need a justified common calibration/test unit or group-level protocol, not an assumption that a group-held-out split alone proves record-level exchangeability.
- An empty tool set does **not** certify tool irrelevance. A large set does **not** certify missing user information. A tool-only set does **not** certify ask/answer/abstain labels or argument security roles.
- A joint `(call,tool)`, `(ask,tool)`, answer, abstain label space is a proposed **standard classification construction**, not new conformal theory. It needs its own labels, scorer, and disjoint calibration.
- Singleton acceptance bounds the **joint wrong-and-accepted event** by alpha. Conditional accepted-request error is only bounded by `min(1, alpha / acceptance_probability)` from that statement, not by alpha itself. A teacher fallback has no inherited guarantee without its own assumptions/evidence.
- Cost-sensitive training or decision rules are objectives, not safety guarantees. Frozen-pointer readiness preserves ranking only when the actual freeze/integration is correct; the current job has no validated result.

### 3.4 Modality and stopping assumptions

The draft's paired-set inequality is the elementary event inclusion

`P(Y in C_speech) >= P(Y in C_text) - P(C_text is not a subset of C_speech)`.

It requires the same semantic gold and menu identities on paired target-distribution requests. Inclusion failures can be counted without labels, but the text coverage premise must hold on that **same** target distribution. Probability over calibration randomness must not be confused with a conditional-on-one-calibrator estimate. Very large speech sets make inclusion trivial, so efficiency must be reported. This is a coupling corollary, not a substantial new conformal theorem or protection from arbitrary speech shift.

Fixed-time conformal coverage does not automatically survive adaptive stopping across streaming prefixes. Park early commit unless there is simultaneous/time-uniform calibration and a repair/irreversible-stale-execution protocol. RASSG already has calibrated invalidity and cancellation components, so a purely heuristic baseline description would be misleading.

### 3.5 G1b: raw-score independence and the refiner trade-off

The new proposition is restricted to the inspected **single-member dot-product / last-token path**, with isolation, menu-independent preprocessing, shared fixed temperature, and the refiner **off**. Another option's text cannot affect the untouched option's raw score if prefix and own tokens/positions remain fixed. Adding/removing options is included only when it changes no truncation, pruning, normalization, or prefix state.

- Softmax probabilities **do** change with the denominator. Ensemble aggregation of member probabilities may also destroy independence of returned values named logits.
- A shared menu-independent sigmoid fit transform preserves raw independence but is **proposed**, not implemented or intrinsically calibrated.
- A poisoned option can still promote **itself** and win. G1b is not injection immunity.
- The refiner changes both query and option vectors, intentionally trading cross-option independence for collision discrimination while preserving set symmetry.
- Perturbation tests must log raw-score differences for untouched options, probability differences, winner changes, and attack outcomes separately.

### 3.6 G3: trust ordering and protected-reference containment

V8 proposes `[trusted prefix][user request][untrusted context][options]`, with the immutable request readout taken **before** untrusted content. The currently inspected pack does not implement that order. Causal language-model masking is insufficient if a joint audio/vision frontend, segmentation, reserved-token injection, or preprocessing mixes trust sources beforehand; refined query vectors are not immutable.

The protected reference `C0` uses authenticated stable registry identities and **trusted reference descriptions**. Removing state but leaving poisoned tool metadata in both passes is not a trusted reference. Catalog additions must be authorized/versioned separately from attacker-added options. Reference calibration must match the request-only score, target label/menu convention, and evaluation probability scope.

The gate accepts the augmented label only if it belongs to `C0`; otherwise it defers. This proves **membership containment only**. Wrong labels inside a multi-option `C0`, malicious self-promotion, full-menu references, and legitimate evidence-required false deferrals remain. A flag-only comparator does not enforce G3. MELON-inspired request-masked checks remain diagnostics requiring benign informative-content false-positive evaluation.

Reusing a request representation is not evidence that a second pass costs only option tokens. Prefix key/value support, frontend reuse, position/mask behaviour, refiner recomputation, and timings remain unimplemented/unmeasured. Injection-negative training that updates the pointer produces a separately hashed adapted checkpoint, not an unchanged locked pointer.

### 3.7 G2c: exact update target and feedback conditions

The proposed controller uses complete true-label replay first:

```text
a1 in [0,1], alpha in (0,1), gamma > 0, lambda >= 0, 0 <= dt <= 1
bt = at - lambda * dt
Ct(bt) = full valid menu for bt <= 0; empty for bt >= 1; nested set otherwise
et = 1{Yt not in Ct(bt)}
a(t+1) = at + gamma * (alpha - et)
```

With `Yt` present in every menu, full/empty saturation bounds the state by `[-gamma*(1-alpha), 1+lambda+gamma*alpha]`. Summation gives exactly `mean(et)-alpha = (a1-a(T+1))/(gamma*T)`, hence an ordinary-average long-run frequency bound. The fixed-step bounded widening is an elementary ACI-style extension, **not new general conformal theory**. PACE's variable-step result instead controls a step-weighted average. Clipping the state adds correction terms and cannot retain the quoted exact identity unchanged.

The theorem does not guarantee rolling-window recovery, singleton/accepted-request correctness, or efficient sets. Gold removal without a valid no-tool outcome breaks saturation. So does claiming it for `Ct intersect C0` when gold can lie outside `C0`; report adaptive **pre-gate** set coverage and **post-gate** containment/deferral separately.

Teacher answers are proxy labels; execution success is not label inclusion; feedback only on deferrals/accepted calls is selective. Full-label, delayed-label, all-round teacher, deferral-only teacher, and execution-proxy streams are separate ablations. Only complete correct inclusion feedback has the stated all-traffic pathwise guarantee. Audit labels unseen by a deployment controller can still measure its true all-traffic performance.

### 3.8 Multimodal uncertainty, proactive signals, and benchmark scope

The text/speech coupling uses the same semantic gold and menu, and a target-distribution text coverage premise. For i.i.d. independent paired evaluation units with fixed scorers/calibrators, Hoeffding can upper-bound the label-free inclusion penalty; this conditional estimate must not be combined with an unrelated calibration-marginal premise. Repeated speakers/query views require a justified group sampler.

Bounded symmetric set disagreement and inclusion failure are pre-outcome signal candidates, not attack detectors or novel proactive conformal theory. Clean transcript twins are privileged offline information; a deployable speech signal needs ASR or another actually observed paired view, with its cost/errors reported. Text renderings of screenshot evidence are not the same object as the protected **request-only** reference `C0`.

Speech, screenshot, speech-plus-screenshot, streaming, size, and benchmark tracks remain in the skeleton with unmeasured tables. No new audio, visual, injection, adaptive, distillation, or 8B performance result is generated by this writing pass.

## 4. Results and provenance register

### 4.1 Matched external rows: what was actually recounted

Inputs: `scratch/eval_pack/eval_external.jsonl`, `scratch/sorobee_baselines_downloaded/external_hammer_1.5b.jsonl`, and `scratch/sorobee_baselines_downloaded/external_xlam_1b.jsonl`. The summary files are `external_baselines_summary.json` and `external_baselines_summary.md` in that same baseline directory.

The evaluation file uses raw OmniRow records, not uniformly nested `questions.tool_route` records. Normalize with the semantics of `veyra/training/p0_upp_ablation.py`'s `to_kev_record`: retain rows with a gold label in their menu, using either the nested route or raw `label/options` fields. The initial nested-only counting attempt failed with `KeyError: 'questions'`; the corrected normalization retained all 1,200 rows.

The fresh recount found **1,200 unique evaluation IDs**, 1,065 tool rows, and 135 `__abstain__` rows. Both baseline files have zero duplicate IDs, unmatched IDs, label mismatches, and inconsistent `is_correct` flags.

| System | Evidence status | Overall correct/total | Tool correct/total | Abstain correct/total |
|---|---|---|---|---|
| Soro 0.6B iso+refiner | **Reported**, KT/results ledger; locked per-row/checkpoint provenance incomplete | 1032/1200 (86.00%) | 920/1065 (86.38%) | 112/135 (82.96%) |
| Soro 4B | **Reported**, ledger; external aggregate agrees with available 4B JSON | 1075/1200 (89.58%) | 956/1065 (89.77%) | 119/135 (88.15%) |
| Hammer-1.5B | **Recounted** from matched raw predictions | 991/1200 (82.58%) | 929/1065 (87.23%) | 62/135 (45.93%) |
| xLAM-1B | **Recounted** from matched raw predictions | 881/1200 (73.42%) | 803/1065 (75.40%) | 78/135 (57.78%) |

Hammer is stronger than reported Soro 0.6B on tool rows. Soro's overall lead is due to abstention, so do not claim superior tool choice in every stratum. Hammer/xLAM flips were **not measured**. Their recorded latency medians and Soro's approximate archived 180 ms do not establish a matched hardware/protocol speedup.

### 4.2 Repeated views change the inference unit

`DATA_LICENSES.md:30` states that the external 1,200 rows cover 115 base queries, and that `val_external_human.jsonl` is byte-identical to `val_external_heldout.jsonl`: there is no independent human split.

The inspected evaluation pack has **321 distinct request texts and 321 raw group IDs**, not 1,200 independent requests. Removing each row's documented `meta.format` plus `_vNN` view suffix from its ID yields **115 candidate parent IDs**: 50 parents have 11 views, and 65 have 10 views. This supports the documented base-query count but is still an inferred ID convention, not an authenticated source-level split manifest.

Use parent-query/semantic-source manifests and paired cluster resampling. Predeclare whether the estimand is view-weighted or parent-weighted. Archived row-level Wilson intervals and McNemar p-values are descriptive/provisional where repeated views violate independent-row inference; do not present them as final inferential evidence. Training-seed variability is a separate uncertainty source. For calibration, explain the exchangeable unit/view sampler or use a justified group-level score.

### 4.3 Isolation ladder and collision evidence

Source: `docs/RESULTS_LEDGER.md:39` (historical 0.6B ladder, seed 42).

| Variant | External correct | Legacy collision correct | Reported five-order flipped rows |
|---|---|---|---|
| Non-isolated v2 | 1006/1200 | 309/421 (73.40%) | 423/5207 (8.12%) |
| Isolated v3 | 1023/1200 | 289/421 (68.65%) | 0/5207 |
| Isolated+refiner v3b | 1032/1200 | 296/421 (70.31%) | 0/5207 |

- KT's 8.08% disagrees with 423/5207, which rounds to 8.12%. Preserve numerator/denominator, not the inconsistent percentage.
- The 84 historical near-miss rows have an invalid tool-choice gold/menu convention. Accuracy aggregate comparisons use **5,123**, while the stability audit can still use **5,207**. Do not mix the denominators.
- Refiner v3b gains **7/421**, or **1.66 percentage points**, over isolated v3. Archived paired discordants are 29 improvements versus 22 regressions (reported p about .401). This is one-seed descriptive evidence, not established significant recovery.
- Other archived aggregate deltas (including -0.61 points pooled, +2.17 points external, and -3.09 points collision versus v2) need per-row and parent-cluster authentication before inferential use.
- Reported maximum spread is **1.99e-5 in probabilities**. Full-backbone dtype/kernel provenance is not established by the report name alone.
- Expanded collisions contain 1,641 query-held-out but **semi-tool-disjoint** rows derived from external/zero-shot source families. Keep them separate; do not pool them as an independent new sample of those splits.

### 4.4 Checkpoint and run-name mismatches

Safe `torch.load(..., map_location='cpu', weights_only=True)` inspections found Qwen3-0.6B-Base configs with **`refiner=False` and missing `option_isolation`** (default false) in these available packs:

- `scratch/eval_pack/ckpt_A/head.pt`
- `scratch/keyush_eval_pack/ckpt_A.zip`
- `scratch/snorlax_ckpt_dataset/ckpt_A.zip`
- `scratch/shrekk3_bench_dataset/ckpt_A.zip`

These are not sufficient to reproduce or authenticate the reported locked isolated-refiner v3b run. A matching adapter base-model name or directory name is not proof. Recover the original weights/config/recipe/predictions and record cryptographic hashes. This is a **replication/provenance gap**, not a claim that every historical Soro result was false.

Two downloaded result trees must also not be silently substituted:

- `scratch/keyush_force_log/Soro-Boro/runs/v3b_eval/full_eval.json` identifies **Qwen/Qwen2.5-0.5B**, not canonical Qwen3-0.6B. Its 1259/1641 expanded and 284/421 legacy collision counts are a different run.
- `scratch/keyush_a4_output/Soro-Boro/runs/v3_eval/full_eval.json` belongs to an expanded-collision comparison, not the original locked ladder.

`scratch/sorobee_4b_downloaded/v3b_full_eval.json` agrees on 1075/1200 external and 334/421 collisions, but records **1199/1330 selection and 1965/2172 zero-shot**, versus ledger values 1200 and 1966. Its split flips sum to **23/5207** (9+7+2+5+0), not ledger 23/5007. Metadata `amp:false` is not a complete fp32 audit. Do not claim a full-precision zero-flip 4B result from this artifact.

### 4.5 Canonical input fidelity and earlier failed jobs

`scratch/when2call_canonical_3652.jsonl` has 3,652 rows with native labels `tool_call=1295`, `request_for_info=1062`, `cannot_answer=1295`, and zero direct-answer gold rows. Its field union is only `id`, `label`, `options`, `source`, `source_id`, `target_tool`, and `text`: it has no original system/context/tool-schema fields. `scratch/make_snorlax_nb.py` constructs user-request-only state and scores the four response strings. Restoring the row count and distractor is **not** sufficient to restore the canonical benchmark input or Drex comparability.

Publication training is APIGen-derived, not ToolBench. The local approximately 24k-dialogue training inventory needs its own conversion/source audit. Historical approximately 51-56% recast scores, or 46.7%/58.3% prior-corrected training diagnostics, must not be compared to the original-format 3,652-row benchmark as matched results.

| Root artifact | Observed earlier/current error | Permitted paper status |
|---|---|---|
| `soro-readiness-head.log:105` | Incompatible torchao 0.10; installed Transformers requires newer than 0.16 | This earlier run failed; a later unlinked aggregate does not authenticate locked-pointer readiness. |
| `soro-when2call-canonical-0-6b-eval.log:112` | Wrong UPP/model-construction arguments cause missing `interaction` on the Peft/Lora/Qwen object | No new canonical When2Call score; context defect remains separate from the API failure. |
| `soro-gemma-fp32-eval.log:97` | Current root log is the later PEFT rejection of `Gemma4ClippableLinear`, not the earlier OOM | No Gemma fp32 score; the OOM is preserved in the separate v4 archive. |

No routing/training code or these user-owned logs was changed in this task.

Later artifacts inspected on 16 November do provide diagnostic numbers, but do **not** close the canonical, native-Drex, full-precision, or locked-readiness gates. The chronology below supersedes any implication that no diagnostic output exists at all.

### 4.6 Speech data and quality

The 42,057 Kokoro clips and approximately 15 GB are **reported data-generation counts**, not speech model performance. `docs/SPEECH_QUALITY_AUDIT.md` reports 30.3% WER on 30 clips while calling it a pass for a below-15% criterion. Those statements conflict; do not repeat the pass claim or treat 15% as a universal speech-quality standard.

Pre-register domain-appropriate duration, clipping, truncation, pronunciation/tool-name corruption, manual intelligibility, and ASR diagnostics. Synthetic/real strata and source-group split leakage need independent audits. Existing project notes treat Audio2Tool as evaluation-only under CC BY-NC; its paper's CC BY licence is not the dataset's licence. The Spoken Function Calling paper licence likewise does not establish dataset redistribution permission. Confirm the actual dataset terms before recasting or releasing any audio artifact.

### 4.7 New quantized 4B S2 artifact: a distinct evaluation

Sources: `scratch/sorobee_4b_results/s2_baseline_and_gate.json`, the **6,050** entries in `s2_baseline_scored_rows.json`, and executed notebook `scratch/sorobee_4b_eval/soro-4b-s2-eval.ipynb`. The notebook passes **`--load-in-4bit`**. `veyra/training/eval_s2_baseline_and_gate.py:234` describes NF4 weights with float32 compute. The JSON key `baseline_raw_fp32` is inherited nomenclature, **not full-precision backbone authentication**. No code was modified to address this discrepancy.

| Split | Rows | Exact correct | Exact match | Flips | Maximum probability spread |
|---|---:|---:|---:|---:|---:|
| `s2_selection` | 572 | 498 | 87.06% | 1 | 0.0540624559 |
| `when2call_mcq` | 3,394 | 2,107 | 62.08% | 24 | 0.0743043423 |
| `agentabstain` | 301 | 117 | 38.87% | 11 | 0.0626870990 |
| `external_s2` | 1,200 | 938 | 78.17% | 4 | 0.0579328537 |
| `collisions_s2` | 421 | 276 | 65.56% | 16 | 0.0745428801 |
| `near_miss_s2` | 55 | 42 | 76.36% | 0 | 0.0361500829 |
| `escalate_probe` | 107 | 5 | Probe, not task accuracy | 0 | 0.0341491997 |

Flips sum to **56/6,050**. S2 adds ask/answer options, so this is not the historical tool-only 4B 89.58% evaluation and cannot replace it. On external S2, gold support remains tool=1,065 and abstain=135; correct counts are **854** and **84**. There are **218 ask predictions**, with **zero gold ask rows**: 218 of 262 exact-match errors are false asks. A permissive `ask_or_exact` rate conceals this failure and must not be called accuracy. The 5/107 escalation matches are a probe statistic with different semantics. Record actual packing, action candidates, quantization, per-order identity mapping, and checkpoint hashes before any final comparison.

### 4.8 Later response-only action score and deterministic context contradictions

Sources: `scratch/shrekk3_results/when2call_canonical_results.json`, executed notebook `scratch/shrekk3_bench_eval/soro-when2call-canonical-eval.ipynb`, exported `scratch/shrekk3_bench_dataset/when2call_canonical_3652.jsonl`, and restored original `scratch/original_when2call/test/when2call_test_mcq.jsonl`.

- Recount: **1,212/3,652 = 33.18729463%**, four-class macro F1 **0.1838653902**, weighted F1 **0.2477317880**. Export/scored ID and gold alignment has **zero mismatches**. The successful log does not show the older constructor/adapter failure, but does not authenticate the locked checkpoint.
- Protocol: uses `UPPModel.from_checkpoint` with `torch_dtype=float32` requested, followed by the pointer's `_batch`, `_hidden`, `_score` methods. Effective state is only `"User Request: " + r["text"]` with four response alternatives. This is a **context-incomplete, zero-shot response-card probe**, not canonical When2Call or a result comparable with published Drex.
- Gold/prediction confusion: call→(call 1063, ask 71, cannot 10, direct 151); ask→(call 727, ask 138, cannot 12, direct 185); cannot→(call 1050, ask 77, cannot 11, direct 157). Supports are 1,295, 1,062, and 1,295; direct has zero gold support. Macro F1 explicitly includes all four labels.
- All original records retain `question`, actually available `tools`, `target_tool`, answers, and UUID. **`orig_tools` exists only on the 1,295 cannot-answer records** and includes the withheld target: every such record has one more original than available tool. It is audit/construction metadata, **not model input**. The 1,062 ask records instead retain `orig_question` and `held_out_param`, also excluded from inference. The export drops the available `tools`; 3,394 original catalogs are nonempty and 258 are empty. Of 1,295 cannot-answer cases, 1,037 still have other available tools. The notebook ignores `target_tool` (non-null on 2,357 rows), but feeding that target alone or restoring pre-removal tools would corrupt rather than repair the canonical task.
- Effective `(text, options)` inputs have **3,483 distinct values**, **166 conflicting-input groups**, and **333 rows** in those groups. An input-only deterministic predictor can correctly label at most **3,486/3,652 = 95.45%** of this defective export. This is an information ceiling for the probe, not the official benchmark, and does not explain its entire performance deficit.

The canonical gate remains open: restore the modified `question`, actual available `tools`, native model-specific prompt/response formatting, and official scorer; keep `orig_tools`, `orig_question`, and held-out construction metadata hidden. Authenticate an action-trained model and report a new number under that protocol. The public manuscript keeps the canonical comparison table unmeasured and adds this diagnostic confusion matrix separately.

### 4.9 Drex local run is a non-native vocabulary proxy

Source output `scratch/snorlax_drex_results/drex_external_1200_results.json` reports **887/1,200 = 73.92%** and **398/1,200 = 33.17%** flipped rows. Orders are original, reversed, and three random permutations seeded by `42 + idx`. Executed notebook: `scratch/snorlax_drex_eval/soro-drex-v15-external-eval.ipynb`; generator: `scratch/make_drex_nb.py`.

The notebook loads **`AutoModelForCausalLM`**, NF4 weights and bfloat16 compute, feeds an ad hoc `State/Options/Answer` prompt, and scores **only the first token** of `tok.encode(" " + key)` in `outputs.logits[0,-1,:]`. It does not load/use the trained `head.pt`, native pointer, reserved packing, or supported TypeSafe/Kev decision scorer. The primary paper and official [model card](https://huggingface.co/nace-ai/drex-v1.5) explicitly say the LM head is not used for decisions. Shared first-token tool prefixes are a possible additional confound; their frequency was not tokenizer-audited.

**Quarantine both numbers as proxy-script diagnostics/protocol failure.** Do not report them as native Drex accuracy, attack success, or a native 33.17% flip headline. No native matched Drex baseline is available from these files; that row remains pending.

### 4.10 Readiness prototype and latest Gemma failure chronology

`scratch/readiness_results.json` reports accuracy **0.884**, precision **0.8909952607**, recall **0.9690721649**, F1 **0.9283950617**, and AUROC **0.9015814847**, on 1,000 nominally disjoint examples with 1,428 train/477 test tool keys. There are no per-row outputs or checkpoint/data hashes linking that aggregate to an authenticated run.

The available `scratch/run_readiness_colab_clean.py` recipe freezes the UPP backbone but separately encodes request/description with ordinary backbone calls (128-token limits), not the deployed request-conditioned pointer/refiner features. For ask rows it can select the first non-special candidate rather than the locked pointer winner or a verified intended tool. Key-disjoint sampling is not authenticated source/family separation. This recipe is not proven to be the source of the aggregate, and neither establishes locked rank retention or readiness on correctly aligned pairs. Keep the aggregate as an **unlinked prototype**, not a passed gate.

Gemma failures now have a later sequence: `scratch/gemma_fp32_err_v4/` records T4 OOM at 14.56 GiB, `scratch/gemma_fp32_err_v5/` records missing `adapter_config.json`, and **`scratch/gemma_fp32_err_v6/` records PEFT rejecting `Gemma4ClippableLinear`**. `scratch/gemma_v6_interim/` is empty. No new fp32 accuracy or order-flip output exists; neither architecture parity nor the speech prerequisite is achieved by these failed attempts.

The recomputations and result/notebook/input hashes for this update are saved in `scratch/paper_survey_2026_11_16/result_audit.json`. Archived results, logs, checkpoints, code, and user plans are preserved, not repaired.

## 5. Paper-completion gates and next experiments

| Priority | Research question / gate | Evidence needed before replacing a placeholder |
|---|---|---|
| 1 | Authenticate the main 0.6B checkpoint | Original isolation+refiner config and tensors, tokenizer, training revision, hashes, and identity-keyed per-row predictions matching the archived run. |
| 2 | Resolve evaluation units and provenance | Source-level parent manifest, admissible gold labels, source/tool/semantic overlap audit, exclusion reasons, and the predeclared view- versus parent-weighted estimand. |
| 3 | Is isolation's collision cost recoverable? | Matched non-isolated / isolated / isolated+refiner recipes with at least three predeclared seeds, stable-key sorting baseline, paired cluster-aware analysis, and identical training budgets. |
| 4 | Is runtime order stability consistent with the theorem? | Real-backbone mask tests; recorded backbone/head dtypes, attention kernels, padding, deterministic settings; identity-aligned per-order probabilities/margins. Keep exact arithmetic, sampled numerical spread, and tie behavior separate. |
| 5 | Can the frozen tool pointer support readiness? | Correct construction API, successful fit, explicit action labels, unchanged pointer ranking, per-class confusion matrices, and tool-retention results. |
| 6 | Can canonical When2Call be reproduced? | Modified benchmark question and actually available tools, native system/response formatting, official length-normalization/label rules, 3,652-row alignment, accuracy and macro F1. Keep original/held-out construction metadata hidden; no recast/Drex cross-protocol comparison. |
| 7 | Are prediction sets useful for deferral? | Locked independent fitting/calibration/test protocol, corrected finite-sample quantile boundary, coverage/set-size/empty/singleton strata, conditional selective risk, wrong-and-accepted rate, and measured fallback performance. |
| 8 | Does speech preserve useful decisions? | Quality/licence pass, authentic paired target data, text coverage premise, native/cascade/text comparison, set efficiency and inclusion-failure uncertainty on a consistent probability space. |
| 9 | Does the G1b/G3 boundary contain injected decisions usefully? | Fixed trusted reference metadata; trust-ordered pack/frontends; raw-score intervention tests; clean/attacked twins, within-reference attacks, ASR/accuracy/false-deferral/reference-level curves; matched isolation and containment ablations. |
| 10 | Can adaptive coverage recover efficiently under shift? | Approximately 5,000-decision labelled streams with valid menus, exact state/saturation logs, cumulative/rolling coverage and normalized size/deferral/recovery; static/weighted/ACI/proactive/PACE-style comparators. |
| 11 | Does the feedback claim survive deployment limits? | Separate complete true-label, delayed, teacher-proxy, deferral-only, and execution-proxy ablations; no all-traffic theorem attached to selective or incorrect labels. |
| 12 | Can screenshots and tri-modal minimal pairs be released? | Evidence-equivalent semantic/menu twins, informative versus irrelevant visual changes, VPI-Bench-style attacks, source permissions, native/generative references, modality-specific quality and trust labels. |
| 13 | Streaming, size, distillation, initialization, outcomes | A simultaneous/time-uniform stopping method and repair/stale-execution protocol; authenticated 0.6B/4B/Gemma/8B ports; separately calibrated distilled/adapted checkpoints and one-variable training comparisons. |

The five existing native figure inputs under `paper/soro_figures/` are preserved: mask/readout/refiner, proposed containment, adaptive loop, paired modalities, and **empty** performance-panel layouts. No fabricated curves are drawn. Planned final-result tables retain `TBD`; the new recounted S2/action diagnostic tables explicitly label their protocol limits and do not fill authenticated final-model placeholders. Nominal levels, data targets, and Gemma parity gates remain targets. Final tables need seed/cluster uncertainty, checkpoint IDs, action confusion/retention, and matched compute.

## 6. Draft integrity and reproducibility of this writing pass

The initial 36-reference evidence and V8 58-reference evidence remain unchanged in their earlier task caches. This update's contract, preservation baseline, primary PDFs/metadata, official venue snapshots, result audit, decision/recovery records, and fresh document checker live under `scratch/paper_survey_2026_11_16/`. Scratch is internal research evidence, not a licensed public release. Do not rerun either old whole checker unchanged against the 66-reference bibliography and revised run chronology.

The current task-scoped document checker covers:

1. Required V8 sections/tracks, balanced TeX braces/environments, unique labels/references, native figure inputs/TikZ node references, and explicit unmeasured tables/plot layouts.
2. Citation resolution and one primary-source register row per bibliography entry (66), including title/version/authorship agreement with saved metadata and explicitly verified publication-year exceptions. Reading depth is individually recorded, not inferred from cached page counts.
3. Archived external/provenance checks plus fresh S2 counts/flips/spreads, non-native Drex notebook scoring, response-only confusion/F1/input contradictions, readiness unlinkage, Gemma failure chronology, and source/result SHA-256 links.
4. Deterministic controller saturation/telescoping and counterexample fixtures: raw versus normalized scores, inside-reference attacks, missing gold, restrictive intersection, proxy/selective labels, clipping, and trivial full-menu modality inclusion. This is not formal proof checking.
5. Preservation hashes for all 855 baseline-protected files, including user plans/code/results/logs, the unrelated MGP manuscript, and all existing figures. This task edits only the Soro manuscript/bibliography, this register, and new task scratch; the user's pre-existing evaluator change remains untouched.

These are deterministic **document/provenance checks**, not a scientific replication, proof assistant, or real-backbone benchmark. The reported mathematical claims remain explicitly conditional on their stated assumptions. LaTeX compilation, focused `tests/test_upp.py` execution, and GPU experiments have **not** been performed in this writing pass. Request approval before compilation/runtime tests; any eventual MiKTeX build should use a separate task scratch output directory rather than the existing MGP manuscript's outputs.

## 7. Verified upcoming conferences and submission choice

**Official-call snapshot: 16 November 2026.** Rank by scientific fit and readiness, not prestige alone. These are mutually exclusive destinations for substantially the same work, not a parallel-submission schedule. Recheck every call/portal before acting.

| Rank / venue | Confirmed 2027 deadline | Timezone / page budget | Fit for this paper and minimum readiness |
|---|---|---|---|
| **1. ICML 2027** | Abstract **14 January**; paper **22 January**; portal opens 8 January | 23:59 AoE; 8 main pages, references/impact/appendices separately allowed | Best broad guarantee/small-model story after authenticated controlled isolation comparison, useful coverage/containment trade-offs, and one substantive multimodal result. Do not sell elementary implications alone as a Theory contribution. |
| **2. ACL 2027 via ARR** | ARR submission **4 January**; ACL commitment **TBA** | 23:59 AoE; long 8 content pages, short 4, separately treated required limitations/references | Strong NLP tool/readiness, efficient models, agents, and multimodal-language fit. Requires review plus meta-review then commitment, not a direct 4 January conference submission. Prefer only if canonical action/protocol evidence is ready earlier. |
| **3. IJCAI 2027** | Abstract **4 January**; full paper and appendix **11 January** | 23:59 AoE; 7 body + up to 2 reference pages | Broad decision/agent reliability fit. Lead with a coherent tested mechanism and quality/safety trade-offs, not a large collection of unfinished tracks. Meaningful abstract is mandatory. |
| **4. SIGIR 2027** | Abstract **14 January**; full paper **21 January** | 23:59 AoE; 9 pages for all non-reference content, references unrestricted | Agentic IR is now a standalone area and safety/robustness is explicit. Very suitable if retrieval/access drives the contribution: changing tool catalogs, retrieval versus selection, near-duplicate ranking, and realistic poisoned metadata. Generic routing with token IR benchmarks is not enough. Abstract is mandatory. |
| **5. Interspeech 2027** | Submission **9 February**; update **16 February**; portal opens 19 January | Timezone not specified in inspected call; regular 4 + 2 reference/ack pages, long 8 + 2 | Focused speech version after native-audio/cascade parity, useful paired coverage, speech source-attribution controls, and real/noisy speech results. A text router with only synthetic audio data is not yet that contribution. |

**India deadline conversions for confirmed AoE dates:** 4 January 23:59 AoE → **5 January 17:29 IST**; 11 January → **12 January 17:29 IST**; 14 January → **15 January 17:29 IST**; 21 January → **22 January 17:29 IST**; 22 January → **23 January 17:29 IST**. Do not apply these to Interspeech until its portal states the timezone. Aim to upload earlier rather than using conversion precision as schedule slack.

Official sources:
- [ICML dates](https://icml.cc/Conferences/2027/Dates), [call](https://icml.cc/Conferences/2027/CallForPapers), and [contribution types](https://icml.cc/Conferences/2027/ContributionTypes).
- [ACL main call](https://2027.aclweb.org/calls/main/) and [ARR call/policies](https://aclrollingreview.org/cfp).
- [IJCAI main call](https://2027.ijcai.org/ijcai-2027-call-for-papers-main-track/) and [submission process](https://2027.ijcai.org/ijcai-2027-submission-process/).
- [SIGIR full-paper call](https://sigir2027.org/pages/submit-full.html).
- [Interspeech call](https://interspeech2027.org/calls/call_for_papers/).

### 7.1 Closed and unannounced alternatives

| Venue | Actual checked status | Consequence |
|---|---|---|
| AISTATS 2027 | Main abstract 29 September 2026; full paper 6 October 2026, already passed | Not an upcoming main-track submission option. |
| AAMAS 2027 | Main paper 8 October 2026, already passed | Agent fit does not create an open deadline. Other tracks need their own verified calls. |
| UAI 2027 | Official AUAI site did not supply an announced 2027 CFP/deadline in this check | Watch list for a tighter uncertainty paper; no guessed February date. |
| NeurIPS 2027 | Official 2027 paper call/deadline not announced in this check | Later broad-ML possibility; no invented spring deadline. |
| KDD 2027 | First cycle closed: abstract 19 July/paper 26 July 2026; second cycle refers to February 2027 but exact dates are not announced in the checked call | Possible later catalog/retrieval/benchmark version, not a dated backup. |
| CCS 2027 | Official important dates are **TBD** | Consider only a security-focused version with complete threat model, adaptive attacks, and action/security outcomes. A May artifact reference is not a submission deadline. |

Cached official HTML/text and hashes are in `scratch/paper_survey_2026_11_16/venue_source_index.json` and `venue_*.html`/`venue_*.txt`. Workshop-proposal calls are not workshop-paper deadlines. No deadline aggregator overrides an official CFP.

### 7.2 Formatting, policies, and human verification

- **ICML:** all submissions require an AI Disclosure Statement; substantive ideation/reasoning, experimental design, data analysis, literature synthesis, and drafting need disclosure. It is outside the main-page limit. Authors retain responsibility; contribution types and reviewer quotas must be checked before registration.
- **ACL/ARR:** reviews precede commitment; dual submission is prohibited. Preprints are generally allowed, but any binding choice not to release a non-anonymous preprint must be respected. Complete required limitations/responsible-research information, reviewer eligibility, and profiles.
- **IJCAI:** register authors/ORCID and reciprocal reviewer requirements early. The submission-process page distinguishes a primary-paper fee waiver from a $100 non-primary fee; do not assume every submission is free.
- **SIGIR:** use the anonymous ACM `sigconf` format and required CCS concepts/keywords; all non-reference appendix/proof material counts in the nine-page limit. Author list locks at abstract submission and OpenReview profile activation can take time. Check ACM AI/authorship/open-access and attendance requirements.
- **Interspeech:** the CFP explicitly rejects papers entirely developed or written by AI and fictitious references. Human authors must substantively verify/revise this skeleton and all citations. Same work cannot enter both long and regular tracks; presentation is in person.

**Practical compression:** the neutral skeleton is far longer than any main-text budget. Keep one coherent core: structural order/readout boundary + controlled accuracy/attack comparison, then one completed coverage/containment/modality extension. Move proofs, protocol diagnostics, failed jobs, large-size/streaming plans, and expanded benchmark documentation to permitted supplementary/release material. Remove the internal venue-planning appendix before anonymous submission. Choose the destination only after the gate evidence, not while pretending every V8 track is already complete.

## 8. Draft AI-use disclosure and remaining reading obligation

Generative AI assists this literature survey, source/result-protocol interpretation, and manuscript scaffold. No model experiment or production-code edit was performed in this task. Human authors have **not** yet been certified as independently verifying every claim. Before submission, they must validate the source-reading notes, proofs, novelty boundaries, data licences, actual model checkpoints, benchmark protocols, and final prose, and supply the chosen venue's truthful disclosure. Disclosure does not replace authorship or scientific verification.

The 66-entry bibliography is now backed by individually documented primary interface/method/theorem/protocol reading, not only search summaries. **This does not mean all papers were read cover to cover.** Full appendices, latest reproducibility assets, dataset permissions, the remaining V5 follow-up queue, and author review stay explicitly open rather than being converted into fictitious completed research.
