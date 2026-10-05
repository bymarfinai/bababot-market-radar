# SHORT-S10B — Router Error Recovery

Status: **COMPLETE — NO PASS / KEEP ROUTER FROZEN**

## Objective

Recover the **5 strong SHORT winners** that are true Lane 1 anatomically but were routed to Lane 0 by the frozen S8 outcome-blind router.

S10A baseline remains:

> **655 → 268 OPEN → 51 / 99 strong WIN → 217 non-target**

The 48 missed strong winners after S10A were:
- true Lane 0 / no selector: 28
- routed Lane 1 but no causal T+1/T+2/T+3 threshold crossing: 15
- router error true Lane 1 → routed Lane 0: **5**

## Anatomy of the 5 strong router errors

| Symbol | Split | Router P(L1) | Same-threshold causal evidence |
|---|---|---:|---|
| SKR | Discovery | 0.326 | no T+1/T+2/T+3 crossing |
| ONDO | Discovery | 0.147 | T+2 only |
| AKE | Validation | 0.307 | T+1 and T+3 |
| RAYSOL | Validation | 0.096 | T+1/T+2/T+3 |
| ROBO | Validation | 0.460 | T+1 and T+3 |

Four of five show at least one causal crossing of the frozen Lane-1 threshold, but a simple low-confidence override is too noisy.

## Bounded correction candidate

To avoid lowering the global router cutoff, S10B tested a bounded secondary override:

> current route = Lane 0  
> AND router P(Lane1) >= **0.25**  
> AND at least **2** causal T+1/T+2/T+3 snapshots satisfy the existing frozen threshold  
> `confirm_side_return_pct >= +0.0338983050847%`

No new feature and no new temporal threshold are introduced.

The 0.25 + repeated-confirmation candidate was used because its anatomy correction precision was:
- Discovery: 4 true-L1 corrections / 8 labeled overrides = **50%**
- Validation: 3 / 3 = **100%**
- Reserve: 2 / 3 = **66.7%**

So it does not degrade routing anatomy in Discovery and improves it in both holdouts.

## Full 655 detector replay

### S10A baseline

> **268 OPEN → 51 strong WIN → 217 non-target**

- precision: 19.03%
- realized-positive: 63
- historical PnL: -$339.81
- peak-MFE equivalent: $1,013.42

### S10B bounded override diagnostic

> **284 OPEN → 55 strong WIN → 229 non-target**

Increment:
- **+16 OPEN**
- **+4 strong WIN**
- **+12 non-target**
- marginal cost: **4.00 entries / added strong WIN**
- incremental historical PnL: **+$15.09**
- incremental realized-positive: 5
- incremental peak-MFE equivalent: +$114.48

But only:

> **2 of the +4 strong winners are actual router-error recoveries**

The other 2 are true Lane-0 strong winners, so the patch leaks into the S10C population.

## Split behavior

### Discovery
- S10A: 160 OPEN / 33 strong WIN / -$203.30
- candidate: 170 OPEN / 35 strong WIN / -$185.11
- increment: +10 OPEN / +2 strong WIN / +$18.18

However both added strong winners are **true Lane-0 winners**, not router-error winners.

The Discovery PnL improvement is heavily driven by one trade:
- FLOCK: historical +$23.04

### Validation
- S10A: 47 OPEN / 11 strong WIN / -$36.84
- candidate: 50 OPEN / 13 strong WIN / -$37.45
- increment: +3 OPEN / +2 strong WIN / -$0.61

Both added strong winners are genuine router errors:
- AKE
- ROBO

### Reserve
- S10A: 61 OPEN / 7 strong WIN / -$99.67
- candidate: 64 OPEN / 7 strong WIN / -$102.15
- increment: **+3 OPEN / +0 strong WIN / -$2.48**

No Reserve strong winner is recovered.

## Why S10B is rejected

The candidate looks acceptable in aggregate, but the actual router-error recovery does not generalize:

1. **Discovery recovers zero of the strong router-error winners.**
2. Validation recovers two strong router errors.
3. Reserve adds three entries and zero strong winners.
4. Two of four added strong winners belong to the true Lane-0 population, contaminating the next recovery stage.
5. Aggregate PnL improvement is largely Discovery/outlier-driven.
6. Recovering all four temporal-crossing router errors would require materially broader overrides and substantially more noise.

Therefore:

> **SHORT-S10B = NO PASS.**

Do not lower the global router cutoff and do not promote a router override.

## Accepted baseline remains

> **S10A: 655 → 268 OPEN → 51 / 99 strong WIN → 217 non-target**

Remaining missed strong winners remain:
- true Lane 0 / no accepted selector: **28**
- routed Lane 1 with no causal same-threshold crossing: **15**
- router errors: **5**

Total:

> **48 missed strong WIN**

## Next stage

Proceed to **SHORT-S10C — Lane 0 Recovery**.

This is the largest remaining recoverable population and should be handled as its own selector/veto problem rather than by weakening the already-stable router.
