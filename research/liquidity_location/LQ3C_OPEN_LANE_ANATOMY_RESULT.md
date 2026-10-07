# LQ-3C — Open-Lane / Outside-Fresh-Supply Anatomy

Status: **PASS — HIGH-COVERAGE FOCUS LANE FOUND**

Version: `lq3c-open-lane-anatomy-v1`

## Objective

LQ-3A and LQ-3B focused on the 102 LONGs that entered inside a FRESH 15m supply zone.

LQ-3C moves to the much larger complement:

> LONG trades that **did not** enter inside FRESH 15m supply.

The research question is:

> Is there a structural location with materially better continuation / runner probability and enough coverage to become a useful positive admission context?

No production authority is changed.

## Frozen universe

- total resolved LONG: 1,236
- inside FRESH 15m supply: 102
- LQ-3C outside-fresh-supply universe: **1,134**

Chronological split:

- TRAIN: **683**
- VALIDATION: **225**
- RESERVE: **226**

Baseline of this 1,134-trade universe:

| Split | Median MFE | MFE <0.5% | MFE >=1% | Realized WR |
|---|---:|---:|---:|---:|
| TRAIN | 0.531% | 47.00% | 29.28% | 27.53% |
| VALIDATION | 0.434% | 52.89% | 24.44% | 21.33% |
| RESERVE | 0.370% | 53.10% | 23.45% | 21.68% |
| ALL | **0.506%** | **49.38%** | **27.16%** | **25.13%** |

## Primary focus rule

Coarse TRAIN discovery found the most useful high-coverage structure around:

> **nearest demand >=3.0% below entry**
>
> AND
>
> **price is not inside active 5m or 15m supply**

This is named:

> **OPEN_LANE**

Interpretation:

- price has already moved materially away from prior demand/support;
- it is not currently trapped inside a local 5m/15m supply zone;
- therefore the trade is structurally closer to a continuation state than a base/compression state.

This is not the same as:

> "far from demand is always good."

It is specific to this momentum-oriented LONG detector and must be read jointly with local supply clearance.

## OPEN_LANE result

### All history

| Metric | OPEN_LANE | Complement |
|---|---:|---:|
| Trades | **209** | 925 |
| Median MFE | **0.683%** | 0.405% |
| MFE <0.5% | **33.49%** | 52.97% |
| MFE >=1% | **38.76%** | 24.54% |
| MFE >=2% | **12.92%** | 7.24% |
| Realized WR | **30.14%** | 24.00% |
| Historical PnL | -$126.42 | -$988.85 |

OPEN_LANE therefore improves:

- median excursion by roughly **69%**
- >=1% runner rate by **+14.22 percentage points**
- low-MFE rate by **-19.48 points**
- realized win rate by **+6.14 points**

This is the first LQ positive location rule with both:

- meaningful effect size;
- meaningful coverage.

## Chronological stability

### TRAIN

- n = **123**
- median MFE = **0.724%**
- MFE <0.5% = **29.27%**
- MFE >=1% = **42.28%**
- realized WR = **31.71%**

Versus TRAIN baseline:

- >=1% runner: **+13.00 pp**
- low-MFE: **-17.73 pp**
- realized WR: **+4.18 pp**

### VALIDATION

- n = **53**
- median MFE = **0.558%**
- MFE <0.5% = **41.51%**
- MFE >=1% = **28.30%**
- realized WR = **24.53%**

Versus Validation baseline:

- >=1% runner: **+3.86 pp**
- low-MFE: **-11.38 pp**
- realized WR: **+3.20 pp**

### RESERVE

- n = **33**
- median MFE = **0.815%**
- MFE <0.5% = **36.36%**
- MFE >=1% = **42.42%**
- realized WR = **33.33%**

Versus Reserve baseline:

- >=1% runner: **+18.97 pp**
- low-MFE: **-16.74 pp**
- realized WR: **+11.65 pp**

The direction of effect is positive in all three chronological partitions.

This is substantially stronger transport evidence than LQ-3B's breakout-retest route.

## Secondary precision tier

A stricter variant was also tested:

> nearest demand >=3%
>
> AND
>
> 5m supply clearance >=0.2%
>
> AND
>
> not inside 15m supply

Named:

> **OPEN_LANE_STRONG**

All-history:

- n = **103**
- median MFE = **0.688%**
- MFE <0.5% = **29.13%**
- MFE >=1% = **40.78%**
- realized WR = **32.04%**

This is stronger than the broad OPEN_LANE on excursion quality, but Reserve has only **14 trades**.

Therefore it remains a secondary precision tier, not the primary frozen rule.

