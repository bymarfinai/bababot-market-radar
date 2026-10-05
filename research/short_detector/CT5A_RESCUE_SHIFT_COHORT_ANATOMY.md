# SHORT-CT5A — Rescue / Shift Cohort Anatomy at +0.075%

Status: **PASS anatomy / primary problem = T+2 -> T+3 rescue**

## Objective

CT-4 established +0.075% as the stability-primary SHORT confirmation threshold.

CT-5A does not change any rule. It dissects the trades whose entry timing/source changes under +0.075%:

- T+1 -> T+2
- T+1 -> T+3
- T+2 -> T+3
- T+3 source switch / ALT fallback
- ALT-T3 overall
- shifted-to-T3 versus non-shifted T3

Frozen:
- +0.075% confirmation
- S10D fast T0
- Lane-0 recovery
- ALT-T3 rule
- V4.3 SHORT-LS4 + BE0.10
- execution contract

## Total shifted cohort

Across research + fresh:

> **90 shifted trades**
> **21 strong / 69 non-target**

Baseline old-entry PnL:
> **-$51.05**

New exact rescued-entry PnL:
> **-$58.97**

Net effect of shifting:
> **-$7.92 deterioration**

Thus, as a whole, later rescue is economically worse than the previous entry timing.

But the cohort is heterogeneous, so blanket removal is not justified.

---

# T+1 -> T+2

Overall:
- 50 trades
- 10 strong
- old-entry PnL: **-$23.75**
- rescued-entry PnL: **-$17.98**
- delta: **+$5.77**

Research:
- 18 trades / 2 strong
- old: -$4.54
- new: **-$1.58**
- delta: +$2.96

Fresh:
- 32 trades / 8 strong
- old: -$19.21
- new: **-$16.40**
- delta: +$2.81

Strong quality after rescue:
- Research strong: 2/2 positive, +$2.24
- Fresh strong: **8/8 positive, +$18.15**

Non-target after rescue:
- Research: -$3.82
- Fresh: -$34.55

## Interpretation

> **Do not blanket-drop T+1 -> T+2.**

The rescue improves economics versus old entry and preserves a very high-quality winner cohort.

The remaining problem is still non-target discrimination inside the transition.

Status:
> **KEEP FOR NOW**

---

# T+1 -> T+3

Overall:
- 15 trades
- 6 strong
- old-entry PnL: **+$10.59**
- rescued-entry PnL: **-$1.19**
- delta: **-$11.78**

Research:
- 5 trades / 2 strong
- old: +$0.40
- new: -$2.12

Fresh:
- 10 trades / 4 strong
- old: +$10.19
- new: **+$0.93**

Strong after rescue:
- overall: **+$8.18**

Non-target after rescue:
- overall: **-$9.37**

## Interpretation

The delayed T+3 rescue destroys substantial value versus the earlier entry.

However the current rescued cohort is only slightly negative overall and still contains six strong winners.

Blanket dropping would save only about $1.19 of current PnL while discarding +$8.18 of strong-winner value.

Status:
> **SECONDARY REVIEW — conditional rescue may be needed, but blanket DROP is not justified.**

---

# T+2 -> T+3

This is the clearest rescue problem.

Overall:
- **21 trades**
- **5 strong**
- old-entry PnL: **-$29.42**
- rescued-entry PnL: **-$31.32**
- delta: **-$1.91**
- strong PnL after rescue: **+$11.35**
- non-target PnL after rescue: **-$42.67**

Research:
- 6 trades / 1 strong
- rescued PnL: **-$13.97**

Fresh:
- 15 trades / 4 strong
- rescued PnL: **-$17.35**

Fresh non-target PnL:
> **-$27.48**

Research non-target PnL:
> **-$15.19**

Severe fallback remains high:
- 9 severe before
- 9 severe after

## Interpretation

> T+2 -> T+3 is negative in both research and fresh.

The extra minute does not clean the bad setups.

This transition is the **primary CT-5B target**.

A blanket DROP is not automatically accepted because five strong winners remain, but a stricter rescue gate is strongly justified.

---

# T3 source switch / ALT fallback

Four trades switch source while remaining T+3.

Composition:
> **4 / 4 non-target**

PnL:
> **-$8.48**

Strong:
> **0**

Research:
> -$5.39

Fresh:
> -$3.09

## Interpretation

This is the cleanest small-sample failure cohort.

