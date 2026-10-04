# PP V4-2A — Observable Peak → Realized Leakage Anatomy Contract

Status: **PREREGISTERED BEFORE ANALYSIS**

## Question

Once the ~5-second observer has actually seen favorable profit, how much of that observable profit is ultimately retained in realized paper PnL, when does giveback begin, and which trade groups lose the most?

This stage is descriptive/anatomical only. It does not define or promote a protection rule.

## Frozen population

Use the Stage1J clean-label cohort:

- strict matched 5s/15s historical coverage;
- clean post-entry MFE >= +0.30%;
- frozen source: `research/profit_protection_v4/results/stage1j_clean_post_entry_mfe_evidence.json`.

Expected cohort size: **99 trades**.

No trade may be added or removed based on realized outcome or leakage.

## Price / PnL definitions

### Observable gross peak

For each trade:

- use archived `pp_v3_fast_peak_observations`;
- restrict observations to the position lifetime;
- observable gross peak = maximum `current_pnl_pct`;
- observable peak timestamp = earliest observation timestamp reaching that maximum;
- peak market price = the archived `current_price` at that observation.

This is historical ~5s information actually available to the observer.

### Executable-net observable peak proxy

Raw `current_pnl_pct` excludes exit friction, while `positions.realized_pnl_pct` is paper net PnL.

To avoid overstating leakage, also calculate a hypothetical **full close at the observed 5s peak market price** using the same paper execution assumptions recorded on the position:

- initial entry fill already embedded in `entry_price`;
- initial quantity from position metadata;
- entry fee from position metadata;
- adverse exit slippage from recorded `slippage_bps`;
- exit fee from recorded `fee_rate`;
- denominator = recorded initial notional.

The result is `observable_net_peak_pct`.

This is an executable-paper proxy, not a claim that an order could have filled exactly at the observation timestamp.

### Realized outcome

Use `positions.realized_pnl_pct`.

This is net paper PnL after actual executed REDUCE/CLOSE actions, fees, and slippage.

## Primary leakage metrics

For every trade with observable net peak > 0:

- `leakage_pp = observable_net_peak_pct - realized_pnl_pct`;
- `retention_ratio = realized_pnl_pct / observable_net_peak_pct`.

Report retention without clipping. Negative retention is meaningful: observed profit became a realized loss.

Primary distribution:

- median retention;
- mean retention;
- P10 / P25 retention;
- share retention >=90%;
- share retention >=80%;
- share retention 50–80%;
- share retention 0–50%;
- share retention <0%;
- median and aggregate leakage in percentage points.

Also report raw gross-peak-to-realized leakage separately for transparency.

## Giveback timing

Using only archived ~5s observations after the observable peak:

For positive observable gross peaks, measure the first timestamp where current PnL falls to or below:

- 90% of observable peak;
- 80%;
- 70%;
- 50%;
- 0% / breakeven.

For each threshold report:

- trades that cross it before close;
- median seconds from observed peak to first crossing;
- P25 / P75 seconds from peak to crossing;
- median seconds remaining from threshold crossing to actual close.

Also report:

- observed-peak → close duration;
- observed-peak age from entry;
- nearest archived 5s PnL before close.

## Anatomy splits

Report the same core retention/leakage metrics by:

### Side
- LONG
- SHORT

### Clean MFE band
- 0.30–0.50%
- 0.50–1.00%
- 1.00–2.00%
- >=2.00%

### Observable net peak band
- <=0%
- 0–0.30%
- 0.30–0.50%
- 0.50–1.00%
- 1.00–2.00%
- >=2.00%

### Runner groups
- observable net peak >=1.00%
- observable net peak >=2.00%

### Close reason
Group by actual `positions.close_reason`.

## Missed-profit severity

Explicitly count:

- observable net peak >=0.30% but realized <=0%;
- observable net peak >=0.50% but realized <=0%;
- observable net peak >=1.00% but realized <=0%;
- observable net peak >=2.00% but realized <=0%;
- realized retention <50% after observable net peak >=0.50%;
- realized retention <80% after observable net peak >=0.50%.

Rank at least the top 20 trades by net leakage percentage points.

## Stage decision output

Stage2A must answer only:

1. Is observable-profit leakage materially larger than the remaining observability gap?
2. At what observable-peak bands is leakage most severe?
3. How quickly does giveback occur after a peak is seen?
4. Are LONG / SHORT / runner groups materially different?
5. Is there enough evidence to proceed to **V4-2B — Optimal Protection Frontier**?

No protection threshold is selected in Stage2A.

## Restrictions

- no future-MFE input into protection decisions;
- no tuning of REDUCE/CLOSE rules;
- no runtime change;
- no trading authority;
- no event-driven deployment;
- no exclusion of bad outcomes after seeing results.
