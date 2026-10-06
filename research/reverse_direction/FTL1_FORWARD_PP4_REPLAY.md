# FTL-1 Forward — Four Frozen Profit Protectors Replay

Status: **COMPLETE — EXIT IMPROVEMENT, SYSTEM STILL NEGATIVE**

Date: 2026-10-06

## Purpose

Replay the exact frozen four parallel Profit Protector branches on the same frozen FTL-1 forward candidate population.

No selector or protector parameter was retuned.

## Frozen forward population

Source:
- FTL-1 frozen 75-second forward OOS rule
- forward universe: 2,503 LONG closed trades
- selected FTL-1 SHORT candidates: **248**
- candidate entry timestamp and entry price are identical to the completed FTL-1 forward replay

FTL selector:
- 75s running MFE <= +0.083542%
- last-30s LONG buy-taker share <= 23.0566%

Execution:
- SHORT notional $500
- fee 0.05% per side
- slippage 2 bps per side
- historical original LONG close timestamp remains the fallback source-close boundary

## Four frozen protectors

### V42_BASELINE
- small arm +0.50%
- retain 60%
- confirmation 3 x 5s
- REDUCE 25% of remaining
- runner qualify +1.50%
- runner retain 90%
- runner confirmation 2 x 5s

### V43_LS
- small arm +0.50%
- SHORT retain 75%
- confirmation 1 x 5s
- full close
- runner logic inherited from V4.2

### BE025_CONSERVATIVE
- gross arm +0.25%
- requires executable net >= 0 before arming
- later executable net <=0 closes
- if observed 5s peak reaches +0.50%, BE is superseded by V4.3-LS / V4.2 runner

### BE018_AGGRESSIVE
- same architecture as BE0.25
- gross arm +0.18%

## Full 248 comparison

| Exit | Wins | WR | Net PnL | Avg | PF |
|---|---:|---:|---:|---:|---:|
| Hold to historical close | 114 | 45.97% | **-$126.73** | -$0.511 | 0.498 |
| Fixed TP0.8 / SL0.5 | 106 | 42.74% | **-$164.50** | -$0.663 | 0.436 |
| V4.2 | 114 | 45.97% | **-$126.88** | -$0.512 | 0.492 |
| V4.3-LS | **117** | **47.18%** | **-$125.65** | -$0.507 | 0.487 |
| BE0.25 | 83 | 33.47% | **-$139.36** | -$0.562 | 0.338 |
| **BE0.18** | 65 | 26.21% | **-$122.84** | -$0.495 | 0.301 |

Best dollar result:
- **BE0.18 = -$122.84**

Best WR:
- **V4.3-LS = 47.18%**

No frozen protector makes the full FTL-1 forward cohort profitable.

## Delta versus hold

- V4.2: **-$0.14**
- V4.3-LS: **+$1.08**
- BE0.25: **-$12.62**
- BE0.18: **+$3.89**

Therefore PP improves some exits but does not solve the selector economics.

## Action counts

### V4.2
- historical-close fallback: 246
- runner close: 2
- reduce25 signals: 9

### V4.3-LS
- historical-close fallback: 232
- V4.3 full close: 16

### BE0.25
- historical-close fallback: 195
- BE closes: 48
- V4.3 full closes after handoff: 5

### BE0.18
- historical-close fallback: 161
- BE closes: **82**
- V4.3 full closes after handoff: 5

BE0.18 is therefore substantially more active, but most of the selected cohort still does not receive a profitable protector exit.

## Critical anatomy by post-SHORT-entry MFE

### MFE < +0.18%

Population:
- **111 trades**

All four protectors produce exactly the same result because none gets enough favorable excursion to arm:

- wins: 10
- WR: **9.01%**
- PnL: **-$167.01**
- PF: 0.009

This cohort alone is larger in loss than the total portfolio loss.

### MFE >= +0.18%

Population:
- **137 trades**

| Exit | WR | PnL | PF |
|---|---:|---:|---:|
| Hold | 75.91% | +$40.28 | 1.48 |
| V4.2 | 75.91% | +$40.13 | 1.49 |
| V4.3-LS | **78.10%** | +$41.35 | 1.54 |
| BE0.25 | 53.28% | +$27.65 | 1.66 |
| **BE0.18** | 40.15% | **+$44.17** | **7.16** |

This proves the protector layer is not the core failure.

Once a SHORT obtains at least about +0.18% favorable excursion, the existing PP family is already capable of positive economics.

### MFE +0.18% to <+0.50%

110 trades:

- V4.2: -$13.46
- V4.3-LS: -$13.46
- BE0.25: **+$7.20**
- **BE0.18: +$26.70**, PF 5.39

This is exactly the zone where the aggressive BE protector is useful.

### MFE +0.50% to <+1.00%

18 trades:

- V4.2: +$25.90
- **V4.3-LS: +$33.57, 18/18 positive**
- BE0.25: +$11.30
- BE0.18: +$11.26

V4.3-LS is highly effective once the trade creates a genuine +0.50% SHORT excursion.

### MFE >= +1.00%

9 trades:

- V4.2: **+$27.70**, 9/9 positive
- V4.3-LS: +$21.24, 9/9 positive
- BE0.25: +$9.15
- BE0.18: +$6.21

The V4.2 runner architecture is strongest for the highest-MFE runner population.

## BE0.18 active-vs-no-action anatomy

BE0.18 active:
- 87 trades
- protected PnL: **+$3.53**
- hold PnL for same trades: -$0.36
- delta: **+$3.89**

BE0.18 no-action:
- 161 trades
- PnL: **-$126.37**

Thus all total improvement from BE0.18 is concentrated in trades where the protector can actually activate.

## Conclusion

The four frozen Profit Protectors do **not** rescue FTL-1 as a complete SHORT system.

However the replay isolates the true problem:

> **The exit layer is not the bottleneck. The 111 post-entry MFE <0.18% trades are.**

The current PP family only becomes useful after favorable SHORT excursion exists.

The next research target should therefore not be another Profit Protector retune.

It should identify, before or immediately after the prospective SHORT entry, which FTL candidates will remain in:

> **post-entry MFE < +0.18%**

versus those that will generate at least:

> **post-entry MFE >= +0.18%**

If the low-MFE subset can be rejected causally, the remaining 137 trades are already positive under the frozen PP stack; BE0.18 is the strongest dollar protector in that surviving population.
