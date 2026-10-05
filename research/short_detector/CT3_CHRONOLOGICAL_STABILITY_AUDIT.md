# SHORT-CT3 — Chronological Stability Audit

Status: **PASS WITH WARNING — +0.075% remains primary**

## Objective

CT-3 audits whether the candidate SHORT temporal confirmation thresholds discovered in CT-1/CT-2 behave consistently across chronological regimes.

No new threshold is fitted here.

Carried thresholds:
- **0.033898%** baseline
- **0.05%** conservative
- **0.075%** primary
- **0.10%** aggressive challenger

The audit covers:
1. Research Discovery
2. Research Validation
3. Research Reserve
4. Fresh 2026-10-01
5. Fresh 2026-10-02
6. Fresh 2026-10-03

Frozen:
- S10D fast T0
- S10C Lane-0 recovery
- alternate T+3 rescue
- router
- Profit Protector parameters

CT-3 still uses baseline-entry economics only for affected-cohort diagnostics.

Exact new entry prices for shifted trades remain deferred to CT-4.

---

# Stability criteria

Primary confirmation candidate should show:

- high strong-winner retention in every block;
- precision improvement in most blocks;
- removed cohorts that are consistently economically bad;
- no evidence that stricter confirmation only works in one regime;
- lane shifts that are not obviously concentrated in profitable baseline cohorts.

A candidate is considered unstable if strong retention collapses in one or more chronological blocks even when aggregate precision improves.

---

# 0.05% — conservative control

Aggregate stability:

- minimum block strong retention: **98.04%**
- precision improved/equal: **6 / 6 blocks**
- removed cohort non-positive: **5 / 6 blocks**
- shifted cohort baseline non-positive: **4 / 6 blocks**

Total affected baseline economics:

- removed executable PnL: **-$28.91**
- shifted baseline executable PnL: **-$16.63**
- severe fallback removed: **11**
- removed strong baseline value: **+$6.60**

## Block view

### Research Discovery
- strong retention: 98.04%
- precision: +0.29 pp
- removed cohort PnL: approximately **+$0.03**
- shifted cohort PnL: -$4.03

### Research Validation
- strong retention: 100%
- precision: +0.95 pp
- removed PnL: -$3.52
- shifted PnL: -$4.55

### Research Reserve
- strong retention: 100%
- precision: +1.14 pp
- removed PnL: -$6.30
- shifted PnL: -$13.77

### Fresh Oct 1
- strong retention: 98.53%
- precision: +0.31 pp
- removed PnL: -$5.17
- shifted PnL: -$1.51

### Fresh Oct 2
- strong retention: 100%
- precision: +0.67 pp
- removed PnL: -$12.81
- shifted baseline PnL: **+$6.42**

### Fresh Oct 3
- strong retention: 100%
- precision: +0.38 pp
- removed PnL: -$1.15
- shifted baseline PnL: **+$0.81**

### Verdict

> **Very stable but weak pruning.**

0.05% remains a conservative control for CT-4.

---

# 0.075% — primary

Aggregate stability:

- minimum block strong retention: **94.44%**
- precision improved/equal: **5 / 6 blocks**
- removed cohort non-positive: **6 / 6 blocks**
- shifted cohort baseline non-positive: **5 / 6 blocks**
- total removed executable baseline PnL: **-$107.88**
- total shifted baseline executable PnL: **-$51.05**
- severe fallback removed: **34**
- removed strong baseline value: **+$19.46**

The key result is:

> **every removed cohort is economically non-positive across all six chronological blocks.**

This is strong evidence that +0.075% is not obtaining its aggregate improvement from one isolated regime.

## Research Discovery

- selected: 220 → 202
- strong: 51 → 49
- strong retention: **96.08%**
- precision delta: **+1.08 pp**
- non-target removed: 16
- removed cohort PnL: **-$14.44**
- severe fallback removed: 8
- shifted: 19
- shifted baseline PnL: **-$13.29**

## Research Validation

- selected: 69 → 66
- strong: 22 → 22
- strong retention: **100%**
- precision delta: **+1.45 pp**
- removed cohort PnL: **-$5.27**
- shifted baseline PnL: **-$7.50**

## Research Reserve

- selected: 75 → 65
- strong: 12 → 12
- strong retention: **100%**
- precision delta: **+2.46 pp**
- removed cohort PnL: **-$21.73**
- severe fallback removed: 5
- shifted baseline PnL: **-$6.04**

This is especially important because Reserve does not show the winner-destruction seen at 0.10%.

## Fresh Oct 1

