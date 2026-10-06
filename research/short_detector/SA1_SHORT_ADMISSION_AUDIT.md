# SHORT-SA1 — Admission Audit

Status: **PASS audit / primary noise source is upstream opportunity-quality admission**

## Scope

SA-1 audits the frozen SHORT admission path before temporal confirmation:

1. Stage 2 movement detection
2. Stage 3 IGNITION / EXPANSION classification
3. Stage 4 direction scoring
4. Stage 5 market context
5. Stage 6 LONG / SHORT / NO TRADE decision

T confirmation, CT7 kill/rescue logic, and Profit Protector are out of scope.

No runtime or paper-entry rule is changed.

## Population

Frozen CT universe:

- BAD-A MFE <0.30%: **243**
- BAD-B 0.30-0.50%: **155**
- GRAY 0.50-1.00%: 363
- TARGET >=1.00%: **326**

Primary contrast:

> **398 BAD <0.50% vs 326 TARGET >=1.00%**

---

# Finding 1 — Stage 2 relative-baseline expansion is the main structural loophole

Stage 2 defines abnormal movement primarily as:

- absolute 5m return floor;
- return expansion relative to own baseline;
- at least one activity expansion ratio.

For STRONG_CONTINUATION it additionally requires stronger relative return/volume/range ratios and directional persistence.

The problem is that BAD trades do not look weak on those ratios.

Median anatomy:

| Metric | BAD-A | BAD-B | TARGET |
|---|---:|---:|---:|
| 5m selected return | 0.808% | 0.772% | 0.860% |
| 15m selected return | 0.992% | 1.003% | **1.230%** |
| 1h selected return | 1.149% | 1.376% | **1.822%** |
| prior median abs 5m return | 0.162% | 0.163% | **0.208%** |
| return expansion ratio | **4.836x** | **4.845x** | 4.370x |
| volume ratio | 3.813x | 3.712x | 3.657x |
| range ratio | **2.614x** | **2.527x** | 2.471x |
| trades ratio | 2.456x | 2.473x | 2.498x |

This is the key inversion:

> **BAD has weaker absolute displacement, but often stronger relative expansion ratios.**

Why:

> its recent baseline is quieter.

So a coin can look like a 4.8x abnormal move relative to its own quiet history while still being an underpowered absolute opportunity.

This is exactly the type of trade that later produces MFE <0.50%.

### Fixed sensitivity probes

Not optimized; used only to identify which dimensions contain signal.

| Probe | BAD keep | TARGET keep | TARGET minus BAD |
|---|---:|---:|---:|
| 5m return >=0.70% | 61.1% | 71.2% | +10.1pp |
| 5m return >=0.90% | 36.7% | 46.9% | +10.2pp |
| 15m return >=1.20% | 34.2% | **51.2%** | **+17.1pp** |
| 1h return >=1.50% | 36.4% | **60.1%** | **+23.7pp** |
| 1h return >=2.00% | 19.1% | **42.9%** | **+23.8pp** |
| prior median abs 5m >=0.18% | 41.2% | **57.7%** | **+16.5pp** |
| prior median abs 5m >=0.20% | 31.9% | **51.8%** | **+19.9pp** |
| return expansion ratio >=5x | **47.7%** | 37.1% | **-10.6pp** |
| range ratio >=2.5x | **56.0%** | 48.8% | **-7.3pp** |

Raising the relative-expansion requirement can therefore make selection worse.

The opportunity-quality signal is much stronger in **absolute displacement and baseline quality**.

---

# Finding 2 — Stage 3 EXPANSION is not equivalent to high future excursion

Stage 3 is only a mapping:

- EARLY_MOVEMENT -> IGNITION
- STRONG_CONTINUATION -> EXPANSION
- LATE_MOVEMENT -> EXHAUSTION

STRONG_CONTINUATION itself comes from the Stage 2 relative-ratio rules.

Observed outcome:

