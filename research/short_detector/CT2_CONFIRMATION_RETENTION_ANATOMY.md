# SHORT-CT2 — Confirmation Threshold Retention Anatomy

Status: **PASS — +0.075% remains the primary confirmation candidate**

## Objective

CT-1 showed that the frozen SHORT Lane-1 temporal threshold:

> **+0.0338983050847%**

is likely too permissive.

CT-2 does not retune further. It dissects the three carried candidates:

- **0.05%** — conservative
- **0.075%** — primary
- **0.10%** — aggressive challenger

against the baseline 0.033898%.

The goal is to distinguish:

1. trades genuinely removed,
2. trades merely delayed into later lanes,
3. strong winners lost,
4. non-target / severe fallback losses removed,
5. whether a stricter threshold is pruning economically bad trades or simply deleting opportunity.

No Profit Protector parameter changes are made.

---

# Baseline reference

## Research S10D

- 364 selected
- 320 executable
- 85 nominal strong
- 80 executable strong
- protected PnL: **-$180.54**

Severe fallback executable non-targets:

> **87 trades / -$326.05**

## Fresh S10H S10D

- 807 selected
- 688 executable
- 189 nominal strong
- 174 executable strong
- protected PnL: **-$299.81**

Severe fallback executable non-targets:

> **190 trades / -$720.89**

---

# 0.05% — conservative

## Research

Genuinely removed:

> **14 trades = 13 non-target + 1 strong**

Executable removed cohort:

- 13 executable
- baseline protected PnL: **-$9.78**
- severe fallback removed: **3**
- lost executable strong baseline PnL: **+$5.51**

Additionally shifted later:

> **18 trades**

Main transitions:
- T+1 → T+2: 13
- T+2 → T+3: 3
- T+1 → T+3: 1
- T+3 source change: 1

## Fresh

Genuinely removed:

> **20 = 19 non-target + 1 strong**

Executable removed cohort:
- 17 executable
- baseline protected PnL: **-$19.13**
- severe fallback removed: **8**
- lost executable strong baseline PnL: **+$1.10**

Shifted later:

> **26 trades**

Main transitions:
- T+1 → T+2: 16
- T+2 → T+3: 6
- T+1 → T+3: 4

### Interpretation

0.05% is very safe, but its pruning power is modest.

It removes only:
- 3 / 87 research severe fallback
- 8 / 190 fresh severe fallback

This is a useful conservative control, not the strongest repair.

---

# 0.075% — primary

## Research

Genuinely removed:

> **31 trades = 29 non-target + 2 strong**

Composition:
- 26 META_LOSS
- 5 META_WIN

Executable removed cohort:

> **28 executable / protected baseline PnL -$41.44**

Loss anatomy:
- 22 baseline losers
- 13 severe fallback
- severe fallback PnL: **-$43.38**

Strong winner cost:
- 2 nominal strong
- both executable
- combined baseline protected PnL: **+$7.07**

The two lost strong winners are:

### MERL
- baseline lane: T+3
- T+3 confirmation: **+0.03390%**
- baseline protected PnL: **+$5.51**

This is a genuine low-confirmation winner that the stricter threshold intentionally gives up.

### ORCA
- baseline lane: T+2
- T+2 confirmation: **+0.06238%**
- T+3 confirmation later reaches +0.56145%
- but T+3 is **not causal** because the winner resolves before that snapshot
- baseline protected PnL: **+$1.56**

This is an example of a fast-resolving winner that cannot simply be recovered by waiting for the later high confirmation.

## Fresh

Genuinely removed:

> **53 trades = 47 non-target + 6 strong**

Composition:
- 41 META_LOSS
- 12 META_WIN

Executable removed cohort:

> **48 executable / protected baseline PnL -$66.45**

Loss anatomy:
- 37 baseline losers
- 21 severe fallback
- severe fallback PnL: **-$71.89**

Strong winner cost:
- 6 executable strong
- combined baseline protected PnL: **+$12.39**

The six strong winners removed are:
- XNY: +$2.10
- 1000XEC: -$0.26
- PONS: +$1.10
- HMSTR: +$6.47
- BTW: +$1.93
- VELODROME: +$1.06

Important:

> one of the six strong labels was already slightly negative after the frozen PP.

Thus the economic winner cost is smaller than the nominal strong-count cost suggests.

## Severe-loss capture

Relative to all baseline executable severe fallback:

- Research: **13 / 87 = 14.9%**
- Fresh: **21 / 190 = 11.1%**

## Trade shifting

0.075% does not merely delete candidates.

### Research shifted later
> **31 trades**

