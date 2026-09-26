# BabaBot Market Radar

Standalone live **Moving Coin Detector (MCD) product**. It has **zero runtime dependency** on `bymarfinai/bababot-discovery`.

The frozen product blueprint is in [`BLUEPRINT.md`](BLUEPRINT.md).

## Development status

### Stage 1 — COMPLETE

Frozen requirement:

> Scan all Binance USDT perpetual markets every ±5 minutes.

Implemented:

- discovers **all** `TRADING + USDT + PERPETUAL` USD-M Futures symbols from Binance `exchangeInfo`
- no top-gainer, momentum, volume, or liquidity pre-filter
- fetches closed 5m history for every symbol
- captures 5m OHLC, volume, quote volume, trade count, and taker-buy volume
- attaches 24h quote volume and 24h price change as raw market context
- runs on the next UTC 5-minute candle boundary + configurable close-confirmation offset
- isolates per-symbol failures so one bad market does not abort the full scan
- writes `data/latest_scan.json` atomically
- public Binance endpoints only; no API key required

### Stage 2 — COMPLETE

Frozen requirement:

> Detect coin yang mulai bergerak.

Implemented:

- evaluates movement from **closed 5m candles only**
- compares each symbol against its **own previous 20-bar baseline**
- measures:
  - 5m return expansion
  - 5m quote-volume expansion
  - true-range expansion
  - trade-count expansion
  - recent directional persistence
- applies an absolute 5m-return floor to avoid false positives from nearly-flat baselines
- preserves newly listed markets in the full Stage 1 scan even when they do not yet have enough history
- emits Stage 2 movement states:
  - `NOISE`
  - `NORMAL`
  - `EARLY_MOVEMENT`
  - `STRONG_CONTINUATION`
  - `LATE_MOVEMENT`
- emits only raw `UP / DOWN / FLAT` direction hints
- **does not** emit LONG/SHORT trade decisions or Stage 3 labels

Stage 2 candidate output includes:

```text
symbol
movement_state
direction_hint
ret_5m / ret_15m / ret_1h / ret_24h
return expansion ratio
volume ratio
range ratio
trade-count ratio
directional persistence
evidence count
reasons
```

### Stage 3 — COMPLETE

Frozen requirement:

> Classify `IGNITION / EXPANSION / EXHAUSTION`.

Stage 3 is a deterministic downstream classification of Stage 2 movement:

```text
EARLY_MOVEMENT
→ IGNITION

STRONG_CONTINUATION
→ EXPANSION

LATE_MOVEMENT
→ EXHAUSTION
```

`NOISE` and `NORMAL` remain outside the movement-stage pipeline and receive no Stage 3 label.

Important scope boundary:

- `IGNITION / EXPANSION / EXHAUSTION` describe the **phase of detected movement**
- `UP / DOWN / FLAT` remains only a raw price-direction hint
- no `LONG_SCORE`
- no `SHORT_SCORE`
- no `LONG / SHORT / NO TRADE` decision yet

The scanner also reports per-cycle counts for:

```text
IGNITION
EXPANSION
EXHAUSTION
```

### Stage 4 — COMPLETE

Frozen requirement:

> Calculate independent `LONG_SCORE / SHORT_SCORE`.

Implemented:

- every moving candidate receives two independent scores on a `0–100` scale
- scores are **not complements** and are not forced to sum to 100
- positive `score_gap = LONG_SCORE - SHORT_SCORE`
- `score_edge = abs(score_gap)`
- scoring uses only evidence already available from Stage 2/3:
  - signed 5m momentum
  - signed 15m momentum
  - signed 1h momentum
  - short-term acceleration
  - movement/return expansion
  - existing volume expansion ratio
  - existing range expansion ratio
  - existing trade-count expansion ratio
  - directional persistence
  - multi-timeframe directional consistency
- component breakdown is retained separately for LONG and SHORT for auditability

Important scope boundary:

```text
Stage 4 DOES NOT read:
breakout / breakdown
taker flow
open interest
funding
market regime
```

Those remain frozen for Stage 5.

Stage 4 also **does not** output `LONG / SHORT / NO TRADE`. A higher score is evidence, not yet an execution decision.

Still not implemented yet (by design):

- breakout/taker/OI/funding/regime context — Stage 5
- `LONG / SHORT / NO TRADE` — Stage 6
- MCP — Stage 7
- dashboard/alerts — Stage 8
- execution — Stage 9

## Run once

```bash
python -m pip install -r requirements.txt
python -m market_radar --once
```

Machine-readable output:

```bash
python -m market_radar --once --json
```

Continuous 5-minute boundary scanner:

```bash
python -m market_radar
```

## Tests

```bash
python -m unittest discover -s tests -v
```
