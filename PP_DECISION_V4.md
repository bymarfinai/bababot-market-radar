# PP-DECISION V4 — High-Frequency Peak Capture

Status: **V4-1 ACTIVE PROSPECTIVE CAPTURE — NO TRADING AUTHORITY**

PP-DECISION V4 is the successor research track to the retired V3 low-tail and Stage 2B.1 shadow paths.

It exists to answer one question:

> Can materially higher causal observation resolution compress the full peak-capture distribution — especially the <80% lower tail — before any new exit/protection logic is engineered?

V4 does **not** assume that the future peak is knowable in real time.

## Authority

At Step 3:

- V4 has **no startup loop**;
- V4 has **no API endpoint**;
- V4 has **no environment flag**;
- V4 has **no paper authority**;
- V4 has **no live authority**;
- V4 does **not** change Stage 12;
- V4 does **not** change the current 15-second fast guard.

This file freezes only the research namespace, definitions, stages, and promotion gates.

## Why V4 exists

The retired V3 track established:

- clean terminal cohort: **1,196** trades;
- median terminal observed peak / true MFE: **90.17%**;
- mean capture: **86.33%**;
- >=90% share: **50.42%**;
- <80% share: **25.67%**;
- **306 / 307** trades below 80% were dominated by favorable excursions occurring between ~15-second current-price observations;
- universal trailing destroyed runners;
- selective 15-second protection also failed to reduce the <80% tail;
- the retired Stage 2B.1 lane proved that ~5-second sampling infrastructure was operational, but that lane has been shut down and archived.

Therefore V4 starts from a different premise:

> Improve causal price-path observability first. Do not tune another protection formula until the information layer itself proves materially better.

## Core definitions

- **True MFE**: offline favorable-excursion benchmark reconstructed after close. Never a runtime input.
- **Observable peak**: maximum executable/current price PnL actually sampled by the active V4 observation mechanism.
- **Observation resolution**: actual time between successive causal executable-price observations.
- **Capture ratio**: observable peak / true MFE for observability stages; later realized exit / true MFE only after an execution stage exists.
- **Low tail**: capture ratio <80%.
- **High capture**: capture ratio >=90%.
- **Runner**: a trade whose favorable excursion continues materially after an earlier local peak/retracement.

## Non-negotiable design rules

1. **One active V4 observation mechanism only.**
   - No parallel 5s shadow plus separate production peak observer.
   - No duplicate polling lanes measuring the same thing.

2. **Observation before protection.**
   - V4 must first prove a better observable-peak distribution.
   - No new trailing/profit-protection formula is promoted during V4-1 to V4-3.

3. **Executable prices only for causal observable peaks.**
   - Current/tick/exchange event prices may count as observed.
   - Candle high/low is an offline benchmark or trigger-touch diagnostic, not an executable observed peak unless the exchange mechanism itself actually observed/acted on it.

4. **No future leakage.**
   - True MFE and terminal-vs-continuation labels are offline labels only.

5. **No synthetic backfill.**
   - Missing historical high-frequency observations are not reconstructed as if they had been observed live.

6. **Explicit activation boundary.**
   - When V4 is eventually activated, only positions/events after the frozen boundary may enter the prospective cohort.

7. **Distributional success criteria.**
   - Median alone is insufficient.
   - V4 must report mean, median, P10, P25, >=90% share, <80% share, and chronological stability.

8. **Runner preservation remains a separate gate.**
   - Better visibility is not permission to exit every local peak.

## Data-source contract

Step 3 intentionally does **not** activate or hard-code a new provider/runtime source.

When V4-1 is implemented, it must expose one canonical observation stream to downstream logic. If more than one market-data API/provider is used for resilience or cross-checking, they must feed that **single canonical stream** rather than create parallel competing peak observers.

Provider selection, fallback behavior, timestamp normalization, duplicate suppression, and disagreement handling must be frozen before V4-1 activation.

## Roadmap

