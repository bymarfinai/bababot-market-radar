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
class MarketContext:
    """Stage 5 context attached to a moving candidate.

    Context describes the market state. It is not the Stage 6 trade decision.
    """

    context_version: str

    # Volume/activity
    quote_volume_5m: float
    quote_volume_24h: float
    volume_ratio: float
    volume_confirmed: bool

    # Structure
    prev_20_high: float
    prev_20_low: float
    breakout_up_pct: float
    breakdown_down_pct: float
    breakout: bool
    breakdown: bool
    failed_breakout: bool
    failed_breakdown: bool
    structure_status: str

    # Aggressive taker flow from the same closed 5m kline
    taker_buy_quote_volume_5m: float
    taker_sell_quote_volume_5m: float
    taker_buy_sell_ratio: float
    taker_buy_share: float
    taker_bias: str

    # Raw Binance open interest (contracts/coins, never USD-valued OI)
    raw_oi_first: float | None
    raw_oi_last: float | None
    raw_oi_change_pct: float | None
    raw_oi_window_minutes: int | None
    oi_interpretation: str | None

    # Funding
    funding_rate: float | None

    # Existing causal regime logic ported from BabaBot Discovery
    market_regime: str | None
    regime_ema7: float | None
    regime_ema20: float | None
    regime_atr14: float | None
    regime_hh: int | None
    regime_hl: int | None
    regime_lh: int | None
    regime_ll: int | None
    regime_source_version: str | None
    regime_bar_close_time_ms: int | None

    context_errors: tuple[str, ...] = ()


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
    stage: str | None = None
    stage_classifier_version: str | None = None
    long_score: float | None = None
    short_score: float | None = None
    score_gap: float | None = None
    score_edge: float | None = None
    long_score_components: dict[str, float] = field(default_factory=dict)
    short_score_components: dict[str, float] = field(default_factory=dict)
    direction_score_version: str | None = None
    market_context: MarketContext | None = None
    market_context_version: str | None = None


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
    movement_stage_version: str
    direction_score_version: str
    market_context_version: str
    context_complete_count: int
    context_partial_count: int
    ignition_count: int
    expansion_count: int
    exhaustion_count: int
    symbols: list[SymbolSnapshot] = field(default_factory=list)
    moving_candidates: list[MovementDetection] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
