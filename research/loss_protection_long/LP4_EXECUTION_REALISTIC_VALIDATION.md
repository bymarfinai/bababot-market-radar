# LP-4 — Execution-Realistic Validation of LP-2A

Status: **FAIL FOR DEPLOYMENT**

LP-4 freezes the LP-2A thresholds unchanged and tests them under an execution-realistic historical overlay. This stage supersedes normalized discovery-dollar estimates for deployment decisions.

## Frozen LP-2A rule

At T+3, all conditions must hold:

1. current side return <= 0.0000%
2. running MFE <= +0.3026839575%
3. selected 5m normalized slope <= -0.0360707804

No threshold retuning was allowed in LP-4.

## Execution contract

- Decision timestamp: `temporal__t3_target_ms`
- Market source: Binance USD-M daily `aggTrades` historical archive
- Execution: first aggregate trade strictly after the decision timestamp and no later than the historical close
- Overlay accounting:
  - preserve historical executed actions up through protector execution
  - close all remaining quantity at the archive market observation
  - apply stored paper slippage and fees
  - ignore later historical actions after the protector diverges
- If the trade is already closed before T+3, or no executable trade exists before the historical close, the historical result is left unchanged.

## Causal executability

LP-2A fires on 254 of 1,236 rows in frozen discovery scoring.

But:
- **121 / 254 are already closed by the T+3 decision**
- only **133** remain open at decision time
- first archive trade before historical close is found for **129**

Current 454 OPEN cohort:
- LP-2A fires: **40**
- already closed by T+3: **26**
- decision-alive: **14**
- actually executed: **13**

This is a major reason normalized LP-2A discovery estimates overstated practical impact.

## Full 1,236 exact replay

| Metric | Historical | With LP-2A | Delta |
|---|---:|---:|---:|
| Total PnL | -$1,294.20 | **-$1,264.68** | **+$29.52** |
| WIN | 304 | **290** | **-14** |
| WR | 24.60% | **23.46%** | **-1.13 pp** |

Trade effects among the 254 fires:
- executed: 129
- helped: 85
- harmed: 39
- unchanged/non-executable: 130

Key exact anatomy:
- TRUE_WRONG_DIRECTION delta: **+$63.34**
- RECOVERED_WINNER delta: **-$65.65**
- historical winners converted to non-positive: **14**

So the full-universe net improvement is small because recovered-winner damage almost fully offsets wrong-direction savings.

## D / V / R exact deltas

| Split | Executed | Exact PnL delta |
|---|---:|---:|
| Development | 79 | +$11.52 |
| Validation | 20 | +$13.50 |
| Reserve | 30 | **+$4.51** |

Reserve remains slightly positive in dollars, but:
- wrong-direction delta: **+$16.09**
- recovered-winner delta: **-$20.27**
- four historical winners are turned non-positive

Therefore the exact path-level economics are materially weaker than normalized LP-2A discovery scoring.

## Current 454 OPEN operational replay

This is the decisive deployment test.

| Metric | Historical | With LP-2A | Delta |
|---|---:|---:|---:|
| Total PnL | **+$62.53** | **+$47.86** | **-$14.67** |
| WIN | **176** | **172** | **-4** |
| WR | **38.77%** | **37.89%** | **-0.88 pp** |

Operational anatomy:
- fires: 40
- decision-alive: 14
- actually executed: 13
- helped: 8
- harmed: 5

Most important:
- wrong-direction fires in 454: 20
- wrong-direction actually executable: **4**
- wrong-direction exact savings: **+$4.21**
- recovered winners hit: **4**
- all 4 are executable
- recovered-winner exact damage: **-$34.26**

That makes LP-2A clearly negative on the current detector policy cohort.

## Path-level exact full-universe effect

| Path | Fired | Executed | Exact delta |
|---|---:|---:|---:|
| TRUE_WRONG_DIRECTION | 186 | 86 | **+$63.34** |
| STALL_NO_EDGE | 15 | 15 | **+$47.22** |
| RIGHT_THEN_FAILURE | 38 | 13 | **-$12.78** |
| RECOVERED_DRAWDOWN | 13 | 13 | **-$65.65** |
| CORRECT_RUNNER | 2 | 2 | **-$2.62** |

The rule does save meaningful wrong-direction and stall losses, but it damages recovered winners too severely.

## Execution latency

Archive execution after the frozen T+3 decision:
- full-universe median: **2.10 sec**
- full-universe p90: **14.24 sec**
- current 454 median: **0.89 sec**
- current 454 p90: **3.14 sec**

Execution availability/latency is therefore not the main failure. The main problem is classification and decision timing.

## LP-4 conclusion

**FAIL FOR DEPLOYMENT.**

LP-2A should not be deployed unchanged.

Why:
1. Current 454 PnL falls from +$62.53 to +$47.86.
2. Current 454 WR falls from 38.77% to 37.89%.
3. Recovered-winner damage (-$34.26) overwhelms current-cohort wrong-direction savings (+$4.21).
4. More than 47% of discovery fires are already closed before T+3, limiting causal utility.
5. The normalized +$199 discovery estimate from LP-2A does not survive exact execution accounting.

## Research implication

The next iteration must not merely optimize the same T+3 rule harder. The exact replay suggests two structural changes are needed:

- **earlier decision availability** for genuinely fast wrong-direction losses; and/or
- **a recovery-preservation gate** that prevents LP from cutting trajectories resembling recovered winners.

Any next candidate must be discovered and validated without reusing Reserve to tune thresholds.

No deployment is authorized from LP-4.
