# WD-5A VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` PostgreSQL + frozen WD-4 mapping.  
Authority: research only.  
Production trading rule changes: none.

## Result

WD-5A successfully reconstructed a complete pre-entry supervised dataset for **849 / 849** strict wrong-direction trades.

### Target distribution — strict primary target

| Resolution target | Trades |
|---|---:|
| OPPOSITE_FROM_ENTRY_WIN | **435** |
| NO_TRADE_TARGET | **386** |
| FLIP_1M_WIN | 14 |
| FLIP_3M_WIN | 14 |
| **Total** | **849** |

### Feature dataset

- rows: **849**
- raw causal features: **121**
- numeric features: 107
- categorical features: 14
- features with missing values: **0**
- constant features: 10
- model-ready nonconstant features: **111**

Model-ready feature-family counts:

| Family | Features |
|---|---:|
| Stage11C gate / evidence | 38 |
| Market context | 26 |
| Direction scores/components | 17 |
| Movement/signal | 15 |
| Decision metadata | 11 |
| Pre-decision processing latency | 3 |
| Other causal | 1 |
| **Total** | **111** |

## Causality audit

All 849 rows pass.

```text
violation_counts = {}
causal_pass = true
```

The decision cutoff is Stage11C's final causal ENTER check, not the later fill.

Post-gate facts were explicitly excluded:

- order-created timestamp: post-decision in 849/849
- position-opened timestamp: post-decision in 849/849
- all fill-derived latency features

This is stricter than the earlier WD-2 feature audit and prevents WD-5B from learning execution timing that could not be known when choosing REVERSE vs NO TRADE.

## Important correction from earlier research code

WD-2's legacy helper assumed `decision_context_confirmations` and `decision_context_conflicts` were lists. In the actual signal snapshot they are numeric counts.

WD-5A reconstructs these directly from the raw snapshot, so those causal fields are preserved correctly.

## Frozen artefacts

### CSV

`/opt/core-app/data/wd5a_causal_entry_features.csv`

- size: 907,273 bytes
- SHA256: `ce7782a71a2dbe51007afe244e1a37edfe903a5ca355baa8a83dd230d77f9744`

### JSONL

`/opt/core-app/data/wd5a_causal_entry_features.jsonl`

- size: 3,998,207 bytes
- SHA256: `d97940a91bc39553b7f643698bd8c5adadea90d0ccf5ed38e98a3f57b063293a`

### Feature manifest

`/opt/core-app/data/wd5a_feature_manifest.json`

- size: 32,938 bytes
- SHA256: `56613d3077ec116cdf13be83e01a362e9bd7302865e0b0997bf90eaf176274b7`

## WD-5B handoff

WD-5A does not claim any predictive separation yet.

WD-5B should now answer:

> Using only these 111 pre-entry causal features, how accurately and robustly can we distinguish `OPPOSITE_FROM_ENTRY_WIN` from `NO_TRADE_TARGET`?

The 28 early-flip cases should be treated as secondary/small classes rather than forcing a four-class model immediately.

The primary WD-5B comparison should therefore begin with the 821 large-class trades:

- 435 OPPOSITE_FROM_ENTRY_WIN
- 386 NO_TRADE_TARGET

and only after establishing robust separation should the 14 + 14 flip cases be layered back in.
