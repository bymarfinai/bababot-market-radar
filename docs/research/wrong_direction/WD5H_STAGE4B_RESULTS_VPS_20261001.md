# WD-5H Stage 4B Frozen Results — 2026-10-01

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

TEMPORAL_PATTERN_DISCOVERY_COMPLETE_SURVIVOR_GUARDED

## Why survivor guarding matters

The Stage 3A outcome can resolve quickly.

Of the 1,891 META_WIN/META_LOSS trades:

### By T+1

Already resolved:
- 152 / 1,891 = 8.04%
- early META_WIN: 34
- early META_LOSS: 118

Still unresolved:
- 1,739
- META_WIN: 530
- META_LOSS: 1,209
- WIN prevalence: 30.48%

### By T+2

Already resolved:
- 335 / 1,891 = 17.72%
- early META_WIN: 67
- early META_LOSS: 268

Still unresolved:
- 1,556
- META_WIN: 497
- META_LOSS: 1,059
- WIN prevalence: 31.94%

### By T+3

Already resolved:
- 535 / 1,891 = 28.29%
- early META_WIN: 113
- early META_LOSS: 422

Still unresolved:
- 1,356
- META_WIN: 451
- META_LOSS: 905
- WIN prevalence: 33.26%

All discrimination results below use only the still-unresolved cohort at each
horizon.

## Horizon comparison

| Horizon | Robust features | Strong features | Diagnostic Val AUC | Diagnostic Test AUC |
|---|---:|---:|---:|---:|
| T+1 | 42 | 21 | 0.584 | 0.626 |
| T+2 | 55 | 32 | 0.677 | 0.722 |
| T+3 | **63** | **57** | **0.804** | **0.757** |

Descriptive best horizon:

**T+3**

The temporal signal strengthens monotonically from T+1 to T+3.

## Strongest T+3 features

### 1. Cumulative selected-side return from T0

AUC:
- train: 0.710
- validation: 0.790
- test: 0.787

Minimum chronological separation: 0.419.

This is the strongest direct confirmation feature.

### 2. Selected-side 3-minute micro return

AUC:
- train: 0.688
- validation: 0.781
- test: 0.748

Its average separation improves materially versus the corresponding T0
feature.

### 3. Selected-side VWAP extension

AUC:
- train: 0.681
- validation: 0.747
- test: 0.709

The temporal version adds substantial separation versus T0.

### 4. Selected short-horizon slope / momentum persistence

AUC:
- train: 0.671
- validation: 0.706
- test: 0.675

### 5. Structure reversal score

The direction is inverse: lower reversal pressure is associated with WIN.

AUC:
- train: 0.333
- validation: 0.243
- test: 0.332

### 6. Close-strength / close-z

AUC:
- train: 0.666
- validation: 0.734
- test: 0.663

### 7. Post-candidate MFE

AUC:
- train: 0.662
- validation: 0.686
- test: 0.744

### 8. Coin minus market 5m

AUC:
- train: 0.649
- validation: 0.655
- test: 0.634

This supports the idea that relative strength, not only absolute price
movement, matters.

## Direct taker confirmation

Selected-side taker share improves with horizon:

### T+1
- train AUC: 0.546
- validation: 0.583
- test: 0.589

### T+2
- train: 0.546
- validation: 0.615
- test: 0.625

### T+3
- train: 0.571
- validation: 0.661
- test: 0.612

Taker flow is useful but materially weaker than the primary price/path and
microstructure evidence.

## Family stability at T+3

| Family | Robust | Strong |
|---|---:|---:|
| Confirmation path | 7 | 6 |
| Delta vs T0 | 12 | 12 |
| Flow | 4 | 3 |
| Market-relative | 7 | 7 |
| Micro | **25** | **21** |
| OI-derived | 2 | 2 |
| Other structure | 6 | 6 |

Micro/path is the deepest stable evidence family.

The fact that all 12 robust delta features are also strong at T+3 is important:
**how the setup changes after T0 carries information beyond the original
snapshot itself.**

## OI interpretation

Stage 4A showed fresh 5m OI availability:

- T+1: 0%
- T+2: 0%
- T+3: 2.39%

Therefore any stable T+3 OI-derived feature is mostly old OI context combined
with new price/path information.

It must not be presented as fresh OI confirmation.

## Diagnostic T+3 model

Fixed train-only top-12 features include:

- cumulative T+3 side return;
- selected-side 3m return;
- VWAP extension;
- selected slope;
- reversal structure;
- close-z;
- selected-side 5m return;
- post-candidate MFE;
- selected-side 1m return;
- opposite-body structure;
- selected body strength.

AUC:

- train: 0.724
- validation: **0.804**
- test: **0.757**

This is dramatically stronger than the static Stage 3B ranking, which was
around AUC 0.57-0.59.

No threshold is selected here.

## Main finding

The static snapshot did not contain enough stable information to identify a
high-purity WIN pocket.

The first three minutes after the candidate appears do.

The key evidence is not a new exotic indicator. It is the evolution of the
existing thesis:

- does price actually move in the selected direction;
- does it hold strength relative to local VWAP/structure;
- does the move remain strong relative to the broader market;
- does taker participation support rather than oppose it;
- does reversal pressure stay low.

T+3 currently gives the strongest historical discrimination.

## Important economic trade-off

Waiting three minutes is not free.

By T+3, 535 resolved trades have already completed their Stage 3A barrier path:

- 422 were early META_LOSS;
- 113 were early META_WIN.

So waiting mechanically avoids many fast failures, but it can also miss fast
winners.

Stage 4C should test selective confirmation among survivors.

Stage 4D must then re-enter at the actual delayed market price and measure the
true economic cost of waiting.

## Next

WD-5H Stage 4C — High-Precision Temporal Confirmation Gate

Stage 4C should:

1. preserve the survivor guard;
2. compare T+1/T+2/T+3 under a frozen selection protocol;
3. select thresholds using validation only;
4. target precision floors such as 60/65/70/75/80%;
5. report coverage and trade/day;
6. avoid requiring fresh OI;
7. keep final historical test as robustness evidence only.

Fresh prospective data remains mandatory before production promotion.

## Frozen artifact hashes

wd5h4b_temporal_pattern_results.json
SHA256:
6bfdd26bb899a2a8917627063471686eaedbd88347bceee9b2b1e86f44d55281

wd5h4b_feature_audit.csv
SHA256:
d7ff210a1d104e80667c4bbd76c02049ec664a1585eb232bb39f8d6a55a3f971
