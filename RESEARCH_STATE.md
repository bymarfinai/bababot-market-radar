# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

WD-5H Stage 3A — Triple-Barrier Meta-Label Reset

Goal: relabel the 2,175 frozen primary-direction candidates according to a
standardized economic path outcome rather than the historical realized exit.

Planned labels:
- META_WIN: profit barrier is reached before invalidation;
- META_LOSS: invalidation/stop barrier is reached first;
- TIMEOUT: neither barrier is reached before the vertical barrier.

No Stage 3A rule has production authority.

## Production State

UNCHANGED.

The production runtime does not import code from research/.

## Supported Findings

1. Overheat is useful as a risk/exhaustion signal.
2. TRUE_WRONG_DIRECTION is structurally different from RIGHT_THEN_FAILURE.
3. OVERHEATED does not imply the opposite side should be traded.
4. Conditional reversal can work inside known true-wrong cases, but is not
   safe as a universal action.
5. Static pre-entry features do not currently support a stable 70%+ selective
   realized-WIN gate.
6. Realized PnL mixes entry quality and lifecycle/exit quality; this is now
   the primary labeling concern.
7. The next hypothesis is meta-labeling with triple barriers, followed by
   overlap-aware validation.

## Rejected / Not Production-Ready

- WD-5B static pre-entry reversal discriminator.
- WD-5F as a universal reversal gate.
- WD-5G full Health + universal Reversal policy.
- WD-5H Stage 2 flat realized-WIN classifier.
- WD-5H Stage 2 hierarchical static realized-WIN gate.
- Adding more static indicators to the same realized-WIN target without
  changing the labeling/validation formulation.

## Parked

- Wallet/on-chain fusion. Revisit only if meta-labeling still lacks independent
  predictive information.
- 1–3 minute delayed confirmation gate. This is the next fallback after the
  meta-label program.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
