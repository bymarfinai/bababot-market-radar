# SHORT-CT7C — Conditional Low-MFE Kill Detector

Status: **PASS research candidate / materially effective / NOT runtime-ready**

## Objective

CT-7C converts the broad CT-7B failure territory into a materially safer kill set.

The architecture is:

> global failure archetype first  
> then conditional second-order kill rule inside that archetype.

T1/T2/T3 are **not** used as the basis of the low-MFE detector.

Future MFE is a research label only.

Realized PnL is evaluation only.

No runtime or paper-entry change is authorized.

---

## Frozen input

CT-7B broad archetypes:

1. A1 — LOW DISPLACEMENT
2. A2 — WEAK RELATIVE EXPANSION
3. A3 — LOW ENERGY RESIDUAL

Those broad regions identify 282 / 398 BAD trades but are not safe enough to veto directly.

CT-7C searches for second-order causal conditions inside each region.

All thresholds are derived only from the **Research Discovery TARGET-MFE** distribution.

---

# Conditional separator finding

The features that become useful inside an archetype are different from the global CT-7A features.

## Inside A1 LOW DISPLACEMENT

Strong conditional signals include:

- market dispersion 5m
- price drift
- acceleration 5m vs 15m
- positioning support
- market selected return 30m
- momentum curvature

Interpretation:

> within an already under-displaced setup, many BAD trades occur when the surrounding market is active/turbulent but the coin lacks stable positioning support or produces a short burst that does not convert into durable excursion.

## Inside A2 WEAK RELATIVE EXPANSION

Useful conditional signals include:

- market dispersion 5m
- 5m return / extension
- momentum curvature
- acceleration 5m vs 15m
- 24h liquidity context

Interpretation:

> weak relative expansion becomes especially dangerous when market dispersion is elevated while the coin remains illiquid or only shows a short, non-persistent extension.

## Inside A3 LOW ENERGY RESIDUAL

Useful conditional signals include:

- previous-3-bar side return
- current 5m side return
- 60m extension
- acceleration
- OI/overheat diagnostics

Interpretation:

> some low-energy setups briefly burst in the selected direction but lack sustained 60m extension. That short burst is not enough to create a durable opportunity.

This validates the CT-7B hypothesis that globally weak features such as OI/heat/acceleration may become useful conditionally inside a morphology archetype.

---

# Frozen CT-7C branches

## K1 — A1 TURBULENT / UNSUPPORTED

Prerequisite:

> trade belongs to A1 LOW DISPLACEMENT

Then kill if at least **2 of 3** are true:

1. market dispersion 5m >= **0.0670849** (Research Discovery TARGET Q70)
2. acceleration 5m vs 15m >= **0.7309212** (Q70)
3. positioning support <= **0.3000000** (Q30)

Result:

- 62 selected
- 60 executable
- **47 BAD**
- 11 GRAY
- 4 TARGET
- 4 strong executable
- BAD-vs-TARGET precision **92.16%**
- dropped PnL **-$95.55**

## K2 — A2 ILLIQUID DISPERSION

Prerequisite:

> trade belongs to A2 WEAK RELATIVE EXPANSION

Kill if both are true:

1. market dispersion 5m >= **0.0568162** (Q65)
2. quote volume 24h <= **4,324,939.01** (Q35)

Result:

- 55 selected
- 53 executable
- **43 BAD**
- 8 GRAY
- 4 TARGET
- 4 strong executable
- BAD-vs-TARGET precision **91.49%**
- dropped PnL **-$104.60**

## K3 — A3 SHORT BURST / NO EXTENSION

Prerequisite:

> trade belongs to A3 LOW ENERGY RESIDUAL

Kill if at least **2 of 3** are true:

1. previous-3-bar side return >= **0.382971** (Q60)
2. current 5m side return >= **0.934752** (Q60)
3. 60m extension <= **0.581813** (Q40)

Result:

- 33 selected
- 33 executable
- **25 BAD**
- 4 GRAY
- 4 TARGET
- 4 strong executable
- BAD-vs-TARGET precision **86.21%**
- dropped PnL **-$64.53**

---

# Marginal contribution

The three branches are not duplicates.

Frozen order:

### K1

Adds:

- **47 BAD**
- 4 TARGET
- dropped PnL -$95.55

### K2 after K1

Adds another:

- **31 new BAD**
- 3 new TARGET
- dropped PnL -$65.05

### K3 after K1+K2

Adds another:

- **17 new BAD**
- 3 new TARGET
- dropped PnL -$40.54

Therefore all three branches contribute material marginal BAD coverage.

---

# CT-7C union

K1 OR K2 OR K3:

- **125 selected**
- **121 executable**
- BAD-A: **61**
- BAD-B: **34**
- BAD total: **95**
- GRAY: 20
- TARGET-MFE: **10**
- strong selected: **10**
- strong executable: **10**

BAD recall across the full low-MFE universe:

> **95 / 398 = 23.87%**

TARGET hit rate:

> **10 / 326 = 3.07%**

BAD-vs-TARGET precision:

> **90.48%**

