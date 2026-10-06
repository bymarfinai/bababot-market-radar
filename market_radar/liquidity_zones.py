from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from .binance import BinancePublicClient


LIQUIDITY_ZONE_VERSION = "lq-ui1-causal-zones-v1"

TF_CONFIG: dict[str, dict[str, float | int]] = {
    "5m": {
        "lookback_ms": 36 * 3_600_000,
        "left": 3,
        "right": 2,
        "min_departure_atr": 0.75,
        "limit": 500,
    },
    "15m": {
        "lookback_ms": 72 * 3_600_000,
        "left": 3,
        "right": 2,
        "min_departure_atr": 0.75,
        "limit": 360,
    },
    "1h": {
        "lookback_ms": 168 * 3_600_000,
        "left": 3,
        "right": 2,
        "min_departure_atr": 0.75,
        "limit": 240,
    },
}


@dataclass(frozen=True)
class Bar:
    open_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_ms: int


@dataclass(frozen=True)
class Zone:
    side: str
    timeframe: str
    base_open_ms: int
    born_ms: int
    lower: float
    upper: float
    atr_at_birth: float
    departure_atr: float
    base_volume_ratio: float
    zone_width_atr: float
    base_index: int
    born_index: int


def _bar(raw: list[Any]) -> Bar:
    return Bar(
        open_ms=int(raw[0]),
        open=float(raw[1]),
        high=float(raw[2]),
        low=float(raw[3]),
        close=float(raw[4]),
        volume=float(raw[5]),
        close_ms=int(raw[6]),
    )


def _true_ranges(bars: list[Bar]) -> list[float]:
    out: list[float] = []
    for i, bar in enumerate(bars):
        previous = bars[i - 1].close if i else bar.open
        out.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous),
                abs(bar.low - previous),
            )
        )
    return out


def _atr_at(trs: list[float], index: int, period: int = 14) -> float:
    values = [
        value
        for value in trs[max(0, index - period + 1) : index + 1]
        if value > 0
    ]
    if not values:
        return float("nan")
    return sum(values) / len(values)


def _volume_ratio(bars: list[Bar], index: int, period: int = 20) -> float:
    history = [
        bar.volume
        for bar in bars[max(0, index - period) : index]
        if bar.volume > 0
    ]
    if not history:
        return float("nan")
    median = statistics.median(history)
    return bars[index].volume / median if median > 0 else float("nan")


def build_zones(bars: list[Bar], timeframe: str) -> list[Zone]:
    if timeframe not in TF_CONFIG:
        raise ValueError(f"unsupported timeframe={timeframe!r}")
    cfg = TF_CONFIG[timeframe]
    left = int(cfg["left"])
    right = int(cfg["right"])
    min_departure_atr = float(cfg["min_departure_atr"])
    trs = _true_ranges(bars)
    zones: list[Zone] = []

    for index in range(max(left, 14), len(bars) - right):
        base = bars[index]
        atr = _atr_at(trs, index)
        if not math.isfinite(atr) or atr <= 0:
            continue

        left_bars = bars[index - left : index]
        right_bars = bars[index + 1 : index + right + 1]
        born_index = index + right
        body_high = max(base.open, base.close)
        body_low = min(base.open, base.close)
        volume_ratio = _volume_ratio(bars, index)

        swing_high = (
            base.high >= max(bar.high for bar in left_bars)
            and base.high >= max(bar.high for bar in right_bars)
        )
        if swing_high:
            lower = body_high
            upper = base.high
            departure = max(0.0, lower - min(bar.low for bar in right_bars))
            departure_atr = departure / atr
            if (
                upper > lower
                and departure_atr >= min_departure_atr
                and right_bars[-1].close < lower
            ):
                zones.append(
                    Zone(
                        side="SUPPLY",
                        timeframe=timeframe,
                        base_open_ms=base.open_ms,
                        born_ms=bars[born_index].close_ms,
                        lower=lower,
                        upper=upper,
                        atr_at_birth=atr,
                        departure_atr=departure_atr,
                        base_volume_ratio=volume_ratio,
                        zone_width_atr=(upper - lower) / atr,
                        base_index=index,
                        born_index=born_index,
                    )
                )

        swing_low = (
            base.low <= min(bar.low for bar in left_bars)
            and base.low <= min(bar.low for bar in right_bars)
        )
        if swing_low:
            lower = base.low
            upper = body_low
            departure = max(0.0, max(bar.high for bar in right_bars) - upper)
            departure_atr = departure / atr
            if (
                upper > lower
                and departure_atr >= min_departure_atr
                and right_bars[-1].close > upper
            ):
                zones.append(
                    Zone(
                        side="DEMAND",
                        timeframe=timeframe,
                        base_open_ms=base.open_ms,
                        born_ms=bars[born_index].close_ms,
                        lower=lower,
                        upper=upper,
                        atr_at_birth=atr,
                        departure_atr=departure_atr,
                        base_volume_ratio=volume_ratio,
                        zone_width_atr=(upper - lower) / atr,
                        base_index=index,
                        born_index=born_index,
                    )
                )
    return zones


def _touches(bar: Bar, zone: Zone) -> bool:
    return bar.high >= zone.lower and bar.low <= zone.upper


