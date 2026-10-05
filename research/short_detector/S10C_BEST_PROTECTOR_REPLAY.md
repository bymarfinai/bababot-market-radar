# SHORT-S10C — Best Profit Protector Replay

Status: **COMPLETE — DIAGNOSTIC / ORIGINAL-ENTRY REPLAY**

Population:
- S10C cumulative SHORT selections: **329**
- strong WIN: **70**
- non-target: **259**

Best previously established protector:
> **V4.3 SHORT-LS4 + BE0.10 on the NO_ACTION lane**

Replay basis:
- original historical entry
- Binance USD-M historical aggTrades
- exact path replay
- 5-second V4.3 sampling
- frozen fee/slippage metadata
- BE only when V4.3 does not activate
- 256 symbol-date archive pairs
- 0 archive errors

## Full 329 result

| Policy | Wins | WR | PnL |
|---|---:|---:|---:|
| Historical actual | 82 | 24.92% | -$334.04 |
| V4.3 SHORT-LS4 | 132 | 40.12% | -$317.38 |
| **V4.3 SHORT-LS4 + BE0.10** | **126** | **38.30%** | **+$49.98** |

Delta of best composite:
- vs historical: **+$384.03**
- vs V4.3 standalone: **+$367.37**

Gross PnL under best composite:
- gross profit: **+$223.55**
- gross loss: **-$173.57**

## Strong 70

Historical:
- 66 positive
- WR 94.29%
- PnL **+$192.05**

V4.3:
- 68 positive
- WR 97.14%
- PnL **+$143.88**

V4.3 + BE0.10:
- 64 positive
- WR 91.43%
- PnL **+$141.49**

So the composite's system-level gain does not come from extracting more dollars from strong winners; it comes from suppressing non-target losses.

## Non-target 259

Historical:
- 16 positive
- PnL **-$526.09**

V4.3:
- 64 positive
- PnL **-$461.26**

V4.3 + BE0.10:
- 62 positive
- PnL **-$91.50**

Thus the composite reduces non-target loss by:

> **+$434.59 vs historical**

This is the dominant mechanism.

## Chronological split

### Discovery
Historical: -$194.98  
V4.3: -$173.24  
**V4.3 + BE0.10: +$72.30**

### Validation
Historical: -$36.45  
V4.3: -$27.61  
**V4.3 + BE0.10: +$8.75**

### Reserve
Historical: -$102.61  
V4.3: -$116.54  
**V4.3 + BE0.10: -$31.06**

The composite is positive in Discovery and Validation. Reserve remains negative, but improves by roughly **+$71.55** versus historical Reserve PnL.

## S10A vs S10C best-protector comparison

S10A 268 trades:
- V4.3 + BE0.10: **+$32.25**

S10C 329 trades:
- V4.3 + BE0.10: **+$49.98**

Increment from the S10C expansion:
> approximately **+$17.73**

Therefore the accepted S10C Lane-0 recovery layer is compatible with the current best protector and improves total PnL in the original-entry replay.

## Interpretation

1. S10C improves detector coverage from 51/99 to 70/99 and also improves protected total PnL.
2. The best protector remains V4.3 SHORT-LS4 + BE0.10.
3. Its main economic role is loss suppression on the 259 non-target trades, not stronger monetization of the 70 strong winners.
4. Validation is now positive under the best composite.
5. Reserve remains the unresolved weakness and prevents any production conclusion.
6. This is still original-entry replay. Execution-realistic delayed entry must remain a separate validation stage.
