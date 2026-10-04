# Market Detector — Profit Discovery Methodology
## Standalone Development Playbook for Replicating LONG Discovery into SHORT

**Document status:** Standalone methodology reference  
**Scope:** Track A — Profit / Opportunity Discovery  
**Current completed LONG reference:** through Stage 3C.7A  
**Primary purpose:** preserve the full research logic, sequence, evaluation discipline, metrics, and failure modes so the same development method can later be applied to SHORT without reconstructing the reasoning from scratch.

---

# 1. Why this document exists

This document is **not** a summary of the LONG detector result.

It is a reusable development playbook describing **how the profit detector was discovered, tested, rejected, refined, and expanded**.

The goal is to make the methodology reproducible.

When development moves to SHORT, the correct approach is **not**:

1. copy LONG thresholds into SHORT;
2. copy LONG feature directions into SHORT;
3. assume the same archetype proportions;
4. assume the same temporal horizon;
5. assume the same Profit Protector behavior.

The correct approach is:

1. freeze the SHORT universe;
2. define SHORT strong winners independently;
3. run the same diagnostic structure used for LONG;
4. identify SHORT-specific winner and loss anatomy;
5. test whether aggregate predictors cancel because multiple archetypes exist;
6. test archetype-specific separation;
7. test temporal confirmation;
8. identify why winners are missed;
9. add recovery layers one at a time;
10. replay the entire SHORT universe after every experiment;
11. measure marginal winner capture, marginal noise, and marginal MFE opportunity;
12. freeze only the layers that survive out-of-sample checks.

This document records that process in detail.

---

# 2. Separation of responsibilities: Track A vs Track B

The Market Detector research is divided into two different engineering problems.

## Track A — Profit / Opportunity Discovery

Track A answers:

> Which trades should the detector open so that it captures as much useful positive price excursion as possible?

Track A is evaluated using:

- number of candidates;
- number of OPEN trades;
- number of strong winners captured;
- strong winners still missed;
- non-target trades opened;
- profitable non-target trades;
- historical realized-positive trades;
- peak MFE opportunity;
- additional MFE created by each recovery layer;
- marginal entries required per additional strong winner;
- split stability across Discovery / Validation / Reserve.

Track A does **not** optimize exits.

A trade can therefore be useful to Track A even if historical realized PnL was poor, provided it generated meaningful positive excursion after entry.

---

## Track B — Profit Protection / Peak Capture

Track B answers:

> Once Track A has opened a position, how much of the available positive excursion can be preserved and converted into realized PnL?

Track B is evaluated using:

- causal peak-capture percentage;
- MFE-to-close giveback;
- exit latency;
- realized PnL;
- final WR;
- runner preservation;
- fees and slippage;
- next-bar execution realism.

Track B is intentionally separate.

This separation is critical because otherwise an entry detector may look bad only because the old historical exit gave back profit, or an exit protector may look good only because it is evaluated on an unrealistically prefiltered winner set.

---

# 3. Frozen LONG research universe

The current LONG research universe contains:

- **1,236 resolved LONG trades**
- **401 META_WIN**
- **835 META_LOSS**

Strong winner definition:

> `Strong WIN = META_WIN AND historical max MFE >= 1.00%`

This produces:

- **245 strong LONG winners**
- **991 non-targets**

The 991 non-targets consist of:

- **156 weak META_WIN** with MFE < 1%
- **835 META_LOSS**

This target definition must remain frozen while comparing recovery experiments.

Changing the target definition midstream would invalidate comparisons between stages.

---

# 4. Core terminology

## 4.1 Candidate

A resolved trade present in the frozen research universe.

For LONG:

> Candidates = **1,236**

---

## 4.2 OPEN / selected

A trade accepted by the current detector policy.

This is the actual population that would be sent to execution / Profit Protector.

---

## 4.3 Strong winner

A trade satisfying:

> `META_WIN AND historical MFE >= 1%`

This is the primary Track A target.

---

## 4.4 Non-target

Any selected trade that is not a strong winner.

A non-target is **not automatically a useless trade**.

A non-target can:

