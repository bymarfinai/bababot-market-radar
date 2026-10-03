> **ARCHIVED / CLOSED / REJECTED TRACK** — retained for reproducibility. Do not continue tuning this 15s low-tail branch in the active research path.\n\n# PP-DECISION V3 — Low-Tail Stage B

Status: **COMPLETE — research only, no production authority**

## Objective

Stage A showed that the <80% low tail is overwhelmingly an intrapoll-excursion problem.

Stage B asks two follow-up questions using the existing frozen dataset:

1. **B1 — Pre-arm detector:** can a trade that will later become low-tail (<80% terminal observed peak / true MFE) be identified causally before the final MFE excursion?
2. **B2 — Exchange-side feasibility:** if protection is delegated to an exchange-side trailing mechanism, can the portfolio reach a materially tighter >=90% peak-capture distribution without killing future runners?

No new prospective data is required for this stage.

## Frozen baseline

- clean terminal trades: **1,196**
- mean terminal observed peak / true MFE: **86.33%**
- median: **90.17%**
- >=90% share: **50.42%**
- <80% share: **25.67%**

For B1, the ambiguous 80–90% group and >100% benchmark-mismatch group are excluded from the binary target.

B1 labels:

- LOW-TAIL: <80% = **307**
- GOOD: 90–100% = **534**
- total labeled = **841**

Chronological split is fixed at first 2/3 train, final 1/3 test.

## B1 — causal pre-arm detector

Features are evaluated only from information available at or before the checkpoint.

### Fixed checkpoints

A fixed checkpoint is included only if the final MFE excursion has not yet been discovered at that timestamp. The nearest observation must be within 30 seconds before the target checkpoint.

| Checkpoint | Covered | Low-tail | Good | Context late-test AUC | Path late-test AUC |
|---|---:|---:|---:|---:|---:|
| T+30s | 804 | 273 | 531 | **0.7105** | **0.6994** |
| T+60s | 755 | 237 | 518 | 0.5490 | 0.5507 |
| T+120s | 693 | 187 | 506 | 0.5979 | 0.5937 |

The only fixed checkpoint with material chronological separation is **T+30s**.

At T+30s, context model with a train false-positive cap of 10% produced on the late test cohort:

- AUC: **0.7105**
- low-tail recall: **25.32%**
- good-trade false-positive rate: **6.15%**
- precision: **62.50%**

At a 20% train false-positive cap:

- low-tail recall: **45.57%**
- good-trade false-positive rate: **16.41%**
- precision: **52.94%**

This is useful separation, but not strong enough to classify all low-tail trades.

### Pre-spike last-observation diagnostic

A separate diagnostic chooses the last causal observation immediately before final MFE discovery.

Its features are causal, but the checkpoint timing is selected retrospectively and therefore **cannot be used directly as a production trigger**.

Late-test results:

- context AUC: **0.7349**
- path-inclusive AUC: **0.8577**

At the path model's 10% train FPR threshold:

- late-test low-tail recall: **57.50%**
- late-test good false-positive rate: **11.28%**
- precision: **67.65%**

At the 20% threshold:

- low-tail recall: **77.50%**
- good false-positive rate: **20.00%**
- precision: **61.39%**

Interpretation:

> There is meaningful local path information immediately before the excursion, but the existing 15-second system does not know in advance which observation is "the last one before the spike."

So Stage B1 finds **signal, but not a complete timing solution**.

## B2 — conservative exchange-side trailing replay

B2 reconstructs fully post-entry closed 1-minute bars from the persisted fast snapshots.

Guardrails:

- the entry-straddling first minute is excluded because its OHLC contains pre-entry price action;
- only bars fully after entry and before close are used;
- 2 bps adverse exit slippage is applied;
- conservative mode never assumes favorable high/low ordering inside the same minute;
- optimistic same-bar mode is reported only as an upper feasibility bound;
- true MFE is an offline denominator only.

Bar coverage across the 1,196 trades:

- median full bars per trade: **14**
- P10: **2**
- P90: **69**

### Native price-callback trailing

Grid tested:

- activation ROI: 0.30%, 0.50%, 0.75%, 1.00%
- price callback: 0.10%, 0.20%, 0.30%, 0.50%

The best native configuration by >=90% share in conservative replay was:

**activation +1.00%, callback 0.10%**

Conservative result:

- >=90% capture share: **5.02%**
- <80% share: **85.70%**
- mean capture: **11.17%**
- median capture: **20.50%**
- triggered: **37.37%**
- among triggered trades, exit before final MFE discovery: **72.71%**

Even the optimistic same-bar bound reached only:

- >=90% share: **6.10%**
- <80% share: **81.77%**

This is far worse than the baseline terminal-peak visibility distribution.

This does **not** mean exchange execution is worse than observation. It means an always-on trailing exit fires on earlier local peaks and sacrifices later continuation before the final MFE.

### Ideal fractional-excursion trailing

To separate exchange callback mechanics from the conceptual runner problem, B2 also tested an idealized stop that retains a fixed fraction of peak excursion.

The best conservative grid result was:

**activation +0.50%, retain 95% of excursion**

Result:

- >=90% capture share: **24.16%**
- <80% share: **68.81%**
- mean capture: **35.65%**
- median capture: **55.92%**
- triggered: **80.69%**
- among triggered trades, exit before final MFE discovery: **68.19%**

Optimistic same-bar bound:

- >=90% share: **28.60%**
- <80% share: **64.30%**

Even a theoretical 95%-retention trail cannot solve the portfolio when applied universally.

## Why B2 fails

The failure is not primarily execution precision.

It is **runner destruction**.

A trade can make:

```text
local peak
→ retracement
→ trailing exit
→ later much higher peak
```

The trailing order successfully captures the local peak but permanently loses the later continuation.

This is exactly the runner problem identified earlier from a different angle.

## Stage B conclusion

Stage B produces two important results.

### 1. Low-tail is partially predictable early

T+30s has real chronological separation:

- late-test AUC ~**0.71**
- controlled-FPR precision ~**62.5%**
- but recall only ~**25%** at the stricter threshold.

Immediately before the spike, path information is much stronger (AUC **0.858**), showing that the missing piece is partly **timing**.

### 2. Universal exchange trailing is rejected

Always-on native trailing and even an idealized 95%-retention trail exit too many trades before final MFE.

Therefore:

> **The solution cannot be "put a tight trail on every armed trade."**

The next capture rule must be **selective and state-dependent**:

- identify high intrapoll-spike risk;
- protect those trades early;
- preserve continuation/runner candidates;
- avoid applying the same trail to every position.

## Stage C implication

Stage C should combine the Stage B evidence into a selective replay:

1. start with the causal T+30 risk signal;
2. add a stateful pre-spike path trigger rather than an oracle-timed checkpoint;
3. activate tight exchange-side protection only on sufficiently high low-tail risk;
4. give non-selected trades a runner-preservation path;
5. replay the combined rule chronologically over the full frozen cohort.

The target metrics remain distributional:

- increase >=90% share from **50.42%**;
- reduce <80% share from **25.67%**;
- improve P10/P25;
- do not achieve improvement by sacrificing later runners.

No production threshold or trading authority is changed by Stage B.

## Reproducibility

- replay script: `research/profit_protection_v3/archive/low_tail_15s/stage_b_low_tail_prearm_exchange.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_b_low_tail_prearm_exchange_1791021852690.json`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_b.py`
