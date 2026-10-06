# FTL-1 — Failure-to-Launch Timing Search, 45s to 120s

Status: **DISCOVERY PASS / PRODUCTION HOLD**

Date: 2026-10-06

## Objective

Find the earliest causal point after an original LONG signal where a future **MFE < +0.50%** trade can be isolated with high precision while enough opposite-side downside remains to make a SHORT economically useful.

This stage explicitly tests the trade-off:

- too early -> false SHORTs / winner contamination;
- too late -> classification precision improves but the remaining downside edge is already spent.

## Frozen universe

- resolved LONG universe: **1,236**
- Binance archived aggTrades raw-path coverage: **1,235 / 1,236**
- one raw-path-unavailable Unicode-symbol RIGHT_THEN_FAILURE trade excluded transparently
- economic replay:
  - $500 notional
  - 0.05% fee per side
  - 2 bps slippage per side
  - SHORT SL 0.50%
  - TP grid 0.30% to 0.80%
  - fallback at the original historical close

Target:
- final historical MFE < +0.50%

Strong-winner contamination:
- final historical MFE >= +1.00%

## Causal checkpoints

Raw aggTrades were sampled at:

- 45s
- 60s
- 75s
- 90s
- 105s
- 120s

At each checkpoint the replay derived only information observable by that point:

- current side return from original market entry;
- running MFE;
- running MAE;
- last-30s price slope;
- last-30s LONG-side buy-taker quantity share.

SHORT execution used the **first aggregate trade after the checkpoint**.

## Chronological split

Raw-covered 1,235 trades were split 60/20/20 chronologically:

- TRAIN: 741 trades, 2026-09-29 05:30 UTC -> 2026-09-30 12:40 UTC
- VALIDATION: 247 trades, 2026-09-30 12:40 UTC -> 2026-09-30 20:05 UTC
- RESERVE: 247 trades, 2026-09-30 20:05 UTC -> 2026-10-01 03:40 UTC

Rule thresholds were derived from TRAIN only.

## Timing results

### 45 seconds

Best classification rule:

- running MFE <= 0.00%
- 30s slope <= 0.00%
- 30s buy-taker share <= 35.62%

Classification:
- TRAIN: 67 fires, 70.15% target precision, 17.91% strong contamination
- VALIDATION: 16 fires, **100% target precision**, 0% strong contamination
- RESERVE: 19 fires, **100% target precision**, 0% strong contamination

Median firing state:
- side return: -0.179%
- running MFE: about 0%
- buy-taker share: 13.8%

Economics remain weak full-history:
- best tested full result: TP0.4 -> **-$30.59**
- TP0.8 -> **-$31.40**

Recent slices are only marginally positive:
- VALIDATION TP0.8: +$0.40
- RESERVE TP0.5: +$4.48

Interpretation:
45s identifies an ultra-weak flow subset in recent data, but TRAIN winner contamination is still too large.

### 60 seconds

Best classification rule:

- side return <= -0.2387%
- running MFE <= +0.0639%
- 30s slope <= +0.0176%

Classification:
- TRAIN precision: 80.39%
- VALIDATION precision: 93.33%
- RESERVE precision: 93.33%
- VALIDATION/RESERVE strong contamination: 0%

However this rule fires after the price is already materially adverse.

Median firing side return:
- **-0.375%**

Economics are poor:
- full TP0.5: **-$56.44**
- VALIDATION TP0.5: -$12.17
- RESERVE TP0.5: -$9.65

Interpretation:
**high label precision does not imply tradable SHORT edge.**
At 60s this particular rule is detecting failure by waiting for too much of the dump to have already happened.

### 75 seconds — key finding

Best classification rule is unexpectedly simple:

- running MFE <= **+0.08354%**
- 30s buy-taker share <= **23.06%**

No adverse-price threshold is required.

Classification:
- TRAIN: 68 fires, 70.59% target precision
- VALIDATION: 16 fires, **100% target precision**
- RESERVE: 27 fires, **92.59% target precision**
- RESERVE strong-MFE contamination: 7.41%

Median firing state:
- side return: **-0.131%**
- running MFE: +0.0166%
- buy-taker share: **9.50%**

This is materially different from the failed 60s pattern.

The 75s rule is not saying:
> price has already dumped enough.

It is saying:
> **the LONG has failed to create favorable excursion and aggressive buy flow has collapsed, while price is only modestly adverse.**

Class composition:

ALL 111:
- TRUE_WRONG_DIRECTION: 82
- STALL_NO_EDGE: 7
- RIGHT_THEN_FAILURE: 7
- RECOVERED_DRAWDOWN: 13
- CORRECT_RUNNER: 2

TRAIN 68:
- WD 45
- Stall 3
- RTF 7
- Recovered 11
- Clean 2

VALIDATION 16:
- WD 14
- Stall 2
- **no winner contamination**

RESERVE 27:
- WD 23
- Stall 2
- Recovered 2
- no Clean / no RTF

Economic result:

Full-history:
- TP0.3: WR 63.06%, -$21.83
- TP0.4: WR 60.36%, **-$20.31**
- TP0.5: WR 58.56%, -$25.97
- TP0.7: WR 58.56%, -$20.15
- TP0.8: WR 57.66%, -$23.28

TRAIN remains negative:
- TP0.4: -$40.59
- TP0.7: -$37.54

VALIDATION:
- TP0.3: +$6.51, WR 75.00%
- TP0.4: +$7.82, WR 68.75%
- TP0.5: +$8.72
- TP0.7: +$11.55
- TP0.8: **+$12.99**, PF 3.92

RESERVE:
- TP0.3: +$9.39, WR 77.78%
- TP0.4: **+$12.46**, WR 77.78%, PF 2.61
- TP0.5: +$6.88
- TP0.8: +$5.83

Combined VALIDATION + RESERVE, 43 fires:
- TP0.3: **+$15.90**, combined WR 76.74%
- TP0.4: **+$20.28**, combined WR 74.42%
- TP0.5: **+$15.60**, combined WR 72.09%
- TP0.8: **+$18.82**, combined WR 72.09%

This is the first causal FTL subset in the 1,236-LONG universe that shows a coherent positive SHORT result in both later chronological slices.

### 90 seconds and later

The classification remains reasonably precise, but economic performance collapses.

90s best rule:
- VALIDATION precision 87.50%
- RESERVE precision 88.46%
- full TP0.3 PnL: -$141.05
- reserve TP0.6: -$7.07

105s:
- VALIDATION precision 90.63%
- RESERVE precision 89.13%
- full best tested result still around -$138 to -$142
- reserve remains negative

120s:
- VALIDATION precision 93.33%
- RESERVE precision 91.67%
- full best tested result around -$55.90
- reserve remains negative

Therefore waiting longer does **not** monotonically improve SHORT economics.

## Core finding

FTL-1 resolves the timing paradox:

1. **45s:** flow weakness can already be seen, but early historical contamination is too high.
2. **60s:** precision looks excellent, but the rule relies on a large adverse price move; the SHORT is late.
3. **75s:** the best rule detects **flow failure without requiring a large completed dump**.
4. **90s+:** the remaining opposite-side economic opportunity deteriorates again.

The best candidate zone is therefore:

> **~75 seconds after the original LONG signal**

with the causal signature:

> **running MFE fails to exceed about +0.08% AND recent LONG buy-taker participation collapses below about 23%.**

This is a different concept from SC-1 adverse-distance persistence.

## Regime caveat

The 75s rule is **not full-history profitable**:
- full 111-trade subset remains about -$20 at the best tested TP settings.

Its profitability is concentrated in VALIDATION and RESERVE.

Metadata audit found no explicit engine-version difference across the three chronological slices:
- paper_trading_version = stage13-v2-event-driven throughout
- stage11c_version = stage11c-v2-evidence-families throughout

Therefore the TRAIN-vs-later divergence cannot currently be attributed to an explicit recorded version change.

Possible causes include:
- market/cohort regime;
- unrecorded runtime/config differences;
- symbol-composition shift;
- a real temporal change in the signal population.

These must be resolved before production promotion.

## FTL-1 verdict

**Discovery: PASS**

A causal, economically interesting pattern exists.

**Production: HOLD**

Do not deploy yet because full-history economics remain negative and the positive result is concentrated in later chronological slices.

## Recommended next stage

FTL-2 should not tune TP first.

It should explain and validate the 75s regime stability:

1. compare TRAIN vs VALIDATION/RESERVE symbol composition and volatility regime;
2. compare the 75s rule's false positives in TRAIN vs later slices;
3. identify why TRAIN contains 13 genuine winners while later slices contain almost none;
4. freeze the 75s rule before looking at any newer forward sample;
5. test the frozen rule on post-2026-10-01 data / paper-forward observations.

The key research object is now:

> **75-second flow-failure SHORT gate**

not generic wrong-direction reversal.
