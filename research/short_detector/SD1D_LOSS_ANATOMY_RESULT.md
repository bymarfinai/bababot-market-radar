# SD-1D — SHORT Loss Anatomy & Failure Clustering

Status: **PASS loss heterogeneity / PASS_DIAGNOSTIC_ONLY for detector research**

## Frozen scope

- resolved SHORT universe: **655**
- META_LOSS: **492**
- loss split D/V/R: **295 / 90 / 107**
- strong WIN reference: **99**
- winner split D/V/R: **59 / 27 / 13**
- loss clustering fit population: **295 Discovery META_LOSS only**
- Validation and Reserve loss rows: projection-only
- provisional winner assignments are reused only as frozen external anatomy from SD-1C

No LONG threshold, feature direction, or cluster proportion was imported.

---

# 1. Independent loss clustering

## Preprocessing

From the same 224 T0 feature family:

- 210 numeric
- 14 categorical
- 193 numeric fields eligible before correlation pruning
- 146 retained numeric after |r| > 0.95 pruning
- 47 correlated numeric removed
- 51 one-hot categorical columns
- final model matrix: **197 columns**
- PCA: **31 components**
- explained Discovery loss variance: **80.34%**

All preprocessing was fit on Discovery META_LOSS only.

## k search

| k | Valid | Discovery sizes | Silhouette | Bootstrap ARI median | ARI p25 |
|---:|---|---|---:|---:|---:|
| **2** | **YES** | **82 / 213** | **0.1877** | **0.8900** | **0.8344** |
| 3 | YES | 185 / 55 / 55 | 0.1629 | 0.6828 | 0.6501 |
| 4 | NO | contains 3-trade cluster | — | — | — |
| 5 | NO | contains 3-trade cluster | — | — | — |
| 6 | NO | contains 3-trade cluster | — | — | — |
| 7 | NO | contains sub-15 clusters | — | — | — |
| 8 | NO | contains sub-15 clusters | — | — | — |

Frozen selected structure:

> **k = 2**

## Preregistered loss-cluster gates

| Gate | Result |
|---|---|
| k >= 2 | PASS |
| Discovery silhouette >= 0.10 | PASS |
| bootstrap median ARI >= 0.50 | **PASS — 0.890** |
| every Discovery cluster >= 15 | PASS |
| Validation has >=2 projected clusters | PASS |
| Reserve has >=2 projected clusters | PASS |

Therefore:

> **SHORT LOSS HETEROGENEITY IS STRUCTURALLY CONFIRMED.**

This is much stronger than SD-1C winner clustering, whose bootstrap ARI was only 0.424.

---

# 2. Frozen SHORT loss regimes

## SHORT_LOSS_CLUSTER_0 — provisional FLOW_GAP_FAILURE

Total:
- **123 / 492 = 25.0%**
- D/V/R = **82 / 24 / 17**

Economics:
- median MFE: **0.579%**
- mean MFE: **0.793%**
- median MAE: **-1.089%**
- historical PnL: **-$295.01**
- average historical return: **-0.480%**
- historical realized-positive: **3 / 123**

WD1 outcome anatomy:
- RIGHT_THEN_FAILURE: **68 / 123 = 55.3%**
- TRUE_WRONG_DIRECTION: **39 / 123 = 31.7%**
- STALL_NO_EDGE: **13**
- CORRECT_RUNNER: 2
- RECOVERED_DRAWDOWN: 1

This lane generally generated more favorable excursion than the other loss cluster, but then failed.

## SHORT_LOSS_CLUSTER_1 — provisional FLOW_ALIGNED_FAILURE

Total:
- **369 / 492 = 75.0%**
- D/V/R = **213 / 66 / 90**

Economics:
- median MFE: **0.310%**
- mean MFE: **0.407%**
- median MAE: **-0.888%**
- historical PnL: **-$912.11**
- average historical return: **-0.494%**
- historical realized-positive: **12 / 369**

