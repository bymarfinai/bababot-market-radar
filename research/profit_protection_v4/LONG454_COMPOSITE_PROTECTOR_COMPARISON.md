# LONG 454 — Profit Protector Composite Comparison

Status: **DIAGNOSTIC / ORIGINAL-ENTRY ARCHIVE REPLAY**

Population: frozen Stage 3C.7A LONG OPEN cohort, **454 trades**.

Authoritative baselines:
- historical actual: 176 wins, 38.77%, +$62.53
- V4.2 Hybrid archive-5s: 177 wins, 38.99%, -$25.69
- SL -1% / TP +1%: 177 wins, 38.99%, +$53.61
- V4.3 LONG Stage3C7A: 247 wins, 54.41%, +$200.48

Composite contract:
- use authoritative V4.2 / V4.3 trade-level settlement;
- only trades whose authoritative V4.2 action is HIST_TIME_FALLBACK / NO_ACTION are eligible for causal net-BE;
- active V4.2 or V4.3 protector actions retain authority;
- BE arms are prior research frontier values, not newly tuned parameters;
- Binance USD-M historical aggTrades; 176 NO_ACTION symbol-date archive pairs; 0 archive errors.

## Composite results

| Policy | Wins | WR | PnL |
|---|---:|---:|---:|
| V4.2 + BE0.10 | 162 | 35.68% | +$267.86 |
| V4.2 + BE0.18 | 162 | 35.68% | +$264.33 |
| V4.2 + BE0.25 | 167 | 36.78% | +$197.94 |
| **V4.3 + BE0.10** | **232** | **51.10%** | **+$494.02** |
| **V4.3 + BE0.18** | **232** | **51.10%** | **+$490.50** |
| V4.3 + BE0.25 | 237 | 52.20% | +$424.11 |

Best total-PnL diagnostic:
- **V4.3 + BE0.10 = +$494.02**

Delta:
- vs historical: **+$431.49**
- vs V4.3 standalone: **+$293.54**
- vs V4.2 standalone: **+$519.71**

Interpretation:
- BE is valuable only as a NO_ACTION loss-management layer, not as a universal exit;
- V4.3 remains the active-profit conversion layer;
- V4.3+BE0.10/0.18 is the strongest current original-entry diagnostic frontier on the frozen LONG454 cohort;
- WR is lower than V4.3 standalone because many losing trades are cut near break-even rather than converted into positive winners, while total dollar PnL improves sharply.

This is not production authority. Chronological validation and execution-realistic integration remain separate.
