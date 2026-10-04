# PP V4-3C3 — Multi-Cycle Reclaim & Volatility-Normalized Reversal Contract

Status: **PREREGISTERED BEFORE CANDIDATE OUTCOME INSPECTION**

Baseline: **Profit Protector V4.2 — Hybrid Protection**

## Objective

Stage3C and Stage3C2 both failed because a single temporal wait or one bounded reclaim probe could not separate continuation from final reversal while preserving runner retention.

Stage3C3 tests a narrower causal hypothesis:

> a genuine reversal is more likely when the trade repeatedly fails to reclaim after an initial giveback, and the total drawdown is large relative to the trade's own recent 5s noise.

No future peak, true MFE, or future-path label may be used by the detector.

## Population

Use the same historical runner-capable population:
- V4.2-triggered trades;
- archived observed peak >= +1.50%;
- 19 trades total;
- first 12 chronological trades = DEV;
- final 7 = LATE chronology robustness check.

LATE is not claimed as pristine because prior stages inspected aggregate history.

## Causal local-noise estimate

At every observation, estimate local noise from observations **strictly before or at the current timestamp**.

Noise scale:
- median absolute change in observed PnL over the previous N intervals;
- N is candidate-selected from **6 or 12 samples** (approximately 30s or 60s at 5s cadence);
- floor noise scale at epsilon 0.01 percentage points to avoid division instability.

Normalized giveback:

`drawdown_z = (running_peak - current_pnl) / local_noise_scale`

This is causal.

## Multi-cycle failed reclaim state

A cycle begins only after:
- running observed peak >= +1.50%; and
- current PnL crosses below an initial floor.

Initial floor candidates:
- **90%**
- **85%** of current running peak.

During an active cycle:
- keep the current running peak P;
- track trough T since the floor crossing;
- define reclaim level:
  `T + reclaim_fraction × (P - T)`

A reclaim attempt becomes **armed** once current PnL rises to or above that reclaim level.

A reclaim attempt becomes a **failed reclaim cycle** if, after being armed and without a new running high:
- price falls back to or below the original initial floor, or
- makes a new trough below T.

After a failed cycle:
- increment failed_reclaim_count;
- reset trough/reclaim state from the new local path;
- keep the same running peak until a new running high occurs.

Any new running high:
- cancels the entire reversal state;
- resets failed_reclaim_count to zero.

## Frozen candidate family

Initial giveback floor:
- **90%, 85%**

Noise lookback:
- **6, 12 samples**

Reclaim fraction:
- **25%, 50%**

Required failed reclaim cycles:
- **1, 2**

Minimum normalized giveback:
- **2.0, 3.0 local-noise units**

Candidate count = 2 × 2 × 2 × 2 × 2 = **32**.

No parameter values may be added after results are inspected.

## Signal semantics

Emit REVERSAL at the first causal observation where all are true:
1. runner peak >= +1.50%;
2. failed_reclaim_count >= required count;
3. current PnL remains <= initial floor;
4. normalized giveback >= required Z threshold.

Emit at most one signal per historical trade for evaluation.

## Evaluation labels

Research-only post-hoc labels:

- **PREMATURE_FALSE_REVERSAL**:
  a later archived observation exceeds the running peak that existed at detector signal.

- **CORRECT_FINAL_REVERSAL**:
  no later archived observation exceeds that signal-time running peak.

Future labels are scoreboards only.

## Retention scoring

For correct signals:
- retention = signal PnL / final archived observed peak;
- report median;
- report share >=80%;
- report share >=75%.

For premature signals:
- report future higher peak;
- report signal-to-future-higher-peak time.

## DEV gates

Candidate is eligible only if all hold:

1. signal coverage >= **50%**;
2. correct-final-reversal precision >= **65%**;
3. premature share <= **35%**;
4. median correct retention >= **80%**;
5. correct signals retaining >=80% >= **50%**.

## DEV ranking

Among eligible candidates:
1. highest precision;
2. lowest premature share;
3. highest >=80 retention share;
4. highest median retention;
5. highest coverage;
6. fewer required failed-reclaim cycles;
7. higher initial floor;
8. shorter noise lookback;
9. lower reclaim fraction;
10. lower normalized-drawdown threshold.

## LATE validation

Freeze top DEV candidate and replay unchanged on LATE.

No post-LATE retuning.

## Baselines

Compare against:
- V4.2 runner close;
- Stage3C closest near-miss;
- Stage3C2 highest-precision candidate;
- Stage3C2 high-retention candidate;
- naive 90/85/80 floors.

## Decision

If no candidate passes:
- Stage3C3 = **NO PASS**;
- do not relax gates;
- do not proceed to Stage3D.

If one or more pass:
- nominate exactly one frozen DEV winner for Stage3D integration research.

Restrictions:
- historical real data only;
- no runtime change;
- no paper/prospective shadow;
- no future true/final peak in causal features;
- no claim of final-peak prediction.
