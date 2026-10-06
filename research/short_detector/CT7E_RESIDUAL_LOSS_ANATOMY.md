# SHORT-CT7E — Residual Loss Anatomy

Status: **PASS anatomy / residual loss still dominated by low-MFE time-fallback failures**

## Current combined system

Frozen stack: CT-5B + CT-6C + CT-7C + CT-7D CLEAN2.

- selected: **938**
- executable: **794**
- wins: **292**
- WR: **36.78%**
- executable strong: **238**
- PnL: **-$136.32**

No runtime or paper-entry change is authorized.

## Residual MFE anatomy

| MFE bucket | Exec | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| BAD-A <0.30% | 153 | 0 | 0.00% | **-$316.29** |
| BAD-B 0.30-0.50% | 116 | 4 | 3.45% | **-$254.83** |
| GRAY 0.50-1.00% | 254 | 66 | 25.98% | **-$132.55** |
| TARGET >=1.00% | 271 | 222 | **81.92%** | **+$567.36** |

BAD <0.50% remains **269 executable / -$571.12**.

MFE <1.00% remains **523 executable / -$703.68**.

TARGET >=1.00% contributes **+$567.36**.

## TARGET should be protected

Strong TARGET:
- 238 executable
- 206 wins
- WR **86.55%**
- PnL **+$570.52**

Non-strong TARGET:
- 33 executable
- PnL **-$3.16**

The TARGET pool is not the primary residual problem.

## HIST_TIME_FALLBACK dominates

| Reason | Exec | Wins | PnL |
|---|---:|---:|---:|
| **HIST_TIME_FALLBACK** | **278** | **1** | **-$808.32** |
| BE0.10 | 225 | 0 | -$37.98 |
| FULL_CLOSE_050 | 260 | 260 | +$444.86 |
| RUNNER_CLOSE | 31 | 31 | +$265.12 |

Profit Protector is not the main bottleneck.

BAD-A fallback: **112 / -$307.64**.

BAD-B fallback: **52 / -$251.44**.

Combined BAD fallback: **164 / -$559.09**.

Approximately **97.9% of residual BAD loss magnitude comes from HIST_TIME_FALLBACK**.

## Existing archetypes still contain most residual BAD loss

Inside A1/A2/A3:
- 171 executable BAD
- **-$369.77**

Outside all three:
- 98 executable BAD
- **-$201.35**

So about **64.7% of residual BAD loss is still inside existing CT-7B broad failure territory**.

Fallback-only split is even clearer:

- inside A1/A2/A3: **106 BAD / -$362.61**
- outside all archetypes: **58 BAD / -$196.47**

This means CT-7B found most of the territory, but CT-7C still under-covers BAD inside it.

## GRAY is secondary

GRAY total: **254 exec / -$132.55**.

GRAY fallback: **92 / -$199.97**.

Outside-all GRAY fallback alone is **57 / -$125.32**, the single largest residual cluster, but GRAY contains many valid winners and is less clean than BAD as a development target.

## Largest residual clusters

| Cluster | Trades | PnL |
|---|---:|---:|
| GRAY fallback outside all | 57 | **-$125.32** |
| BAD-B fallback outside all | 25 | **-$123.24** |
| BAD-A fallback multi-archetype | 35 | **-$115.37** |
| BAD-A fallback outside all | 33 | **-$73.23** |
| BAD-A fallback A1 | 23 | **-$59.33** |
| BAD-A fallback A2 | 18 | **-$51.11** |
| BAD-B fallback A1 | 8 | **-$47.17** |
| TARGET fallback outside all | 17 | -$41.43 |
| BAD-B fallback A2 | 9 | **-$35.05** |

## Research / Fresh transport

Research:
- total **-$29.63**
- BAD **-$144.20**
- GRAY -$37.73
- TARGET +$152.29

Fresh:
- total **-$106.68**
- BAD **-$426.92**
- GRAY -$94.83
- TARGET +$415.07

The same anatomy appears in both.

BAD is negative in all six chronological blocks.

## Lane sanity check

Residual BAD PnL:
- T0 **-$147.83**
- T1 **-$160.39**
- T2 **-$178.85**
- T3 **-$84.05**

The problem remains cross-lane, supporting the global low-MFE architecture.

## Oracle diagnostics

Leakage-only ceilings:

- perfect BAD-A removal -> **+$179.97**
- perfect BAD <0.50 removal -> **+$434.81**
- perfect BAD fallback removal -> **+$422.77**
- perfect MFE <1 fallback removal -> **+$622.74**

These are not deployable rules. They show where the economic mass remains.

## Verdict

> **PASS residual anatomy.**

Primary next target:

> **106 residual BAD HIST_TIME_FALLBACK trades already inside A1/A2/A3, totaling -$362.61.**

Secondary next target:

> **58 BAD fallback trades outside all current archetypes, totaling -$196.47.**

Tertiary:

> GRAY fallback outside current archetypes: 57 / -$125.32.

## Recommended CT-7F

CT-7F should first do **Residual Conditional Kill Expansion inside A1/A2/A3**, searching for branches orthogonal to K1/K2/K3.

It should not start with a brand-new global archetype family yet.

No runtime promotion is authorized.
