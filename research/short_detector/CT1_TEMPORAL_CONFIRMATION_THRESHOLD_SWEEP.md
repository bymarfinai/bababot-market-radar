# SHORT-CT1 — Temporal Confirmation Threshold Sweep

Status: **PASS — primary threshold candidate = +0.075%**

## Objective

Test whether the frozen SHORT Lane-1 temporal confirmation threshold:

> **+0.0338983050847%**

is too permissive and contributes materially to SHORT false positives.

CT-1 changes only the Lane-1 temporal confirmation threshold used by the causal T+1/T+2/T+3 recovery path.

Frozen during this test:
- S10D fast T0 override
- S10C Lane-0 recovery
- S10D alternate T+3 rescue
- router
- all other detector rules
- Profit Protector is **not evaluated in CT-1**
- no runtime changes

Threshold grid:

> 0.0339%, 0.05%, 0.075%, 0.10%, 0.125%, 0.15%, 0.158514%, 0.20%

Datasets:
- Research resolved SHORT universe: **655**, strong = **99**
- Fresh resolved S10H universe: **1,449**, strong = **261**

Baseline S10D at 0.033898%:
- Research: 364 selected / 85 strong / 279 non-target
- Fresh: 807 selected / 189 strong / 618 non-target

---

# Sweep result

| Threshold | Research selected | Research strong | Research precision | Research NT removed | Fresh selected | Fresh strong | Fresh precision | Fresh NT removed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **0.0339%** | 364 | 85 | 23.35% | — | 807 | 189 | 23.42% | — |
| **0.05%** | 350 | 84 | 24.00% | 13 | 787 | 188 | 23.89% | 19 |
| **0.075%** | **333** | **83** | **24.92%** | **29** | **754** | **183** | **24.27%** | **47** |
| 0.10% | 309 | 79 | 25.57% | 49 | 718 | 178 | 24.79% | 78 |
| 0.125% | 296 | 76 | 25.68% | 59 | 696 | 176 | 25.29% | 98 |
| 0.15% | 283 | 75 | 26.50% | 71 | 677 | 173 | 25.55% | 114 |
| 0.158514% | 281 | 75 | 26.69% | 73 | 667 | 171 | 25.64% | 122 |
| 0.20% | 261 | 73 | 27.97% | 91 | 639 | 170 | 26.60% | 149 |

Higher thresholds consistently improve aggregate precision and remove non-targets.

But the cost in strong-winner retention becomes material beyond approximately 0.075–0.10%.

---

# Strong retention vs baseline-selected strong winners

| Threshold | Research strong retained | Fresh strong retained | Research NT removed | Fresh NT removed | Minimum block strong retention |
|---|---:|---:|---:|---:|---:|
| 0.05% | **98.82%** | **99.47%** | 4.66% | 3.07% | **98.04%** |
| **0.075%** | **97.65%** | **96.83%** | **10.39%** | **7.61%** | **94.44%** |
| 0.10% | 92.94% | 94.18% | 17.56% | 12.62% | **83.33%** |
| 0.125% | 89.41% | 93.12% | 21.15% | 15.86% | 83.33% |
| 0.15% | 88.24% | 91.53% | 25.45% | 18.45% | 83.33% |
| 0.158514% | 88.24% | 90.48% | 26.16% | 19.74% | 83.33% |
| 0.20% | 85.88% | 89.95% | 32.62% | 24.11% | 83.33% |

---

# Why +0.075% is the CT-1 primary candidate

At +0.075%:

## Research
- selected: **333**
- strong: **83**
- non-target: **250**
- precision: **24.92%**
- strong retention vs S10D baseline: **97.65%**
- non-target removal: **29 / 279 = 10.39%**

## Fresh
- selected: **754**
- strong: **183**
- non-target: **571**
- precision: **24.27%**
- strong retention vs S10D baseline: **96.83%**
- non-target removal: **47 / 618 = 7.61%**

Noise removed per strong lost:
- Research: **14.5 non-targets per strong lost**
- Fresh: **7.83 non-targets per strong lost**

Most importantly:

> **every chronological block retains at least 94.44% of its baseline-selected strong winners.**

Block strong-retention vs the 0.0339% baseline:
- Research Discovery: **96.08%**
- Research Validation: **100%**
- Research Reserve: **100%**
- Fresh Oct 1: **95.59%**
- Fresh Oct 2: **98.82%**
- Fresh Oct 3: **94.44%**

This is the cleanest tested balance between stricter confirmation and winner preservation.

---

# Why +0.10% is not the primary yet

+0.10% gives stronger aggregate pruning:

Research:
- removes 49 non-targets
- loses 6 strong
- precision rises to 25.57%

Fresh:
- removes 78 non-targets
- loses 11 strong
- precision rises to 24.79%

However block-level winner retention deteriorates:

- Research Reserve: **83.33%**
- Fresh Oct 3: **86.11%**

Thus +0.10% is retained only as an **aggressive challenger**.

---

# LONG-equivalent +0.158514%

Applying the approximate LONG confirmation threshold directly to SHORT:

Research:
- selected 281
- strong 75
- strong retention: **88.24%**
- non-target removal: **26.16%**

Fresh:
- selected 667
- strong 171
- strong retention: **90.48%**
- non-target removal: **19.74%**

This confirms that simply copying the LONG threshold is too aggressive for the current SHORT structure.

SHORT does benefit from a stricter threshold, but its optimal range appears substantially below the LONG threshold.

---

# Lane/source shift

As the confirmation threshold rises:
- T+1 temporal entries fall sharply;
- some candidates migrate to later T+2/T+3 entries;
- alternate T+3 rescue becomes more active;
- T0 fast and Lane-0 recovery remain frozen.

This means CT-4 execution replay is essential before finalizing any threshold, because stricter confirmation changes not only selection count but also **entry timing**.

CT-1 therefore does **not** make a profitability claim.

---

# CT-1 verdict

> **Baseline +0.0339% is likely too permissive.**

The sweep gives a clear confirmation-strength frontier.

Frozen candidates for next analysis:

1. **0.05% — conservative**
2. **0.075% — primary**
3. **0.10% — aggressive challenger**
4. 0.033898% — baseline control

Do not promote any threshold yet.

Next stage:

> **CT-2 — retention anatomy**

CT-2 should identify exactly which strong winners and non-target/severe-loss trades are removed or delayed by 0.05%, 0.075%, and 0.10%, before execution-realistic PP replay.

No runtime or production changes are authorized by CT-1.
