# SHORT-SA4 — Full Admission Re-run + Residual BAD Audit

Status: **PASS anatomy / SA3 admission architecture materially reduces BAD, residual failure structure now isolated**

## Objective

SA-4 treats the frozen SA-3 architecture as the candidate SHORT admission stack and recomputes the entire frozen CT4 +0.075 universe.

This stage does not create a new rule.

It answers:

1. how much BAD-A/B is actually removed by the new admission architecture;
2. how much TARGET/strong is retained;
3. which residual BAD population is a negative-filter miss versus rescue collateral;
4. whether the next step should expand existing CT7 conditional kills or discover a new failure family.

No runtime or paper-entry rule is changed.

## Important interpretation

The funnel below is a **research attribution funnel**, not a literal production execution order.

CT5B/CT6C remain T-derived hard research vetoes.

SA2-Q95 and CT7C are pre-T-style negative quality/failure selectors.

SA3 T2/T3 branches are selective positive rescue.

---

# 1. Frozen universe

CT4 +0.075:

- selected: **1,087**
- executable: **931**
- PnL: **-$380.39**

Initial BAD <0.50%:

- selected: **398**
- executable: **379**
- protected PnL: **-$833.14**

Initial strong executable:

> **246**

---

# 2. Gross admission funnel

Mutually exclusive negative-attribution order before rescue:

| Layer | Selected | BAD | GRAY | TARGET | Strong | CT4 executable | CT4 PnL of cohort |
|---|---:|---:|---:|---:|---:|---:|---:|
| CT5B hard | 9 | **7** | 0 | 2 | 0 | 7 | -$24.21 |
| CT6C hard | 19 | **13** | 4 | 2 | 0 | 13 | -$19.93 |
| CT7C negative | 123 | **93** | 20 | 10 | 10 | 119 | **-$197.85** |
| Q95 incremental | 64 | **38** | 14 | 12 | 10 | 62 | **-$68.92** |
| unflagged selected | 872 | **247** | 325 | 300 | 246 | 730 | -$69.49 |

SA3 positive rescue then pulls back:

- 14 executable trades
- 8 strong
- 3 BAD
- 3 GRAY
- 8 TARGET total
- exact rescue PnL **+$2.39**

The negative gross counts therefore should not be interpreted as final permanent drops.

---

# 3. BAD rejection achieved by SA3 architecture

Initial:

> **398 selected BAD**

Final selected after negative selection + rescue:

> **250 BAD**

Therefore:

> **148 / 398 BAD selected removed = 37.19%**

Executable:

> **379 -> 234**

Therefore:

> **145 executable BAD removed = 38.26%**

BAD protected PnL:

> **-$833.14 -> -$503.67**

Improvement in BAD loss mass:

> **+$329.47**

This confirms that the SHORT admission redesign is materially working.

The system is no longer carrying the same BAD-A/B load that existed before SA1-SA3.

---

# 4. Strong / TARGET retention

Selection level:

### Strong

- initial selected strong: 266
- final selected strong: 254
- retention: **95.49%**

### TARGET >=1%

- initial selected TARGET: 326
- final selected TARGET: 308
- retention: **94.48%**

Exact executable level:

### Strong

> **234 / 246 = 95.12%**

### TARGET

> **266 / 279 = 95.34%**

So the admission improvement is not coming from indiscriminate winner destruction.

---

# 5. Final exact SA3 state

- executable: **744**
- wins: **284**
- WR: **38.17%**
- strong executable: **234**
- PnL: **-$67.09**

MFE decomposition:

| Bucket | Exec | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| BAD-A <0.30% | **132** | 0 | 0.00% | **-$271.04** |
| BAD-B 0.30-0.50% | **102** | 3 | 2.94% | **-$232.64** |
| GRAY 0.50-1.00% | 244 | 63 | 25.82% | **-$127.63** |
| TARGET >=1.00% | 266 | 218 | **81.95%** | **+$564.21** |

Residual BAD remains:

> **234 executable / -$503.67**

This remains the dominant unresolved problem.

---

# 6. HIST_TIME_FALLBACK still dominates

Final close reasons:

| Reason | Exec | Wins | Strong | PnL |
|---|---:|---:|---:|---:|
| **HIST_TIME_FALLBACK** | **256** | 1 | 10 | **-$736.34** |
| BE0.10 | 205 | 0 | 21 | -$33.45 |
| FULL_CLOSE_050 | 251 | 251 | 171 | +$432.53 |
| RUNNER_CLOSE | 32 | 32 | 32 | +$270.17 |

Within residual BAD:

- fallback: **146**
- fallback PnL: **-$494.52**

Thus almost all remaining BAD loss still comes from trades that never develop sufficient excursion and eventually die at fallback.

Profit Protector remains secondary.

---

# 7. Residual BAD is mostly negative-filter miss, not rescue contamination

Residual BAD total:

> **234 / -$503.67**

### Rescue collateral

Only:

- **3 BAD**
- PnL **-$12.39**
- fallback PnL **-$12.29**

### Negative-filter misses

The real unresolved admission problem is:

- **231 BAD**
- PnL **-$491.29**
- 144 fallback
- fallback PnL **-$482.24**

Therefore:

> **97.5% of residual BAD loss is not caused by T rescue.**

Do not respond by broadly tightening SA3 rescue.

The primary problem is still negative-selection coverage.

---

# 8. Known territory still contains most residual admission loss

Among the 231 true negative-filter misses:

