# Stage 3C.7A — Full 454 Archive-5s Exit Replay

Status: **authoritative strategy replay for the frozen 454 LONG OPEN cohort under the archive-5s contract**.

This result supersedes earlier mixed-quality 454 proxy tables, including PP4.2 coverage-limited +$94.77 and PP4.2 15s+1m reconstructed +$80.69. Those figures must not be used as final strategy results.

## Replay contract
- Universe: 454 Stage 3C.7A LONG OPEN trades.
- Market path: Binance USD-M daily aggTrades historical archive.
- Coverage: 454/454; 301 required symbol-date archive files available.
- Sampling for PP4.2: first sample entry+5s, then every 5s; latest aggregate-trade price at/before boundary; carry-forward if no new trade.
- Strategy replacement: full initial position; no historical exit actions inherited.
- Historical final close price is fallback only if tested strategy has not closed by original close time.
- Fees/slippage: stored paper-trading configuration.
- Two trades closed before the first 5s sample; PP4.2 could not act and used fallback close.

## Final results

| Strategy | OPEN | WIN | WR | PnL |
|---|---:|---:|---:|---:|
| Historical actual | 454 | 176 | 38.77% | +$62.53 |
| PP4.2 Hybrid archive-5s replay | 454 | 177 | 38.99% | **-$25.69** |
| SL -1% / TP +1% | 454 | 177 | 38.99% | +$53.61 |
| SL -1% / TP +1% / BE +0.15% permanent | 454 | 20 | 4.41% | -$150.76 |
| SL -1% / TP +1% / BE +0.18% permanent | 454 | 368 | 81.06% | -$120.81 |
| SL -1% / TP +1% / BE +0.18% only before +0.5% | 454 | 357 | 78.63% | -$103.49 |

## Strong-target / non-target anatomy

| Strategy | Strong target PnL (150) | Strong-target WR | Non-target PnL (304) | Non-target WR |
|---|---:|---:|---:|---:|
| Historical actual | +$560.28 | 91.33% | -$497.75 | 12.83% |
| PP4.2 Hybrid | +$489.78 | 87.33% | -$515.46 | 15.13% |
| SL -1% / TP +1% | +$567.42 | 95.33% | -$513.81 | 11.18% |
| BE +0.18% only before +0.5% | +$84.22 | 97.33% | -$187.71 | 69.41% |

## Interpretation
1. PP4.2 is not optimal on this frozen cohort: historical +$62.53 becomes -$25.69.
2. Static SL -1% / TP +1% is the best tested replacement by total PnL but still trails historical: +$53.61 vs +$62.53.
3. The +0.18% BE rules raise WR sharply but destroy dollar PnL by cutting strong runners too early.
4. High WR is not equivalent to high profitability.
5. Earlier mixed-resolution proxy figures are exploratory only and are superseded by this result.

PP4.2 action counts: 190 small reductions; 68 runner closes.
