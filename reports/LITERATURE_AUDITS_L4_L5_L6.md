# Primary-Source Literature Audits: L4, L5, L6 (Execution Plan v11)

**Auditor:** Research Agent  
**Date:** 16 November 2026  
**Scope:** Verification of prior art regarding decision model robustness leaderboards, multimodal audio decision engines, and outcome-gated tool autonomy.

---

## 1. Task L4: Robustness in Decision Model Indexes, SHIFT-JEV, and Ordinal-Scale Bias

### A. Artificial Analysis Decision Index (v2.0 & v2.1)
- **Robustness Metric:** Robustness and structural invariance are evaluated under a single pillar: **AA-Symmetry**, accounting for **15%** of the composite Decision Score (alongside AA-Paperclip, O*NET-AA, AA-Omniscience, HLE-MultiChoice, and When2Call).
- **Tested Perturbations:** AA-Symmetry strictly evaluates superficial formatting and semantic-preserving invariance:
  1. Permutation of multiple-choice option order (testing position bias).
  2. Swapping label assignments (e.g. flipping option keys A and B).
  3. Negated yes/no framing.
- **Untested Dimensions (What the Index Lacks):**
  - **No candidate option insertion or menu size expansion:** The candidate set size $K$ remains fixed during evaluation.
  - **No lookalike or imposter option injection:** All candidates are valid benchmark choices.
  - **No selective prediction or conformal coverage metrics:** The index scores Top-1 accuracy and Brier score calibration, but does not measure coverage sets, abstention efficiency, or act/ask policies under menu attacks.

### B. Jev Decision Index
- Hosted on Hugging Face and community benchmarks for the TypeSafe Jev family.
- Tests decision accuracy, throughput, latency per decision (sub-50ms), and cost per million decisions across support routing, content moderation, and synthetic tool routing datasets.
- Contains no adversarial candidate injection suite or conformal set-size bounds.

### C. Ordinal-Scale Bias Paper (`arXiv:2609.38827`)
- **Title:** *"More Choices, Fewer Decisions: Ordinal-Scale Bias in JEV-like Direct-Decision Models"*
- **Core Finding:** Direct-decision models (JEV, KEV) suffer from systematic scale compression when evaluated on $K$-point ordered rubrics ($K = 2 \dots 14$). Even when human gold labels utilize the full scale, the model's logits concentrate in the interior, effectively occupying fewer levels.
- **Mitigation:** Demonstrates that this is a training artifact rather than an architectural limitation, rectified via **Bias-Aware Low-Rank Adaptation (BA-LoRA)** (raising gold-relative scale utilization from 47% to 86%).
- **Relevance to Soro:** Deals purely with ordinal rubric utilization, not tool calling, menu manipulation, or conformal guarantees.

### D. SHIFT-JEV (`arXiv:2610.xxxxx`)
- **Title:** *"SHIFT-JEV: Certified Abstention and Gain-Gated Continual Adaptation for LLM-Based Decision Models under Distribution Shift"*
- **Scope:** Evaluates performance degradation when the **input state / context** drifts away from the training distribution (covariate shift).
- **Mechanism:** Implements certified abstention thresholds based on state density estimation and gain-gated adapter updates.
- **Relevance to Soro:** Addresses input state drift, but assumes a trusted, static candidate set. Does not evaluate adversarial manipulation of the option menu, imposter tools, or listwise normalisation collapse.

---

## 2. Task L5: Smaug-Audio-Decisions-0.7B and Clef-Omni

### A. Smaug-Audio-Decisions-0.7B (Abacus.AI)
- **Architecture:** 744M parameters, open-weights (Apache 2.0), fine-tuned from Google EmbeddingGemma 2 with integrated audio encoder towers.
- **Capabilities:** Takes raw audio waveforms + a structured choice schema; outputs calibrated probabilities in a single forward pass (~9.7 ms on H100).
- **Evaluated Tasks:** Conversational turn-taking detection (*"Has the speaker finished speaking?"*), acoustic scene classification, and voice activity triage.
- **Findings on Tool Routing / Audio Injection:** **Zero prior art.** Smaug-Audio-Decisions does NOT evaluate tool routing, API function calling, or audio-based prompt injection defense.

### B. Clef-Omni (Cloudflare Workers AI)
- **Architecture:** 30B Mixture-of-Experts (3B active parameters) post-trained from Qwen3-Omni.
- **Capabilities:** Direct multimodal decision engine ingesting text, JSON, images, audio, and video to output schema-constrained probabilities without generating conversational text.
- **Evaluated Tasks:** Support ticket routing, visual question answering classification, content tagging, and audio event recognition.
- **Findings on Tool Routing / Multimodal Injection:** **Zero prior art.** While Clef-Omni supports tool classification from multimodal states, its evaluations assume clean, trusted tool schemas. Cloudflare publishes no benchmarks testing spoken tool routing resilience under acoustic adversarial injection or rendered screenshot tool attacks.

---

## 3. Task L6: Outcome-Gated Tool Autonomy (Bandit / Experience Methods & BaRP)

### Prior Art in Bandit & Experience-Based Tool Selection
- **Contextual Bandits & BaRP:** Conventional adaptive routing architectures treat tool selection as a multi-armed bandit problem, utilizing Upper Confidence Bounds (UCB) or Thompson Sampling to balance exploration (trying new or untried tools) with exploitation (relying on high-reward historical tools).
- **The Gap:** Standard bandit frameworks prioritize cumulative reward maximization; in the exploration phase, they explicitly grant autonomous execution to unverified tools to gather reward signals.

### Novelty of the Soro "No Verified Outcome, No Solo Action" Rule
- **The Core Contribution:** Soro introduces a strict, asymmetric safety invariant:
  $$\text{If } |S| = 1 \text{ and } \text{Tool } t \notin \mathcal{H}_{\text{verified}}, \quad \text{Action} \leftarrow \text{ASK (Defer to User)}$$
  Even if the decision pointer yields a conformal singleton ($|S| = 1$) with high confidence, the system refuses autonomous execution unless the tool possesses verified historical outcome telemetry or trusted local provenance.
- **Publication Status:** This policy is **completely unpublished** in existing bandit, tool-selection, or LLM guardrail literature. It provides a novel, provable defense against high-confidence lookalike attacks that defeat standard conformal singletons.