WD1 outcome anatomy:
- TRUE_WRONG_DIRECTION: **214 / 369 = 58.0%**
- RIGHT_THEN_FAILURE: **112 / 369 = 30.4%**
- STALL_NO_EDGE: **31**
- RECOVERED_DRAWDOWN: 11
- CORRECT_RUNNER: 1

This lane is the dominant source of SHORT loss dollars.

---

# 3. Winner ↔ loss regime mapping

The preregistered six-feature signature mapping was applied only after loss k=2 was frozen.

Signature features:
- selected-side taker share
- side return 1m
- flow support
- price × flow gap
- micro acceleration 1m vs 3m
- coin minus market 15m

## Frozen mapping

> **Winner ARCHETYPE_0 → LOSS_CLUSTER_0**

> **Winner ARCHETYPE_1 → LOSS_CLUSTER_1**

Mapping distances:
- winner0 → loss0: **1.211**
- winner0 → loss1: 3.037
- winner1 → loss0: 3.661
- winner1 → loss1: **0.177**

Selected total one-to-one distance:
- **1.388**

Alternative cross-mapping:
- **6.698**

So the mapping is not marginal; the aligned winner regime is particularly close to the aligned failure regime in the frozen signature space.

## Structural proportions

Winner provisional regimes:
- ARCHETYPE_0: **30.3%**
- ARCHETYPE_1: **69.7%**

Loss frozen regimes:
- LOSS_CLUSTER_0: **25.0%**
- LOSS_CLUSTER_1: **75.0%**

The proportions are remarkably similar.

This repeats the key lesson from LONG research:

> **archetype identity itself is not the edge.**

The detector must distinguish:

1. flow-gap / counterflow WIN from flow-gap / counterflow FAILURE;
2. flow-aligned / recovery WIN from flow-aligned FAILURE.

---

# 4. Within-regime separation — Lane 0

Frozen populations:

| Split | Winner A0 | Loss L0 |
|---|---:|---:|
| Discovery | 17 | 82 |
| Validation | 8 | 24 |
| Reserve | 5 | 17 |

## Best D+V frozen feature

`f_f_market_dispersion_15m`

Frozen direction:
> **HIGH favors WIN**

AUC:
- Discovery: **0.711**
- Validation: **0.708**
- Reserve: **0.441**

For comparison, aggregate Discovery strong-WIN-vs-loss separation on this feature was only:

> **0.543**

So within-regime separation dramatically improved D/V, but **reversed on Reserve**.

Other notable D/V candidates:

| Feature | Direction | D AUC | V AUC | R AUC |
|---|---|---:|---:|---:|
| market dispersion 15m | HIGH | **0.711** | **0.708** | **0.441** |
| impulse concentration | LOW | 0.670 | 0.615 | 0.435 |
| volume ratio last/prev10 | LOW | 0.592 | 0.583 | 0.671 |
| selected taker share 3m | LOW | 0.613 | 0.562 | 0.741 |
| context regime LL | LOW | 0.556 | 0.568 | 0.788 |

Counts:
- features with D and V >=0.60: **2**
- features with D/V/R all >=0.60: **0**

Post-hoc all-split floor diagnostic:
- best floor: **0.583**
- feature: `f_micro_volume_ratio_last_vs_prev10`
- D/V/R = **0.592 / 0.583 / 0.671**

This post-hoc diagnostic is **not** a frozen detector candidate.

---

# 5. Within-regime separation — Lane 1

Frozen populations:

| Split | Winner A1 | Loss L1 |
|---|---:|---:|
| Discovery | 42 | 213 |
| Validation | 19 | 66 |
| Reserve | 8 | 90 |

## Best D+V frozen feature

`f_median_abs_ret_5m_pct`

Frozen direction:
> **HIGH favors WIN**

AUC:
- Discovery: **0.622**
- Validation: **0.724**
- Reserve: **0.450**

Aggregate Discovery separation was already about:
- **0.618**

