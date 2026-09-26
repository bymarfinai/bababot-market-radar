from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Iterable

from .models import MovementDetection


MOVEMENT_DETECTOR_VERSION = "stage2-v1"


class InsufficientHistoryError(ValueError):
    """Raised when a symbol does not yet have enough closed 5m history."""


@dataclass(frozen=True)
class MovementDetectorConfig:
    """Stage 2 thresholds.

    These are deterministic production rules for detecting abnormal movement,
    not LONG/SHORT trade scores and not Stage 3 movement labels.

    The detector normalizes current activity against each symbol's own recent
    5m baseline so the same logic can scan the entire USDT-perpetual universe.
    """

    baseline_bars: int = 20
    min_history_bars: int = 25

    # Absolute floor prevents tiny low-volatility noise from becoming a
    # candidate only because its historical baseline is extremely small.
    min_abs_ret_5m_pct: float = 0.15

    # Relative-to-own-baseline movement evidence.
    return_expansion_ratio: float = 2.0
    volume_expansion_ratio: float = 1.5
    range_expansion_ratio: float = 1.4
    trades_expansion_ratio: float = 1.5

    # Strong continuation requires persistent direction plus stronger activity.
    strong_return_ratio: float = 3.0
    strong_volume_ratio: float = 2.0
    strong_range_ratio: float = 1.6

    # A move can still be detected but flagged as already late. Stage 3 will
    # later decide whether that becomes EXHAUSTION.
    late_1h_same_direction_pct: float = 6.0
    late_24h_same_direction_pct: float = 30.0


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _closed_klines(raw: Iterable[list[Any]], now_ms: int) -> list[list[Any]]:
    return [row for row in raw if len(row) > 10 and int(row[6]) < now_ms]


def _ret(closes: list[float], bars: int) -> float:
    if len(closes) <= bars or closes[-1 - bars] <= 0:
        return 0.0
    return 100.0 * (closes[-1] / closes[-1 - bars] - 1.0)


def _median(values: list[float], floor: float = 0.0) -> float:
    if not values:
        return floor
    return max(float(statistics.median(values)), floor)


