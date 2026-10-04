# Stage 3C.7A — Early T+1/T+2 Same-Threshold Recovery

## Scope
Full frozen LONG universe: **1,236** trades.
Target: **245 strong WINs = META_WIN AND historical MFE >= 1.00%**.

## Rule
Flow-Aligned LONG may enter at the earliest causal T+1 / T+2 / T+3 snapshot where:

`confirm_side_return_pct >= 0.158514%`

The threshold is unchanged from Stage 3C.3. Counterflow logic is unchanged.

## Full 1,236 replay
Baseline:
- OPEN: **345**
- strong WIN captured: **114/245 = 46.5%**
- non-target OPEN: **231**
- profitable non-target: **29**

Stage 3C.7A:
- OPEN: **454**
- strong WIN captured: **150/245 = 61.2%**
- missed strong WIN: **95**
- non-target OPEN: **304**
- profitable non-target: **39**

Incremental result:
- **+109 OPEN**
- **+36 strong WIN**
- **+73 non-target**
- **+10 profitable non-target**
- **+63 non-profitable non-target**
- marginal cost: **3.03 additional entries per additional strong WIN**
- incremental strong-WIN rate: **33.0%**
- additional peak-MFE opportunity: **+$606.28**
  - strong-WIN peak MFE: **+$389.15**
  - non-target peak MFE: **+$217.13**

Strong-WIN rate among OPEN is essentially flat: **33.0% -> 33.0%**.

## Chronological split stability
Discovery:
- OPEN **207 -> 269**
- strong WIN **74 -> 98**

Validation:
- OPEN **77 -> 98**
- strong WIN **24 -> 29**

Reserve:
- OPEN **61 -> 87**
- strong WIN **16 -> 23**
- capture **42.1% -> 60.5%**
- precision **26.2% -> 26.4%**
- marginal cost about **3.71 entries per additional strong WIN**

## Recovery source
- T+1 early recovery: **66 additional entries -> 21 strong WIN**
- T+2 early recovery: **43 additional entries -> 15 strong WIN**

## Verdict
**PASS for Track-A recall expansion.**

Stage 3C.7A becomes the current Track-A baseline:

`1,236 -> 454 OPEN -> 150 strong WIN -> 304 non-target -> 39 profitable non-target`

It improves recall without lowering the threshold, but it does not improve precision. Historical PnL remains reference-only because delayed execution and profit capture are handled separately in Track B.
