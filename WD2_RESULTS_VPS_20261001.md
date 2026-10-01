# WD-2 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` PostgreSQL.  
Cohort: 2,175 frozen WD-1 trades.  
Authority: research only.

## Executive finding

The main finding is that TRUE_WRONG_DIRECTION and RECOVERED_DRAWDOWN are **only weakly separable at entry**, but become strongly separable during the first ~3 minutes after entry.

This means an aggressive static Stage 11C retune is not supported by WD-2. A tighter static entry filter risks rejecting many of the 385 recovered-drawdown winners. The strongest information appears in persistent post-entry adverse movement plus independent micro evidence.

## 1. Entry snapshot: true wrong vs recovered

The strongest numeric entry separation is weak:

| Feature | Wrong median | Recovered median | Separation |
|---|---:|---:|---:|
| return expansion ratio | 4.6506 | 4.3628 | 0.094 |
| Stage11C side-adjusted drift | ~0.000% | ~0.000% | 0.092 |
| side-adjusted 1h return | +1.525% | +1.757% | 0.082 |
| median abs 5m return | 0.171% | 0.181% | 0.068 |
| signal age | 31.6 s | 29.0 s | 0.056 |

The largest categorical gaps are also modest:

- signal taker BUY: 60.3% wrong vs 53.8% recovered
- BEAR regime: 31.0% vs 24.9%
- EXPANSION: 71.3% vs 66.5%
- IGNITION: 28.7% vs 33.5%
- BREAKOUT: 58.9% vs 54.8%

No single static entry feature cleanly separates wrong direction from a drawdown that later recovers.

## 2. Stage 11C family alignment is not sufficient

Every admitted trade already has PRICE_STRUCTURE=ALIGNED.

Yet full-cohort outcomes remain poor in several apparently acceptable family combinations.

Large examples:

| Entry segment | N | Wrong | Recovered | Correct runner |
|---|---:|---:|---:|---:|
| LONG + ALIGNED/ALIGNED/NEUTRAL/OPPOSITE | 119 | 51.3% | 13.4% | 6.7% |
| SHORT + ALIGNED/ALIGNED/NEUTRAL/ALIGNED | 113 | 50.4% | 16.8% | 0.9% |
| LONG + ALIGNED/ALIGNED/ALIGNED/NEUTRAL | 147 | 46.3% | 15.6% | 6.8% |
| LONG + ALIGNED/ALIGNED/NEUTRAL/NEUTRAL | 203 | 44.3% | 16.3% | 6.9% |

Overall:

- LONG wrong-direction rate: 41.8%
- SHORT: 34.1%
- LONG IGNITION: 43.5%
- LONG EXPANSION: 41.1%
- SHORT IGNITION: 29.9%
- SHORT EXPANSION: 35.7%

LONG is therefore a material leakage area, but stage alone is not enough to solve it.

## 3. Correct runners do not simply have “more alignment”

Compared with TRUE_WRONG_DIRECTION, CORRECT_RUNNER entry snapshots show some moderate differences:

- runner Stage11C side drift median: -0.060% vs ~0.000%
- runner side 1m return: +0.071% vs +0.144%
- runner gate taker share for the proposed side: 0.599 vs 0.664
- runner side 5m return: +0.902% vs +0.792%

Flow family ALIGNED appears in 76.0% of wrong-direction trades but only 62.6% of correct runners. Regime ALIGNED appears in 37.7% of wrong trades vs 23.5% of runners.

This is a warning against simply requiring “more aligned evidence.” Very hot immediate continuation can also be late/exhausted entry.

## 4. Exact high-resolution divergence

High-resolution snapshots require an observation within +/-45 seconds of the target and the position must still be alive at the horizon.

### +1 minute

| Metric | True wrong | Recovered |
|---|---:|---:|
| median current PnL | -0.093% | +0.023% |
| median MFE | 0.146% | 0.246% |
| side 3m return negative | 14.8% | 10.4% |
| flow opposite | 47.9% | 36.7% |
| PnL <= -0.35% | 8.2% | 0.8% |

The split exists but remains incomplete.

### +3 minutes

| Metric | True wrong | Recovered | Difference |
|---|---:|---:|---:|
| median current PnL | -0.116% | +0.173% | -0.289 pp |
| side 3m return negative | 62.8% | 23.3% | +39.5 pp |
| flow opposite | 52.7% | 34.9% | +17.8 pp |
| positioning opposite | 27.1% | 13.3% | +13.8 pp |
| opposite micro-structure | 12.4% | 1.6% | +10.8 pp |
| danger >=2 | 42.7% | 16.9% | +25.8 pp |
| danger >=4 | 23.6% | 8.8% | +14.8 pp |
| >=2 adverse evidence families | 47.0% | 18.9% | +28.1 pp |
| >=3 adverse evidence families | 23.1% | 8.8% | +14.2 pp |
| PnL <= -0.35% | 11.0% | 1.6% | +9.3 pp |

Approximate 95% CIs for the true-wrong minus recovered gaps:

- side 3m negative: +32.2 to +46.8 pp
- flow opposite: +9.9 to +25.7 pp
- positioning opposite: +7.5 to +20.1 pp
- opposite micro-structure: +7.0 to +14.6 pp
- danger >=2: +18.8 to +32.8 pp
- >=2 adverse families: +20.9 to +35.3 pp

The +3m divergence is materially stronger than any entry-time separation.

### +5 minutes

True-wrong median PnL remains -0.116% while recovered median PnL rises to +0.291%.

However, by +5m:

- 51.8% of TRUE_WRONG_DIRECTION positions were already closed,
- only 8.3% of RECOVERED_DRAWDOWN were closed.

Therefore waiting until 5 minutes is too late for a large fraction of wrong-direction trades. The useful decision window is earlier.

## 5. Candidate dynamic signatures for WD-3

These are research signatures, not production rules.

At +3m among matched TRUE_WRONG_DIRECTION and RECOVERED_DRAWDOWN trades:

| Signature | True wrong flagged | Recovered flagged | Precision for true-wrong within the two classes |
|---|---:|---:|---:|
| ret3 negative + flow opposite | 37.2% | 13.7% | 79.1% |
| ret3 negative + positioning opposite | 27.4% | 13.3% | 74.2% |
| ret3 negative + micro-structure opposite | 12.4% | 1.6% | 91.5% |
| >=2 adverse families | 47.0% | 18.9% | 77.6% |
| >=3 adverse families | 23.1% | 8.8% | 78.4% |
| danger >=2 | 42.7% | 16.9% | 77.9% |
| danger >=4 | 23.6% | 8.8% | 78.8% |
| PnL <= -0.35% | 11.0% | 1.6% | 90.5% |

High precision alone is not enough: PnL <= -0.35% and micro-structure reversal catch only a small fraction of wrong trades. WD-3 should therefore test combinations that improve loss capture without killing recovered drawdowns.

## 6. WD-2 conclusion

WD-2 does **not** support a blanket static tightening of Stage 11C.

The evidence supports a different direction:

1. retain the current moving-coin detection universe,
2. do not treat an immediate small drawdown as automatic failure,
3. focus on a short dynamic confirmation window around the first 1–3 minutes,
4. require persistent adverse price evidence plus at least one independent evidence family before escalating,
5. explicitly benchmark missed recovered drawdowns.

The central WD-3 question is now:

> Should the system delay/confirm entry, or enter immediately and use a 1–3 minute dynamic wrong-direction discriminator?

WD-3 must counterfactually compare both approaches against the frozen cohort before any production tuning is promoted.