Strong selected retention:

> **96.24%**

Strong executable retention:

> **95.93%**

This is a large improvement over the broad CT-7B territory:

- CT-7B broad union BAD recall: 70.85%, but 109 strong selected inside.
- CT-7C executable kill candidate: 23.87% BAD recall, with only 10 strong selected inside.

CT-7C therefore successfully converts broad failure territory into a much safer kill set.

---

# PnL decomposition

Executable kill cohort:

## BAD-A

- 60 executable
- PnL **-$154.95**
- only 1 winner

## BAD-B

- 34 executable
- PnL **-$63.53**
- only 1 winner

Combined BAD loss removed:

> **-$218.48**

## GRAY

- 17 executable
- PnL **-$6.27**

## TARGET / strong collateral

- 10 executable
- all 10 strong
- all 10 profitable
- PnL **+$23.61**

Net kill-cohort PnL:

> **-$201.14**

Thus CT-7C sacrifices +$23.61 of strong profit to eliminate more than $224 of non-strong/low-MFE losses.

The economics are favorable, but the strong collateral is real and must be addressed before runtime promotion.

---

# Research / Fresh transport

Research kill cohort:

- 32 BAD
- 1 TARGET / strong
- PnL **-$94.62**
- BAD-vs-TARGET precision **96.97%**

Fresh kill cohort:

- 63 BAD
- 9 TARGET / strong
- PnL **-$106.52**
- BAD-vs-TARGET precision **87.50%**

Both Research and Fresh improve if the CT-7C kill candidate is applied.

---

# Chronological blocks

| Block | BAD killed | TARGET killed | Strong killed | Dropped PnL |
|---|---:|---:|---:|---:|
| Research Discovery | 21 | 0 | 0 | **-$82.31** |
| Research Validation | 4 | 1 | 1 | **-$4.07** |
| Research Reserve | 7 | 0 | 0 | **-$8.23** |
| Fresh Oct 1 | 31 | 6 | 6 | **-$50.84** |
| Fresh Oct 2 | 26 | 2 | 2 | **-$45.95** |
| Fresh Oct 3 | 6 | 1 | 1 | **-$9.73** |

Result:

> **6/6 blocks have negative dropped PnL**

So unlike the broad CT-7B archetype union, the CT-7C conditional kill set does not make any known chronological block worse on net.

This is a major improvement in execution safety.

---

# Exact CT4 replay impact

Frozen CT4 +0.075 baseline:

- 1,087 selected
- 931 executable
- 246 executable strong
- WR **33.41%**
- PnL **-$380.39**

Applying CT-7C only:

- 962 selected
- 810 executable
- 236 executable strong
- WR **36.05%**
- PnL **-$179.25**

CT-7C improvement:

> **+$201.14**

That removes more than half of the baseline loss magnitude.

---

# Combined CT-5B + CT-6C + CT-7C

Overlap is small:

- CT-7C vs CT-6C: 1 trade
- CT-7C vs CT-5B: 1 trade
- CT-5B vs CT-6C: 0 trades

Combined result:

- **936 selected**
- **792 executable**
- **236 executable strong**
- wins: 290
- WR **36.62%**
- PnL **-$138.40**

Research:

- 251 executable
- WR **38.25%**
- PnL **-$29.63**

Fresh:

- 541 executable
- WR **35.86%**
- PnL **-$108.77**

Total improvement versus CT4 +0.075 baseline:

> **-$380.39 -> -$138.40**

Improvement:

> **+$241.99**

Approximately 63.6% of the original loss magnitude is removed.

However:

> profitability is still negative.

And:

> 10 executable strong trades are sacrificed by the CT-7C layer.

---

# CT-7C verdict

> **PASS as a research-only conditional low-MFE kill candidate.**

The important result is architectural:

CT-7A found global weak morphology.

CT-7B located broad failure archetypes covering 70.9% of BAD.

CT-7C can safely narrow those archetypes into a kill set with:

- **23.87% global BAD recall**
- **90.48% BAD-vs-TARGET precision**
- **95.93% executable strong retention**
- **6/6 blocks with negative dropped PnL**
- **+$201.14 standalone PnL improvement**

This is materially stronger than the earlier T-based low-MFE veto.

But CT-7C is **not runtime-ready** because:

1. 10 strong winners are still removed;
2. those winners contribute +$23.61;
3. combined system PnL remains -$138.40;
4. all current validation cohorts have already influenced the research path and a later unseen cohort is still needed before authority.

---

# Next stage implication

CT-7D should not simply loosen CT-7C thresholds.

The correct next problem is:

> **rescue strong winners from inside the CT-7C kill set without re-admitting many BAD trades.**

This is where the earlier T framework can become useful again.

T should not be used to define low-MFE failure.

Instead:

> Low-MFE detector = negative-selection / kill engine  
> T confirmation = positive-selection / strong-winner rescue engine

A strong T-confirmation override can be tested only on the CT-7C flagged population.

That directly follows the architecture insight that T is better suited to identifying strong winners than to identifying the full low-MFE population.

No runtime promotion is authorized by CT-7C.