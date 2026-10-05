# SHORT-S10J-6C — T0 Severe-Fallback Repair

Status: **NO PASS — T0 suppressor rejected**

## Objective

After S10J-6B, T0 became the largest remaining negative lane in fresh development data:

> **181 executable / 37 strong / -$75.99**

Fresh T0 severe fallback:

> **50 trades / -$175.01**

The goal of S10J-6C was to determine whether a causal regime-normalized T0 suppressor could remove these severe failures without damaging the positive research T0 behavior.

Frozen:
- S10D base
- S10J-4 Primary V2
- S10J-6B accepted T+2 repair
- V4.3 SHORT-LS4 + BE0.10
- T0 original executable timing
- prior-only rolling normalization

No production/runtime change is made in this stage.

---

# Baseline regime mismatch

## Research T0

> **83 executable / 29 strong / +$9.18**

## Fresh T0

> **181 executable / 37 strong / -$75.99**

This is important:

> T0 is already profitable in the research replay but negative in the fresh development regime.

Therefore a T0 suppressor must improve fresh behavior **without removing profitable research trades**.

---

# Single normalized threshold scan

Candidate families included:
- relative coin-minus-market 30m
- relative price drift
- relative OI change
- relative micro-volume ratio
- relative flow support
- relative taker share

Gate requirements:
- research strong retention >=90%
- fresh strong retention >=90%
- minimum block strong retention >=75%
- non-positive veto economics in at least 5/6 chronological blocks

Result:

> **0 single-threshold candidates passed.**

No single normalized T0 feature produced enough severe-loss removal while preserving winner transport.

---

# Two-signal AND scan

The strongest stable anatomy from S10J-6A was:

> strong T0 tends to have better relative coin-minus-market performance

and severe fallback tends to have:

> higher relative gate price drift.

The best two-signal fresh candidate was:

> `f_f_coin_minus_market_30m__lpct64 <= 0.35`

AND

> `f_gate_price_drift_pct__pct128 >= 0.80`

## Research

- strong retention: **96.6%**
- severe removal: **0%**
- veto cohort PnL: **+$2.57**

The rule fires on a profitable Research Discovery cohort.

Therefore applying it would make research economics worse.

## Fresh

- strong retention: **94.6%**
- severe removal: **12%**
- veto cohort PnL: **-$22.32**

Fresh behavior is directionally useful, but it does not transport to research.

Verdict:

> **REJECT**

Reason:

> fresh improvement is obtained by a rule that removes profitable research trades.

This is exactly the failure pattern S10J is designed to avoid after S10G.

---

# Bounded three-signal test

One final bounded complexity test was allowed.

The third signal was restricted to feature families that already had a stable anatomical direction:
- low relative micro-volume
- high relative OI-acceleration / overheat

No unrestricted feature fishing was performed.

A representative best clean rule:

> coin underperformance  
> AND high price drift  
> AND low relative micro-volume

produced:

## Research
- veto trades: **0**
- strong retention: 100%
- severe removal: 0%
- veto PnL: $0

## Fresh
- strong retention: **94.6%**
- severe removal: **8%**
- veto PnL: **-$16.81**

Although technically non-negative across all six blocks, the rule has:

> **zero research activation**

Therefore it has no evidence of transport.

It is effectively a fresh-only rule.

Verdict:

> **REJECT**

Four-signal or more complex searches were not attempted because they would increase overfit risk without establishing transport.

---

# Why S10J-6C is intentionally a NO PASS

Fresh T0 clearly contains harmful severe fallback trades.

But the current causal normalized feature set cannot isolate them in a way that is simultaneously:

- useful in fresh data,
- active in research,
- winner-preserving,
- and economically directional across regimes.

The key asymmetry is:

> **Research T0 = +$9.18**  
> **Fresh T0 = -$75.99**

A suppressor that only explains the fresh loss but has no valid research behavior is not robust enough.

Therefore:

> **T0 remains unchanged.**

No T0 rule is added to Primary V2 / S10J-6B.

---

# Current accepted stack after S10J-6C

Accepted development stack remains:

1. S10D base detector
2. S10J-4 Primary V2:
   - T+1 low relative micro-volume veto
   - T+3 low relative confirmation veto
3. S10J-6B:
   - T+2 weak relative confirmation
   - AND high relative gate price drift
4. V4.3 SHORT-LS4 + BE0.10
5. **No T0 suppressor**

Current fresh development PnL remains:

> **-$182.01**

Lane PnL:
- T0: **-$75.99**
- T+1: **-$66.14**
- T+2: **-$34.23**
- T+3: **-$5.65**

---

# Engineering implication

Because T0 cannot currently be repaired without regime-specific fitting:

> **do not continue adding complexity to T0.**

The next rational target is:

> **S10J-6D — residual T+1 severe-fallback repair**

Why:
- T+1 is the second-largest remaining lane loss: **-$66.14**
- S10J-4 already showed normalized T+1 signals transport better than T0 signals
- T+1 has temporal information unavailable to T0
- T+3 is already nearly neutral
- T+2 has already been materially repaired

Any later T0 solution should require either:
- a genuinely new causal feature family, or
- evidence from a later regime.

## Verdict

> **S10J-6C = NO PASS.**

This is a valid research result.

The stage prevents a fresh-only T0 suppressor from being promoted simply because it improves the opened S10H development window.

No runtime or production change is authorized.
