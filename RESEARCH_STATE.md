# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

**WD-5H Stage 3B — Purged Meta-Model + Overlap Uniqueness Weighting**

Stage 3A is complete. The frozen primary meta-label is:

- side: existing primary LONG/SHORT candidate;
- entry origin: actual historical paper entry;
- path: causal 1m close-confirmed;
- upper barrier: net +0.5%;
- lower barrier: net -0.5%;
- vertical barrier: 30 minutes;
- economics include historical fee/slippage assumptions.

Primary labels across 2,175 trades:

- META_WIN: 564
- META_LOSS: 1,327
- TIMEOUT: 284

No Stage 3B rule has production authority.

## Production State

UNCHANGED.

The production runtime does not import code from research/.

## Supported Findings

1. Overheat is useful as a risk/exhaustion signal.
2. TRUE_WRONG_DIRECTION is structurally different from RIGHT_THEN_FAILURE.
3. OVERHEATED does not imply the opposite side should be traded.
4. Conditional reversal can work inside known true-wrong cases, but is not
   safe as a universal action.
5. Static pre-entry features did not support a stable 70%+ selective
   historical-realized-WIN gate.
6. Historical realized PnL mixed entry quality and lifecycle/exit quality.
7. Stage 3A confirms that triple-barrier relabeling materially changes the
   target:
   - 160/660 RIGHT_THEN_FAILURE become META_WIN;
   - 768/849 TRUE_WRONG become META_LOSS;
   - 205 historical non-positive trades become META_WIN;
   - 63 historical positive trades become META_LOSS.
8. Outcome-window overlap is severe: median average concurrency is about 15.4
   and aggregate uniqueness mass is about 166 across 2,175 rows. Stage 3B
   therefore must use purging/embargo and uniqueness weighting.

## Rejected / Not Production-Ready

- WD-5B static pre-entry reversal discriminator.
- WD-5F as a universal reversal gate.
- WD-5G full Health + universal Reversal policy.
- WD-5H Stage 2 flat historical-realized-WIN classifier.
- WD-5H Stage 2 hierarchical static historical-realized-WIN gate.
- Adding more static indicators to the old realized-WIN target without
  changing the labeling/validation formulation.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE: META_LABEL_RESET_COMPLETE

Frozen primary:
NET +0.5% / -0.5% / 30m, close-confirmed, fee/slippage included.

## Parked

- Wallet/on-chain fusion. Revisit only if the meta-label program still lacks
  independent predictive information.
- 1–3 minute delayed confirmation gate. This is the next fallback if the
  purged meta-label program fails.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
