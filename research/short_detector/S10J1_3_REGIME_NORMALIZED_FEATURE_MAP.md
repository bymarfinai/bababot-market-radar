# SHORT-S10J-1 to S10J-3 — Regime-Normalized Suppressor Feature Map

Status: **COMPLETE — normalized feature map established / no suppressor promoted yet**

## Scope

S10J-1 to S10J-3 deliberately stop before fitting a new production suppressor.

The goal is to replace the regime-sensitive hard bands that failed in S10H/S10I with causal, relative representations and test whether their winner-vs-noise direction remains stable across chronological regimes.

Frozen baseline:

> **S10D detector + V4.3 SHORT-LS4 + BE0.10**

No S10E or S10G hard-band veto is treated as trusted production logic.

No Profit Protector parameter is changed.

## Development blocks

Six chronological blocks are used:

1. Research Discovery
2. Research Validation
3. Research Reserve
4. Fresh 2026-10-01
5. Fresh 2026-10-02
6. Fresh 2026-10-03

The fresh S10H window is now development data and is not considered sealed validation anymore.

Combined S10D-selected development set:

> **1,171 trades**

Composition:
- Research Discovery: 220
- Research Validation: 69
- Research Reserve: 75
- Fresh Oct 1: 315
- Fresh Oct 2: 323
- Fresh Oct 3: 169

## Causal normalization

Every normalized value uses only observations available **before the current trade**.

Two rolling contexts are frozen for this scan:

### Global context

Previous:

> **128 S10D-selected trades**

Features:
- empirical percentile
- robust z-score using median / MAD

Minimum prior history:
> 20 observations

### Lane-specific context

Previous:

> **64 S10D-selected trades from the same entry lane**

Features:
- empirical percentile
- robust z-score using median / MAD

Minimum prior history:
> 20 observations

The current trade is normalized before it is added to the rolling history.

Therefore no future-row leakage is introduced by the normalization itself.

## Causal feature eligibility

A feature is only evaluated if it is available at the corresponding entry decision:

- T0: T0 information only
- T+1: T0 + T+1
- T+2: T0 + T+1 + T+2
- T+3: T0 + T+1 + T+2 + T+3

Cross-lane use of future temporal features is rejected.

---

# Why normalization is necessary

The S10I failure showed that the old hard bands change class meaning across regimes.

Example:

### T+2 `f_f_taker_accel_1m` hard band

Research hit cohort:
> 11 trades → **0 strong**

Fresh hit cohort:
> 18 trades → **11 strong**

The same absolute interval changed from a pure loss zone into a majority-winner zone.

S10J therefore evaluates the feature relative to recent market context rather than as a fixed numeric interval.

---

# Lane 0

No fully clean 6/6 normalized suppressor direction was found.

Best candidate:

### High lane-relative price drift percentile

`f_gate_price_drift_pct__lpct64 >= 0.70`

Direction:
- negative in **5 / 6** blocks
- positive in Research Validation only

Block delta = strong-rate(hit) - strong-rate(keep):

- Research Discovery: -3.30 pp
- Research Validation: **+12.12 pp**
- Research Reserve: -30.00 pp
- Fresh Oct 1: -3.93 pp
- Fresh Oct 2: -3.89 pp
- Fresh Oct 3: -9.72 pp

Verdict:

> **not clean enough to promote as a standalone T0 suppressor**

T0 remains the weakest normalized-suppressor lane at this stage.

---

# Lane 1 — strongest normalized evidence

Several normalized signals remain loss-enriched in **all 6 / 6 blocks**.

## Candidate A — relative overheat

`f_new_overheat_pressure__lrz64 >= +0.5`

Meaning:

> current overheat is at least +0.5 robust-z relative to recent same-lane T+1 history.

Direction:

> **negative strong-rate delta in 6 / 6 blocks**

Deltas:
- Discovery: -12.50 pp
- Validation: -25.00 pp
- Reserve: -9.09 pp
- Fresh Oct 1: -10.99 pp
- Fresh Oct 2: -10.10 pp
- Fresh Oct 3: -14.29 pp

Mean:
> **-13.66 pp**

This is materially different from the failed absolute S10E overheat band.

## Candidate B — low relative micro-volume ratio

`f_micro_volume_ratio_last_vs_prev10__pct128 <= 0.30`

Meaning:

> current micro-volume ratio is in the bottom 30% of the prior 128 S10D candidates.

Direction:

> **negative in 6 / 6 blocks**

Deltas:
- Discovery: -10.70 pp
- Validation: -2.38 pp
- Reserve: -17.65 pp
- Fresh Oct 1: -7.61 pp
- Fresh Oct 2: -7.43 pp
- Fresh Oct 3: -29.23 pp

Mean:
> **-12.50 pp**

## Other T+1 candidates with 6/6 negative direction

