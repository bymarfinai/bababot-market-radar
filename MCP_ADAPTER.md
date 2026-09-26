# BabaBot Market Radar — MCP Adapter Contract

Status: Stage 7 integration contract.

This document intentionally keeps the MCP layer thin.

## Principle

The existing BabaBot MCP must **not** duplicate any Market Radar logic.

MCP only reads deterministic Market Radar output.

```text
Market Radar
    ↓
read-only HTTP API
    ↓
existing BabaBot MCP
    ↓
AI inspection
```

The MCP layer must not:

- rescan Binance
- calculate movement stage
- recalculate LONG_SCORE / SHORT_SCORE
- reinterpret Open Interest
- calculate regime
- change LONG / SHORT / NO TRADE
- execute orders

## Minimal tool set

Only three read-only tools are required.

### 1. get_market_radar

Purpose: retrieve the latest compact radar state.

Backend:

```text
GET /radar/latest
```

Arguments: none.

### 2. get_moving_coins

Purpose: list current moving candidates.

Backend:

```text
GET /radar/candidates
```

Optional filters:

```text
decision=LONG|SHORT|NO_TRADE
stage=IGNITION|EXPANSION|EXHAUSTION
```

Examples:

```text
GET /radar/candidates?decision=LONG
GET /radar/candidates?stage=IGNITION
```

### 3. inspect_symbol

Purpose: inspect one symbol.

Backend:

```text
GET /radar/symbol/{symbol}
```

Argument:

```text
symbol: string
```

If the symbol is a moving candidate, the endpoint returns the candidate's stage,
scores, decision, context, and decision reasons.

If the symbol is not moving, it returns only the latest basic Stage 1 snapshot.

## Health endpoint

```text
GET /health
```

This is operational only and does not need to be an MCP tool.

## Runtime command

The existing scanner behavior remains unchanged unless API serving is explicitly enabled.

```bash
python -m market_radar --serve
```

Railway can supply the HTTP port using `PORT`.

## Important

Do not create a second independent MCP server for Market Radar while the existing
BabaBot MCP is available.

The intended final integration is to add the three read-only proxy tools above to
the existing BabaBot MCP Worker.
