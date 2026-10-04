# PP V4-2C — Runner Preservation / Two-Regime Protection

Status: **COMPLETE — RESEARCH ONLY**

## Executive result

A two-regime hybrid improves the balance between small-profit conversion and runner preservation.

Stage2C tested exactly **24 preregistered hybrid candidates** on the frozen 99-trade Stage2A cohort.

Because Stage2B already inspected all chronological thirds, Stage2C makes **no untouched-holdout claim**. Instead it requires positive improvement in EARLY, MID, and LATE and compares against both Stage2B static reference regimes.

Balanced-pass candidates: **2 / 24**.

The preregistered stability ranking selects:

> **Small mode:** arm +0.50%, retain 60%, confirm 3 observations  
> **Action:** REDUCE 25% of remaining quantity once  
> **Runner qualification:** observed running peak >= +1.50%  
> **Runner mode:** retain 90%, confirm 2 observations, then CLOSE remaining

Research shorthand:

`small 0.50/60/3 -> reduce 25%; runner at 1.50 -> 90/2`

This is a research reference only. It is **not deployed**.

## Why this candidate was selected

Stage2C ranks balanced-pass candidates by:

1. highest minimum chronological-third USD improvement;
2. then full-cohort total USD;
3. then win rate.

Selected candidate chronological deltas versus actual:

- EARLY: **+$11.86**
- MID: **+$42.28**
- LATE: **+$34.61**

Minimum third improvement: **+$11.86**.

The second balanced-pass candidate has slightly higher full total (+$81.54) but a lower minimum-third improvement (+$10.13), so it loses the preregistered stability ranking.

## Full 99-trade result

Historical actual:
- total: **-$10.02**
- wins: **36 / 99**
- win rate: **36.36%**

Stage2B runner static reference:
- total: **+$75.96**
- wins: **37 / 99**
- win rate: **37.37%**

Selected Stage2C hybrid:
- total: **+$78.73**
- delta versus actual: **+$88.75**
- wins: **45 / 99**
- win rate: **45.45%**
- small partial reductions: **49**
- runner closes: **19**

So the hybrid:
- slightly exceeds the Stage2B runner-static total;
- improves win conversion by **+8.08 percentage points** versus the runner-static reference;
- retains most of the runner benefit.

## Small / medium observable profit

Observable executable-net peak 0.30–1.00%, N=33.

Historical / Stage2B runner reference:
- total: about **+$0.65 / +$1.94**
- wins: **15 / 33**
- win rate: **45.45%**
- nonpositive: **18**

Selected hybrid:
- total: **+$8.33**
- wins: **21 / 33**
- win rate: **63.64%**
- nonpositive: **12**
- small reductions: **32**

The hybrid therefore converts **6 additional small/medium trades** from nonpositive to positive versus the runner reference/baseline region.

It does not match the aggressive static rule's small-profit conversion:
- aggressive static 0.50/60/2 wins **28 / 33** small/medium trades;
- but that static rule damages runner retention severely.

Stage2C intentionally trades some small-profit aggressiveness for runner preservation.

## Runner >=1%

N=20.

Historical:
- total: **+$71.35**
- median retention: **36.37%**
- nonpositive: **2**

Stage2B runner-static:
- total: **+$156.03**
- median retention: **77.27%**

Selected hybrid:
- total: **+$150.80**
- median retention: **73.57%**
- >=80% retention share: **35%**
- wins: **19 / 20**
- nonpositive: **1**

The hybrid gives up only **3.70 percentage points** of median runner retention versus the Stage2B runner-static reference, within the preregistered 5-point tolerance.

## Runner >=2%

N=9.

Historical:
- total: **+$44.81**
- median retention: **37.17%**
- nonpositive: **1**

Stage2B runner-static:
- total: **+$104.55**
- median retention: **82.46%**

Selected hybrid:
- total: **+$100.00**
- median retention: **82.46%**
- >=80% retention share: **55.56%**
- wins: **9 / 9**
- nonpositive: **0**

For the >=2% runner group, the hybrid preserves the **same median retention** as the Stage2B runner-static reference.

## Comparison with aggressive static protection

Stage2B aggressive static reference:

`0.50 / 60% / confirm 2 / full CLOSE`

Full cohort:
- total: **+$28.22**
- win rate: **56.57%**

Runner >=1%:
- median retention: **46.85%**

Runner >=2%:
- median retention: **46.56%**

Selected Stage2C hybrid:
- total: **+$78.73**
- win rate: **45.45%**
- runner >=1% median retention: **73.57%**
- runner >=2% median retention: **82.46%**

This confirms the value of partial reduction plus runner transition instead of fully closing every early giveback.

## Concentration / stability

Selected hybrid:
- helped trades: **49**
- harmed trades: **13**

By chronological third:

EARLY:
- delta: **+$11.86**
- helped: 14
- harmed: 5

MID:
- delta: **+$42.28**
- helped: 21
- harmed: 3

LATE:
- delta: **+$34.61**
- helped: 14
- harmed: 5

Contribution concentration:
- largest positive contributor: **19.45%** of total uplift
- top 3: **44.15%**

The result is materially less concentrated than the Stage2B best static LATE result and is not dependent on a single trade.

Largest improvements include:
- UAIUSDT LONG: **+$17.27**
- USUSDT SHORT: **+$12.56**
- BRUSDT SHORT: **+$9.36**
- ATUSDT SHORT: **+$6.27**

Largest deterioration:
- COMPUSDT LONG: **-$2.01**
- FLOWUSDT LONG: **-$1.13**

These harmed runner cases remain important inputs for Stage2D/shadow validation.

## Balanced-pass gate

The selected hybrid passes all preregistered gates:

1. total USD > historical actual: **PASS**
2. win rate > Stage2B runner reference: **PASS**
3. runner >=1% median retention >=72.27%: **PASS** at 73.57%
4. runner >=2% median retention >=77.46%: **PASS** at 82.46%
5. small/medium nonpositive count lower than runner reference: **PASS**, 18 -> 12
6. positive USD delta in EARLY/MID/LATE: **PASS**

## Interpretation

Stage2B showed that one static rule cannot simultaneously maximize:
- small-profit conversion;
- runner retention.

Stage2C demonstrates that a simple causal state machine can materially combine both:

1. once a modest profit has been observed, a **small partial reduction** protects some value;
2. if the trade later proves itself and reaches +1.50% observed running peak, it transitions into **runner mode**;
3. runner mode protects the remaining position using the looser 90% / 2-observation trailing logic.

The 25% small reduction is important. Larger 50–75% early reductions improve some win-conversion metrics but fail the runner-preservation balance gate more often.

## Stage2C decision

Proceed to:

> **V4-2D — Full Replay / Prospective Shadow Specification**

Stage2D should:
- replay the selected state machine trade-by-trade with auditable action logs;
- verify fee/quantity accounting and action ordering;
- compare selected hybrid vs historical vs both Stage2B static references;
- define a prospective shadow-only implementation;
- validate on new positions before any exit authority is considered.

## Runtime decision

- no Stage2C policy deployed;
- no runtime change;
- no new REDUCE/CLOSE authority;
- live remains disabled/disarmed.

## Frozen artifacts

- preregistration:
  `docs/research/profit_protection_v4/PP_V4_STAGE2C_RUNNER_PRESERVATION_CONTRACT.md`
- evaluator:
  `research/profit_protection_v4/stage2c_runner_preservation.py`
- full 24-candidate sweep:
  `research/profit_protection_v4/results/stage2c_runner_preservation_sweep.json`
- frozen result:
  `research/profit_protection_v4/results/stage2c_runner_preservation.json`
