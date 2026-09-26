from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


REGIME_CONTEXT_VERSION = "b27ag-swing-regime-v1"
VALID_REGIMES = {"BULL", "BEAR", "SIDEWAYS"}


@dataclass(frozen=True)
class RegimeContext:
    regime: str
    ema7: float
    ema20: float
    atr14: float
    hh: int
    hl: int
    lh: int
    ll: int
    latest_swing_high: float | None
    latest_swing_low: float | None
    regime_bar_open_time_ms: int
    regime_bar_close_time_ms: int
    source_version: str = REGIME_CONTEXT_VERSION


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _closed_klines(
    raw: Iterable[list[Any]],
    now_ms: int,
) -> list[list[Any]]:
    """Only completed 4H candles are allowed to influence regime."""
    return [
        row
        for row in raw
        if len(row) > 6 and int(row[6]) < now_ms
    ]


def _ema(values: list[float], period: int) -> list[float]:
    """Exact EMA recurrence used by the existing B27AG regime implementation."""
    if not values:
        return []
    out = [values[0]]
    k = 2.0 / (period + 1.0)
    for value in values[1:]:
        out.append(value * k + out[-1] * (1.0 - k))
    return out


def _atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float]:
    """Exact ATR recurrence used by the existing B27AG implementation."""
    n = len(highs)
    out = [0.0] * n
    for i in range(1, n):
        true_range = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        out[i] = out[i - 1] + (true_range - out[i - 1]) / min(i, period)
    return out


class SwingRegime:
    """Port of the existing BabaBot Discovery B27AG SwingRegime.

    Frozen semantics/defaults:
      lookback = 5
      swing ATR separation = 0.5
      BULL: hh>=2, hl>=2, EMA7>EMA20, close>EMA20
      BEAR: lh>=2, ll>=2, EMA7<EMA20, close<EMA20
      otherwise SIDEWAYS

    This is copied into Market Radar so runtime dependency on Discovery is zero.
    """

    def __init__(self, lookback: int = 5, swing_atr: float = 0.5) -> None:
        self.lookback = lookback
        self.swing_atr = swing_atr
        self.hh = 0
        self.hl = 0
        self.lh = 0
        self.ll = 0
        self.latest_swing_high: float | None = None
        self.latest_swing_low: float | None = None
        self.previous_swing_high: float | None = None
        self.previous_swing_low: float | None = None

    def process(
        self,
        i: int,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        ema_fast: list[float],
        ema_slow: list[float],
        atr14: list[float],
    ) -> str:
        if i < self.lookback:
            return "SIDEWAYS"

        mid = i - self.lookback // 2
        if mid < 0:
            return "SIDEWAYS"

        start = max(0, i - self.lookback)
        window_highs = highs[start : i + 1]
        window_lows = lows[start : i + 1]
        min_separation = self.swing_atr * atr14[i] if atr14[i] > 0 else 0.0

        if highs[mid] == max(window_highs) and (
            self.latest_swing_high is None
            or abs(highs[mid] - self.latest_swing_high) >= min_separation
        ):
            self.previous_swing_high = self.latest_swing_high
            self.latest_swing_high = float(highs[mid])
            if self.previous_swing_high:
                if self.latest_swing_high > self.previous_swing_high:
                    self.hh += 1
                else:
                    self.lh += 1
                    self.hh = max(0, self.hh - 1)

        if lows[mid] == min(window_lows) and (
            self.latest_swing_low is None
            or abs(lows[mid] - self.latest_swing_low) >= min_separation
        ):
            self.previous_swing_low = self.latest_swing_low
            self.latest_swing_low = float(lows[mid])
            if self.previous_swing_low:
                if self.latest_swing_low > self.previous_swing_low:
                    self.hl += 1
                    self.ll = max(0, self.ll - 1)
                else:
                    self.ll += 1
                    self.hl = max(0, self.hl - 1)

        if (
            self.hh >= 2
            and self.hl >= 2
            and ema_fast[i] > ema_slow[i]
            and closes[i] > ema_slow[i]
        ):
            return "BULL"

        if (
            self.lh >= 2
            and self.ll >= 2
            and ema_fast[i] < ema_slow[i]
            and closes[i] < ema_slow[i]
        ):
            return "BEAR"

        return "SIDEWAYS"


def classify_regime(
    klines_4h: Iterable[list[Any]],
    now_ms: int,
) -> RegimeContext:
    """Classify the latest available completed 4H regime.

    Direct Binance 4H candles are used, but only rows whose close timestamp is
    already in the past are admitted. No current/open 4H bar can leak in.
    """
    rows = _closed_klines(klines_4h, now_ms)
    if len(rows) < 25:
        raise ValueError(f"need >=25 closed 4H candles, got {len(rows)}")

    highs = [_f(row[2]) for row in rows]
    lows = [_f(row[3]) for row in rows]
    closes = [_f(row[4]) for row in rows]

    ema7 = _ema(closes, 7)
    ema20 = _ema(closes, 20)
    atr14 = _atr(highs, lows, closes, 14)

    detector = SwingRegime(lookback=5, swing_atr=0.5)
    regime = "SIDEWAYS"
    for i in range(len(rows)):
        regime = detector.process(i, highs, lows, closes, ema7, ema20, atr14)

    if regime not in VALID_REGIMES:
        raise AssertionError(f"invalid regime: {regime}")

    last = rows[-1]
    return RegimeContext(
        regime=regime,
        ema7=round(ema7[-1], 12),
        ema20=round(ema20[-1], 12),
        atr14=round(atr14[-1], 12),
        hh=detector.hh,
        hl=detector.hl,
        lh=detector.lh,
        ll=detector.ll,
        latest_swing_high=detector.latest_swing_high,
        latest_swing_low=detector.latest_swing_low,
        regime_bar_open_time_ms=int(last[0]),
        regime_bar_close_time_ms=int(last[6]),
    )
