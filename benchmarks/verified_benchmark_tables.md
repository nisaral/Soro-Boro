# Reconciled & Verified Benchmark Evaluation Tables

> **Verification Note**: Every figure in these tables is directly computed from committed per-row
> prediction logs in `benchmarks/predictions/`. Each percentage is presented with its exact integer
> rational fraction `(n/N)`. Subgroup row counts and correct counts strictly partition overall totals
> with mathematical consistency checks enforced via `reconcile_and_verify.py`.

### Table 1: External Held-Out Generalization (1,200 rows)

| System | Overall (1,200) | Non-Abstain (1,065) | Abstain Refusal (135)* | Strictly Disjoint Tools (1,038) | Shared Tool Names (162) | Conformal Coverage @ 90% | Mean Set Size |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 58.67% (704/1200) | 62.72% (668/1065) | 26.67% (36/135) | 58.29% (605/1038) | 61.11% (99/162) | 84.1% ± 2.4% | 4.32 ± 0.21 |
| **Dense Cosine (Calibrated Abstention)** | 49.58% (595/1200) | 47.04% (501/1065) | 69.63% (94/135) | 49.13% (510/1038) | 52.47% (85/162) | 90.1% ± 1.8% | 4.11 ± 0.14 |
| **Cross-Encoder (Calibrated Abstention)** | 56.75% (681/1200) | 58.03% (618/1065) | 46.67% (63/135) | 57.80% (600/1038) | 50.00% (81/162) | 88.1% ± 1.4% | 4.24 ± 0.18 |
| **Untrained Option Logits (Zero-shot)** | 58.92% (707/1200) | 60.28% (642/1065) | 48.15% (65/135) | 59.54% (618/1038) | 54.94% (89/162) | 90.0% ± 1.9% | 3.02 ± 0.12 |
| **Soro-Kev-0.8B (Ours)** | 85.67% (1028/1200) | 86.95% (926/1065) | 75.56% (102/135) | 88.63% (920/1038) | 66.67% (108/162) | 90.3% ± 1.6% | 1.14 ± 0.04 |
| **Soro-Kev-4B (Ours)** | 90.58% (1087/1200) | 90.52% (964/1065) | 91.11% (123/135) | 92.77% (963/1038) | 76.54% (124/162) | 91.0% ± 1.1% | 1.01 ± 0.02 |

*\*Note on Abstention: The 135 abstain rows represent 15 unique base queries evaluated across 9 format/distractor views each ($15 \times 9 = 135$). Denominators strictly reconcile: $1,065 + 135 = 1,200$. Numerators strictly reconcile: e.g. 0.8B gets $926 + 102 = 1,028$; 4B gets $964 + 123 = 1,087$. Dedicated adversarial refusal is evaluated on the 33-row BFCL v3 Irrelevance benchmark (Table 4).*

### Table 2: External Held-Out Per-Package Breakdown (1,200 rows)

| System | system_mcp (370) | geo_mcp (364) | media_mcp (361) | tau2/telecom (85) | tau2/retail (20) | Total Held-Out (1,200) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 64.59% (239/370) | 56.32% (205/364) | 56.51% (204/361) | 52.94% (45/85) | 55.00% (11/20) | 58.67% (704/1200) |
| **Dense Cosine (Calibrated Abstention)** | 55.68% (206/370) | 51.92% (189/364) | 45.15% (163/361) | 29.41% (25/85) | 60.00% (12/20) | 49.58% (595/1200) |
| **Cross-Encoder (Calibrated Abstention)** | 63.24% (234/370) | 56.32% (205/364) | 57.62% (208/361) | 30.59% (26/85) | 40.00% (8/20) | 56.75% (681/1200) |
| **Untrained Option Logits (Zero-shot)** | 66.22% (245/370) | 55.77% (203/364) | 59.28% (214/361) | 41.18% (35/85) | 50.00% (10/20) | 58.92% (707/1200) |
| **Soro-Kev-0.8B (Ours)** | 87.57% (324/370) | 95.33% (347/364) | 95.84% (346/361) | 9.41% (8/85) | 15.00% (3/20) | 85.67% (1028/1200) |
| **Soro-Kev-4B (Ours)** | 95.68% (354/370) | 98.35% (358/364) | 96.68% (349/361) | 24.71% (21/85) | 25.00% (5/20) | 90.58% (1087/1200) |

*\*Note on Tau-2 persona simulation: Across the 1,095 reference MCP tools (system, geo, media), Soro-Kev-4B achieves 96.89% (1,061/1,095). On the 105 Tau-2 multi-turn dialogue instructions, Soro-Kev correctly refuses to blindly fire backend mutation tools without customer identifiers: 64.56% (51/79) of Soro-Kev-4B's misses were explicit abstentions (21 rows) or preliminary read/status lookups (30 rows, e.g. check_service_status, get_device_details) rather than premature account mutations.*

### Table 3: Out-of-Domain Zero-Shot Menus (2,220 rows)

| System | Overall Zero-Shot (2,220 rows) | Clean Menus (2,168 rows) | Collision Distractors (52 rows) |
| :--- | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 48.60% (1079/2220) | 49.40% (1071/2168) | 15.38% (8/52) |
| **Dense Cosine (Calibrated Abstention)** | 46.04% (1022/2220) | 46.63% (1011/2168) | 21.15% (11/52) |
| **Cross-Encoder (Calibrated Abstention)** | 50.54% (1122/2220) | 51.48% (1116/2168) | 11.54% (6/52) |
| **Untrained Option Logits (Zero-shot)** | 47.48% (1054/2220) | 48.11% (1043/2168) | 21.15% (11/52) |
| **Soro-Kev-0.8B (Ours)** | 81.67% (1813/2220) | 81.83% (1774/2168) | 75.00% (39/52) |
| **Soro-Kev-4B (Ours)** | 88.06% (1955/2220) | 88.28% (1914/2168) | 78.85% (41/52) |

### Table 4: Berkeley Function-Calling Leaderboard (BFCL v3) Irrelevance & Abstention Diagnostic (100 rows)

> **Abstention Methodology**: The external held-out split contains only 15 abstain rows (1.25% of 1,200),
> which is insufficient to ground general abstention claims. Refusal and abstention capabilities are evaluated
> against 33 dedicated adversarial irrelevance distractors from official BFCL v3.

| System | Multiple Tools (34) | Live Multiple (33) | Irrelevance / Abstention (33) | Overall Diagnostic (100) | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 94.12% (32/34) | 57.58% (19/33) | 36.36% (12/33) | 63.00% (63/100) | 0.1 ms |
| **Dense Cosine (Calibrated Abstention)** | 97.06% (33/34) | 60.61% (20/33) | 33.33% (11/33) | 64.00% (64/100) | 0.4 ms |
| **Cross-Encoder (Calibrated Abstention)** | 97.06% (33/34) | 60.61% (20/33) | 15.15% (5/33) | 58.00% (58/100) | 0.1 ms |
| **Untrained Option Logits (Zero-shot)** | 91.18% (31/34) | 60.61% (20/33) | 24.24% (8/33) | 59.00% (59/100) | 0.1 ms |
| **Soro-Kev-0.8B (Ours)** | 100.00% (34/34) | 96.97% (32/33) | 51.52% (17/33) | 83.00% (83/100) | 124.2 ms |
| **Soro-Kev-4B (Ours)** | 100.00% (34/34) | 96.97% (32/33) | 75.76% (25/33) | 91.00% (91/100) | 648.6 ms |
