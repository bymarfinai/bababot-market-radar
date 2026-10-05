# SD-2B4 — SHORT Delayed-Entry Exit Compatibility Contract

Status: **PREREGISTERED / RESEARCH ONLY / NO EXIT RETUNING**

## Purpose
Test whether the frozen SD-2B2 Lane-1 T+3 confirmation candidate remains economically usable after realistic delayed entry, and whether existing frozen exit/protection policies are compatible with the new SHORT lane.

This stage intentionally embeds the delayed-entry reconstruction prerequisite before exit testing.

## Frozen entry candidate
Lane:
- provisional winner `SHORT_ARCHETYPE_1`
- frozen failure `SHORT_LOSS_CLUSTER_1`

Causal confirmation rule:

`T+3 confirm_side_return_pct >= +0.0338983050847%`

Expected selected causal cohort from SD-2B2:
- Discovery: 76 selected / 23 strong WIN
- Validation: 22 / 11
- Reserve: 30 / 5
- total: **128 selected / 39 strong WIN**

The rule, horizon, lane assignment, and threshold may not be changed in SD-2B4.

## Delayed-entry execution proxy
For each selected trade:

1. decision time = frozen T+3 target timestamp;
2. delayed entry = **open of the first complete Binance USD-M 1-minute bar strictly after the T+3 target timestamp**;
3. if the historical position has already closed before that executable bar, classify as `NO_EXECUTABLE_ENTRY`;
4. delayed entry side remains SHORT;
5. reuse the original position initial notional and paper fee/slippage settings when available from frozen position metadata;
6. post-entry MFE and MAE are recomputed from market data after delayed entry.

This matches the established Stage 3C.4 execution proxy and is not a claim about exact historical order-book fills.

## Market path
- delayed entry price: Binance USD-M Futures 1-minute kline open;
- intratrade exit simulation: Binance USD-M daily aggTrades;
- 5-second protector observations:
  - first observation = delayed_entry + 5s;
  - then every 5s;
  - latest aggTrade at or before boundary;
  - carry forward last known price if no new print;
- replay horizon ends at the frozen historical close timestamp.

Historical close price/time is a fallback timing boundary only; historical partial exit actions are not inherited into the delayed position.

## Frozen exit policies

### A. DELAYED_HIST_CLOSE
Hold full delayed position until the frozen historical final close price/time.

Purpose:
- delayed-entry baseline.

### B. SL1_TP1
Full close on first raw post-entry aggTrade reaching:
- +1.00% SHORT return, or
- -1.00% SHORT return;
otherwise historical-close fallback.

### C. V42_HYBRID
Frozen V4.2 logic:
- small arm = +0.50%
- small retain = 60%
- confirmation = 3 x 5s samples
- reduce fraction = 25%
- runner qualify = +1.50%
- runner retain = 90%
- runner confirmation = 2 x 5s samples
- historical-close fallback for remainder

### D. V43_SHORT_LS4
Archived SHORT-specific V4.3 near-miss, **not production-approved**:
- small arm = +0.50%
- small retain = 75%
- confirmation = 1 x 5s sample
- reduce fraction = 100% full close
- runner logic unchanged:
  - qualify +1.50%
  - retain 90%
  - confirm 2

This policy previously improved the old 13-trade SHORT REDUCE25 lane but failed the 75–80% retained-peak objective. SD-2B4 tests transport only; it does not rehabilitate the old formal NO PASS.

## No optimization
SD-2B4 performs:
- **zero exit-parameter tuning**
- zero Reserve-based selection
- zero search over arms / retain ratios / confirmation counts / fractions

All four exit policies are frozen before results are measured.

## Required outputs

For each split and full executable cohort:
- selected count
- executable / no-executable count
- original strong-WIN count
- delayed MFE median / mean
- delayed MAE median / mean
- strong winners retaining delayed MFE >=0.5% and >=1.0%
- non-targets reaching delayed MFE >=0.5% and >=1.0%

For each exit policy:
- PnL USDT
- WR
- average and median return
- gross profit / gross loss
- max loss
- strong-WIN vs non-target economics
- action counts
- retention relative to delayed post-entry MFE for realized-positive trades
- comparison versus DELAYED_HIST_CLOSE

## Compatibility tiers

An existing exit policy is called:

### COMPATIBLE
On **Validation and Reserve separately**:
- PnL >= DELAYED_HIST_CLOSE PnL
- winner count >= DELAYED_HIST_CLOSE winner count - 1
- no increase in gross loss >10%
and on full executable cohort:
- PnL improvement >0

### PROMISING
- full executable PnL improvement >0
- neither Validation nor Reserve PnL deterioration exceeds $10
- no catastrophic winner destruction

### INCOMPATIBLE
Anything worse.

These tiers assess compatibility only, not production readiness.

## Integrity
- no runtime changes;
- no paper/live promotion;
- paper entry pause remains independent;
- no LONG V4.3 parameter set is imported into SHORT;
- exact order-book fill realism is not claimed.