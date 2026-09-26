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


@dataclass(frozen=True)
class MovementDetection:
    """Stage 2 movement result.

    direction_hint is raw price movement (UP/DOWN/FLAT), not a LONG/SHORT
    trading decision. Stage 3 and Stage 4 own the later stage/score semantics.
    """

    symbol: str
    detector_version: str
    candle_close_time_ms: int
    movement_state: str
    direction_hint: str
    is_moving: bool
    ret_5m_pct: float
    ret_15m_pct: float
    ret_1h_pct: float
    ret_24h_pct: float
    median_abs_ret_5m_pct: float
    return_expansion_ratio: float
    volume_ratio: float
    range_ratio: float
    trades_ratio: float
    directional_persistence: bool
    evidence_count: int
    reasons: tuple[str, ...] = ()


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
    movement_detector_version: str
    movement_evaluated_count: int
    movement_skipped_count: int
    moving_candidate_count: int
    symbols: list[SymbolSnapshot] = field(default_factory=list)
    moving_candidates: list[MovementDetection] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