def detect_movement(
    symbol: str,
    klines: Iterable[list[Any]],
    now_ms: int,
    ret_24h_pct: float = 0.0,
    config: MovementDetectorConfig | None = None,
) -> MovementDetection:
    """Detect whether a symbol is experiencing abnormal live movement.

    Stage 2 deliberately does NOT emit:
      * IGNITION / EXPANSION / EXHAUSTION
      * LONG_SCORE / SHORT_SCORE
      * LONG / SHORT / NO TRADE

    It only determines whether movement is present and records raw evidence.
    All calculations use fully closed 5m candles.
    """
    cfg = config or MovementDetectorConfig()
    rows = _closed_klines(klines, now_ms)

    if len(rows) < cfg.min_history_bars:
        raise InsufficientHistoryError(
            f"{symbol}: need >= {cfg.min_history_bars} closed 5m candles, got {len(rows)}"
        )

    closes = [_f(row[4]) for row in rows]
    highs = [_f(row[2]) for row in rows]
    lows = [_f(row[3]) for row in rows]
    quote_volumes = [_f(row[7]) for row in rows]
    trades = [_f(row[8]) for row in rows]

    five_min_returns: list[float] = []
    true_range_pcts: list[float] = []

    for idx in range(1, len(rows)):
        prev_close = closes[idx - 1]
        close = closes[idx]

        five_min_returns.append(
            100.0 * (close / prev_close - 1.0) if prev_close > 0 else 0.0
        )

        true_range = max(
            highs[idx] - lows[idx],
            abs(highs[idx] - prev_close),
            abs(lows[idx] - prev_close),
        )
        true_range_pcts.append(
            100.0 * true_range / prev_close if prev_close > 0 else 0.0
        )

    baseline = cfg.baseline_bars

    # Previous baseline bars only; the current candle is excluded.
    prior_abs_returns = [
        abs(value) for value in five_min_returns[-(baseline + 1) : -1]
    ]
    prior_quote_volumes = quote_volumes[-(baseline + 1) : -1]
    prior_ranges = true_range_pcts[-(baseline + 1) : -1]
    prior_trades = trades[-(baseline + 1) : -1]

    # Floors keep ratios finite for symbols whose recent candles were almost flat.
    median_abs_ret = _median(prior_abs_returns, floor=0.03)
    median_quote_volume = _median(prior_quote_volumes)
    median_range = _median(prior_ranges, floor=0.03)
    median_trades = _median(prior_trades)

    ret_5m = _ret(closes, 1)
    ret_15m = _ret(closes, 3)
    ret_1h = _ret(closes, 12)

    return_ratio = abs(ret_5m) / median_abs_ret if median_abs_ret > 0 else 0.0
    volume_ratio = (
        quote_volumes[-1] / median_quote_volume if median_quote_volume > 0 else 0.0
    )
    range_ratio = (
        true_range_pcts[-1] / median_range if median_range > 0 else 0.0
    )
    trades_ratio = trades[-1] / median_trades if median_trades > 0 else 0.0

    if ret_5m > 0:
        direction_hint = "UP"
        sign = 1.0
    elif ret_5m < 0:
        direction_hint = "DOWN"
        sign = -1.0
    else:
        direction_hint = "FLAT"
        sign = 0.0

    recent_returns = five_min_returns[-3:]
    same_direction_bars = (
        sum(1 for value in recent_returns if sign != 0 and value * sign > 0)
        if sign != 0
        else 0
    )
    directional_persistence = (
        sign != 0
        and same_direction_bars >= 2
        and ret_15m * sign > 0
    )

    return_expanding = return_ratio >= cfg.return_expansion_ratio
    volume_expanding = volume_ratio >= cfg.volume_expansion_ratio
    range_expanding = range_ratio >= cfg.range_expansion_ratio
    trades_expanding = trades_ratio >= cfg.trades_expansion_ratio

    evidence_flags = (
        return_expanding,
        volume_expanding,
        range_expanding,
        trades_expanding,
        directional_persistence,
    )
    evidence_count = sum(1 for flag in evidence_flags if flag)

    activity_confirmed = volume_expanding or range_expanding or trades_expanding
    is_moving = (
        abs(ret_5m) >= cfg.min_abs_ret_5m_pct
        and return_expanding
        and activity_confirmed
    )

    same_direction_1h = ret_1h * sign if sign != 0 else 0.0
    same_direction_24h = ret_24h_pct * sign if sign != 0 else 0.0

    if is_moving and (
        same_direction_1h >= cfg.late_1h_same_direction_pct
        or same_direction_24h >= cfg.late_24h_same_direction_pct
    ):
        movement_state = "LATE_MOVEMENT"
    elif (
        is_moving
        and return_ratio >= cfg.strong_return_ratio
        and volume_ratio >= cfg.strong_volume_ratio
        and range_ratio >= cfg.strong_range_ratio
        and directional_persistence
    ):
        movement_state = "STRONG_CONTINUATION"
    elif is_moving:
        movement_state = "EARLY_MOVEMENT"
    elif (
        abs(ret_5m) < cfg.min_abs_ret_5m_pct / 2.0
        and return_ratio < 1.25
        and volume_ratio < 1.20
        and range_ratio < 1.20
    ):
        movement_state = "NOISE"
    else:
        movement_state = "NORMAL"

    reasons: list[str] = []
    if return_expanding:
        reasons.append(f"5m return {return_ratio:.2f}x own baseline")
    if volume_expanding:
        reasons.append(f"5m quote volume {volume_ratio:.2f}x baseline")
    if range_expanding:
        reasons.append(f"5m true range {range_ratio:.2f}x baseline")
    if trades_expanding:
        reasons.append(f"5m trade count {trades_ratio:.2f}x baseline")
    if directional_persistence:
        reasons.append(f"direction persists across recent 5m bars")
    if movement_state == "LATE_MOVEMENT":
        reasons.append("same-direction move already extended on 1h/24h")

    return MovementDetection(
        symbol=symbol,
        detector_version=MOVEMENT_DETECTOR_VERSION,
        candle_close_time_ms=int(rows[-1][6]),
        movement_state=movement_state,
        direction_hint=direction_hint,
        is_moving=is_moving,
        ret_5m_pct=round(ret_5m, 6),
        ret_15m_pct=round(ret_15m, 6),
        ret_1h_pct=round(ret_1h, 6),
        ret_24h_pct=round(ret_24h_pct, 6),
        median_abs_ret_5m_pct=round(median_abs_ret, 6),
        return_expansion_ratio=round(return_ratio, 4),
        volume_ratio=round(volume_ratio, 4),
        range_ratio=round(range_ratio, 4),
        trades_ratio=round(trades_ratio, 4),
        directional_persistence=directional_persistence,
        evidence_count=evidence_count,
        reasons=tuple(reasons),
    )
