# Market Detector Research State

Last frozen state: 2026-10-02

## Current Next Stage

WD-5H Stage 4D — Delayed-Entry Economic Replay

Stage 4C is complete.

The formal validation-only temporal gate selected:

- horizon: T+3 minutes
- score threshold: 0.6028066188778062
- validation precision floor: 80%

Validation result:

- TAKE: 37
- resolved TAKE: 35
- META_WIN: 28
- META_LOSS: 7
- TIMEOUT: 2
- resolved precision: 80.0%
- all-TAKE WIN rate including TIMEOUT: 75.68%
- eligible coverage: 10.57%

Same frozen rule on historical test:

- TAKE: 25
- resolved TAKE: 20
- META_WIN: 13
- META_LOSS: 7
- TIMEOUT: 5
- resolved precision: 65.0%
- all-TAKE WIN rate including TIMEOUT: 52.0%
- eligible coverage: 7.37%

Formal Stage 4C status:

TEMPORAL_HIGH_PRECISION_GATE_NOT_READY

The rule missed the frozen promotion criterion because test all-TAKE WIN rate
was below 55%, even though resolved precision reached 65%.

## Why Stage 4D Still Matters

Stage 4C is materially stronger than the static path.

At T+3 the historical test survivor base rates were:

- resolved META_WIN prevalence: 74 / 278 = 26.62%
- all eligible WIN rate including TIMEOUT: 74 / 339 = 21.83%

The selected 4C rule lifts these to:

- resolved precision: 65.0% (about 2.44x base)
- all-TAKE WIN rate: 52.0% (about 2.38x base)

This is strong enough to justify an economic replay, but not production
promotion.

Stage 4D must answer whether entering only after T+3 confirmation still has
positive economics after:

- delayed market entry price;
- historical fee/slippage assumptions;
- missed early winners;
- changed TP/SL reachability from the delayed entry;
- runner loss / opportunity cost.

## Production State

UNCHANGED.

Stage 4C has no production authority.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE
- WD-5H Stage 3B — COMPLETE / WEAK
- WD-5H Stage 3C — REJECTED
- WD-5H Stage 3D — SKIPPED
- WD-5H Stage 3E — NOT APPLICABLE
- WD-5H Stage 4A — COMPLETE
- WD-5H Stage 4B — COMPLETE / PROMISING
- WD-5H Stage 4C — COMPLETE / PROMISING BUT NOT READY

## Stage 4D Constraint

Stage 4D must replay the exact frozen 4C rule.

Do not retune:

- horizon;
- model features;
- score threshold;
- survivor definition.

Stage 4D is allowed to compare economic accounting variants, but the gate
itself is frozen.

Fresh prospective Stage 4E data remains mandatory before any production
promotion.

## Parked

- Wallet/on-chain fusion.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