- briefly move positive;
- reach +0.3%;
- reach +0.5%;
- even exceed +1%;
- later reverse;
- finally close negative;
- be labelled META_LOSS.

Therefore:

> `non-target != zero opportunity`

This became one of the most important findings of the LONG research.

---

## 4.5 Profitable non-target

A selected non-target whose **historical realized PnL > 0**.

This is different from MFE-positive.

---

## 4.6 MFE-positive trade

A trade whose historical Maximum Favorable Excursion was greater than zero.

This means the trade was at least temporarily profitable after entry.

It does **not** mean the trade ultimately closed profitably.

---

## 4.7 Peak-MFE dollar equivalent

For the current frozen research normalization:

> `Peak MFE $ equivalent = historical MFE % × $5`

This is used only as a common opportunity measure consistent with the historical position sizing embedded in the dataset.

It is **not** a guaranteed realizable profit.

It is an oracle-style upper-bound opportunity measure.

---

# 5. Mandatory research integrity rules

These rules must also be applied when SHORT development begins.

## Rule 1 — Never judge a detector only by AUC

AUC, correlation, enrichment, and classifier statistics are diagnostic tools.

The final Track A decision must always return to:

> candidates → OPEN → captured strong WIN → non-target → profitable spillover → MFE opportunity

---

## Rule 2 — Every accepted experiment must be replayed against the full universe

For LONG:

> all **1,236** rows

No stage is accepted merely because it improves a subset.

Every recovery layer must report the full-universe effect.

---

## Rule 3 — Always maintain a locked comparison baseline

A new stage is compared to the **current best accepted policy**, not to whichever earlier stage makes it look best.

Example:

Before Stage 3C.7A, baseline was:

> 1,236 → 345 OPEN → 114 strong WIN → 231 non-target → 29 profitable non-target

After Stage 3C.7A passed, the new baseline became:

> 1,236 → 454 OPEN → 150 strong WIN → 304 non-target → 39 profitable non-target

Every later experiment must compare against **454 / 150 / 304 / 39** until a better layer is accepted.

---

## Rule 4 — Separate recall improvement from precision improvement

A detector can improve because:

- it captures more winners while preserving precision;
- it captures the same winners with fewer entries;
- or both.

These are different achievements.

Stage 3C.7A was a **recall expansion**, not a precision improvement.

---

## Rule 5 — Temporal features must be causal

If a trade has already resolved before T+3, then a T+3 snapshot cannot be treated as a valid live decision point.

This is why temporal rows were censored when the outcome had already resolved.

---

## Rule 6 — Never treat historical MFE peak as known in real time

The detector can observe trajectory only as time unfolds.

Historical peak MFE is used to measure opportunity, not as an input available at decision time.

---

## Rule 7 — Separate original-entry historical economics from delayed-entry economics

A temporal confirmation rule may wait until T+1, T+2, or T+3.

Historical PnL generated from the original T0 entry cannot automatically be claimed as the PnL of the delayed-entry strategy.

Execution-realistic replay is required for that.

---

# 6. Stage history — how the LONG discovery method was built

# 6.1 Stage 3C.1 — Exhaustive single-parameter T0 tuning

Purpose:

> Determine whether a single T0 feature can separate strong winners from losses strongly enough to build a clean detector.

Research scale:

- **224 T0 predictors**
- approximately **32.275 million candidate rules**

Result:

- **0 strong single-feature rules**
- discovery-only patterns overfit;
- no stable |r| around 0.5 predictor;
- reserve behavior did not support a simple one-dimensional rule.

Conclusion:

> The poor T0 separation was not simply caused by insufficient threshold tuning.

This stage prevented wasting time endlessly adjusting one threshold.

---

# 6.2 Stage 3C.1B — Winner anatomy and clustering

The **245 strong LONG winners** were examined separately.

Two winner archetypes emerged.

## Archetype A — Counterflow / Reversal

- **65 / 245**
- **26.5%**
- historical PnL approximately **+$195.27**
- average historical return approximately **+0.601%**
- realized-positive rate approximately **87.7%**

## Archetype B — Flow-Aligned / Continuation

