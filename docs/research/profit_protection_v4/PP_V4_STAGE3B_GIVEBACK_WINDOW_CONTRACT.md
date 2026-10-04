# PP V4-3B — Giveback Window Anatomy Contract

Status: **PREREGISTERED BEFORE RESULT INSPECTION**

## Objective

Measure the causal time window available after an observed running peak begins to give back, before profit falls through 95%, 90%, 85%, 80%, and 75% of that running peak.

Stage3B is anatomy only. It does not tune or deploy a new protection rule.

## Population

Primary analysis:
- all 62 historical trades where Profit Protector V4.2 Hybrid actually fired;
- preserve labels for:
  - 56 active failures with final protected retention <75% of true clean MFE;
  - 6 controls with final protected retention >=75%.

Secondary context:
- the 108 positive-MFE NO_ACTION trades remain out of the giveback-window timing analysis because their archived observed peak never reached the current +0.50% arm.

## Data source

Use only archived historical 5s observations already available to V4.2 replay.

True clean MFE is an evaluation label only. It must never be used to generate a causal crossing or decision.

## Giveback episode definition

For each trade, scan archived 5s observations chronologically.

A running peak is the highest observed gross PnL seen so far.

For each giveback level L in:
- 95%
- 90%
- 85%
- 80%
- 75%

record the first time current observed PnL falls to or below L × the then-current positive running peak.

Each threshold crossing is labelled:

- **RECOVERED_NEW_HIGH** if a later archived observation exceeds the running peak that existed at the crossing, before trade close.
- **FINAL_REVERSAL** if no later observation exceeds that peak.

A crossing is causal: its label may use future data for retrospective anatomy, but the crossing itself uses only data known at that timestamp.

## Required measurements

Per crossing:
- position_id, symbol, side;
- Stage3A class and failure/control label;
- threshold;
- running peak PnL at crossing;
- running peak timestamp;
- crossing timestamp;
- seconds from peak to crossing;
- current PnL at crossing;
- giveback depth;
- RECOVERED_NEW_HIGH or FINAL_REVERSAL;
- if recovered: seconds from crossing to new high;
- if final reversal: seconds from crossing to historical close.

Per trade final-peak path:
- highest archived 5s observed peak;
- timestamp of that peak;
- first post-final-peak crossing of 95/90/85/80/75%;
- seconds from final observed peak to each crossing;
- whether each threshold was reached before the V4.2 protection action;
- V4.2 first overlay timestamp;
- runner-close timestamp where applicable.

## Aggregate questions

For each threshold:
1. how many triggered trades ever cross it;
2. how often an early crossing later recovers to a new high (false-exit risk);
3. how often it belongs to the final reversal;
4. median/p25/p75 seconds from running peak to crossing;
5. median recovery time for transient pullbacks;
6. on final reversal, median time available between 95→90→85→80→75.

Break down by:
- Stage3A failure class;
- true-MFE band;
- failure vs >=75% control;
- runner vs REDUCE25-only action path.

## Stage3B decision rule

Stage3B must identify whether there is a temporal separation between:
- transient givebacks that recover to a new high, and
- final reversals that continue through the protection floor.

It may nominate candidate causal features for V4-3C, but it must not choose/tune a final trading rule.

## Restrictions

- historical real data only;
- no prospective/paper test;
- no runtime change;
- no parameter optimization;
- no future true MFE in live decision features;
- no claim that final peak is knowable in real time.
