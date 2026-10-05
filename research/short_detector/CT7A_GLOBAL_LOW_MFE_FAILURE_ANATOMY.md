# SHORT-CT7A — Global Low-MFE Failure Anatomy

Status: **PASS anatomy / low-MFE failure has a global non-temporal market-morphology signature**

## Objective

CT-7A intentionally stops using T0/T1/T2/T3 as the primary research basis.

The question is:

> Across the entire SHORT universe, what causal market-state characteristics distinguish trades that eventually fail to produce MFE >=0.50% from trades that eventually produce MFE >=1.00%?

Primary populations:

- **BAD** = future max MFE <0.50%
- **TARGET-MFE** = future max MFE >=1.00%
- **GRAY** = 0.50% <= future max MFE <1.00%, excluded from the primary binary contrast but retained for severity anatomy

Population:

- BAD: **398 selected**
- GRAY: 363
- TARGET-MFE: **326 selected**
- Total selected: 1,087

No T1/T2/T3 feature is used in the main analysis.

Lane is not used to build the separation. Lane is only used as a secondary transport check.

Future max MFE is a research label only.

No runtime or paper-entry change is authorized by CT-7A.

## Feature universe

Research and Fresh share 236 columns. After removing metadata and all temporal T features, CT-7A evaluates **228 common non-temporal candidate features**. Of those, **214 numeric/high-coverage causal features** are usable.

A strict global-stability feature must satisfy coverage >=95%, overall AUC separation >=0.58, same BAD direction in Research and Fresh, same direction in at least 5/6 chronological blocks, and same direction in at least 3/4 lanes.

Result:

> **18 globally stable features**

This is the first important CT-7A result: low-MFE failure is not only visible after temporal confirmation. It already has a causal global morphology before the T framework is applied.

## Strongest global separators

| Feature | Concept | BAD direction | Separation | Research AUC | Fresh AUC | Blocks | Lanes |
|---|---|---|---:|---:|---:|---:|---:|
| f_micro_distance_selected_extreme_15m | distance from selected extreme | LOW | **0.654** | 0.349 | 0.343 | 5/6 | **4/4** |
| f_ret_1h_pct_for_selected | 1h selected-side momentum | LOW | **0.651** | 0.327 | 0.358 | **6/6** | **4/4** |
| f_f_relative_overextension_30m | relative move vs market | LOW | **0.646** | 0.429 | 0.324 | **6/6** | **4/4** |
| f_f_coin_minus_market_30m | coin minus market 30m | LOW | **0.646** | 0.429 | 0.324 | **6/6** | **4/4** |
| f_micro_side_ret_30m | 30m side move | LOW | **0.635** | 0.430 | 0.339 | 5/6 | **4/4** |
| f_median_abs_ret_5m_pct | movement amplitude | LOW | **0.627** | 0.374 | 0.372 | 5/6 | **4/4** |
| f_context_quote_volume_5m | liquidity/activity | LOW | **0.613** | 0.403 | 0.380 | 5/6 | **4/4** |
| f_gate_side_ret_3m_pct | immediate side momentum | LOW | **0.607** | 0.437 | 0.375 | 5/6 | **4/4** |
| f_f_coin_residual_5m_vs_btc | move vs BTC | LOW | **0.595** | 0.405 | 0.406 | **6/6** | **4/4** |
| f_micro_selected_vwap_extension_20 | VWAP extension | LOW | **0.583** | 0.440 | 0.409 | 5/6 | **4/4** |

The consistent direction is important: the global BAD population is generally **weaker**, not stronger, on directional movement, relative-market strength, distance from the selected extreme, and activity/liquidity.

This is different from the earlier hypothesis that low-MFE failure would mainly be an overheat/exhaustion problem.

## Severity anatomy

Several features show a clean progression from BAD-A -> BAD-B -> GRAY -> TARGET.

### 1h selected-side return

- BAD-A: **1.149%**
- BAD-B: **1.376%**
- GRAY: **1.689%**
- TARGET: **1.822%**

### 30m micro selected-side return

- BAD-A: **1.045%**
- BAD-B: **1.051%**
- GRAY: **1.435%**
- TARGET: **1.449%**

### Median absolute 5m return

- BAD-A: **0.162%**
- BAD-B: **0.163%**
- GRAY: **0.195%**
- TARGET: **0.208%**

### 3m selected-side return

- BAD-A: **0.472%**
- BAD-B: **0.506%**
- GRAY: **0.559%**
- TARGET: **0.598%**

### 5m coin residual vs BTC

- BAD-A: **0.607**
- BAD-B: **0.624**
- GRAY: **0.720**
- TARGET: **0.731**

These monotonic variables are especially useful for CT-7B because they behave like a severity spectrum rather than a binary artifact.

## Not every strong separator is monotonic

