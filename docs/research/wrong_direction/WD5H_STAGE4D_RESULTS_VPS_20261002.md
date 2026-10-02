# WD-5H Stage 4D Frozen Results — 2026-10-02

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

DELAYED_ENTRY_ECONOMICS_NOT_READY

The Stage 4C classifier contains real ranking information, but the frozen T+3
gate is too late to produce acceptable entry economics.

## Frozen selected set

- total TAKE: 62
- validation: 37
- historical test: 25

Original Stage 4C labels across the 62:

- META_WIN: 41
- META_LOSS: 14
- TIMEOUT: 7

## Exact delayed execution coverage

First Binance futures aggTrade at or after exact T0+3m:

- coverage: 62 / 62
- median wait: 743.5 ms
- p90: 4.797 seconds
- maximum: 16.321 seconds

Therefore the economic failure is not caused by a coarse candle-entry proxy.

## Overall delayed-entry replay

After entering at the delayed market price:

- META_WIN: 15
- META_LOSS: 45
- TIMEOUT: 2
- resolved precision: 25.0%
- all-TAKE WIN rate: 24.19%
- actual-exit positive rate: 25.81%

Economics:

- actual close-exit net: **-$94.59**
- average per TAKE: **-$1.53**
- standardized barrier net: **-$75.09**
- standardized average: **-$1.21**

## Historical validation replay

- TAKE: 37
- delayed META_WIN: 10
- delayed META_LOSS: 27
- TIMEOUT: 0
- resolved precision: 27.03%
- actual-exit net: **-$54.87**
- standardized net: **-$42.50**

The original 80% Stage 4C validation classification purity does not survive
actual delayed entry.

## Historical test replay

- TAKE: 25
- delayed META_WIN: 5
- delayed META_LOSS: 18
- TIMEOUT: 2
- resolved precision: **21.74%**
- all-TAKE WIN rate: **20.0%**
- actual positive-exit rate: 24.0%

Economics:

- actual-exit net: **-$39.72**
- average per TAKE: **-$1.59**
- standardized barrier net: **-$32.59**

Therefore Stage 4D fails the economic replay decisively.

## Label transition

### Original META_LOSS — 14

- delayed META_LOSS: 14

None are rescued by waiting and entering later.

### Original META_WIN — 41

- delayed META_WIN: **15**
- delayed META_LOSS: **25**
- delayed TIMEOUT: 1

This is the core failure mechanism.

About 61% of the original META_WIN candidates become delayed META_LOSS.

### Original TIMEOUT — 7

- delayed META_LOSS: 6
- delayed TIMEOUT: 1

## Confirmation chase / edge consumption

Median selected-side move before delayed entry:

- all selected: **+0.4135%**
- original META_WIN candidates: **+0.4497%**

Relative to the original +0.5% Stage 3A favorable barrier:

- all selected have already consumed **82.70%** of the barrier at entry;
- original META_WIN candidates have already consumed **89.93%**.

This explains why Stage 4C classification can look excellent while Stage 4D
economics collapse.

The model is recognizing that the favorable move is happening, but by the time
the confirmation is available the economically attractive entry is largely
gone.

## Entry degradation

All selected:

- median side-adjusted degradation: +0.414%
- mean: +0.462%
- p90: +0.695%

Historical test:

- median: +0.418%
- mean: +0.469%
- p90: +0.662%

## Zero-cost sensitivity

To separate execution cost from structural lateness, Stage 4D reruns the exact
same delayed entries with:

- fee = 0
- slippage = 0

Overall:

- META_WIN: 22
- META_LOSS: 33
- TIMEOUT: 7
- resolved precision: 40.0%
- all-TAKE WIN rate: 35.48%
- actual-exit net: **-$36.38**

Historical test:

- META_WIN: 8
- META_LOSS: 14
- TIMEOUT: 3
- resolved precision: 36.36%
- all-TAKE WIN rate: 32.0%
- net: **-$20.59**

The replay remains negative even with zero execution cost.

Therefore fees and slippage worsen the result but are not the primary cause.

## Runner retention

Conservative 60-minute close-based MFE:

### >=1% runners

- original: 36
- retained after delayed entry: 28
- retention: **77.78%**

### >=2% runners

- original: 19
- retained: 13
- retention: **68.42%**

Some large continuation remains after T+3, but not enough to compensate for
the much larger META_WIN-to-META_LOSS conversion.

## Early-resolution opportunity accounting

Across the final 40% historical population, before T+3:

- early META_WIN: 39
- early META_LOSS: 142
- ratio early LOSS / early WIN: **3.64x**

Waiting three minutes does mechanically avoid many more fast failures than fast
winners.

However, among the remaining candidates the formal confirmation rule enters
too late.

## Interpretation

Stage 4B and 4C were not false discoveries.

They answered a classification question:

> Is the original selected-side move proving itself during the first three
> minutes?

The answer was yes.

Stage 4D asks a different and more important trading question:

> After waiting for that proof, is there still enough edge left to enter?

For the frozen T+3 gate, the answer is no.

## Decision

Do not proceed to Stage 4E with the current gate.

Do not deploy the T+3 threshold.

The next hypothesis should preserve temporal confirmation but reduce chase
dependence.

Candidate direction:

- earlier evidence accumulation;
- anti-chase cap;
- relative strength / structure / flow confirmation;
- remaining-edge estimate from the delayed entry itself.

Any redesigned rule is a new research hypothesis and requires fresh prospective
validation before production.

## Frozen artifact hashes

wd5h4d_delayed_entry_replay.csv
SHA256:
30484571e15669a712cba0fe2f7636128b70bf7207867c1886e98865a59b6802

wd5h4d_delayed_entry_results.json
SHA256:
dadf5bb3bb1797f462a3c151db3c2640522b06eff63b5b767502b61b5fc69a86

wd5h4d_delayed_entry_agg_cache.jsonl
SHA256:
92849527560d8affbf4d8843fb8c75030f7b6501e7b16b3ad334d4692c7a8d54
