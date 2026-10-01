# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

WD-5H Stage 4 — Causal 1–3 Minute Confirmation Window

The static pre-entry meta-label program is closed.

Stage 3A fixed the target by replacing historical realized PnL with a
triple-barrier entry-quality label.

Stage 3B then showed only weak static ranking power.

Stage 3C tested whether a very selective TAKE/ABSTAIN threshold could still
extract a high-purity WIN pocket.

It could not.

## Stage 3C Formal Result

Primary architecture:
BASELINE_UNPURGED_UNWEIGHTED

Validation:
- no usable threshold reached 60% precision with >=10 resolved TAKEs;
- best usable threshold: 6 META_WIN / 11 resolved TAKEs = 54.55%.

Applying the same validation-frozen threshold to test:
- 1 META_WIN / 7 resolved TAKEs = 14.29%.

The 50% validation floor threshold:
- validation: 9/18 = 50.0%;
- same threshold test: 4/15 = 26.67%.

Purged+uniqueness sensitivity:
- no usable >=60% threshold;
- ultra-selective validation: 5/8 = 62.5%;
- same threshold test: 1/8 = 12.5%.

Formal status:

STATIC_HIGH_PRECISION_GATE_NOT_READY

## Decision

Do not proceed to Stage 3D end-to-end replay.

There is no validated static high-precision gate worth replaying.

Do not add more static indicators to this same entry snapshot in an attempt to
rescue the path.

The preferred next hypothesis is the causal 1–3 minute confirmation window,
because earlier WD-2/WD-3 research showed materially stronger separation after
the candidate signal appears.

## Production State

UNCHANGED.

No Stage 3A/3B/3C model or threshold has production authority.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE: META_LABEL_RESET_COMPLETE
- WD-5H Stage 3B — COMPLETE: META_RANKING_SIGNAL_WEAK
- WD-5H Stage 3C — COMPLETE: STATIC_HIGH_PRECISION_GATE_NOT_READY
- WD-5H Stage 3D — SKIPPED BY DESIGN: no usable gate to replay
- WD-5H Stage 3E — NOT APPLICABLE

## Parked

- Wallet/on-chain fusion.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