- **180 / 245**
- **73.5%**
- historical PnL approximately **+$633.68**
- average historical return approximately **+0.704%**
- realized-positive rate approximately **92.8%**

Important discovery:

Several features changed direction between archetypes.

Example:

Aggregate strong-WIN vs loss taker-share AUC looked useless around:

> **0.490**

But inside archetypes:

- Counterflow preferred the LOW direction;
- Continuation preferred the HIGH direction.

Therefore the aggregate statistic cancelled itself.

This established a key methodology principle:

> A weak aggregate predictor may hide strong but opposite conditional relationships.

---

# 6.3 Stage 3C.1C — Loss anatomy

The **835 LONG META_LOSS** trades were also clustered.

Two dominant loss archetypes appeared:

## Flow-Aligned Failure

- **602 / 835**
- **72.1%**

## Counterflow Failure

- **233 / 835**
- **27.9%**

These proportions almost mirrored the winner archetypes.

Therefore:

> Archetype identity itself is not an edge.

The detector must separate:

- Flow-Aligned winner vs Flow-Aligned failure;
- Counterflow winner vs Counterflow failure.

Within-archetype analysis showed:

### Flow-Aligned

Very difficult at T0.

Best stable single-feature AUC floor approximately:

> **0.551**

### Counterflow

More separable.

Best stable single-feature AUC floor around:

> **0.648**

Examples included:

- acceleration 5m vs 15m;
- coin residual vs BTC;
- slope5.

This led to separate treatment by lane.

---

# 6.4 Stage 3C.2 — Archetype-specific feature combinations

## Flow-Aligned lane

Multiple 2-, 3-, and 4-feature combinations were tested.

Best 2-feature examples only reached roughly:

- Discovery ~0.582
- Validation ~0.592
- Reserve ~0.611

Adding more features did not improve Reserve enough.

Conclusion:

> Flow-Aligned continuation could not be solved reliably from T0 alone.

---

## Counterflow lane

Counterflow separation improved with combinations.

A useful 3-feature logistic combination used:

- coin residual 5m vs BTC;
- momentum curvature;
- entry price drift.

AUC:

- Discovery ~0.676
- Validation ~0.688
- Reserve ~0.718

A four-rule LOSS veto was frozen as a research candidate:

- `f_new_accel_5_vs_15 <= 0.6214308333`
- `f_f_selected_slope5_norm <= 0.2612069909`
- `f_f_coin_minus_market_30m >= -0.1486000362`
- `f_f_coin_minus_market_15m <= 2.5904018610`

All four had to fire to veto.

The veto improved Counterflow classification but was not independently profitable.

This was still useful because Track A needed a structured lane, not necessarily standalone PnL.

---

# 6.5 Stage 3C.3 — Flow-Aligned temporal confirmation

Since T0 could not solve Flow-Aligned continuation, the research moved into time.

Snapshots:

- T+1
- T+2
- T+3

Strict causal censoring was enforced.

Eligible rows:

- T+1: **717**
- T+2: **632**
- T+3: **545**

Best model AUC D/V/R:

### T+1
- 0.637
- 0.647
- 0.682

### T+2
- 0.725
- 0.725
- 0.714

### T+3
- 0.754
- 0.831
- 0.722

T+3 was clearly more informative.

A very simple feature was particularly useful:

> `confirm_side_return_pct`

At T+3, simple AUC was roughly:

- Discovery 0.720
- Validation 0.794
- Reserve 0.756

Frozen threshold selected from Validation:

> **T+3 side return >= +0.158514%**

This threshold became the base temporal confirmation rule.

---

# 6.6 Stage 3C.4 — Execution-realistic temporal replay

The question changed from:

> “Can T+3 classify winners?”

to:

> “After waiting until T+3, is there still enough movement left to trade?”

Execution approximation:

- decision at T+3 timestamp;
- entry at the open of the first full Binance USD-M 1m bar strictly after T+3;
- if the old trade closed before that executable bar, no entry;
- MFE / MAE recomputed from delayed entry.

Reserve findings:

- selected: 26
- executable: 24
- strong targets: 11
- delayed MFE >=1% among targets: **7/11 = 63.6%**
- delayed MFE >=1% among losses: **0/13**

