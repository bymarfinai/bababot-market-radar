# LC-1 — LONG Confirmation Entry Grid

Status: **COMPLETE — exact raw-path replay on core-prod, 2026-10-06**

Authority: research only. No production entry, execution, Health, or profit-protection rule changed.

## Question

Can LONG quality be improved by delaying entry until price first proves the LONG direction by +0.10% to +0.50%, then using a tight 0.30% to 0.50% stop from the fresh entry?

## Frozen universe and execution contract

- frozen resolved LONG universe: **1,236**
- raw Binance archive coverage: **1,235 / 1,236**
- one raw-path-unavailable outlier: `PAPER:我踏马来了USDT:1790664299999:LONG`
  - class: RIGHT_THEN_FAILURE
  - historical PnL: -$0.95
  - duration: ~12.7 seconds
- confirmation reference: original market-entry signal point
- confirmation levels: +0.10 / +0.20 / +0.30 / +0.35 / +0.40 / +0.50%
- fresh LONG entry: first archived aggTrade at/above confirmation threshold
- notional: $500
- fee: 0.05% per side
- slippage: 2 bps per side
- SL trigger: 0.30 / 0.40 / 0.50% below the fresh filled entry price
- if SL is not hit: close on the last archived aggTrade at/before the original historical close timestamp
- raw source: Binance USD-M daily aggTrades

## Entry-selection effect

| Confirmation | Entries | Entry rate | WD admitted | WD leakage | Stall admitted | RTF admitted | Recovered | Clean | Original-winner retention | Winner-class purity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +0.10% | 912 | 73.85% | 302 | 54.41% | 65 | 243 | 228 | 74 | 100.00% | 33.11% |
| +0.20% | 758 | 61.38% | 173 | 31.17% | 57 | 226 | 228 | 74 | 100.00% | 39.84% |
| +0.30% | 621 | 50.28% | 64 | 11.53% | 49 | 211 | 228 | 69 | 98.34% | 47.83% |
| +0.35% | 567 | 45.91% | 21 | 3.78% | 45 | 204 | 228 | 69 | 98.34% | 52.38% |
| +0.40% | 539 | 43.64% | 7 | 1.26% | 35 | 201 | 228 | 68 | 98.01% | 54.92% |
| +0.50% | 491 | 39.76% | **1** | **0.18%** | **3** | 194 | 228 | 65 | 97.02% | **59.67%** |

The confirmation gate is therefore highly effective at removing TRUE_WRONG_DIRECTION and STALL, especially from +0.35% upward.

However RIGHT_THEN_FAILURE remains structurally eligible because these trades did prove the original LONG direction before later failing.

## Economic grid

| Confirm | SL | Entries | Fresh WR | Net PnL | PF | SL hits |
|---:|---:|---:|---:|---:|---:|---:|
| +0.10% | 0.30% | 912 | 19.52% | -$791.59 | 0.43 | 573 |
| +0.10% | 0.40% | 912 | 22.59% | -$709.92 | 0.53 | 473 |
| +0.10% | 0.50% | 912 | 25.55% | -$723.98 | 0.54 | 389 |
| +0.20% | 0.30% | 758 | 20.32% | -$645.40 | 0.44 | 470 |
| +0.20% | 0.40% | 758 | 24.01% | -$623.66 | 0.50 | 389 |
| +0.20% | 0.50% | 758 | 25.99% | -$583.88 | 0.56 | 313 |
| +0.30% | 0.30% | 621 | 19.65% | -$598.93 | 0.40 | 415 |
| +0.30% | 0.40% | 621 | 25.12% | -$466.18 | 0.55 | 314 |
| +0.30% | 0.50% | 621 | **27.05%** | -$493.06 | 0.55 | 252 |
| +0.35% | 0.30% | 567 | 19.93% | -$534.36 | 0.40 | 375 |
| +0.35% | 0.40% | 567 | 24.87% | **-$393.46** | 0.58 | 287 |
| +0.35% | 0.50% | 567 | 26.28% | -$413.52 | 0.58 | 222 |
| +0.40% | 0.30% | 539 | 17.81% | -$524.33 | 0.39 | 364 |
| +0.40% | 0.40% | 539 | 21.15% | -$479.26 | 0.49 | 290 |
| +0.40% | 0.50% | 539 | 25.05% | **-$392.78** | **0.59** | 208 |
| +0.50% | 0.30% | 491 | 16.50% | -$422.38 | 0.47 | 337 |
| +0.50% | 0.40% | 491 | 19.14% | -$479.19 | 0.45 | 280 |
| +0.50% | 0.50% | 491 | 21.59% | -$428.39 | 0.53 | 205 |

Best fresh-entry WR in this grid:
- confirmation **+0.30%**
- SL **0.50%**
- WR **27.05%**
- PnL **-$493.06**

Best net PnL in this grid:
- confirmation **+0.40%**
- SL **0.50%**
- PnL **-$392.78**
- WR **25.05%**
- PF **0.59**

No tested LC-1 cell is profitable.

## Why confirmation works on WD but still fails economically

At +0.40% confirmation:
- WD falls to **7 / 555**
- Stall falls to **35 / 73**
- original winner retention remains **296 / 302 = 98.01%**
- but RIGHT_THEN_FAILURE still admits **201 / 306**

With +0.40% confirmation and 0.50% SL:
- Correct Runner: 68 entries, 36 fresh winners, +$97.69
- Recovered Drawdown: 228 entries, 97 fresh winners, +$176.52
- RIGHT_THEN_FAILURE: 201 entries, only 2 fresh winners, **-$536.26**
- Stall: 35 entries, 0 winners, -$108.53
- TRUE_WRONG_DIRECTION: 7 entries, 0 winners, -$22.20

The dominant residual failure is therefore no longer wrong-direction leakage. It is RIGHT_THEN_FAILURE.

A second issue is entry-chasing. Many historical Recovered Winners are profitable from the original entry, but after waiting for +0.30 to +0.50% confirmation and entering at the higher price, a tight 0.30 to 0.50% SL catches their normal pullback before recovery.

## LC-1 conclusion

Simple price confirmation is **excellent as a direction-validation gate**, but poor as a complete entry rule.

It should not be used as:

`signal -> +X% -> immediate market entry -> tight SL`

Instead the evidence supports a two-stage entry architecture:

1. **prove direction** around +0.35 to +0.50% to eliminate WD/STALL;
2. **do not chase the confirmation print**;
3. after confirmation, wait for a pullback/retest or a second persistence condition before fresh LONG entry;
4. separately discriminate RIGHT_THEN_FAILURE from real winners.

The next research problem is therefore **post-confirmation entry timing + RTF rejection**, not a higher confirmation threshold.
