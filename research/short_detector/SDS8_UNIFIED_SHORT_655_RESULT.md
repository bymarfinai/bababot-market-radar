# SHORT-S8 — Unified Full-Universe Replay

Status: **PARTIAL PASS — unified baseline established; recall recovery required**

## Trading funnel

> **655 candidates → 150 OPEN → 37 / 99 strong WIN → 113 non-target**

Additional output:
- weak META_WIN selected: **28**
- META_LOSS selected: **85**
- profitable non-target: **8**
- historical realized-positive selected: **44**
- historical WR: **29.33%**
- historical original-entry PnL: **-$171.62**
- selected peak-MFE equivalent: **$547.45**

Strong-target metrics:
- recall: **37 / 99 = 37.37%**
- precision: **37 / 150 = 24.67%**
- baseline strong-target prevalence: **15.11%**
- precision lift: **1.63x**

This is the first outcome-blind full-universe SHORT baseline.

---

# 1. Outcome-blind T0 router

The router replicates LONG Stage 3C.5 methodology.

Training labels:
- anatomy lane 0 = winner archetype 0 + matched loss cluster 0
- anatomy lane 1 = winner archetype 1 + matched loss cluster 1

Weak META_WIN rows were excluded from router training because they do not have frozen anatomy labels, but the router was applied to them during full-universe inference.

Router-labeled population:
- Discovery: **354**
- Validation: **117**
- Reserve: **120**

Frozen inputs:
- gate flow family
- selected taker share
- 1m side return
- flow support
- micro acceleration 1m vs 3m
- coin-minus-market 30m
- OI change 30m
- volume ratio last vs previous 10m

Frozen logistic router:
- L2
- C = 0.1
- class_weight = balanced
- probability >=0.50 → lane 1

No Validation / Reserve tuning was performed.

## Router performance

| Split | AUC | Accuracy |
|---|---:|---:|
| Discovery | **0.9733** | **92.09%** |
| Validation | **0.9386** | **93.16%** |
| Reserve | **0.9833** | **95.83%** |

Confusion matrices, true lane0/lane1:

Discovery:
- lane0 → 89 correct / 10 routed lane1
- lane1 → 237 correct / 18 routed lane0

Validation:
- lane0 → 29 / 3
- lane1 → 80 / 5

Reserve:
- lane0 → 20 / 2
- lane1 → 95 / 3

Therefore the outcome-blind router transports well to Validation and sealed Reserve.

Across all 655:
- routed lane 0: **186**
- routed lane 1: **469**

---

# 2. Strong-WIN routing integrity

Among the 99 strong SHORT winners:

- true lane1 → routed lane1: **64**
- true lane1 → routed lane0: **5**
- true lane0 → routed lane0: **28**
- true lane0 → routed lane1: **2**

So strong-winner router disagreement is:

> **7 / 99**

The main coverage problem is therefore not a generally broken router.

---

# 3. Frozen unified policy

## Routed lane 0

> **NO_ACCEPTED_SELECTOR**

Reason:
- SD-2A static multi-feature models failed Reserve
- SD-2B2 primary D/V-selected temporal candidates failed Reserve
- post-hoc Lane-0 alternatives were not promoted

Therefore S8 does not invent a Lane-0 rule.

## Routed lane 1

Frozen SD-2B2 rule:

> causal unresolved T+3 snapshot AND  
> `confirm_side_return_pct >= +0.0338983050847%`

No T+1/T+2 early recovery is enabled yet.

---

# 4. Full 655 result

## Overall

| Metric | SHORT-S8 |
|---|---:|
| Candidates | **655** |
| OPEN | **150** |
| Strong WIN total | **99** |
| Strong WIN captured | **37** |
| Recall | **37.37%** |
| Non-target selected | **113** |
| Precision | **24.67%** |
| Precision lift | **1.63x** |
| Profitable non-target | **8** |
| Historical realized-positive | **44** |
| Historical WR | **29.33%** |
| Historical PnL | **-$171.62** |
| Peak-MFE equivalent | **$547.45** |

Selected composition:
- 37 strong WIN
- 28 weak META_WIN
- 85 META_LOSS

---

# 5. Chronological stability

## Discovery

> **393 → 90 OPEN → 23 / 59 strong WIN**

- recall: **38.98%**
- precision: **25.56%**
- precision lift: **1.70x**
- non-target selected: 67
- profitable non-target: 5
- historical realized-positive: 27
- historical WR: 30.0%
- historical PnL: **-$111.56**

## Validation

> **131 → 26 OPEN → 8 / 27 strong WIN**