| Stage | BAD | TARGET | BAD share among BAD+TARGET |
|---|---:|---:|---:|
| IGNITION | 95 | 92 | 50.8% |
| **EXPANSION** | **303** | 234 | **56.4%** |

Rates:

- **76.1% of BAD** is classified EXPANSION
- 71.8% of TARGET is classified EXPANSION

For BAD-A specifically:

> **192 / 243 = 79.0% are EXPANSION**

Therefore current Stage 3 naming overstates opportunity quality.

It correctly identifies strong movement relative to the coin's recent baseline, but that does not mean the move has enough absolute excursion potential to become a profitable SHORT opportunity.

---

# Finding 3 — Stage 4 amplifies the same relative-activity evidence

Stage 4 gives:

- 50 points momentum/acceleration
- 25 points activity expansion
- 10 persistence
- 15 timeframe consistency

Median score components:

| Component | BAD | TARGET |
|---|---:|---:|
| Momentum | 34.32 | **38.10** |
| Activity | **22.77** | 22.16 |
| Persistence | 10.00 | 10.00 |
| Consistency | 15.00 | 15.00 |
| Sum of median components | 82.09 | 85.26 |

This means an aligned candidate often receives approximately:

> **47 points from activity + persistence + consistency before momentum quality is considered.**

With Stage 6 min score only 68:

> only about 21 additional momentum points are needed.

BAD therefore receives nearly the same Stage 4 score as TARGET.

Median selected score:

- BAD-A: **79.54**
- BAD-B: **79.02**
- TARGET: **82.27**

The score difference is too small for the current score gate to be a strong quality discriminator.

### Raising score alone is a poor repair

Fixed probe:

- score >=80 keeps **47.5% BAD**
- score >=80 keeps **57.4% TARGET**

Only +9.9pp separation while discarding 42.6% of TARGET.

Momentum itself is more informative:

- momentum >=35 keeps 45.7% BAD
- momentum >=35 keeps **63.8% TARGET**
- separation **+18.1pp**

So the issue is not simply that min_score=68 is numerically too low.

The score composition mixes opportunity quality with activity evidence that is already inflated by relative-baseline normalization.

---

# Finding 4 — Stage 4 edge gate is effectively non-binding in this SHORT universe

Stage 6 requires:

- winning score >=68
- score edge >=10

But opposite score is almost always zero in this selected SHORT population.

Median opposite score:

> **0.0** in BAD-A, BAD-B, and TARGET

Even the 90th percentile opposite score is approximately zero for most buckets.

As a result:

> if selected SHORT score already passes 68, edge >=10 almost automatically passes.

Fixed probe:

> **100% of BAD and TARGET in the frozen selected universe already have edge >=15.**

So the edge gate is currently adding essentially no excursion-quality protection.

---

# Finding 5 — Stage 5/6 context confirms direction, not opportunity magnitude

SHORT core confirmations are:

- BREAKDOWN / FAILED_BREAKOUT structure
- SELL taker flow
- FRESH_SHORT_PARTICIPATION OI

Market regime is additional directional context.

This is useful for side correctness, but it does not separate BAD from TARGET strongly.

Core patterns:

| Core pattern | BAD | TARGET |
|---|---:|---:|
| structure+taker | 145 | 149 |
| structure+taker+OI | **133** | 97 |
| taker+OI | **63** | 36 |
| taker only | **32** | 17 |

More directional confirmations do not imply more future excursion.

A stricter core-confirmation probe is nearly neutral:

- core >=2 keeps about **88% of BAD**
- core >=2 keeps about **90% of TARGET**

A stricter context balance is worse:

- balance >=2 keeps about **81% BAD**
- only **77% TARGET**

Therefore Stage 5/6 context should not be repurposed as the main low-MFE quality filter.

It is doing a different job:

> **is SHORT direction supported?**

not:

> **is there enough opportunity magnitude to trade?**

