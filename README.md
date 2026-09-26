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
- fetches the newest **closed 5m candle** for every symbol
- captures 5m OHLC, volume, quote volume, trade count, and taker-buy volume
- attaches 24h quote volume and 24h price change as raw market context
- runs on the next UTC 5-minute candle boundary + configurable close-confirmation offset
- isolates per-symbol failures so one bad market does not abort the full scan
- writes `data/latest_scan.json` atomically
- public Binance endpoints only; no API key required

Not implemented yet (by design):

- moving-coin detection
- `IGNITION / EXPANSION / EXHAUSTION`
- `LONG_SCORE / SHORT_SCORE`
- OI/funding/regime context
- `LONG / SHORT / NO TRADE`
- MCP/dashboard/alerts/execution

Those belong to later frozen blueprint stages.

## Run Stage 1 once

```bash
python -m pip install -r requirements.txt
python -m market_radar --once
```

Machine-readable console output:

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
