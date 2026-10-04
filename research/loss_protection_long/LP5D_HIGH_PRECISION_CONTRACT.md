# LP-5D — High-Precision 75–90s Protector Discovery Contract

Status: **PREREGISTERED — no LP-5D result inspected at freeze time.**

## Frozen scope

Universe: current Stage 3C.7A **454 LONG OPEN** cohort.

Priority target:
- actual realized non-positive;
- historical max MFE < +0.50%;
- frozen count: **120 PRE-0.5 losses**;
- **96 WRONG_DIRECTION** trades are tracked as the highest-value subgroup.

Controls:
- **176 actual realized-positive trades** from the same operational cohort.

Decision timestamps are restricted to exactly:
- **75s**
- **80s**
- **85s**
- **90s**

A trade is eligible only if its historical close is strictly after the decision timestamp.

## Causal features

Only path information observable by the decision time may be used:
1. current side return;
2. running MFE;
3. running MAE.

No final MFE, final MAE, future return, final path label, or post-decision information may enter a rule.

## Candidate families

At each frozen timestamp, Development may generate:

1. **SIDE** — current side return <= threshold.
2. **MFE** — running MFE <= threshold.
3. **SIDE_AND_MFE** — current side return <= threshold AND running MFE <= threshold.
4. **LOGIT3** — logistic score from side return + running MFE + running MAE, fit on Development only; only its score threshold is swept.

All threshold values and logistic weights are learned from Development only.

## Development hard gates

A candidate survives Development only when all are true:
- PRE-0.5 precision >= **80%**;
- actual-winner fire rate <= **5%** of alive Development winners;
- captures at least **10%** of alive Development PRE-0.5 losses;
- fires on at least **5** Development trades.

For each timestamp/family, only the single best Development candidate is carried to Validation, ranked by:
1. PRE-0.5 captured count;
2. higher precision;
3. lower winner fire rate;
4. earlier timestamp / simpler family.

## Validation screening

A frozen Development candidate survives Validation only when all are true:
- PRE-0.5 precision >= **70%**;
- actual-winner fire rate <= **5%** of alive Validation winners;
- captures at least **10%** of alive Validation PRE-0.5 losses;
- at least **3** Validation fires.

The final LP-5D candidate is selected using Development + Validation only, ranked by:
1. Validation PRE-0.5 captured count;
2. Validation precision;
3. Development PRE-0.5 captured count;
4. earlier timestamp;
5. simpler family.

## Sealed Reserve gate

Reserve is evaluated exactly once for the final frozen candidate.

PASS requires:
- PRE-0.5 precision >= **70%**;
- actual-winner fire rate <= **5%** of alive Reserve winners;
- PRE-0.5 recall >= **10%** of alive Reserve PRE-0.5 losses;
- exact archive execution replay has **positive Reserve PnL delta**;
- no more than **1** historical Reserve winner is converted to non-positive.

## Execution replay

For the final candidate only:
- decision time = frozen 75/80/85/90s boundary;
- execution = first Binance USD-M archived aggregate trade strictly after decision and no later than historical close;
- preserve historical executed actions through protector execution;
- close all remaining quantity using stored slippage and fees;
- ignore later historical actions after divergence;
- non-executable trades remain unchanged.

No production or paper-trading authority is granted by LP-5D discovery alone.