# RD-0B — Exact 555 Wrong-Direction Reverse TP/SL Grid

Status: **PASS — exact raw-path research replay completed on core-prod, 2026-10-06**

Authority: research only. No production detector, execution, Health, or profit-protection authority changed.

## Frozen contract

- universe: **555 resolved LONG `TRUE_WRONG_DIRECTION` trades**
- historical PnL: **-$1,543.4890**
- original average PnL: **-$2.7811/trade**
- reverse side: **SHORT**
- entry: same original market-entry point
- notional: **$500**
- fee: **0.05% per side**
- slippage: **2 bps per side**
- path: Binance USD-M archived **aggTrades**
- ordering: true aggregate-trade first touch
- holding window: original `opened_at_ms -> closed_at_ms`
- if neither TP nor SL is hit: close at the last archived aggregate trade at/before the original historical close timestamp

Two threshold conventions were replayed:

1. **PRICE** — TP/SL percentages refer to market-price movement from the original entry point. Reported PnL is net of fee + slippage.
2. **NET** — TP/SL percentages refer directly to net PnL percentage after fee + slippage, matching the older WD-4 convention.

Archive coverage: **555 / 555**.  
Unique symbol-days: **394**.  
Archive fetch errors: **0**.

## PRICE TP/SL grid

| TP | SL | TP hits | SL hits | Hist-close fallback | Positive | WR | Net PnL | Avg/trade | PF |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.3% | 0.3% | 457 | 54 | 44 | 478 | 86.13% | +$279.54 | +$0.504 | 3.10 |
| 0.3% | 0.4% | 493 | 6 | 56 | 517 | 93.15% | +$410.69 | +$0.740 | 13.12 |
| 0.3% | 0.5% | 498 | 1 | 56 | 522 | **94.05%** | +$428.58 | +$0.772 | 21.82 |
| 0.4% | 0.3% | 358 | 59 | 138 | 460 | 82.88% | +$424.64 | +$0.765 | 3.82 |
| 0.4% | 0.4% | 392 | 7 | 156 | 501 | 90.27% | +$580.82 | +$1.047 | 14.16 |
| 0.4% | 0.5% | 398 | 1 | 156 | 507 | 91.35% | +$604.98 | +$1.090 | 22.54 |
| 0.5% | 0.3% | 209 | 62 | 284 | 452 | 81.44% | +$469.82 | +$0.847 | 3.93 |
| 0.5% | 0.4% | 227 | 7 | 321 | 494 | 89.01% | +$638.09 | +$1.150 | 13.82 |
| 0.5% | 0.5% | 232 | 1 | 322 | 500 | 90.09% | +$664.54 | +$1.197 | 20.69 |
| 0.6% | 0.3% | 108 | 63 | 384 | 449 | 80.90% | +$471.91 | +$0.850 | 3.88 |
| 0.6% | 0.4% | 121 | 7 | 427 | 492 | 88.65% | +$647.25 | +$1.166 | 13.74 |
| 0.6% | 0.5% | 126 | 1 | 428 | 498 | 89.73% | +$676.20 | +$1.218 | 20.46 |
| 0.7% | 0.3% | 68 | 63 | 424 | 448 | 80.72% | +$484.79 | +$0.874 | 3.96 |
| 0.7% | 0.4% | 76 | 7 | 472 | 491 | 88.47% | +$661.77 | +$1.192 | 13.99 |
| **0.7%** | **0.5%** | **78** | **1** | **476** | **497** | **89.55%** | **+$691.46** | **+$1.246** | **20.80** |
| 0.8% | 0.3% | 44 | 64 | 447 | 446 | 80.36% | +$486.27 | +$0.876 | 3.92 |
| 0.8% | 0.4% | 47 | 7 | 501 | 489 | 88.11% | +$659.10 | +$1.188 | 13.76 |
| 0.8% | 0.5% | 48 | 1 | 506 | 495 | 89.19% | +$689.16 | +$1.242 | 20.35 |

### PRICE finding

Every tested PRICE grid cell is positive.

Best tested net PnL:
- **TP 0.7% / SL 0.5%**
- net **+$691.46**
- positive trades **497 / 555**
- WR **89.55%**
- PF **20.80**

Highest WR:
- **TP 0.3% / SL 0.5%**
- WR **94.05%**
- net **+$428.58**
- TP hits **498**
- SL hits **1**

