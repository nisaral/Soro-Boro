# Safe Recovery Under Risk Budget (SRRB) & Risk-Recovery Frontier Protocol

**Document Version:** 1.0 (Frozen)  
**Date:** October 8, 2026

---

## 1. The Core Limitation of Single-Point Comparisons

Comparing systems at arbitrary single operating points is methodologically flawed:
- An aggressive system achieving 95% recovery with 4% duplicate side-effects is not strictly "better" or "worse" than a cautious system achieving 80% recovery with 0% duplicates.
- They occupy different coordinates on a Pareto trade-off curve.

To evaluate algorithmic superiority fairly, we define the **Safe Recovery Under Risk Budget (SRRB)** metric.

---

## 2. Formal Mathematical Definition

Let $\mathcal{A}$ be the action space, $\mathcal{O}$ be the observation space, and $\pi: \mathcal{O} \to \mathcal{A}$ be a recovery policy.

For a distribution of execution faults $\mathcal{D}$, let:
- $\text{SRR}(\pi) = \mathbb{E}_{\mathcal{D}} [\mathbb{I}(\text{action safely completes the task})]$
- $\text{DER}(\pi) = \mathbb{E}_{\mathcal{D}} [\mathbb{I}(\text{action causes duplicate side-effects})]$

### Definition: Safe Recovery Under Risk Budget
For an enterprise risk tolerance $\epsilon \ge 0$:
$$\text{SRRB}(\epsilon) = \max_{\pi \in \Pi} \text{SRR}(\pi) \quad \text{subject to} \quad \text{DER}(\pi) \le \epsilon$$

### The Feasible Frontier
The curve $\mathcal{F}(\epsilon) = \text{SRRB}(\epsilon)$ across $\epsilon \in [0.00, 0.05]$ defines the **feasible safety/recovery frontier**.

---

## 3. Standard Evaluation Budgets

To compare policies objectively, we evaluate all systems at standard enterprise risk budgets:

| Risk Budget ($\epsilon$) | Enterprise Consequence Level | Example Production Scenario |
| :---: | :--- | :--- |
| **$\text{DER} = 0.0\%$** | **Critical / Zero-Tolerance** | Financial debits, irreversible cloud infrastructure teardown |
| **$\text{DER} \le 0.1\%$** | High-Value / Strict | High-frequency database updates, automated inventory reservation |
| **$\text{DER} \le 0.5\%$** | Controlled Production | Automated ticket generation, transactional email dispatches |
| **$\text{DER} \le 1.0\%$** | Moderate Risk | Idempotent document caching, batch log writes |
| **$\text{DER} \le 2.0\%$** | Low Consequence | Non-critical metric scraping, internal notification pings |
| **$\text{DER} \le 5.0\%$** | Permissive / Experimental | Read-only retries, speculative web queries |

---

## 4. Finite-Sample Bound Protocol (Rule of Three)

Whenever a policy achieves zero observed duplicates across $N$ independent runs:
1. It MUST NOT be called "zero risk".
2. The empirical point estimate is reported as $\widehat{\text{DER}} = 0.0\%$.
3. The one-sided 95% upper confidence bound MUST be calculated as:
   $$\text{DER}_{95\% \text{ UCB}} = 1 - (0.05)^{1/N} \approx \frac{2.9957}{N}$$
   For $N = 500$:
   $$\text{DER}_{95\% \text{ UCB}} = \frac{2.9957}{500} = 0.599\% \approx 0.60\%$$