This confirmed that temporal confirmation still left meaningful opportunity.

However exact realized PnL was inconclusive because historical exit fills were intraminute and not retained precisely.

Therefore:

> temporal confirmation was accepted as discovery evidence, not as proven execution PnL.

---

# 6.7 Stage 3C.5 — Unified LONG full 1,236 replay

A major integrity problem had to be fixed before full replay.

The earlier winner archetype clusters were built using outcome-group anatomy.

Those outcome-derived labels cannot be used directly as a live router.

Therefore an **outcome-blind T0 archetype router** was built from Discovery features.

Router performance:

### Validation
- AUC approximately **0.985**
- accuracy approximately **95.4%**

### Reserve
- AUC approximately **0.990**
- accuracy approximately **94.5%**

Unified policy:

### Counterflow
> Select unless the frozen four-rule veto fires.

### Flow-Aligned
> Select only if causal T+3 side return >= +0.158514%.

Full replay result:

> **1,236 candidates**
> → **345 OPEN**
> → **114 strong winners**
> → **231 non-targets**

Strong-target metrics:

- precision = **114 / 345 = 33.0%**
- recall = **114 / 245 = 46.5%**

Historical realized-positive metrics:

- realized-positive trades = **134**
- historical WR = **134 / 345 = 38.8%**

Historical realized PnL:

> approximately **+$61.91**

This became the first usable full-universe Track A baseline.

---

# 7. Critical discovery: non-target does not mean no profit opportunity

Within the 345 OPEN baseline:

### Strong targets
- **114**
- peak MFE equivalent ≈ **$1,295.84**
- historical realized PnL ≈ **+$430.24**

### Non-targets
- **231**
- peak MFE equivalent ≈ **$811.49**
- historical realized PnL ≈ **-$368.33**

This established a critical distinction.

A non-target trade can still generate meaningful positive excursion before later failing.

This observation changed the Track A reporting framework.

The system should no longer report only:

> strong winner vs loss

It must also report:

> positive excursion available inside non-targets.

---

# 8. Stage 3C.6 — Missed winner anatomy

At Stage 3C.5:

- strong winners total = **245**
- captured = **114**
- missed = **131**

Instead of blindly lowering thresholds, the 131 missed winners were classified by reason.

Mutually exclusive primary causes:

## T3 threshold fail
- **66**
- **50.4%**
- peak-MFE opportunity ≈ **$645.22**

## T3 no longer causal / resolved too quickly
- **37**
- **28.2%**
- peak-MFE opportunity ≈ **$394.46**

## Counterflow veto
- **18**
- **13.7%**
- peak-MFE opportunity ≈ **$162.64**

## Router error
- **10**
- **7.6%**
- peak-MFE opportunity ≈ **$100.27**

The most important finding:

> **103 / 131 misses were Flow-Aligned temporal misses.**

Only:

> **10 / 131**

were primarily router errors.

Therefore rebuilding the router was not the highest-value next step.

---

# 9. Early-recovery insight from Stage 3C.6

Among the 131 missed strong winners:

> **35 had already crossed the SAME +0.158514% threshold at T+1 or T+2 while the snapshot was still causal.**

Breakdown:

- **20** at T+1
- **15** at T+2

This suggested an unusually clean recovery experiment:

> Do not lower the threshold.  
> Do not add a new feature.  
> Simply allow earlier confirmation when the same condition is already satisfied.

This became Stage 3C.7A.

---

# 10. Stage 3C.7A — Early T+1 / T+2 same-threshold recovery

Rule:

For the Flow-Aligned lane:

> enter at the earliest causal T+1 / T+2 / T+3 snapshot where  
> `confirm_side_return_pct >= +0.158514%`

Counterflow logic remained unchanged.

The threshold was **not lowered**.

---

## 10.1 Full 1,236 replay result

Previous baseline:

> **1,236 → 345 OPEN → 114 strong WIN → 231 non-target → 29 profitable non-target**

Stage 3C.7A:

> **1,236 → 454 OPEN → 150 strong WIN → 304 non-target → 39 profitable non-target**

Changes:

