# Stage 3C — Strong Microstructure Parameter Discovery

## Frozen target

The target remains unchanged:

- universe: 1,236 resolved LONG trades
- target: 245 trades satisfying BOTH `META_WIN` and historical maximum MFE >= 1.00%
- non-target: 991 trades

No META_LOSS rebound is relabeled as a target WIN.

## Existing-data result

An exhaustive search over the existing T0 families (momentum, volume/activity, taker flow, OI, funding, VWAP, structure, relative market strength, entry drift) did not produce a stable strong pre-entry parameter.

Existing T0 ceiling remains weak. The strongest stable individual relationships are roughly in the AUC 0.57–0.61 range.

Causal temporal features improve materially by T+3, but this is not evidence of a strong PRE-ENTRY parameter. Examples on unresolved trades include confirm-side-return and micro side-return, with validation/reserve AUC materially above T0. They remain temporal confirmation features and must not be reported as T0 predictive strength.

## Why new data is required

The frozen cohort does not contain historical L2 order-book event streams, queue refill/cancellation events, or raw sub-minute aggregate-trade sequences.

Binance REST aggregate-trade timestamp lookup is restricted to recent data for the required endpoint, so the Sep 29–Oct 1 cohort cannot be honestly reconstructed from that endpoint now.

Therefore Stage 3C must not fabricate historical LOB/CVD values.

## New feature families

The research feature engine in `stage3c_microstructure_features.py` defines causal parameters that can be collected before a future entry decision:

### Order book
- top-1 queue imbalance
- top-5 / top-10 / top-20 quantity imbalance
- top-5 / top-10 / top-20 notional imbalance
- distance-weighted book imbalance
- near-touch liquidity concentration
- spread
- microprice edge

### AggTrade flow
- 1s / 5s / 15s / 30s / 60s quote CVD
- CVD share
- trade-count imbalance
- buyer-vs-seller average trade-size ratio
- large-trade imbalance
- CVD acceleration across nested windows
- CVD persistence
- price response per unit of signed flow
- absorption proxy

## Strong-parameter acceptance rule

A feature is not called STRONG because it looks good in one sample.

Preferred acceptance requires:
- same directional relationship across chronological discovery, validation, and untouched reserve/forward test
- no outcome/future leakage
- point-biserial |r| >= 0.50 OR a clearly predeclared predictive equivalent such as OOS AUC >= 0.70
- enough support to avoid tiny-pocket artifacts
- target accounting always remains 245/1,236 for the frozen LONG objective, or the exact denominator of the forward cohort

If no feature passes, Stage 3C reports NO STRONG PARAMETER FOUND. It does not lower the definition after seeing results.

## Deployment boundary

This branch is research-only. No new microstructure feature has entry authority. Production Stage 11C / Stage 13 behavior must not change until a later frozen validation stage explicitly promotes a feature.
