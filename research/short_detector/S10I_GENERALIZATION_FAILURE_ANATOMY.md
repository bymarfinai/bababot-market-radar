# SHORT-S10I — Fresh Generalization Failure Anatomy

Status: **DIAGNOSIS COMPLETE — suppressor transport failure identified**

## Objective

Explain why the frozen S10G SHORT detector passed the research replay but failed the fresh sealed S10H window.

S10H must now be treated as an opened development/failure-analysis dataset. It cannot be reused as a sealed validation set after any repair.

## Key finding

The failure is **not primarily the S10D recovery detector**.

The dominant failure is:

> **the S10E and S10G false-positive suppressor bands do not transport to the fresh regime.**

Several bands that were strongly loss-enriched in the research data become winner-enriched in the fresh data.

---

# Stage-by-stage transport

## Research

Base resolved universe:
> 655 → 99 strong WIN  
> base prevalence = **15.11%**

S10D:
> **364 → 85 strong + 279 non-target**
- precision: **23.35%**
- recall: **85.86%**
- lift: **1.54x**

S10E:
> **331 → 83 strong + 248 non-target**
- precision: **25.08%**
- recall: **83.84%**
- lift: **1.66x**

S10G:
> **225 → 79 strong + 146 non-target**
- precision: **35.11%**
- recall: **79.80%**
- lift: **2.32x**

Thus the research profitability improvement came largely from the S10E/S10G pruning layers.

## Fresh S10H

Base resolved universe:
> 1,449 → 261 strong WIN  
> base prevalence = **18.01%**

S10D:
> **807 → 189 strong + 618 non-target**
- precision: **23.42%**
- recall: **72.41%**
- lift: **1.30x**

S10E:
> **751 → 172 strong + 579 non-target**
- precision: **22.90%**
- recall: **65.90%**
- lift: **1.27x**

S10G:
> **516 → 112 strong + 404 non-target**
- precision: **21.71%**
- recall: **42.91%**
- lift: **1.21x**

## Important interpretation

S10D research precision:
> **23.35%**

S10D fresh precision:
> **23.42%**

This is almost unchanged.

Therefore:

> **the core S10D selection/recovery layer transports much better than the later suppressors.**

S10D recall does degrade:
- research 85.86%
- fresh 72.41%

but its precision remains essentially stable.

The catastrophic loss of discrimination occurs after S10D.

---

# S10E overheat veto transport failure

Frozen S10E veto:

> `f_new_overheat_pressure in [4.0018436068809455, 4.470349182901625]`

## Research

Before veto:
- 85 strong
- 279 non-target

Veto removed:
- **2 strong**
- **31 non-target**

Winner removal rate:
> **2.35%**

Non-target removal rate:
> **11.11%**

Veto cohort strong rate:
> **6.06%**

This is a useful suppressor.

## Fresh

Before veto:
- 189 strong
- 618 non-target

Veto removed:
- **17 strong**
- **39 non-target**

Winner removal rate:
> **8.99%**

Non-target removal rate:
> **6.31%**

Veto cohort strong rate:
> **30.36%**

Therefore the same band becomes winner-enriched in fresh data.

S10E consequently reduces precision:

> S10D fresh 23.42% → S10E fresh **22.90%**

---

# S10G suppressor transport failure

## Aggregate S10G veto

### Research

Before S10G:
- 83 strong
- 248 non-target

Removed:
- **4 strong**
- **102 non-target**

Winner removal rate:
> **4.82%**

Non-target removal rate:
> **41.13%**

This is highly selective pruning.

### Fresh

Before S10G:
- 172 strong
- 579 non-target

Removed:
- **60 strong**
- **175 non-target**

Winner removal rate:
> **34.88%**

Non-target removal rate:
> **30.22%**

The suppressor now removes winners at a higher rate than noise.

That is why:

> S10E fresh precision 22.90% → S10G fresh **21.71%**

---

# T+1 failure

Fresh S10E T+1 cohort:

> 241 → 57 strong + 184 non-target

Research S10G T+1 veto had been extremely effective.

## Research T+1

Veto:
> **75 → 2 strong + 73 non-target**

Kept:
> **40 → 12 strong + 28 non-target**

Veto strong rate:
> **2.67%**