### V4-0 — Namespace & Contract ✅ COMPLETE

Purpose:
- open the new namespace;
- freeze definitions and gates;
- explicitly separate V4 from retired V3 paths;
- make no runtime change.

Artifacts:
- `PP_DECISION_V4.md`
- `docs/research/profit_protection_v4/PP_V4_HIGH_FREQUENCY_PEAK_CAPTURE_CONTRACT.md`
- `research/profit_protection_v4/README.md`

### V4-1 — High-Frequency Observability Benchmark 🟢 ACTIVE PROSPECTIVE CAPTURE

Implementation frozen before prospective activation:

- prospective start boundary: `1791079128949` (Binance server time; frozen while entries were paused and open positions = 0);\n- canonical source: **Binance USD-M Futures REST all-symbol ticker-price snapshot**;
- source mode: **PRIMARY**;
- fallback: **NONE / FAIL-CLOSED**;
- target cadence: **5 seconds**;
- one batch request per active cycle, not one request per symbol;
- canonical observed timestamp: local receive timestamp;
- provider event timestamp: unavailable/null for this REST endpoint;
- duplicate key: position + V4 cycle/observation timestamp; duplicate attempts are audited;
- position scope: PAPER positions opened strictly after the prospective start boundary;
- persistence: `pp_v4_observation_cycles` + `pp_v4_peak_observations`;
- audit endpoint: `GET /pp-v4/stage1/summary`;
- evaluator: `research/profit_protection_v4/stage1_observability_benchmark.py`.

No AI calls. No REDUCE/CLOSE. No paper/live order submission. Stage 12 remains 15 seconds.

Matched evaluation after close compares the same position across:
1. V4 high-frequency current-price peak;
2. existing ~15s PP-V2 current-price peak;
3. offline true MFE.

#### Preregistered cohort gate

Before V4-2/V4-3 decisions:
- >= **100** closed matched trades;
- >= **50** matched trades with true MFE >= +0.30%.

#### Preregistered data-quality gate

- cycle error rate <= **2%**;
- missing-position sample rate <= **2%**;
- duplicate observation attempts = **0**;
- median per-position sample gap <= **5.75s**;
- P90 per-position sample gap <= **7.5s**;
- max per-position sample gap <= **20s**.

#### Preregistered V4-2 observability gate

Against the same-trade ~15s comparator:
- median capture uplift >= **+3.0 percentage points**;
- aggregate favorable-peak / true-MFE capture uplift >= **+3.0 pp**.

#### Preregistered V4-3 lower-tail gate

All must pass:
- >=90% capture share uplift >= **+5.0 pp**;
- <80% capture share reduction >= **5.0 pp**;
- P10 uplift >= **+5.0 pp**;
- P25 uplift >= **+3.0 pp**;
- LATE chronological third must not lose >=90% share;
- LATE chronological third must not increase <80% share.

These thresholds are frozen before prospective results are available.

No exit authority.

#### Activation record

- deployed commit: `fbdf4f74ebb76178802879bba3d9e95a0a7bfd10`;
- prospective start boundary: `1791079128949`;
- boundary frozen while entries were paused and open positions = **0**;
- runtime enabled: `PP_V4_STAGE1_ENABLED=true`;
- target cadence: **5s**;
- Stage 12 fast guard remained **15s**;
- audit endpoint validated **HTTP 200**;
- V4 tables created successfully;
- initial rows/positions/cycles: **0 / 0 / 0** (clean start);
- entries resumed in **RUN** after validation;
- live trading remained disarmed.

### V4-1H — Historical Matched 5s vs 15s Benchmark ✅ COMPLETE

A retrospective same-trade benchmark was run against the archived Stage 2B.1 5s observations, existing ~15s PP-V2 observations, and lifecycle true MFE.

Raw matched closed PAPER positions: **208**.