## Important counterintuitive finding: near demand is not the winner area

For this momentum LONG universe, entering close to old demand is **not** the high-quality location.

### Nearest demand <1.5%

All-history:

- n = **355**
- median MFE = **0.337%**
- MFE <0.5% = **57.46%**
- MFE >=1% = **22.25%**
- realized WR = **23.66%**

Reserve:

- n = 92
- median MFE = **0.297%**
- low-MFE = **67.39%**
- >=1% runner = **14.13%**
- realized WR = **15.22%**

### Nearest demand <2.0%

All-history:

- n = **568**
- median MFE = **0.362%**
- MFE <0.5% = **55.63%**
- MFE >=1% = **22.18%**
- realized WR = **23.94%**

This area has materially lower expansion quality than the complement.

Therefore:

> **near demand should not be promoted as a LONG focus area for this detector.**

For this system, being near old demand often means:

- price has not yet separated from its prior base;
- local expansion is weak / unresolved;
- the momentum thesis has less demonstrated continuation.

This is a detector-specific result, not a general trading claim.

## 2D structural picture

The clearest broad pattern is:

### Demand 1–2% away + clear 5m/15m supply

- n = **286**
- median MFE = 0.390%
- MFE >=1% = 21.33%
- low-MFE = 56.29%
- realized WR = 22.03%

### Demand 2–3% away + clear 5m/15m supply

- n = **227**
- median MFE = 0.470%
- MFE >=1% = 26.87%
- low-MFE = 50.22%
- realized WR = 25.11%

### Demand >=3% away + clear 5m/15m supply

- n = **209**
- median MFE = **0.683%**
- MFE >=1% = **38.76%**
- low-MFE = **33.49%**
- realized WR = **30.14%**

This forms the first clear location gradient found in the LQ research:

> as the LONG trade moves farther away from prior demand **while staying clear of local 5m/15m supply**, continuation quality improves materially.

## Area classification after LQ-3C

### FOCUS

```
OPEN_LANE
nearest demand >=3%
AND not inside 5m supply
AND not inside 15m supply
```

This is the best broad positive structural context found so far.

### FOCUS — stronger but lower coverage

```
OPEN_LANE_STRONG
nearest demand >=3%
AND 5m supply clearance >=0.2%
AND not inside 15m supply
```

Use as research priority / scoring boost, not as a hard requirement.

### DEPRIORITIZE

```
nearest demand <1.5%
```

or more broadly:

```
nearest demand <2.0%
```

These zones have consistently weaker runner probability and higher low-MFE incidence.

They are **not hard BLOCK zones** yet because TRAIN realized WR does not uniformly collapse.

### WAIT / REQUIRE PROOF

From LQ-3A / LQ-3B:

```
inside FRESH 15m supply
```

Do not treat this as normal entry context.

### REJECTED

From LQ-3A:

```
inside FRESH 15m supply
then T+2/T+3 price falls below lower boundary
```

This remains the strongest negative state.

## Why historical PnL is still negative

OPEN_LANE improves opportunity quality, but historical realized PnL remains negative.

That is not a contradiction.

OPEN_LANE has:

- larger MFE,
- more >=1% runners,
- fewer low-MFE failures,
- better realized WR,

but the existing historical lifecycle still gives back too much excursion and closes many trades poorly.

This means:

> **location is fixing admission quality, not exit quality.**

Supply/demand should therefore not be expected to replace the Profit Protector.

Instead:

```
direction signal
    -> structural location
    -> entry routing
    -> profit protection / exit
```

are separate layers.

## LQ-3C verdict

LQ-3C supports three practical conclusions.

1. **Yes, there is now a broad area worth focusing on.**

   OPEN_LANE has materially higher continuation / runner probability across TRAIN, VALIDATION, and RESERVE.

2. **No, demand itself is not the good entry zone.**

   For this momentum system, entries close to old demand are generally lower-expansion contexts.

3. **Location alone does not solve PnL.**

   It improves the quality of the opportunity set, but the lifecycle / profit-capture layer still needs to convert MFE into realized PnL.

## Next stage

Recommended next stage:

> **LQ-4 — Structural Location Shadow Router**

Add research-only location states to each LONG candidate:

- `FOCUS_OPEN_LANE`
- `FOCUS_OPEN_LANE_STRONG`
- `NORMAL`
- `DEPRIORITIZE_NEAR_DEMAND`
- `WAIT_FRESH_15M_SUPPLY`

Then forward-track:

- admission count
- MFE
- realized PnL
- runner rate
- rejection / acceptance transitions

No order authority should change until forward validation confirms the frozen LQ-3C effect.