- OPEN: **345 → 454 = +109**
- strong WIN: **114 → 150 = +36**
- missed strong WIN: **131 → 95**
- capture rate: **46.5% → 61.2%**
- non-target: **231 → 304 = +73**
- profitable non-target: **29 → 39 = +10**

Marginal winner cost:

> **109 / 36 = 3.03 additional entries per additional strong winner**

Strong-winner precision stayed effectively unchanged:

> ~33.0% → ~33.0%

Therefore:

> Stage 3C.7A is a recall improvement, not a precision improvement.

---

## 10.2 Reserve confirmation

Reserve changed from:

> **61 OPEN → 16 strong WIN**

to:

> **87 OPEN → 23 strong WIN**

Reserve strong-winner capture:

> **42.1% → 60.5%**

Reserve precision:

> **26.2% → 26.4%**

This is important because the improvement was not limited to Discovery.

---

# 11. Full economic anatomy of the 454 OPEN after Stage 3C.7A

## Strong targets

- trades: **150**
- peak MFE opportunity ≈ **$1,684.99**
- historical realized PnL ≈ **+$560.28**

Historical realized peak retention:

> approximately **33.3%**

---

## Non-targets

- trades: **304**
- peak MFE opportunity ≈ **$1,028.61**
- historical realized PnL ≈ **-$497.75**

This population is especially important.

Of the 304 non-targets:

- **301 / 304** had MFE > 0
- **232 / 304** reached MFE >= 0.3%
- **183 / 304** reached MFE >= 0.5%
- **37 / 304** reached MFE >= 1.0%

Therefore:

> almost all selected non-targets were temporarily profitable.

---

# 12. Non-target realized outcome breakdown

Within the 304 non-targets:

## Historical realized profit
- **39 trades**
- peak MFE ≈ **$232.83**
- realized PnL ≈ **+$32.33**

## Historical realized <= 0
- **265 trades**
- peak MFE ≈ **$795.79**
- realized PnL ≈ **-$530.07**

Of those 265 historical non-profitable non-targets:

- **262** had MFE > 0
- **193** reached >=0.3%
- **145** reached >=0.5%
- **27** reached >=1.0%

This is a major research insight:

> a large portion of historical losses were not necessarily immediate directional failures; many were positive-excursion trades that later gave back the move.

Track A records this opportunity.

Track B determines whether it can actually be harvested causally.

---

# 13. MFE-bucket breakdown of the 304 non-targets

| Peak MFE bucket | Trades | Peak MFE $ | Historical realized $ |
|---|---:|---:|---:|
| MFE <= 0 | 3 | ~$0 | ~-$9.95 |
| 0 to 0.3% | 69 | ~$71.06 | ~-$165.88 |
| 0.3 to 0.5% | 49 | ~$91.18 | ~-$185.47 |
| 0.5 to 1.0% | 146 | ~$505.72 | ~-$116.18 |
| >=1.0% | 37 | ~$360.66 | ~-$20.26 |
| **Total** | **304** | **~$1,028.61** | **~-$497.75** |

This table must be replicated for SHORT.

It prevents the research from incorrectly treating all non-targets as equally bad.

---

# 14. Incremental anatomy of Stage 3C.7A itself

The additional **109 entries** created by 3C.7A consisted of:

- **36 additional strong winners**
- **73 additional non-targets**

Historical outcome of the additional non-targets:

- **10** realized positive
- **63** realized non-positive

But:

> all **73 / 73** additional non-targets had positive MFE.

Additional opportunity:

### Strong winners added
- peak MFE ≈ **$389.15**
- historical realized ≈ **+$130.04**

### Non-targets added
- peak MFE ≈ **$217.13**
- historical realized ≈ **-$129.41**

Combined:

- additional peak MFE ≈ **+$606.28**
- historical PnL delta ≈ **+$0.62**

This is a perfect illustration of why Track A and Track B must remain separate.

Track A successfully discovered more movement.

Historical exit behavior failed to monetize most of it.

---

# 15. The required Track A ledger after every future experiment

Every Track A experiment must produce this exact reporting structure.

## Full universe ledger

