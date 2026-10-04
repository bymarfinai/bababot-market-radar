# SD-1C — SHORT Winner Anatomy & Clustering

Status: **NO PASS under preregistered stability gate / strong two-regime anatomy evidence**

## Frozen scope

- full resolved SHORT universe: **655**
- strong SHORT winners: **99**
- Discovery / Validation / Reserve strong winners: **59 / 27 / 13**
- clustering fit population: **Discovery strong winners only (59)**
- Validation and Reserve: projection-only
- no META_LOSS row participated in clustering or k selection
- no LONG archetype label, threshold, or feature direction was imported

## Preprocessing

Starting from the same SD-1B T0 feature universe:

- 224 modeled T0 fields
- 210 numeric
- 14 categorical
- 192 numeric fields had sufficient Discovery-winner coverage and non-zero variance
- correlation pruning at |r| > 0.95 left **136 numeric**
- 46 one-hot categorical columns
- final model matrix: **182 columns**
- PCA: **18 components**
- Discovery variance explained: **81.14%**

All imputation, correlation pruning, scaling, PCA, and KMeans fitting used only the 59 Discovery strong winners.

## k search

The preregistered minimum Discovery cluster size was 5.

| k | Valid? | Discovery cluster sizes | Silhouette | Bootstrap ARI median | ARI p25 |
|---:|---|---|---:|---:|---:|
| **2** | **YES** | **17 / 42** | **0.1955** | **0.4242** | **0.3112** |
| 3 | NO | 4 / 39 / 16 | — | — | — |
| 4 | NO | 9 / 27 / 1 / 22 | — | — | — |
| 5 | NO | contains 1-trade clusters | — | — | — |
| 6 | NO | contains 1-trade clusters | — | — | — |
| 7 | NO | contains 1-trade clusters | — | — | — |
| 8 | NO | contains 1-trade clusters | — | — | — |

Frozen selected structure: **k = 2**.

### Preregistered gates

| Gate | Result |
|---|---|
| k >= 2 | PASS |
| Discovery silhouette >= 0.10 | PASS |
| Bootstrap median ARI >= 0.50 | **FAIL — 0.424** |
| Min Discovery cluster >= 5 | PASS |
| Validation projects to >=2 clusters | PASS |
| Reserve projects to >=2 clusters | PASS |

Therefore:

> **SD-1C does not formally confirm stable winner clustering under the preregistered gate.**

The ARI threshold is not relaxed post hoc.

However, the projected economic / flow anatomy is highly structured and is retained as a **provisional two-regime hypothesis** for the next diagnostic stage.

---

# Provisional SHORT winner regimes

The neutral cluster IDs remain authoritative. Semantic labels below are descriptive only.

## SHORT_ARCHETYPE_0 — provisional FLOW_GAP / COUNTERFLOW regime

Total:
- **30 / 99 = 30.3%**
- D/V/R = **17 / 8 / 5**
- D/V/R shares = **28.8% / 29.6% / 38.5%**

Economics:
- median MFE: **1.943%**
- mean MFE: **2.122%**
- historical realized PnL: **+$92.58**
- average realized return: **+0.617%**
- realized-positive: **26 / 30 = 86.7%**

Historical WD1 outcome:
- CORRECT_RUNNER: **13**
- RECOVERED_DRAWDOWN: **13**
- RIGHT_THEN_FAILURE: **4**

Typical T0 signature:
- selected-side taker share median: **0.448**
- 1m selected-side return median: **-0.014%**
- flow-support median: **-0.50**
- price-vs-flow gap median: **+0.076**
- micro acceleration 1m-vs-3m median: **-0.210**
- coin-minus-market 15m median: **+1.589%**

Interpretation:

> Price / relative-strength can already be elevated while immediate order flow is weak or opposing. The winner later resolves despite a visible price-flow mismatch.

This is why the semantic description **FLOW_GAP / COUNTERFLOW** is reasonable, but it remains provisional because cluster bootstrap stability missed the gate.

## SHORT_ARCHETYPE_1 — provisional FLOW_ALIGNED / RECOVERY regime

Total:
- **69 / 99 = 69.7%**
- D/V/R = **42 / 19 / 8**
- D/V/R shares = **71.2% / 70.4% / 61.5%**

Economics:
- median MFE: **1.401%**
- mean MFE: **1.898%**
- historical realized PnL: **+$173.84**
- average realized return: **+0.504%**
- realized-positive: **65 / 69 = 94.2%**

Historical WD1 outcome:
- RECOVERED_DRAWDOWN: **63 / 69 = 91.3%**
- CORRECT_RUNNER: **2**
- RIGHT_THEN_FAILURE: **4**

Typical T0 signature:
- selected-side taker share median: **0.706**
- 1m selected-side return median: **+0.179%**
- flow-support median: **+1.00**
- price-vs-flow gap median: **0**
- micro acceleration 1m-vs-3m median: **+0.012**
- coin-minus-market 15m median: **+0.929%**

Interpretation:

> This is a much more flow-aligned T0 state, but historically most winners still pass through a recovered-drawdown path before ultimately winning.

The semantic description **FLOW_ALIGNED / RECOVERY** is therefore supported by both T0 flow anatomy and historical trajectory, while remaining provisional.

---

# Split stability

The two projected cluster shares do **not** collapse out of sample:

| Cluster | Discovery | Validation | Reserve | max shift vs D |
|---|---:|---:|---:|---:|
| ARCHETYPE_0 | 28.8% | 29.6% | 38.5% | 9.6 pp |
| ARCHETYPE_1 | 71.2% | 70.4% | 61.5% | 9.6 pp |