def zone_state(zone: Zone, bars: list[Bar], asof_ms: int) -> dict[str, Any]:
    if zone.born_ms > asof_ms:
        return {
            "state": "UNBORN",
            "touch_count": 0,
            "broken_ms": None,
            "flip_ms": None,
        }

    touch_count = 0
    in_touch = False
    broken_ms: int | None = None
    flip_ms: int | None = None

    for bar in bars[zone.born_index + 1 :]:
        if bar.close_ms > asof_ms:
            break
        touched = _touches(bar, zone)
        if touched and not in_touch:
            touch_count += 1
        in_touch = touched

        if broken_ms is None:
            broken = (
                bar.close > zone.upper
                if zone.side == "SUPPLY"
                else bar.close < zone.lower
            )
            if broken:
                broken_ms = bar.close_ms
                in_touch = False
                continue
        else:
            if (
                zone.side == "SUPPLY"
                and bar.low <= zone.upper
                and bar.close > zone.upper
            ):
                flip_ms = bar.close_ms
            elif (
                zone.side == "DEMAND"
                and bar.high >= zone.lower
                and bar.close < zone.lower
            ):
                flip_ms = bar.close_ms

    if broken_ms is not None:
        state = "FLIPPED" if flip_ms is not None else "BROKEN"
    else:
        state = "TESTED" if touch_count else "FRESH"

    return {
        "state": state,
        "touch_count": touch_count,
        "broken_ms": broken_ms,
        "flip_ms": flip_ms,
    }


def _distance_pct(price: float, zone: Zone) -> float | None:
    if zone.lower <= price <= zone.upper:
        return 0.0
    if zone.side == "SUPPLY":
        if price < zone.lower:
            return (zone.lower / price - 1.0) * 100.0
        return None
    if price > zone.upper:
        return (1.0 - zone.upper / price) * 100.0
    return None


def _fetch_closed_bars(
    client: BinancePublicClient,
    symbol: str,
    timeframe: str,
    asof_ms: int,
) -> list[Bar]:
    cfg = TF_CONFIG[timeframe]
    raw = client.get(
        "/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": timeframe,
            "startTime": asof_ms - int(cfg["lookback_ms"]),
            "endTime": asof_ms,
            "limit": int(cfg["limit"]),
        },
    )
    if not isinstance(raw, list):
        raise RuntimeError("Binance klines response is not a list")
    bars = [_bar(row) for row in raw]
    return [bar for bar in bars if bar.close_ms <= asof_ms]


def _serialize_active_zone(
    zone: Zone,
    state: dict[str, Any],
    reference_price: float,
) -> dict[str, Any]:
    return {
        "side": zone.side,
        "timeframe": zone.timeframe,
        "base_open_ms": zone.base_open_ms,
        "born_ms": zone.born_ms,
        "lower": zone.lower,
        "upper": zone.upper,
        "mid": (zone.lower + zone.upper) / 2.0,
        "departure_atr": zone.departure_atr,
        "base_volume_ratio": (
            zone.base_volume_ratio
            if math.isfinite(zone.base_volume_ratio)
            else None
        ),
        "zone_width_atr": zone.zone_width_atr,
        "touch_count": int(state["touch_count"]),
        "state": state["state"],
        "distance_pct": _distance_pct(reference_price, zone),
        "contains_reference": zone.lower <= reference_price <= zone.upper,
    }


def liquidity_zone_snapshot(
    *,
    symbol: str,
    asof_ms: int,
    reference_price: float | None = None,
    client: BinancePublicClient | None = None,
) -> dict[str, Any]:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        raise ValueError("symbol is required")
    asof_ms = int(asof_ms)
    if asof_ms <= 0:
        raise ValueError("asof_ms must be positive")

    client = client or BinancePublicClient(timeout=8.0, retries=2)
    bars_by_tf: dict[str, list[Bar]] = {}
    zones: list[dict[str, Any]] = []

    for timeframe in ("5m", "15m", "1h"):
        bars = _fetch_closed_bars(client, symbol, timeframe, asof_ms)
        bars_by_tf[timeframe] = bars

    if reference_price is None:
        five_minute = bars_by_tf["5m"]
        if not five_minute:
            raise RuntimeError("no closed 5m bars available at snapshot")
        reference_price = five_minute[-1].close
    reference_price = float(reference_price)
    if not math.isfinite(reference_price) or reference_price <= 0:
        raise ValueError("reference_price must be positive")

    for timeframe in ("5m", "15m", "1h"):
        bars = bars_by_tf[timeframe]
        for zone in build_zones(bars, timeframe):
            if zone.born_ms > asof_ms:
                continue
            state = zone_state(zone, bars, asof_ms)
            if state["state"] in {"BROKEN", "FLIPPED"}:
                continue
            zones.append(_serialize_active_zone(zone, state, reference_price))

    # Match the frozen LQ-1 combined-nearest tie-break contract.
    tf_priority = {"1h": 0, "15m": 1, "5m": 2}
    zones.sort(
        key=lambda item: (
            0 if item["contains_reference"] else 1,
            item["distance_pct"]
            if item["distance_pct"] is not None
            else float("inf"),
            tf_priority.get(str(item["timeframe"]), 9),
            -float(item["departure_atr"]),
        )
    )

    nearest: dict[str, Any] = {"supply": None, "demand": None}
    for side in ("SUPPLY", "DEMAND"):
        candidates = [
            item
            for item in zones
            if item["side"] == side and item["distance_pct"] is not None
        ]
        candidates.sort(
            key=lambda item: (
                float(item["distance_pct"]),
                tf_priority.get(str(item["timeframe"]), 9),
                -float(item["departure_atr"]),
            )
        )
        if candidates:
            nearest[side.lower()] = candidates[0]

    return {
        "version": LIQUIDITY_ZONE_VERSION,
        "symbol": symbol,
        "asof_ms": asof_ms,
        "reference_price": reference_price,
        "timeframes": ["5m", "15m", "1h"],
        "zone_count": len(zones),
        "nearest": nearest,
        "zones": zones,
        "causal": True,
    }