### Inside existing A1/A2/A3 broad territory

- **134 executable**
- PnL **-$293.02**
- 87 fallback
- fallback PnL **-$288.86**

### Outside all current broad archetypes

- **97 executable**
- PnL **-$198.26**
- 57 fallback
- fallback PnL **-$193.38**

Therefore:

> **59.6% of negative-filter miss loss remains inside already-known A1/A2/A3 territory.**

This means we should **not abandon CT7B/CT7C morphology**.

The largest unresolved mass is still in known failure territory.

---

# 9. Near-miss anatomy inside A1/A2/A3

For each residual BAD trade, SA-4 measures how close it is to the frozen K1/K2/K3 conditional rule.

## Group A — ONE CONDITION SHORT

These trades are inside A1/A2/A3 and have at least one CT7C branch for which they satisfy half of the required conditions but do not cross the kill threshold.

- **83 executable**
- PnL **-$199.51**
- 57 fallback
- fallback PnL **-$197.93**

This is the cleanest next development target.

These trades are not a new morphology.

They are:

> **known failure morphology with an under-covered conditional boundary.**

## Group B — ZERO K SIGNAL

Inside broad A1/A2/A3, but none of the frozen K conditions materially fire:

- **51 executable**
- PnL **-$93.52**
- 30 fallback
- fallback PnL **-$90.92**

These likely need a genuinely different second-order conditional branch.

## Group C — OUTSIDE ALL

Not inside A1/A2/A3 at all:

- **97 executable**
- PnL **-$198.26**
- 57 fallback
- fallback PnL **-$193.38**

This population is almost the same economic size as the one-condition-short group.

But it cannot be solved by merely relaxing K1/K2/K3.

It requires new failure-family discovery.

---

# 10. Priority ranking from SA4

## Priority 1 — known-territory near-miss expansion

> **83 trades / -$199.51**

Reason:

- already inside validated A1/A2/A3 morphology;
- only one conditional step short;
- cross-block presence is broad;
- almost all loss is fallback;
- likely lower architecture risk than inventing a new global archetype.

## Priority 2 — outside-all failure discovery

> **97 trades / -$198.26**

Reason:

- almost identical economic loss mass to Priority 1;
- completely outside current failure morphology;
- requires new base admission family rather than threshold relaxation.

## Priority 3 — inside-archetype zero-signal branch discovery

> **51 trades / -$93.52**

These are known broad morphology but current conditional feature families do not explain them.

## Priority 4 — rescue collateral

> **3 BAD / -$12.39**

Too small to justify broad rescue tightening.

---

# 11. Lane remains diagnostic, not root cause

Residual BAD PnL:

| Lane | Exec | PnL | Fallback PnL |
|---|---:|---:|---:|
| T0 | 70 | -$133.44 | -$127.47 |
| T1 | 59 | -$140.74 | -$143.88 |
| T2 | 72 | **-$165.60** | **-$161.26** |
| T3 | 33 | -$63.90 | -$61.91 |

BAD still persists across all lanes.

T2 is the largest residual lane but not uniquely responsible.

This continues to validate the architecture:

> **negative admission quality should remain global; T should remain primarily positive confirmation/rescue.**

---

# 12. Chronological BAD persistence

Residual BAD is negative in all six blocks:

| Block | Exec BAD | BAD PnL |
|---|---:|---:|
| Research Discovery | 40 | -$64.46 |
| Research Validation | 14 | -$21.75 |
| Research Reserve | 20 | -$35.62 |
| Fresh Oct 1 | 62 | **-$168.30** |
| Fresh Oct 2 | 49 | -$97.67 |
| Fresh Oct 3 | 49 | **-$115.88** |

This is not a single-day artifact.

---

# 13. Oracle ceilings

Leakage-only diagnostics:

Perfect removal of all residual BAD:

> **-$67.09 -> +$436.58**

Perfect removal of only residual BAD fallback:

> **-$67.09 -> +$427.43**

Perfect removal of residual GRAY fallback:

> **-$67.09 -> +$125.46**

The economic opportunity remains overwhelmingly concentrated in low-MFE fallback failure.

These are ceilings only, not deployable rules.

---

# SA4 verdict

> **PASS.**

The SA1-SA3 redesign is working.

It has:

- removed **37.2% of selected BAD**;
- removed **38.3% of executable BAD**;
- improved BAD PnL by **+$329.47**;
- preserved **95.12% executable strong**;
- preserved **95.34% executable TARGET**.

Therefore:

> **do not restart the SHORT detector again from zero.**

The residual problem is now narrower and structured.

The next development should not globally tighten Stage 2/4 again.

---

# Recommended next stage

## SA-5A — Known-Territory Near-Miss Expansion

Primary population:

> **83 residual BAD / -$199.51**

Goal:

> add conditional branches or boundary logic inside A1/A2/A3 that capture one-condition-short failures while protecting SA3 strong/TARGET retention.

Guardrails:

- no future-MFE live input;
- thresholds fit from Research Discovery only;
- strong retention target >=95%;
- TARGET retention target >=95%;
- Research/Fresh transport;
- chronological block stability;
- exact replay after any new kill;
- no blanket relaxation of K1/K2/K3.

After SA-5A:

## SA-5B — Outside-All Failure Family Discovery

Population:

> **97 residual BAD / -$198.26**

Only after known-territory expansion should a new global failure morphology be developed.

No runtime promotion is authorized by SA-4.