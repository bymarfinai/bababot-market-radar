# WD-5E VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`, frozen WD-4/WD-5C/WD-5D cohorts plus causal Binance pre-entry 1m reconstruction.  
Authority: research only.  
Production trading rule changes: none.

## Executive result

WD-5E is a **partial pass**, not a production-ready multi-head detector.

Formal status:

- Continuation Health: **PROMISING_STABLE**
- Path Expectation: **PROMISING_BUT_MODEL_SELECTION_UNSTABLE**
- Reversal Thesis: **NO_ROBUST_REVERSAL_HEAD**
- Overall: **PARTIAL_PASS_NOT_PRODUCTION_READY**
- Production authority: **NONE**

The main positive result is that the system can now characterize **healthy versus overheated continuation** materially better than before.

The unresolved bottleneck remains:

> before entry, can the detector reliably distinguish a wrong-direction case that should be REVERSED from one that should be NO TRADE?

WD-5E improves that question somewhat, but not enough.

---

## Head A — Continuation Health

Cohort:

- 523 MFE >=1% runner opportunities
- 404 positive-final winners
- 119 runner misses

### Selected model

Validation selects the **WD-5D engineered feature head**.

| Window | AUC |
|---|---:|
| Validation | **0.783** |
| Final test | **0.767** |

The signal remains strong across both chronological windows.

Important selected features include:

- `overheat_pressure`
- 15m-vs-1h acceleration
- score x activity heat
- activity heat
- heat x extension
- 5m-vs-15m acceleration
- normalized extension
- momentum curvature
- flow-gap interactions
- micro-fade interactions

### Combined sensitivity

The combined legacy + engineered model is also stable:

- validation AUC: **0.778**
- final test AUC: **0.773**

This independently supports the continuation-health signal.

### Triage sensitivity

Validation-selected triage applied to final test:

- coverage: **99.0%**
- HEALTHY precision: **77.9%**
- OVERHEATED/FAILURE precision: **61.1%**
- decided accuracy: **75.0%**

This is not a production threshold, but it shows Health is the strongest head in the prototype.

### Head conclusion

**PROMISING_STABLE**

The system now has a credible causal signal for:

> healthy continuation versus continuation that is becoming too hot / failure-prone.

---

## Head B — Path Expectation

Cohort:

- 500 winners
- 385 RECOVERED
- 115 CLEAN

Positive class = RECOVERED.

### Validation-selected model

Validation selects the legacy feature variant:

- validation AUC: **0.812**
- final test AUC: **0.649**

This selection itself is not stable enough.

### Engineered-only sensitivity

WD-5D path-shape features show the opposite chronological pattern:

- validation AUC: **0.724**
- final test AUC: **0.778**

### Combined sensitivity

Combined model:

- validation AUC: **0.800**
- final test AUC: **0.709**

Its final-test triage:

- RECOVERED precision: **91.4%**
- CLEAN precision: **66.7%**
- decided accuracy: **89.9%**

However, the combined model was not the validation-selected winner, so WD-5E does not replace the selected model after observing final test.

### Head conclusion

**PROMISING_BUT_MODEL_SELECTION_UNSTABLE**

There is meaningful path-shape information, but the exact model/feature variant still changes across chronological windows.

This head should remain research-only.

---

## Head C — Reversal Thesis

Primary target:

| Target | N |
|---|---:|
| REVERSE | 435 |
| NO TRADE | 386 |
| Total | **821** |

### Pre-entry micro coverage

- 821 / 821 trades reconstructed
- minimum usable closed candles per trade: **30**
- cached historical source rows: 39 per position window
- all candle features stop at the causal Stage11C decision boundary

### Best validation-selected linear variant

The selected variant is **micro-only**.

Selected features are surprisingly simple:

1. selected-side 15m pre-entry return
2. selected-side 10m pre-entry return
3. selected-side 20m VWAP extension
4. selected-side 5m pre-entry return
5. selected-side 30m pre-entry return

Performance:

| Window | AUC | Balanced accuracy |
|---|---:|---:|
| Validation | **0.656** | 0.608 |
| Final test | **0.574** | 0.546 |

This is better than the WD-5B entry-state result during validation, but it does not hold strongly enough on the final chronological test.

### Other reversal variants

| Variant | Validation AUC | Test AUC |
|---|---:|---:|
| Legacy causal | 0.492 | 0.610 |
| WD-5D engineered | 0.567 | **0.630** |
| **Micro only** | **0.656** | 0.574 |
| Engineered + micro | 0.625 | 0.592 |
| All portable | 0.499 | 0.616 |

The ranking of variants changes materially by time window.

That is a hallmark of unstable / regime-dependent reversal separation.

### High-confidence triage

The validation-selected micro triage gives:

Validation:

- coverage: 37.8%
- REVERSE precision: **70.0%**
- NO TRADE precision: **73.1%**
- decided accuracy: **72.6%**

But when frozen thresholds are applied to final test:

- coverage: 48.5%
- REVERSE precision: **71.4%**
- NO TRADE precision: **43.8%**
- decided accuracy: **46.3%**

So the apparent high-confidence NO-TRADE boundary does not survive.

REVERSE precision remains decent only at extremely low recall:

- final REVERSE recall: **4.85%**

That is far too narrow to solve the 435-case problem.

---

## Nonlinear reversal sensitivity

A shallow random forest was also tested on the new micro features.

Validation-selected nonlinear model:

- top 20 micro features
- depth 3
- min leaf 15

Performance:

- validation AUC: **0.630**
- final test AUC: **0.606**

This is more even than the selected logistic model but remains below a promotion-grade discriminator.

The nonlinear model therefore does not rescue the reversal thesis.

---

## Novel-symbol reversal check

The untouched final test includes:

- **33 trades**
- **30 symbols never seen in training or validation**

For the validation-selected micro logistic model:

- AUC: **0.396**
- balanced accuracy: **0.300**

This is the strongest reason WD-5E does not promote the reversal head.

The current micro signal does not generalize reliably to unseen coins.

---

## Formal reversal conclusion

The best minimum chronological AUC across linear + nonlinear tested reversal models is:

**0.606**

Novel-symbol AUC:

**0.396**

Formal status:

**NO_ROBUST_REVERSAL_HEAD**

Therefore WD-5E does **not** authorize:

- automatic LONG -> SHORT reversal
- automatic SHORT -> LONG reversal
- full WD-4 conversion of 435 cases into opposite-direction entries

The 435 WD-4 cases remain economically WIN-capable in hindsight, but the system still cannot identify them robustly before entry.

---

## What WD-5E successfully changes

The detector architecture is now empirically asymmetric:

```text
MOVEMENT / CURRENT SIDE
        |
        v
CONTINUATION HEALTH HEAD  ----> promising
        |
        +-- HEALTHY
        |     -> continuation candidate
        |
        +-- OVERHEATED
              -> do not blindly chase
              -> reversal research candidate

PATH EXPECTATION HEAD     ----> promising but unstable
        |
        +-- CLEAN
        +-- RECOVERED

REVERSAL THESIS HEAD      ----> not robust yet
        |
        +-- REVERSE
        +-- NO TRADE
        +-- ABSTAIN
```

The main architectural improvement is that:

> **OVERHEATED no longer needs to mean SHORT/LONG reversal automatically.**

It can instead become a distinct state:

> continuation quality is bad; do not chase; require independent reversal proof.

This prevents an unreliable reversal head from contaminating the strong health signal.

---

## Implication for the target 849 wrong-direction trades

WD-4 target remains:

- 463 strict WIN-capable paths
- 386 NO-TRADE targets

But WD-5E still cannot safely route the 435 opposite-from-entry cases at sufficient causal reliability.

Therefore the system should **not yet** attempt:

```text
OVERHEATED -> automatically reverse
```

A safer research architecture is:

```text
HEALTHY      -> continue
OVERHEATED   -> block / abstain first
                |
                +-- reverse only when stronger opposite evidence exists
```

That preserves the strong discovery without inventing reversal certainty.

---

## Frozen artifacts

### Pre-entry micro cache

`/opt/core-app/data/wd5e_preentry_1m_cache.jsonl`

SHA256:

`a0a5a6f30c7fb20e1de5d1423290b02c197f1f7b81b2271302f5fe836066146d`

### Multi-head reversal dataset

`/opt/core-app/data/wd5e_multihead_features.csv`

SHA256:

`4852298bec3bedb03cf6a7f71025a8e512cf4908fc1fee02c952e45cbd6b796f`

### Full result

`/opt/core-app/data/wd5e_multihead_results.json`

SHA256:

`d8cd0d19f1b20818167e4dad988c8376884e9239f1594e61ab163c55557310cc`

Focused WD-0 through WD-5E tests:

**56 / 56 PASS**

---

## Handoff

The next stage should **not** immediately be a production multi-head replay.

The strongest next research path is to improve the missing reversal evidence while preserving the now-validated Health head.

Candidate directions include:

1. broader market-relative context at decision time
   - BTC / ETH beta
   - relative strength versus market
   - breadth / cross-sectional momentum

2. richer positioning context
   - OI acceleration rather than single OI change
   - funding acceleration
   - liquidation / crowding proxies when available

3. order-book / taker-flow dynamics
   - flow acceleration / exhaustion
   - imbalance changes rather than one snapshot

4. conditional reversal logic
   - only ask REVERSE after Health says OVERHEATED
   - otherwise abstain / NO TRADE

Until then, continuation health can advance as a research module, but reversal remains blocked.
