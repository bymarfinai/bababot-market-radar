# SHORT-CT7B — Global Low-MFE Failure Archetype Discovery

Status: **PASS discovery / three broad failure archetypes found / NOT veto-ready**

## Objective

CT-7B stops treating T0/T1/T2/T3 as the organizing framework and searches directly for recurring combinations of the global non-temporal morphology discovered in CT-7A.

Primary labels remain:

- BAD-A: future max MFE <0.30%
- BAD-B: 0.30% <= future max MFE <0.50%
- GRAY: 0.50% <= future max MFE <1.00%
- TARGET-MFE: future max MFE >=1.00%

Future MFE is used only as a research label.

No T1/T2/T3 feature is used.

Lane is not used as a model basis.

No runtime or paper-entry change is authorized.

## Feature basis

CT-7B uses eight independent morphology representatives from CT-7A:

1. distance from selected extreme 15m
2. selected-side return 1h
3. relative overextension 30m
4. median absolute return 5m
5. quote volume 5m
6. immediate side return 3m
7. coin residual 5m vs BTC
8. selected VWAP extension 20

Existing detector momentum-score features are excluded from the core archetype search to reduce circularity.

## Threshold contract

All weak-state thresholds are fit only from the **Research Discovery TARGET-MFE** population.

The selected archetypes use the 45th percentile of TARGET values:

| Feature | P45 TARGET threshold |
|---|---:|
| distance selected extreme 15m | **0.183672** |
| selected-side return 1h | **1.812068%** |
| relative overextension 30m | **1.003325** |
| median abs return 5m | **0.191196%** |
| coin residual 5m vs BTC | **0.699792** |
| VWAP extension 20 | **0.654604** |

A value at or below the threshold means that morphology dimension is weak relative to the Research Discovery TARGET distribution.

## Candidate search

CT-7B scans interpretable pair/triple combinations using TARGET quantile thresholds.

Discovery filters require:

- meaningful BAD support in Research Discovery;
- BAD-vs-TARGET precision in discovery;
- transport into Research Validation/Reserve;
- transport into Fresh;
- no dependence on T lane.

Result:

> **131 transport-qualified candidate archetype rules**

These are not execution rules. They are candidate descriptions of recurring weak-opportunity states.

A diversity/overlap pass selects three representative archetypes.

---

# Archetype A1 — LOW DISPLACEMENT

Definition:

> distance from selected extreme 15m <= **0.183672**
>
> AND selected-side return 1h <= **1.812068%**

Interpretation:

> the coin has not displaced far enough in the selected direction and remains too close to its recent selected-side extreme.

Coverage:

- BAD-A: **134**
- BAD-B: **70**
- BAD total: **204 / 398 = 51.26%**
- GRAY: 75
- TARGET: **80 / 326 = 24.54%**
- strong selected: **74**
- strong executable: 71

BAD-vs-TARGET precision:

> **71.83%**

Executable cohort PnL:

> **-$320.53**

A1 is the broadest archetype and establishes that more than half of all low-MFE failures live in a low-displacement state.

But the 74 strong trades inside A1 prove that low displacement alone cannot be used as a hard kill rule.

---

# Archetype A2 — WEAK RELATIVE EXPANSION

Definition:

All three must be weak:

> selected-side return 1h <= **1.812068%**
>
> relative overextension 30m <= **1.003325**
>
> VWAP extension 20 <= **0.654604**

Interpretation:

> weak absolute displacement + weak move relative to the market + weak local extension from VWAP.

Coverage:

- BAD-A: **104**
- BAD-B: **63**
- BAD total: **167 / 398 = 41.96%**
- GRAY: 80
- TARGET: **66 / 326 = 20.25%**
- strong selected: **59**
- strong executable: 59

BAD-vs-TARGET precision:

> **71.67%**

Executable cohort PnL:

> **-$262.99**

A2 catches a large failure population that is not identical to A1.

---

# Archetype A3 — LOW ENERGY RESIDUAL

Definition:

All three must be weak:

> distance from selected extreme 15m <= **0.183672**
>
> median absolute return 5m <= **0.191196%**
>
> coin residual 5m vs BTC <= **0.699792**

Interpretation:

> low local movement energy + weak idiosyncratic move versus BTC + insufficient selected-side displacement.

Coverage:

- BAD-A: **82**
- BAD-B: **45**
- BAD total: **127 / 398 = 31.91%**
- GRAY: 43
- TARGET: **54 / 326 = 16.56%**
- strong selected: **48**
- strong executable: 47

BAD-vs-TARGET precision:

> **70.17%**

Executable cohort PnL:

> **-$183.68**

A3 is narrower than A1/A2 but represents a distinct low-energy / low-residual failure mode.

---

## BAD overlap between archetypes