- `f_new_overheat_pressure__rz128 >= +0.5`
- `f_new_overheat_pressure__pct128 >= 0.70`
- `f_new_overheat_pressure__lpct64 >= 0.70`
- `f_micro_volume_ratio_last_vs_prev10__rz128 <= -0.5`

Interpretation:

> T+1 now has multiple independent normalized representations pointing in the same direction.

This is the strongest evidence produced by S10J-3.

---

# Lane 2

The most stable signal is not the old T+2 absolute taker-acceleration band.

## Candidate A — weak T+1 confirmation relative to regime

`t1_confirm_side_return_pct__rz128 <= -0.5`

This is causal for a later T+2 decision.

Direction:

> **negative in 6 / 6 blocks**

Deltas:
- Discovery: -0.22 pp
- Validation: -18.46 pp
- Reserve: -4.76 pp
- Fresh Oct 1: -0.86 pp
- Fresh Oct 2: -5.79 pp
- Fresh Oct 3: -0.77 pp

Mean:
> **-5.14 pp**

The effect is smaller than the best T+1 features but directionally stable.

## Candidate B — weak T+2 confirmation percentile

`t2_confirm_side_return_pct__pct128 <= 0.30`

Valid sample support exists in four blocks with sufficient hit/keep counts.

All four valid blocks are negative:
- Discovery: -10.26 pp
- Fresh Oct 1: -7.16 pp
- Fresh Oct 2: -33.33 pp
- Fresh Oct 3: -22.73 pp

Research Validation / Reserve have too few hits for this rule to be considered established.

Verdict:

> promising but not yet robust enough as a standalone rule.

## Important observation

The old T+2 `f_f_taker_accel_1m` absolute band is **not** recovered as a stable normalized suppressor.

That is desirable: it confirms that the catastrophic S10H inversion was not fixed simply by shifting the old threshold.

---

# Lane 3

Research sample size is small, so conclusions are weaker.

Best usable normalized candidate:

### High global relative micro-volume ratio

`f_micro_volume_ratio_last_vs_prev10__pct128 >= 0.70`

Five blocks have enough support and all five are negative:
- Discovery: -20.00 pp
- Reserve: -16.67 pp
- Fresh Oct 1: -19.51 pp
- Fresh Oct 2: -23.08 pp
- Fresh Oct 3: -5.15 pp

Research Validation has only two hits and is not counted as valid.

Another causal candidate:

`t3_confirm_side_return_pct__pct128 <= 0.30`

also shows negative direction in all four blocks with enough support.

Verdict:

> Lane 3 has potentially useful normalized suppressors, but sample support is much weaker than Lane 1.

---

# Comparison with failed absolute bands

The old absolute bands remain visibly regime-sensitive.

Examples:

### S10E overheat band

Research:
- Discovery: strongly loss-enriched
- Validation: strongly loss-enriched
- Reserve: loss-enriched

Fresh:
- Oct 1: **winner-enriched**
- Oct 2: only mildly loss-enriched
- Oct 3: only mildly loss-enriched

### T+2 taker-acceleration band

Research:
- Discovery: loss-enriched
- Validation: loss-enriched
- Reserve: loss-enriched

Fresh:
- Oct 1: **winner-enriched**
- Oct 2: **winner-enriched**
- Oct 3: **winner-enriched**

The normalized scan therefore validates the S10I diagnosis:

> narrow absolute bands were the wrong representation for a regime-sensitive suppressor.

---

# S10J-3 shortlist

## Highest-confidence

### T+1
1. High lane-relative overheat robust-z
2. Low global relative micro-volume ratio percentile

Both are negative in all six chronological blocks.

## Medium-confidence

### T+2
1. Low global robust-z of T+1 confirmation side-return
2. Low T+2 confirmation percentile

The first is directionally stable 6/6 but has modest effect size.
The second has stronger effect but insufficient research holdout support.

### T+3
1. High relative micro-volume ratio
2. Low relative T+3 confirmation return

Promising but research sample is small.

## Weak / unresolved

### T0
No candidate satisfies the same robustness standard.

Do not force a T0 suppressor yet.

---

# Verdict

> **S10J-1 to S10J-3 = PASS.**

We now have evidence that regime-normalized representations can recover stable winner-vs-noise direction that the old hard bands could not.

But:

> **no new veto has been accepted yet.**

This stage maps stable features only.

The correct next stage is:

> **S10J-4 — build a low-complexity Suppressor V2 using only the stable normalized signals, with explicit winner-retention and chronological-stability gates.**

Constraints for S10J-4:
- maximum 2–4 signals total;
- monotonic relative rules preferred;
- no narrow absolute bands;
- no T0 suppressor unless new evidence supports one;
- preserve S10D as base;
- V4.3 + BE0.10 remains frozen;
- S10H is development-only;
- a later unseen window is required for sealed validation after S10J is frozen.
