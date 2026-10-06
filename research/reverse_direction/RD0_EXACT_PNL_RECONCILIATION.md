# RD-0 — Exact PnL Reconciliation

Status: **research-only / no production authority**

RD-0 exists to answer one narrow question before any selective-reversal tuning:

> Why does historical LONG net PnL of roughly -$1,294 not become +$1,294 when every direction is flipped?

## Frozen universe

- source: `/app/data/wd5h4a_temporal_features.csv`
- side: LONG only
- resolved primary labels: META_WIN / META_LOSS
- expected universe: **1,236 trades**
- entry/exit timing: unchanged from the historical trade
- REDUCE/CLOSE market endpoints: unchanged from the historical trade
- historical quantities: unchanged for the algebraic same-quantity control

RD-0 is not a new detector, not a Health replacement, and not a profit-protection rule.

## Required scenarios

1. Historical DB net PnL.
2. Historical stored-fill replay.
3. Original LONG raw PnL at the historical market endpoints with zero fee/slippage.
4. Mirrored SHORT raw PnL at exactly the same market endpoints with zero fee/slippage.
5. Mirrored SHORT with Binance regular taker fee **0.05% per side**, no modeled slippage.
6. Mirrored SHORT with taker **0.05% per side + 2 bps slippage per side**.
7. Sensitivity: BNB fee benchmark **0.045% per side + 2 bps slippage**.
8. Execution-comparable mirror using fresh **$500** notional with the same historical exit fractions.

The raw control must satisfy, trade by trade:

`original_raw_same_market + mirror_raw_same_market == 0`

within floating-point tolerance.

The stored-fill historical replay must also reconcile to `positions.realized_pnl` before the RD-0 result is accepted.

## Outputs

Running:

`python research/reverse_direction/rd0_exact_pnl_reconciliation.py --data-dir /app/data`

writes:

- `research/reverse_direction/results/RD0_TRADE_DETAIL.csv`
- `research/reverse_direction/results/RD0_EXACT_PNL_RECONCILIATION.json`
- `research/reverse_direction/results/RD0_RESULT.md`

The result explicitly decomposes:

- raw directional edge,
- taker-fee drag,
- incremental slippage drag,
- fixed-notional execution effect,
- and the gap between naive `+abs(historical net)` and a true same-endpoint direction inversion.

## Fee correction used by RD-0

Active paper defaults are aligned to the Binance USD-M regular-user taker benchmark:

- fee: **0.0005 = 0.05% per side**
- modeled slippage: **2 bps per side**, separately configurable

Archived research artifacts keep their original recorded assumptions for reproducibility.