The three archetypes are related but not duplicates.

| Pair | BAD Jaccard overlap |
|---|---:|
| A1 vs A2 | **0.390** |
| A1 vs A3 | **0.511** |
| A2 vs A3 | **0.380** |

This is important.

A pure duplicate pair would approach 1.0.

Here the overlap is moderate, which means the archetypes describe multiple weak-opportunity structures rather than the same threshold under different names.

## Marginal BAD contribution

Using the frozen order A1 -> A2 -> A3:

- A1 contributes **204 BAD**
- A2 adds **63 new BAD** not already in A1
- A3 adds another **15 new BAD**

Union:

> **282 / 398 BAD = 70.85%**

This is the main CT-7B success.

The T-based CT-6C clean veto covered only about 10% of T2 BAD.

The global morphology architecture now identifies failure territory containing more than **70% of all low-MFE BAD trades**.

---

## Union anatomy

A1 OR A2 OR A3 covers:

- 541 selected trades
- 512 executable
- BAD-A: **176**
- BAD-B: **106**
- BAD total: **282**
- GRAY: 137
- TARGET: **122**
- strong selected: **109**
- strong executable: **106**
- executable cohort PnL: **-$424.08**

BAD recall:

> **70.85%**

BAD-vs-TARGET precision:

> **69.80%**

But TARGET hit rate is:

> **37.42%**

This is far too high for a veto.

The union also contains 109 strong trades.

Therefore:

> **CT-7B is a successful discovery map, not a kill rule.**

---

## Chronological transport of the union

| Block | BAD captured | BAD recall | TARGET captured | Precision | Cohort PnL |
|---|---:|---:|---:|---:|---:|
| Research Discovery | 48 | 71.64% | 20 | 70.59% | **-$116.61** |
| Research Validation | 16 | 80.00% | 14 | 53.33% | **+$12.82** |
| Research Reserve | 28 | 77.78% | 6 | 82.35% | **-$20.13** |
| Fresh Oct 1 | 78 | 74.29% | 28 | 73.58% | **-$145.04** |
| Fresh Oct 2 | 67 | 67.68% | 34 | 66.34% | **-$68.05** |
| Fresh Oct 3 | 45 | 63.38% | 20 | 69.23% | **-$87.07** |

The failure territory transports strongly by BAD coverage.

However, Research Validation is the critical warning:

> the archetype union there has **+$12.82** realized protected PnL.

If the union were blindly vetoed, that block would get worse.

This directly proves why CT-7B must not be promoted as a hard filter.

---

## Lane transport

Even though lane is not part of the archetype definitions, the union captures BAD trades across all four lanes.

BAD captured by lane:

- T0: **87**
- T1: **69**
- T2: **84**
- T3: **42**

This further supports the architectural hypothesis:

> low-MFE failure is a global opportunity-quality problem, not a T-lane-specific phenomenon.

---

## Main conceptual finding

CT-7A showed that low-MFE trades have a global weak-morphology signature.

CT-7B now shows that the signature decomposes into several broad archetypes and that these archetypes collectively cover most BAD trades.

But strong winners also exist inside the same broad regions.

Therefore the next problem is no longer:

> find low-MFE territory.

That territory has now been found.

The next problem is:

> **inside each failure archetype, what second-order causal features separate the BAD members from the strong/TARGET survivors?**

This is exactly where features that were weak globally may become useful conditionally:

- OI / positioning
- taker flow
- crowding / overheat
- rejection structure
- failure/reversal structure
- context interactions
- score-family conflicts

A feature can be weak globally but highly discriminative inside one morphology archetype.

---

## CT-7B verdict

> **PASS failure-archetype discovery.**

Three broad, transportable low-MFE archetypes are frozen:

1. **A1 LOW DISPLACEMENT**
2. **A2 WEAK RELATIVE EXPANSION**
3. **A3 LOW ENERGY RESIDUAL**

Their union identifies:

> **282 / 398 = 70.85% of BAD trades**

with moderate pairwise BAD overlap.

But direct veto is rejected because the same union also captures:

> **122 TARGET-MFE and 109 strong selected trades**.

## Frozen CT-7C objective

CT-7C should operate **inside A1/A2/A3**, not globally.

For each archetype:

1. compare BAD members vs TARGET/strong members;
2. search conditional second-order separators;
3. build high-precision kill branches inside the archetype;
4. require Research/Fresh and chronological transport;
5. measure marginal BAD coverage after accounting for overlap;
6. do not use T lane as the primary basis;
7. do not use future MFE, realized PnL, close reason, or protector outcome as detector inputs.

Target for CT-7C:

> convert the **70.9% broad BAD territory** into a materially smaller but much safer executable kill set.

No runtime promotion is authorized by CT-7B.