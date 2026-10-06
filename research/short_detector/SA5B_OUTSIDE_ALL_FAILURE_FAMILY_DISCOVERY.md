# SHORT-SA5B — Outside-All Failure Family Discovery

Status: **PASS discovery / two broad failure families found / NOT veto-ready**

## Objective

SA-5B intentionally skips SA-5A and attacks the second SA-4 priority directly:

> residual BAD that survives the SA-3 architecture and sits outside all frozen CT7B archetypes A1/A2/A3.

Frozen SA-4 exact residual:

- outside-all executable BAD: **97**
- PnL: **-$198.26**
- HIST_TIME_FALLBACK: 57
- fallback PnL: **-$193.38**

SA-5B does not loosen K1/K2/K3.
It does not modify T or Profit Protector.
No runtime or paper-entry change is authorized.

## 1. Discovery population

The discovery universe is SA-3 final-selected SHORT candidates that are outside A1/A2/A3.

- selected total: **536**
- BAD <0.50%: **110**
- GRAY 0.50-1.00%: 223
- TARGET >=1.00%: **203**
- strong selected: **157**

Exact residual executable BAD:

> **97 / -$198.26**

Future MFE is used only as a research label.
Realized PnL is evaluation only.
Thresholds are derived from Research Discovery TARGET distributions.

## 2. Strict kill-ready scan fails

The first SA-5B scan searched for interpretable two/three-feature conjunctions using non-temporal pre-T features.

Under strict conditions requiring strong BAD-vs-TARGET precision, Research Discovery transport, Research holdout transport, Fresh transport, and chronological agreement, the result was:

> **0 veto-ready family**

This is an important architectural result:

> the outside-all population is more heterogeneous than the original A1/A2/A3 territory.

Therefore SA-5B is frozen as family discovery, not direct kill development.

## 3. Feature anatomy

After excluding exact A1/A2/A3 and Q95 basis features, the strongest stable separators include:

- 30m distance from selected extreme
- 10m / 15m selected-side return
- overheat pressure
- coin-minus-market 15m
- 3m selected-side return
- price drift

The strongest first separator is:

> f_micro_distance_selected_extreme_30m

BAD direction:

> LOW

Global outside-old BAD-vs-TARGET separation is approximately **0.646**.

Research and Fresh point in the same direction.
All 6 chronological blocks point in the same direction.

This suggests a medium-horizon stall geometry not captured by the old 15m A1/A3 definitions.

## 4. B1 — 30M PROXIMITY STALL

Definition:

> f_micro_distance_selected_extreme_30m <= Research Discovery outside-old TARGET Q45

Frozen threshold:

> **0.2502502503**

Interpretation:

> after surviving the old A1/A2/A3 and Q95 filters, the candidate remains too close to its selected-direction extreme over a 30m horizon instead of creating durable separation.

A1 required 15m proximity plus weak 1h displacement.
B1 is a standalone 30m geometry inside the population that explicitly sits outside A1/A2/A3.

So B1 is a new horizon morphology, although semantically adjacent to the old proximity concept.

### B1 selected result

- selected: **211**
- BAD: **67 / 110**
- BAD recall: **60.91%**
- TARGET: 80 / 203
- TARGET hit: 39.41%
- BAD-recall minus TARGET-hit: **+21.50pp**
- GRAY: 64
- strong selected: 72

Most importantly:

> BAD hit-rate exceeds TARGET hit-rate in **6 / 6 chronological blocks**.

### B1 exact economics

- executable: 197
- BAD executable: **59**
- BAD PnL: **-$102.80**
- TARGET executable: 78
- TARGET PnL: **+$221.76**
- strong executable: 71
- total cohort PnL: **+$93.50**

Therefore B1 is absolutely not safe as a direct kill.
It is a broad failure territory only.

## 5. B2 — WEAK PRESSURE / DRIFT STALL

B2 is discovered only among candidates that survive B1.

Remaining after B1:

- BAD: 43
- TARGET: 123

Definition:

> at least **2 of 3** are weak

1. f_new_overheat_pressure <= **7.6874470**
2. f_gate_price_drift_pct <= **0.04364424**
3. f_gate_side_ret_3m_pct <= **0.65582310**

Each threshold is Research Discovery B1-survivor TARGET **Q50**.

### B2 selected result

Inside the B1-survivor population:

- selected: 157
- BAD: **33 / 43**
- conditional BAD recall: **76.74%**
- TARGET: 46 / 123
- TARGET hit: 37.40%
- BAD-recall minus TARGET-hit: **+39.35pp**
- GRAY: 78
- strong selected: 36

