# WD-5E — Multi-Head Opportunity Detector Prototype

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5E turns the WD-5B through WD-5D findings into a three-head causal prototype.

The prototype does not issue production orders. It tests whether the current frozen research data can support three distinct decisions:

1. **Continuation Health**
   - healthy continuation versus overheated continuation that later fails.

2. **Path Expectation**
   - clean winner versus recovered-drawdown winner.

3. **Reversal Thesis**
   - for WD-4 strict wrong-direction cases, distinguish:
     - `REVERSE` / opposite-from-entry WIN target
     - `NO TRADE` target.

This deliberately avoids forcing one universal LONG/SHORT classifier.

## Head definitions

### Head A — Continuation Health

Cohort:

- future MFE >= 1%
- positive-final runner winners versus RIGHT_THEN_FAILURE runner misses

N = 523:

- healthy/winner: 404
- overheated-failure/missed: 119

Feature variants:

- legacy causal features
- WD-5D engineered features
- combined

### Head B — Path Expectation

Cohort:

- WD-1 `CORRECT_RUNNER`
- WD-1 `RECOVERED_DRAWDOWN`

N = 500:

- recovered: 385
- clean: 115

Positive class = RECOVERED.

Feature variants:

- legacy causal features
- WD-5D engineered features
- combined

### Head C — Reversal Thesis

Primary WD-4 strict target cohort:

- `OPPOSITE_FROM_ENTRY_WIN`: 435
- `NO_TRADE_TARGET`: 386

N = 821.

Positive class = REVERSE.

This head is the critical bottleneck because WD-5B showed the existing Stage4/5/6/11C feature space contains very little independent opposite-side evidence.

## New pre-entry micro-path reconstruction

WD-5E reconstructs Binance USD-M Futures 1m candles ending at the **Stage11C causal ENTER decision timestamp**.

For every one of the 821 reversal-target trades:

- 39 historical 1m rows were retrieved in the cached source window
- the model uses the last 30 closed candles
- candles with `close_at_ms > Stage11C checked_at_ms` are discarded
- coverage = 821 / 821

Cache:

`/opt/core-app/data/wd5e_preentry_1m_cache.jsonl`

## 32 micro features

WD-5E adds 32 symmetric, side-adjusted pre-entry features.

### Multi-horizon micro return

- side-adjusted 1m
- 3m
- 5m
- 10m
- 15m
- 30m returns
- previous 3m / 5m returns
- recent-versus-prior momentum decay

### Local extreme / rejection

- distance to selected-side 15m extreme
- distance to selected-side 30m extreme
- selected-side candle close location
- reversal/rejection wick
- selected-side candle body
- consecutive selected-side bars

### Range / volume / trade behavior

- latest range versus previous 10 bars
- 3m range versus prior 3m
- latest volume versus previous 10 bars
- 3m volume versus prior 3m
- trade-count ratio

### Taker-flow microstructure

- selected-side taker share 1m
- selected-side taker share 3m
- prior selected-side taker share 3m
- taker-flow decay
- price-flow divergence

### Exhaustion signatures

- volume climax then fade
- range contraction after impulse
- 20-bar close z-score
- selected-side VWAP extension
- fixed micro reversal-pressure interaction

All features are calculated from data known before the entry decision.

## Chronological evaluation protocol

Each head is sorted by actual trade timestamp.

- first 60% = training + train-only feature ranking
- next 20% = validation / hyperparameter selection / triage threshold selection
- final 20% = untouched final test

Logistic search:

- top-k feature counts
- L2 regularization

Reversal additionally receives a nonlinear shallow-random-forest sensitivity check.

## Triage

Each selected logistic model is also tested in an abstaining form.

A validation-selected lower / upper probability pair creates:

- positive action
- negative action
- ABSTAIN

The threshold search attempts precision floors from 80% downward.

Triage is diagnostic only and has no trading authority.

## Reversal robustness checks

Because reversal is the most safety-critical head, WD-5E adds:

1. linear logistic variants
2. shallow nonlinear forest
3. final-test subset containing symbols never seen in train or validation

The novel-symbol subset contains:

- 33 trades
- 30 unseen symbols.

## Promotion rule

WD-5E does not promote a multi-head action policy unless the reversal head also becomes robust.

Continuation Health or Path Expectation success alone is not enough to authorize automatic reverse execution.

## Reproducibility

Code:

- `market_radar/wd5e_multihead.py`
- `scripts/wd5e_multihead.py`
- `tests/test_wd5e_multihead.py`

Outputs:

- `/opt/core-app/data/wd5e_preentry_1m_cache.jsonl`
- `/opt/core-app/data/wd5e_multihead_features.csv`
- `/opt/core-app/data/wd5e_multihead_results.json`

Focused WD-0 through WD-5E tests at completion: **56/56 PASS**.
