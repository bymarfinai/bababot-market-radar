# FTL-3 — Favorable SHORT Confirmation After FTL-2 Veto

Status: **FAIL — CONFIRMATION-THEN-ENTRY CHASES THE MOVE**

Date: 2026-10-06

## Objective

Test whether the remaining FTL-2 candidates should be required to prove that downside is still available before capital is committed.

Frozen sequence:

1. FTL-1 75s candidate.
2. FTL-2 veto:
   - drop / do not SHORT when side return at 75s <= -0.282752%.
3. For survivors, do not enter immediately.
4. Require an additional favorable downside move from the prospective 75s SHORT anchor:
   - 0.05%
   - 0.10%
   - 0.15%
   - 0.18%
5. Confirmation must occur within:
   - 30s
   - 60s
   - 120s
6. Enter SHORT on the first raw Binance aggTrade that touches the confirmation level.
7. Exit with the frozen BE0.18 protector stack:
   - BE0.18 raw arm,
   - V4.3-LS handoff at +0.50% observed peak,
   - V4.2 runner logic.

No confirmation or PP threshold was retuned after seeing Validation/Reserve.

## Audit correction

An initial FTL-3 replay reconstructed the 192 survivors from an older forward-checkpoint side75 value.

Although the count was also 192, the ID set did not exactly match the FTL-2 primary cohort:
- reconstructed baseline: about -$90.16
- authoritative FTL-2 baseline: -$82.9957

That initial FTL-3 run was rejected.

FTL-2 was rerun and the exact 192 survivor IDs were exported directly from the authoritative FTL-2 implementation.

The final FTL-3 replay below uses those exact IDs.

Baseline now matches exactly:

| Split | N | Frozen BE0.18 baseline |
|---|---:|---:|
| TRAIN | 56 | **-$1.37** |
| VALIDATION | 80 | **-$55.77** |
| RESERVE | 56 | **-$25.85** |
| VAL + RESERVE | 136 | **-$81.63** |
| ALL | 192 | **-$83.00** |

## Grid result

### Confirmation -0.05% from prospective 75s SHORT anchor

#### Timeout 30s

| Split | Entry N | Entry rate | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 23 | 41.1% | 52.17% | **-$2.95** |
| VALIDATION | 31 | 38.8% | 22.58% | **-$24.34** |
| RESERVE | 17 | 30.4% | 52.94% | **+$0.23** |
| ALL | 71 | 37.0% | 39.44% | **-$27.07** |

This is the only moderate-size lane with a slightly positive Reserve result, but it fails Validation.

#### Timeout 60s

TRAIN-selected primary among settings with at least 20 entries and >=50% original-good retention:

| Split | Entry N | WR | PnL |
|---|---:|---:|---:|
| TRAIN | 32 | 46.88% | **-$1.87** |
| VALIDATION | 42 | 16.67% | **-$30.23** |
| RESERVE | 24 | 45.83% | **-$3.08** |
| ALL | 98 | 33.67% | **-$35.18** |

The TRAIN baseline before confirmation was -$1.37, so even on TRAIN this confirmation lane does not improve economics.

#### Timeout 120s

| Split | Entry N | WR | PnL |
|---|---:|---:|---:|
| TRAIN | 40 | 42.50% | -$3.38 |
| VALIDATION | 54 | 16.67% | -$33.97 |
| RESERVE | 36 | 36.11% | -$14.37 |
| ALL | 130 | 30.00% | -$51.72 |

Longer arming windows admit more trades but worsen economics.

## Confirmation -0.10%

Representative 60s lane:

| Split | Entry N | WR | PnL |
|---|---:|---:|---:|
| TRAIN | 20 | 50.00% | -$2.33 |
| VALIDATION | 23 | 8.70% | -$17.43 |
| RESERVE | 14 | 42.86% | -$3.67 |
| ALL | 57 | 31.58% | -$23.44 |

No tested 0.10% timeout transports to positive Validation/Reserve economics.

## Confirmation -0.15%

A superficially attractive TRAIN result appears at 30s:

- TRAIN entries: 6
- TRAIN PnL: **+$2.61**
- TRAIN PF: 4.23

But it is tiny and fails immediately out of sample:

- VALIDATION: 8 entries, **-$10.68**
- RESERVE: 4 entries, **-$3.76**
- VAL + RESERVE: **-$14.44**

Rejected as non-robust.

## Confirmation -0.18%

The 30s lane trades only 13 of 192 candidates:

- ALL PnL: **-$2.53**
- entry rate: 6.77%

Out of sample:
- VALIDATION: -$1.02
- RESERVE: -$3.76

The small aggregate loss comes primarily from almost never trading, not from a positive edge.

## Why favorable confirmation fails

FTL-3 confirms a key execution distinction.

The proposed logic was:

> prove the SHORT direction by letting price fall further -> enter SHORT.

For a SHORT, this means entering at a **lower price after the favorable move has already occurred**.

That is direction confirmation but also **entry chasing**.

The result mirrors the earlier LONG confirmation problem:

- confirmation improves certainty that the recent direction is real;
- but entry quality deteriorates because the strategy pays for that confirmation with lost remaining excursion.

Example:

> prospective SHORT anchor = 100.00  
> wait for -0.10% confirmation -> price = 99.90  
> enter SHORT at ~99.90

The strategy has now surrendered 0.10% of the move before entry, while round-trip friction is still about 0.14%.

The remaining downside must be much larger merely to break even.

This is why old-good retention can remain high while post-confirmation economics remain poor.

## Verdict

FTL-3 is a **FAIL**.

Do not deploy:

> FTL candidate -> distance veto -> favorable downside touch -> immediate SHORT.

No tested 0.05 / 0.10 / 0.15 / 0.18% confirmation with 30 / 60 / 120s timeout produces robust positive economics across TRAIN, VALIDATION and RESERVE.

## Structural implication

The research now shows the same execution problem on both sides:

- LONG: prove-up and buy immediately -> chase upward.
- SHORT: prove-down and short immediately -> chase downward.

Therefore confirmation should be used as **state validation**, not the actual entry price.

The next logical architecture is:

> FTL candidate  
> -> FTL-2 distance veto  
> -> downside confirmation  
> -> **wait for upward retest / bounce**  
> -> SHORT only if the bounce fails

This would preserve directional proof while attempting to recover a better SHORT entry price.

Any next stage should test confirmation-then-retest, not larger confirmation thresholds.
