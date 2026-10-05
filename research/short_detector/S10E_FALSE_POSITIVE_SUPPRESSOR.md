# SHORT-S10E — False-Positive Suppressor

Status: **PASS — research false-positive suppressor / no production authority**

## Objective

Start from the S10D high-coverage frontier:

> **364 OPEN → 85 / 99 strong WIN → 279 non-target**

and remove as many non-target selections as possible while retaining at least approximately **95% of the 85 captured strong winners**.

Primary retention gate:

> retain at least **81 / 85 strong WIN**

## Search design

S10E uses only T0 features available before entry.

Feature hygiene follows the prior SHORT T0 research:
- 224 modeled T0 fields
- infrastructure / latency / clock fields excluded
- Discovery and Validation used for threshold search
- veto candidates constrained to lose at most:
  - 2 / 51 Discovery strong winners
  - 1 / 22 Validation strong winners

The per-feature candidate objective maximizes stable non-target removal across Discovery and Validation.

Reserve is then audited.

Important caveat:
- Reserve had already been observed in earlier SHORT stages;
- the final operating candidate below was selected after count and protected-PnL frontier inspection.

Therefore S10E is a **research frontier**, not a newly sealed holdout result.

## Single-veto scan

155 evaluable T0 veto candidates survived the D/V winner-retention constraints.

Several useful frontiers emerged.

### Maximum-prune candidate

`f_f_oi_change_30m_pct in [-0.1138785521, +0.0329207349]`

Veto:
- 54 trades
- 50 non-target
- 4 strong WIN

Keep:
> **310 OPEN → 81 strong WIN → 229 non-target**

Strong retention:
- 81 / 85 = **95.29%**

Protected PnL:
- **+$53.65**

This removes the most non-targets among the ≥95%-retention single-rule candidates, but sacrifices one winner in Validation and one in Reserve.

### Safe-prune candidate

`f_micro_rejection_wick_last in [0.04, 0.1666666667]`

Veto:
- 47 trades
- 45 non-target
- 2 strong WIN

Keep:
> **317 OPEN → 83 strong WIN → 234 non-target**

Strong retention:
- 83 / 85 = **97.65%**

No Validation or Reserve strong winner is removed.

Protected PnL:
- **+$65.71**

### Best economics / accepted research candidate

`f_new_overheat_pressure in [4.0018436068809455, 4.470349182901625]`

Action:

> **VETO selection when T0 overheat pressure is inside this band**

Veto:
- **33 trades**
- **31 non-target**
- **2 strong WIN**
- historical PnL of vetoed cohort: **-$76.30**
- protected PnL of vetoed cohort: **-$29.09**

The vetoed cohort has only:
- 4 historical realized-positive trades
- 6 protected-positive trades

## Accepted S10E result

Before:

> **364 OPEN → 85 strong WIN → 279 non-target**

After overheat-pressure veto:

> **331 OPEN → 83 strong WIN → 248 non-target**

Metrics:
- strong retention: **83 / 85 = 97.65%**
- global strong-WIN recall: **83 / 99 = 83.84%**
- precision: **25.08%**
- historical realized-positive: 92
- historical WR: **27.79%**
- historical PnL: **-$264.95**

Relative to S10D:
- OPEN: 364 → **331**
- strong WIN: 85 → **83**
- non-target: 279 → **248**
- non-target removed: **31**
- precision: 23.35% → **25.08%**

## Split anatomy

### Discovery

Veto:
- 23 trades
- 21 non-target
- 2 strong WIN

Keep:
> **197 OPEN → 49 strong WIN → 148 non-target**

Protected:
- **+$79.77**

### Validation

Veto:
- 5 trades
- **5 non-target**
- **0 strong WIN**

Keep:
> **64 OPEN → 22 strong WIN → 42 non-target**

Protected:
- **+$12.72**

### Reserve

Veto:
- 5 trades
- **5 non-target**
- **0 strong WIN**

Keep:
> **70 OPEN → 12 strong WIN → 58 non-target**

Protected:
- **-$18.01**

The veto therefore removes zero strong winners from both chronological holdouts.

## Removed strong winners

Only two strong winners are sacrificed, both from Discovery:

1. HBAR
   - historical PnL: +$1.49
   - MFE: 1.07%
   - protected PnL: +$1.43

2. JUP
   - historical PnL: +$6.39
   - MFE: 2.64%
   - protected PnL: +$6.24

No Validation or Reserve strong winner is sacrificed.

## Best-protector economics

Protector:

> **V4.3 SHORT-LS4 + BE0.10 on NO_ACTION**

### S10D baseline

- 364 trades
- 140 protected-positive
- protected WR: 38.46%
- protected PnL: **+$45.39**

### S10E accepted

- 331 trades
- 134 protected-positive
- protected WR: **40.48%**
- protected PnL: **+$74.47**

Delta:

> **+$29.09 protected PnL**

Improvement:
- approximately **+64%** versus S10D protected PnL

Chronological protected PnL:

| Split | S10D | S10E |
|---|---:|---:|
| Discovery | +$60.91 | **+$79.77** |
| Validation | +$12.81 | **+$12.72** |
| Reserve | -$28.33 | **-$18.01** |
| Total | +$45.39 | **+$74.47** |

So:
- Discovery improves materially;
- Validation is essentially unchanged;
- Reserve loss improves by about **+$10.32**.

## Union-veto check

The accepted overheat-pressure rule was combined with other D/V-frozen veto candidates.

Result:

> no multi-rule union improves the D+V frontier while preserving the same winner-retention gate.

The simple one-rule veto is therefore preferred over a more complex suppressor.

## Current SHORT research frontier

### High-coverage S10D

> **364 OPEN → 85 / 99 strong WIN → 279 non-target**

Protected:
> **+$45.39**

### S10E accepted operating research point

> **331 OPEN → 83 / 99 strong WIN → 248 non-target**

Protected:
> **+$74.47**

### Maximum-prune alternative

> **310 OPEN → 81 / 99 strong WIN → 229 non-target**

Protected:
> **+$53.65**

Thus the best current balance is S10E overheat-pressure veto:
- retains substantially more strong winners than maximum-prune;
- produces the highest protected PnL;
- removes no strong winners in Validation/Reserve.

## Verdict

> **SHORT-S10E = PASS as the current best research operating point.**

Carry forward:

> **331 OPEN → 83 / 99 strong WIN → 248 non-target → +$74.47 protected PnL**

The next stage should be:

> **SHORT-S10F — Final Efficient Frontier / Execution-Realistic Validation**

S10F should compare:
- S10C
- S10D
- S10E accepted
- S10E maximum-prune

under execution-realistic entry timing and the frozen V4.3 + BE0.10 protector before any runtime promotion.
