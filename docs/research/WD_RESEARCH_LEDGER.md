# Wrong-Direction Research Ledger

This ledger is the compact source of truth for completed/rejected WD research.
Historical code and result documents are preserved; rejected ideas should not
be silently retried under a new name.

| Stage | Status | Main finding | Do not repeat blindly |
|---|---|---|---|
| WD-0 | COMPLETE | Cohort attribution/data hygiene frozen | Mixing legacy/pre-rebuild cohorts |
| WD-1 | COMPLETE | 2,175 trades labeled; 849 strict true-wrong | Treating every loss as wrong direction |
| WD-2 | COMPLETE | First 1–3m contains stronger failure evidence | Assuming entry snapshot is the only useful timing |
| WD-3 | RESEARCH ONLY | Early counterfactual close can reduce damage | Calling loss reduction a direction fix |
| WD-4 | COMPLETE | 54.5% of strict wrong cases are opposite-win capable under strict 30m mapping | Equating hindsight reverse capability with causal identifiability |
| WD-5A | COMPLETE | Causal entry matrix frozen | Using fill/post-entry information as entry features |
| WD-5B | REJECTED | Static reversal discrimination near random / structurally biased | Reusing continuation score as reversal thesis |
| WD-5C | COMPLETE | Runner archetypes mapped; many winners recover first | Treating recovered winner as bad entry |
| WD-5D | PARTIAL | Overheat/exhaustion signal found; runner size weak | Stronger momentum automatically means better trade |
| WD-5E | PARTIAL | Health head useful; reversal head not robust, novel symbols collapsed | Auto-reverse from overheat |
| WD-5F | RESEARCH CANDIDATE | One-sided reversal works inside conditional wrong cases | Applying WD-5F probability as universal reversal probability |
| WD-5G | REJECTED | Health-only beats Health+Reversal; universal reversal damages runners | OVERHEATED equals TRUE_WRONG_DIRECTION |
| WD-5H Stage 1 | COMPLETE | Flat WIN-vs-all weak; pairwise class differences real | Collapsing all non-winner failure modes |
| WD-5H Stage 2 | REJECTED | Static high-precision realized-WIN gate fails; nonlinear sensitivity does not rescue | Adding another static classifier to same target |

## Current Hypothesis

### WD-5H Stage 3A — Triple-Barrier Meta-Label Reset

The primary direction model already produces LONG/SHORT candidates. The next
research question is not whether historical exit PnL ended positive.

It is:

Did the primary side generate a standardized tradeable favorable move before
standardized invalidation?

This separates entry-thesis quality from lifecycle/profit-protection quality.

## Planned Sequence

1. Stage 3A — Triple-Barrier Meta-Label Reset
2. Stage 3B — Purged/embargoed meta-model with overlap uniqueness weighting
3. Stage 3C — High-precision TAKE/ABSTAIN frontier
4. Stage 3D — Full end-to-end replay
5. Stage 3E — Fresh prospective shadow validation

## Fallback Sequence

If Stage 3B/3C cannot produce a stable usable high-precision pocket:
1. stop the static meta-label path;
2. test the previously observed 1–3 minute causal confirmation window;
3. only then reconsider external data such as on-chain wallet flow.

## Repository Policy

- Production code belongs in market_radar/.
- WD experiments belong in research/wrong_direction/.
- Historical research docs belong in docs/research/wrong_direction/.
- Frozen result data remain outside git on the research VPS and are referenced
  by hashes in result docs.
- Failed experiments are archived, not erased.
- Scratch files may be removed only when proven reproducible and not
  audit/source-of-truth files.
