# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

WD-5H Stage 3C — High-Precision TAKE/ABSTAIN Frontier

Stage 3B is complete.

The meta-label target remains:

- META_WIN: selected side reaches net +0.5% before net -0.5% within 30m;
- META_LOSS: selected side reaches net -0.5% first;
- TIMEOUT: neither barrier resolves inside 30m.

Stage 3B tested three architectures:

1. baseline unpurged/unweighted;
2. purged + 30m embargo, unweighted;
3. purged + 30m embargo + Stage3A uniqueness weighting.

Architecture selection was frozen using outer-validation average precision,
then AUC, then top-10% precision.

Outer validation selected the baseline architecture. Its untouched final test
was weak:

- AUC: 0.5695
- average precision: 0.2846
- test META_WIN prevalence: 24.87%
- top-10% precision: 28.95%

Purged+weighted was slightly better on the final test (AUC 0.5882, AP 0.3026,
top-5% precision 36.84%), but it did not win outer validation and therefore
cannot be promoted post-hoc.

Formal Stage 3B status:

META_RANKING_SIGNAL_WEAK

No model has production authority.

## Production State

UNCHANGED.

The production runtime does not import research code.

## Supported Findings

1. Triple-barrier relabeling materially improves target semantics.
2. TRUE_WRONG_DIRECTION maps strongly to META_LOSS.
3. RIGHT_THEN_FAILURE contains a meaningful META_WIN subset.
4. Outcome windows overlap heavily; purging and uniqueness weighting remain
   methodologically appropriate.
5. Purging/weighting do not yet produce a stable strong pre-entry ranking
   signal across chronological windows.
6. The final test shows a small post-hoc advantage for purged/weighted, but
   validation did not select it; this is diagnostic only.
7. Static pre-entry features still appear insufficient for a confident
   high-precision gate, but Stage 3C will formally test the selective
   TAKE/ABSTAIN frontier before this path is closed.

## Rejected / Not Production-Ready

- WD-5B static reversal discriminator.
- WD-5F universal reversal.
- WD-5G Health + universal Reversal policy.
- WD-5H Stage 2 historical-realized-WIN gate.
- WD-5H Stage 3B current meta-ranking models for production use.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE: META_LABEL_RESET_COMPLETE
- WD-5H Stage 3B — COMPLETE: META_RANKING_SIGNAL_WEAK

## Parked

- Wallet/on-chain fusion.
- 1–3 minute delayed confirmation gate.

If Stage 3C cannot find a stable usable high-precision pocket, the static
pre-entry meta-label path should stop and the 1–3 minute confirmation path
becomes the preferred next hypothesis.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
