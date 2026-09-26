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

### Stage 5 — COMPLETE

Frozen requirement:

> Read volume, breakout/breakdown, taker flow, raw OI, funding, and existing market regime.

Implemented candidate context:

- **Volume**
  - current closed 5m quote volume
  - 24h quote volume
  - relative 5m volume ratio vs the symbol's own baseline
  - volume-confirmation flag
- **Breakout / breakdown**
  - previous 20 closed 5m high / low
  - confirmed `BREAKOUT`
  - confirmed `BREAKDOWN`
  - `FAILED_BREAKOUT`
  - `FAILED_BREAKDOWN`
  - `FAILED_BOTH_SIDES`
  - `NO_STRUCTURAL_BREAK`
- **Taker flow**
  - read directly from the exact closed 5m Binance kline used by the detector
  - taker-buy quote volume
  - derived taker-sell quote volume
  - buy/sell ratio
  - buy share
  - `BUY / SELL / BALANCED` bias
- **Raw Open Interest**
  - Binance `sumOpenInterest` only
  - `sumOpenInterestValue` is intentionally ignored
  - causal OI timestamp filtering
  - raw OI change %
  - context interpretation:
    - price up + OI up → fresh long participation
    - price up + OI down → short covering
    - price down + OI up → fresh short participation
    - price down + OI down → long liquidation
- **Funding**
  - current Binance `lastFundingRate`
- **Existing market regime**
  - existing causal BabaBot Discovery B27AG 4H `SwingRegime(lookback=5, swing_atr=0.5)` semantics ported into this repo
  - `BULL`: HH>=2 + HL>=2 + EMA7>EMA20 + completed close>EMA20
  - `BEAR`: LH>=2 + LL>=2 + EMA7<EMA20 + completed close<EMA20
  - otherwise `SIDEWAYS`
  - only completed 4H bars are admitted
  - Market Radar never calls Discovery at runtime

Additional OI/funding/regime API calls are made **only for moving candidates**, while Stage 1 continues scanning the full Binance USDT-perpetual universe.

Stage 5 is context only. It does **not** change Stage 4 scores and does **not** output a final trade decision.

### Stage 6 — COMPLETE

Frozen requirement:

> Output final `LONG / SHORT / NO TRADE`.

Stage 6 is deterministic and runs only after Stage 5 context has been attached.

Base score gates preserve the existing MCD prototype defaults:

```text
winning directional score >= 68
score edge vs opposite side >= 10
```

Decision flow:

```text
moving candidate
→ valid IGNITION / EXPANSION / EXHAUSTION
→ EXHAUSTION = NO TRADE
→ choose higher LONG_SCORE or SHORT_SCORE as candidate side
→ require score >=68
→ require edge >=10
→ require complete OI + funding + regime context
→ evaluate context confirmations and conflicts
→ reject confirmed structural break against the candidate side
→ require positive context balance
→ LONG / SHORT / NO TRADE
```

Context voting:

- volume expansion can confirm either directional candidate
- aligned confirmed breakout/breakdown confirms
- failed opposite-side break can confirm a reclaim/rejection
- aligned taker bias confirms; opposite taker bias conflicts
- fresh raw-OI participation aligned with the proposed direction confirms
- fresh raw-OI participation against the proposed direction conflicts
- aligned 4H regime confirms; opposite regime conflicts; SIDEWAYS is neutral
- funding is retained and exposed as positioning context but does **not** independently trigger or veto a trade

Stage-specific confirmation gate:

```text
IGNITION  : minimum 2 context confirmations
EXPANSION : minimum 1 context confirmation
EXHAUSTION: always NO TRADE
```

A moving candidate that fails any gate receives `NO TRADE` with explicit `decision_reasons`.

Final candidate output now includes:

```text
decision
decision_side_candidate
decision_context_confirmations
decision_context_conflicts
decision_context_balance
decision_reasons
decision_version
```

Per scan, Market Radar also reports:

```text
LONG count
SHORT count
NO TRADE count
```

Still not implemented yet (by design):

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