For a strict apple-to-apple cohort, observations were restricted to the position lifetime and required:
- true MFE >= +0.30%;
- first 5s observation <= 6s after entry;
- final 5s observation <= 6s before close;
- first 15s observation <= 20s after entry;
- final 15s observation <= 20s before close.

Strict cohort: **124 trades**.

Main result:
- median capture: **82.00% -> 87.03%** (**+5.03 pp**);
- aggregate peak / true MFE: **68.37% -> 72.31%** (**+3.94 pp**);
- >=90% share: **34.68% -> 43.55%** (**+8.87 pp**);
- <80% share: **48.39% -> 42.74%** (**5.65 pp reduction**);
- P10: **1.98% -> 5.96%** (**+3.97 pp**);
- P25: **19.92% -> 23.23%** (**+3.30 pp**).

Per trade:
- improved: **66**
- tied: **52**
- worsened: **6**.

Chronological EARLY/MID/LATE all showed positive aggregate and >=90% share uplift; the LATE cohort did not collapse.

Diagnostic against the already-frozen V4 thresholds:
- V4-2 median uplift: PASS;
- V4-2 aggregate uplift: PASS;
- V4-3 >=90 share uplift: PASS;
- V4-3 <80 reduction: PASS;
- V4-3 P25: PASS;
- V4-3 **P10: FAIL** (+3.97 pp vs +5 pp target).

Interpretation:
5s resolution is materially better than ~15s and supports the V4 direction, especially for early favorable excursions. However, 5s alone does not yet establish that the low tail is solved. This result is **retrospective diagnostic only** and grants no protection/trading authority.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE1H_HISTORICAL_MATCHED_BENCHMARK.md`

Frozen result:
`research/profit_protection_v4/results/stage1h_historical_matched_benchmark_1791043570111.json`

### V4-1I — 5s Failure Anatomy ✅ COMPLETE

Stage1H's apparent 5s lower tail was decomposed with actual post-entry Binance traded-price evidence.

Critical benchmark finding:
- Stage12 fast MFE uses rolling closed 1m highs/lows that are **not clipped to the position entry timestamp**;
- newly opened positions can inherit favorable extrema that occurred before entry;
- historical lifecycle MFE can therefore create false post-entry profit opportunities.

Among the **53** Stage1H apparent 5s `<80%` failures:
- **25 (47.17%)** actually had post-entry MFE < +0.30% and were false MFE-eligible cases;
- **4 (7.55%)** were benchmark-contamination dominant and moved above 80% after correction;
- **4 (7.55%)** had both contamination and a genuine 5s miss;
- **20 (37.74%)** were clean genuine post-entry 5s misses.

Thus **29 / 53 = 54.72%** of apparent failures were invalidated or resolved primarily by benchmark correction.

For the **24 genuine residual 5s misses**:
- every trade spent <5 consecutive seconds at >=90% of actual post-entry MFE;
- **20 / 24** spent <=1 second;
- **3 / 24** spent about 2 seconds;
- **1 / 24** spent 3–4 seconds;
- **0 / 24** persisted >=5 seconds.

Decision:
- Stage1H remains directional evidence that 5s improves visibility versus ~15s;
- Stage1H MFE-based promotion gates are **partially superseded** until clean post-entry MFE labels exist;
- no protection formula may be tuned against the contaminated MFE benchmark;
- next priority: **V4-1J — fix Stage12 MFE entry-boundary handling and rebuild clean MFE labels**;
- only then rerun 5s vs 15s and decide whether sub-5s/event-driven observation is required.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE1I_5S_FAILURE_ANATOMY.md`

Frozen result:
`research/profit_protection_v4/results/stage1i_5s_failure_anatomy.json`

### V4-1J — Clean Post-Entry MFE Rebuild ✅ COMPLETE

Stage1J corrected the MFE entry-boundary defect discovered in Stage1I and rebuilt the historical benchmark without using old MFE eligibility as a selection filter.

