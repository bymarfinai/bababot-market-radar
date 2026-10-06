# RD-0 Wrong-Direction Preflight Audit

Status: **PRELIMINARY CONTROL PASS / exact VPS replay still required**

## Question

Why can the 555 LONG `WRONG_DIRECTION` trades lose in their original direction, while prior reverse experiments also appeared negative?

## Frozen aggregate

- `WRONG_DIRECTION`: **555 trades**
- historical realized PnL: **-$1,543.49**
- average historical PnL: **-$2.781/trade**
- average historical return: **-0.5562%**

This magnitude is far larger than modeled Binance trading friction.

## Library row-level audit

The available Library copy of `LP3_WINNER_HARM_INTERACTION_1236.csv` is truncated after 822 rows, but exact-match extraction recovers **352 WRONG_DIRECTION rows**.

Observed on those 352 rows:

- historical PnL: **-$985.24**
- average realized return: **-0.5598%**
- median realized return: **-0.5576%**
- 216 / 352 closed between **-0.50% and -0.75%**
- only 9 / 352 closed better than -0.20%

Therefore this is not a population of tiny losses that can plausibly remain negative after direction inversion purely because of fees.

## Algebraic same-endpoint control

Historical runtime assumptions:

- fee: 0.075% per side
- slippage: 2 bps per side
- approximate round-trip friction: **0.19%**
- $500 notional => **~$0.95/trade**

Corrected Binance benchmark:

- fee: 0.05% per side
- slippage: 2 bps per side
- approximate round-trip friction: **0.14%**
- $500 notional => **~$0.70/trade**

Using the frozen 555 aggregate:

- historical friction estimate: 555 × $0.95 = **$527.25**
- inferred original raw directional PnL: -$1,543.49 + $527.25 = **-$1,016.24**
- pure opposite raw PnL at identical market endpoints: **+$1,016.24**
- corrected reverse friction: 555 × $0.70 = **$388.50**
- inferred corrected reverse net: **+$627.74**
- inferred average corrected reverse: **+$1.13/trade = +0.2262%**

On the directly observable 352-row subset, the same per-trade algebra gives:

- inferred corrected reverse PnL: **+$404.44**
- inferred positive reverse trades: **313 / 352 = 88.92%**

These are algebraic controls, not an execution replay. Exact exit notional and fee calculations can move the final dollar value modestly, but the sign should not flip if the replay truly freezes the same market endpoints.

## Diagnosis

A true same-entry / same-exit / side-only inversion must satisfy:

`LONG_raw + SHORT_raw = 0`

trade by trade.

Therefore any prior experiment in which both the original 555 LONG wrong-direction cohort and its reversed counterpart remain materially negative is **not a pure side inversion**. It is changing at least one additional element such as:

- exit timestamp / horizon,
- TP / SL path,
- candle-close censor,
- quantity construction,
- lifecycle / Health actions,
- or execution endpoint.

That is the likely source of the apparent anomaly.

## Exact RD-0

`research/reverse_direction/rd0_exact_pnl_reconciliation.py` now defaults to:

`--scope wrong_direction`

and asserts exactly **555 TRUE_WRONG_DIRECTION LONG trades**.

The exact VPS replay must verify:

1. stored historical execution replay matches DB PnL,
2. raw LONG + raw SHORT = 0 trade by trade,
3. fee-only reverse,
4. fee + 2bps reverse,
5. fixed $500 reverse.

No TP, SL, Health, horizon replacement, or detector tuning is allowed in the pure inversion lane.
