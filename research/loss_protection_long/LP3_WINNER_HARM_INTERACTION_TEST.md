# LP-3 — Winner Harm & Protector Interaction Test

Status: **PASS — interaction test completed; architecture decision frozen.**

Important decision:
- **LP-2A remains the selected protector candidate for the next execution-realistic validation.**
- **LP-2B is NOT allowed as an independent supplement yet.**
- Raw LP-2A OR LP-2B fails the Reserve winner-preservation guardrail.

No production deployment is authorized.

## Inputs

LP-2A wrong-direction candidate:
- T+3 side return <= 0
- T+3 running MFE <= +0.302684%
- T+3 selected 5m normalized slope <= -0.036071

LP-2B sub-0.5 stall-cut candidate:
- T+3 running MFE <= +0.140056%
- T+3 side return <= -0.189349%
- T+3 selected-side VWAP extension 20 <= +0.516788

Both act at T+3 (~2.61 min median), so when both fire the economic discovery action is the same T+3 normalized close. For classification/audit, LP-2A receives precedence.

## Interaction anatomy

Full-universe counts:

| State | N |
|---|---:|
| LP-2A fires | 254 |
| LP-2B fires | 161 |
| Both fire | **105** |
| LP-2A only | **149** |
| LP-2B only | **56** |
| Union | **310** |

LP-2B therefore adds only 56 unique fires beyond LP-2A.

Composition of LP-2B-only:
- 47 WRONG_DIRECTION
- 4 MISSED_OPPORTUNITY
- 4 RECOVERED_WINNER
- 1 CLEAN_WINNER
- 51 / 56 are actual non-positive
- 5 / 56 are realized-positive

So LP-2B does add genuine unique loss coverage, but its stability must be judged on Reserve.

## Raw union: LP-2A OR LP-2B

Full universe:

- fires: **310**
- actual non-positive: **290**
- actual non-positive precision: **93.55%**
- wrong-direction caught: **233 / 555 = 41.98%**
- sub-0.5 failures caught: **248 / 626 = 39.62%**
- recovered winners harmed: **17 / 228 = 7.46%**
- all realized-positive harmed: **20 / 304 = 6.58%**

Normalized economics:
- historical PnL on fired trades: **-$795.95**
- normalized T+3 close: **-$563.21**
- normalized loss-side improvement: **+$311.49**
- normalized winner harm: **-$78.75**
- normalized net delta: **+$232.74**

This looks stronger than LP-2A alone in full-sample aggregate, but full-sample aggregate is not sufficient.

## D / V / R stability

| Metric | Development | Validation | Reserve |
|---|---:|---:|---:|
| Fires | 189 | 61 | 60 |
| Actual non-positive precision | 93.65% | 96.72% | **90.00%** |
| Wrong-direction recall | 42.41% | 44.55% | **38.52%** |
| Sub-0.5 failure recall | 40.34% | 38.81% | **38.52%** |
| Recovered-winner harm | 6.21% | 5.13% | **13.64%** |
| All realized-positive harm | 5.97% | 3.85% | **11.76%** |
| Normalized net delta | +$121.33 | +$58.92 | **+$52.50** |

The raw union **FAILS** the winner-preservation Reserve gate because recovered-winner harm rises above the 10% ceiling.

For comparison, LP-2A alone on Reserve:
- fires: 49
- actual non-positive precision: 91.84%
- wrong-direction recall: 31.15%
- recovered-winner harm: **9.09%**
- all realized-positive harm: **7.84%**
- normalized net delta: **+$51.49**

Adding all LP-2B unique fires only changes Reserve net delta from +$51.49 to +$52.50, while recovered-winner harm worsens from 9.09% to 13.64%.

That is not an acceptable trade.

## Incremental LP-2B-only economics

Full universe LP-2B-only:

- fires: 56
- actual non-positive: 51
- realized-positive: 5
- normalized loss-side improvement: **+$52.48**
- normalized winner harm: **-$18.89**
- normalized net delta: **+$33.59**

But Reserve LP-2B-only:

- fires: **11**
- actual non-positive: 9
- realized-positive: 2
- precision: **81.82%**
- normalized loss-side improvement: **+$10.21**
- normalized winner harm: **-$9.21**
- normalized net delta: only **+$1.00**

This is the core interaction problem: the unique LP-2B contribution collapses on Reserve.

## D/V-only supplement rescue attempt

A supplement gate was searched only inside LP-2B-only using Development, screened on Validation, then Reserve opened once.

Preselected gate:
- `T+3 taker accel 5m <= +0.0148854`

Development:
- fires 20
- precision 100%
- winner harm count 0
- normalized delta +$18.58

Validation:
- fires 9
- precision 100%
- winner harm count 0
- normalized delta +$11.68

Reserve:
- fires 7
- precision **71.43%**
- winner harm count **2**
- normalized delta **-$2.55**

Result: **FAIL**.

No alternate threshold is selected after seeing Reserve. Post-Reserve cherry-picking is prohibited.

## Architecture decision

### Selected
**LP-2A only** proceeds to execution-realistic validation.

### Held
**LP-2B remains research-only** and is not allowed to act as an independent supplement yet.

### Why
1. LP-2A already passes its Reserve high-precision gate.
2. Raw LP-2A OR LP-2B increases Reserve recovered-winner harm to 13.64%.
3. LP-2B-only contributes only +$1.00 normalized Reserve delta while almost equally offsetting loss saved with winner harm.
4. A D/V-selected supplemental gate fails Reserve.
5. Therefore the apparent +$232.74 full-universe union gain is not stable enough to justify the additional winner risk.

## What LP-3 does NOT prove

The dollar figures above are **normalized discovery estimates**, not exact trade-execution PnL.

They use:
- frozen T+3 side return
- $5 per 1% normalization
- historical realized PnL comparison

They do not yet include an execution-realistic fill at the actual next observable trade, exact fees/slippage, or integration with the current 454 OPEN detector cohort.

## Next step

**LP-4 — Execution-Realistic Validation of LP-2A**

Required:
1. freeze LP-2A thresholds unchanged;
2. replay exact causal decision timing around T+3;
3. execute on the next available historical market observation;
4. include stored fee/slippage assumptions;
5. test full discovery universe where executable;
6. then apply unchanged to the current 454 OPEN policy cohort;
7. compare exact PnL, loss saved, winner harmed, and strong-runner survival.

LP-2B must stay out of the combined engine unless a future independent temporal state model proves stable out of sample.
