from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SymbolSnapshot:
    symbol: str
    candle_open_time_ms: int
    candle_close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    base_volume_5m: float
    quote_volume_5m: float
    trades_5m: int
    taker_buy_base_volume_5m: float
    taker_buy_quote_volume_5m: float
    quote_volume_24h: float
    price_change_pct_24h: float


@dataclass
class MarketScan:
    scan_started_at_ms: int
    scan_finished_at_ms: int
    binance_server_time_ms: int
    interval: str
    universe_count: int
    completed_count: int
    failed_count: int
    candle_close_time_ms: int | None
    symbols: list[SymbolSnapshot] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