The stricter Lane-1 threshold rejects the original temporal confirmation, but ALT-T3 immediately admits the trade anyway.

In development data this effectively defeats part of the confirmation tightening.

Status:
> **PRIMARY CT-5B TARGET**

Sample size is small, so it still requires stability-aware testing before promotion.

---

# ALT-T3 overall

At +0.075%:

- 19 selected
- 16 executable
- 4 strong
- protected PnL: **-$9.90**
- WR: 31.25%

Strong:
> **+$9.74**

Non-target:
> **-$19.64**

Research:
> **-$3.92**

Fresh:
> **-$5.99**

Fallback:
- 8 trades
- **-$20.38**

By block ALT-T3 is not uniformly bad:
- Research Discovery: +$0.42
- Research Validation: -$0.99
- Research Reserve: -$3.35
- Fresh Oct 1: -$4.97
- Fresh Oct 2: +$1.00
- Fresh Oct 3: -$2.02

## Interpretation

ALT-T3 is net-negative in both research and fresh, but it still contains real strong winners and is positive in two blocks.

Therefore:

> **do not blanket-disable ALT-T3 yet.**

CT-5B should distinguish:
- ALT used as a fallback after failing the stronger temporal threshold
versus
- ALT setups that are independently valid.

---

# Shifted-to-T3 versus non-shifted T3

All T3 at +0.075%:

> 173 selected / 131 executable / **-$57.09**

## Shifted into T3

T+1->T+3 plus T+2->T+3:

- 36 selected
- 31 executable
- 11 strong
- PnL: **-$32.51**
- strong PnL: +$19.53
- non-target PnL: **-$52.04**

## Not shifted into T3

- 137 selected
- 100 executable
- 27 strong
- PnL: **-$24.58**
- strong PnL: +$71.94
- non-target PnL: -$96.52

Per selected trade, the shifted-to-T3 cohort is far more damaging.

## Block anatomy of shifted-to-T3

- Research Discovery: **-$11.49**
- Research Validation: **-$1.17**
- Research Reserve: **-$3.44**
- Fresh Oct 1: **-$11.87**
- Fresh Oct 2: **+$1.00**
- Fresh Oct 3: **-$5.55**

Only Fresh Oct 2 is positive.

This is strong evidence that rescue-to-T3 is the main architectural weakness exposed by CT-4.

---

# Key CT-5A conclusion

Do **not** implement a generic:

> failed confirmation -> DROP all rescue

because different transitions behave very differently.

## Keep for now

### T+1 -> T+2
- improves economics versus old entry;
- 10 strong winners;
- all 10 executable strong remain positive after rescue.

## Primary CT-5B targets

### 1. T+2 -> T+3
- negative research and fresh;
- -$31.32 current rescued PnL;
- -$42.67 non-target PnL;
- severe failures survive the extra confirmation delay.

### 2. T3 source switch / ALT fallback
- 4/4 non-target;
- -$8.48;
- appears to bypass the intent of the stricter temporal threshold.

## Secondary targets

### T+1 -> T+3
- large deterioration versus old entry;
- but six strong winners make blanket rejection unattractive.

### ALT-T3 overall
- negative research and fresh;
- but small sample and four strong winners;
- needs conditional rather than blanket treatment.

---

# Diagnostic upper bound

If current T+2->T+3 and T3-source-switch trades were simply rejected:

Research CT-4:
> -$135.33 -> approximately **-$115.97**

Fresh CT-4:
> -$245.06 -> approximately **-$224.62**

This is diagnostic only.

It would also remove:
- 1 research strong T+2->T+3 winner
- 4 fresh strong T+2->T+3 winners

Therefore CT-5B must search for a discriminative rescue gate rather than blindly deleting the transition.

---

# CT-5A verdict

> **CT-5A = PASS anatomy.**

The central finding is:

> **The problem is not rescue in general. The problem is primarily rescue into T+3, especially T+2 -> T+3 and threshold-fail fallback through ALT-T3.**

Next:

> **CT-5B — DROP vs RESCUE architecture test**

Minimum candidates:
1. current +0.075% architecture
2. disable only T3 source-switch / threshold-fail ALT fallback
3. stricter gate for T+2 -> T+3
4. combined T+2->T+3 gate + source-switch block
5. stress test blanket T+2->T+3 DROP
6. leave T+1->T+2 unchanged

No production/runtime change is authorized by CT-5A.