B2 therefore adds a genuinely different pressure/drift morphology after B1.

### B2 exact economics

- executable: 106
- BAD executable: **29**
- BAD PnL: **-$88.06**
- TARGET executable: 32
- TARGET PnL: **+$87.66**
- strong executable: 29
- total cohort PnL: **-$32.17**

B2 is economically negative as a broad cohort, but still cannot be killed directly because strong/TARGET collateral is too large.

## 6. B1 + B2 union explains almost all outside-all BAD

Because B2 is conditional on surviving B1, the union is cleanly interpretable.

### Selection-level coverage

B1 + B2:

- BAD covered: **100 / 110**
- BAD coverage: **90.91%**
- TARGET hit: **126 / 203 = 62.07%**
- GRAY: 142
- strong selected hit: **108 / 157 = 68.79%**

Chronological BAD coverage:

| Block | BAD covered / total | BAD coverage | TARGET hit |
|---|---:|---:|---:|
| Research Discovery | 18 / 19 | **94.74%** | 70.73% |
| Research Validation | 3 / 3 | **100%** | 50.00% |
| Research Reserve | 6 / 7 | **85.71%** | 66.67% |
| Fresh Oct 1 | 24 / 26 | **92.31%** | 52.63% |
| Fresh Oct 2 | 29 / 32 | **90.63%** | 64.71% |
| Fresh Oct 3 | 20 / 23 | **86.96%** | 66.67% |

The family union transports across every block.

## 7. Exact residual loss coverage

Original outside-all exact residual:

> **97 BAD / -$198.26**

B1 + B2 covers:

> **88 / 97 executable BAD = 90.72%**

Covered BAD PnL:

> **-$190.86**

So the new families explain approximately:

> **96.3% of outside-all residual BAD net loss mass**

They also cover 53 of 57 outside-all BAD fallback trades.

Only:

> **9 executable BAD / -$7.40**

remain outside B1+B2.

This means the old OUTSIDE_ALL problem is no longer morphologically unexplained.

SA-5B has mapped almost all of it.

## 8. The broad union must NOT be killed

Exact B1+B2 union:

- executable: **303**
- BAD executable: 88 / **-$190.86**
- GRAY executable: 105 / -$57.23
- TARGET executable: **110 / +$309.42**
- strong executable: **100**
- total cohort PnL: **+$61.33**

If the broad union were simply killed:

> current SA-3 PnL -$67.09 would deteriorate to approximately **-$128.42**

and strong retention would collapse.

Therefore:

> **SA-5B is discovery, not a kill gate.**

The family signal is real, but the conditional separator inside each family is still missing.

## 9. Remaining unexplained tail

Only 9 executable outside-all BAD remain outside B1+B2:

- APT
- BROCCOLI714
- CKB
- DYDX
- MOVR
- NEAR
- WLFI
- YB
- 龙虾

Combined PnL:

> **-$7.40**

One of these is actually a positive FULL_CLOSE_050 trade.

So the economically important outside-all problem is now overwhelmingly inside B1/B2.

There is no reason to create a third broad family yet.

# SA-5B verdict

> **PASS failure-family discovery.**

The outside-all residual decomposes into:

### B1 — 30M PROXIMITY STALL

A medium-horizon geometry failure.

### B2 — WEAK PRESSURE / DRIFT STALL

A conditional pressure/drift failure among B1 survivors.

Together they explain:

- **90.9% of selected outside-all BAD**
- **90.7% of executable outside-all BAD**
- approximately **96.3% of outside-all BAD net loss mass**

with transport across Research and Fresh chronology.

But neither family is veto-ready.
The broad union also contains large profitable TARGET/strong populations.

## Recommended next stage

The correct next step is not another global archetype.

It is:

> **SA-5C — Conditional Kill Discovery inside B1/B2**

SA-5C should search for second-order causal separators inside:

1. B1 30M PROXIMITY STALL
2. B2 WEAK PRESSURE / DRIFT STALL

using the same discipline that converted CT7B broad A1/A2/A3 into CT7C K1/K2/K3.

Primary guardrails:

- thresholds fit from Research Discovery TARGET only
- no future MFE live inputs
- no T as the negative-selector basis
- strong/TARGET retention >=95% at combined-system level
- Research/Fresh transport
- chronological stability
- exact execution replay after candidate kill union
- SA3 T rescue remains a separate positive layer

SA-5A remains skipped per user instruction.

No runtime promotion is authorized by SA-5B.