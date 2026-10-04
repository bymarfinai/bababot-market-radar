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
