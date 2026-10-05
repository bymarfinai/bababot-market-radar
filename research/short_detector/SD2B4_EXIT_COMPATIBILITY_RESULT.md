# SD-2B4 — SHORT Delayed-Entry Exit Compatibility

Status: **PARTIAL PASS — exit compatibility confirmed, profitability not achieved**

## Frozen entry rule

Lane 1 only:

`T+3 confirm_side_return_pct >= +0.0338983050847%`

This is the SD-2B2 STRONG research candidate.

Frozen selected cohort:
- Discovery: 76 selected / 23 strong WIN
- Validation: 22 / 11
- Reserve: 30 / 5
- Total: **128 selected / 39 strong WIN**

No entry threshold or lane definition was retuned.

## Execution reconstruction

Execution proxy:
- decision at frozen T+3 target
- entry = open of first complete Binance USD-M 1m bar strictly after T+3
- SHORT entry with historical paper fee/slippage settings
- $500 initial notional
- fee rate 0.075%
- slippage 2 bps
- intratrade market path from Binance USD-M daily aggTrades
- protector sampling every 5 seconds
- replay ends at the frozen historical close timestamp

Coverage:
- kline symbol-date pairs: **115**
- aggTrade symbol-date pairs: **103**
- kline errors: **0**
- aggTrade errors: **0**

This is a print-based historical execution proxy, not historical order-book fill proof.

## Delayed-entry feasibility

From 128 selected trades:

- executable delayed entries: **112**
- no executable entry: **16**

No-executable:
- Discovery: 9
- Validation: 3
- Reserve: 4

Only **2 / 16** no-executable trades were strong WINs:
- Discovery: 1
- Validation: 1
- Reserve: 0

Therefore waiting until T+3 naturally removes:
- **14 non-targets**
- only **2 strong winners**

Executable cohort:
- **37 strong WIN**
- **75 non-target**

## Post-entry opportunity

### Strong winners

Across 37 executable strong winners:

- median delayed MFE: **+1.107%**
- mean delayed MFE: **+1.208%**
- median delayed MAE: **-0.176%**
- delayed MFE >=0.5%: **35 / 37 = 94.6%**
- delayed MFE >=1.0%: **21 / 37 = 56.8%**

### Non-targets

Across 75 executable non-targets:

- median delayed MFE: **+0.092%**
- mean delayed MFE: **+0.163%**
- median delayed MAE: **-0.611%**
- delayed MFE >=0.5%: **6 / 75 = 8.0%**
- delayed MFE >=1.0%: **0 / 75**

This is the strongest execution-level separation in SD-2B4:

> **No executable non-target reached +1% delayed MFE, while 21 strong winners did.**

## Reserve delayed opportunity

Reserve executable:
- 5 strong winners
- 21 non-targets

Strong winners:
- median delayed MFE: **+0.878%**
- all **5 / 5** retained >=0.5%
- only **1 / 5** retained >=1.0%
- median MAE: **-0.110%**

Non-targets:
- median MFE: **+0.112%**
- 2 / 21 reached >=0.5%
- **0 / 21** reached >=1.0%
- median MAE: **-0.513%**

Waiting until T+3 therefore retains meaningful but smaller Reserve winner opportunity.

---

# Frozen exit-policy comparison

Policies were frozen before replay:

1. DELAYED_HIST_CLOSE
2. SL1_TP1
3. V42_HYBRID
4. archived V43_SHORT_LS4 near-miss

## Full executable cohort — 112 trades

| Exit | Wins | WR | PnL | Delta vs delayed baseline |
|---|---:|---:|---:|---:|
| DELAYED_HIST_CLOSE | 26 | 23.21% | **-$249.96** | — |
| SL1_TP1 | 26 | 23.21% | **-$201.61** | **+$48.35** |
| V42_HYBRID | 27 | 24.11% | **-$222.40** | **+$27.56** |
| **V43_SHORT_LS4** | **38** | **33.93%** | **-$196.59** | **+$53.37** |

All three tested protectors improve aggregate PnL relative to holding until the historical close.

The best total-dollar result is:

> **V43_SHORT_LS4: +$53.37 improvement**

But absolute PnL remains negative.

---

# Validation

19 executable trades:
- 10 strong WIN
- 9 non-target

