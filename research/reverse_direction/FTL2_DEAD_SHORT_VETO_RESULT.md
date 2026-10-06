# FTL-2 — Dead SHORT Veto from Pre-Entry 0-75s Microstructure

Status: **PARTIAL PASS — LOSS REDUCTION TRANSPORTS / SYSTEM STILL NEGATIVE**

Date: 2026-10-06

## Objective

Starting from the frozen FTL-1 forward candidate population, identify the 111 candidates whose prospective SHORT position never achieves post-entry MFE >= +0.18%, while preserving as many of the 137 economically useful candidates as possible.

The target is explicitly post-entry SHORT opportunity, not the original LONG failure label.

## Frozen population

- FTL-1 forward SHORT candidates: **248**
- post-entry MFE >= +0.18%: **137**
- post-entry MFE < +0.18%: **111**

Frozen protector used for economic scoring:
- **BE0.18 aggressive**
- no protector retuning

Baseline BE0.18:
- full 248: **-$122.84**

## Chronological research split

No random split was used.

- TRAIN = 2026-10-01: 71 candidates
  - good >=0.18 MFE: 42
  - dead <0.18 MFE: 29
  - BE0.18 baseline: **-$18.84**
- VALIDATION = 2026-10-02: 105
  - good: 61
  - dead: 44
  - BE0.18 baseline: **-$69.34**
- RESERVE = 2026-10-03: 72
  - good: 34
  - dead: 38
  - BE0.18 baseline: **-$34.66**

Threshold discovery used TRAIN only.

## Causal feature set

49 features were derived exclusively from Binance raw aggTrades observable by the 75-second decision point.

Families included:
- side return at 15 / 30 / 45 / 60 / 75s;
- running MFE and MAE progression;
- 30 / 45 / 60s slopes;
- buy-taker shares and flow deltas;
- path high/low distances;
- age of recent high/low;
- local range and realized tick volatility;
- down-tick share;
- trade-rate;
- peak giveback and rebound from path low.

No post-entry feature was used as an input.

## Primary frozen veto

The highest-ranked TRAIN-only veto is:

> **DROP / DO NOT SHORT if side return at 75s <= -0.282752%**

Equivalently:

> if the original LONG has already moved against itself by roughly **-0.283% or more** before the prospective SHORT entry, do not chase the move.

No additional condition is required.

## TRAIN

Baseline:
- 71
- BE0.18 PnL: **-$18.84**

Veto:
- drops 15
- 12 dead
- 3 good
- dead precision: **80.0%**
- dead recall: 41.38%
- good retention: **92.86%**

Survivors:
- 56
- 39 good
- BE0.18 PnL: **-$1.37**

Improvement:
- **+$17.47**

## VALIDATION — untouched 2026-10-02

Baseline:
- 105
- **-$69.34**

Frozen veto:
- drops 25
- 17 dead
- 8 good
- dead precision: **68.0%**
- dead recall: 38.64%
- good retention: **86.89%**

Survivors:
- 80
- 53 good
- PnL: **-$55.77**

Improvement:
- **+$13.57**

The veto reduces losses but does not make Validation profitable.

## RESERVE — untouched 2026-10-03

Baseline:
- 72
- **-$34.66**

Frozen veto:
- drops 16
- 14 dead
- 2 good
- dead precision: **87.5%**
- dead recall: 36.84%
- good retention: **94.12%**

Survivors:
- 56
- 32 good
- PnL: **-$25.85**

Improvement:
- **+$8.81**

Again the loss reduction transports, but absolute profitability does not.

## Validation + Reserve combined

Frozen veto:
- drops 41
- 31 dead
- 10 good
- dead precision: **75.61%**
- dead recall: 37.80%
- good retention: **89.47%**

Survivors:
- 136
- 85 good
- PnL: **-$81.63**

Baseline Validation + Reserve:
- **-$104.00**

Improvement:
- **+$22.38**

## Full 248 diagnostic

Frozen veto:
- drops **56**
- dead dropped: **43**
- good collateral: **13**
- dead precision: **76.79%**
- dead recall: **38.74%**
- good retention: **90.51%**

Survivors:
- **192**
- good: 124
- dead: 68
- BE0.18 PnL: **-$83.00**

Full baseline:
- **-$122.84**

Full delta:
- **+$39.84**

Therefore the veto removes roughly one-third of the original full-sample loss while preserving over 90% of the >=0.18%-MFE population.

## Interpretation

The result validates the economic timing hypothesis:

> A LONG that has already fallen too far by the 75-second FTL decision is often a **bad LONG but also a bad SHORT entry**.

The move has already been consumed.

The strongest simple causal signal is not an additional order-flow statistic. It is:

> **distance already travelled before the SHORT entry.**

This explains the earlier paradox:
- final LONG outcome can remain very poor;
- yet reversing at 75 seconds can lose because the prospective SHORT enters after a large part of the decline has already happened.

## Other TRAIN candidates

Several two-feature rules achieved 90-100% dead precision on TRAIN, including combinations of:
- deep side75 decline,
- very recent path low,
- MAE75,
- long-window negative slope.

However none of the top ten TRAIN-frozen candidates made both Validation and Reserve profitable.

They are exploratory only and are not promoted.

## Verdict

FTL-2 is a **partial pass**:

- the pre-entry veto transports as a loss reducer;
- it preserves about 90% of the useful >=0.18%-MFE cohort;
- it improves total BE0.18 result from -$122.84 to about **-$83.00**;
- but it does **not** solve profitability.

Production remains **HOLD**.

## Next implication

After the frozen distance veto, the remaining 192 trades still contain:
- 124 useful >=0.18%-MFE trades;
- **68 dead <0.18%-MFE trades**.

The next clean target should not keep mining the same 0-75s feature space.

A more direct causal architecture is:

> **75s FTL candidate -> distance veto -> require a small favorable SHORT confirmation after 75s before actual execution**

For example, first-touch favorable confirmation from the prospective 75s price can be tested before committing capital.

This directly asks whether downside is still available instead of predicting it indirectly.
