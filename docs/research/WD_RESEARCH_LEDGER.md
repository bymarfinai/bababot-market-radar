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
| WD-5H Stage 3A | COMPLETE | Triple-barrier reset: 564 META_WIN / 1,327 META_LOSS / 284 TIMEOUT; RTF relabeling confirmed; overlap severe | Training on historical realized exit PnL or ignoring overlapping label windows |
| WD-5H Stage 3B | COMPLETE / WEAK | Purged + uniqueness-weighted meta-model did not win outer validation; selected baseline final AUC 0.570/AP 0.285; weighted final diagnostic AUC 0.588/AP 0.303 | Treating the small final weighted uplift as validated or promoting any 3B model |
| WD-5H Stage 3C | REJECTED | No static high-precision pocket: best usable validation 54.5% on 11 trades, same threshold test 14.3%; weighted ultra-selective 62.5% val -> 12.5% test | Continuing static snapshot tuning or proceeding to Stage 3D without a validated gate |

## Current Hypothesis

### WD-5H Stage 4 — Causal 1–3 Minute Confirmation Window

The static pre-entry path is now closed.

Stage 3C could not find a stable selective TAKE region even after fixing
label semantics, controlling overlap, and testing abstention.

The next question is:

Can a bounded 1–3 minute post-candidate / pre-capital confirmation window
separate META_WIN from META_LOSS using causal path development that was not
available at the original entry snapshot?

Primary evidence families should include:

- selected-side 1m/3m price path;
- microstructure;
- taker flow;
- OI / positioning;
- market-relative movement;
- thesis strengthening vs deterioration.

The experiment must account for delayed-entry cost and runner retention.

## Planned Sequence

1. Stage 3A — Triple-Barrier Meta-Label Reset — COMPLETE
2. Stage 3B — Purged meta-model + uniqueness weighting — COMPLETE / WEAK
3. Stage 3C — High-precision TAKE/ABSTAIN frontier — REJECTED
4. Stage 3D — SKIPPED: no validated gate to replay
5. Stage 3E — NOT APPLICABLE
6. Stage 4 — 1–3 minute causal confirmation research — NEXT

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