The highest-PnL cells use a higher TP and therefore allow many trades to reach the original historical close instead of cashing out at a small TP. This shows that the direction inversion itself carries substantial value; the TP is not the sole source of profitability.

## NET TP/SL grid

| TP net | SL net | TP hits | SL hits | Hist-close fallback | Positive | WR | Net PnL | Avg/trade | PF |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.3% | 0.3% | 213 | 208 | 134 | 326 | 58.74% | +$104.69 | +$0.189 | 1.31 |
| 0.3% | 0.4% | 270 | 99 | 186 | 422 | 76.04% | +$349.13 | +$0.629 | 2.59 |
| 0.3% | 0.5% | 313 | 15 | 227 | 492 | 88.65% | +$594.10 | +$1.070 | 10.50 |
| 0.4% | 0.3% | 118 | 213 | 224 | 319 | 57.48% | +$115.95 | +$0.209 | 1.33 |
| 0.4% | 0.4% | 150 | 102 | 303 | 415 | 74.77% | +$362.10 | +$0.652 | 2.58 |
| 0.4% | 0.5% | 173 | 15 | 367 | 486 | 87.57% | +$616.13 | +$1.110 | 10.10 |
| 0.5% | 0.3% | 69 | 216 | 270 | 316 | 56.94% | +$107.52 | +$0.194 | 1.31 |
| 0.5% | 0.4% | 86 | 103 | 366 | 414 | 74.59% | +$361.98 | +$0.652 | 2.57 |
| 0.5% | 0.5% | 99 | 15 | 441 | 486 | 87.57% | +$621.23 | +$1.119 | 10.18 |
| 0.6% | 0.3% | 43 | 216 | 296 | 315 | 56.76% | +$118.98 | +$0.214 | 1.34 |
| 0.6% | 0.4% | 55 | 103 | 397 | 413 | 74.41% | +$376.82 | +$0.679 | 2.63 |
| **0.6%** | **0.5%** | **60** | **15** | **480** | **485** | **87.39%** | **+$634.31** | **+$1.143** | **10.35** |
| 0.7% | 0.3% | 30 | 217 | 308 | 313 | 56.40% | +$116.32 | +$0.210 | 1.33 |
| 0.7% | 0.4% | 36 | 104 | 415 | 411 | 74.05% | +$373.38 | +$0.673 | 2.60 |
| 0.7% | 0.5% | 40 | 15 | 500 | 483 | 87.03% | +$632.10 | +$1.139 | 10.22 |
| 0.8% | 0.3% | 19 | 217 | 319 | 312 | 56.22% | +$111.88 | +$0.202 | 1.32 |
| 0.8% | 0.4% | 23 | 104 | 428 | 410 | 73.87% | +$367.51 | +$0.662 | 2.57 |
| 0.8% | 0.5% | 26 | 15 | 514 | 482 | 86.85% | +$626.68 | +$1.129 | 10.09 |

Best NET-threshold cell:
- **TP +0.6% net / SL -0.5% net**
- **+$634.31**
- WR **87.39%**
- PF **10.35**

## Diagnostic observation

Raw aggTrades do not reproduce the observed WD taxonomy as a perfect 555/555 `TP0.3-before-SL0.4/0.5` identity:

- PRICE TP0.3 / SL0.4: TP first **493**, SL first **6**, fallback **56**
- PRICE TP0.3 / SL0.5: TP first **498**, SL first **1**, fallback **56**

This is not a grid failure. It demonstrates that `TRUE_WRONG_DIRECTION` is based on the lifecycle's observed/evaluated MFE/MAE path, while raw aggTrades contain higher-frequency and boundary movement that the stored evaluation path does not perfectly reproduce.

The critical result remains: once the exact 555 WD cohort is isolated and actually reversed at the same entry/lifetime, **all tested TP/SL PRICE combinations are economically positive after corrected Binance fee and modeled slippage**.

## RD-0B conclusion

The earlier blanket-reversal losses were not evidence that the 555 wrong-direction trades remain bad when reversed.

They were produced by a different replay contract / contaminated universe / changed lifecycle.

For the exact current 555 LONG `TRUE_WRONG_DIRECTION` cohort:

> **wrong original direction contains a strong opposite-side economic edge.**

The next research problem is therefore **selection**: identify these WD trades causally before outcome is known, while excluding recovered winners and right-then-failure trades.
