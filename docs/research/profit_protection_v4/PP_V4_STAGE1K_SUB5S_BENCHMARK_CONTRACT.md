# PP V4-1K — Clean Residual Sub-5s Benchmark Contract

Status: **PREREGISTERED BEFORE RUN**

## Question

For the clean Stage1J residual lower tail, does periodic 2-second or 1-second current-price observation materially recover favorable excursions missed by the archived ~5-second observer, or is event-driven/tick observation required?

## Frozen population

Use only Stage1J clean-label trades satisfying:

- strict matched 5s + 15s lifecycle coverage;
- clean post-entry MFE >= +0.30%;
- archived actual 5s capture <80%.

Population is frozen at **24 trades** from:
`research/profit_protection_v4/results/stage1j_clean_post_entry_mfe_evidence.json`.

This population must match the 24 genuine residual trades from Stage1I.

## Historical price source

Binance USD-M Futures public market data.

For each position:

- clean MFE remains the Stage1J post-entry traded-price benchmark;
- full 1m klines identify only minutes capable of beating the archived 5s observed peak;
- aggregate trades are fetched for those candidate minutes;
- entry and exit boundary minutes are clipped to the actual position lifetime.

## Periodic polling simulation

Offline counterfactual only. No runtime authority.

Cadences:
- 5,000 ms diagnostic;
- 2,000 ms candidate;
- 1,000 ms candidate.

Polling phase must not be cherry-picked.

For each cadence, simulate all phase offsets on a **100 ms grid**:
- 5s: 50 offsets;
- 2s: 20 offsets;
- 1s: 10 offsets.

For a sample timestamp, the observable price is the latest aggregate-trade price available at or before that timestamp. No future trade may be used.

Primary outputs per cadence:
- probability across phase offsets of capture >=80%;
- probability across phase offsets of capture >=90%;
- probability across phase offsets of capture >=95%;
- median capture across phase offsets;
- P10 capture across phase offsets.

Event-driven/tick is reported only as an **observability upper bound**. It sees every historical aggregate trade and therefore can observe the clean MFE peak; this is not an execution-PnL claim.

## Decision rule

Current clean Stage1J lower tail:

`24 / 99 = 24.24%`.

To compress the overall clean <80% share to <=10%, at least **15 of the 24 residual trades** must be rescued to >=80%.

For periodic cadence selection:

1. Compute each trade's phase-averaged probability of reaching >=80%.
2. Sum those probabilities to obtain expected residual rescues.
3. Convert expected rescues to projected overall <80% share out of the fixed 99 clean-eligible trades.
4. Prefer the **slowest** cadence that projects <=10% overall <80%.
5. If neither 2s nor 1s meets the target, periodic polling is insufficient and event-driven observation becomes the next research candidate.

Secondary diagnostics:
- >=90 rescue;
- LONG vs SHORT;
- phase sensitivity;
- trades that remain difficult even at 1s.

## Restrictions

- no protection formula tuning;
- no exit authority;
- no synthetic future interpolation;
- no best-phase-only conclusion;
- no change to live trading;
- active V4 5s observer remains research-only.
