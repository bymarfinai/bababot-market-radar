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
