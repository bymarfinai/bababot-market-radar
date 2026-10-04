# Market Detector Research State

Last frozen state: 2026-10-02

## Current Next Stage

WD-5H Stage 5A — Anti-Chase / Earlier Confirmation Redesign

Stage 4D is complete.

The exact frozen Stage 4C gate was replayed economically:

- horizon: T+3 minutes
- score threshold: 0.6028066188778062
- selected candidates: 62
  - validation: 37
  - historical test: 25

Delayed entry used the first actual Binance futures aggTrade at or after the
exact T0+3m timestamp, then applied the historical fee and slippage assumptions.

## Stage 4D Formal Result

DELAYED_ENTRY_ECONOMICS_NOT_READY

Overall delayed replay:

- META_WIN: 15
- META_LOSS: 45
- TIMEOUT: 2
- resolved precision: 25.0%
- all-TAKE WIN rate: 24.19%
- actual-exit net PnL: -$94.59
- standardized barrier net: -$75.09

Historical test only:

- META_WIN: 5
- META_LOSS: 18
- TIMEOUT: 2
- resolved precision: 21.74%
- all-TAKE WIN rate: 20.0%
- actual-exit net PnL: -$39.72
- standardized barrier net: -$32.59

## Main Mechanism Found

The T+3 classifier was accurately recognizing moves that were already in
progress, but the economic entry arrived after most of the original edge had
already been consumed.

Median selected-side move before delayed entry:

- all selected: +0.414%
- original META_WIN candidates: +0.450%

Relative to the original +0.5% Stage 3A META_WIN barrier:

- all selected had already consumed about 82.7% of the original barrier;
- original META_WIN candidates had already consumed about 89.9%.

Original META_WIN transitions after delayed entry:

- 15 remain META_WIN
- 25 become META_LOSS
- 1 becomes TIMEOUT

Therefore the current temporal gate is primarily a late confirmation / chase
detector rather than an economically usable entry trigger.

## Costs Are Not the Main Cause

A zero-fee / zero-slippage replay still fails:

- META_WIN: 22
- META_LOSS: 33
- TIMEOUT: 7
- resolved precision: 40.0%
- actual-exit net: -$36.38

The failure therefore persists even without execution costs.

## Runner Retention

Using conservative 60-minute close-based MFE:

- original >=1% runners: 36
  - retained after delay: 28 = 77.78%
- original >=2% runners: 19
  - retained after delay: 13 = 68.42%

The delay preserves some runners, but not enough to offset the large conversion
of original META_WIN into delayed losses.

## Early Resolution Trade-off

Across the final 40% historical population before T+3:

- early META_WIN: 39
- early META_LOSS: 142

Waiting three minutes does avoid many more fast failures than fast winners,
but the surviving high-score entries are too late economically under the
current gate.

## Decision

Do not proceed to Stage 4E fresh shadow with the current T+3 rule.

Do not deploy the Stage 4C gate.

Do not reinterpret the Stage 4C 65% historical resolved precision as a
tradeable WR.

The next research direction should preserve the temporal insight while
removing chase dependence:

- earlier confirmation;
- anti-chase cap / remaining-edge constraint;
- relative-strength / structure / flow evidence that does not require the
  selected-side price move itself to already be near the barrier.

Any redesigned rule will be research-only and will require fresh prospective
validation before production.

## Production State

UNCHANGED.

No Stage 4A-4D research rule has production authority.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE
- WD-5H Stage 3B — COMPLETE / WEAK
- WD-5H Stage 3C — REJECTED
- WD-5H Stage 4A — COMPLETE
- WD-5H Stage 4B — COMPLETE / PROMISING
- WD-5H Stage 4C — COMPLETE / PROMISING CLASSIFICATION ONLY
- WD-5H Stage 4D — COMPLETE / ECONOMICALLY REJECTED
- WD-5H Stage 4E — SKIPPED: current gate failed economic replay

## Parked

- Wallet/on-chain fusion.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/


---

## Profit Discovery Playbook

For the complete standalone Track A methodology and the replication protocol from LONG into SHORT, read:

- `research/PROFIT_DISCOVERY_PLAYBOOK_LONG_TO_SHORT.md`

This playbook is the authoritative methodology reference for winner anatomy, temporal confirmation, missed-winner recovery, full-universe replay, incremental efficiency, MFE spillover, and SHORT replication. Do not copy LONG thresholds mechanically into SHORT.

## PP V4-3B Giveback Window Anatomy — COMPLETE

- Baseline: Profit Protector V4.2 — Hybrid Protection.
- 62 triggered trades, 1,751 giveback events.
- 80% running-peak crossing recovered to a later new high in 79.19% of events; fixed 80% trailing is rejected.
- Recovery at 80% is regime-dependent: <1% peak 86.07%, 1–1.5% 62.50%, 1.5–3% 34.78%, >=3% 42.86%.
- Of 9 Stage3A RUNNER_TRIGGER_DELAY cases, 7 were temporally premature exits before a later higher peak; 2 were true post-final-peak delayed exits.
- At 80% crossing, final reversals were older and faster: median age 24.95s vs 10.13s transient; median downward velocity 0.0366 vs 0.0154 pp/s.
- Next: PP V4-3C Temporal Reversal Detector. Historical research only; no runtime authority.
