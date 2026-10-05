# SHORT-CT6A — Low-MFE Failure Anatomy

Status: **PASS anatomy / low-MFE admission is the dominant cross-lane loss population**

## Objective

CT-6A is anatomy only.

It does **not** create a production rule and does **not** use MFE as a live feature.

The purpose is to map the frozen CT-4 +0.075% selected universe by future MFE label so CT-6B can search for causal pre-entry separators.

Frozen baseline:

- SHORT temporal confirmation floor: +0.075%
- CT-4 exact execution-realistic replay
- V4.3 SHORT-LS4
- BE0.10
- fee/slippage/notional frozen
- CT-5B remains a separate research architecture repair
- no runtime / paper-entry change

MFE coverage:

> **1,087 / 1,087 selected trades = 100%**

## Frozen MFE anatomy labels

- **BAD-A**: MFE < 0.30%
- **BAD-B**: 0.30% <= MFE < 0.50%
- **GRAY**: 0.50% <= MFE < 1.00%
- **TARGET-MFE**: MFE >= 1.00%

Important:

> MFE is future information and is used only as a research label.

TARGET-MFE is not identical to META_WIN / strong. Strong remains the frozen META_WIN AND MFE >= 1% contract.

## Headline distribution

| MFE bucket | Selected | Executable | Exec strong | Protected WR | Protected PnL | Avg PnL |
|---|---:|---:|---:|---:|---:|---:|
| **BAD-A <0.30%** | 243 | 224 | 0 | **0.45%** | **-$503.60** | **-$2.25** |
| **BAD-B 0.30-0.50%** | 155 | 155 | 0 | **3.23%** | **-$329.54** | **-$2.13** |
| GRAY 0.50-1.00% | 363 | 273 | 0 | 27.47% | -$136.13 | -$0.50 |
| **TARGET-MFE >=1.00%** | 326 | 279 | 246 | **82.44%** | **+$588.89** | **+$2.11** |

Combined low-MFE:

> **MFE <0.50% = 398 selected / 379 executable / 0 strong / -$833.14**

That population is only 36.6% of selected trades, yet it creates more than twice the magnitude of the final system loss.

Baseline total protected PnL:

> **-$380.39**

Oracle removal of MFE <0.50%:

> **+$452.75**

No strong trade exists below MFE 0.50% under the frozen strong contract.

## BAD-A versus BAD-B

BAD-A is the most terminal cohort:

- 243 selected
- 224 executable
- only **1 positive executable**
- WR **0.45%**
- PnL **-$503.60**
- 127 severe fallbacks
- severe fallback PnL **-$443.29**

BAD-B is also structurally poor:

- 155 selected
- 155 executable
- only **5 positive executable**
- WR **3.23%**
- PnL **-$329.54**
- 63 severe fallbacks
- severe fallback PnL **-$311.38**

Therefore the low-MFE problem is not driven by a few outliers.

It is a broad population-level admission problem.

## Gray cohort

GRAY 0.50-1.00%:

- 363 selected
- 273 executable
- WR 27.47%
- PnL -$136.13
- average -$0.50
- 47 severe fallbacks

GRAY remains negative, but its damage per trade is materially smaller than BAD-A/B.

This supports a staged detector objective:

1. high-precision BAD-A rejection first;
2. BAD-B rejection second;
3. GRAY only after winner retention is proven.

## TARGET-MFE cohort

MFE >=1.00%:

- 326 selected
- 279 executable
- 246 executable strong
- WR **82.44%**
- PnL **+$588.89**
- avg **+$2.11**

The 33 executable non-strong trades inside TARGET-MFE contribute only -$3.16 net.

This means the core opportunity population is economically strong; the system-level negative result is dominated by admission of low-MFE trades.

## Lane anatomy

### Combined MFE <0.50%

| Lane | Low-MFE selected | Low-MFE executable | Share of lane selected | Low-MFE PnL | Severe fallback | Oracle lane PnL if removed |
|---|---:|---:|---:|---:|---:|---:|
| T0 | 112 | 112 | 42.42% | **-$190.60** | 48 | **+$123.79** |
| T1 | 92 | 92 | 34.46% | **-$214.80** | 47 | **+$75.12** |
| **T2** | **127** | **115** | 33.16% | **-$285.88** | **63** | **+$169.07** |
| T3 | 67 | 60 | 38.73% | **-$141.87** | 32 | **+$84.78** |

Key finding:

> **Every lane becomes positive if its MFE <0.50% population is removed.**

Therefore low-MFE failure is a cross-lane admission issue.

T2 has the largest absolute low-MFE loss mass:

> **-$285.88**

T1 follows:

> **-$214.80**

T0:

> **-$190.60**

T3:

> **-$141.87**

CT-6B should therefore preserve lane-specific information sets rather than fit one global cutoff.

## Detailed lane distributions

### T0

