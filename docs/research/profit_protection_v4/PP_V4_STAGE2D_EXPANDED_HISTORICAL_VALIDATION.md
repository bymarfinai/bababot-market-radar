# PP V4-2D — Expanded Historical Validation

Status: **COMPLETE — HISTORICAL-ONLY VALIDATION**

## Why this validation exists

The prospective Stage2D shadow was intentionally disabled before collecting new PAPER positions. The selected Stage2C hybrid was first tested against the largest existing historical cohort with strict archived ~5s coverage.

## Primary cohort

Historical closed PAPER positions with strict lifecycle coverage for both archived 5s and 15s observations:

- total: **189 trades**
- clean post-entry MFE >= +0.30%: **99**
- clean post-entry MFE < +0.30%: **90**

The selected Stage2C policy is unchanged:

`small 0.50/60/3 -> REDUCE 25%; runner qualify 1.50 -> retain 90/confirm2`

## Result on all 189 strict trades

Historical actual:
- total realized: **-$242.13**
- winners: **37 / 189**
- win rate: **19.58%**

With Stage2C hybrid replay:
- total simulated: **-$153.38**
- improvement: **+$88.75**
- loss reduction: **36.65%**
- winners: **46 / 189**
- win rate: **24.34%**
- helped trades: **49**
- harmed trades: **13**
- small reductions: **49**
- runner closes: **19**

The hybrid materially improves the historical population, but **does not make the full 189-trade population profitable**.

## Why the full result remains negative

The 99 clean-MFE >=0.30% trades are exactly the profit-opportunity cohort previously studied:

- actual: **-$10.02**
- hybrid: **+$78.73**
- improvement: **+$88.75**
- win rate: **36.36% -> 45.45%**

The other 90 strict trades never reached clean post-entry MFE +0.30%:

- actual: **-$232.10**
- hybrid: **-$232.10**
- winners: **1 / 90**
- policy actions: **0**
- improvement: **$0**

Those 90 low-opportunity trades account for **95.86% of the absolute net loss** in the 189-trade strict cohort.

This is expected: a profit-protection policy cannot protect profit that never becomes observable.

## Interpretation

Stage2C/2D profit protection is doing its intended job:

- it materially improves trades that develop observable profit;
- it does not create profit on trades that never develop a protectable excursion.

Therefore the dominant unresolved problem in the full historical population is now upstream of profit protection:

> **entry / direction / NO-TRADE selection for the 90 trades that never reached +0.30% clean MFE.**

Prospective PAPER shadow is not required to establish this point and remains disabled.

## Raw 208-trade sensitivity

There are 208 historical closed positions with some archived 5s observations, but 19 fail the strict lifecycle coverage requirement.

Those 19 are not valid for causal protection replay because their 5s path is truncated. A raw 208-trade replay produces misleading deterioration and is not used for the primary conclusion.

Primary source of truth remains the **189 strict-coverage trades**.

## Runtime status

- Stage2D prospective shadow: **disabled**
- automation/watch: **disabled**
- control: **RUN**
- live trading: **disabled/disarmed**
- no protection authority
