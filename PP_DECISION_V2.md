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

## Stage 3 — Prospective Fast Shadow

Stage 3 runs PP-DECISION V2 prospectively on the existing Stage 12 fast-monitor cadence (default 15 seconds) while PP-LEGACY V3 remains the actual paper authority.

Stage 3 requirements:

- strict clean-cohort boundary using `PP_DECISION_V2_STAGE3_START_MS`
- only positions opened strictly after the boundary are evaluated by V2
- every V2 fast observation is persisted to dedicated `pp_decision_v2_observations`
- logging includes current PnL, MFE, previous PnL, elapsed time, giveback, decay velocity, danger score, V1 base action, V2 overlay action, final shadow action, and fast gate
- V2 actions remain observation-only and cannot create paper/live orders
- PP-DECISION V1 Final remains frozen as comparator
- PP-ADAPTIVE V1 and PP-LEGACY V3 remain comparator/control families

The dedicated observation stream fixes the main limitation discovered in Stage 2 historical replay: ordinary 15-second HOLD observations are now retained for V2 even though the Legacy fast-guard persistence continues to remain sparse by design.

### Stage 3 pre-activation validation

- targeted V2 Stage 3 tests: 13 / 13 PASS
- never-relaxes-V1 deterministic sweep: 11,760 / 11,760 PASS
- dedicated observation logging test: PASS
- strict post-boundary gating test: PASS
- full repository regression: 174 / 174 PASS


## Stage 3 prospective activation record

- status: RUNNING / prospective fast shadow
- code main commit: badde777c37357a61ecd1717e9d420488da3c192
- PP_DECISION_V2_STAGE3_START_MS: 1790757169768
- strict cohort rule: only positions opened strictly after the boundary are included
- activation zero-state: 0 V2 observations and 0 post-boundary positions before entries resumed
- observation table: pp_decision_v2_observations
- fast cadence: existing Stage 12 fast loop, default 15 seconds
- authority: PP-LEGACY V3
- V1 Final / Adaptive remain shadow comparators
- live trading: disabled / disarmed
- validation: 13/13 targeted Stage 3 tests PASS; 11,760/11,760 never-relaxes-V1 sweep PASS; 174/174 full suite PASS

## Stage 4 — Runner Preservation Hybrid

Status: **COMPLETED AS EXPERIMENT / FAIL PROMOTION GATE / NOT DEPLOYED**.

Objective: keep Stage 3 fast protection in the 0.5%–<1.0% MFE zone while preserving runners after MFE reaches 1.0%.

### What was tested

1. Naive handoff: V2 below 1%; V1-style runner logic above 1%.
2. True handoff: V2 fast below 1%; actual PP-DECISION V1 Final closed-1m events above 1%; V2 fast retained only as an emergency override.
3. Softer pre-1% de-risk fractions.
4. Separate pre-1% trim state vs runner reduction state.
5. Two-/three-sample persistence confirmation.
6. Causal continuation-grace candidates using only information available at decision time.

The best balanced causal candidate used one fast-sample grace when:

- PP-DECISION V1 base action was HOLD,
- MFE > 0.65%,
- current profit > 0.30%,
- still below the 1.0% runner handoff.

At/above 1.0% MFE, normal control handed off to the original V1 Final 1m decision stream; the fast layer only retained an extreme RUNNER_EMERGENCY override.

### Latest matched cohort benchmark

Cohort: 1,234 closed post-Stage-3 trades.

All trades:
- Legacy V3: -1466.16, WR 22.53%
- Adaptive S5-B: -1470.52, WR 24.23%
- Decision V1 Final: -1392.21, WR 25.85%
- Decision V2 Stage 3: -1372.08, WR 33.87%
- Stage 4 best candidate: -1354.82, WR 33.06%

MFE 0.5%–<1.0% (361 trades):
- Legacy V3: -320.48, WR 14.13%
- Adaptive S5-B: -306.43, WR 17.17%
- Decision V1 Final: -257.80, WR 21.33%
- Decision V2 Stage 3: -25.77, WR 51.52%
- Stage 4 best candidate: -61.60, WR 49.86%

