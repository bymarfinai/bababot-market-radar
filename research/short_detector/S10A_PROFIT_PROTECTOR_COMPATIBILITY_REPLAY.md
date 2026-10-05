# S10A — Profit Protector Compatibility Replay

Status: **COMPLETE — DIAGNOSTIC / ORIGINAL-ENTRY REPLAY**

Population:
- S10A selected SHORT trades: **268**
- strong WIN: **51**
- non-target: **217**
- historical realized-positive: **63**
- historical non-profit: **205**

Replay basis:
- original historical entry
- Binance USD-M daily aggTrades
- 5-second archived protector sampling
- historical final-close market price as fallback
- frozen paper fee/slippage metadata

This is not yet the execution-realistic delayed T+1/T+2/T+3 entry replay.

## Full 268 comparison

| Policy | Wins | WR | PnL |
|---|---:|---:|---:|
| Historical | 63 | 23.5% | -$339.81 |
| V4.2 Hybrid | 70 | 26.1% | -$316.32 |
| V4.3 SHORT-LS4 | 103 | 38.4% | -$309.10 |
| SL/TP 1% | 67 | 25.0% | -$254.04 |
| BE +0.10 standalone | 3 | 1.1% | -$142.01 |
| BE +0.18 standalone | 5 | 1.9% | -$132.26 |
| BE +0.25 standalone | 17 | 6.3% | -$209.17 |
| **V4.2 + BE0.10** | **62** | **23.1%** | **+$20.39** |
| **V4.2 + BE0.18** | **63** | **23.5%** | **+$2.31** |
| V4.2 + BE0.25 | 63 | 23.5% | -$108.52 |
| **V4.3-LS4 + BE0.10** | **99** | **36.9%** | **+$32.25** |
| **V4.3-LS4 + BE0.18** | **99** | **36.9%** | **+$12.70** |
| V4.3-LS4 + BE0.25 | 99 | 36.9% | -$98.13 |

Composite semantics:
- active V4.2 / V4.3 protector retains authority when it fires;
- BE applies only to the corresponding NO_ACTION lane;
- BE variants are frozen prior research policies, not newly tuned parameters.

## Best total-dollar result

**V4.3 SHORT-LS4 + BE0.10**
- PnL: **+$32.25**
- wins: **99 / 268**
- WR: **36.94%**
- gross profit: **+$171.17**
- gross loss: **-$138.92**
- median return: approximately **-0.006%**

Strong-WIN 51:
- 49 positive
- PnL **+$106.06**

Non-target 217:
- 50 positive
- PnL **-$73.81**

Historical non-profit 205:
- historical PnL: **-$473.28**
- with V4.3+BE0.10: **-$83.71**
- 41 become positive

## Strong-winner preservation frontier

### V4.2 + BE0.10
Full:
- PnL **+$20.39**
- 62 wins

Strong 51:
- 45 positive
- PnL **+$168.60**

Non-target 217:
- PnL **-$148.21**

This produces less total PnL than V4.3+BE0.10, but converts the strong-winner cohort into substantially more dollars.

### V4.2 + BE0.18
Full:
- PnL **+$2.31**

Strong 51:
- PnL **+$170.07**

It is a more conservative BE frontier but leaves less total edge.

## 85 historical non-profit trades with MFE >=0.5%

Historical:
- PnL **-$87.37**
- wins 0

V4.3 SHORT-LS4:
- PnL **+$3.99**
- wins **42 / 85**

V4.3 + BE0.10:
- PnL **+$38.67**
- wins **41 / 85**

V4.3 + BE0.18:
- PnL **+$38.67**
- wins **41 / 85**

This confirms that the 0.5–1.0% MFE group contains meaningful recoverable economics.

## Chronological split

### Historical
- Discovery: -$203.30
- Validation: -$36.84
- Reserve: -$99.67

### V4.2 + BE0.10
- Discovery: **+$39.07**
- Validation: **-$0.23**
- Reserve: **-$18.46**

### V4.3 + BE0.10
- Discovery: **+$63.40**
- Validation: **-$1.96**
- Reserve: **-$29.18**

So the improvement transports across D/V/R, but absolute profitability does not yet pass Validation/Reserve.

## Interpretation

1. V4.2 alone helps only modestly.
2. V4.3-LS4 materially raises WR but remains negative alone.
3. Standalone BE dramatically cuts losses but destroys winner counting because exits occur around net break-even.
4. The strongest architecture is **active profit protection + BE only on NO_ACTION trades**.
5. V4.3+BE0.10 is the best total-dollar candidate on the full 268 replay.
6. V4.2+BE0.10/0.18 is stronger for preserving strong-winner dollar conversion.
7. Aggregate positive PnL is driven by Discovery; Validation is near break-even and Reserve remains negative.
8. No production authority is granted.

Next clean validation should replay the accepted S10A temporal entries at their executable delayed T+1/T+2/T+3 entry prices with the frozen composite policies.
