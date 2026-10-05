# PS-4.5 — Realtime Protection Shadow UI

Status: **COMPLETE / PASS**

Runtime authority: **NONE**

Prospective runtime wiring: **NOT ENABLED**

UI refresh cadence: **10 seconds**

## Objective

Implement the PS-2.5 frozen UI contract inside the existing Binance-style BabaBot Futures Terminal.

The UI must compare the four independent shadow protection branches for one source trade without duplicating the source position row.

Branches:

1. `V42_BASELINE` — V4.2
2. `V43_LS` — V4.3
3. `BE025_CONSERVATIVE` — BE0.25
4. `BE018_AGGRESSIVE` — BE0.18

PS-4.5 is read-only.

It does not enable shadow trading, create parents, fan out events, settle branches, or change paper/live execution authority.

## Terminal placement

The terminal order is now:

```text
Positions
Protection Shadow
Open Orders
Order History
Position History
Signal History
AI Risk
Trading Control
```

The existing Positions tab remains unchanged and authoritative for the current source paper/live lifecycle.

## Main Protection Shadow table

One source trade = one row.

Columns:

| Trade | Side | Entry / Mark | Parity | V4.2 | V4.3 | BE0.25 | BE0.18 | Best / Δ vs V4.2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Each protector cell shows:

- effective current/final branch PnL
- branch short label
- current branch state
- delta versus V4.2 when available

Closed branches use final realized PnL.

Open partially reduced branches use total current PnL:

```text
realized settled PnL
+
executable remaining-position PnL
```

This preserves the PS-4 correction that prevents partial realized PnL from being compared against full-position branch PnL.

## Parity-first comparison

A trade with:

```text
comparison_eligible = false
```

is visibly marked:

`EXCLUDED — parity invalid`

and no best-branch winner is shown.

This prevents corrupt/missing event streams from appearing in comparative performance.

## Summary strip

The Protection Shadow pane exposes:

- tracked parent trades
- comparison-eligible trades
- virtual CLOSED branch count
- execution authority / contract version

The authority display remains:

`NONE`

## Prospective causal warning

The UI reads the PS-3 adapter contract and surfaces the research-scope warning.

It explicitly distinguishes:

- frozen ex-post V4.3 / BE research headlines
- prospective causal shadow outcomes

This matters because PS-4 demonstrated that causal V4.3 from entry does not reproduce the frozen ex-post full170 headline on future-runner trades.

The UI therefore does not present frozen values as expected prospective results.

## Expandable trade inspector

Clicking a parent row opens a four-card comparison inspector.

Each branch card displays:

- protector label / family
- OPEN / CLOSED status
- current/final PnL
- delta vs V4.2
- current state
- lane
- action
- decision reason
- MFE / MAE
- remaining quantity
- BE / runner flags
- virtual close time / price

The selected row is highlighted.

## Virtual Settlement Ledger

The inspector also loads:

`GET /shadow/protection/settlements?parent_id=...`

and displays:

- time
- branch
- intent source
- action
- settlement status
- executed quantity
- fill
- realized PnL delta
- remaining quantity
- reason

Settlement history is loaded only for the selected parent and refreshed while selected.

## Read-only API usage

The dashboard now consumes:

`GET /shadow/protection/positions?limit=120`

`GET /shadow/protection/contract`

`GET /shadow/protection/adapters`

`GET /shadow/protection/settlement`

and on selected parent:

`GET /shadow/protection/settlements?parent_id=...`

No shadow UI code issues a POST request.

No control endpoint is used by the shadow pane.

## Dormant / unavailable state

PS-1 through PS-4 are still not connected to the current paper/live event loop.

Therefore PS-4.5 handles two valid empty states:

### API available, no prospective shadow trades

Displays:

`No shadow trades yet`

### Shadow endpoints not active on the current deployment

Displays:

`Protection Shadow API not active`

and:

`Shadow backend dormant/unavailable`

The rest of the dashboard continues normally.

The UI never manufactures branch results to fill an empty state.

## Responsive behavior

Desktop:

- four branch cards side-by-side

Medium viewport:

- two-by-two branch cards

Small viewport:

- single-column branch cards

The existing terminal horizontal scrolling remains available for the comparison table.

## State isolation

New frontend-only state:

- shadow snapshot
- UI contract
- adapter contract
- settlement contract
- shadow API error
- selected parent
- per-parent settlement cache

This does not alter source Positions state.

## Validation

`tests/test_dashboard_ps45_shadow_ui.py`

Coverage:

1. tab placement after Positions
2. one-row / four-protector main table
3. detail inspector + settlement ledger
4. all required read-only endpoints
5. no shadow POST/control mutation
6. parity-invalid trade exclusion
7. prospective causal warning
8. dormant backend empty state
9. refresh state wiring
10. PS-2.5 detail fields
11. responsive branch layout
12. inline JavaScript syntax via Node

Host result:

**12/12 PASS**

Backend production-image regression:

- PS-4: **17/17 PASS**
- PS-3: **16/16 PASS**
- PS-2.5: **10/10 PASS**
- PS-2: **13/13 PASS**
- PS-1: **10/10 PASS**
- Stage7 Read API: **15/15 PASS**
- BE6: **7/7 PASS**

Backend total:

**88/88 PASS**

Combined validated checks:

**100 PASS**

A graphical browser screenshot was not generated on core-prod because no browser executable is installed there. No browser package was installed or environment changed just for verification.

## PS-4.5 verdict

**PASS**

The existing BabaBot Futures Terminal now has a read-only Protection Shadow surface capable of displaying all four branch outcomes side-by-side from the PS-2.5/PS-4 API contract.

The current trading runtime remains unchanged.

## Next

Before aggregate prospective WR/PnL can be meaningful, fresh source positions must actually feed the shadow stack.

Recommended next stage:

**PS-5A — Prospective Shadow Runtime Wiring**

- create one shadow parent after each new paper entry
- emit common raw market events
- emit 5s protection samples
- emit source REDUCE/CLOSE lifecycle events
- process PS-3 decisions
- process PS-4 settlement
- preserve execution authority NONE
- establish a clean prospective boundary

Then:

**PS-5B — Prospective Comparison Dashboard**

Aggregate only parity-valid fresh trades:

- PnL
- WR
- LONG / SHORT
- per protection branch
- delta vs V4.2
- saved losses
- harmed winners
- close reason distribution
- 25 / 50 / 100 / 200 trade windows
