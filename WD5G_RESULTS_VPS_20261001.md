# WD-5G VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`.  
Authority: research only.  
Production trading changes: none.

## Executive conclusion

Formal status:

`END_TO_END_POLICY_NOT_READY`

The full replay shows that the **Health / overheat filter is useful**, but the WD-5F reversal gate is **not portable to the full trade population**.

The key problem is now clear:

> The reversal detector can perform reasonably inside known TRUE_WRONG_DIRECTION cases, but it cannot reliably distinguish those cases from trades whose original direction was actually valid and whose later lifecycle failed.

That causes false reversals of RIGHT_THEN_FAILURE, CLEAN, and RECOVERED winners.

## Baseline

2,175 trades:

- net PnL: **-$2,338.65**
- WR: **23.31%**
- profit factor: **0.373**

## Health-only ablation

Policy:

- healthy -> KEEP
- overheated -> SKIP

Results:

- trades: 1,208
- skipped: 967
- net PnL: **-$1,234.58**
- WR: **25.50%**
- profit factor: **0.395**

Improvement versus baseline:

**+$1,104.07**

This shows the overheat signal is economically useful as a filtering concept.

However, it is too aggressive to be considered a final entry gate because it also removes many valuable runners and winners.

## WD-5G primary policy

Policy:

- healthy -> KEEP
- overheated + WD-5F confirmation -> REVERSE
- otherwise -> SKIP

Results:

- KEEP: 1,208
- REVERSE: 395
- SKIP: 572
- trade count: 1,603
- net PnL: **-$1,456.34**
- WR: **28.82%**
- profit factor: **0.447**

Versus baseline:

- PnL improvement: **+$882.31**
- WR improvement: **+5.51 percentage points**

But versus health-only:

**-$221.76**

Therefore the reversal head makes the full system worse than simply skipping overheated trades.

## Reverse execution result

395 reversed trades:

- wins: 154
- losses: 241
- WR: **38.99%**
- net PnL: **-$221.76**

Exit outcomes:

- TP +0.5%: 144
- SL -0.5%: 233
- horizon final: 18

So the full-population reversal action is economically negative.

## Why the reversal gate fails end-to-end

Breakdown of the 395 reversed trades by original WD-1 outcome:

- TRUE_WRONG_DIRECTION: 130
- RIGHT_THEN_FAILURE: **169**
- RECOVERED_DRAWDOWN: 46
- CORRECT_RUNNER: 37
- STALL_NO_EDGE: 13

The detector is reversing more RIGHT_THEN_FAILURE trades than TRUE_WRONG_DIRECTION trades.

That distinction matters:

- TRUE_WRONG_DIRECTION: original direction was fundamentally wrong.
- RIGHT_THEN_FAILURE: original direction was initially right and produced meaningful MFE, but exit/lifecycle later failed.

A reversal-at-entry policy should not treat those two classes the same.

## TRUE_WRONG_DIRECTION result

Original:

- N = 849
- actual net PnL: **-$2,374.55**

WD-5G:

- KEEP original: 517
- SKIP: 202
- REVERSE: 130

Among the 130 reversed TRUE_WRONG_DIRECTION trades:

- WIN: **86**
- LOSS: **44**
- reverse subset WR: **66.15%**
- reverse subset net PnL: approximately **+$102.18**

So WD-5F is useful **inside the true wrong-direction subset**.

The problem is identifying that subset before entry.

Across all 849:

- policy WIN: 86
- policy SKIP: 202
- remaining LOSS: 561
- WIN or SKIP: **288 / 849 = 33.92%**
- remaining loss: **66.08%**

This is far below the desired transformation of wrong-direction trades into WIN or NO TRADE.

## Health gate coverage of wrong direction

Only **332 / 849** TRUE_WRONG_DIRECTION trades are classified as overheated.

Therefore:

- 332 are eligible for SKIP/REVERSE
- **517 remain KEEP** and continue losing under the original side

Even a perfect reversal detector inside the overheated subset cannot solve the full wrong-direction problem.

This is a major WD-5G architectural finding.

## Runner preservation failure

RUNNER + BIG_RUNNER:

- total: 523
- original net PnL: **+$1,174.80**

WD-5G actions:

- KEEP: **259**
- REVERSE: 136
- SKIP: 128

Original-side preservation:

**49.52%**

Policy runner PnL:

**+$537.65**

So more than half of runner opportunities are no longer preserved on their original side.

This fails the runner-preservation requirement.

### BIG_RUNNER

145 trades:

- original PnL: **+$851.41**
- policy PnL: **+$409.95**

Actions:

- KEEP 72
- REVERSE 38
- SKIP 35

### RUNNER 1–2%

378 trades:

- original PnL: **+$323.38**
- policy PnL: **+$127.69**

Actions:

- KEEP 187
- REVERSE 98
- SKIP 93