Runtime:
- Stage12 lifecycle version: `stage12-v3.1-entry-boundary`;
- MFE/MAE and hard-stop position-path bounds use only fully closed candles whose open timestamp is at/after `opened_at_ms`, plus current price;
- candles that straddle entry are excluded from position excursion accounting;
- market-context rolling candles remain unchanged and cannot feed position MFE/MAE.

Historical clean-label cohort:
- strict matched 5s + 15s trades: **189**;
- clean post-entry MFE >= +0.30%: **99**;
- old MFE >= +0.30% but clean MFE < +0.30%: **25**;
- old MFE < +0.30% but clean MFE >= +0.30%: **0**.

Clean same-trade benchmark:
- median capture: **88.02% -> 93.29%** (**+5.27 pp**);
- aggregate capture: **83.81% -> 87.86%** (**+4.05 pp**);
- >=90% share: **43.43% -> 56.57%** (**+13.13 pp**);
- <80% share: **33.33% -> 24.24%** (**9.09 pp reduction**);
- P10: **42.23% -> 50.31%** (**+8.08 pp**);
- P25: **70.41% -> 80.90%** (**+10.49 pp**).

Chronological LATE third:
- aggregate uplift **+5.17 pp**;
- >=90 share uplift **+12.12 pp**;
- <80 share reduction **15.15 pp**.

Clean-label diagnostic:
- cohort gate: **PASS**;
- V4-2 median/aggregate observability gates: **PASS**;
- V4-3 >=90 / <80 / P10 / P25 / LATE stability gates: **PASS**.

This supersedes Stage1H's contaminated-MFE gate interpretation. Stage1H remains useful only as historical directional evidence.

No protection/trading authority is granted. The remaining clean 5s lower tail is **24.24%**, with SHORT still weaker than LONG. The next research question is whether sub-5s/event-driven observation compresses that residual tail before any protection formula is engineered.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE1J_CLEAN_MFE_REBUILD.md`

Frozen result:
`research/profit_protection_v4/results/stage1j_clean_mfe_rebuild.json`

### V4-1K — Clean Residual Sub-5s Benchmark ✅ COMPLETE

Stage1K tested the **24 / 99 (24.24%)** clean Stage1J residual trades whose archived actual 5s capture remained below80%.

The Stage1K population matches the 24 genuine residual Stage1I trades exactly.

Offline counterfactual:
- Binance USD-M aggregate trades;
- 100ms polling-phase grid;
- 2s and 1s decisions use only their own scheduled samples;
- no archived 5s floor is allowed to rescue a failing phase;
- event-driven/tick is an observability upper bound only.

Preregistered objective:
- compress overall clean <80% share from 24.24% to <=10%;
- requires at least **15 / 24** residual trades rescued to >=80%.

Results:
- 2s expected >=80 rescue: **5.6 / 24** -> projected overall <80 **18.59%** -> **FAIL**;
- 1s expected >=80 rescue: **8.3 / 24** -> projected overall <80 **15.86%** -> **FAIL**;
- event-driven/tick historical upper bound: 24 / 24 observable, but this is **not** an execution claim.

At 1s:
- median phase probability of >=80 capture: **20%**;
- only **4 / 24** trades hit >=80 in every tested phase;
- **8 / 24** have zero >=80 hit probability across the tested 1s phases;
- LONG expected >=80 rescue: **6.0 / 13 (46.15%)**;
- SHORT expected >=80 rescue: **2.3 / 11 (20.91%)**.

Decision:
- do **not** deploy 2s or 1s periodic polling as the low-tail solution;
- do **not** tune protection formulas;
- next information-layer research candidate is **V4-1L — Event-Driven Observability Benchmark**;
- no runtime or trading authority is granted by Stage1K.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE1K_SUB5S_BENCHMARK.md`

Frozen result:
`research/profit_protection_v4/results/stage1k_sub5s_phase_benchmark.json`

### V4-2A — Observable Peak → Realized Leakage Anatomy ✅ COMPLETE

Frozen Stage1J clean cohort: **99 trades**.

