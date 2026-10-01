# WD-1 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` PostgreSQL.
Authority: research labels only. No trading rule was changed.

## Frozen cohort

- Stage 11C: `stage11c-v2-evidence-families`
- Mode: PAPER
- Status: CLOSED
- Cohort: POST_ENTRY_REBUILD
- Cutoff: `closed_at_ms <= 1790826404280`
- Cutoff time: 2026-10-01 10:46:44.280 WIB
- Eligible / labeled: 2,175 / 2,175
- Insufficient data: 0

## Distribution

| Outcome | Trades | Share | Net PnL |
|---|---:|---:|---:|
| TRUE_WRONG_DIRECTION | 849 | 39.0345% | -2374.55178331 |
| RECOVERED_DRAWDOWN | 385 | 17.7011% | +1056.99863629 |
| STALL_NO_EDGE | 166 | 7.6322% | -605.50154541 |
| RIGHT_THEN_FAILURE | 660 | 30.3448% | -746.44014174 |
| CORRECT_RUNNER | 115 | 5.2874% | +330.84533049 |

## LONG / SHORT split

| Outcome | LONG | SHORT |
|---|---:|---:|
| TRUE_WRONG_DIRECTION | 579 | 270 |
| RECOVERED_DRAWDOWN | 251 | 134 |
| STALL_NO_EDGE | 98 | 68 |
| RIGHT_THEN_FAILURE | 367 | 293 |
| CORRECT_RUNNER | 89 | 26 |

## Key interpretation

The earlier ~66-70% losing-trade figure is not the same as wrong-direction rate.
Under the frozen WD-1 definition, strict TRUE_WRONG_DIRECTION is 39.0345%.
A further 7.6322% is STALL_NO_EDGE, while 30.3448% reached at least +0.50% MFE before ending non-positive and therefore belongs to RIGHT_THEN_FAILURE rather than entry-direction failure.

RECOVERED_DRAWDOWN is large (17.7011%); 316 of 385 reached at least +1% MFE. WD-2 must therefore distinguish true wrong direction from recoverable early adverse movement before proposing a tighter entry or early-exit rule.

## Safety / reproducibility

Pre-WD1 PostgreSQL backup:
`/opt/core-app/backups/pre-wd1-20261001-114529.dump`

SHA256:
`cbd0d01ce21c85c02bd23daf2bd4f64f49247fac75358dfe3c5b23f8e978af7b`
