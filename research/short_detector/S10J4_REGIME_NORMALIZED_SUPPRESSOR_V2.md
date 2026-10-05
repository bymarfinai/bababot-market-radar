# SHORT-S10J-4 — Regime-Normalized Suppressor V2

Status: **PRIMARY RESEARCH CANDIDATE FROZEN FOR S10J-5 EXECUTION REPLAY**

## Objective

Build a low-complexity false-positive suppressor on top of the stable S10D base without repeating the S10E/S10G hard-band overfit.

Frozen base:
- S10D detector
- V4.3 SHORT-LS4
- BE0.10 on V4.3 NO_ACTION
- no S10E/S10G absolute veto bands

Development data:
- Research Discovery / Validation / Reserve
- Fresh S10H Oct 1 / Oct 2 / Oct 3
- S10H is development-only and is no longer a sealed holdout.

## Candidate search constraints

- maximum 2–4 normalized signals
- causal by entry lane
- monotonic rules only
- no narrow absolute bands
- no T0 rule unless stable evidence exists
- research strong retention >= 90%
- fresh strong retention >= 90%
- no chronological block allowed to lose precision for the accepted primary
- no future temporal feature use before its lane decision

## Primary Suppressor V2

The primary candidate uses exactly **2 signals**.

### Rule 1 — T+1 low relative micro-volume

For a T+1 candidate:

> VETO if `f_micro_volume_ratio_last_vs_prev10` is at or below the **30th percentile** of the prior 128 S10D-selected trades.

Normalization is causal:
- prior rows only
- current trade is evaluated before entering rolling history
- minimum rolling history: 20 observations

### Rule 2 — T+3 low relative confirmation

For a T+3 candidate:

> VETO if `t3_confirm_side_return_pct` is at or below the **30th percentile** of the prior 128 S10D-selected trades.

This is causal because T+3 confirmation is available at the T+3 decision point.

### No rule for T0

T0 had no 6/6 clean normalized suppressor candidate.

### No primary rule for T+2

T+2 normalized candidates showed useful evidence, but either:
- effect size was weaker, or
- research support was too sparse.

They remain challengers, not part of primary V2.

---

# Aggregate result

## Research

S10D baseline:

> **364 → 85 strong + 279 non-target**

Precision:
> **23.35%**

Primary V2 veto:

> **47 → 5 strong + 42 non-target**

Keep:

> **317 → 80 strong + 237 non-target**

Metrics:
- strong retention: **94.12%**
- non-target removal: **15.05%**
- precision: **25.24%**
- precision improvement: **+1.88 percentage points**

## Fresh S10H development window

S10D baseline:

> **807 → 189 strong + 618 non-target**

Precision:
> **23.42%**

Primary V2 veto:

> **84 → 10 strong + 74 non-target**

Keep:

> **723 → 179 strong + 544 non-target**

Metrics:
- strong retention: **94.71%**
- non-target removal: **11.97%**
- precision: **24.76%**
- precision improvement: **+1.34 percentage points**

## Combined development set

Baseline:

> **1,171 → 274 strong + 897 non-target**

Primary V2 veto:

> **131 → 15 strong + 116 non-target**

Veto composition:

> **88.55% non-target**

Keep:

> **1,040 → 259 strong + 781 non-target**

Metrics:
- strong retention: **94.53%**
- non-target removal: **12.93%**
- precision: **24.90%**
- baseline precision: 23.40%
- improvement: **+1.51 percentage points**

---

# Chronological stability

| Block | Strong retention | Precision before | Precision after | Delta |
|---|---:|---:|---:|---:|
| Research Discovery | 94.12% | 23.18% | 25.67% | **+2.49 pp** |
| Research Validation | 90.91% | 31.88% | 33.33% | **+1.45 pp** |
| Research Reserve | 100.00% | 16.00% | 17.14% | **+1.14 pp** |
| Fresh Oct 1 | 95.59% | 21.59% | 22.97% | **+1.38 pp** |
| Fresh Oct 2 | 92.94% | 26.32% | 27.05% | **+0.74 pp** |
| Fresh Oct 3 | 97.22% | 21.30% | 23.65% | **+2.35 pp** |

Result:

> **6 / 6 blocks improve precision.**

No chronological block shows the S10G-style inversion where the veto cohort becomes more winner-rich than the kept cohort.

---

# Lane effect

## T0

Unchanged.

> 264 → 66 strong + 198 non-target  
> precision 25.00%

## T+1

Baseline:

> 379 → 80 strong + 299 non-target

Primary V2 veto:

> **99 → 12 strong + 87 non-target**

Keep:

> **280 → 68 strong + 212 non-target**

Precision:

> **21.11% → 24.29%**

## T+2

Unchanged in primary V2.

> 373 → 96 strong + 277 non-target

## T+3

Baseline:

> 155 → 32 strong + 123 non-target

Primary V2 veto:

> **32 → 3 strong + 29 non-target**

Keep:

> **123 → 29 strong + 94 non-target**

Precision:

> **20.65% → 23.58%**

---

# Boolean structure check

The two strongest T+1 normalized signals were also tested as AND vs OR.

## T+1 AND

High relative overheat AND low relative micro-volume:

Research:
- strong retention 100%
- non-target removal only 3.94%

Fresh:
- strong retention 98.41%
- non-target removal only 2.75%

Verdict:

> too conservative; insufficient noise removal.

## T+1 OR

High relative overheat OR low relative micro-volume:

Research:
- strong retention 96.47%
- non-target removal 23.66%

Fresh:
- strong retention **86.77%**

Verdict:

> too aggressive; fails the >=90% fresh winner-retention gate.

Therefore the accepted T+1 component is:

> **low relative micro-volume alone.**

---

# Challengers retained for S10J-5

## Conservative challenger

T+1 low relative micro-volume only.

Research:
- strong retention 97.65%
- non-target removal 12.90%
- precision 25.46%

Fresh:
- strong retention 94.71%
- non-target removal 8.25%
- precision 23.99%

## T+1 + T+2 challenger

T+1 low relative micro-volume OR T+2 low relative confirmation percentile.

Research:
- strong retention 92.94%
- non-target removal 16.49%
- precision 25.32%

Fresh:
- strong retention 93.65%
- non-target removal 13.27%
- precision 24.82%

This challenger also improves all six chronological blocks, but is more aggressive than the primary and has weaker T+2 support.

---

# Why Primary V2 is different from S10G

S10G used narrow absolute feature bands and achieved high in-sample pruning but failed transport.

Primary V2 instead uses:
- relative rank against recent regime
- monotonic tails
- causal rolling history
- only two rules
- no forced rule for every lane
- explicit strong-retention gate
- explicit six-block stability gate

Its improvement is intentionally smaller than S10G research precision.

That is by design.

The priority is:

> **stable modest discrimination across regimes > spectacular discrimination in one regime.**

---

# Verdict

> **S10J-4 = PASS as a low-complexity research suppressor design stage.**

Primary Suppressor V2 is now frozen for the next stage:

> **S10J-5 — execution-realistic replay with frozen V4.3 + BE0.10**

S10J-5 must compare at minimum:
1. S10D baseline
2. Conservative T+1-only candidate
3. Primary V2
4. T+1 + T+2 challenger

No production/runtime changes are authorized by S10J-4.

After S10J-5, any final repair still requires a later **new unseen sealed window**.