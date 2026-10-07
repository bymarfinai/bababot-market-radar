# LQ-3D — Open-Lane Admission + Profit-Protection Replay

Status: **ADMISSION PARTIAL PASS / GOOD-ISOLATION FAIL / PP-V2 TARGET-60 FAIL**

Version: `lq3d-open-lane-admission-pp-v1`

## Objective

LQ-3C found a structurally healthier LONG context:

> **OPEN_LANE = nearest demand >=3% below entry AND not inside active 5m/15m supply**

OPEN_LANE improves MFE and runner probability, but historical WR is still only about 30%.

LQ-3D tests two separate hypotheses:

1. **Admission hypothesis**  
   Can GOOD trades be isolated from BAD trades inside OPEN_LANE using causal entry-time features?

2. **Profit-protection hypothesis**  
   Can the current frozen PP Decision V2 hybrid rescue enough RIGHT_THEN_FAILURE (RTF) trades to lift the selected cohort toward the target WR >60%?

No production authority is changed.

---

## Base OPEN_LANE universe

LQ-3C OPEN_LANE:

- total trades: **209**
- GOOD = Recovered + Correct Runner: **63**
- BAD = True Wrong Direction + Stall: **70**
- RTF = **76**

The central problem is therefore not only BAD admission.

RTF alone is larger than either GOOD or BAD.

---

# LQ-3D-A — Admission separation

## GOOD vs BAD separation

The strongest robust entry-time family combined:

> `f_micro_consecutive_selected_bars <= 2`

and

> `f_gate_side_adjusted_drift_pct <= 0.06782%`

This is a **not-overextended** entry profile:

- no long streak of same-direction micro bars;
- very small gate-time drift;
- OPEN_LANE location already satisfied.

### Selected cohort

| Split | N | GOOD | BAD | RTF | GOOD/(GOOD+BAD) | Historical WR |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 44 | 15 | 6 | 23 | **71.43%** | 34.09% |
| VALIDATION | 19 | 9 | 2 | 8 | **81.82%** | 47.37% |
| RESERVE | 13 | 4 | 2 | 7 | **66.67%** | 30.77% |
| ALL | **76** | **28** | **10** | **38** | **73.68%** | **36.84%** |

### Interpretation

This rule is a real separator of:

> **GOOD vs BAD**

BAD falls from 70 / 209 in the broad OPEN_LANE universe to only:

> **10 / 76**

while 28 GOOD remain.

So the admission layer is doing useful work.

However, RTF becomes the dominant remaining population:

> **38 / 76 = 50% of the selected cohort**

This is why realized WR remains only 36.84%.

---

## Can GOOD be isolated directly from all non-GOOD at entry?

A second scan explicitly treated:

- GOOD = positive class
- BAD + RTF = negative class

using only causal entry-time features.

Result:

> **FAIL**

Best univariate AUC:

> **0.5929**

No two-feature rule satisfying the minimum sample contract could achieve:

> **WR >=60% in TRAIN + VALIDATION + RESERVE simultaneously**

Stable >=60% rules found:

> **0**

This is the critical result.

### Why GOOD-vs-BAD looked strong but realized WR did not

RTF resembles GOOD at entry.

The detector frequently identifies a trade that really does have favorable directional opportunity, but the path later decays and gives the move back.

Therefore:

```
GOOD vs BAD
    -> separable

GOOD vs RTF
    -> heavily overlapping at entry
```

So adding more entry-time thresholds is unlikely to solve the entire WR problem.

---

# LQ-3D-B — Frozen PP replay

## Was RTF already profit-protected historically?

Yes.

The original Stage12-v3 lifecycle already applied profit-protection logic to these trades.

For the broader OPEN_LANE RTF population, last evaluations overwhelmingly show reasons such as:

- `gave_back_all_profit`
- `major_mfe_giveback`
- `small_mfe_giveback`

So RTF is **not** a case of "no profit protector existed."

The issue is:

> the old protector often reacts only after a large giveback has already occurred.

The newer PP Decision V2 is more aggressive, but in this historical period it was a **shadow layer**, not execution authority.

---

## Replay contract

The frozen PP Decision V2 is:

> **V1 base contract + fast-decay overlay**

V2 can only escalate V1.

Replay uses the exact stored:

> `pp_decision_v2_observations`

rather than 5-minute position evaluations, because 5-minute evaluations can miss intrabar MFE peaks and giveback timing.

Replay semantics match the existing Stage6 validation implementation:

- REDUCE = 50% of remaining size
- a later REDUCE while already reduced escalates to CLOSE through the frozen policy
- fees and configured slippage are included
- if no PP action closes the full position, remaining size settles at the historical exit

### Coverage

Selected admission cohort:

> **76 trades**

Fast-shadow coverage:

> **52 / 76 = 68.42%**

The remaining 24 trades are not imputed or extrapolated.

---

## Covered-sample economics

| Mode | Wins | WR | Net PnL |
|---|---:|---:|---:|
| Historical control | 21 / 52 | **40.38%** | **-$27.09** |
| PP V1 replay | 21 / 52 | **40.38%** | **-$11.23** |
| **PP V2 hybrid replay** | **23 / 52** | **44.23%** | **-$0.06** |

