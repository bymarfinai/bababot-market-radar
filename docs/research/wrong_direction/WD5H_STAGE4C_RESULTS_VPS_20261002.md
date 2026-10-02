# WD-5H Stage 4C Frozen Results — 2026-10-02

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

TEMPORAL_HIGH_PRECISION_GATE_NOT_READY

The temporal gate is materially promising, but it does not satisfy the frozen
promotion criterion.

## Horizon results

### T+1

No validation threshold with at least 10 resolved TAKEs reached 60% precision.

### T+2

Highest feasible validation floor: 60%.

Validation:
- threshold: 0.6367286185
- TAKE: 11
- resolved TAKE: 10
- META_WIN: 6
- META_LOSS: 4
- TIMEOUT: 1
- resolved precision: 60.0%
- all-TAKE WIN rate: 54.55%

Same rule on historical test:
- TAKE: 9
- META_WIN: 7
- META_LOSS: 2
- TIMEOUT: 0
- resolved precision: 77.78%
- all-TAKE WIN rate: 77.78%

This tiny T+2 test pocket is diagnostic only. T+2 is not the formal selected
rule because horizon selection was already frozen on validation and T+3
reached a higher precision floor.

### T+3

T+3 reaches every tested validation precision floor through 80%.

#### 60% floor

Validation:
- META_WIN / resolved TAKE: 71 / 118 = 60.17%
- TIMEOUT: 28

Test:
- 50 / 115 = 43.48%
- TIMEOUT: 20

#### 65% floor

Validation:
- 58 / 89 = 65.17%

Test:
- 42 / 77 = 54.55%

#### 70% floor

Validation:
- 36 / 51 = 70.59%
- all-TAKE WIN rate: 64.29%

Test:
- 20 / 33 = 60.61%
- all-TAKE WIN rate: 51.28%

#### 75% floor

Validation:
- 30 / 40 = 75.0%
- all-TAKE WIN rate: 69.77%

Test:
- 15 / 24 = 62.5%
- all-TAKE WIN rate: 50.0%

#### 80% floor — FORMAL SELECTED RULE

Frozen threshold:

0.6028066188778062

Validation eligible candidates:
- N = 350

Validation TAKE:
- 37
- resolved TAKE: 35
- META_WIN: 28
- META_LOSS: 7
- TIMEOUT: 2
- resolved precision: 80.0%
- all-TAKE WIN rate: 75.68%
- coverage: 10.57%

Historical test eligible candidates:
- N = 339

Same frozen threshold:
- TAKE: 25
- resolved TAKE: 20
- META_WIN: 13
- META_LOSS: 7
- TIMEOUT: 5
- resolved precision: 65.0%
- all-TAKE WIN rate: 52.0%
- coverage: 7.37%

## Lift versus T+3 survivor base

Validation survivor base:

- resolved: 92 META_WIN / 279 = 32.97%
- all eligible: 92 / 350 = 26.29%

Formal selected gate:

- resolved precision: 80.0% = about 2.43x base
- all-TAKE WIN rate: 75.68% = about 2.88x base

Historical test survivor base:

- resolved: 74 META_WIN / 278 = 26.62%
- all eligible: 74 / 339 = 21.83%

Formal selected gate:

- resolved precision: 65.0% = about 2.44x base
- all-TAKE WIN rate: 52.0% = about 2.38x base

This is a major improvement over static pre-entry filtering.

## Why formal status is still NOT READY

The frozen promotion-oriented check required:

- selected validation floor >= 70%;
- historical test resolved precision >= 65%;
- historical test resolved TAKE count >= 10;
- historical test all-TAKE WIN rate >= 55%.

The formal rule meets the first three but misses the fourth:

- all-TAKE WIN rate = 52.0%.

The criterion must not be relaxed after seeing the result.

## Interpretation

Stage 4C provides the strongest selective filtering evidence so far.

The temporal gate is not merely improving AUC. It creates a high-score subset
whose historical test resolved precision rises from a 26.62% survivor base to
65%.

However, five of the 25 selected test candidates are TIMEOUT, reducing the
operational all-TAKE WIN rate to 52%.

That is still a large lift, but not enough for promotion.

## Why Stage 4D is warranted

Stage 4C still labels outcome relative to the original T0 economic path.

It does not answer the real deployment question:

What happens if capital is actually deployed only at T+3?

The selected candidates may have already moved materially before confirmation.
A delayed entry can:

- lose favorable entry price;
- change TP/SL probability;
- miss runners;
- convert original META_WIN to delayed-entry LOSS/TIMEOUT;
- or improve economics by avoiding weak early entries.

Stage 4D should therefore replay the exact frozen 4C candidate set using the
actual T+3 delayed market price.

No 4C rule may be retuned.

## Frozen artifact hashes

wd5h4c_temporal_gate_results.json
SHA256:
ebdc47706490f891ca342a25bc4fa15e25dacbb495f9e3cb816606986eea3e04

wd5h4c_temporal_gate_predictions.csv
SHA256:
9151cba23809f82f5039dbad94782fa2cf6bc2ca6b31e9f0536e48cb820b0b92