- BAD-A: 76 exec / -$140.34
- BAD-B: 36 exec / -$50.25
- GRAY: 63 exec / -$8.76
- TARGET-MFE: 89 exec / +$132.55
- TARGET WR: 73.03%

T0 has the highest selected share of low-MFE among T0-T2 and no temporal confirmation history is available at entry.

### T1

- BAD-A: 50 exec / -$117.34
- BAD-B: 42 exec / -$97.47
- GRAY: 90 exec / -$65.71
- TARGET-MFE: 60 exec / +$140.83
- TARGET WR: 83.33%

T1 remains materially damaged even after leaving BAD-A/B because its GRAY cohort is still -$65.71.

### T2

- BAD-A: 61 exec / -$155.87
- BAD-B: 54 exec / -$130.00
- GRAY: 85 exec / -$53.42
- TARGET-MFE: 94 exec / +$222.49
- TARGET WR: 86.17%

T2 is the highest-priority lane for CT-6B because it contains:

- largest low-MFE loss mass;
- largest number of low-MFE selected trades;
- richer T1/T2 causal temporal information than T0/T1.

### T3

- BAD-A: 37 exec / -$90.05
- BAD-B: 23 exec / -$51.82
- GRAY: 35 exec / -$8.24
- TARGET-MFE: 36 exec / +$93.02
- TARGET WR: 94.44%

T3 has the highest proportion of low-MFE executable trades:

> 60 / 131 = **45.8%**

but CT-5B currently removes only a small high-precision subset.

## Chronological stability

Low-MFE <0.50% is negative in **all 6 blocks**:

| Block | Low-MFE selected | Executable | Low-MFE PnL | Severe fallback PnL | TARGET-MFE PnL |
|---|---:|---:|---:|---:|---:|
| Research Discovery | 67 | 67 | **-$164.20** | -$153.22 | **+$71.25** |
| Research Validation | 20 | 20 | **-$29.67** | -$23.56 | **+$36.70** |
| Research Reserve | 36 | 34 | **-$57.49** | -$49.73 | **+$45.15** |
| Fresh Oct 1 | 105 | 102 | **-$244.52** | -$221.61 | **+$104.01** |
| Fresh Oct 2 | 99 | 88 | **-$173.14** | -$150.26 | **+$253.73** |
| Fresh Oct 3 | 71 | 68 | **-$164.13** | -$156.28 | **+$78.05** |

This is one of the strongest CT-6A findings:

> **low-MFE <0.50% is negative in 6/6 chronological blocks, while TARGET-MFE >=1.00% is positive in 6/6 blocks.**

The separation is therefore not caused by one day or one research split.

## Research versus Fresh

Research:

- low-MFE <0.50%: 123 selected / 121 executable / **-$251.36**
- GRAY: 112 / 86 / -$37.07
- TARGET-MFE: 98 / 84 / **+$153.10**

Fresh:

- low-MFE <0.50%: 275 selected / 258 executable / **-$581.79**
- GRAY: 251 / 187 / -$99.06
- TARGET-MFE: 228 / 195 / **+$435.79**

The same anatomy transports from historical research to Fresh.

Fresh does not introduce a different direction; it increases the scale of the same problem.

## Failure-reason anatomy

BAD-A:

- HIST_TIME_FALLBACK: 167
- BE0.10: 57
- no strong

BAD-B:

- HIST_TIME_FALLBACK: 71
- BE0.10: 79
- FULL_CLOSE_050: 5
- no strong

GRAY:

- HIST_TIME_FALLBACK: 97
- BE0.10: 102
- FULL_CLOSE_050: 74

TARGET-MFE:

- FULL_CLOSE_050: 198
- RUNNER_CLOSE: 32
- BE0.10: 27
- HIST_TIME_FALLBACK: 22

This also shows why profit protection alone cannot solve the admission problem:

> most BAD-A/B trades never create enough favorable excursion for the protector to harvest meaningful profit.

## CT-6A verdict

> **PASS anatomy.**

The dominant detector problem is now defined as:

> **predict future MFE failure using only causal information available by the lane decision time.**

Primary research target for CT-6B:

> **BAD = MFE <0.50%**

Protection class:

> **TARGET-MFE = MFE >=1.00%**

GRAY 0.50-1.00% remains a secondary class and should not initially be treated as equivalent to BAD-A/B.

### CT-6B priority order

1. **T2** — largest low-MFE loss mass (-$285.88), temporal features available.
2. **T1** — -$214.80 low-MFE loss.
3. **T0** — -$190.60, but fewer temporal signals.
4. **T3** — -$141.87; CT-5B already provides a small high-precision repair.

CT-6B must:

- use only causal pre-entry / decision-time features;
- measure BAD-A and BAD-B recall separately;
- protect TARGET-MFE retention;
- report strong retention independently;
- test Research Discovery / Validation / Reserve / Fresh Oct1/2/3 separately;
- avoid using MFE itself in any candidate gate;
- avoid fitting one global threshold across lanes unless transport evidence proves it.

No runtime promotion is authorized.