Example: f_micro_distance_selected_extreme_15m medians are BAD-A 0.127, BAD-B 0.136, GRAY 0.292, TARGET 0.205.

It separates BAD from TARGET globally, but GRAY exceeds TARGET. Therefore CT-7A does **not** support a simple universal threshold on this feature.

This is one reason the next stage should search for **failure archetypes / interactions**, not blindly threshold the top-AUC variable.

## Global feature-family anatomy

| Family | Numeric features | Stable global features | Best separation |
|---|---:|---:|---:|
| **Microstructure** | 27 | **5** | **0.654** |
| **Market-relative** | 21 | **4** | **0.646** |
| Signal kinematics | 12 | 2 | 0.651 |
| Selection-state momentum | 22 | 2 | 0.624 |
| Gate snapshot | 27 | 2 | 0.607 |
| Context | 18 | 1 | 0.613 |
| OI / positioning | 17 | **0** | 0.576 |
| Momentum-extension derived | 9 | **0** | 0.574 |
| Flow / taker | 33 | **0** | 0.569 |
| Activity/heat derived | 6 | **0** | 0.532 |
| Latency | 3 | 0 | 0.532 |

Under a strict global transport requirement, OI, taker-flow, heat, and overheat variables do not produce a standalone globally stable separator. That does not mean they are useless; they are more likely to matter as archetype-specific interactions or secondary confirmation inside a failure cluster.

The universal axis is much more clearly:

> **insufficient directional displacement + insufficient relative strength + insufficient movement/activity**

## Redundancy check

The 18 stable variables are not 18 independent signals. High correlations collapse them into roughly **9 independent concepts**:

1. distance from selected extreme
2. 1h directional momentum
3. 30m relative/directional displacement
4. movement amplitude
5. existing momentum score
6. liquidity/activity
7. immediate 3m side momentum
8. short-horizon relative strength vs BTC
9. VWAP extension

Examples of redundancy:

- 15m vs 30m distance: Spearman **0.946**
- selected 1h return vs raw 1h return: inverse **-1.000**
- relative overextension 30m vs coin-minus-market 30m: **1.000**
- selected momentum score vs delta momentum score: **0.984**
- gate 3m side return vs micro 3m side return: **1.000**

CT-7B therefore must not double-count correlated variables as independent evidence.

## Lane independence

Lane was not used in discovery, yet the strongest global variables preserve the same BAD direction across all four lanes.

1h selected return AUC by lane: T0 0.288, T1 0.395, T2 0.391, T3 0.310.

Relative overextension 30m by lane: T0 0.355, T1 0.374, T2 0.356, T3 0.346.

5m residual vs BTC by lane: T0 0.398, T1 0.392, T2 0.411, T3 0.397.

This is strong evidence that the low-MFE morphology is **not created by the T architecture itself**.

T influences when/how the trade enters, but the underlying weak-opportunity state already exists globally.

## Chronological transport

The most convincing variables also transport through the six time blocks. Examples: 1h selected-side return, relative overextension 30m, and 5m residual vs BTC all point in the BAD direction in **6/6 blocks**.

The signal survives Research Discovery, Research Validation, Research Reserve, Fresh Oct 1, Fresh Oct 2, and Fresh Oct 3.

## What CT-7A changes conceptually

The working model should now be:

> A large share of MFE <0.50% trades are not mainly good trades confirmed at the wrong T.

Instead, many are:

> **underpowered opportunities that already lack sufficient displacement, relative strength, movement amplitude, or activity before temporal confirmation.**

This explains why the T-based low-MFE veto had low coverage.

## CT-7A verdict

> **PASS global anatomy.**

Evidence supports a dedicated Low-MFE Failure Detector upstream of the T confirmation system.

The primary research basis should remain **global causal market morphology**, not T1/T2/T3 lane membership.

However, CT-7A does **not** authorize a universal hard threshold yet because single-feature separation is moderate, several strong variables are highly redundant, some variables are not monotonic through GRAY, and the likely solution is multiple failure archetypes rather than one BAD rule.

## Frozen input for CT-7B

CT-7B should perform **Failure Archetype Discovery** using the approximately 9 independent signal concepts.

Primary concepts:

1. 1h selected-side momentum
2. 30m relative/directional displacement
3. distance from selected extreme
4. movement amplitude / volatility
5. 3m immediate side momentum
6. 5m relative residual vs BTC/market
7. liquidity/activity
8. VWAP extension
9. selected momentum score only as a secondary/current-detector state variable

CT-7B should search for combinations such as weak displacement + weak relative strength, weak momentum + low activity, or weak short-horizon movement + weak BTC residual, rather than increasing one threshold globally.

The target remains to maximize BAD-A/B rejection while preserving TARGET-MFE and strong trades across Research, Fresh, chronological blocks, and lanes.

No runtime promotion is authorized.