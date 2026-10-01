# WD-5H Stage 4A Frozen Results — 2026-10-01

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

TEMPORAL_FEATURE_RECONSTRUCTION_COMPLETE

## Coverage

- rows: 2,175 / 2,175
- exact Stage11C gate match: 2,175 / 2,175
- pre-entry cache: 2,175 / 2,175
- post-entry 1m cache: 2,175 / 2,175
- OI cache: 2,175 / 2,175
- benchmark symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT
- causality violations: 0

Stage11C-to-fill latency:

- median: 200 ms
- p90: 389 ms

## Temporal feature matrix

- output columns: 351
- temporal feature columns: 330
- temporal features per horizon: 110

Per horizon approximately:

- micro: 32
- market-relative: 21
- flow: 15
- OI: 11
- direct confirmation-path: 10
- T0 deltas: 15

## Closed 1m-bar availability

### T+1

- exactly 1 new closed bar: 2,173
- zero new closed bars: 2

### T+2

- exactly 2 new closed bars: 2,173
- exactly 1: 2

### T+3

- exactly 3 new closed bars: 2,173
- exactly 2: 2

The two boundary cases are:

- HUSDT LONG
- RIVERUSDT LONG

These are not missing exchange bars.

Their Stage11C decisions occur so close to a minute boundary that the next
candle close falls just after the exact T+1 target.

The strict causal implementation therefore correctly excludes that candle at
T+1.

## OI temporal availability

Fresh 5m OI point after T0:

| Horizon | Trades with new OI point | Coverage |
|---|---:|---:|
| T+1 | 0 | 0.00% |
| T+2 | 0 | 0.00% |
| T+3 | 52 | 2.39% |

This is a major design finding.

Because the candidates are typically emitted shortly after 5-minute signal
boundaries, a 1-3 minute confirmation window usually ends before the next
historical 5-minute OI observation exists.

Therefore:

- OI can remain a static/context feature;
- OI cannot be treated as a broadly available fresh temporal confirmation
  signal at T+1/T+2/T+3;
- Stage 4B should focus primarily on price path, microstructure, taker flow,
  and market-relative movement.

## Labels carried forward

For Stage 4B only:

- META_WIN: 564
- META_LOSS: 1,327
- TIMEOUT: 284

These labels are not used in Stage 4A feature derivation.

## Conclusion

Stage 4A successfully creates the causal temporal dataset required for the
next research phase.

No predictive claim is made yet.

The main practical result is that the confirmation problem is now observable
at exact T+1/T+2/T+3 timestamps without using partially formed bars or future
data.

## Next

WD-5H Stage 4B — Temporal Confirmation Pattern Discovery

Stage 4B should compare META_WIN versus META_LOSS separately for each horizon
and answer:

1. which temporal features gain separation after T0;
2. whether T+1, T+2, or T+3 provides the strongest stable discrimination;
3. which feature directions remain stable across chronological partitions;
4. which evidence combinations are plausible candidates for Stage 4C.

Stage 4B must not choose a production threshold.

## Frozen artifact hashes

wd5h4a_temporal_features.csv
SHA256: 23cd213d07e676cc5e176be6f311fa765b348bea00d387c1edc49194b64f345a

wd5h4a_temporal_feature_results.json
SHA256: c1a161836efbd8740063e6bfa624c256b9d54b92ea24786ebc9365cb4a808967

wd5h4a_benchmark_1m_cache.json
SHA256: 37b4edfa59d68512d278e9c529e6747aa08cfdfbe272f7e138c11a96cc05ed9c

wd5h4a_oi_5m_cache.jsonl
SHA256: 6b2c06a86e1f203b68324cfadd76531061d952140adb60c361dc2336a5fce169
