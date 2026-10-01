# WD-5F — Conditional Reversal Confirmation Detector

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5F tests a safer reversal architecture:

> Only evaluate reversal after the continuation has already been classified as overheated.

The decision semantics are asymmetric:

- high-confidence opposite thesis -> `REVERSE`
- otherwise -> `NO TRADE`

This matters because false negatives are economically tolerable: a reverse-capable case that is skipped becomes NO TRADE rather than a loss.

False positives are the dangerous error: reversing a trade that should have been skipped.

## Frozen overheat gate

WD-5F reuses the frozen WD-5D overheat threshold:

`overheat_pressure >= 5.481925222153388`

The threshold is not retuned in WD-5F.

Applied to the 821 large WD-4 targets:

- eligible primary cases: 821
- conditional overheated cases: 319
- share: 38.86%
- REVERSE target: 179
- NO TRADE target: 140
- REVERSE prevalence: 56.11%

The overheat condition therefore enriches the REVERSE target from roughly 53.0% overall to 56.1%.

## New evidence families

WD-5F adds 51 research features in three causal groups.

### Market-relative context

Benchmarks:

- BTCUSDT
- ETHUSDT
- BNBUSDT
- SOLUSDT

Features include:

- market median selected-side return over 1m / 3m / 5m / 15m / 30m
- market alignment / opposition fractions
- market dispersion
- BTC / ETH selected-side returns
- coin minus market return
- 20-bar coin beta to BTC
- beta-adjusted residual return
- relative overextension versus market

Benchmark 1m data are reconstructed only from candles closed by the Stage11C decision timestamp.

### Taker-flow / micro-structure dynamics

Features include:

- selected-side taker share over 1m / 3m / 5m
- prior-window taker share
- taker acceleration / decay
- selected taker delta
- break of prior 3-bar / 5-bar opposite structure
- two-bar opposite body
- failed selected-side extreme
- selected-side 5-bar slope
- structure reversal score
- volume climax fade
- range climax fade

### OI dynamics

Historical Binance 5m OI is reconstructed for every conditional case.

Features include:

- current 5m OI change
- previous 5m OI change
- OI acceleration
- 15m / 30m OI change
- OI unwind while price continues selected-side
- OI crowding while price continues
- OI acceleration x overheat
- OI crowding x overheat

OI historical coverage is complete for the 319 conditional cases.

## Chronological evaluation

Conditional cohort:

- train: first 60% = 191
- validation: next 20% = 64
- test: final 20% = 64

Class balance:

Train:
- REVERSE 97
- NO TRADE 94

Validation:
- REVERSE 40
- NO TRADE 24

Test:
- REVERSE 42
- NO TRADE 22

The selected logistic variant is chosen using validation AUC only.

Variants:

- WD-5E micro
- market-relative
- flow / structure
- OI dynamics
- all new features
- WD-5D engineered + new
- all portable conditional features

A shallow randomized forest is also tested as nonlinear sensitivity.

## One-sided reversal gate

After the symmetric classification audit, WD-5F formalizes the correct decision objective:

> reverse only when validation precision is very high; otherwise default to NO TRADE.

The frozen one-sided threshold search uses:

- validation precision floor: 80%
- minimum validation flags: 5
- maximize recall subject to that precision floor

This is more aligned with the economic target than requiring symmetric REVERSE / NO TRADE classification.

## Important holdout caveat

The one-sided decision objective was formalized after the first symmetric WD-5F test inspection.

Therefore the final one-sided result is a **research candidate**, not a pristine production-promotion holdout.

Prospective shadow validation remains mandatory.

## Reproducibility

Code:

- `market_radar/wd5f_conditional_reversal.py`
- `scripts/wd5f_conditional_reversal.py`
- `tests/test_wd5f_conditional_reversal.py`

Outputs:

- `/opt/core-app/data/wd5f_benchmark_1m_cache.json`
- `/opt/core-app/data/wd5f_oi_5m_cache.jsonl`
- `/opt/core-app/data/wd5f_conditional_reversal_features.csv`
- `/opt/core-app/data/wd5f_conditional_reversal_results.json`

Focused WD-0 through WD-5F tests: **63/63 PASS**.
