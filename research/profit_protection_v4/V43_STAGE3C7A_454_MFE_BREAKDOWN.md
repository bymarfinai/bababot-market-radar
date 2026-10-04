# V4.3 LONG Transport Replay — Stage 3C.7A 454 Archive-5s

Status: **RESEARCH TRANSPORT REPLAY — promising, not production-authorized.**

## Correction

The earlier quick estimate that placed V4.3 at approximately +$31.14 on the 454 cohort was invalid because it added the LS3/LS4 improvement from a different 170-trade research cohort to the Stage 3C.7A 454 baseline.

This replay fixes that by applying the frozen V4.3 LONG LS3 parameters directly to the authoritative Stage 3C.7A 454 archive-5s paths.

## Universe and contract

- Universe: **454 Stage 3C.7A OPEN trades**
- Side: **LONG only**
- Market path: Binance USD-M daily aggTrades archive
- Sampling: entry+5s, then every 5s, latest aggregate trade at/before boundary with carry-forward
- Baseline check: V4.2 exactly reproduces the authoritative result
  - 177 WIN
  - 38.99% WR
  - **-$25.69**
- V4.3 replacement is applied only to trades that V4.2 classified as **REDUCE25-only**.
- V4.2 NO_ACTION, RUNNER_CLOSE, and REDUCE25+RUNNER_CLOSE paths remain unchanged.

V4.3 LONG LS3 transported parameters:
- small arm: **+0.50%**
- small retain: **97%**
- small confirmation: **1**
- reduce fraction: **100%**
- runner qualify: **+1.50%**
- runner retain: **90%**
- runner confirmation: **2**

## Overall result

| Strategy | WIN | WR | PnL |
|---|---:|---:|---:|
| Historical actual | 176 | 38.77% | +$62.53 |
| V4.2 archive-5s | 177 | 38.99% | -$25.69 |
| **V4.3 LONG transport** | **247** | **54.41%** | **+$200.48** |

- V4.3 delta vs V4.2: **+$226.17**
- V4.3 delta vs historical: **+$137.95**
- V4.3 replacement applied to **163 trades**
- V4.3 action counts:
  - HIST_TIME_FALLBACK: 223
  - V43_FULL_CLOSE: 163
  - RUNNER_CLOSE: 41
  - REDUCE25+RUNNER_CLOSE: 27

## MFE distribution

| MFE bucket | N | Historical PnL | V4.2 PnL | V4.3 PnL | V4.3 WR | V4.3 applied | Median V4.3 close |
|---|---:|---:|---:|---:|---:|---:|---:|
| <0.30% | 72 | -$175.83 | -$182.66 | -$178.66 | 2.78% | 1 | -0.498% |
| 0.30-<0.50% | 49 | -$185.47 | -$225.02 | -$225.02 | 2.04% | 0 | -0.650% |
| 0.50-<1.00% | 146 | -$116.18 | -$107.71 | **+$53.72** | **60.27%** | 82 | +0.196% |
| 1.00-<1.50% | 96 | +$61.40 | +$52.33 | **+$111.17** | **79.17%** | 72 | +0.312% |
| 1.50-<2.00% | 30 | +$43.98 | +$85.30 | +$87.21 | 83.33% | 8 | +0.669% |
| 2.00-<3.00% | 29 | +$79.35 | +$148.73 | +$148.73 | 86.21% | 0 | +1.185% |
| 3.00-<5.00% | 22 | +$150.36 | +$135.21 | +$135.21 | 95.45% | 0 | +1.286% |
| >=5.00% | 10 | +$204.93 | +$68.12 | +$68.12 | 90.00% | 0 | +1.054% |

The main V4.3 gain is concentrated in the **0.50-1.50% MFE** region.

## V4.3 full-close subset

The transported V4.3 rule closes 163 baseline REDUCE25-only trades.

- V4.3 WIN: **162 / 163**
- V4.3 subset PnL: **+$284.20**
- same trades historical PnL: **+$49.91**
- same trades V4.2 PnL: **+$58.04**
- V4.3 positive close: **162**
- non-positive close: **1**
- helped vs V4.2: **143**
- harmed vs V4.2: **20**
- helped vs historical: **137**
- harmed vs historical: **26**

MFE:
- median: **0.989%**
- 25th percentile: **0.735%**
- 75th percentile: **1.226%**

V4.3 close:
- median: **+0.328%**
- 25th percentile: **+0.286%**
- 75th percentile: **+0.404%**
- maximum: **+0.991%**

Retention vs historical MFE:
- median: **37.55%**
- 25th percentile: **26.41%**
- 75th percentile: **48.78%**

This means the transported V4.3 rule is profitable primarily because it converts many trades that historically gave back their +0.5%-1.5% MFE into small realized gains. It is **not** a high-retention protector.

## Important interpretation

The result is highly promising as an out-of-cohort transport replay, but it does **not** overturn the original LS3 status of NO_PASS for the 75-80% retention objective.

V4.3 here optimizes realized dollars / win conversion much better than V4.2, while still retaining only roughly 38% of MFE on the median transported trade.

Therefore:
- use this replay as a strong candidate baseline for further research;
- do not label it production-ready yet;
- next validation should focus on whether the +0.50%-1.50% MFE conversion remains stable on a fresh unseen cohort and whether the large-MFE runner lane can be improved without damaging the new gains.