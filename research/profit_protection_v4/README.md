# Profit Protection V4 Research Namespace

Status: **V4-1 ACTIVE PROSPECTIVE CAPTURE**

This directory is reserved for the PP V4 High-Frequency Peak Capture research line.

Source of truth:
- `PP_DECISION_V4.md`
- `docs/research/profit_protection_v4/PP_V4_HIGH_FREQUENCY_PEAK_CAPTURE_CONTRACT.md`

## Current state

V4-1 now has one research-only canonical observer implementation and an offline matched-trade evaluator.

Prospective start boundary: `1791079128949`\n\nRuntime components:
- observer: `market_radar/profit_protection_v4_observer.py`
- audit: `GET /pp-v4/stage1/summary`
- evaluator: `stage1_observability_benchmark.py`

The observer has no paper/live trading authority and does not alter Stage 12.

## Planned order

1. V4-1 High-Frequency Observability Benchmark
2. V4-2 Matched 15s vs high-frequency comparison
3. V4-3 Lower-Tail Compression Gate
4. V4-4 Protection + Runner Engineering, only after V4-3 passes

Do not skip directly to V4-4.


## Parallel Protection Shadow track

- **PT-L2 — LONG Parallel Profit Protector Wiring: IMPLEMENTED / VALIDATED / NOT ACTIVATED**
- Stage3C7A LONG is the only prospective production cohort; generic PAPER and SHORT are excluded.
- Activation is fail-closed unless the PP-V4 5s observer and shadow runtime use the exact same fresh boundary.
- PT-L3 must isolate Stage12 Health execution authority before the prospective epoch is enabled.

- **PS-5A — Prospective Shadow Runtime Wiring: IMPLEMENTED / VALIDATED**
- Fresh PAPER positions can now create one persistent shadow parent with four branches; LIVE source positions remain excluded.
- Added a persistent prospective epoch/boundary so historical positions cannot mix into fresh validation. Boundary changes fail closed with `BOUNDARY_CONFLICT`.
- Existing PP-V4 5s observer now feeds `PROTECTION_SAMPLE_5S`; before each sample, PS-5A catches Binance USD-M `aggTrades` up to the observation timestamp for causal BE0.18/0.25 evidence.
- Added batch event fanout + batch adapter processing so hundreds of aggTrades are written/evaluated efficiently while preserving exact canonical order.
- Raw feed uses persistent aggregate-trade ID cursors, gap/late/page-limit/retention guards, and comparison fail-closed semantics. Capacity overflow excludes the experiment rather than rejecting the source paper trade.
- Raw polling automatically stops once BE is terminal/superseded; V4.2/V4.3/runner 5s observation continues.
- Stage13 OPEN/REDUCE/CLOSE hooks are fail-isolated: source paper fills are persisted first, then shadow receives the event. Shadow errors can never roll back source trading.
- Added source lifecycle restart reconciliation for missed FILLED REDUCE/CLOSE orders; late recovery is explicitly parity-invalid rather than silently treated as clean evidence.
- Source CLOSE archives the shadow parent even when comparison is invalid, preventing orphaned experiments.
- PS-4 settlement was optimized for prospective raw volume: it now reads only mark/intent/source-lifecycle events instead of rescanning every raw trade on every settle; existing PS-4 semantics remain regression-clean.
- Read-only runtime endpoint: `GET /shadow/protection/runtime`; PS-4.5 UI now shows ACTIVE/DORMANT runtime state and prospective boundary.
- Validation: **PS-5A core 15/15 PASS**, **wiring isolation 6/6 PASS**, existing production-image backend suite **125/125 PASS**, PS-4.5 UI **12/12 PASS**; combined **137/137 PASS**.
- `execution_authority=NONE`; source mode is PAPER ONLY.
- Next after clean activation: **PS-5B — Prospective Comparison Metrics** using only fresh parity-valid trades.
- Detail: `PS5A_PROSPECTIVE_RUNTIME_WIRING.md`.

