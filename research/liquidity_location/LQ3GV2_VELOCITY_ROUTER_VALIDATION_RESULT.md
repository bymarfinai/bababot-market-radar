# LQ-3G-V2 — Velocity Router Validation

Status: **PASS RESEARCH / PRODUCTION HOLD**

Version: `lq3gv2-velocity-router-validation-v1`

## Objective

LQ-3G-V showed that post-entry price velocity is materially more discriminative than the static entry feature family.

LQ-3G-V2 validates whether that velocity edge survives:

1. exact threshold replay on the authoritative frozen 209-trade OPEN_LANE matrix;
2. chronological TRAIN / VALIDATION / RESERVE splits;
3. neighboring-threshold perturbation;
4. a two-stage T+60s -> T+120s velocity state machine.

This stage does **not** change order authority.

This is also **not** a delayed-entry backtest. Historical realized PnL still belongs to the original entry. The router is interpreted as a post-entry state classifier until a separate action replay is performed.

---

## Important correction to the prior V1 discussion

The earlier ad-hoc V1 probe reported a rule approximately described as:

```
v_0_15s >= 0.00706 pp/s
AND
v_0_60s >= -0.000333 pp/s
```

with 66.67% WR in all three splits.

When LQ-3G-V2 re-ran the same logic from the authoritative frozen `main` CSV, that exact result did **not** reproduce.

Exact recheck:

| Split | N | Wins | WR |
|---|---:|---:|---:|
| TRAIN | 16 | 10 | 62.50% |
| VALIDATION | 10 | 6 | 60.00% |
| RESERVE | 4 | 3 | 75.00% |
| ALL | 30 | 19 | 63.33% |

The Reserve sample is only 4 and the surrounding threshold grid produced:

> **0 robust cells** satisfying the minimum-sample + >=60% requirement.

Therefore:

> the FAST15 + NO-COLLAPSE60 rule is **not frozen**.

The prior 66.67/66.67/66.67 result should be treated as superseded.

---

# Authoritative T+60s router

The earliest robust rule that survives the authoritative rerun is:

```
eta_to_nearest_supply_at_60s <= 1478.877 seconds
AND
time_to_MFE_within_first_60s >= 33.321 seconds
```

Interpretation:

- the trade is progressing toward nearby supply fast enough that the implied ETA is not extremely long;
- the best favorable excursion in the first minute occurs in the latter half of that minute, rather than as an immediate spike-and-fade.

Named:

> **EARLY60_CONFIRM**

## Exact result

| Split | N | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 22 | 14 | **63.64%** | **+$80.45** |
| VALIDATION | 13 | 8 | **61.54%** | **+$11.58** |
| RESERVE | 5 | 3 | **60.00%** | -$1.13 |
| ALL | **40** | **25** | **62.50%** | **+$90.90** |

Clean class mix ALL:

- Correct Runner: **22**
- Recovered Drawdown: **3**
- RTF: **10**
- True Wrong Direction: **2**
- Stall: **3**

Compared with the 209-trade OPEN_LANE baseline, this state strongly suppresses wrong-direction / no-edge trades.

However, the sample remains small.

Pooled Wilson 95% interval:

> **47.03% to 75.78%**

So the point estimate is above 60%, but statistical uncertainty remains material.

---

# T+60s threshold robustness

A local 8 x 6 perturbation grid was tested around:

- supply ETA threshold;
- time-to-MFE threshold.

Total cells:

> **48**

Cells that independently preserve:

- TRAIN n >=15
- Validation n >=5
- Reserve n >=5
- WR >=60% in all three splits

were:

> **14 / 48 = 29.17%**

So the T+60s edge is **not a one-cell accident**, but it is also not universally robust.

Examples:

### ETA <=1383s + time-to-MFE >=25s

- TRAIN: 16/24 = **66.67%**
- Validation: 8/13 = **61.54%**
- Reserve: 3/5 = **60.00%**
- ALL: 27/42 = **64.29%**

### ETA <=1479s + time-to-MFE >=33.321s

- TRAIN: **63.64%**
- Validation: **61.54%**
- Reserve: **60.00%**
- ALL: **62.50%**

This supports a real 60-second velocity/location family, but not yet production confidence.

---

# Authoritative T+120s strong confirmation

The strongest robust post-entry state is:

```
v_0_120s >= 0.0008457199 percentage-points/second
AND
eta_to_nearest_supply_at_60s <= 1383.3246 seconds
```

Equivalent 120-second net progress is roughly:

> **+0.1015% or better**

while retaining a reasonable supply-traversal ETA.

Named:

> **STRONG120_CONFIRM**

## Exact result

| Split | N | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 16 | 12 | **75.00%** | **+$89.29** |
| VALIDATION | 10 | 8 | **80.00%** | **+$15.79** |
| RESERVE | 5 | 4 | **80.00%** | **+$4.89** |
| ALL | **31** | **24** | **77.42%** | **+$109.97** |

Pooled Wilson 95% interval:

> **60.19% to 88.61%**

This is the first velocity-family result where the **pooled lower confidence bound itself is above 60%**.

Reserve is still only five trades, so this remains research, not production.

---

# T+120s robustness

Local threshold grid:

- 8 velocity thresholds;
- 7 supply-ETA thresholds.

Total:

> **56 cells**

Stable >=60% cells:

> **25 / 56 = 44.64%**

This is materially more robust than the T+60s family.

Examples:

### v120 >=0.0004 + ETA <=1800s

- TRAIN: **76.19%**
- Validation: **66.67%**
- Reserve: **80.00%**
- ALL: **73.68%**
- n = 38

### v120 >=0.0006196 + ETA <=1800s

- TRAIN: **80.00%**
- Validation: **66.67%**
- Reserve: **80.00%**
- ALL: **75.68%**
- n = 37

### Frozen STRONG120

- TRAIN: **75.00%**
- Validation: **80.00%**
- Reserve: **80.00%**
- ALL: **77.42%**
- n = 31

This is a coherent threshold family, not an isolated optimum.

---

# The most important state transition

The strongest finding in V2 is not merely a threshold.

It is the transition:

```
T+60s EARLY60_CONFIRM
        |
        +-- still STRONG at T+120s
        |      -> high-quality continuation
        |
        +-- fails T+120s upgrade
               -> decay / failure state
```

## EARLY60 -> STRONG120

Trades satisfying both states:

- N = **24**
- Wins = **20**
- WR = **83.33%**
- PnL = **+$106.05**

Split:

- TRAIN: 9/12 = **75.00%**
- Validation: 8/8 = **100.00%**
- Reserve: 3/4 = **75.00%**

Class mix:

- Correct / Recovered winners: **20**
- RTF: **4**
- True Wrong: **0**
- Stall: **0**

This is an exceptionally clean continuation state, though the Reserve sample is only four.

## EARLY60 but fails STRONG120 upgrade

Trades:

- N = **16**
- Wins = **5**
- WR = **31.25%**
- PnL = **-$15.15**

Class mix:

- winner: 5
- RTF: 6
- True Wrong: 2
- Stall: 3

This is the key new insight:

> **the failure to sustain velocity from minute 1 into minute 2 is highly adverse.**

It is much more informative than the static entry snapshot.

## T+120 strong without T+60 early confirm

- N = 7
- Wins = 4
- WR = **57.14%**

So the highest-quality path is not merely "positive at 120s."

It is:

> **early acceptable structure -> sustained velocity -> strong 120s confirmation.**

---

# Router interpretation

Research-only state machine:

```
OPEN_LANE entry
      |
      v
T+60 seconds
      |
      +-- EARLY60_CONFIRM
      |        |
      |        v
      |     T+120
      |        |
      |        +-- STRONG120_CONFIRM
      |        |      -> VELOCITY_STRONG
      |        |         historical final WR 83.33%
      |        |
      |        +-- FAIL UPGRADE
      |               -> VELOCITY_DECAY
      |                  historical final WR 31.25%
      |
      +-- NO EARLY CONFIRM
               |
               v
             T+120
               |
               +-- late strong -> weaker recovery lane
               +-- still weak  -> no confirmation
```

This is a **post-entry state classifier**.

It is not yet an executable decision rule.

---

# What V2 proves

## 1. Velocity matters

Yes.

The difference is not just static entry setup.

How the trade **develops through time** carries materially more information.

## 2. Recovery / sustained movement matters more than the first impulse alone

The stale FAST15 rule did not survive authoritative replication.

The robust signal comes from:

- path development through 60 seconds;
- sustained movement into 120 seconds;
- supply-traversal speed.

## 3. T+60 can identify an early focus group

EARLY60_CONFIRM:

> **62.5% pooled WR**

with all chronological split point estimates >=60%.

## 4. T+120 is much stronger

STRONG120_CONFIRM:

> **77.42% pooled WR**

with TRAIN / Validation / Reserve:

> **75% / 80% / 80%**

## 5. Velocity decay is highly adverse

EARLY60_CONFIRM that fails to remain STRONG at 120s:

> **31.25% WR**

This creates a promising future **loss-protection / early-close** research lane.

---

# Production decision

**HOLD.**

Reasons:

1. Reserve sample is still only five for the main frozen rules.
2. This study classifies positions after entry; it does not replay the PnL of delaying entry until T+60/T+120.
3. The router has not yet replayed a live action such as:
   - cut on T+120 decay;
   - keep on strong confirmation;
   - enter only after confirmation.

No order authority is changed.

---

# Recommended next stage

> **LQ-3G-V3 — Velocity Action Replay**

Use the frozen V2 states and replay actual actions.

Primary experiment:

1. original OPEN_LANE entry remains unchanged;
2. observe through T+60;
3. if EARLY60_CONFIRM, keep;
4. at T+120:
   - if STRONG120_CONFIRM -> continue under normal PP;
   - if EARLY60_ONLY_DECAY -> early-close;
5. compare against historical lifecycle.

Secondary experiment:

> delayed-entry at T+60 / T+120

using actual market price at the checkpoint, including fees/slippage, because the current V2 WR cannot be interpreted as delayed-entry WR.

Required outputs:

- exact WR;
- exact PnL;
- trade count;
- winner harm;
- RTF rescue / loss reduction;
- TRAIN / Validation / Reserve;
- comparison against historical and existing PP.

That is the correct bridge from **velocity classification** into **executable trading logic**.