Kept strong rate:
> **30.0%**

## Fresh T+1

Veto:
> **168 → 43 strong + 125 non-target**

Kept:
> **73 → 14 strong + 59 non-target**

Veto strong rate:
> **25.60%**

Kept strong rate:
> **19.18%**

The veto has literally inverted:

> the cohort being removed is now richer in strong winners than the cohort being kept.

### Individual T+1 rules

#### `f_new_accel_15_vs_60` band

Research hit:
- 44
- 2 strong
- strong rate **4.55%**

Fresh hit:
- 110
- 29 strong
- strong rate **26.36%**

#### `f_new_volume_over_range` band

Research:
- 31 hit
- 1 strong
- **3.23%**

Fresh:
- 75 hit
- 18 strong
- **24.0%**

#### `f_gate_price_drift_pct` band

Research:
- 26 hit
- **0 strong**

Fresh:
- 47 hit
- 9 strong
- **19.15%**

All three hard bands lose their original loss-enrichment.

---

# T+2 failure

Fresh S10E T+2 cohort:

> 238 → 59 strong + 179 non-target

## Research T+2

Veto:
> **31 → 2 strong + 29 non-target**

Kept:
> **70 → 27 strong + 43 non-target**

Veto strong rate:
> **6.45%**

Kept strong rate:
> **38.57%**

## Fresh T+2

Veto:
> **67 → 17 strong + 50 non-target**

Kept:
> **171 → 42 strong + 129 non-target**

Veto strong rate:
> **25.37%**

Kept strong rate:
> **24.56%**

The veto provides essentially no discrimination in the fresh regime.

### Individual T+2 rules

#### `t2_confirm_side_return_pct` band

Research:
- 13 hit
- **0 strong**

Fresh:
- 25 hit
- 5 strong
- **20.0%**

#### `f_f_taker_accel_1m` band

Research:
- 11 hit
- **0 strong**

Fresh:
- 18 hit
- **11 strong**
- strong rate: **61.11%**

This is the most severe inversion found in S10I.

A region that was a perfect loss-only veto in the research set becomes a majority-winner region in fresh data.

#### `f_new_gate_price_x_flow_gap` band

Research:
- 13 hit
- 2 strong
- **15.38%**

Fresh:
- 32 hit
- 2 strong
- **6.25%**

This is the notable exception: this rule remains loss-enriched and is the most transportable of the three T+2 suppressor components.

---

# Root cause

The SHORT failure is not accurately described as simply:

> “the market changed.”

The more precise cause is:

> **the S10E/S10G suppressors rely on narrow absolute feature bands whose class meaning is regime-dependent.**

During research, these bands happened to isolate false positives extremely well.

In the fresh regime:
- the same feature ranges are occupied by many genuine winners;
- winner-removal rates rise sharply;
- the pruning layer destroys recall;
- precision actually declines rather than improves.

This explains the selection-lift collapse:

> **2.32x research → 1.21x fresh**

and ultimately the S10H protected PnL failure:

> **-$179.30**

## What still works

Two things remain clearly real:

1. **Strong SHORT opportunities remain highly monetizable.**
   - S10H executable strong cohort: 104
   - protected WR: 85.58%
   - protected PnL: **+$290.78**

2. **S10D retains meaningful transport.**
   - precision research: 23.35%
   - precision fresh: 23.42%

Thus the next repair should not restart the entire SHORT detector from zero.

---

# Engineering implication

Do **not** patch the existing S10E/S10G absolute bands using new thresholds from S10H.

That would simply overfit the now-opened S10H window.

Instead the next development stage should redesign suppression to be **regime-normalized / relative**, for example:
- percentile or z-score relative to current market regime,
- cross-sectional rank,
- winner-vs-noise margin conditioned on volatility/flow regime,
- stability across rolling chronological blocks,
- no single narrow absolute band allowed to carry the suppressor.

S10H may be used for development diagnostics only.

Any repaired suppressor must then be frozen and tested on a **new later unseen window**.

## Verdict

> **S10I = DIAGNOSIS COMPLETE.**

Primary failure source:

> **S10E/S10G hard-band suppressors overfit the research regime and become winner-destructive out of sample.**

No production/runtime changes are authorized.