This is encouraging.

Reserve support is small (**13 total winners**), so composition stability must not be overstated.

Centroid-distance behavior is generally reasonable in Reserve; ARCHETYPE_0 Validation contains one large-distance outlier and should be inspected in later work.

---

# Strong feature separation between the two winner regimes

On Discovery winners, the strongest original-feature separators include:

| Feature | ARCHETYPE_0 | ARCHETYPE_1 | Separation AUC |
|---|---:|---:|---:|
| gate taker share for selected side | lower | higher | **0.958** |
| price x flow gap | higher | lower | **0.953** |
| heat x flow gap | higher | lower | **0.952** |
| flow gap gate | higher | lower | **0.947** |
| gate price x flow gap | higher | lower | **0.946** |
| micro selected taker share 1m | lower | higher | **0.945** |
| flow support | lower | higher | **0.899** |

This gives the k=2 structure a coherent market interpretation rather than a purely abstract PCA partition.

---

# Signal cancellation vs META_LOSS

After the two winner regimes were frozen, the 492 META_LOSS rows were used only as an external contrast.

This reveals a very important mechanism behind SD-1B.

## Selected-side taker share

Aggregate strong WIN vs LOSS:
- separation AUC: only **0.546**

But by provisional winner regime:
- ARCHETYPE_0 vs LOSS: **0.847**, useful direction = **LOW**
- ARCHETYPE_1 vs LOSS: **0.585**, useful direction = **HIGH**

So the two winner regimes point in **opposite directions**.

## Gate price x flow gap

Aggregate:
- separation AUC: **0.526**

By regime:
- ARCHETYPE_0 vs LOSS: **0.839**, useful direction = **HIGH**
- ARCHETYPE_1 vs LOSS: **0.611**, useful direction = **LOW**

Again: opposite direction.

## Flow support

Aggregate:
- separation AUC: **0.522**

By regime:
- ARCHETYPE_0 vs LOSS: **0.789**, useful direction = **LOW**
- ARCHETYPE_1 vs LOSS: **0.593**, useful direction = **HIGH**

Again: cancellation.

## Micro reversal pressure

Aggregate:
- separation AUC: **0.522**

By regime:
- ARCHETYPE_0 vs LOSS: **0.724**, useful direction = **HIGH**
- ARCHETYPE_1 vs LOSS: **0.628**, useful direction = **LOW**

Again: opposite direction.

### Core insight

This is the strongest SD-1C finding:

> **Several features that looked nearly useless in aggregate SD-1B become materially informative inside one winner regime, with opposite useful directions across regimes.**

This is exactly the kind of cancellation mechanism that a universal single-feature SHORT detector cannot represent.

---

# Relationship to SD-1A

SD-1A showed:

- 99 strong SHORT winners
- 76 RECOVERED_DRAWDOWN
- 15 CORRECT_RUNNER
- 8 RIGHT_THEN_FAILURE

SD-1C refines that:

### ARCHETYPE_0 (30)
- 13 CORRECT_RUNNER
- 13 RECOVERED_DRAWDOWN
- 4 RIGHT_THEN_FAILURE

### ARCHETYPE_1 (69)
- **63 RECOVERED_DRAWDOWN**
- 2 CORRECT_RUNNER
- 4 RIGHT_THEN_FAILURE

Therefore the headline “76/99 winners are recovered drawdown” is mostly driven by one dominant **flow-aligned recovery regime**, not uniformly by all SHORT winners.

That distinction matters for future detector design.

---

# Comparison with LONG winner anatomy

LONG Stage 3C.1B historical reference:
- selected k = 2
- silhouette ≈ **0.171**
- bootstrap ARI median ≈ **0.812**
- cluster mix ≈ 26.5% counterflow / 73.5% flow-aligned

SHORT SD-1C:
- selected k = 2
- silhouette = **0.195**
- bootstrap ARI median = **0.424**
- projected mix ≈ 30.3% flow-gap / 69.7% flow-aligned-recovery

The proportions and market meaning look surprisingly similar, but the **SHORT clustering is materially less bootstrap-stable**.

Therefore we must not simply declare that SHORT has replicated the LONG archetypes.

---

# Verdict

**SD-1C = NO_PASS_UNSTABLE_CLUSTERING under the preregistered gate.**

At the same time:

**TWO-REGIME CANCELLATION EVIDENCE = STRONG.**

What we can safely say:
1. A k=2 Discovery structure is the only non-tiny cluster solution.
2. The two projected groups remain present in Validation and Reserve.
3. Their T0 flow signatures are strongly different.
4. Several aggregate-near-random features reverse useful direction between the two groups.
5. This provides a strong explanation for SD-1B instability.

What we cannot say yet:
- the two cluster IDs are production-stable archetypes;
- either cluster can be routed live;
- either cluster has entry authority;
- the bootstrap gate can be relaxed from 0.50 to 0.424 after seeing the result.

## Next research step

The playbook-compatible next stage is **SD-1D — SHORT Loss Anatomy**.

It should:
- characterize the 492 META_LOSS independently;
- test whether losses also exhibit flow-gap vs flow-aligned structure;
- compare provisional winner regime against matching failure regime;
- determine whether within-regime separation is materially stronger than the aggregate SD-1B scan.

Because SD-1C did not pass the stability gate, SD-1D must treat these winner regimes as **provisional reference anatomy**, not a live router.