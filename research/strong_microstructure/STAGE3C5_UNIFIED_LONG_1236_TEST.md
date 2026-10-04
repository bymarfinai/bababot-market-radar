# Stage 3C.5 — Unified LONG Full-Universe Test

## Frozen scope

- LONG universe: **1,236**
- target: **245** trades satisfying BOTH `META_WIN` and historical MFE >= 1.00%
- non-target: **991**
- weak META_WIN with MFE <1% remain non-targets

## Outcome-blind routing

The unified test cannot route trades using eventual WIN/LOSS labels.

A T0 archetype router was therefore trained on Discovery anatomy labels only and then applied to all 1,236 LONG trades.

Router inputs:
- gate flow family
- selected taker share
- 1m side return
- flow support
- micro acceleration 1m vs 3m
- coin-minus-market 30m
- OI change 30m
- volume ratio vs previous 10m

Logistic router, C=0.1:
- Validation AUC: **0.985**, accuracy **95.4%**
- sealed Reserve AUC: **0.990**, accuracy **94.5%**

No eventual WIN/LOSS label is used at inference.

## Unified policy

### Counterflow route

Use the frozen Stage 3C.2 four-rule failure veto. Select unless all four veto rules fire.

### Flow-Aligned route

Require a causal unresolved T+3 snapshot and:

`confirm_side_return_pct >= 0.158514%`

No threshold is re-tuned in Stage 3C.5.

## Full 1,236 result

- selected: **345 / 1,236 = 27.9%**
- strong WIN captured: **114 / 245 = 46.5% recall**
- false positives: **231**
- precision: **114 / 345 = 33.0%**
- baseline target rate: **245 / 1,236 = 19.8%**
- precision enrichment: **1.67x**

Selected composition:
- 114 strong WIN
- 78 weak META_WIN
- 153 META_LOSS

Lane contribution:
- Counterflow: 157 selected, 46 strong WIN captured, precision **29.3%**
- Flow-Aligned: 188 selected, 68 strong WIN captured, precision **36.2%**

## Chronological stability

Discovery:
- 74/162 captured = **45.7% recall**
- 207 selected
- precision **35.7%**
- lift vs split baseline **1.64x**

Validation:
- 24/45 captured = **53.3% recall**
- 77 selected
- precision **31.2%**
- lift **1.71x**

Sealed Reserve:
- 16/38 captured = **42.1% recall**
- 61 selected
- precision **26.2%**
- lift **1.71x**

## Improvement versus Stage 3B Reserve

Stage 3B ~80%-validation-recall operating point:
- selected **165**
- captured **28/38**
- false positives **137**
- precision **17.0%**

Stage 3C.5 unified:
- selected **61**
- captured **16/38**
- false positives **45**
- precision **26.2%**

Changes:
- selected trades: **-104**
- false positives: **-92**
- precision: **+9.3 percentage points**
- captured strong WIN: **-12**

Interpretation: Stage 3C.5 is materially more selective and cleaner than Stage 3B, but recall remains too low for the final LONG detector.

## Economics integrity

Historical original-entry reference economics for the 345 selected trades:
- full historical PnL: **+$61.91**
- average original-entry return/trade: **+0.0359%**

Sealed Reserve:
- historical PnL reference: **-$4.09**
- average return/trade: **-0.0134%**

These are **not execution-realistic Flow-Aligned delayed-entry economics**. Stage 3C.4 showed exact delayed-entry realized profitability remains inconclusive because exact historical intraminute exit fills are unavailable.

Therefore Stage 3C.5 must not be called a profitable strategy.

## Verdict

**PARTIAL PASS.**

The architecture improves precision and false-positive burden substantially across the full frozen 1,236 LONG universe, including sealed Reserve, but only captures about half of the 245 strong winners.

The next optimization target is therefore **recall recovery without surrendering the precision gain**.