| Metric | Current baseline | New experiment | Delta |
|---|---:|---:|---:|
| Candidates | N | N | 0 |
| OPEN | A | B | B-A |
| Strong WIN captured | C | D | D-C |
| Strong WIN missed | E | F | F-E |
| Capture rate | C/Target | D/Target | delta pp |
| Non-target OPEN | G | H | H-G |
| Profitable non-target | I | J | J-I |
| Historical realized-positive trades | K | L | L-K |
| Historical WR | K/A | L/B | delta pp |
| Historical realized PnL | $X | $Y | $Y-$X |
| Peak MFE opportunity | $P | $Q | $Q-$P |

---

## Incremental efficiency ledger

For only the newly added entries:

- additional OPEN;
- additional strong winners;
- additional non-targets;
- additional profitable non-targets;
- additional MFE-positive non-targets;
- additional MFE >=0.3%;
- additional MFE >=0.5%;
- additional MFE >=1%;
- additional peak-MFE opportunity;
- additional historical realized PnL;
- entries per additional strong winner;
- incremental strong-winner rate.

The most important efficiency metric is:

> `marginal entries per additional strong winner`

Example from 3C.7A:

> `109 / 36 = 3.03`

---

# 16. Efficient-frontier methodology

The objective is **not automatically 245 / 245 strong winners**.

A detector can theoretically capture more winners by opening almost everything.

That is not useful.

Instead, Track A should construct an efficient frontier.

Example structure:

| OPEN | Strong WIN captured | Capture rate | Non-target | Profitable spillover | Peak MFE |
|---:|---:|---:|---:|---:|---:|
| 345 | 114 | 46.5% | 231 | 29 | $2,107.33 |
| 454 | 150 | 61.2% | 304 | 39 | $2,713.60 |
| next stage | ? | ? | ? | ? | ? |

Each recovery layer is judged on:

1. winner capture gained;
2. additional entries required;
3. non-target burden;
4. out-of-sample stability;
5. additional peak-MFE opportunity.

The optimum may be below 100% winner recall.

---

# 17. Profit Protector scenario analysis — how to use it correctly

A hypothetical 80% peak-capture scenario was calculated to understand the economic ceiling.

For Stage 3C.7A:

- total peak-MFE opportunity ≈ **$2,713.60**
- 80% of peak ≈ **$2,170.88 gross**

Only approximately **3 / 454** trades never had positive MFE.

If those three historical losses are left unchanged at approximately **-$9.95**, the simple hypothetical net becomes:

> approximately **+$2,160.93**
The corresponding hypothetical profitable-trade count would be:

> **451 / 454 ≈ 99.34%**

However, this must be labelled correctly.

This is:

> **an 80%-of-historical-peak scenario**

It is **not** a causal Profit Protector backtest.

Historical peak is known only after the fact.

Therefore these figures are useful as:

- economic ceiling;
- opportunity sizing;
- Track B target comparison;

but not as proof of achievable trading performance.

---

# 18. What must NOT be copied mechanically into SHORT

When SHORT work begins, do **not** reuse the following as assumptions:

- LONG strong-winner prevalence;
- LONG archetype count;
- LONG archetype proportions;
- LONG threshold +0.158514%;
- LONG T+1/T+2/T+3 hierarchy;
- LONG Counterflow veto thresholds;
- LONG router weights;
- LONG feature directions;
- LONG MFE distribution;
- LONG entries-per-winner efficiency;
- LONG 80% capture implication.

SHORT must independently earn every rule.

---

# 19. SHORT replication protocol

The development sequence for SHORT should follow this order.

# SHORT-S1 — Freeze SHORT universe

Current known universe reference:

- **655 resolved SHORT**
- **163 META_WIN**
- **492 META_LOSS**
- **99 strong WIN** using the same conceptual target:
  `META_WIN AND MFE >=1%`

Before any modeling, verify and freeze:

- exact row count;
- target definition;
- historical realized PnL;
- MFE availability;
- temporal coverage;
- split assignment.

---

# SHORT-S2 — Single-feature T0 scan

Repeat the exhaustive T0 scan.

Questions:

1. Is SHORT easier than LONG at T0?
2. Are there any stable single-feature rules?
3. Do signs reverse relative to LONG?
4. Does Reserve support the Discovery pattern?

