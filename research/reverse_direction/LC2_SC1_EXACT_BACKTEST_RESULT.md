# LC-2 + SC-1 Exact Backtest Result

Status: **COMPLETE — both candidate routers fail economic backtest**

Date: 2026-10-06  
Authority: research only. No production trading state changed.

## Frozen universe

- resolved LONG universe: 1,236
- Binance archived aggTrades coverage: 1,235 / 1,236
- one raw-path-unavailable Unicode-symbol RIGHT_THEN_FAILURE trade excluded transparently
- notional: $500
- fee: 0.05% per side
- slippage: 2 bps per side
- holding window bounded by original historical close

---

## LC-2 — Confirm LONG, wait pullback, then BUY

Tested:
- LONG confirmation: +0.35 / +0.40 / +0.50%
- post-confirmation pullback from running post-confirm peak: 0.10 / 0.15 / 0.20 / 0.25%
- entry modes:
  - TOUCH: buy at first pullback touch
  - RECLAIM: after pullback, wait +0.05% rebound from post-pullback low
- fresh-entry SL: 0.30 / 0.40 / 0.50%
- no TP; fallback to original historical close

### Best LC-2 by WR

- confirm +0.35%
- pullback 0.10%
- TOUCH entry
- SL 0.50%
- entries: 567
- WR: **33.69%**
- net PnL: **-$234.72**
- PF: 0.76
- WD admitted: 21
- RTF admitted: 204
- Recovered admitted: 228
- Clean admitted: 69
- original-winner retention: 98.34%

### Best LC-2 by PnL

- confirm +0.50%
- pullback 0.15%
- TOUCH entry
- SL 0.30%
- entries: 491
- WR: 28.72%
- net PnL: **-$159.38**
- PF: 0.80
- WD admitted: 1
- Stall admitted: 3
- RTF admitted: **194**
- Recovered admitted: 228
- Clean admitted: 65
- original-winner retention: 97.02%

### LC-2 conclusion

Pullback entry materially improves the direct-confirmation LC-1 result, but remains negative.

The dominant residual problem is not wrong-direction leakage:
- at +0.50 confirmation, only 1 WD and 3 Stall remain,
- but 194 RIGHT_THEN_FAILURE trades still qualify.

Therefore:
**price confirmation + generic pullback cannot distinguish RTF from genuine winners.**

---

## SC-1 — Fail-down + persistence -> SHORT

Fixed replay contract:
- SHORT candidate only before LONG confirmation
- LONG confirmation block: +0.35 / +0.40%
- adverse trigger: -0.25 / -0.30 / -0.35%
- persistence: 30 / 60 / 75 seconds
- SHORT entry if price is still at/below adverse threshold at persistence expiry
- once SHORT entry occurs, TP/SL continue normally even if price later reaches the prior LONG-confirmation level
- TP: 0.30 to 0.80%
- SL: 0.50%

The first SC-1 implementation had an audit bug where TP/SL updates stopped after a post-entry LONG-confirmation touch. SC-1 was rerun with that bug fixed. The fixed results are unchanged in ranking and economics.

### Highest SC-1 WR

- LONG block +0.40%
- adverse -0.25%
- persistence 75s
- TP 0.30%
- SL 0.50%
- entries: 442
- WD: 323
- WD precision: 73.08%
- winner contamination: 39
- WR: **33.94%**
- net PnL: **-$334.52**
- PF: 0.23

### Best SC-1 PnL

- LONG block +0.40%
- adverse -0.35%
- persistence 75s
- TP 0.80%
- SL 0.50%
- entries: 248
- WD: 168
- WD precision: 67.74%
- winner contamination: 20
- WR: 27.42%
- net PnL: **-$151.24**
- PF: 0.44

### SC-1 conclusion

Simple fail-down + elapsed-time persistence is not sufficient to reproduce the profitable oracle 555-WD reverse result.

Even when the selected cohort is majority WD, selection occurs too late and/or mixes:
- Stall,
- RTF,
- Recovered winners,
- and WD trades whose remaining post-entry downside is already largely spent.

Thus:
**oracle WD reverse is profitable, but this causal WD selector is not.**

---

## Combined verdict

| Candidate | Best net PnL | Best WR | Verdict |
|---|---:|---:|---|
| LC-1 direct confirm BUY | -$392.78 | 27.05% | FAIL |
| LC-2 confirm + pullback BUY | **-$159.38** | **33.69%** | FAIL, improved |
| SC-1 adverse + persistence SHORT | **-$151.24** | **33.94%** | FAIL |
| Oracle exact 555 WD reverse | **+$691.46** | **89.55%** | Economic edge proven, not causal |

## Research implication

The next problem is no longer simple threshold tuning.

For LONG:
- need a dedicated **RIGHT_THEN_FAILURE rejection model** after direction is proven.

For SHORT:
- need a dedicated **early WD trajectory classifier** that detects remaining opposite-side opportunity, not merely adverse distance + elapsed time.

Do not forward-test LC-2 or SC-1 in current form.