Stage2A reconstructs an executable-net observable peak benchmark from archived ~5s observations while preserving any REDUCE that occurred before the eventual observed peak. The benchmark includes recorded paper entry fee, exit fee, and adverse slippage.

Core result:
- mean remaining positive observability gap: **0.138 pp**;
- mean observable-net-peak → realized leakage: **0.717 pp**;
- leakage is about **5.21x larger** than the remaining observability gap on the mean comparison;
- no-prior-REDUCE robustness subset (N=74): **4.98x**.

Protectable observable net peak >= +0.50%, N=42:
- median observable net peak: **+0.940%**;
- median actual realized: **+0.378%**;
- median retention: **29.29%**;
- **41 / 42** retained <80%;
- **35 / 42** retained <50%;
- **10 / 42** ended <=0% realized.

Runner >= +1.00%, N=20:
- median retention: **36.37%**;
- >=80% retention: **1 / 20**.

Runner >= +2.00%, N=9:
- median retention: **37.17%**;
- >=80% retention: **0 / 9**.

Giveback timing after the observed 5s peak:
- below 90% of peak: median **9.995s**;
- below 80%: median **15.032s**;
- below 70%: median **25.027s**;
- below 50%: median **74.984s**;
- actual peak-to-close median: **234.5s**.

Decision:
- the dominant current bottleneck is **realized profit retention**, not the residual observability gap;
- proceed to **V4-2B — Optimal Protection Frontier**;
- Stage2A selects **no** protection threshold;
- no runtime/trading authority is granted.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE2A_OBSERVABLE_REALIZED_LEAKAGE.md`

Frozen result:
`research/profit_protection_v4/results/stage2a_observable_realized_leakage.json`

### V4-2B — Optimal Protection Frontier ✅ COMPLETE

Stage2B swept **144 causal CLOSE-overlay rules** on the frozen 99-trade Stage2A cohort.

Split:
- development EARLY+MID: **66 trades**;
- untouched LATE holdout: **33 trades**.

Grid:
- arm peak: 0.30 / 0.50 / 0.75 / 1.00 / 1.50 / 2.00%;
- retain ratio: 95 / 90 / 85 / 80 / 75 / 70 / 60 / 50%;
- confirmation: 1 / 2 / 3 consecutive ~5s observations.

Results:
- Pareto frontier: **18 candidates**;
- LATE holdout-positive: **6 candidates**.

Strongest research reference:
`arm=1.50%, retain=90%, confirm=2`

LATE holdout:
- total realized: **+$0.47 -> +$38.56**;
- delta: **+$38.10**;
- observable-net-peak >=0.50% median retention: **31.46% -> 60.93%**;
- runner >=1% median retention: **36.97% -> 86.42%**;
- runner >=1% >=80 retention share: **0% -> 62.50%**;
- runner >=2% median retention: **43.13% -> 73.44%**;
- runner >=2% nonpositive outcomes: **1 -> 0**.

Full 99-trade diagnostic:
- total realized: **-$10.02 -> +$75.96**;
- delta: **+$85.98**;
- trigger count: **19 / 99**;
- runner >=1% median retention: **36.37% -> 77.27%**;
- runner >=2% median retention: **37.17% -> 82.46%**.

Concentration diagnostic for the best reference:
- EARLY delta **+$11.34**;
- MID delta **+$36.54**;
- LATE delta **+$38.10**;
- LATE 7/8 triggered trades improve and 1 deteriorates;
- largest single LATE contributor = **40.77%** of LATE improvement.

The frontier also exposes a second regime:
- lower-arm `0.50 / 60% / 2` increases full-cohort win rate to **56.57%** and cuts >=0.50%-peak nonpositive outcomes from 10 to 1;
- but runner >=1% / >=2% median retention remains only about **46–47%**.

Decision:
- one universal static rule is not sufficient;
- proceed to **V4-2C — Runner Preservation / Two-Regime Protection**;
- Stage2B selects **no runtime policy** and grants no protection authority.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE2B_OPTIMAL_PROTECTION_FRONTIER.md`

