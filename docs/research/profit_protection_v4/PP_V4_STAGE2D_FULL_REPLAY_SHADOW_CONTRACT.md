# PP V4-2D — Full Replay + Prospective Shadow Contract

Status: **PREREGISTERED BEFORE IMPLEMENTATION**

## Objective

Stage2D has two deliverables:

1. audit the selected Stage2C hybrid trade-by-trade with explicit causal action logs and accounting invariants;
2. activate the same state machine prospectively in **shadow-only** mode on new PAPER positions.

No Stage2D shadow action may submit, alter, reduce, or close a paper/live position.

## Frozen selected state machine

Small-profit mode:
- arm when observed running gross peak >= +0.50%;
- giveback condition: current observed gross PnL <= 60% of running peak;
- require 3 consecutive canonical V4 observations;
- shadow action: REDUCE 25% of then-remaining quantity;
- only one small-mode reduction.

Runner transition:
- permanent once observed running gross peak >= +1.50%;
- disables any not-yet-fired small reduction.

Runner mode:
- giveback condition: current observed gross PnL <= 90% of running peak;
- require 2 consecutive canonical V4 observations;
- shadow action: CLOSE 100% of remaining shadow quantity.

## Historical full replay audit

Use the same frozen 99 Stage2A clean-label trades.

For every trade persist an audit row containing:
- chronological input observations;
- every state transition;
- any preserved historical execution before first counterfactual action;
- shadow REDUCE/CLOSE action;
- quantity before/after each action;
- allocated entry fee;
- exit fee and adverse slippage;
- final fallback close if no runner close occurs after divergence;
- final simulated PnL.

Mandatory invariants:
1. timestamps never decrease;
2. no future observation is consumed;
3. small REDUCE count <=1;
4. runner qualification is irreversible;
5. runner CLOSE count <=1;
6. no shadow action occurs after shadow CLOSE;
7. quantity never becomes negative;
8. total exited quantity equals initial quantity at replay completion;
9. total allocated entry fee equals recorded entry fee within numerical tolerance;
10. regenerated aggregate metrics equal frozen Stage2C selected-reference metrics.

Any invariant failure blocks prospective activation.

## Prospective shadow runtime

A shadow engine consumes each successfully persisted canonical V4 observation.

Eligibility:
- PAPER only;
- position opened strictly after `PP_V4_STAGE2D_START_MS`;
- Stage2D shadow explicitly enabled.

Persistence:
- `pp_v4_stage2d_shadow_state`
- `pp_v4_stage2d_shadow_actions`

State records:
- running observed peak;
- small confirmation count;
- runner confirmation count;
- small-fired flag;
- runner-qualified flag;
- shadow remaining fraction;
- last observation timestamp;
- terminal shadow-close flag.

Actions:
- `SHADOW_REDUCE_25`
- `SHADOW_CLOSE_REMAINDER`

Actions are research records only.

The Stage2D module must not import or call:
- paper order submission;
- paper REDUCE/CLOSE execution;
- live trading submission;
- control-state mutation.

## Restart behavior

State must hydrate from persistent storage.

Reprocessing the same observation must be idempotent:
- no duplicate state transition;
- no duplicate action.

## Shadow data-quality gate

Before any later authority discussion, prospective shadow must demonstrate:
- zero duplicate shadow actions;
- zero out-of-order accepted observations;
- zero state invariant errors;
- shadow position start coverage >=98% of eligible positions;
- canonical observation sample-gap quality remains within existing V4 limits.

## Prospective evaluation minimum

No exit authority may be considered until at least:
- 100 prospectively closed matched shadow positions; and
- 50 positions whose shadow running peak reached >=+0.50%.

Evaluation must compare:
- actual historical paper outcome;
- shadow counterfactual outcome reconstructed from shadow actions and actual final close;
- observed peak retention;
- small/medium conversion;
- runner >=1% and >=2% retention;
- chronological stability.

## Activation procedure

1. merge code with shadow disabled by default;
2. PAUSE_ENTRIES;
3. require zero open positions for a clean boundary;
4. freeze `PP_V4_STAGE2D_START_MS`;
5. enable shadow only;
6. rebuild/restart app;
7. verify store + endpoint + no order authority;
8. resume RUN.

## Audit endpoint

`GET /pp-v4/stage2d/shadow/summary`

## Runtime authority

**NONE.**

Stage2D may observe and persist hypothetical actions only.