Do not proceed from a strong Discovery-only rule.

---

# SHORT-S3 — Winner anatomy

Analyze only the strong SHORT winners.

Goals:

- determine whether there are multiple winner archetypes;
- identify opposite feature directions;
- test clustering stability;
- measure archetype composition;
- identify cancellation effects.

Do not assume “Counterflow” and “Flow-Aligned” are the correct SHORT labels until the data supports them.

---

# SHORT-S4 — Loss anatomy

Cluster / characterize SHORT losses independently.

Compare:

- winner archetype vs matching failure archetype.

The purpose is to answer:

> what separates successful SHORT continuation from failed SHORT continuation?

and:

> what separates successful SHORT reversal from failed SHORT reversal?

---

# SHORT-S5 — Archetype-specific T0 combinations

For each SHORT archetype:

- 2-feature combinations;
- 3-feature combinations;
- 4-feature combinations;
- simple vetoes if supported;
- logistic / linear scoring if appropriate.

Evaluate D/V/R separately.

---

# SHORT-S6 — Temporal confirmation

If any lane remains weak at T0:

- T+1
- T+2
- T+3
- later horizons if justified

Use strict causal censoring.

Determine:

- earliest useful temporal horizon;
- best simple observable;
- whether a fixed threshold exists;
- whether delayed entry still leaves meaningful MFE.

---

# SHORT-S7 — Execution-realistic delayed replay

For temporal rules:

- decision timestamp;
- next executable 1m bar;
- recompute delayed-entry MFE / MAE;
- eliminate trades no longer executable;
- distinguish classification success from executable opportunity.

---

# SHORT-S8 — Unified full-universe replay

Build an outcome-blind runtime router if archetypes are used.

Then replay all frozen SHORT candidates.

Required output:

> candidates → OPEN → strong WIN → non-target → profitable non-target → realized-positive trades → historical WR → peak MFE opportunity.

This becomes the first SHORT baseline.

---

# SHORT-S9 — Missed winner anatomy

Take all strong SHORT winners still missed.

Classify reasons.

Possible categories:

- router error;
- veto rejection;
- temporal threshold fail;
- resolved before confirmation;
- early signal existed;
- late bloomer;
- no distinguishable signal.

Do not immediately lower thresholds.

First determine **why** the winners were lost.

---

# SHORT-S10 — Recovery layers

Test recovery one layer at a time.

Possible examples:

- early same-threshold confirmation;
- veto relaxation only for a clearly defined subgroup;
- router correction;
- adaptive threshold lane;
- late-bloomer lane;
- second temporal regime.

After every experiment:

> replay the entire SHORT universe.

---

# SHORT-S11 — Build the SHORT efficient frontier

Maintain a table of accepted stages:

| Stage | OPEN | Strong WIN | Recall | Non-target | Profitable spillover | Peak MFE | Entries/+WIN |
|---|---:|---:|---:|---:|---:|---:|---:|

Select the operating point based on marginal economics and stability.

---

# 20. Required result wording for future research

To avoid ambiguous reporting, every future result should begin with the trading funnel.

Example:

> **655 SHORT candidates → 180 OPEN → 55 strong WIN → 125 non-target**

Then immediately report:

- strong-WIN capture = `55 / 99`;
- strong-WIN rate = `55 / 180`;
- profitable non-target count;
- historical realized-positive count;
- historical WR;
- peak-MFE opportunity;
- delta from prior accepted baseline.

Only after that should AUC, correlation, feature importance, or classifier metrics be discussed.

---

# 21. Failure patterns to avoid

## Failure 1 — “AUC improved, therefore detector improved”

False.

The only accepted proof is full-universe replay.

---

## Failure 2 — Lowering thresholds before missed-winner anatomy

This can produce huge entry inflation.

Always diagnose the miss reason first.

---

## Failure 3 — Treating every non-target as garbage

LONG proved this is wrong.

Most selected non-targets had positive MFE.

Always inspect excursion distribution.

---

## Failure 4 — Treating MFE-positive as realized winner

Also wrong.

MFE is opportunity.

