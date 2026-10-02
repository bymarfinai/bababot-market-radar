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
| WD-5H Stage 4A | COMPLETE | Reconstructed 330 causal temporal features at T+1/T+2/T+3 for all 2,175 trades with 0 causality violations; OI fresh-update coverage only 0/0/2.39% | Treating 5m OI as if it were a fresh 1-3m confirmation signal or using partially formed 1m candles |
| WD-5H Stage 4B | COMPLETE / PROMISING | Survivor-guarded temporal discrimination strengthens sharply with delay; fixed diagnostic AUC T+1 0.584/0.626, T+2 0.677/0.722, T+3 0.804/0.757 val/test; T+3 strongest | Using already barrier-resolved trades in confirmation discovery, treating T+3 OI-derived signal as fresh OI, or choosing a TAKE threshold in discovery |
| WD-5H Stage 4C | COMPLETE / PROMISING NOT READY | Validation-only selection chose T+3 threshold 0.6028066: 80% resolved precision on 35 validation trades; same rule historical test 65% on 20 resolved, 52% WIN including TIMEOUT; ~2.4x lift over T+3 base but misses promotion criterion | Switching to T+2 post-hoc because its tiny test pocket looked better, retuning threshold from test, or calling 52% all-TAKE WIN production-ready |

## Current Hypothesis

### WD-5H Stage 4D — Delayed-Entry Economic Replay

Stage 4C found a meaningful but not promotion-ready temporal gate.

The exact gate is frozen:

- T+3
- fixed Stage 4B top-12 temporal model
- threshold 0.6028066188778062
- survivor guard unchanged

Stage 4D should answer:

Does the 4C confirmation improvement survive when the trade is actually entered
at the T+3 market price rather than the original T0 entry price?

The replay must include:

- delayed entry market price;
- fee + slippage;
- symmetric barrier outcomes from delayed entry;
- missed early WIN and early LOSS opportunity accounting;
- coverage / trade count;
- delayed-entry degradation versus original path;
- runner retention.

No gate retuning is allowed in Stage 4D.

## Planned Sequence

1. Stage 4A — causal temporal reconstruction — COMPLETE
2. Stage 4B — temporal pattern discovery — COMPLETE / PROMISING
3. Stage 4C — high-precision temporal gate — COMPLETE / PROMISING NOT READY
4. Stage 4D — delayed-entry replay — NEXT
5. Stage 4E — fresh shadow validation only if economics justify it

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