The policy therefore damages exactly the large opportunities WD-5C was trying to preserve.

## Realized winner preservation

507 actual positive trades:

- actual positive PnL: **+$1,389.94**

WD-5G:

- KEEP: 308
- REVERSE: 84
- SKIP: 115

Original winner preservation:

**60.75%**

Policy PnL from the original winner population falls to:

**+$600.54**

This is not acceptable for promotion.

## Path-class impact

### RECOVERED_WINNER

- N = 385
- actual: **+$1,057.00**
- health-only: +$648.17
- WD-5G: **+$533.17**

### CLEAN_WINNER

- N = 115
- actual: **+$330.85**
- health-only: +$157.56
- WD-5G: **+$65.06**

### RIGHT_THEN_FAILURE

- N = 660
- actual: **-$746.44**
- health-only: **-$271.90**
- WD-5G: -$398.02

The Health filter helps RIGHT_THEN_FAILURE materially, but reversing many of those entries gives back some of the benefit.

## Post-hoc reversal threshold sensitivity

A stricter reversal threshold reduces damage, but does not solve the architecture.

| Threshold | Reverses | Reverse PnL | Total PnL | Wrong-direction WIN/SKIP |
|---:|---:|---:|---:|---:|
| 0.514 frozen | 395 | -$221.76 | -$1,456.34 | 33.92% |
| 0.55 | 242 | -$135.58 | -$1,370.16 | 36.75% |
| 0.59 | 134 | -$52.93 | -$1,287.51 | 38.16% |
| 0.65 | 54 | $0.00 | -$1,234.58 | 39.10% |
| 0.67 | 39 | +$17.50 | **-$1,217.08** | 39.10% |
| 0.72 | 12 | +$5.00 | -$1,229.58 | 39.10% |

The 0.67 threshold looks slightly better than health-only in this already-inspected replay, but it is purely post-hoc and cannot be treated as a validated rule.

More importantly, the wrong-direction WIN/SKIP ceiling remains ~39% because the 517 non-overheated wrong-direction trades are never intercepted.

## Score calibration problem

Across the entire overheated population, higher WD-5F reversal probability does not produce a clean monotonic increase in opposite-side profitability.

Even the highest score decile remains aggregate negative under the bounded reverse simulation.

This shows that the WD-5F probability is conditioned on its research cohort and is not calibrated as a universal reversal probability.

## Formal promotion assessment

Pass:

- PnL better than baseline

Fail:

- PnL not worse than health-only
- wrong-direction WIN/SKIP >=50%
- runner preservation >=80%
- realized-winner preservation >=80%
- aggregate reverse PnL >=0

Formal status:

`END_TO_END_POLICY_NOT_READY`

## Main diagnosis

The next bottleneck is not simply reversal timing.

The missing causal question is:

> Is this an actual TRUE_WRONG_DIRECTION entry, or was the original direction valid and only the later trade lifecycle failed?

WD-5G proves that `OVERHEATED` is not equivalent to `WRONG DIRECTION`.

The detector needs to separate at least:

```text
A. TRUE WRONG DIRECTION
   -> reverse or skip

B. RIGHT DIRECTION, OVERHEATED / LATE ENTRY
   -> skip / delay, not reverse

C. RIGHT DIRECTION, RUNNER / RECOVERED
   -> preserve original side

D. RIGHT THEN FAILURE
   -> original entry thesis can be valid; improve lifecycle / protection
```

This distinction is required before another full replay can become promotion-grade.

## Frozen artifacts

`/opt/core-app/data/wd5g_preentry_1m_cache.jsonl`  
SHA256: `ed3e697c0d66e6e9ef06cad2ef80eaf9e1eafd7fee36e1e1411675efa4d55331`

`/opt/core-app/data/wd5g_postentry_1m_cache.jsonl`  
SHA256: `f2a8aaea8e8f9dda6d38d84e5383eff27bfc2b7b1d530c1188aa6b72ba75aba6`

`/opt/core-app/data/wd5g_end_to_end_replay_rows.csv`  
SHA256: `a167de54416784fef22c8876ed6d82cf81dbb9c0dedc4a78010328285fc35fc8`

`/opt/core-app/data/wd5g_end_to_end_replay_results.json`  
SHA256: `c3a7d90520b3980f0b0c550979e38718449b444d40676f55cb65827b1f9ce5c7`

Focused WD-0 through WD-5G tests:

**67 / 67 PASS**

## Handoff

WD-5G should not be promoted.

The next research stage should build an **Entry Thesis Reliability / True-Wrong-Direction detector** across the full trade population.

Its job is to separate:

- TRUE_WRONG_DIRECTION
- RIGHT_THEN_FAILURE
- RECOVERED / CLEAN runner
- STALL / NO EDGE

before the reversal gate is allowed to act.

Only trades classified as likely TRUE_WRONG_DIRECTION should reach the WD-5F reversal confirmation head.