Realized outcome depends on exit.

---

## Failure 5 — Mixing Track A and Track B

Entry discovery and peak capture must be independently evaluated.

---

## Failure 6 — Using outcome-informed archetype labels as live routing

Outcome-derived anatomy can be used diagnostically.

Runtime routing must be outcome-blind.

---

## Failure 7 — Claiming delayed-entry PnL using original-entry historical fills

Invalid.

Delayed-entry policies require delayed-entry replay.

---

# 22. Current LONG baseline to preserve before further Track A work

After Stage 3C.7A, the accepted LONG Track A baseline is:

> **1,236 candidates**
> → **454 OPEN**
> → **150 strong winners captured**
> → **95 strong winners missed**
> → **304 non-targets**
> → **39 profitable non-targets**
> → **176 historical realized-positive trades**
> → **historical WR ≈ 38.77%**
> → **historical realized PnL ≈ +$62.53**
> → **total peak-MFE opportunity ≈ $2,713.60**

Strong-winner recall:

> **150 / 245 = 61.2%**

Strong-winner rate among OPEN:

> **150 / 454 ≈ 33.0%**

Non-target MFE-positive rate:

> **301 / 304 ≈ 99.0%**

This is the comparison point for the next LONG recovery stage.

---

# 23. Current unresolved LONG opportunity

Strong winners still missed:

> **95**

The next LONG development must continue from the 454 / 150 baseline.

It must not revert to the earlier 345 / 114 baseline.

Any proposed recovery layer must report:

- how many of the remaining 95 strong winners it recovers;
- how many additional entries it requires;
- how many additional non-targets are introduced;
- how much additional MFE opportunity is created;
- whether Discovery / Validation / Reserve remain directionally consistent.

---

# 24. Final methodology principle

The central lesson from LONG development is:

> **Profit discovery should not be engineered as a binary “winner vs loser” classifier only.**

The detector is better understood as a system for identifying:

1. **strong target opportunities**, and
2. **positive-excursion spillover** that may still be economically useful under a competent Profit Protector.

Therefore the complete Market Detector architecture is:

> **candidate universe**
> → **archetype / regime understanding**
> → **T0 filtering where possible**
> → **temporal confirmation where needed**
> → **recovery layers for missed winners**
> → **full-universe replay**
> → **efficient-frontier selection**
> → **Profit Protector / Track B**
> → **execution-realistic final strategy**

This sequence—not any single threshold—is the reusable intellectual property that should be carried from LONG into SHORT.

---

# 25. Files associated with the current LONG methodology

Key current artifacts include:

- `D4_STAGE3C1_EXHAUSTIVE_SINGLE_PARAMETER_TUNING_2026-10-04.xlsx`
- `D4_STAGE3C1B_WINNER_ANATOMY_2026-10-04.xlsx`
- `D4_STAGE3C1C_LONG_LOSS_ANATOMY_2026-10-04.xlsx`
- `D4_STAGE3C2_ARCHETYPE_COMBINATION_2026-10-04.xlsx`
- `D4_STAGE3C3_FLOW_ALIGNED_TEMPORAL_CONFIRMATION_2026-10-04.xlsx`
- `D4_STAGE3C4_EXECUTION_REALISTIC_TEMPORAL_REPLAY_2026-10-04.xlsx`
- `D4_STAGE3C5_UNIFIED_LONG_1236_TEST_2026-10-04.xlsx`
- `D4_STAGE3C6_MISSED_WINNER_ANATOMY_2026-10-04.xlsx`
- `D4_STAGE3C7A_EARLY_RECOVERY_FULL_1236_2026-10-04.xlsx`
- `D4_STAGE3C7A_FULL_1236_DECISIONS.csv`

This MD file should remain separate from stage-specific research notes.

---

# 26. Use this file when SHORT development starts

The correct instruction for a future development session is:

> Read `MARKET_DETECTOR_PROFIT_DISCOVERY_PLAYBOOK_LONG_TO_SHORT.md` first.  
> Do not copy LONG thresholds mechanically.  
> Reproduce the methodology from the SHORT frozen universe, and report every accepted experiment using the full-universe Track A ledger.
