# PP V4-2C — Runner Preservation / Two-Regime Protection Contract

Status: **PREREGISTERED BEFORE REPLAY**

## Question

Can a causal two-regime protection overlay preserve the runner performance discovered in Stage2B while materially improving conversion of small/medium observable profits?

Stage2C is retrospective research only. It does not grant runtime authority.

## Frozen population

Use the same **99 Stage2A clean-label trades**.

Stage2C does **not** claim an untouched holdout because Stage2B already inspected EARLY/MID/LATE. Instead Stage2C requires chronological stability across all three frozen thirds and compares every hybrid against the two Stage2B reference regimes.

## Stage2B reference regimes

### Runner reference

`arm=1.50%, retain=90%, confirm=2`

Full-cohort diagnostic:
- total: +$75.96
- win rate: 37.37%
- runner >=1% median retention: 77.27%
- runner >=2% median retention: 82.46%

### Aggressive small-profit reference

`arm=0.50%, retain=60%, confirm=2`

Full-cohort diagnostic:
- total: +$28.22
- win rate: 56.57%
- runner >=1% median retention: 46.85%
- runner >=2% median retention: 46.56%

The purpose of Stage2C is to combine these strengths, not choose one of them.

## Hybrid state machine

The overlay has two modes.

### Mode A — small/medium profit protection

Before runner qualification, one **partial REDUCE** is allowed.

Candidate small-mode templates are frozen from Stage2B holdout-positive / frontier behavior:

1. `arm=0.50%, retain=60%, confirm=2`
2. `arm=0.50%, retain=60%, confirm=3`
3. `arm=0.75%, retain=80%, confirm=2`
4. `arm=0.75%, retain=90%, confirm=3`

When the small-mode condition triggers:
- reduce a fixed fraction of the then-remaining quantity;
- apply recorded paper slippage and exit fee;
- allocate entry fee proportionally;
- small mode cannot reduce a second time.

Reduction fractions:
- 25%
- 50%
- 75%

### Mode B — runner preservation

Runner mode activates permanently once the observed running gross peak reaches:

- +1.00%, or
- +1.50%.

Once runner mode activates:
- small-mode protection is disabled if it has not already fired;
- the remaining quantity uses runner trailing:
  - retain 90% of observed running peak;
  - confirmation = 2 consecutive ~5s observations.

The runner CLOSE trigger uses only observations available at that time.

## Counterfactual execution accounting

Historical actions before the **first overlay action** are preserved.

After the first overlay action:
- later historical REDUCE orders are ignored because counterfactual quantity has diverged;
- if runner CLOSE triggers, close all remaining quantity at that observation market price with recorded paper slippage/fee;
- if runner CLOSE never triggers, close the remaining counterfactual quantity at the historical final CLOSE fill price/time;
- entry fee is allocated exactly once across all exited quantity.

No market-impact model is added because the paper engine does not model market impact.

## Candidate grid

- 4 frozen small-mode templates
- 3 partial-reduce fractions
- 2 runner qualification levels

Total: **24 hybrid candidates**.

No additional hybrid thresholds may be added after results are seen.

## Evaluation

For every candidate report:

- total realized USD;
- delta vs historical actual;
- win rate;
- trigger counts:
  - small REDUCE count;
  - runner CLOSE count;
- observable-net-peak >=0.30–1.00% subgroup:
  - total USD;
  - win rate;
  - nonpositive count;
  - median retention;
- runner >=1%:
  - total USD;
  - median retention;
  - >=80% retention share;
  - nonpositive count;
- runner >=2%:
  - same metrics;
- chronological EARLY / MID / LATE total delta;
- number of trades helped / harmed by overlay.

## Balanced-pass gate

A hybrid is **balanced-pass** only if all are true:

1. full-cohort total realized USD > historical actual total;
2. full-cohort win rate > Stage2B runner reference win rate (37.37%);
3. runner >=1% median retention >= **72.27%**  
   (within 5 percentage points of the Stage2B runner reference);
4. runner >=2% median retention >= **77.46%**  
   (within 5 percentage points of the Stage2B runner reference);
5. small/medium observable-net-peak 0.30–1.00% nonpositive count is lower than the Stage2B runner reference;
6. EARLY, MID, and LATE each have positive USD delta versus historical actual.

## Research reference selection

Among balanced-pass candidates, rank by:

1. highest minimum chronological-third USD improvement;
2. then highest full-cohort total USD;
3. then highest win rate.

This favors stability over one-period optimization.

Stage2C may name a research reference but may not deploy it.

## Decision

Proceed to V4-2D full replay / prospective-shadow specification if:
- at least one balanced-pass candidate exists;
- it preserves runner retention while improving small/medium conversion;
- improvement is positive in all three chronological thirds.

Otherwise return to protection-state-machine design.

## Restrictions

- no runtime change;
- no protection authority;
- no live change;
- no future MFE in triggers;
- no second small-mode reduction;
- no grid expansion after results.
