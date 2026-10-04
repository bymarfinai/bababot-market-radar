# Stage 3C.3 — Flow-Aligned LONG Temporal Confirmation

## Scope

- LONG only.
- Flow-Aligned lane only: **180 strong WIN vs 602 Flow-Aligned Failure**.
- Strong WIN remains `META_WIN AND historical MFE >= 1.00%`.
- Counterflow 4-rule veto from Stage 3C.2 remains frozen and was **not retuned**.

## Causal censoring

A row is eligible at T+1 / T+2 / T+3 only when its primary outcome had **not** resolved before that temporal snapshot:

`primary_label_end_ms > temporal_target_ms`

Primary predictor search excludes `confirm_mfe_pct` and `confirm_mae_pct` so the model does not become tautological with the MFE>=1% research target.

Eligible lane counts:

- T+1: **717** total, **169** strong WIN
- T+2: **632** total, **159** strong WIN
- T+3: **545** total, **143** strong WIN

## Horizon result

### T+1

Best 4-feature model:
- selected VWAP extension
- volume climax/fade
- taker acceleration 1m
- micro side return 1m

AUC Discovery / Validation / Reserve: **0.637 / 0.647 / 0.682**.

Result: still weak-to-moderate.

### T+2

Best 4-feature model:
- selected VWAP extension
- micro side return 1m
- micro side return 3m
- delta VWAP extension

AUC Discovery / Validation / Reserve: **0.725 / 0.725 / 0.714**.

Result: usable predictive separation begins to appear.

### T+3

Best Discovery+Validation-selected 4-feature model:
- `confirm_side_return_pct`
- selected VWAP extension
- close-z
- delta coin-minus-market 15m

AUC Discovery / Validation / Reserve: **0.754 / 0.831 / 0.722**.
Reserve score-target correlation: **r ≈ 0.319**.

Result: T+3 materially improves Flow-Aligned separation, but it is not a strong-correlation detector.

## Simpler T+3 observation

`confirm_side_return_pct` alone has AUC Discovery / Validation / Reserve **0.720 / 0.794 / 0.756**.

A Validation-tuned operating point around 60% target recall uses threshold ≈ **+0.1585%**.

Reserve:
- selected **26/122**
- captured **11/24** strong WINs
- recall **45.8%**
- precision **42.3%**
- false positives **15**
- historical original-entry PnL **+$18.74**
- historical original-entry average return/trade **+0.144%**

These economics are from the original frozen entry, **not reconstructed delayed T+3 entry economics**.

The simple feature outperforms the selected composite on sealed Reserve, but that simplification became obvious only after Reserve inspection. It therefore requires a fresh validation cohort before promotion.

## Verdict

**Stage 3C.3 = PARTIAL PASS, research-only.**

- T+1: insufficient.
- T+2: useful but moderate.
- T+3: clearly predictive.
- Temporal confirmation explains part of the Flow-Aligned ambiguity.
- Higher-recall gates still admit too many failures.
- Counterflow candidate remains frozen.
- No production entry/veto authority changes.