Frozen result:
`research/profit_protection_v4/results/stage2b_optimal_protection_frontier.json`

### V4-2C — Runner Preservation / Two-Regime Protection ✅ COMPLETE

Stage2C tested **24 preregistered causal hybrid candidates** on the frozen 99-trade Stage2A cohort.

No untouched-holdout claim is made in Stage2C because Stage2B already inspected all chronological thirds. Instead Stage2C requires positive improvement in EARLY/MID/LATE and compares against both Stage2B static reference regimes.

Balanced-pass candidates: **2 / 24**.

Selected research reference by preregistered stability ranking:

`small arm=0.50%, retain=60%, confirm=3 -> REDUCE 25%; runner qualify=1.50% -> retain=90%, confirm=2 -> CLOSE remaining`

Full 99-trade diagnostic:
- historical total: **-$10.02**;
- Stage2B runner-static total: **+$75.96**;
- selected hybrid total: **+$78.73**;
- win rate: **36.36% actual / 37.37% runner-static / 45.45% hybrid**;
- small partial reductions: **49**;
- runner closes: **19**;
- helped / harmed: **49 / 13**.

Small/medium observable-net peak 0.30–1.00%, N=33:
- nonpositive outcomes: **18 -> 12**;
- wins: **15 -> 21**;
- total: **+$0.65 actual -> +$8.33 hybrid**.

Runner >=1%, N=20:
- Stage2B runner-static median retention: **77.27%**;
- selected hybrid median retention: **73.57%**;
- difference: **-3.70 pp**, inside preregistered -5 pp tolerance;
- hybrid total: **+$150.80**;
- nonpositive: **1**.

Runner >=2%, N=9:
- selected hybrid median retention: **82.46%**, equal to Stage2B runner-static median;
- total: **+$100.00**;
- nonpositive: **0**.

Chronological stability:
- EARLY delta **+$11.86**;
- MID delta **+$42.28**;
- LATE delta **+$34.61**.

Concentration:
- largest positive contributor = **19.45%** of total uplift;
- top 3 = **44.15%**.

