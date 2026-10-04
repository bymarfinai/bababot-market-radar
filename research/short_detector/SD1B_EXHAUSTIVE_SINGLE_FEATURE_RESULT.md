# SD-1B — Exhaustive Single-Feature T0 Scan

Status: **FAIL as a strong single-feature detector / PASS as diagnostic research**

## Frozen contract

Universe:
- **655 resolved SHORT**
- **99 strong WIN**
- **556 non-target**
- chronological D/V/R = **393 / 131 / 131**

Strong WIN:
`META_WIN AND historical_max_mfe_pct >= 1.00%`

Feature hygiene:
- 231 raw `f_*` fields
- 7 time / infrastructure-latency fields excluded
- **224 modeled T0 features**
- 210 numeric
- 14 categorical

No LONG threshold or feature direction was copied.

## Search scale

The exhaustive scan evaluated:

> **9,191,630 candidate single-feature rules**

Numeric families:
- <= threshold
- >= threshold
- every exact contiguous Discovery-value band

Categorical:
- states / state subsets when feasible

Per-feature rule selection used only Discovery + Validation.
Reserve was evaluated only after the rule for that feature had been frozen.

- 198 features produced an evaluable frozen rule
- 26 were constant / unevaluable under the preregistered support requirements
- STRONG gate: phi >= 0.50 in Discovery, Validation, and Reserve
- strong rules found: **0**

## Discovery-only overfit warning

The strongest Discovery-only pocket was:

`f_f_market_selected_ret_15m between +0.504506 and +0.521089`

Discovery:
- selected: **11**
- strong WIN: **11 / 11**
- precision: **100%**
- recall: **18.64%**
- phi: **0.4037**
- historical selected PnL: **+$25.69**

But the exact frozen band selected:
- Validation: **0 trades**
- Reserve: **0 trades**

Therefore this is a narrow Discovery sweet spot, not a reusable SHORT detector.

## Best Discovery + Validation frozen rule

Feature:

`f_micro_decay_5_vs_prev5 <= -1.759177`

| Split | Selected | Strong WIN | Precision | Recall | Phi | Historical PnL |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 27 | 11 | 40.74% | 18.64% | **0.1956** | +$11.74 |
| Validation | 10 | 5 | 50.00% | 18.52% | **0.2089** | -$12.27 |
| Reserve | 5 | 1 | 20.00% | 7.69% | **0.0671** | -$7.55 |
| Full 655 | 42 | 17 | 40.48% | 17.17% | 0.1853 | **-$8.09** |

The D/V signal is real enough to be interesting, but it collapses on Reserve and is not economically attractive as a standalone selector.

## Top D+V frozen rules

| Rank | Feature | Frozen rule | D phi | V phi | R phi | Full selected | Strong WIN | Precision | Recall | PnL |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | f_micro_decay_5_vs_prev5 | <= -1.7592 | .196 | .209 | .067 | 42 | 17 | 40.5% | 17.2% | -$8.09 |
| 2 | f_f_coin_residual_5m_vs_btc | 1.9406–3.5120 | .207 | .194 | -.051 | 30 | 13 | 43.3% | 13.1% | -$20.21 |
| 3 | f_context_raw_oi_change_pct | -0.0061–0.0114 | .188 | .194 | .049 | 22 | 10 | 45.5% | 10.1% | -$2.68 |
| 4 | f_f_market_selected_ret_30m | -0.1956–-0.1331 | .204 | .185 | .049 | 33 | 14 | 42.4% | 14.1% | +$4.59 |
| 5 | f_micro_side_ret_5m | >= 1.8295 | .187 | .185 | -.066 | 45 | 16 | 35.6% | 16.2% | -$38.22 |
| 6 | f_new_oi_per_price | -0.0158–0.0062 | .177 | .249 | .129 | 29 | 13 | 44.8% | 13.1% | +$3.09 |
| 7 | f_new_volume_over_range | 1.0171–1.0610 | .177 | .194 | .067 | 25 | 11 | 44.0% | 11.1% | +$26.00 |
| 8 | f_ret_5m_pct_raw | <= -1.8340 | .169 | .185 | -.079 | 50 | 16 | 32.0% | 16.2% | -$60.09 |
| 9 | f_ret_5m_pct_for_selected | >= 1.8340 | .169 | .185 | -.079 | 50 | 16 | 32.0% | 16.2% | -$60.09 |
| 10 | f_score_component_delta_activity | 17.5481–18.1560 | .174 | .159 | .000 | 18 | 9 | 50.0% | 9.1% | +$27.91 |

## Best already-frozen cross-split consistency

After all per-feature rules were frozen, the strongest minimum phi across all three splits was:

`f_f_coin_minus_market_15m >= 2.527486`

Equivalent behavior also appears in `f_f_relative_overextension_15m`.

- Discovery phi: **0.1328**
- Validation phi: **0.1307**
- Reserve phi: **0.1715**
- all-split floor: **0.1307**
- full selected: **41**
- strong WIN captured: **14**
- precision: **34.15%**
- recall: **14.14%**
- historical PnL: **-$56.08**

This is more stable than the top D/V rule, but far too weak to qualify as a standalone detector.

Across all already-frozen feature rules:
- **17** had D/V stability score >= 0.15
- **96** had D/V stability score >= 0.10
- only **13** retained an all-split phi floor >= 0.10
- **0** retained an all-split floor >= 0.15
- **0** reached the preregistered strong gate of 0.50

## SHORT vs LONG Stage 3C.1

LONG reference:
- best Discovery-only single feature: approximately **0.214**
- best D+V stability ceiling: approximately **0.146**
- no strong stable rule

SHORT:
- best Discovery-only pocket: **0.404**
- best D+V stability: **0.196**
- no strong stable rule
- Reserve collapses the apparent leading patterns

Interpretation:

> SHORT shows more T0 structure than LONG in Discovery / Validation, but that structure is not stable enough to support a one-dimensional detector.

The correct conclusion is **not** that SHORT has no T0 edge.

The conclusion is:

> aggregate SHORT winner behavior is likely conditional / multi-regime, so a single global threshold is insufficient.

This is consistent with SD-1A, where **76 / 99 strong SHORT winners (76.77%)** came from the RECOVERED_DRAWDOWN anatomy rather than a single clean continuation pattern.

## Decision

**SD-1B = FAIL_NO_STRONG_SINGLE_FEATURE.**

Do not deploy or promote any single T0 rule.

The next playbook stage is **SD-1C — SHORT Winner Anatomy**:
- analyze the 99 strong winners only;
- identify whether multiple winner archetypes exist;
- test whether feature signs cancel across archetypes;
- establish SHORT-specific clusters before testing multi-feature combinations.

Reserve remains untouched for any future threshold tuning.