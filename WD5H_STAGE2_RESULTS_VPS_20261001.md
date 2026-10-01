# WD-5H Stage 2 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`.  
Authority: research only.  
Production changes: none.

## Executive conclusion

Formal status:

`HIGH_PRECISION_WIN_GATE_NOT_READY`

The hierarchical architecture is conceptually better than a flat WIN-vs-ALL classifier, but the currently available **pre-entry causal information is not strong enough to produce a stable high-precision WIN gate**.

This is the main Stage 2 result.

---

## Pairwise heads

### 1. WINNER vs TRUE_WRONG_DIRECTION

Selected logistic:

- top-k: 5
- L2: 4.0

Selected features:

- Stage11C side-adjusted drift
- 30m distance to selected-side local extreme
- median absolute 5m return
- gate price drift
- selected-side Stage5 taker share

Performance:

| Window | AUC |
|---|---:|
| Inner train validation | 0.617 |
| Outer validation | **0.587** |
| Final test | **0.590** |

This head is not strong enough as a high-confidence winner discriminator.

### 2. WINNER vs RIGHT_THEN_FAILURE

Selected logistic:

- top-k: 5
- L2: 0.1

Main features:

- 15m local-extreme distance
- 30m local-extreme distance
- overheat pressure
- micro reversal pressure
- score x activity heat

Performance:

| Window | AUC |
|---|---:|
| Inner validation | 0.667 |
| Outer validation | **0.607** |
| Final test | **0.629** |

This is more stable than the TRUE_WRONG head but still insufficient for a very selective WIN gate.

### 3. WINNER vs STALL_NO_EDGE

Selected logistic:

- top-k: 40
- L2: 0.1

Performance:

| Window | AUC |
|---|---:|
| Inner validation | 0.573 |
| Outer validation | **0.576** |
| Final test | **0.667** |

The final window improves, but model selection is unstable and the small STALL class makes high-confidence rejection unreliable.

---

## Primary hierarchical gate

Validation-selected thresholds:

- WIN vs TRUE_WRONG >= **0.39796**
- WIN vs RIGHT_THEN_FAILURE >= **0.38212**
- WIN vs STALL >= **0.93046**

### Validation

- candidates: 435
- TAKE: **28**
- coverage: **6.44%**
- VALID_WINNER: 11
- precision / WR: **39.29%**
- net PnL: **-$17.88**

Taken-class composition:

- WINNER: 11
- TRUE_WRONG: 14
- RIGHT_THEN_FAILURE: 3
- STALL: 0

Runner preservation among valid runner winners:

- 7 / 78 = **8.97%**

BIG_RUNNER preservation:

- 3 / 27 = **11.11%**

No tested threshold combination achieved even a **60% validation precision floor** while retaining the predefined >=5% validation coverage.

### Untouched final test

The frozen validation-selected thresholds produce:

- candidates: 435
- TAKE: **18**
- coverage: **4.14%**
- VALID_WINNER: 6
- precision / WR: **33.33%**
- net PnL: **-$24.21**

Taken classes:

- TRUE_WRONG_DIRECTION: 8
- VALID_WINNER: 6
- RIGHT_THEN_FAILURE: 3
- STALL_NO_EDGE: 1

Valid runner preservation:

- 5 / 64 = **7.81%**

Valid BIG_RUNNER preservation:

- 2 / 17 = **11.76%**

Therefore the selective gate fails both goals:

1. precision is still low,
2. it also discards most of the winners/runners we wanted to retain.

---

## Flat WIN-vs-ALL baseline

The flat model is also weak.

Validation:

- TAKE: 34
- precision: **26.47%**
- net PnL: -$18.37

Test:

- TAKE: 35
- precision: **34.29%**
- net PnL: -$31.22

So Stage 1 was correct that a flat WIN-vs-ALL classifier is not a good solution.

However, the hierarchical version does not yet provide the required improvement.

---

## Novel-symbol test

Final chronological test contains:

- 15 trades
- 13 symbols unseen in training + validation

The frozen hierarchical gate takes:

**0 trades**

This is safe in the sense of abstention, but gives no evidence that the current gate generalizes to unseen symbols.

