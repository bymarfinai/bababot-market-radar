# WD-5D VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`, frozen WD-5C cohort.  
Authority: research only.  
Production trading rule changes: none.

## Executive conclusion

WD-5D finds a **promising and chronologically stable overheat / exhaustion signal**.

It does **not** yet find a robust detector for exact opportunity magnitude.

The strongest result is:

> The system can identify meaningful evidence that an already-valid continuation is becoming overheated, but it still cannot reliably know in advance that a trade will become a >=1% or >=2% runner.

Formal machine-readable statuses:

- runner overheat signal: **FOUND_PROMISING**
- absolute runner-size signal: **WEAK_UNSTABLE**
- BIG_RUNNER vs SMALL_EDGE signal: **UNSTABLE**
- CLEAN vs RECOVERED path signal: **PROMISING**
- production authority: **NONE**

## 1. Runner winner versus runner miss

Cohort:

- 404 runner winners
- 119 runner misses
- total 523

### Fair chronological model comparison

| Feature set | Validation AUC | Final test AUC |
|---|---:|---:|
| Baseline causal | **0.770** | **0.761** |
| Engineered only | **0.783** | **0.767** |
| Combined | **0.778** | **0.773** |

The new features add a smaller but real improvement after correcting baseline feature ranking.

Most importantly, the engineered feature set is independently competitive and remains strong in both chronological windows.

## 2. Strongest new feature: overheat pressure

For runner winners versus misses:

- full separation: **0.503**
- median chronological-fifth separation: **0.513**
- minimum fifth separation: **0.408**
- direction consistent across chronological blocks

Median value:

- runner winner: **4.94**
- runner miss: **10.82**

Because the model's positive class is WIN, the raw feature AUC is below 0.5:

- AUC(WIN higher) = **0.249**

This means **higher overheat pressure strongly points toward MISSED runner**, not winner.

This is the strongest single structural WD-5D result.

## 3. Other stable exhaustion features

Runner winners tend to have lower:

- 15m-versus-1h acceleration
- selected score x activity heat
- total activity heat
- 5m-versus-15m acceleration
- normalized 5m / 15m extension
- heat x extension

Approximate medians:

### 15m-vs-1h acceleration

- winner: **0.234**
- miss: **0.429**
- separation: **0.416**
- chronological direction: consistent

### score x activity heat

- winner: **2.46**
- miss: **3.83**
- separation: **0.382**
- median fifth separation: **0.366**
- minimum fifth separation: **0.298**

### activity heat

- winner: **3.09**
- miss: **4.39**
- separation: **0.325**

This confirms the WD-5C hypothesis:

> runner failure frequently occurs after movement becomes too hot, not too weak.

## 4. Simple overheat threshold diagnostic

Threshold selected **only on the first 60% chronological runner cohort**:

`overheat_pressure >= 5.4819`

This means "flag as possible overheated runner."

### Train

- miss recall: **87.9%**
- winner keep rate: **57.5%**
- balanced accuracy: **72.7%**

### Validation

- miss recall: **78.3%**
- winner keep rate: **58.5%**
- balanced accuracy: **68.4%**

### Final test

- miss recall: **70.0%**
- winner keep rate: **62.7%**
- balanced accuracy: **66.3%**

The threshold is not precise enough for production by itself, but the direction remains stable out of sample.

## 5. Overheat quintiles

Among all 523 >=1% runner opportunities:

| Overheat quintile | Miss rate | Actual net PnL |
|---|---:|---:|
| Q1 — coolest | **7.6%** | +$256.73 |
| Q2 | **9.6%** | +$270.20 |
| Q3 | **15.2%** | +$348.30 |
| Q4 | **30.8%** | +$216.03 |
| Q5 — hottest | **50.5%** | +$83.54 |

The miss rate rises almost monotonically with overheat intensity.

This is strong descriptive evidence that the current continuation system needs a distinction between:

- healthy expansion
- overheated expansion

rather than simply rewarding stronger momentum.

## 6. Absolute runner opportunity remains difficult

Task:

> future MFE >=1% versus future MFE <1%

Combined model:

- validation AUC: **0.586**
- final test AUC: **0.649**

Baseline:

- validation AUC: **0.584**
- final test AUC: **0.650**

The new features do not materially improve this task.

Formal status:

**WEAK_UNSTABLE**

So WD-5D does **not** justify a production rule that says:

> only enter trades predicted to become runners.

We can see exhaustion better than exact future opportunity size.

## 7. BIG_RUNNER versus SMALL_EDGE remains unstable

Task:

- BIG_RUNNER MFE >=2%
- SMALL_EDGE MFE 0.5–1%

Combined:

- validation AUC: **0.669**
- final test AUC: **0.591**

Engineered-only:

- validation AUC: 0.657
- final test AUC: 0.563

Formal status:

**UNSTABLE**

Therefore we still cannot safely pre-label a specific entry as BIG_RUNNER rather than SMALL_EDGE.

## 8. CLEAN versus RECOVERED path is promising

Combined model:

- validation AUC: **0.800**
- final test AUC: **0.709**

Engineered-only:

- validation AUC: 0.724
- final test AUC: **0.778**

Baseline:

- validation AUC: 0.812
- final test AUC: 0.649

The new micro-shape features materially improve robustness on the final chronological test.

Important features include:

- 1m-vs-3m micro acceleration
- 1m/3m micro ratio
- heat x micro fade
- 5m-vs-15m acceleration
- overheat pressure
- family balance / regime support

Formal status:

**PROMISING**

This supports a future path-shape head that can tell Stage12 whether early drawdown is more likely to be:

- normal / recoverable
- or failure / exhaustion

## 9. Architectural meaning

WD-5D changes the direction of the next detector design.

The strongest causal information is not yet:

> "this will be a 2% runner"

It is:

> "this otherwise-valid continuation is healthy versus becoming overheated."

That suggests the future Opportunity Detector should not be a single BIG-RUNNER classifier.

A better architecture is:

```text
CURRENT CONTINUATION THESIS
          |
          +-- Healthy expansion
          |      -> allow continuation
          |      -> runner-preservation candidate
          |
          +-- Overheated expansion
          |      -> do not chase
          |      -> evaluate reversal thesis
          |
          +-- Weak/no edge
                 -> skip / aggressive protection
```

This directly complements WD-5B, where the system lacked an explicit opposite/reversal thesis.

## 10. What is and is not ready

### Ready for the next research stage

- `overheat_pressure`
- multi-timeframe acceleration / curvature
- activity heat
- score x activity heat
- micro-fade interactions
- clean/recovered path features

### Not ready for production

- threshold 5.4819
- BIG_RUNNER prediction
- >=1% runner-only entry filtering
- reversal execution
- automatic Stage12 mode assignment

## Frozen artefacts

### Feature dataset

`/opt/core-app/data/wd5d_opportunity_exhaustion_features.csv`

SHA256:

`b8cbd671a278d74e2b68412b9a49fd3882e984e152fb8c92cc66452b1ce5ad2d`

### Full discovery result

`/opt/core-app/data/wd5d_feature_discovery_results.json`

SHA256:

`6110bcc8733986c5bf4b1aff29ee813bee6a261b235a8e11360de120bc60f2ca`

## Handoff

The next stage should use the WD-5D features to build a multi-head causal detector.

However, because absolute runner-size prediction remains weak, it should **not** immediately be framed as "predict BIG RUNNER."

The most defensible next heads are:

1. healthy continuation vs overheated continuation
2. clean path vs recovered path
3. continuation thesis vs reversal thesis
4. only later, conditional runner-size probability

This preserves the strongest discovered signal instead of forcing an unsupported exact-runner classifier.