V2 materially improves PnL capture.

But it does **not** solve the target-WR problem.

---

## Chronological PP replay

### TRAIN

- n = 20
- historical WR = 40.0%
- V1 WR = 40.0%
- **V2 WR = 50.0%**
- V2 PnL = **+$14.23**

### VALIDATION

- n = 19
- historical WR = 47.37%
- V1 WR = 42.11%
- V2 WR = **47.37%**
- V2 PnL = -$6.95

### RESERVE

- n = 13
- historical WR = 30.77%
- V1 WR = **38.46%**
- V2 WR = **30.77%**
- V2 PnL = -$7.34

There is no stable transport to >60%.

---

# RTF rescue rate

Covered RTF:

> **26 trades**

Historical:

- wins = 0
- PnL = -$44.95

PP V1:

- converted wins = **2 / 26**
- WR = **7.69%**
- PnL = -$32.36

PP V2:

- converted wins = **4 / 26**
- WR = **15.38%**
- PnL = -$25.29

V2 is better than V1, but the rescue rate is far below what is required.

---

# Winner preservation

A profit protector cannot be judged only on RTF rescue.

It must also avoid damaging genuine winners.

### RECOVERED_DRAWDOWN

Covered:

- n = 14
- historical wins = 14
- V1 wins = 14
- V2 wins = **14**
- V2 PnL = **+$52.53**

Good.

### CORRECT_RUNNER

Covered:

- n = 7
- historical wins = **7**
- V1 wins = **5**
- V2 wins = **5**

So the current PP family also converts:

> **2 / 7 Correct Runners into non-winning outcomes**

within the covered sample.

This winner harm matters when targeting WR >60%.

---

# Math required for 60% WR

The admission-selected cohort has:

- total = **76**
- historical winners = **28**
- RTF = **38**
- BAD = **10**

To reach at least 60% WR:

> need **46 winners**

Therefore:

> need **18 additional net winners**

If no current winner were harmed, that requires converting:

> **18 / 38 RTF = 47.37%**

of all RTF into positive realized outcomes.

Observed PP V2 conversion on the covered RTF sample is:

> **4 / 26 = 15.38%**

That is not close enough.

And because V2 can also harm Correct Runners, the actual required gross rescue rate would be even higher.

---

# Can GOOD and RTF separate after entry?

Yes, somewhat.

Unlike entry-time features, temporal behavior begins to separate them.

GOOD vs RTF:

| Feature | AUC |
|---|---:|
| **T+3 selected slope5 norm** | **0.687** |
| **T+2 side return** | **0.675** |
| **T+3 side return** | **0.673** |
| T+3 VWAP extension | 0.668 |
| T+3 selected taker share | 0.646 |
| T+2 selected taker share | 0.642 |

Example medians:

- GOOD T+2 side return: **+0.200%**
- RTF T+2 side return: **-0.014%**

- GOOD T+3 side return: **+0.291%**
- RTF T+3 side return: **+0.054%**

This is meaningful, but still only moderate discrimination.

It suggests the next edge is not another static entry filter.

It is:

> **detecting the transition from genuine continuation into RTF decay as early as possible.**

---

# Final LQ-3D verdict

## 1. Location helped

OPEN_LANE remains a useful structural prerequisite.

## 2. Entry admission helped remove BAD

The frozen admission profile:

```
OPEN_LANE
AND consecutive selected micro bars <=2
AND gate drift <=0.06782%
```

produces:

> **73.68% GOOD among GOOD+BAD**

across all splits.

So BAD admission can be improved.

## 3. GOOD cannot be cleanly isolated from RTF at entry

GOOD-vs-all entry-time discrimination is weak:

> best AUC **0.593**

Stable >60% entry rule:

> **none**

Therefore RTF is not primarily an entry-recognition problem.

## 4. Current PP V2 is not enough

Covered-sample WR:

> **40.38% -> 44.23%**

RTF rescue:

> **15.38%**

Required RTF conversion for 60% target:

> **at least 47.37% if no winner harm**

Therefore:

> **PP Decision V2 fails the target-60 gate.**

## 5. The remaining problem is now sharply defined

The main unresolved population is:

> **RTF inside otherwise-good OPEN_LANE admission**

These trades look sufficiently similar to genuine winners at entry, move favorably, and only then begin to decay.

---

# Recommended next stage

**LQ-3E — RTF Temporal Decay / Profit-Lock Timing**

Freeze the 38 RTF from the LQ-3D admission cohort and compare them against the 28 GOOD.

Goal:

1. find the earliest causal point where RTF diverges from GOOD;
2. identify whether T+1 / T+2 / T+3 price, slope, flow, CLV, VWAP extension or decay gives a robust warning;
3. convert that warning into a profit-lock / early-close rule;
4. explicitly optimize:
   - RTF conversion rate;
   - Correct Runner preservation;
   - final WR;
   - final PnL;
5. require transport through TRAIN / VALIDATION / RESERVE.

Target:

> **>=60% realized WR without sacrificing the runner population to get there.**

No production trading authority is changed by LQ-3D.