So this lane shows less aggregate-cancellation benefit than Lane 0, and the candidate still fails Reserve.

Other notable D/V candidates:

| Feature | Direction | D AUC | V AUC | R AUC |
|---|---|---:|---:|---:|
| median abs return 5m | HIGH | **0.622** | **0.724** | **0.450** |
| selected slope5 norm | HIGH | 0.612 | 0.604 | 0.422 |
| micro decay 5 vs prev5 | LOW | 0.601 | 0.636 | 0.342 |
| range contraction after impulse | LOW | 0.596 | 0.613 | 0.556 |
| extension 15m norm | LOW | 0.586 | 0.727 | 0.422 |

Counts:
- features with D and V >=0.60: **3**
- features with D/V/R all >=0.60: **0**

Post-hoc all-split floor diagnostic:
- best floor: **0.567**
- feature: `f_new_heat_x_extension`
- D/V/R = **0.630 / 0.581 / 0.567**

Again, this is anatomy only.

---

# 6. Main SD-1D finding

SD-1D produces two simultaneous conclusions.

## Conclusion A — loss heterogeneity is real and stable

Unlike the provisional winner clustering:

- winner bootstrap ARI: **0.424**
- loss bootstrap ARI: **0.890**

The SHORT loss universe contains a robust two-regime structure.

The 25% / 75% loss composition also closely mirrors the provisional 30% / 70% winner composition.

## Conclusion B — matching winner and loss regimes helps diagnosis, but does not yet solve entry

Lane 0 shows a strong example of hidden conditional structure:

- aggregate Discovery AUC: **0.543**
- within-regime Discovery: **0.711**
- within-regime Validation: **0.708**

This confirms that aggregate mixing can hide useful signal.

But Reserve drops to:

> **0.441**

Lane 1 similarly drops from a promising D/V pair to:

> **0.450 Reserve AUC**

And across both lanes:

> **0 features maintained oriented AUC >=0.60 across Discovery, Validation, and Reserve.**

Therefore the correct conclusion is not that regime separation failed.

The correct conclusion is:

> **regime separation reveals conditional signal, but no single T0 feature is stable enough to become the SHORT detector.**

---

# 7. Comparison to LONG reference

LONG loss anatomy historically found:
- approximately 72.1% flow-aligned failure;
- approximately 27.9% counterflow failure;
- flow-aligned winner-vs-failure weak at T0;
- counterflow winner-vs-failure materially more separable.

SHORT now shows:
- **75.0% aligned failure**
- **25.0% flow-gap failure**

The composition is again strikingly similar.

However, SHORT Lane 0's promising D/V separation does **not** survive Reserve, so the LONG counterflow result must not be copied over.

---

# 8. Verdict

## Loss clustering

**PASS_LOSS_HETEROGENEITY**

The 492 META_LOSS population has a robust k=2 structure.

## Standalone within-regime single-feature detector

**NO PASS**

No frozen single feature survives the D/V/R >=0.60 stability requirement in either matched regime.

## Overall SD-1D

> **PASS_DIAGNOSTIC_ONLY**

What is now established:
1. SHORT losses have two robust regimes.
2. Those regimes map cleanly to the two provisional winner regimes.
3. Winner and loss regime proportions are similar.
4. Archetype identity alone is not an edge.
5. Conditional within-regime signal can be much stronger than aggregate signal.
6. Single-feature T0 separation is still not stable enough on Reserve.

What is not authorized:
- live archetype router;
- SHORT entry threshold;
- loss veto;
- paper or production deployment.

## Next playbook-compatible stage

The next research stage should be **SD-2A — archetype-specific multi-feature combinations**.

It should keep both lanes separate:
- Lane 0: provisional FLOW_GAP WIN vs FLOW_GAP FAILURE;
- Lane 1: provisional FLOW_ALIGNED/RECOVERY WIN vs FLOW_ALIGNED FAILURE.

Because SD-1C winner clustering missed its ARI gate, these remain research lanes rather than production classes.