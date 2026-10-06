# LQ-2 — LONG Location Anatomy: MFE vs Structural Liquidity

Status: **PASS / ANATOMY COMPLETE**

Version: `lq2-long-location-anatomy-v1`

## Research questions

1. Is low LONG MFE primarily explained by entry-to-supply distance?
2. Is entering inside / near demand materially better than entering inside supply?
3. Does zone timeframe or state provide a stronger discriminator than raw distance?
4. Which location feature is stable enough to advance to LQ-3?

Universe is the exact frozen **1,236 resolved LONG trades** used by LQ-1.

No production threshold was optimized or activated.

## Executive result

The simple hypothesis:

> "smaller distance to supply -> smaller MFE"

is **not supported as a standalone rule**.

Spearman correlations:

| Feature | n | Spearman rho vs MFE |
|---|---:|---:|
| Nearest supply distance | 1,176 | **+0.0287** |
| 5m supply distance | 1,012 | **+0.0511** |
| 15m supply distance | 1,115 | **+0.0144** |
| 1h supply distance | 1,146 | **-0.0085** |
| Nearest demand distance | 1,234 | **+0.1412** |

Therefore, raw headroom distance alone is too weak.

However, **zone state + timeframe matters**.

The strongest causal anatomy discovered in LQ-2 is:

> **LONG entry inside a FRESH 15m supply zone**

This condition is materially more concentrated in low-MFE trades and stays directionally stable across chronological TRAIN / VALIDATION / RESERVE.

## MFE bucket anatomy

| MFE bucket | n | Median supply distance | Inside any supply | Inside fresh 15m supply | Median demand distance |
|---|---:|---:|---:|---:|---:|
| <0.30% | 478 | 0.0307% | 46.23% | **11.51%** | 1.8987% |
| 0.30–0.50% | 150 | 0.0000% | 48.00% | **8.67%** | 1.8771% |
| 0.50–1.00% | 283 | 0.0527% | 43.46% | **6.01%** | 2.0555% |
| 1.00–2.00% | 226 | 0.0889% | 43.81% | **5.31%** | 2.2487% |
| >=2.00% | 99 | 0.0704% | 42.42% | **5.05%** | 2.5909% |

Important distinction:

- **inside any supply** barely changes across MFE buckets
- **inside fresh 15m supply** declines almost monotonically as MFE improves

That is the first useful structural-liquidity signal.

## Raw nearest-supply distance is weak

| Entry -> nearest supply | n | Median MFE | MFE <0.5% | MFE >=1% | Realized win |
|---|---:|---:|---:|---:|---:|
| Inside supply | 557 | 0.4009% | 52.60% | 25.31% | 23.88% |
| 0–0.20% | 138 | 0.3611% | 55.07% | 25.36% | 23.91% |
| 0.20–0.40% | 92 | 0.5096% | 48.91% | 25.00% | 26.09% |
| 0.40–0.70% | 126 | 0.5621% | 46.03% | 26.98% | 22.22% |
| 0.70–1.00% | 56 | 0.4281% | 51.79% | 26.79% | 28.57% |
| >1.00% | 207 | 0.5228% | 48.79% | 28.02% | 27.05% |

There is no monotonic gradient strong enough to justify a rule such as:

> `distance_to_supply < X => block LONG`

That rule would overfit.

## Timeframe matters

### 5m supply

| Group | n | Median MFE | MFE <0.5% | MFE >=1% |
|---|---:|---:|---:|---:|
| Inside | 266 | 0.3385% | 55.26% | 23.31% |
| Outside | 746 | 0.4573% | 50.94% | 25.74% |

### 15m supply

| Group | n | Median MFE | MFE <0.5% | MFE >=1% |
|---|---:|---:|---:|---:|
| Inside | 310 | **0.3590%** | **56.45%** | 24.52% |
| Outside | 805 | **0.5016%** | **49.81%** | 26.21% |

### 1h supply

| Group | n | Median MFE | MFE <0.5% | MFE >=1% |
|---|---:|---:|---:|---:|
| Inside | 360 | 0.4970% | 50.00% | 27.22% |
| Outside | 786 | 0.4271% | 52.04% | 24.81% |

So a generic multi-timeframe `inside_supply` flag is conceptually wrong.

The clearest adverse location is local/intermediate **15m supply**, not 1h supply.

## Strongest candidate: inside FRESH 15m supply

Full universe:

| Group | n | Median MFE | MFE <0.5% | MFE >=1% | Realized win |
|---|---:|---:|---:|---:|---:|
| **Inside fresh 15m supply** | **102** | **0.2536%** | **66.67%** | **16.67%** | **18.63%** |
| Complement | 1,134 | 0.5056% | 49.38% | 27.16% | 25.13% |

Effect versus complement:

- low-MFE rate: **+17.29 percentage points**
- >=1% runner rate: **-10.49 points**
- realized win rate: **-6.50 points**
- median MFE approximately halved

Class composition of the 102 flagged trades:

| Outcome | Count |
|---|---:|
| TRUE_WRONG_DIRECTION | **58** |
| STALL_NO_EDGE | **10** |
| RIGHT_THEN_FAILURE | 15 |
| RECOVERED_DRAWDOWN | 16 |
| CORRECT_RUNNER | **3** |

Thus 68 / 102 are the low-MFE WD + STALL family.

It is **not yet clean enough for an unconditional production BLOCK**, because 19 genuine winners are also present.

## Chronological stability

| Split | n flagged | Median MFE | MFE <0.5% | MFE >=1% | Win rate |
|---|---:|---:|---:|---:|---:|
| TRAIN | 58 | 0.2391% | 62.07% | 22.41% | 22.41% |
| VALIDATION | 22 | 0.2713% | **72.73%** | 18.18% | 18.18% |
| RESERVE | 22 | 0.2536% | **72.73%** | **0.00%** | **9.09%** |

Complement low-MFE rates:

- TRAIN: 47.00%
- VALIDATION: 52.89%
- RESERVE: 53.10%

The adverse effect is directionally stable in all three chronological partitions.

This is materially stronger than raw supply distance.

## Outcome-class location anatomy

| Class | n | Median supply distance | Inside any supply | Inside fresh 15m supply | Median demand distance |
|---|---:|---:|---:|---:|---:|
| TRUE_WRONG_DIRECTION | 555 | 0.0095% | 47.57% | **10.45%** | 1.9044% |
| STALL_NO_EDGE | 73 | 0.1105% | 39.73% | **13.70%** | 1.8590% |
| RIGHT_THEN_FAILURE | 306 | 0.0566% | 42.81% | 4.90% | 2.3486% |
| RECOVERED_DRAWDOWN | 228 | 0.0991% | 42.98% | 7.02% | 1.9541% |
| CORRECT_RUNNER | 74 | 0.0219% | 47.30% | **4.05%** | 2.3039% |

Again, ordinary supply distance does not separate classes well.

Fresh 15m supply is roughly:

- 10.45% of TRUE_WRONG_DIRECTION
- 13.70% of STALL
- only 4.05% of CORRECT_RUNNER

This makes it a plausible adverse context feature for LQ-3.

## Is demand better than supply?

### Strict inside-zone comparison

| Location | n | Median MFE | MFE <0.5% | MFE >=1% | Win rate |
|---|---:|---:|---:|---:|---:|
| Supply only | **551** | 0.4009% | 52.63% | 25.41% | 23.77% |
| Demand only | **17** | 0.5717% | 47.06% | 23.53% | 23.53% |
| Both | 6 | 0.4841% | 50.00% | 16.67% | 33.33% |
| Neither | 662 | 0.5072% | 49.40% | 27.19% | 25.23% |

Demand-only has a higher median MFE than supply-only, but:

- only **17 trades**
- >=1% rate is not better
- win rate is essentially identical
- total PnL remains negative

Therefore:

> **LQ-2 does not support the claim that entering in demand is automatically better than entering in supply.**

A relaxed "near demand with supply not close" definition also remains too sparse:

- demand <=0.5%
- supply >0.25%
- n = **19**
- median MFE = 0.4159%
- >=1% = 36.84%
- win = 36.84%

This is interesting but far too small to freeze as a rule.

Also, nearest-demand distance has a weak **positive** correlation with MFE (+0.1412), meaning stronger runners are often *farther* from old demand. That is consistent with momentum / breakout trades moving away from prior support.

Demand therefore should be treated as **context / downside support**, not as a universal LONG entry requirement.

## LQ-2 conclusion

### Rejected

Do **not** build:

`LONG blocked if nearest supply distance < X%`

and do **not** assume:

`inside demand = good LONG`

Both are too simplistic.

### Supported for LQ-3

The useful structural feature is:

`inside FRESH 15m supply`

It is:

- causal
- interpretable
- materially enriched in low-MFE trades
- stable across chronological partitions
- substantially rarer in CORRECT_RUNNER than in WD / STALL

But its precision is still insufficient for direct production blocking.

## Next research question

LQ-3 should determine whether the 34 non-low-MFE trades inside fresh 15m supply can be separated using:

- supply departure strength
- zone width
- touch / freshness geometry
- 5m acceptance or rejection around the 15m supply
- Stage11C microstructure / taker flow
- breakout acceptance vs rejection

Target:

> preserve the adverse 68 WD/STALL examples while recovering as many as possible of the 19 genuine winners and useful RTF continuation opportunities.

No production order authority is changed by LQ-2.