# LP-1A — Full LONG 1,236 Loss Anatomy

Status: **PASS — discovery anatomy frozen**.

This stage mirrors the LONG profit-detector discovery process by starting from the full resolved LONG universe, not only the current 454 OPEN policy cohort.

## Universe

- Total resolved LONG: **1,236**
- Historical realized-positive: **304**, gross +$961.26
- Historical realized non-positive: **932**, gross -$2,255.46
- Net full-universe historical PnL: **-$1,294.20**
- META_WIN source rows: 401
- META_LOSS source rows: 835
- Protector target for LP discovery is **actual realized non-positive**, not META_LOSS labels.

META label cross-check:
- META_WIN: 256 realized-positive, 145 realized non-positive
- META_LOSS: 48 realized-positive, 787 realized non-positive

Therefore META_WIN/META_LOSS must not be treated as direct profit/loss outcomes for protector research.

## Primary loss anatomy

Using the frozen outcome/path labels already present in the 1,236-row discovery dataset:

| Path | Actual non-positive N | Loss PnL | Share of gross loss $ | Median MFE | Median MAE | Median duration |
|---|---:|---:|---:|---:|---:|---:|
| TRUE_WRONG_DIRECTION / WRONG_DIRECTION | 555 | **-$1,543.49** | **68.43%** | +0.183% | -0.919% | 3.97m |
| STALL non-positive | 71 | **-$340.36** | **15.09%** | +0.406% | -1.296% | 32.10m |
| RIGHT_THEN_FAILURE / MISSED_OPPORTUNITY | 306 | **-$371.61** | **16.48%** | +0.714% | -1.022% | 3.78m |
| **TOTAL** | **932** | **-$2,255.46** | **100%** | — | — | — |

Important: STALL contains 73 total trades; 71 are non-positive and 2 are small realized-positive controls.

## Favorable-excursion loss map

| Historical max MFE | Total trades | Realized + | Realized non-positive | Non-positive loss PnL | Share of all loss $ |
|---|---:|---:|---:|---:|---:|
| <= 0% | 22 | 0 | 22 | -$68.54 | 3.04% |
| >0 to <0.18% | 251 | 0 | 251 | -$715.84 | 31.74% |
| 0.18% to <0.50% | 355 | 2 | 353 | **-$1,099.46** | **48.75%** |
| 0.50% to <1.00% | 283 | 43 | 240 | -$267.63 | 11.87% |
| >=1.00% | 325 | 259 | 66 | -$103.99 | 4.61% |

Combined **MFE < +0.50%**:
- 628 total trades
- 626 realized non-positive
- only 2 realized-positive
- net PnL **-$1,883.45**
- non-positive loss PnL **-$1,883.85**
- represents **83.52% of all gross loss dollars**

This is hindsight anatomy only. Eventual max MFE is not a causal production feature.

## Existing frozen path controls

| Path style | N | Realized + | PnL | Median MFE | Median MAE | Median duration |
|---|---:|---:|---:|---:|---:|---:|
| WRONG_DIRECTION | 555 | 0 | -$1,543.49 | +0.183% | -0.919% | 3.97m |
| STALL | 73 | 2 | -$339.96 | +0.405% | -1.296% | 31.06m |
| MISSED_OPPORTUNITY | 306 | 0 | -$371.61 | +0.714% | -1.022% | 3.78m |
| RECOVERED_WINNER | 228 | 228 | +$727.30 | +1.468% | -0.922% | 19.14m |
| CLEAN_WINNER | 74 | 74 | +$233.55 | +1.575% | -0.346% | 13.65m |

Critical winner-harm guardrail:
- Valid winners = 302
- **228 / 302 = 75.50% are RECOVERED_WINNER**
- They contribute about **75.69% of valid-winner PnL**
- Therefore an early-drawdown-only stop rule is structurally dangerous.

## Composite anatomy

| Composite archetype | N | PnL |
|---|---:|---:|
| NO_EDGE_NONWIN | 555 | -$1,543.49 |
| BORDERLINE_NONWIN | 71 | -$340.36 |
| SMALL_EDGE_FAILED | 240 | -$267.63 |
| RUNNER_MISSED | 56 | -$70.31 |
| BIG_RUNNER_MISSED | 10 | -$33.67 |
| NO_EDGE_WIN | 2 | +$0.40 |
| SMALL_EDGE_WIN | 43 | +$14.75 |
| RUNNER_RECOVERED | 134 | +$226.41 |
| RUNNER_CLEAN | 36 | +$62.27 |
| BIG_RUNNER_RECOVERED | 64 | +$493.53 |
| BIG_RUNNER_CLEAN | 25 | +$163.89 |

## LP-1A conclusions

1. The dominant problem is **pre-0.50% failure**, not runner giveback.
2. MFE <0.50% accounts for **83.52% of gross loss dollars**.
3. The single largest candidate lane is the **0.18%–0.50% sub-0.5 zone**: 353 non-positive trades and -$1,099.46 loss.
4. The BE idea is therefore economically relevant, but it cannot be armed merely because price touches +0.18%; many future runners pass through the same region.
5. TRUE_WRONG_DIRECTION is the largest loss class by dollars: 555 trades, -$1,543.49.
6. RIGHT_THEN_FAILURE is secondary by dollars: 306 trades, -$371.61.
7. Winner preservation is a hard constraint because 75.5% of valid winners are recovered winners rather than clean winners.

## Next stage: LP-1B Temporal Loss Anatomy

LP-1B must answer causally, before future MFE is known:
- What separates TRUE_WRONG_DIRECTION from future recovered winners?
- What separates eventual sub-0.5 stalls from trades merely passing through +0.18%–+0.50% on the way to a runner?
- When does that separation first become reliable?
- After +0.50%, what distinguishes RIGHT_THEN_FAILURE from valid runners?

No production protector rule is frozen in LP-1A.