- selected: 315 → 290
- strong: 68 → 65
- strong retention: **95.59%**
- precision delta: **+0.83 pp**
- non-target removed: 22
- removed cohort PnL: **-$36.03**
- severe fallback removed: 11
- shifted baseline PnL: **-$18.92**

## Fresh Oct 2

- selected: 323 → 303
- strong: 85 → 84
- strong retention: **98.82%**
- precision delta: **+1.41 pp**
- non-target removed: 19
- removed cohort PnL: **-$24.42**
- severe fallback removed: 7
- shifted baseline PnL: **+$3.91**

This is the only block where the shifted cohort was slightly profitable at the old entry.

This does not invalidate the threshold, but exact delayed-entry replay is required.

## Fresh Oct 3 — warning block

- selected: 169 → 161
- strong: 36 → 34
- strong retention: **94.44%**
- precision delta: **-0.18 pp**
- non-target removed: 6
- removed cohort PnL: **-$5.99**
- severe fallback removed: 3
- shifted baseline PnL: **-$9.21**

Fresh Oct 3 is the weakest CT-3 block.

The threshold still removes a net-negative cohort and retains more than 94% of strong winners, but nominal precision declines slightly because two strong winners are removed.

### Verdict

> **PASS WITH WARNING**

+0.075% remains the primary threshold candidate because:

1. removed cohorts are non-positive in **6/6** blocks;
2. strong retention never falls below **94.44%**;
3. precision improves in **5/6** blocks;
4. shifted baseline economics are non-positive in **5/6** blocks;
5. Research Reserve remains fully strong-preserving;
6. the only weak block is Fresh Oct 3, and the degradation is small enough to require CT-4 rather than immediate rejection.

---

# 0.10% — aggressive challenger

Aggregate stability:

- minimum block strong retention: **83.33%**
- precision improved/equal: 5/6
- removed cohort non-positive: 6/6
- shifted cohort baseline non-positive: 5/6
- removed executable baseline PnL: **-$148.47**
- shifted baseline executable PnL: **-$84.46**
- severe fallback removed: **54**
- removed strong baseline value: **+$56.66**

The loss pruning is stronger, but winner cost rises sharply.

## Research Reserve

- strong retention: **83.33%**
- 2 / 12 baseline-selected strong winners removed

This includes previously identified high-value winner loss such as PROMPT.

## Fresh Oct 3

- strong retention: **86.11%**
- precision delta: **-1.04 pp**
- 5 strong winners removed
- only 11 non-targets removed

Noise removed per strong lost:

> **2.2 : 1**

This is materially worse than the earlier blocks.

### Verdict

> **FAIL STABILITY GATE**

0.10% may still be retained as an aggressive CT-4 stress challenger, but it is no longer eligible as the primary confirmation setting.

---

# Severe-loss removal by block at 0.075%

The +0.075% candidate removes severe fallback across most regimes:

- Research Discovery: 8
- Research Validation: 0
- Research Reserve: 5
- Fresh Oct 1: 11
- Fresh Oct 2: 7
- Fresh Oct 3: 3

Total:

> **34 severe fallback trades**

The absence of severe removal in Research Validation is not caused by winner destruction; strong retention remains 100% and the removed cohort is still net-negative.

---

# Trade-shift behavior at 0.075%

The most common transitions are:

- T+1 → T+2
- T+1 → T+3
- T+2 → T+3

This confirms that raising confirmation does two distinct things:

1. deletes weak setups entirely;
2. forces marginal setups to prove themselves for another minute or two.

CT-3 can evaluate the quality of the old entries, but it cannot know whether the later reconstructed entries are better or worse.

That is now the critical unknown.

---

# CT-3 verdict

> **CT-3 = PASS WITH WARNING for +0.075%.**

Ranking entering CT-4:

1. **0.075% — primary**
2. **0.05% — conservative control**
3. **0.10% — aggressive stress challenger / stability fail**
4. 0.033898% — frozen baseline

The evidence now supports the original hypothesis:

> **+0.0339% is too permissive, and approximately +0.075% is a more robust SHORT confirmation floor.**

But promotion is still prohibited because entry timing changes materially.

---

# Next stage

> **CT-4 — exact execution-realistic replay + frozen V4.3 SHORT-LS4 + BE0.10**

CT-4 must reconstruct the actual later entry for every shifted T+1/T+2/T+3 trade and compare:

- baseline 0.033898%
- conservative 0.05%
- primary 0.075%
- aggressive 0.10%

Required outputs:
- selected vs executable
- strong executable retention
- per-lane PnL
- per-block PnL
- removed vs shifted economics
- frozen PP result
- whether Fresh Oct 3 remains a weak regime after exact execution
- whether +0.075% actually improves total SHORT economics rather than merely improving labels

No runtime or production change is authorized by CT-3.
