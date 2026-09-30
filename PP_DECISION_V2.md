# PP-DECISION V2

## Stage 1 — Fast Profit Decay

Status: built and tested; runtime shadow flag remains OFF pending review.

V2 keeps the frozen PP-DECISION V1 Final rules as its base. Stage 1 adds a fast profit-decay overlay evaluated on the existing Stage 12 fast-monitor cadence (default 15 seconds). The overlay may only escalate a V1 action: HOLD -> REDUCE -> CLOSE. It can never relax a V1 decision.

### Why V2 exists

V1 reacts mainly to how much of MFE has been given back. V2 additionally asks how quickly that profit is disappearing. A rapid 15-30 second reversal is therefore treated differently from the same-sized retrace spread over several minutes.

### Fast-decay contract

The overlay arms after MFE reaches 0.50%.

- FAST_WATCH: giveback >=10% and normalized decay >=20% of MFE per minute.
- FAST_DECISION: giveback >=20% and normalized decay >=30% of MFE per minute. Danger 0-1 keeps HOLD; 2-3 REDUCE; >=4 CLOSE.
- FAST_FORCE_PROTECT: giveback >=25% and normalized decay >=50% of MFE per minute. OPEN must at least REDUCE; REDUCED closes; danger >=4 closes.
- SHOCK_DECAY: MFE >=1%, giveback >=15%, >=0.25 percentage-point profit drop in <=30 seconds. OPEN REDUCE; REDUCED CLOSE; danger >=4 CLOSE.

Danger evidence remains deterministic: adverse 3m momentum +2, adverse micro-structure break +2, opposing taker flow +1, adverse OI positioning +1.

### AI role

No AI is used in V2 Stage 1. Fast profit protection remains deterministic. AI can be evaluated later only as an advisory layer for ambiguous states; it must never override hard deterministic protection.

### Safety / methodology

- PP-DECISION V1 Final stays frozen as the comparison baseline.
- PP-LEGACY V3 remains actual paper authority.
- `PP_DECISION_V2_STAGE1_ENABLED=false` by default.
- V2 Stage 1 is not activated in production after build/test.
- No V1 thresholds are retuned using Stage 5 outcomes.

## Stage 1 test result

- targeted V2 tests: 12 / 12 PASS
- V2 never-relaxes-V1 sweep: 11,760 / 11,760 PASS
- full repository regression: 173 / 173 PASS
- rapid-shock scenario (+1.58% -> +1.31% in 30s): V1 HOLD, V2 REDUCE
- same retrace over 5 minutes: V1 HOLD, V2 HOLD
- fast-decision scenario (+1.58% -> +1.20% in 45s, danger=2): V1 HOLD, V2 REDUCE
- fast-force scenario (+1.58% -> +1.10% in 30s): V1 HOLD, V2 REDUCE
- Sub-1% fast fade (+0.80% -> +0.62% in 30s, danger=2): V1 HOLD, V2 REDUCE
- small fast noise (+1.58% -> +1.40% in 30s): V2 WATCH only, no forced exit

Conclusion: Stage 1 demonstrates the intended sensitivity increase without changing the frozen V1 base rules. Production activation remains intentionally OFF until explicit approval.

## Stage 2 — Historical Replay & 3-Way Benchmark

Status: completed as a retrospective pre-test. V2 remains NOT activated in production.

Dataset: 273 closed Stage6 trades with matched PP-LEGACY V3 outcomes, S5 adaptive lanes, and persisted position evaluations. All 273 trades had at least one FAST_GUARD snapshot; 654 FAST_GUARD snapshots were available. PP-ADAPTIVE V1 is represented by S5-B because it is the strongest current S5 adaptive baseline in the matched replay.

Important limitation: the historical fast-monitor stream is sparse. The runtime intentionally persists the first fast snapshot and actionable later fast snapshots, while ordinary later fast HOLD samples are ephemeral. Therefore the replay cannot perfectly reconstruct every 15-second V2 decay observation and likely understates the intended fast-decay overlay. The replay is a pre-test, not promotion evidence.

### All matched trades (N=273)

- PP-LEGACY V3: net -281.5268; WR 20.51%
- PP-ADAPTIVE V1 / S5-B: net -300.1028; WR 19.78%
- PP-DECISION V2 replay: net -304.2512; WR 20.15%

On all trades, Legacy is best. This universe includes many trades that never achieved meaningful positive MFE, where profit protection is not expected to repair poor entries.

### Profit-protection eligible: observed MFE >=0.50% (N=145)

- PP-LEGACY V3: net +80.1533; WR 37.24%
- PP-ADAPTIVE V1 / S5-B: net +103.2165; WR 35.86%
- PP-DECISION V2 replay: net +99.0681; WR 36.55%

V2 vs Legacy: +18.9148 total (+0.1304/trade). Bootstrap 95% CI for mean paired difference: [-0.1657, +0.3960], so the advantage is not yet statistically decisive.

V2 vs Adaptive S5-B: -4.1484 total (-0.0286/trade). Bootstrap 95% CI: [-0.4222, +0.2842], effectively a small and uncertain difference.

### Stronger-profit subset: observed MFE >=1.00% (N=56)

- PP-LEGACY V3: net +154.4390; WR 66.07%
- PP-ADAPTIVE V1 / S5-B: net +180.2652; WR 69.64%
- PP-DECISION V2 replay: net +163.7781; WR 75.00%

Adaptive S5-B has the highest net PnL in this subset; V2 has the highest win rate. V2 beats Legacy by +9.3391 total but trails S5-B by -16.4870. Paired bootstrap intervals remain wide and cross zero.

### Sensitivity observations

- V2 replay produced protective actions on 131 / 273 positions.
- 122 positions self-closed in the replay.
- only 3 first-action cases were clear V2 early escalations while the V1 base still said HOLD.
- this low incremental count is consistent with sparse persisted FAST_GUARD history: most ordinary 15-second HOLD observations were not stored, so historical data cannot fully reproduce V2's intended 15-30 second profit-decay behavior.

### Stage 2 conclusion

Historical replay does not justify calling V2 superior yet. On trades that reached MFE >=0.50%, V2 is materially better than Legacy in aggregate but slightly behind S5-B; on MFE >=1%, V2 has the best WR but S5-B has better net PnL. Because the fast historical stream is sparse, Stage 2 should be treated as a sanity benchmark. The correct next validation is a prospective V2 shadow with every V2 fast-decay observation explicitly recorded so sensitivity, MFE capture, giveback-at-action, runner survival, and matched net PnL can be measured without reconstruction bias.