| Exit | Wins | PnL |
|---|---:|---:|
| DELAYED_HIST_CLOSE | 7 | -$19.46 |
| SL1_TP1 | 7 | **-$4.83** |
| V42_HYBRID | 7 | -$7.24 |
| V43_SHORT_LS4 | **9** | -$6.83 |

V43 improves:
- PnL by **+$12.63**
- wins from 7 to **9**

SL1_TP1 has the best Validation dollar result.

---

# Reserve

26 executable trades:
- 5 strong WIN
- 21 non-target

| Exit | Wins | PnL |
|---|---:|---:|
| DELAYED_HIST_CLOSE | 3 | -$69.14 |
| SL1_TP1 | 3 | -$63.87 |
| V42_HYBRID | 4 | -$67.46 |
| **V43_SHORT_LS4** | **6** | **-$59.27** |

V43 improves Reserve:
- PnL by **+$9.87**
- wins from 3 to **6**

It still does not make Reserve profitable.

---

# Strong-WIN economics

Across the 37 executable strong winners:

| Exit | Positive trades | PnL |
|---|---:|---:|
| DELAYED_HIST_CLOSE | 26 / 37 | +$25.91 |
| **SL1_TP1** | 26 / 37 | **+$71.37** |
| V42_HYBRID | 27 / 37 | +$49.03 |
| V43_SHORT_LS4 | **34 / 37** | +$60.15 |

Two different strengths emerge:

### SL1_TP1
Best strong-winner dollar conversion:
- +$71.37
- winner retention median: **53.72%**

### V43_SHORT_LS4
Best winner conversion rate:
- **34 / 37 = 91.9%** positive
- +$60.15

But V43 median winner retention remains only about:

> **26.2% of delayed MFE**

Therefore the old V4.3-LS4 retained-peak problem remains unresolved.

It is still **not** a 75–80% peak-retention solution.

---

# Non-target economics

This is now the dominant problem.

Across 75 executable non-targets:

| Exit | PnL |
|---|---:|
| DELAYED_HIST_CLOSE | **-$275.87** |
| SL1_TP1 | -$272.98 |
| V42_HYBRID | -$271.43 |
| V43_SHORT_LS4 | **-$256.74** |

Even the best existing exit still loses:

> **-$256.74 on non-targets**

Compare this with V43 strong-winner profit:

> **+$60.15**

So the selected cohort remains negative not because the true winners cannot produce profit, but because the false-positive population is still too expensive.

---

# Compatibility verdict

Under the preregistered compatibility gates:

- **SL1_TP1 = COMPATIBLE**
- **V42_HYBRID = COMPATIBLE**
- **V43_SHORT_LS4 = COMPATIBLE**

All three:
- improve full-cohort PnL
- do not materially worsen Validation / Reserve gross loss
- preserve acceptable winner counts

Among existing frozen policies:

> **V43_SHORT_LS4 is the best overall compatibility benchmark by total PnL and winner conversion.**

But:

> **SL1_TP1 captures substantially more of strong-winner delayed MFE.**

No existing exit receives production authority.

---

# Core SD-2B4 conclusion

SD-2B4 answers the exit question:

> **Yes — existing SHORT exit protection is compatible with the new delayed T+3 entry lane.**

But it also shows that exit engineering is **not the main remaining bottleneck**.

The dominant economics are:

- strong winners, V43: **+$60.15**
- non-targets, V43: **-$256.74**
- net: **-$196.59**

Therefore further tuning V4.3 alone cannot solve the SHORT system.

The next research priority should target:

> **post-entry failure / loss protection for the T+3-confirmed SHORT lane**

rather than more profit-protector tuning.

Especially important:
- 75 non-targets have median delayed MFE only **+0.092%**
- median delayed MAE **-0.611%**
- **0 / 75** non-targets reach +1% MFE

while:
- 35 / 37 strong winners reach +0.5%
- 21 / 37 reach +1%

That is a strong basis for a causal post-entry failure detector / loss protector research stage.

## Final verdict

**SD-2B4 = PARTIAL PASS**

Pass:
- delayed T+3 entry retains meaningful winner opportunity
- existing exit policies improve results
- V43_SHORT_LS4 is transport-compatible
- Validation and Reserve both improve under V43

Fail / unresolved:
- absolute PnL remains negative
- false-positive losses dominate
- V43 still captures only ~26% median delayed MFE on positive strong winners
- no production promotion

No runtime or paper-trading behavior was changed.