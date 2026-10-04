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