- recall: **29.63%**
- precision: **30.77%**
- lift: **1.49x**
- non-target selected: 18
- profitable non-target: 3
- historical realized-positive: 11
- historical WR: 42.31%
- historical PnL: **-$9.04**

## Reserve

> **131 → 34 OPEN → 6 / 13 strong WIN**

- recall: **46.15%**
- precision: **17.65%**
- lift: **1.78x**
- non-target selected: 28
- profitable non-target: 0
- historical realized-positive: 6
- historical WR: 17.65%
- historical PnL: **-$51.02**

The unified policy does not collapse on Reserve recall, although precision remains low.

---

# 6. Lane contribution

## Routed lane 0

- routed candidates: **186**
- strong WIN routed there: **33**
- OPEN: **0**
- captured: **0**

This is the largest deliberate coverage hole in S8.

## Routed lane 1

- routed candidates: **469**
- strong WIN routed there: **66**
- OPEN: **150**
- strong WIN captured: **37**
- non-target selected: **113**

Thus the frozen T+3 lane captures:

> **37 / 66 = 56.1%**

of strong winners actually routed to Lane 1.

---

# 7. Missed strong-WIN baseline for SHORT-S9

S8 captures 37 / 99.

Therefore:

> **62 strong winners remain missed.**

Primary selection-state breakdown before detailed S9 anatomy:

### Routed lane 0 / no accepted selector
- **33 strong WIN**

This includes:
- 28 true anatomy lane-0 winners correctly routed lane 0
- 5 true lane-1 winners misrouted lane 0

### Routed lane 1 but T+3 no longer causal
- **18 strong WIN**

### Routed lane 1, causal T+3, threshold fail
- **11 strong WIN**

These three groups sum to:

> **33 + 18 + 11 = 62 missed strong WIN**

This is now the exact input population for SHORT-S9.

---

# 8. Opportunity anatomy

## Selected strong winners — 37

- historical realized-positive: **36 / 37**
- historical PnL: **+$68.25**
- average historical return: **+0.369%**
- peak-MFE equivalent: **$264.50**

## Selected non-targets — 113

- profitable non-targets: **8**
- historical PnL: **-$239.87**
- average historical return: **-0.425%**
- peak-MFE equivalent: **$282.95**

Like LONG, non-target does not mean zero positive excursion.

The selected non-targets contain slightly more aggregate peak-MFE opportunity than the selected strong winners, despite losing historically.

---

# 9. Comparison with LONG Stage 3C.5 baseline

| Metric | LONG 3C.5 | SHORT S8 |
|---|---:|---:|
| Universe | 1,236 | 655 |
| Strong targets | 245 | 99 |
| OPEN | 345 | 150 |
| Strong captured | 114 | 37 |
| Recall | **46.5%** | **37.4%** |
| Precision | **33.0%** | **24.7%** |
| Precision lift | **1.67x** | **1.63x** |

The enrichment ratio is surprisingly similar.

SHORT starts with lower recall and precision, primarily because:
1. Lane 0 has no accepted selector yet;
2. T+3 loses fast-resolving Lane-1 winners;
3. some Lane-1 winners fail the frozen threshold;
4. a small number are router errors.

This is exactly why the LONG pipeline moved next to missed-winner anatomy rather than retuning the whole detector.

---

# 10. Historical PnL caveat

The **-$171.62** S8 PnL uses historical original-entry results.

Lane-1 runtime intent is delayed temporal entry, so this number is **not** execution-realistic profitability evidence.

SD-2B4 already showed delayed-entry economics and exit compatibility separately.

S8 exists to establish unified **coverage and selection anatomy**, exactly like LONG Stage 3C.5.

---

# 11. Verdict

> **SHORT-S8 = PARTIAL PASS**

PASS:
- outcome-blind router is strong and stable through Reserve;
- full 655 replay is now available;
- first unified SHORT funnel is frozen;
- strong-winner miss population is exactly identified;
- Reserve recall does not collapse.

Not yet sufficient:
- only **37 / 99 = 37.4%** strong-winner coverage;
- Lane 0 contributes zero OPEN because it has no accepted selector;
- 62 strong winners remain missed;
- historical reference economics are negative.

## Next stage

Per the LONG pipeline, the next stage is:

> **SHORT-S9 — Missed Winner Anatomy**

Use exactly the **62 missed strong winners** from this S8 baseline.

Do not lower the threshold or invent a new lane first.

Classify why each winner was missed, then choose the highest-value recovery experiment exactly like LONG Stage 3C.6 → 3C.7A.