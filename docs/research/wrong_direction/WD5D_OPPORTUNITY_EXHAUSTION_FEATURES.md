# WD-5D — Opportunity + Exhaustion Feature Discovery

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5D builds a richer causal feature space for the winner archetypes discovered in WD-5C.

The immediate questions are:

1. Can we distinguish a healthy runner from an overheated continuation that later fails?
2. Can we identify a >=1% runner opportunity before entry?
3. Can we distinguish BIG_RUNNER from SMALL_EDGE?
4. Can we distinguish CLEAN versus RECOVERED winner path shape?

WD-5D is a feature-discovery stage. It does not promote a trading rule.

## Source cohort

Input:

`/opt/core-app/data/wd5c_winner_archetypes.csv`

Frozen cohort:

- 2,175 closed PAPER trades
- causal Stage11C decision-time features
- WD-5C opportunity / path / capture labels
- no future outcome field is exposed as a model feature

## New causal features

WD-5D derives **27 new features** from information already available at the causal entry decision.

### Momentum-shape features

- 5m versus 15m acceleration
- 15m versus 1h acceleration
- momentum curvature
- 1m versus 3m micro acceleration
- 1m / 3m micro speed ratio
- gate 3m speed versus signal 5m speed

### Volatility-normalized extension

- 5m extension normalized by median absolute 5m return
- 15m normalized extension
- 1h normalized extension

### Activity heat

A geometric interaction of:

- return expansion
- volume ratio
- range ratio
- trade-count ratio

Additional interactions:

- score x activity heat
- heat x price extension

### Flow / positioning mismatch

- selected-side taker-flow gap
- context flow gap
- price x flow gap
- gate-price x flow gap
- heat x flow gap
- OI change per unit selected-side price move

### Micro-fade / exhaustion

- heat x micro fade
- activity-normalized extension
- volume / range relationship
- trades / range relationship

### Thesis support

Numeric encodings of:

- Stage11C family balance
- positioning support
- regime support
- flow support
- composite continuation support

### Fixed overheat-pressure composite

`overheat_pressure` is deliberately label-agnostic.

It combines:

- selected score,
- activity heat,
- positive multi-timeframe acceleration,
- weak near-entry flow,
- and micro fade.

The formula is frozen before threshold evaluation.

## Evaluation tasks

### A. RUNNER_WIN vs RUNNER_MISSED

Cohort:

- MFE >= 1%
- positive-final runner winners versus RIGHT_THEN_FAILURE runner misses

N = 523:

- winner: 404
- missed: 119

This is the primary exhaustion task.

### B. RUNNER_OPPORTUNITY vs SUB1

- positive target: future MFE >= 1%
- negative target: future MFE < 1%

N = 2,175.

This tests absolute opportunity-size prediction.

### C. BIG_RUNNER vs SMALL_EDGE

- BIG_RUNNER: MFE >= 2%
- SMALL_EDGE: 0.5% <= MFE < 1%

N = 782.

### D. CLEAN vs RECOVERED

- WD-1 CORRECT_RUNNER path versus RECOVERED_DRAWDOWN winner path

N = 500.

## Chronological model protocol

For every task:

- first 60% chronological = training / feature ranking
- next 20% = validation / model selection
- last 20% = final test

Feature ranking is train-only for all three variants:

1. baseline causal features
2. engineered-only features
3. combined baseline + engineered

This was explicitly corrected during WD-5D so the baseline and engineered variants receive identical feature-selection treatment.

The model is regularized logistic regression implemented in research-only pure Python. Production dependencies are unchanged.

## Stability analysis

Every new feature is also measured independently across five chronological blocks.

For numeric features WD-5D records:

- full-cohort rank separation
- direction
- median fifth separation
- minimum fifth separation
- directional consistency

This prevents one-window effects from being treated as structural findings.

## Overheat threshold diagnostic

A simple one-feature diagnostic is performed only for the runner winner/missed cohort.

Selection:

- first 60% chronological only
- threshold chosen to maximize balanced accuracy for detecting MISSED runner
- validation and final test remain untouched

This diagnostic is **not** a production threshold because it is conditioned on the future-known runner cohort and belongs to discovery, not deployment.

## Reproducibility

Code:

- `market_radar/wd5d_features.py`
- `scripts/wd5d_features.py`
- `tests/test_wd5d_features.py`

Outputs:

- `/opt/core-app/data/wd5d_opportunity_exhaustion_features.csv`
- `/opt/core-app/data/wd5d_feature_discovery_results.json`

Focused WD-0 through WD-5D tests at completion: **51/51 PASS**.