Transitions:
- T+1 → T+2: 18
- T+1 → T+3: 5
- T+2 → T+3: 6
- T+3 source change: 2

Strong among shifted:
> **5**

The shifted cohort's baseline protected PnL was:

> **-$26.83**

### Fresh shifted later
> **59 trades**

Transitions:
- T+1 → T+2: 32
- T+1 → T+3: 10
- T+2 → T+3: 15
- T+3 source change: 2

Strong among shifted:
> **16**

The shifted cohort's baseline protected PnL was:

> **-$24.22**

This is potentially favorable, but CT-2 cannot claim the later entries improve economics.

Those trades require exact delayed-entry replay in CT-4.

---

# 0.10% — aggressive challenger

## Research

Genuinely removed:

> **55 = 49 non-target + 6 strong**

Executable removed cohort:

> **50 executable / baseline protected PnL -$39.36**

Severe fallback removed:
> **22**

Severe fallback PnL:
> **-$70.08**

This appears attractive from a loss-removal perspective.

However lost executable strong baseline PnL is already:

> **+$36.06**

The key example is:

### PROMPT
- Research Reserve
- T+1 confirmation: **+0.09667%**
- baseline protected PnL: **+$23.49**
- runner-close winner

Thus crossing from 0.075% to 0.10% begins deleting high-value winners rather than only weak/noisy opportunities.

Other lost research strong winners include:
- PLAY +$2.33
- MERL +$5.51
- ORCA +$1.56
- FOGO +$1.87
- ON +$1.30

This explains why the total removed research cohort is only -$39.36 despite removing substantially more severe losses than 0.075%.

## Fresh

Genuinely removed:

> **89 = 78 non-target + 11 strong**

Executable removed cohort:
- 82 executable
- baseline protected PnL: **-$109.11**
- severe fallback removed: **32**
- severe fallback PnL: **-$109.90**
- lost strong baseline PnL: **+$20.60**

Fresh pruning remains economically attractive in isolation.

But the research winner-cost and CT-1 block-level retention degradation make 0.10% a riskier regime-sensitive choice.

---

# Direct comparison

| Metric | 0.05% | **0.075%** | 0.10% |
|---|---:|---:|---:|
| Research removed | 14 | **31** | 55 |
| Research NT removed | 13 | **29** | 49 |
| Research strong lost | 1 | **2** | 6 |
| Research removed cohort PnL | -$9.78 | **-$41.44** | -$39.36 |
| Research severe removed | 3 | **13** | 22 |
| Research lost-strong PnL | +$5.51 | **+$7.07** | **+$36.06** |
| Fresh removed | 20 | **53** | 89 |
| Fresh NT removed | 19 | **47** | 78 |
| Fresh strong lost | 1 | **6** | 11 |
| Fresh removed cohort PnL | -$19.13 | **-$66.45** | -$109.11 |
| Fresh severe removed | 8 | **21** | 32 |
| Fresh lost-strong PnL | +$1.10 | **+$12.39** | +$20.60 |

---

# Why 0.075% survives CT-2

0.075% is the best balance found so far because:

1. It removes a clearly net-negative executable cohort in both research and fresh data.
2. It captures materially more severe fallback than 0.05%.
3. Its lost winner value remains modest:
   - research +$7.07
   - fresh +$12.39
4. It avoids the large research winner destruction introduced at 0.10%.
5. CT-1 already showed minimum chronological-block strong retention of **94.44%** at 0.075%.
6. Most additional strictness beyond 0.075% starts buying more pruning by paying disproportionately more winner value.

This is the key CT-2 conclusion:

> **0.075% looks like genuine noise pruning.**
>
> **0.10% starts to become opportunity pruning.**

---

# Important limitation

0.075% also changes entry timing for a large set:

- 31 research trades shift later
- 59 fresh trades shift later

Those shifted trades have negative baseline PnL in aggregate, but their economics under the new later entry cannot be inferred from baseline replay.

Therefore:

> **CT-2 does not yet prove that 0.075% improves total PnL.**

It proves that the trades fully removed by 0.075% are economically and anatomically loss-enriched.

---

# CT-2 verdict

> **PASS — keep +0.075% as the primary threshold candidate.**

Carry forward:

1. **0.033898% baseline**
2. **0.05% conservative**
3. **0.075% primary**
4. **0.10% aggressive challenger**

Next:

> **CT-3 — chronological stability audit**

CT-3 should test whether the removal and lane-shift behavior remains structurally consistent across Discovery / Validation / Reserve / Fresh Oct 1 / Oct 2 / Oct 3.

After CT-3:

> **CT-4 — exact execution-realistic replay + frozen V4.3 + BE0.10**

No runtime or production change is authorized by CT-2.
