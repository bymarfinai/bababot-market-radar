# BabaBot Market Radar — MCP Interface

Status: **Stage 7 COMPLETE**

## Final architecture

Stage 7 is implemented directly inside the standalone Market Radar service.

```text
Market Radar deterministic engine
        ↓
latest_scan.json
        ↓
read-only HTTP + MCP interface
        ↓
AI / MCP client inspection
```

This keeps Market Radar runtime-independent from BabaBot Discovery and avoids
creating another calculation engine.

The existing BabaBot MCP Worker is not modified and is not required for Market
Radar to operate.

## MCP endpoint

```text
POST /mcp
```

Production service:

```text
https://market-radar-production-d307.up.railway.app/mcp
```

The implementation supports the MCP handshake-era protocol revision:

```text
2025-11-25
```

The server is stateless. Tool calls read the latest deterministic radar snapshot
from disk.

## Tools

Exactly three read-only tools are exposed.

### get_market_radar

Arguments: none.

Returns:

- latest scan timestamps
- market universe/completion counts
- candidate counts
- IGNITION / EXPANSION / EXHAUSTION counts
- LONG / SHORT / NO TRADE counts
- compact current candidate list

### get_moving_coins

Optional arguments:

```text
decision = LONG | SHORT | NO TRADE
stage    = IGNITION | EXPANSION | EXHAUSTION
```

Returns the current moving candidates after optional filtering.

### inspect_symbol

Required argument:

```text
symbol
```

If the symbol is currently moving, returns:

- stage
- final decision
- LONG_SCORE / SHORT_SCORE
- score gap / edge
- movement returns
- volume ratio
- breakout/breakdown context
- taker context
- raw OI context
- funding
- market regime
- decision reasons

If the symbol is not currently moving, returns the latest basic Stage 1 snapshot.

## Non-MCP read endpoints

```text
GET /health
GET /radar/latest
GET /radar/candidates
GET /radar/symbol/{symbol}
```

These endpoints expose the same deterministic output for dashboard/operational use.

## Scope boundary

The MCP layer does **not**:

- rescan Binance
- calculate movement state
- classify IGNITION / EXPANSION / EXHAUSTION
- recalculate LONG_SCORE / SHORT_SCORE
- reinterpret Open Interest
- calculate market regime
- change LONG / SHORT / NO TRADE
- execute orders

All calculations remain inside Stage 1–6. MCP is read-only inspection only.

## Runtime

Railway service:

```text
market-radar
```

Start command:

```text
python -m market_radar --serve
```

MCP and the ordinary read API run in the same service/process boundary as a
small read-only server thread. The scanner itself remains on its existing
5-minute closed-candle scheduler.
