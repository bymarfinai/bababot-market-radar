# LP-5D — High-Precision 75–90s Protector Discovery

Status: **FAIL — no deployment candidate survives sealed Reserve + exact execution replay.**

LP-5D follows the preregistered contract in `LP5D_HIGH_PRECISION_CONTRACT.md`.

## Frozen scope

- current Stage 3C.7A LONG operational cohort: **454 trades**
- actual realized-positive controls: **176**
- PRE-0.5 realized losses: **120**
- WRONG_DIRECTION subgroup: **96**
- decision timestamps searched: **75 / 80 / 85 / 90 seconds**
- causal features only: current side return, running MFE, running MAE
- Development is used for threshold/model fitting
- Validation screens Development winners
- Reserve is opened once for the one final frozen D+V candidate

## Development / Validation result

Four Development candidates survive Validation.

The candidate frozen before Reserve is the simple 75-second conjunction:

```
current_side_return_pct <= -0.2719758485%
AND
running_mfe_pct <= +0.4585533556%
```

### Development

- alive population: **221**
- alive PRE-0.5: **54**
- alive winners: **110**
- fires: **16**
- PRE-0.5 captured: **13**
- winner fires: **2**
- other-loss fires: **1**
- WRONG_DIRECTION captured: **12**
- PRE-0.5 precision: **81.25%**
- PRE-0.5 recall among alive: **24.07%**
- winner-fire rate: **1.82%**

### Validation

- alive population: **73**
- alive PRE-0.5: **30**
- alive winners: **27**
- fires: **6**
- PRE-0.5 captured: **5**
- winner fires: **0**
- other-loss fires: **1**
- WRONG_DIRECTION captured: **4**
- PRE-0.5 precision: **83.33%**
- PRE-0.5 recall among alive: **16.67%**
- winner-fire rate: **0.00%**

This is strong enough to freeze the candidate before opening Reserve.

## Sealed Reserve

Reserve immediately rejects the frozen candidate:

- alive population: **74**
- alive PRE-0.5: **18**
- alive winners: **28**
- fires: **3**
- PRE-0.5 captured: **1**
- winner fires: **2**
- PRE-0.5 precision: **33.33%**
- PRE-0.5 recall among alive: **5.56%**
- winner-fire rate: **7.14%**

Preregistered Reserve requirements were:
- precision >= 70%
- winner-fire rate <= 5%
- PRE-0.5 recall >= 10%

The candidate fails **all three** classification gates.

The three Reserve fires are:
- INUSDT — WRONG_DIRECTION loss
- ACUUSDT — RECOVERED_DRAWDOWN winner
- MELANIAUSDT — RECOVERED_DRAWDOWN winner

This is exactly the failure mode LP-4 warned about: recovered winners can temporarily look like slow/failed early progress.

## Exact archive execution replay

The frozen candidate is still replayed exactly to quantify economics.

Execution contract:
- decision at T+75s
- first Binance USD-M aggregate trade strictly after the decision
- must execute before the historical close
- preserve historical actions through protector execution
- close remaining quantity with stored slippage and fees
- ignore later historical actions after divergence

Coverage:
- fires: **25**
- executable: **25 / 25**
- archive errors: **0**
- median execution delay: **1.143s**
- p90 execution delay: **4.092s**

### Development execution

- 16 fires
- PnL delta: **+$4.63**
- PRE-0.5 delta: **+$9.55**
- winner delta: **-$8.50**
- 2 historical winners converted to non-positive

### Validation execution

- 6 fires
- PnL delta: **+$9.03**
- PRE-0.5 delta: **+$8.51**
- winner fires: **0**

### Reserve execution

- 3 fires
- PnL delta: **-$17.69**
- PRE-0.5 / WD delta: **-$0.52**
- winner delta: **-$17.17**
- **2 historical winners converted to non-positive**
- all 3 Reserve fires are harmed versus historical outcome

So Reserve does not merely fail classification. The exact economics fail badly as well.

## Full current-454 overlay

| Metric | Historical | With LP-5D |
|---|---:|---:|
| Total PnL | **+$62.53** | **+$58.49** |
| Delta | — | **-$4.04** |
| WIN | **176** | **172** |
| WR | **38.77%** | **37.89%** |

Across all 25 fires:
- historical PnL: **-$74.23**
- protected PnL: **-$78.27**
- delta: **-$4.04**
- helped: **11**
- harmed: **14**
- PRE-0.5 target delta: **+$17.53**
- winner delta: **-$25.67**
- winners converted non-positive: **4**

Important nuance:
- the PRE-0.5 aggregate is helped;
- however the WRONG_DIRECTION subgroup itself is **-$2.42 worse** overall under this rule;
- much of the apparent benefit comes from STALL / selected non-WD loss behavior;
- recovered-winner damage overwhelms the saved loss dollars.

## LP-5D conclusion

**FAIL. Do not deploy this rule.**

LP-5C was correct that approximately 75–90 seconds contains meaningful discrimination, but LP-5D shows that a static high-precision threshold built from side return / running MFE / MAE is **not stable enough across time**.

The central unresolved problem is now narrower:

> distinguish a genuine early failure from a recovered winner that temporarily occupies the same 75–90s state.

The next stage should therefore **not** simply loosen/tighten the same threshold or reopen Reserve for tuning.

Recommended next research stage:

**LP-5E — Recovery-Preservation Temporal Shape Gate**

Use Development + Validation only to test whether short sequential shape inside the 75–90s window can separate:
- persistent deterioration / no recovery;
- transient dip followed by recovery.

Reserve from LP-5D is now consumed for this hypothesis family and must not be reused to tune LP-5E thresholds. A genuinely fresh validation holdout is required before any production authority.