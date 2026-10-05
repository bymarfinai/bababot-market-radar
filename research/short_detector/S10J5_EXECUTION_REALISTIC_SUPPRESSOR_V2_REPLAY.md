# SHORT-S10J-5 — Execution-Realistic Replay of Regime-Normalized Suppressor V2

Status: **PASS economic improvement / FAIL profitability / no production promotion**

## Objective

Replay the frozen S10J-4 suppressor candidates using the same execution-realistic entry contract and the same frozen Profit Protector used in prior SHORT research.

No suppressor rule was retuned in S10J-5.

Frozen:
- base detector: **S10D**
- Profit Protector: **V4.3 SHORT-LS4 + BE0.10**
- T0 original executable entry
- T+1/T+2/T+3 first Binance 1m bar open strictly after the causal target
- original paper close time as fallback
- exact Binance aggTrade path after reconstructed entry
- frozen fee/slippage/notional metadata

Candidates:
1. S10D baseline
2. T+1 normalized micro-volume only
3. **Primary V2: T+1 normalized micro-volume + T+3 normalized confirmation**
4. T+1 + T+2 challenger

---

# Market-data integrity

Fresh S10D universe:

> **807 selected**

Execution plan:

> **688 executable → 119 no-executable**

Executable strong targets:

> **174**

Fresh executable lane mix:
- T0: 181
- T+1: 231
- T+2: 192
- T+3: 84

Market archives:
- 452 required 1m kline symbol-date files
- 500 required aggTrade symbol-date files
- **0 missing**
- **0 errors**

Replay completed:

> **688 / 688**

---

# Headline comparison

## Research execution-realistic

| Candidate | Selected | Executable | Exec strong | Protected WR | Protected PnL | Delta vs S10D |
|---|---:|---:|---:|---:|---:|---:|
| S10D baseline | 364 | 320 | 80 | 32.50% | **-$180.54** | — |
| T+1 only | 326 | 286 | 79 | 34.97% | **-$128.13** | **+$52.42** |
| **Primary V2** | **317** | **280** | **76** | **34.64%** | **-$131.62** | **+$48.93** |
| T+1 + T+2 | 312 | 277 | 76 | 34.66% | **-$129.92** | **+$50.62** |

All normalized suppressor variants improve research execution-realistic economics versus S10D.

However:

> **none is profitable.**

## Fresh S10H development window

| Candidate | Selected | Executable | Exec strong | Protected WR | Protected PnL | Delta vs S10D |
|---|---:|---:|---:|---:|---:|---:|
| S10D baseline | 807 | 688 | 174 | 33.14% | **-$299.81** | — |
| T+1 only | 746 | 632 | 164 | 34.18% | **-$237.38** | **+$62.43** |
| **Primary V2** | **723** | **616** | **164** | **34.58%** | **-$218.66** | **+$81.15** |
| T+1 + T+2 | 713 | 615 | 163 | 34.63% | **-$220.01** | **+$79.80** |

Primary V2 is the strongest fresh economic improvement among the pre-frozen S10J-4 candidates.

Fresh improvement:

> **-$299.81 → -$218.66**

or:

> **+$81.15**

But the result remains materially negative.

---

# Primary V2 strong retention

## Research

S10D executable strong:
> 80

Primary V2 executable strong:
> **76**

Retention:
> **95.00%**

## Fresh

S10D executable strong:
> 174

Primary V2 executable strong:
> **164**

Retention:
> **94.25%**

This satisfies the design goal of preserving approximately 94–95% of executable strong opportunities.

---

# Primary V2 veto economics

## Research

Vetoed executable cohort:

> **40 trades → 4 strong**

Protected PnL:

> **-$48.93**

Thus removing the cohort improves total PnL by the same amount.

## Fresh

Vetoed executable cohort:

> **72 trades → 10 strong**

Protected PnL:

> **-$81.15**

Again, the vetoed cohort is net-negative and removing it improves total economics.

This confirms that the normalized suppressor is economically directional, not merely label-improving.

---

# Chronological fresh stability

## S10D baseline

- Oct 1: **-$215.42**
- Oct 2: **+$25.30**
- Oct 3: **-$109.69**

## Primary V2

- Oct 1: **-$177.91**
- Oct 2: **+$36.51**
- Oct 3: **-$77.27**

Improvement by day:

- Oct 1: **+$37.51**
- Oct 2: **+$11.22**
- Oct 3: **+$32.42**

Therefore:

> **Primary V2 improves protected PnL on all 3 / 3 fresh chronological days.**

This is materially healthier than the old S10E/S10G hard-band behavior.

---

# Research split stability

S10D → Primary V2:

