# FTL-4 — Confirm -> Bounce/Retest -> SHORT

Status: **ARCHITECTURE PARTIAL PASS / PRODUCTION HOLD**

Date: 2026-10-06

## Objective

Test whether FTL-3 failed because confirmation was used as the actual SHORT entry price.

FTL-4 separates:

1. directional proof;
2. entry price.

Frozen upstream sequence:

- FTL-1 75s failure-to-launch candidate;
- FTL-2 distance veto;
- exact FTL-2 survivor IDs: **192**;
- exit: frozen BE0.18 with V4.3-LS / V4.2 runner handoff.

The new entry architecture is:

> downside confirmation -> do not enter -> wait for upward bounce/retest -> SHORT at the improved price.

A second lane also tested:

> downside confirmation -> bounce -> small failed-reclaim turn-down -> SHORT.

## Audit note

FTL-4 rebuilt the 75s anchor directly from raw Binance aggTrades and the exact FTL-2 survivor IDs.

The reconstructed BE0.18 baseline is:

- TRAIN: -$1.61
- VALIDATION: -$56.13
- RESERVE: -$26.72
- ALL: **-$84.46**

The prior authoritative FTL-2 result was:

- **-$82.9957**

Difference:
- **-$1.46 total**, about $0.0076 per trade.

The cohort IDs are exact, but the reconstructed raw-anchor execution path differs slightly from the earlier temporary checkpoint path. FTL-4 comparisons are internally self-consistent under the rebuilt raw-path contract.

This delta is small relative to the improvement magnitude, but it is retained as an audit caveat and production remains HOLD.

# FTL-4A — confirm then bounce-touch entry

Grid:

Downside confirmation from 75s anchor:
- 0.05%
- 0.10%
- 0.15%

Confirmation timeout:
- 30s
- 60s

Bounce from fresh local low after confirmation:
- 0.03%
- 0.05%
- 0.08%
- 0.10%

Retest timeout:
- 15s
- 30s
- 60s

Entry:
- first raw aggregate trade touching the bounce threshold.

Exit:
- BE0.18 frozen stack.

## Best robust-size candidate #1

Configuration:

> confirm -0.05% within 30s  
> then bounce +0.10% from post-confirm local low within 60s  
> then SHORT

Results:

| Split | Entries | WR | PnL | PF |
|---|---:|---:|---:|---:|
| TRAIN | 15 | 40.00% | **+$4.41** | 2.89 |
| VALIDATION | 16 | 31.25% | **-$1.86** | 0.63 |
| RESERVE | 9 | 33.33% | **+$1.68** | 2.63 |
| VAL + RESERVE | 25 | 32.00% | **-$0.18** | 0.97 |
| ALL | 40 | 35.00% | **+$4.23** | 1.50 |

Median total delay:
- ALL: ~31.4s after the 75s anchor.

Good/dead composition:
- 34 historical >=0.18%-MFE good candidates
- 6 dead candidates

The lane keeps only ~27% of the old-good population, so it is selective.

## Best robust-size candidate #2

Configuration:

> confirm -0.05% within 60s  
> bounce +0.10% within 60s  
> SHORT

Results:

| Split | Entries | WR | PnL | PF |
|---|---:|---:|---:|---:|
| TRAIN | 17 | 41.18% | **+$4.10** | 2.36 |
| VALIDATION | 24 | 29.17% | **-$4.05** | 0.48 |
| RESERVE | 11 | 45.45% | **+$3.94** | 4.82 |
| VAL + RESERVE | 35 | 34.29% | **-$0.11** | 0.99 |
| ALL | 52 | 36.54% | **+$3.99** | 1.34 |

Median total delay:
- ~39s.

This is the largest promising lane.

It transforms the full rebuilt baseline from roughly:

> **-$84.46**

to:

> **+$3.99**

by entering only 52 / 192 survivors.

However the combined untouched Validation + Reserve result remains essentially flat:

> **-$0.11**

Therefore it is not yet a proven positive out-of-sample edge.

## Robustness search

A robust-size rule was required to have approximately:
- TRAIN >=12-15 entries;
- VALIDATION >=15 entries;
- RESERVE >=8 entries.

Under that requirement:

> **No FTL-4A configuration was positive in BOTH Validation and Reserve.**

This is the decisive production gate.

Some tiny-sample configurations were positive across aggregate later slices, but with only ~4-10 trades and were rejected as non-actionable.

## Interpretation

FTL-4A materially improves economics compared with FTL-3.

FTL-3:

> confirm downside -> immediately SHORT lower

failed because confirmation consumed the edge.

FTL-4A:

> confirm downside -> wait for upward bounce -> SHORT higher

recovers entry quality.

This supports the execution hypothesis:

> confirmation should validate state, while the retest supplies the execution price.

The strongest tested bounce is relatively large:

> approximately **+0.10% from the local post-confirmation low**.

That bounce partly offsets:
- the confirmation distance already spent;
- modeled trading friction.

This is why the architecture can move full-sample economics from strongly negative toward breakeven/positive.

# FTL-4B — bounce plus failed-reclaim turn-down

A second grid added a final failure condition after the bounce:

- bounce completed;
- track bounce high;
- require price to fall:
  - 0.02%
  - 0.03%
  - 0.05%
  from the bounce high;
- within:
  - 15s
  - 30s;
- then SHORT.

## Result

The extra failed-reclaim confirmation did **not** improve robustness.

Best robust-size FTL-4B lane:

> confirm -0.10% <=60s  
> bounce +0.05% <=60s  
> fail/retrace -0.03% <=30s  
> SHORT

Results:

| Split | Entries | WR | PnL |
|---|---:|---:|---:|
| TRAIN | 12 | 33.33% | **+$2.03** |
| VALIDATION | 17 | 35.29% | **-$3.70** |
| RESERVE | 9 | 44.44% | **-$0.55** |
| VAL + RESERVE | 26 | 38.46% | **-$4.25** |
| ALL | 38 | 36.84% | **-$2.22** |

No robust-size FTL-4B configuration was positive in both Validation and Reserve.

The extra turn-down requirement therefore reintroduces the same problem:

> wait for additional confirmation -> surrender entry quality again.

## FTL-4 verdict

### FTL-4A

**Architecture: PASS**

The confirm-then-bounce concept is substantially better than immediate confirm-then-SHORT.

It is the first tested SHORT-entry architecture in this branch that:
- produces positive TRAIN;
- positive Reserve;
- positive full rebuilt sample;
- brings combined Validation+Reserve to essentially breakeven.

### Production: HOLD

Because:
- Validation remains negative;
- Validation+Reserve is slightly negative;
- no robust-size configuration is independently positive in both Validation and Reserve;
- reconstructed anchor audit differs by $1.46 from the prior temporary-checkpoint baseline.

### FTL-4B

**FAIL**

Adding a failed-reclaim turn-down after the bounce does not help.

## Current best architecture

The most promising shape is:

> FTL 75s candidate  
> -> FTL-2 veto  
> -> downside confirmation about -0.05%  
> -> wait for bounce about +0.10% from fresh low  
> -> SHORT at bounce touch  
> -> BE0.18 / V4.3 / V4.2 protection

Do **not** add another turn-down confirmation after the bounce.

## Recommended next stage

Freeze one FTL-4A rule before any new sample:

Candidate:

> confirm -0.05% within 30s  
> bounce +0.10% within 60s  
> SHORT  
> BE0.18 stack

Then forward-test it on genuinely later trades.

The research question is no longer whether reversal SHORT is possible.

It is whether this confirm-then-retest architecture remains near or above breakeven on a new chronological cohort without threshold changes.
