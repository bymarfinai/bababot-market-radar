# PP V4 — High-Frequency Peak Capture Contract

Status: **FROZEN DESIGN CONTRACT — NOT ACTIVE**

Canonical source of truth: `PP_DECISION_V4.md`

## Purpose

This contract defines how the next peak-capture research track must be built before any new collector or protection mechanism is enabled.

The old 15-second low-tail track and the 5-second Stage 2B.1 shadow lane are retired. V4 must not reactivate them by renaming old runtime code.

## Architecture boundary

V4 must expose exactly one canonical causal price-observation stream.

Conceptually:

```text
market-data source(s)
        ↓
timestamp / provenance normalization
        ↓
duplicate + disagreement handling
        ↓
ONE canonical V4 executable-price stream
        ↓
observability metrics
        ↓
ONLY AFTER GATE PASS:
protection / runner logic
```

Multiple upstream APIs may be used for resilience or verification, but downstream peak state must not be maintained independently by multiple competing observers.

## V4-1 implementation prerequisites

Before any future activation commit, freeze:

1. canonical observation schema;
2. primary and fallback market-data sources;
3. provider disagreement rule;
4. timestamp source and clock-skew handling;
5. duplicate suppression key;
6. reconnect/gap behavior;
7. polling/event cadence;
8. prospective start boundary;
9. storage table/schema;
10. matched-trade evaluation protocol;
11. minimum sample gate;
12. minimum effect-size gates.

None of these are activated by Step 3.

## Canonical observation schema — planned

A future V4 observation should minimally contain:

- observation_id;
- position_id;
- opened_at_ms;
- observed_at_ms;
- source_event_at_ms when supplied by provider;
- receive_at_ms;
- symbol;
- side;
- entry_price;
- current_price;
- current_pnl_pct;
- running_observed_peak_pct;
- running_observed_peak_at_ms;
- delta_pnl_pct_points;
- sample_gap_ms;
- source_name;
- source_mode (PRIMARY/FALLBACK);
- source_sequence or event id when available;
- data_quality flags;
- position_status.

No true-MFE or terminal label belongs in runtime rows.

## Benchmark contract

Each closed matched trade will eventually compare:

1. V4 high-frequency observable peak;
2. historical/comparable ~15s observable peak;
3. offline true MFE.

The comparison must be same-trade whenever possible.

Do not compare different trade populations and call the difference a cadence effect.

## Metrics

Mandatory:
- N matched;
- mean capture;
- median capture;
- weighted capture when valid;
- P10;
- P25;
- >=80% share;
- >=90% share;
- >=95% share;
- <80% share;
- missing-data rate;
- cadence P10/P50/P90;
- max observation gap;
- early/mid/late chronological thirds.

Diagnostics:
- LONG vs SHORT;
- MFE magnitude bands;
- volatility/range bands;
- duration bands;
- early-spike vs late-peak trades.

## No-protection rule

V4-1 through V4-3 are information-layer research only.

They may:
- observe;
- persist;
- compare;
- label offline;
- diagnose.

They may not:
- REDUCE;
- CLOSE;
- submit paper exits;
- submit live exits;
- change Stage 12 thresholds;
- change current Stage 12 fast cadence.

## Failure conditions

Stop the track before protection engineering if:
- high-frequency observations do not materially improve lower-tail distribution;
- improvement exists only in median but not P10/P25 or <80%;
- apparent improvement comes from dropping hard trades with missing data;
- chronological late cohort collapses;
- provider disagreement/timestamp quality prevents a trustworthy matched comparison.

## Archived evidence

V3 references:
- `research/profit_protection_v3/archive/low_tail_15s/ARCHIVE.md`
- `research/profit_protection_v3/archive/stage2b1_5s_shadow/ARCHIVE.md`

These are comparison evidence only.