### Discovery

> **-$143.92 → -$108.52**

Improvement:
> **+$35.40**

### Validation

> **+$1.11 → +$11.00**

Improvement:
> **+$9.89**

### Reserve

> **-$37.73 → -$34.10**

Improvement:
> **+$3.64**

Thus Primary V2 improves all three research splits as well.

---

# Lane economics

## Research

### S10D baseline
- T0: **+$9.18**
- T+1: **-$105.19**
- T+2: **-$88.49**
- T+3: **+$3.95**

### Primary V2
- T0: **+$9.18**
- T+1: **-$52.77**
- T+2: **-$88.49**
- T+3: **+$0.46**

Primary V2 substantially repairs T+1 but does not touch the large T+2 loss.

## Fresh

### S10D baseline
- T0: **-$75.99**
- T+1: **-$128.57**
- T+2: **-$70.88**
- T+3: **-$24.37**

### Primary V2
- T0: **-$75.99**
- T+1: **-$66.14**
- T+2: **-$70.88**
- T+3: **-$5.65**

Fresh improvement:
- T0: unchanged
- T+1: **+$62.43**
- T+2: unchanged
- T+3: **+$18.72**

Residual failure is therefore now concentrated in:

> **T0 + T+1 residual + T+2**

T+3 is almost neutral after V2.

---

# Strong vs non-target economics

## Research Primary V2

Strong:
> 76 executable  
> 66 positive  
> WR **86.84%**  
> PnL **+$147.48**

Non-target:
> 204 executable  
> 31 positive  
> WR **15.20%**  
> PnL **-$279.10**

## Fresh Primary V2

Strong:
> 164 executable  
> 146 positive  
> WR **89.02%**  
> PnL **+$449.04**

Non-target:
> 452 executable  
> 67 positive  
> WR **14.82%**  
> PnL **-$667.70**

The underlying strong SHORT opportunity remains highly monetizable.

The remaining failure is still false-positive volume/economics.

---

# Profit Protector contribution

## Research Primary V2

Delayed hold:
> **-$422.33**

V4.3:
> **-$373.80**

V4.3 + BE0.10:
> **-$131.62**

Composite improvement vs delayed hold:

> **+$290.71**

## Fresh Primary V2

Delayed hold:
> **-$561.75**

V4.3:
> **-$636.49**

V4.3 + BE0.10:
> **-$218.66**

Composite improvement vs delayed hold:

> **+$343.08**

Important observation:

> V4.3 standalone is not sufficient on the broad fresh S10D population; BE0.10 provides most of the final loss compression.

Profit Protector is still helpful, but it cannot offset the remaining volume of non-target entries.

---

# Challenger interpretation

## T+1-only

Best research PnL among the three normalized candidates:

> **-$128.13**

but fresh:

> **-$237.38**

It is more conservative and preserves winners well, but leaves T+3 noise untouched.

## T+1 + T+2 challenger

Research:
> **-$129.92**

Fresh:
> **-$220.01**

It is close to Primary V2 but slightly worse on fresh economics and sacrifices one additional fresh executable strong target.

Primary V2 therefore remains the best balanced candidate from the pre-frozen S10J-4 set.

---

# Relationship to old S10G

For reference, old S10G produced:

> **-$179.30** on the sealed S10H replay.

That is numerically better than Primary V2's **-$218.66** on the now-opened S10H development window.

However:

- S10G failed sealed generalization;
- S10I proved its hard-band suppressors became winner-destructive;
- S10G therefore remains rejected as a production candidate.

S10J-5 does **not** claim that V2 already beats S10G on PnL.

Its value is that:

> **V2 improves economics consistently across all research splits and all fresh days without reproducing the hard-band inversion.**

---

# Verdict

> **S10J-5 = PASS for economic transport / FAIL for profitability.**

Primary V2:
- improves research S10D by **+$48.93**
- improves fresh S10D by **+$81.15**
- improves all 3 research splits
- improves all 3 fresh days
- retains **95.00%** of research executable strong targets
- retains **94.25%** of fresh executable strong targets

But:

> **Research PnL remains -$131.62**  
> **Fresh development PnL remains -$218.66**

Therefore:

> **Primary V2 must not be promoted to production or shadow runtime yet.**

The next engineering problem is no longer "does normalized suppression work?"

That answer is:

> **yes, modestly and consistently.**

The next problem is:

> **how to remove the remaining false-positive economics, especially T0/T+2 and residual T+1, without sacrificing the transport stability achieved by V2.**

Any subsequent repair using S10H remains development work and will require a new later unseen sealed window for validation.

No runtime trading changes are authorized by S10J-5.