---

## Ultra-selective post-hoc sensitivity

After the primary test had been inspected, the minimum TAKE count was relaxed below the predefined 5% coverage rule.

### Logistic hierarchy

Best validation pocket found:

- TAKE: 3
- WINNER: 2
- precision: **66.7%**
- PnL: +$3.30

Frozen same thresholds on test:

- TAKE: 2
- WINNER: 1
- precision: **50.0%**

Even extreme selectivity does not produce a stable 70%+ winner pocket.

---

## Nonlinear sensitivity

Shallow random-forest pairwise models were also tested post-hoc.

Pairwise test AUCs:

- WIN vs TRUE_WRONG: **0.633**
- WIN vs RIGHT_THEN_FAILURE: **0.630**
- WIN vs STALL: **0.692**

These are slightly better in places than logistic, but still moderate.

The best ultra-selective validation intersections reached:

- 75% precision
- generally only 3–4 trades

The top validation candidate:

- validation: 3 WIN / 4 TAKE = **75%**
- test: 0 WIN / 2 TAKE = **0%**

Other nonlinear candidate pockets also collapse or become too small on the final test.

Therefore Stage 2 failure is **not explained only by linear underfitting**.

---

## Why Stage 1 looked stronger than Stage 2

Stage 1 measured **descriptive pairwise feature separation**.

For example:

- TRUE_WRONG vs RIGHT_THEN_FAILURE had many stable univariate differences.
- WINNER vs RIGHT_THEN_FAILURE also had many stable differences.

But stable group-level distribution differences do not guarantee that individual trades can be classified with high precision.

Stage 2 tests the harder question:

> Can these differences be combined causally, trade by trade, to select mostly winners?

Current answer:

**not yet.**

The distributions still overlap too much at the exact entry decision.

---

## Architectural meaning

The current data support several useful statements:

- overheated entries are riskier,
- TRUE_WRONG and RIGHT_THEN_FAILURE differ structurally,
- market-relative and micro-location features matter,
- some failure classes can be ranked moderately.

But they do **not** support:

> "At the current Stage11C entry timestamp, select only trades with 70–80% probability of becoming realized winners."

That target is not currently identifiable with enough reliability from the static pre-entry state.

---

## Formal assessment

Failed:

- validation WIN precision >=70%
- test WIN precision >=65%
- positive test PnL
- hierarchical precision >= flat test precision

Passed only:

- test TAKE count >=10

Formal status:

`HIGH_PRECISION_WIN_GATE_NOT_READY`

Production authority:

`NONE`

---

## Most important implication

The next improvement should **not** simply add another static pre-entry detector on top of the same snapshot.

Stage 2 suggests the remaining information is likely temporal.

Earlier WD-2 / WD-3 work already showed that the first 1–3 minutes after the candidate contains much stronger separation between failure and recoverable / valid trades.

A more promising next architecture is therefore:

```text
CANDIDATE
    |
    v
PRE-ENTRY THESIS FILTER
    |
    +-- obvious bad -> NO TRADE
    |
    v
SHORT CONFIRMATION WINDOW
    |
    +-- thesis strengthens -> ENTER
    +-- thesis deteriorates -> NO TRADE
```

This would trade some entry immediacy for substantially higher selectivity.

Stage 2 itself does not implement that next architecture; it only establishes that the static high-precision gate is not ready.

---

## Frozen artifacts

`/opt/core-app/data/wd5h2_selective_gate_predictions.csv`

SHA256:

`0c24b5500f7cfbe674eb528d55e9b1a639a10c5758147cd7eacec531b877b328`

`/opt/core-app/data/wd5h2_selective_gate_results.json`

SHA256:

`2da7a6bb5dfb7ed2c0243cc602f370e09ef0b46356e64b4f2e307ed11cf53aa9`

Tests:

**76 / 76 PASS**

## Handoff

WD-5H Stage 2 is complete.

The evidence does not support promotion of a static selective-entry gate.

The strongest next hypothesis is a **causal short confirmation-window gate**, using the candidate as time zero and observing a tightly bounded 1–3 minute evidence window before committing capital.
