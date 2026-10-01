# WD-5F VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`, frozen WD-4/WD-5D/WD-5E cohorts plus causal Binance benchmark and OI history.  
Authority: research only.  
Production rule changes: none.

## Executive conclusion

WD-5F finds a **one-sided conditional reversal candidate**.

Formal research status:

`ONE_SIDED_REVERSAL_CANDIDATE_FOUND`

Production authority:

`NONE`

The safe action semantics are:

```text
OVERHEATED
    |
    +-- reversal confidence high -> REVERSE
    |
    +-- otherwise -> NO TRADE
```

The detector does **not** attempt to force a symmetric classification of every case.

## Conditional cohort

Frozen WD-5D overheat threshold:

`5.481925222153388`

Applied to 821 WD-4 REVERSE / NO TRADE targets:

| Cohort | N |
|---|---:|
| All primary WD-4 targets | 821 |
| Overheated conditional cohort | **319** |
| REVERSE target | **179** |
| NO TRADE target | **140** |

Conditional REVERSE prevalence:

**56.11%**

This is higher than the ~53% baseline in the full primary cohort, but overheat alone is not enough to make a reversal decision.

## Selected feature family

Validation selects the **market-relative** model.

Selected features:

1. coin beta to BTC over the recent 20 one-minute bars
2. coin minus market 5m return
3. market 5m dispersion
4. 30m relative overextension
5. coin minus market 30m return
6. ETH selected-side 5m return
7. market 15m dispersion
8. market selected-side 1m return
9. market selected-side 5m return
10. 15m relative overextension

This is the strongest architectural finding of WD-5F:

> reversal confirmation becomes more portable when the coin is evaluated relative to the surrounding market, not only from its own local momentum.

## Symmetric ranking performance

Selected market-relative model:

| Window | AUC |
|---|---:|
| Validation | **0.683** |
| Final test | **0.579** |
| Novel-symbol final subset | **0.566** |

The overall ranking is still not strong enough for a symmetric REVERSE / NO TRADE classifier.

However, novel-symbol AUC materially improves from WD-5E's 0.396 to 0.566.

## One-sided high-precision gate

The model is not used as a general binary classifier.

Validation selects a high-confidence REVERSE threshold subject to:

- REVERSE precision >= 80%
- at least 5 validation flags
- maximize REVERSE recall

Frozen threshold:

`0.5142449163777649`

### Validation

- flagged: 31 / 64
- REVERSE precision: **80.65%**
- REVERSE recall: **62.50%**
- false-reverse rate among NO TRADE: 25.0%
- default NO TRADE: 33 / 64

### Final chronological test

- flagged: 11 / 64
- correct REVERSE: 8
- false REVERSE: 3
- default NO TRADE: 53

Metrics:

- REVERSE precision: **72.73%**
- REVERSE recall: **19.05%**
- false-reverse rate among NO TRADE: **13.64%**

This is intentionally conservative: most cases are skipped rather than reversed.

## Novel-symbol check

Final-test subset:

- 29 trades
- symbols not seen during train/validation

At the frozen one-sided threshold:

- flagged: 7
- correct REVERSE: 5
- false REVERSE: 2
- REVERSE precision: **71.43%**
- REVERSE recall: **27.78%**
- false-reverse rate among NO TRADE: **18.18%**

This is a substantial improvement over WD-5E's novel-symbol reversal failure.

## Why one-sided evaluation is the right objective

The original WD-4 goal is:

> convert wrong-direction trades into WIN or NO TRADE.

Therefore:

- false negative REVERSE -> NO TRADE = foregone profit, but no bad entry
- false positive REVERSE on a NO TRADE target = dangerous new bad trade

The detector should optimize the second error, not symmetric classification accuracy.

This is why WD-5F defaults to NO TRADE.

## Alternative sensitivity

The full conditional feature model shows better broad chronological ranking consistency:

- validation AUC: 0.645
- test AUC: **0.655**
- novel-symbol AUC: **0.641**

At a validation 80% precision threshold:

- test REVERSE precision: **81.82%**
- test REVERSE recall: **21.43%**
- false-reverse rate: **9.09%**

However, this variant was not the validation-AUC winner and is therefore treated only as supportive sensitivity, not substituted after seeing test results.

This suggests that combining market-relative context with legacy + WD-5D features may become useful after prospective validation.

## OI result

OI acceleration / crowding adds information in some historical windows but is not stable enough alone.

Standalone OI model:

- validation AUC: 0.646
- test AUC: 0.389

Therefore OI dynamics are retained as research features but are **not** sufficient reversal confirmation.

## Flow / structure result

Standalone flow / structure model:

- validation AUC: 0.578
- test AUC: 0.488

Again, useful context but not a standalone reversal head.

## Nonlinear sensitivity

Shallow forest:

- validation AUC: 0.549
- test AUC: 0.509

The nonlinear model does not improve the conditional reversal problem.

## Formal research gate

The selected one-sided candidate meets the WD-5F research requirements:

- validation AUC >= 0.65: PASS
- test AUC >= 0.55: PASS
- novel-symbol AUC >= 0.55: PASS
- validation REVERSE precision >= 80%: PASS
- test REVERSE precision >= 70%: PASS
- test REVERSE recall >= 15%: PASS
- novel-symbol REVERSE precision >= 65%: PASS
- novel-symbol flagged N >= 3: PASS

Formal status:

`ONE_SIDED_REVERSAL_CANDIDATE_FOUND`

## Critical caveat

The one-sided objective was formalized after the initial symmetric WD-5F test results had already been inspected.

Therefore this is **not a pristine promotion result**.

It is valid as a research discovery and architecture candidate, but production promotion requires fresh prospective data.

## Architectural result

The emerging detector now looks like:

```text
CURRENT DIRECTION
       |
       v
CONTINUATION HEALTH
       |
       +-- HEALTHY
       |      -> CONTINUE candidate
       |
       +-- OVERHEATED
              |
              v
     CONDITIONAL REVERSAL CONFIRMATION
              |
              +-- high-confidence market-relative reversal
              |      -> REVERSE candidate
              |
              +-- everything else
                     -> NO TRADE
```

This is much safer than:

`OVERHEATED -> automatically reverse`

## Frozen artifacts

### Benchmark cache

`/opt/core-app/data/wd5f_benchmark_1m_cache.json`

SHA256:

`b96d32608340a6a1b3e830b5ea4fa8d66af68a2a2c5d1a3d68f2ae1dff2c03b6`

### OI cache

`/opt/core-app/data/wd5f_oi_5m_cache.jsonl`

SHA256:

`5b0821fdfc0aa17f86aa1e7b8d15fc872ea10d0439fcd9d7d7488e34f91f526a`

### Feature dataset

`/opt/core-app/data/wd5f_conditional_reversal_features.csv`

SHA256:

`5b98aa3a5ad09dbd2e4ab320a08b9d6dcaec569bb1b5f4b6d788ef5c01889c3a`

### Full result

`/opt/core-app/data/wd5f_conditional_reversal_results.json`

SHA256:

`21461e9982b96db74915c23bbcbf5ed41183cc8f2bf34a7f96e0017987a2835c`

Focused WD-0 through WD-5F tests:

**63 / 63 PASS**

## Handoff

WD-5F is complete as a research stage.

The next sensible step is a historical end-to-end replay using the asymmetric policy:

1. healthy continuation -> preserve existing side
2. overheated -> apply one-sided reversal confirmation
3. high-confidence confirmation -> reverse
4. otherwise -> no trade
5. path expectation informs Stage12 protection

Because the one-sided objective revision consumed the current holdout, any promotion decision after replay must still require fresh prospective shadow validation.
