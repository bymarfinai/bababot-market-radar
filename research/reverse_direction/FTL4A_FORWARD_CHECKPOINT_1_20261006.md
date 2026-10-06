# FTL-4A Frozen Forward Checkpoint 1

Status: **FORWARD STARTED / INSUFFICIENT SAMPLE**

Date: 2026-10-06

## Frozen rule

No retuning.

1. 75s FTL candidate:
   - running MFE <= +0.0835421888%
   - last-30s LONG buy-taker share <= 23.0565953%
2. FTL-2 veto:
   - do not SHORT if side75 <= -0.2827521206%
3. Downside confirmation:
   - -0.05% from the 75s anchor within 30s
4. Bounce/retest:
   - +0.10% from fresh post-confirm local low within 60s
5. SHORT at first bounce touch
6. Frozen BE0.18 / V4.3-LS / V4.2 runner exit stack

## Forward cutoff

Prior research sample ended at approximately:

- 2026-10-06 03:02 UTC

Only positions opened after that cutoff are eligible for this forward checkpoint.

## New closed LONG population

At checkpoint time:

- new closed LONG trades: **1**
- symbol: SENTUSDT
- opened: 2026-10-06 03:02:26.145 UTC
- closed: 2026-10-06 07:32:08.421 UTC
- historical LONG realized PnL: **+$0.6066**

Raw Binance Futures aggTrades replay:
- 15,789 aggregate trades
- exact path from original LONG open through historical close

## Frozen 75s state

At 75 seconds:

- running MFE: **+0.89599%**
- 30s LONG buy-taker share: **79.7661%**
- side return: **+0.77912%**

FTL-1 frozen thresholds require:
- running MFE <= +0.08354%
- buy-taker share <= 23.0566%

Therefore:

> **FTL-1 = FALSE**

FTL-2 veto itself would not have rejected the trade, but it is irrelevant because the upstream FTL gate did not fire.

## FTL-4A result

- FTL candidate: NO
- confirmation stage: not evaluated
- bounce/retest stage: not evaluated
- SHORT entry: **NO ENTRY**
- strategy PnL: **$0**
- historical LONG PnL: +$0.6066

This is the correct behavior for the frozen forward rule.

## Interpretation

The forward framework is operating causally and is not forcing every new LONG into a reverse SHORT.

This particular trade showed strong LONG continuation by 75s:
- high favorable excursion;
- very high aggressive buy participation;
- positive side return.

It is therefore the opposite of the intended failure-to-launch population.

## Verdict

No statistical conclusion can be drawn yet because the genuinely new forward cohort contains only one closed LONG trade.

The important checkpoint is:

> **Frozen FTL-4A rule produced zero false reverse entry on the first genuinely new LONG trade.**

Thresholds remain unchanged for the next forward observations.
