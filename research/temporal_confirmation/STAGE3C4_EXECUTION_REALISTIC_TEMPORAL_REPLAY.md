# Stage 3C.4 — Execution-Realistic Temporal Replay

## Frozen policy

Flow-Aligned LONG only.

The T+3 confirmation rule is **not re-tuned**:

`temporal__t3_confirm_side_return_pct >= 0.158514%`

Execution approximation:
- decision occurs at the T+3 target timestamp
- entry is the **open of the first complete 1-minute bar strictly after that timestamp**
- if the historical position had already closed before that executable bar, the trade is **no executable entry**
- post-entry MFE / MAE are recomputed from Binance USD-M 1-minute bars

## OOS execution set

Validation:
- Stage 3C.3 selected: **30**
- no executable delayed entry: **4**
- executable: **26**
- original strong targets among executable: **15**

Reserve:
- Stage 3C.3 selected: **26**
- no executable delayed entry: **2**
- executable: **24**
- original strong targets among executable: **11**

All no-executable OOS trades were original META_LOSS rows.

## Does >=1% opportunity remain after waiting?

Validation:
- strong targets retaining delayed MFE >=1%: **11/15 = 73.3%**
- losses reaching delayed MFE >=1%: **1/11**
- capture relative to all 24 T+3-eligible strong targets: **11/24 = 45.8%**

Reserve:
- strong targets retaining delayed MFE >=1%: **7/11 = 63.6%**
- losses reaching delayed MFE >=1%: **0/13**
- capture relative to all 24 T+3-eligible strong targets: **7/24 = 29.2%**

## Post-entry separation

Median delayed MFE:
- Validation target: **1.273%**
- Validation loss: **0.080%**
- Reserve target: **1.417%**
- Reserve loss: **0.349%**

Median delayed MAE:
- Validation target: **-0.093%**
- Validation loss: **-0.591%**
- Reserve target: **-0.111%**
- Reserve loss: **-0.399%**

## Realized economics caveat

Exact old exit fills are intraminute and not preserved in the frozen research rows, so two exit conventions are reported.

### Exit-equivalent method
- Validation: **$-23.75**, avg **-0.183%/trade**
- Reserve: **$-18.27**, avg **-0.152%/trade**

### 1-minute bar-close sensitivity
- Validation: **$1.27**, avg **0.010%/trade**
- Reserve: **$4.62**, avg **0.039%/trade**

Median absolute difference between exit proxies:
- Validation: **0.259%**
- Reserve: **0.180%**

The difference is large enough to flip the sign of aggregate PnL. Profitability is therefore **inconclusive**, not proven.

## Verdict

**Stage 3C.4 = PARTIAL PASS.**

Pass:
- delayed T+3 entry still leaves meaningful favorable excursion
- Validation: **11/15** selected strong targets retain +1% MFE after delayed entry
- Reserve: **7/11** retain +1%
- Reserve false positives reaching +1% after entry: **0/13**

Fail / unresolved:
- execution-realistic Reserve capture is only **7/24 = 29.2%** of all T+3-eligible strong targets
- conservative exit-equivalent economics are negative
- exact realized economics cannot be established without exact intraminute execution data or a fresh forward replay

No production promotion.
