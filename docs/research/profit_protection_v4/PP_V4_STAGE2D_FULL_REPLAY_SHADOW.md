# PP V4-2D — Full Replay + Prospective Shadow

Status: **COMPLETE — SHADOW ONLY**

Historical full replay of the selected Stage2C hybrid passed on all 99 trades.

Selected state machine:
- small mode: arm +0.50%, retain 60%, confirm 3;
- action: reduce 25% of then-remaining quantity once;
- runner qualification: observed running peak >=+1.50%;
- runner mode: retain 90%, confirm 2, then close remaining.

Replay audit:
- 99 trades;
- Stage2C aggregate metrics matched exactly;
- total simulated PnL: **+$78.73**;
- win rate: **45.45%**;
- small reductions: **49**;
- runner closes: **19**;
- runner >=1% median retention: **73.57%**;
- runner >=2% median retention: **82.46%**;
- invariant failures: **0**.

Action accounting:
- preserved historical executions before divergence: 18;
- shadow reduce actions: 49;
- runner qualifications: 19;
- shadow close remainder: 19;
- fallback final closes after a small reduction without runner close: 43;
- untouched actual outcomes: 37.

Prospective implementation:
- module: `market_radar/profit_protection_v4_stage2d_shadow.py`;
- consumes only successfully persisted canonical V4 observations;
- persists state and hypothetical actions;
- idempotent action IDs;
- restart-safe persistent state;
- fail-isolated from canonical V4 observer;
- endpoint: `GET /pp-v4/stage2d/shadow/summary`;
- environment:
  - `PP_V4_STAGE2D_SHADOW_ENABLED`
  - `PP_V4_STAGE2D_START_MS`.

Shadow actions:
- `SHADOW_REDUCE_25`
- `SHADOW_CLOSE_REMAINDER`

Authority is hard-coded as **NONE**. The module does not submit paper or live orders.

Promotion remains blocked until prospective minimum:
- 100 closed matched shadow positions;
- 50 positions reaching shadow running peak >=+0.50%;
- zero duplicate actions;
- zero out-of-order accepted observations;
- zero invariant errors;
- >=98% position-start coverage.

No exit authority is granted by Stage2D.


## Stage2D production shadow activation

- merged implementation commit: `8e3560b9b9789b925bd96b2b27a605daeffa7a73`
- clean shadow boundary: `1791094561302`
- control at boundary: `PAUSE_ENTRIES`
- open positions at boundary: **0**
- `PP_V4_STAGE2D_SHADOW_ENABLED=true`
- shadow version: `pp-v4-stage2d-shadow-v1`
- authority: **NONE**
- app health after rebuild: **healthy**
- shadow endpoint: **HTTP 200**
- initial store: 0 positions / 0 actions / 0 duplicates / 0 out-of-order / 0 invariant errors
- control resumed to `RUN` at `1791094640894`
- live remained disabled/disarmed

Any prospective Stage2D shadow evaluation must use positions opened strictly after `1791094561302`.


## Stage2D historical-first correction

At user direction, prospective shadow collection was disabled before new PAPER validation.

Expanded historical validation on all **189 strict-coverage existing trades** shows:
- actual total: **-$242.13**;
- selected hybrid: **-$153.38**;
- improvement: **+$88.75** (**36.65% loss reduction**);
- win rate: **19.58% -> 24.34%**.

The 99 clean-MFE >=0.30% opportunity trades improve from **-$10.02 -> +$78.73**.

The additional 90 trades with clean MFE <0.30%:
- actual **-$232.10**;
- hybrid **-$232.10**;
- only **1 / 90** winners;
- **0 protection actions**.

Those 90 trades account for **95.86%** of the strict cohort's absolute net loss. Profit protection cannot repair trades that never produce protectable profit.

Current decision:
- prospective Stage2D shadow: **DISABLED**;
- historical-first validation: **ACTIVE source of truth**;
- next unresolved bottleneck: upstream entry/direction/NO-TRADE filtering for the 90 low-MFE trades;
- no protection authority.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE2D_EXPANDED_HISTORICAL_VALIDATION.md`
