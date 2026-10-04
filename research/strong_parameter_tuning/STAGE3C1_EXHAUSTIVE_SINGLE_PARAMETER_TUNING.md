# Stage 3C.1 — Exhaustive Single-Parameter Tuning

## Frozen target

- universe: **1,236 resolved LONG trades**
- target: **245 trades** satisfying BOTH `META_WIN` and historical maximum MFE >= 1.00%
- non-target: 991
- Discovery: 741 / 162 targets
- Validation: 247 / 45 targets
- sealed Reserve: 248 / 38 targets

The target definition is unchanged from Stage 3B.

## What was tuned

The original T0 feature set contains 231 `f_*` fields. Seven time / infrastructure-latency fields remain excluded, leaving **224 T0 parameters**:

- 210 numeric
- 14 categorical

For each numeric parameter, Stage 3C.1 evaluates:

- `x <= threshold`
- `x >= threshold`
- contiguous sweet-spot bands `low <= x <= high`

The numeric sweep uses the exact observed Discovery value boundaries, not a small hand-picked threshold list.

For categorical features, state rules are evaluated; low-cardinality fields also evaluate state subsets.

Candidate count:

- **32,275,307 numeric rules**
- **72 categorical rules**
- **32,275,379 total candidate rules**

## Selection protocol

1. Candidate boundaries are generated from Discovery only.
2. For each feature, a rule is selected for positive stability across Discovery + Validation.
3. The rule is then frozen.
4. Sealed Reserve is evaluated only after the rule has been frozen.
5. Reserve must never be used to retune the threshold.

Association metric is phi / point-biserial correlation between the binary rule-selected flag and the binary target label.

Preferred STRONG rule requirement remains `|r| >= 0.50` consistently. Small-support pockets must not be called strong simply because their precision is high.

## Result

**NO STRONG SINGLE-PARAMETER RULE FOUND.**

Key ceilings:

- best Discovery-only rule: `f_f_market_dispersion_15m`, r = **0.214**; it collapses in Validation
- best Discovery+Validation stability score among numeric rules: about **0.146**
- no one-parameter rule reaches r >= 0.50
- no one-parameter rule is close to the strong threshold on sealed Reserve

### Examples after tuning

#### Relative strength

`f_f_coin_minus_market_30m`

- tuned band: **2.9192 to 4.4262**
- Discovery: 52 selected / 20 targets, precision 38.5%, r = 0.110
- Validation: 20 / 8, precision 40.0%, r = 0.167
- Reserve: 17 / 5, precision 29.4%, r = 0.106
- Reserve historical PnL: **-$2.83**
- Reserve avg realized return/trade: **-0.033%**

This is one of the more stable market-parameter sweet spots, but it is still weak and low recall.

#### OI

`f_new_oi_per_price`

- tuned band: **1.3752 to 2.8068**
- Discovery r = 0.115
- Validation r = 0.116
- Reserve r = 0.084
- Reserve: 10 selected / 3 targets
- Reserve historical PnL: **-$3.89**
- Reserve avg realized return/trade: **-0.078%**

#### Volume

`f_micro_volume_ratio_last_vs_prev10`

- tuned band: **1.654x to 3.111x**
- Discovery r = 0.083
- Validation r = 0.085
- Reserve r = 0.027
- Reserve: 46 selected / 8 targets
- Reserve historical PnL: **-$57.52**
- Reserve avg realized return/trade: **-0.250%**

So tuning volume from a fixed value such as 2x to other values does not reveal a strong stable sweet spot.

#### Tiny-support warning

`f_gate_approval_age_s` has a narrow **6.863–6.933 s** band with r around 0.136 / 0.156 / 0.158 across D/V/R, but Reserve support is only **3 trades / 2 targets**. It is an operational/timing feature with negligible coverage and must not be treated as the desired market detector.

## Interpretation

Stage 3C.1 materially strengthens the conclusion from Stage 3B:

- weak raw linear correlation was not merely caused by using the wrong obvious threshold
- one-by-one nonlinear threshold/band tuning does uncover sweet spots
- those sweet spots remain weak, low-coverage, unstable, or economically poor
- therefore the missing separation is not solved by tuning any single existing T0 parameter

Stage 3C.1 is **FAIL as a source of a strong single-parameter detector**.

The stable sweet spots may still be useful as ingredients for **Stage 3C.2 — multi-parameter combination tuning**, where interactions such as volume band + OI band + relative strength + taker state can be tested without changing the frozen 245/1,236 target contract.