MFE >=1.0% (301 trades):
- Legacy V3: +500.16, WR 74.42%
- Adaptive S5-B: +652.31, WR 77.74%
- Decision V1 Final: +681.99, WR 79.40%
- Decision V2 Stage 3: +470.10, WR 76.08%
- Stage 4 best candidate: +523.18, WR 74.75%

MFE >=0.5% (662 trades):
- Legacy V3: +179.67, WR 41.54%
- Adaptive S5-B: +345.88, WR 44.71%
- Decision V1 Final: +424.19, WR 47.73%
- Decision V2 Stage 3: +444.33, WR 62.69%
- Stage 4 best candidate: +461.58, WR 61.18%

Stage 4 improved aggregate net versus Stage 3 by +17.25 and improved the >=1% runner subset by +53.08, but degraded the 0.5%–<1.0% zone by -35.83. Bootstrap confidence interval for Stage4-vs-Stage3 mean difference still crossed zero. Chronological thirds also showed inconsistent improvement: early/mid runner preservation improved, while the late cohort did not consistently improve.

### Stage 4 conclusion

The original intuition was directionally correct: Stage 3 is too aggressive on future runners, and a runner-preservation handoff materially recovers some lost upside. However, a simple handoff cannot fully solve the problem because irreversible pre-1% reductions already remove size before the trade proves itself as a runner.

Stage 4 therefore does **not** pass promotion. No production rule is changed. PP-DECISION V2 Stage 3 remains the active prospective shadow.

The next research problem is not merely a looser >=1% threshold; it is distinguishing transient pre-1% giveback from genuine profit failure before taking irreversible size off.

Validation of the experimental code path:
- targeted Stage 4 tests: 15 / 15 PASS
- full repository regression: 176 / 176 PASS
- production deployment: NO

## Stage 5 — Runner-vs-Failure Discriminator

Status: built as an **observation-only shadow discriminator**. It does not change PP-DECISION V2 Stage 3 HOLD/REDUCE/CLOSE authority.

### Research question

Stage 4 showed that future runners are often trimmed before they reach 1% MFE. A simple >=1% handoff therefore arrives too late. Stage 5 asks a narrower causal question at the first actionable 0.5%-<1.0% profit-protection event:

> Is this giveback transient and likely to continue into a runner, or is it persistent profit failure?

### Historical prospective dataset

Using the Stage 3 post-boundary observation stream:

- 470 first actionable sub-1% trigger cases were initially labelled.
- 112 later reached >=1% MFE (RUNNER).
- 313 failed to reach 1% and later fell to <=0% / closed negative (FAILURE).
- 45 were ambiguous and excluded from the primary binary analysis.

A single trigger snapshot was only moderately informative. The best simple snapshot rules produced roughly 0.67-0.70 balanced accuracy. The causal 30-45 second follow-up was materially more informative.

### Frozen Stage 5 discriminator

The classifier starts WATCHING at the first actionable V2 event with 0.50% <= MFE < 1.00%.

After a 30-second causal follow-up:

- `FAILURE_LIKELY / HIGH` when current PnL < +0.15%.
  - Historical precision for FAILURE across chronological DEV / VAL / TEST: 92.7% / 96.6% / 97.2%.
- `TRANSIENT_LIKELY / MEDIUM_HIGH` when:
  - initial MFE >= +0.70%,
  - initial current PnL >= +0.45%,
  - frozen V1 base action was HOLD,
  - and follow-up current PnL remains >= +0.30%.
  - Historical runner precision across chronological DEV / VAL / TEST: 70.8% / 63.6% / 66.7%.
- `TRANSIENT_CONFIRMED / CONFIRMED` if MFE reaches >=1.00% while the watch is still active.
- everything else becomes `AMBIGUOUS / LOW`.

### Why this is shadow-only

Temporal classification materially improves runner-vs-failure discrimination, especially on the failure side, but retrospective counterfactual tests did **not** yet justify changing irreversible actions:

- broad 15-30 second grace harmed the strong Stage 3 0.5%-<1% edge;
- selective high-precision grace reduced that damage but still failed to beat Stage 3 robustly on the chronological holdout;
- a one-fast-tick selective skip was nearly neutral out-of-sample rather than meaningfully positive.

