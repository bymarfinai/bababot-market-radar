# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

WD-5H Stage 4C — High-Precision Temporal Confirmation Gate

Stage 4B is complete with a survivor guard that excludes any META_WIN or
META_LOSS already barrier-resolved before the evaluated confirmation horizon.

This guard is mandatory. Without it, a temporal feature could partly observe
an outcome that had already occurred.

## Stage 4B Main Result

Temporal confirmation materially improves discrimination versus the static
pre-entry snapshot.

Diagnostic ranking AUC on survivor cohorts:

| Horizon | Validation AUC | Test AUC |
|---|---:|---:|
| T+1 | 0.584 | 0.626 |
| T+2 | 0.677 | 0.722 |
| T+3 | **0.804** | **0.757** |

Descriptive best horizon: **T+3**.

No TAKE threshold has been selected yet.

## Survivor / Early-Resolution Trade-off

Resolved Stage 3A population: 1,891.

At T+1:
- 152 already resolved (34 META_WIN, 118 META_LOSS);
- 1,739 remain unresolved;
- survivor META_WIN prevalence: 30.48%.

At T+2:
- 335 already resolved (67 WIN, 268 LOSS);
- 1,556 remain unresolved;
- survivor WIN prevalence: 31.94%.

At T+3:
- 535 already resolved (113 WIN, 422 LOSS);
- 1,356 remain unresolved;
- survivor WIN prevalence: 33.26%.

Waiting therefore removes many early failures but also misses some early
winners. Stage 4D must explicitly price this opportunity cost.

## Strongest Stable T+3 Patterns

Among trades still unresolved at T+3:

1. cumulative selected-side return from T0;
2. selected-side 3m micro return;
3. VWAP extension in the selected direction;
4. selected-side short-horizon slope / momentum persistence;
5. lower reversal-structure score;
6. close-location / close-z strength;
7. post-candidate MFE;
8. coin relative strength versus market/BTC;
9. selected-side taker participation.

The strongest direct feature, T+3 cumulative side return, remains stable:

- train AUC: 0.710
- validation AUC: 0.790
- test AUC: 0.787

## Family Stability at T+3

Robust features (stable direction in all chronological splits and minimum
separation >= 0.05):

- confirmation path: 7
- delta versus T0: 12
- flow: 4
- market-relative: 7
- micro: 25
- OI-derived: 2
- other structure features: 6

Strong features (minimum separation >= 0.10):

- confirmation path: 6
- delta versus T0: 12
- flow: 3
- market-relative: 7
- micro: 21
- OI-derived: 2
- other structure features: 6

OI-derived temporal features must not be interpreted as fresh OI evidence:
historical 5m OI provides a new observation to only 52/2,175 trades at T+3.
Most apparent T+3 OI-derived signal is old OI context interacting with new
price movement.

## Production State

UNCHANGED.

Stage 4B has no production authority.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE
- WD-5H Stage 3B — COMPLETE / WEAK
- WD-5H Stage 3C — REJECTED
- WD-5H Stage 3D — SKIPPED
- WD-5H Stage 3E — NOT APPLICABLE
- WD-5H Stage 4A — COMPLETE
- WD-5H Stage 4B — COMPLETE: TEMPORAL_PATTERN_DISCOVERY_COMPLETE_SURVIVOR_GUARDED

## Stage 4C Constraint

Stage 4C may test a high-precision temporal TAKE/ABSTAIN gate, but must:

- preserve the survivor guard;
- select thresholds from validation only;
- compare T+1/T+2/T+3 without post-hoc switching from test;
- keep OI as context, not fresh temporal confirmation;
- report selected count, coverage, precision, and implied trade/day.

Because historical test behavior has now been inspected during discovery,
Stage 4C/4D remain historical robustness research. Production promotion
requires fresh prospective Stage 4E data.

## Parked

- Wallet/on-chain fusion.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