---

# Finding 6 — Expansion's looser Stage 6 confirmation requirement is not the main cause

Stage 6 currently requires:

- IGNITION: 2 directional confirmations
- EXPANSION: 1 directional confirmation

This looked suspicious because BAD is overrepresented in EXPANSION.

But actual selected EXPANSION decisions mostly have >=2 confirmations anyway.

EXPANSION confirmation counts:

- BAD: 14 with only 1 confirmation out of 303
- TARGET: 12 with only 1 confirmation out of 234

So increasing EXPANSION required confirmations from 1 to 2 would only affect a small minority and would not solve the 398-BAD problem.

---

# Finding 7 — Absolute liquidity and market-relative movement are missing from the admission quality concept

Median causal context:

| Metric | BAD | TARGET |
|---|---:|---:|
| absolute quote volume 5m | **56,703** | **109,666** |
| quote volume 24h | 5.56m | **8.30m** |
| breakdown depth | 0.297% | **0.404%** |
| coin minus market 30m | 0.882 | **1.288** |
| coin residual vs BTC 5m | 0.612 | **0.731** |

These are consistent with CT-7A:

> TARGET opportunities are not merely abnormal relative to themselves; they also have more absolute movement, liquidity, structural depth, and market-relative displacement.

The current Stage 2-4 admission path does not explicitly encode that distinction strongly enough.

---

# SA-1 root-cause ranking

## Root cause #1 — Stage 2 normalization loophole

**High confidence.**

Relative-to-own-baseline expansion can rate a quiet/illiquid coin as extremely strong even when its absolute opportunity is weak.

BAD's return/range expansion ratios are equal to or stronger than TARGET despite substantially weaker 15m/1h excursion.

## Root cause #2 — Stage 4 double-rewards relative activity

**High confidence.**

The Stage 4 activity component reuses the same expansion ratios, while persistence and consistency add another 25 points.

This lets underpowered movement clear the 68 score threshold.

## Root cause #3 — Stage 3 EXPANSION semantic mismatch

**Medium-high confidence.**

EXPANSION currently means strong continuation relative to baseline, not high expected excursion quality.

76.1% of BAD is labeled EXPANSION.

## Root cause #4 — Edge gate redundancy

**High confidence.**

The opposite score is usually near zero, so min_edge=10 contributes almost no filtering after min_score=68.

## Not root cause — Stage 5 directional context

**High confidence.**

Context confirmation is useful for side direction but has weak/no discrimination for BAD vs TARGET opportunity magnitude.

## Not root cause — Profit Protector / T confirmation

Already established downstream by CT-7 series and outside SA-1 scope.

---

# Architectural implication

Do **not** reset the entire SHORT detector.

Keep:

- Stage 5 directional context semantics
- T confirmation as positive strong-selection / timing
- CT-7D rescue concept
- Profit Protector

Rework the admission concept around Stage 2-4.

The missing layer is:

> **Opportunity Quality**

between movement detection and temporal confirmation.

A candidate can be correctly identified as moving SHORT but still fail quality:

> SHORT direction = valid  
> movement = abnormal  
> opportunity magnitude = insufficient  
> => NO ENTRY

---

# Recommended SA-2 objective

SA-2 should design an **Opportunity Quality Gate**, not merely raise Stage 4 min_score.

Candidate dimensions should prioritize:

1. absolute 15m / 1h selected-side displacement;
2. baseline movement amplitude / tradability floor;
3. absolute liquidity;
4. market-relative displacement;
5. structural breakdown depth;
6. momentum-quality component.

Relative expansion ratios should remain useful for movement discovery, but should **not be treated as proof of trade-quality excursion**.

SA-2 target should explicitly map the frontier:

- BAD rejection 20 / 30 / 40 / 50 / 60%
- TARGET retention
- strong retention
- Research/Fresh transport
- six chronological blocks

No runtime promotion is authorized by SA-1.
