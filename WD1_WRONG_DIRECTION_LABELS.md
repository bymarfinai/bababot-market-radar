# WD-1 — Wrong-Direction Outcome Labels

Status: IMPLEMENTED IN REPOSITORY  
Authority: RESEARCH LABELS ONLY  
Trading behavior changed: NO

WD-1 converts the WD-0-clean paper-trading cohort into mutually exclusive outcome classes. It does not tune Stage 2/4/6/11C and does not change Stage 12 exits.

## Frozen discovery snapshot

WD-1 primary discovery is frozen at:

- `closed_at_ms <= 1790826404280`
- 2026-10-01 10:46:44.280 WIB
- 2,175 eligible closed Stage 11C V2 paper trades

Trades closing after this cutoff stay available for later prospective validation but are not added to the WD-1 discovery sample.

## Admission cohort

Primary WD-1 input is deliberately narrow:

- `POST_ENTRY_REBUILD`
- `PAPER`
- position status `CLOSED`
- proven `fresh_gate_version = stage11c-v2-evidence-families`
- causal position evaluations at or before the actual close

Known Stage 11C V1 rows and WD-0 `unknown` rows are not mixed into the primary V2 discovery cohort.

## Frozen label version

`wd1-outcome-taxonomy-v1`

These thresholds define labels only. They are not proposed production trading thresholds.

| Threshold | Value | Purpose |
|---|---:|---|
| Early window | 30 minutes | Detect adverse movement soon after entry |
| Early adverse MAE | <= -0.35% | Evidence that the trade moved materially against entry |
| Wrong-direction MFE ceiling | < +0.35% | Trade never established meaningful favorable movement |
| Directionally valid MFE | >= +0.50% | Direction was demonstrated at least once |
| Runner marker | >= +1.00% | Separate strong runners inside valid-direction classes |

The 0.35%-0.50% gap is intentional. Borderline movement goes to `STALL_NO_EDGE` instead of being forced into `TRUE_WRONG_DIRECTION`.

## Outcome taxonomy

### TRUE_WRONG_DIRECTION

All conditions must hold:

- final result is non-positive,
- adverse MAE <= -0.35% occurs within the first 30 minutes,
- maximum observed MFE stays below +0.35%.

Interpretation: the position moved against the chosen side early and never established a meaningful favorable excursion.

### RECOVERED_DRAWDOWN

All conditions must hold:

- final result is profitable,
- maximum MFE reaches at least +0.50%,
- early adverse MAE <= -0.35% occurs first,
- the first +0.50% MFE occurs later.

Interpretation: an early adverse move was recoverable. This class is critical so WD-2 does not learn to kill every early drawdown.

### STALL_NO_EDGE

The trade never reaches +0.50% MFE but does not satisfy the stricter true-wrong-direction path.

Examples:

- low MFE but no meaningful early MAE,
- borderline +0.35% to <+0.50% favorable movement,
- flat/noisy trade without directional follow-through.

### RIGHT_THEN_FAILURE

All conditions:

- maximum MFE reaches at least +0.50%,
- final result is non-positive.

This label has priority over recovered-drawdown logic. Once a trade demonstrated >=+0.50% favorable excursion, it is not labeled a direction-detection failure. It belongs to profit preservation / exit analysis.

### CORRECT_RUNNER

All conditions:

- maximum MFE reaches at least +0.50%,
- final result is profitable,
- it is not an early-adverse-then-recovery trade.

A separate `reached_runner_1pct` flag records whether MFE reached >=+1.00%.

## Insufficient-data quarantine

`INSUFFICIENT_DATA` is not one of the five research outcome classes.

A row is quarantined if WD-1 cannot establish:

- valid open/close timestamps,
- a causal MFE/MAE evaluation path,
- both MFE and MAE coverage,
- a realized final outcome.

WD-2 should exclude these rows from model/discriminator discovery until their path can be reconstructed independently.

## Causality controls

WD-1 ignores:

- evaluations before position open,
- evaluations after position close,
- future Stage 11C revalidations,
- Stage 4/5/6/11C features when creating the outcome label.

Entry features are intentionally held out of labeling. They become explanatory variables only in WD-2, reducing circularity.

## Files

- `market_radar/wrong_direction_labels.py` — taxonomy, persistence, backfill, summary
- `tests/test_wrong_direction_labels.py` — pure and store-level regression tests
- `scripts/wd1_label_trades.py` — runs WD-0 cohort backfill first, then WD-1 labeling

## Runner

```bash
python scripts/wd1_label_trades.py
```

The runner reports:

- number of eligible Stage 11C V2 closed positions,
- count per outcome class,
- `INSUFFICIENT_DATA` count,
- per-label net realized PnL,
- share of each label,
- number that reached >=+1% MFE.

## Runtime status

At implementation time the Railway `market-radar` deployment remains failed and the Railway Postgres service has no active deployment. Therefore the taxonomy is implemented and executable, but production WD-1 class counts are not claimed until the ledger is accessible and the runner executes successfully.

## WD-2 handoff

WD-2 should compare causal entry/pre-entry features across at least:

- `TRUE_WRONG_DIRECTION` vs `CORRECT_RUNNER`,
- `TRUE_WRONG_DIRECTION` vs `RECOVERED_DRAWDOWN`,
- `STALL_NO_EDGE` as a separate timing/no-follow-through problem,
- `RIGHT_THEN_FAILURE` kept separate from direction-detector tuning.

The central WD-2 question is:

> Which information available at entry distinguishes true wrong direction from temporary adverse movement that later recovers?