Therefore Stage 5 records predictions prospectively but cannot alter Stage 3 actions. Promotion requires prospective evidence that prediction-conditioned action changes improve net PnL without degrading the 0.5%-<1% protection edge.

### Stage 5 storage

Dedicated table: `pp_decision_v2_discriminator`.

One stateful row is stored per position with:
- initial trigger MFE/current/giveback,
- V1 base action and V2 final action,
- watch start time,
- final discriminator status,
- 30-second follow-up MFE/current,
- confidence and classifier version.

Stage 5 uses a separate clean prospective boundary and is fail-open relative to the Stage 3 protector.


## Stage 5 prospective activation record

- status: RUNNING / observation-only discriminator shadow
- code main commit: 722ad217c73e54968aaa870e32ec6c26b9d97ecf
- PP_DECISION_V2_STAGE5_START_MS: 1790821977687
- strict cohort rule: only positions opened strictly after the boundary can enter Stage 5
- activation zero-state: 0 post-boundary positions and 0 discriminator rows before/at initial verification
- active protector remains: pp-decision-v2-stage3-prospective-fast-shadow
- Stage 5 authority: NONE; predictions cannot modify HOLD / REDUCE / CLOSE
- validation: 9/9 targeted discriminator tests PASS; 183/183 full repository regression PASS
- control resumed: RUN; lifecycle exits enabled
- live trading: disabled / disarmed

## Stage 6 — Prospective Discriminator Validation

Status: built as a clean prospective validation harness. Stage 6 has no trading authority.

Purpose:
- validate Stage 5 predictions on unseen post-boundary trades;
- measure prospective classifier precision by label;
- compute stateful counterfactual PnL for the active Stage 3 protector versus unconditional 15-second and 30-second grace windows;
- preserve Stage 3 and Stage 5 behavior unchanged.

A Stage 6 case exists only when a post-boundary position has a Stage 5 discriminator watch and later closes.

At close Stage 6 stores:
- Stage 5 classifier status/confidence;
- predicted RUNNER / FAILURE / UNRESOLVED;
- realized future outcome RUNNER / FAILURE / AMBIGUOUS;
- prediction correctness when objectively scoreable;
- max MFE and minimum PnL after the watch starts;
- actual PP-LEGACY control net PnL;
- stateful PP-DECISION V2 Stage 3 replay net PnL;
- hypothetical 15-second grace net PnL;
- hypothetical 30-second grace net PnL;
- delta of each grace lane versus Stage 3;
- action counts for all replay lanes.

The grace lanes are analytical counterfactuals only. They do not submit or alter paper/live orders.

Dedicated table: `pp_decision_v2_stage6_validation`.
Read endpoint: `/pp-decision-v2/stage6/summary`.
A recovery cycle finalizes any eligible closed case missed during a restart.

Promotion criteria remain prospective: classifier precision must hold on unseen trades and any prediction-conditioned grace policy must improve economic PnL without degrading the strong 0.5%-<1% Stage 3 protection edge.


## Stage 6 prospective activation record

- status: RUNNING / prospective discriminator validation
- code main commit: 653c896f208c80d741e7abc8bc1376ec0f7f598d
- PP_DECISION_V2_STAGE6_START_MS: 1790823038032
- strict cohort rule: only positions opened strictly after the boundary can become Stage 6 cases
- activation zero-state: 0 post-boundary positions and 0 Stage 6 validation rows
- validation table: pp_decision_v2_stage6_validation
- summary endpoint: /pp-decision-v2/stage6/summary
- active protector remains PP-DECISION V2 Stage 3 shadow
- Stage 5 remains observation-only classifier
- Stage 6 authority: NONE; Stage 3 / grace15 / grace30 are analytical replay lanes only
- validation: 5/5 targeted Stage 6 tests PASS; 188/188 full repository regression PASS
- GitHub transfer: 6/6 byte-for-byte MATCH
- control resumed: RUN; lifecycle exits enabled
- live trading: disabled / disarmed