- **PS-4.5 — Realtime Protection Shadow UI: COMPLETE / PASS**
- Added a read-only **Protection Shadow** terminal tab immediately after Positions, preserving the existing Binance-style dashboard and source-position authority.
- One source trade renders as one row with side-by-side `V4.2`, `V4.3`, `BE0.25`, and `BE0.18` branch PnL/state plus parity and best/delta-vs-V4.2 fields.
- Parity-invalid trades are visibly `EXCLUDED` from best-branch comparison; the UI never ranks corrupted experiments.
- Row click opens a four-branch inspector with lane/action/reason, MFE/MAE, remaining quantity, BE/runner flags, close details, and the PS-4 virtual settlement ledger.
- The UI surfaces the prospective-causal warning from the adapter contract so frozen ex-post V4.3/BE headlines are not presented as expected forward results.
- Shadow API polling is integrated into the existing 10s refresh cycle; selected settlement history is refreshed independently.
- Dormant/unavailable shadow backends render explicit safe empty states rather than fake data or dashboard errors.
- Shadow UI is strictly GET/read-only; no POST/control/order authority was added. Current paper/live runtime remains unchanged.
- Validation: **PS-4.5 UI 12/12 PASS** on host; existing shadow/backend production-image regression remains **88/88 PASS**. Combined validated checks: **100 PASS**.
- PS-5A now supplies the prospective runtime feed; this UI remains strictly read-only. Next: **PS-5B — Prospective Comparison Metrics**.
- Detail: `PS45_REALTIME_SHADOW_UI.md`.

- **PS-4 — Shadow Settlement: COMPLETE / PASS**
- Added independent virtual settlement ledger for REDUCE/CLOSE intents, with remaining quantity, side-aware fill/slippage, fee allocation, realized/current PnL, close time/price/reason, and OPEN/CLOSED branch status.
- Source lifecycle fallback is supported: source REDUCE mirrors only before protection divergence; source CLOSE always closes remaining virtual quantity. Actual source fills/fees can be preserved where appropriate.
- PS-3 now persists intent history so REDUCE -> later RUNNER CLOSE can be replayed after restart/catch-up without losing the earlier action.
- Closed branches remain passive event consumers so all four event cursors stay aligned while sibling branches continue.
- Preferred orchestration is decision -> settlement through `process_shadow_event_with_settlement`; sequential recovery uses `process_pending_with_settlement`.
- UI comparison was hardened so OPEN partial branches use total executable current PnL rather than partial realized PnL.
- Historical V4.2 economic parity is exact: **170/170, 0 mismatch**, PS-4 **-$100.14766343166133** vs frozen **-$100.14766343166144**.
- **Important strategy finding:** causal full170 V4.3 produces **-$142.229333 / 60 wins / 35.29% WR**, versus frozen ex-post-scope V4.3 **-$43.312886 / 60 wins**. The **17 differences are entirely runner lanes** (11 RUNNER_CLOSE + 6 REDUCE25+RUNNER_CLOSE); the frozen REDUCE25 target itself remains **43/43 exact**. This is a causal-routing issue, not settlement error.
- Therefore frozen V4.3/BE integrated historical headlines must not be treated as prospective causal expectations; fresh parallel shadow is required.
- Read-only endpoints added: `GET /shadow/protection/settlement` and `GET /shadow/protection/settlements?parent_id=...&branch=...`.
- PS-4 unit tests: **17/17 PASS**; production-image regression across PS-4/PS-3/PS-2.5/PS-2/PS-1/Read API/BE6: **88/88 PASS**. `execution_authority=NONE`; realtime wiring remains disabled.
- Next: **PS-4.5 — Realtime Protection Shadow UI**, then **PS-5 — Comparison Dashboard**.
- Detail: `PS4_SHADOW_SETTLEMENT.md`, `PS3_PROTECTION_ADAPTERS.md`, `PS25_UI_DATA_CONTRACT.md`, `PS2_EVENT_FANOUT_PARITY_GUARD.md`, and `PS1_PARALLEL_SHADOW_CORE.md`.

## Activation

- deployed commit: `fbdf4f74ebb76178802879bba3d9e95a0a7bfd10`
- prospective boundary: `1791079128949`
- clean activation: 0 open positions at boundary
- endpoint: `GET /pp-v4/stage1/summary`
- current authority: observation only