Decision:
- the two-regime architecture passes all balanced gates;
- proceed to **V4-2D — Full Replay / Prospective Shadow Specification**;
- Stage2C selects **no runtime policy** and grants no protection authority.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE2C_RUNNER_PRESERVATION.md`

Frozen result:
`research/profit_protection_v4/results/stage2c_runner_preservation.json`

### V4-2D — Full Replay + Prospective Shadow ✅ COMPLETE

Historical audit:
- 99/99 trades replayed;
- Stage2C metrics exact;
- invariant failures: **0**;
- selected hybrid total: **+$78.73**;
- win rate: **45.45%**;
- small REDUCE count: **49**;
- runner CLOSE count: **19**.

Prospective shadow implementation:
- persistent two-regime state machine;
- canonical V4 5s observations only;
- action authority: **NONE**;
- fail-isolated from the canonical observer;
- endpoint: `GET /pp-v4/stage2d/shadow/summary`.

Prospective activation requires a fresh zero-open-position boundary. Minimum evaluation is 100 closed matched positions and 50 positions reaching >=+0.50% running observed peak. No runtime exit authority is granted.

Full report:
`docs/research/profit_protection_v4/PP_V4_STAGE2D_FULL_REPLAY_SHADOW.md`

### V4-2 — 5s/Event Path vs 15s Benchmark ⏳ BLOCKED ON V4-1

Use matched trades only.

Required comparison:
- old ~15s observable peak;
- V4 high-frequency observable peak;
- true MFE.

Primary question:

> Did higher-frequency observation materially recover favorable excursions that the 15-second path missed?

No protection tuning.

### V4-3 — Lower-Tail Compression Gate ⏳ BLOCKED ON V4-2

Explicitly test whether the information layer fixes the problem that killed V3.

Baseline reference from frozen V3 terminal cohort:
- >=90% share: **50.42%**
- <80% share: **25.67%**
- P10: **67.99%**
- P25: **79.48%**

V4-3 must determine whether the new path:
- materially increases >=90% share;
- materially reduces <80% share;
- improves P10/P25;
- is stable chronologically;
- does not achieve apparent improvement through benchmark mismatch or missing-data selection.

If lower-tail compression is not material, V4 protection engineering remains blocked.

### V4-4 — Protection + Runner Engineering ⛔ BLOCKED ON V4-3 PASS

Only after observability improves materially:
- engineer state-dependent profit protection;
- preserve continuation runners;
- evaluate actual exit economics with fees/slippage;
- use chronological tuning/holdout;
- never optimize directly against future MFE in runtime.

## Promotion gates

### V4-1 data-quality gate

Required before analysis:
- stable timestamping;
- bounded missing observations;
- no duplicate observations counted as independent samples;
- explicit source/fallback provenance;
- sample cadence measured from actual timestamps, not configuration alone.

### V4-2 observability gate

A matched-trade comparison must show a material improvement over the old ~15s path. Exact promotion threshold will be preregistered before V4-1 activation and must not be chosen after seeing results.

### V4-3 distribution gate

The new information layer must improve the **distribution**, not just the median.

A pass requires all of:
- >=90% share improves;
- <80% share declines;
- P10 improves;
- P25 improves;
- no major chronological cohort collapses.

The exact minimum effect sizes must be frozen before the prospective evaluation.

### V4-4 protection gate

Any later protection policy must improve realized/counterfactual economics while preserving runners and respecting execution constraints.

## Relationship to archived V3 evidence

Do not delete or rewrite:

- `research/profit_protection_v3/archive/low_tail_15s/`
- `research/profit_protection_v3/archive/stage2b1_5s_shadow/`
- historical table `pp_v3_fast_peak_observations`

Those artifacts are controls and failure evidence.

They may be used for historical comparison, but they must not be silently reactivated as V4 runtime components.

## Step 3 completion condition

Step 3 is complete when:

- the V4 namespace exists;
- this contract is merged;
- README/source-of-truth links exist;
- active runtime contains **zero PP_V4 startup hooks, endpoints, env flags, or loops**;
- Stage 12 remains unchanged.

At that point V4-1 may be designed, but it is still not active.

## Stage1J production activation

- merged runtime commit: `84e2f65df4e6065f0deca595253e4ff1a77e5309`
- clean runtime boundary freeze: `1791088148534`
- control at boundary: `PAUSE_ENTRIES`
- open positions at boundary: **0**
- deployed lifecycle version: `stage12-v3.1-entry-boundary`
- post-deploy boundary probe: PASS
- app container health: healthy
- V4 5s observer remained enabled at 5s with no trading authority
- control resumed to `RUN` at `1791088208713`
- live trading remained disabled/disarmed

Any prospective clean-MFE runtime cohort must use positions opened **after `1791088148534`**. Because there were zero open positions at the freeze, no pre-fix position state crosses the boundary.


## Stage2D production shadow activation

- merged implementation commit: `8e3560b9b9789b925bd96b2b27a605daeffa7a73`
- clean shadow boundary: `1791094561302`
- control at boundary: `PAUSE_ENTRIES`
- open positions at boundary: **0**
- `PP_V4_STAGE2D_SHADOW_ENABLED=true`
- shadow version: `pp-v4-stage2d-shadow-v1`
- authority: **NONE**
- app health after rebuild: **healthy**
- shadow endpoint: **HTTP 200**
- initial store: 0 positions / 0 actions / 0 duplicates / 0 out-of-order / 0 invariant errors
- control resumed to `RUN` at `1791094640894`
- live remained disabled/disarmed

Any prospective Stage2D shadow evaluation must use positions opened strictly after `1791094561302`.
