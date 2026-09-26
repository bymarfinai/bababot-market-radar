from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Iterable

from .models import MarketContext, MovementDetection, SymbolSnapshot
from .regime_context import REGIME_CONTEXT_VERSION, RegimeContext


MARKET_CONTEXT_VERSION = "stage5-v1"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _closed_rows(raw: Iterable[list[Any]], now_ms: int) -> list[list[Any]]:
    return [
        row
        for row in raw
        if len(row) > 10 and int(row[6]) < now_ms
    ]


def _structure_context(rows: list[list[Any]]) -> dict[str, Any]:
    if len(rows) < 21:
        raise ValueError("need >=21 closed 5m candles for 20-bar structure")

    highs = [_f(row[2]) for row in rows]
    lows = [_f(row[3]) for row in rows]
    closes = [_f(row[4]) for row in rows]

    prev_high = max(highs[-21:-1])
    prev_low = min(lows[-21:-1])

    high = highs[-1]
    low = lows[-1]
    close = closes[-1]

    breakout = prev_high > 0 and close > prev_high
    breakdown = prev_low > 0 and close < prev_low

    failed_breakout = (
        prev_high > 0
        and high > prev_high
        and close <= prev_high
    )
    failed_breakdown = (
        prev_low > 0
        and low < prev_low
        and close >= prev_low
    )

    if breakout:
        status = "BREAKOUT"
    elif breakdown:
        status = "BREAKDOWN"
    elif failed_breakout and failed_breakdown:
        status = "FAILED_BOTH_SIDES"
    elif failed_breakout:
        status = "FAILED_BREAKOUT"
    elif failed_breakdown:
        status = "FAILED_BREAKDOWN"
    else:
        status = "NO_STRUCTURAL_BREAK"

    breakout_up_pct = (
        100.0 * (close / prev_high - 1.0)
        if prev_high > 0 and close > prev_high
        else 0.0
    )
    breakdown_down_pct = (
        100.0 * (prev_low / close - 1.0)
        if close > 0 and close < prev_low
        else 0.0
    )

    return {
        "prev_20_high": prev_high,
        "prev_20_low": prev_low,
        "breakout_up_pct": breakout_up_pct,
        "breakdown_down_pct": breakdown_down_pct,
        "breakout": breakout,
        "breakdown": breakdown,
        "failed_breakout": failed_breakout,
        "failed_breakdown": failed_breakdown,
        "structure_status": status,
    }


def _taker_context(latest_row: list[Any]) -> dict[str, Any]:
    """Read aggressive taker flow directly from the same closed Binance kline.

    Binance kline fields:
      7  quote asset volume
      10 taker buy quote asset volume

    Therefore taker sell quote volume = total quote volume - taker buy quote
    volume. This keeps taker flow timestamp-aligned with the exact candle used
    by Stage 2-4 and avoids a second endpoint with ambiguous period alignment.
    """
    total_quote = max(0.0, _f(latest_row[7]))
    buy_quote = min(total_quote, max(0.0, _f(latest_row[10])))
    sell_quote = max(0.0, total_quote - buy_quote)

    if sell_quote > 0:
        ratio = buy_quote / sell_quote
    elif buy_quote > 0:
        ratio = 999999.0
    else:
        ratio = 1.0

    share = buy_quote / total_quote if total_quote > 0 else 0.5

    if share >= 0.55:
        bias = "BUY"
    elif share <= 0.45:
        bias = "SELL"
    else:
        bias = "BALANCED"

    return {
        "taker_buy_quote_volume_5m": buy_quote,
        "taker_sell_quote_volume_5m": sell_quote,
        "taker_buy_sell_ratio": ratio,
        "taker_buy_share": share,
        "taker_bias": bias,
    }


def _raw_oi_context(
    oi_hist: list[dict[str, Any]] | None,
    candle_close_time_ms: int,
    movement: MovementDetection,
) -> dict[str, Any]:
    """Parse Binance raw OI only.

    IMPORTANT: intentionally ignores sumOpenInterestValue. Stage 5 must never
    silently switch to USD-valued OI because its scale/meaning differs from raw
    open interest.
    """
    if not oi_hist:
        raise ValueError("raw OI history unavailable")

    usable: list[tuple[int, float]] = []
    for item in oi_hist:
        if not isinstance(item, dict):
            continue
        if "sumOpenInterest" not in item:
            continue

        timestamp = int(item.get("timestamp", 0) or 0)
        raw_oi = _f(item.get("sumOpenInterest"), default=-1.0)
        if raw_oi <= 0:
            continue

        # Do not admit an OI observation timestamped after the closed signal bar.
        if timestamp and timestamp > candle_close_time_ms:
            continue

        usable.append((timestamp, raw_oi))

    usable.sort(key=lambda item: item[0])

    if len(usable) < 2:
        raise ValueError("need >=2 causal raw OI observations")

    first_ts, first_oi = usable[0]
    last_ts, last_oi = usable[-1]
    change_pct = 100.0 * (last_oi / first_oi - 1.0)

    window_minutes: int | None = None
    if first_ts > 0 and last_ts >= first_ts:
        window_minutes = int(round((last_ts - first_ts) / 60_000))

    # Interpretation uses price direction as context, not as a trade decision.
    price_delta = movement.ret_15m_pct
    eps = 1e-12
    if price_delta > eps and change_pct > eps:
        interpretation = "FRESH_LONG_PARTICIPATION"
    elif price_delta > eps and change_pct < -eps:
        interpretation = "SHORT_COVERING"
    elif price_delta < -eps and change_pct > eps:
        interpretation = "FRESH_SHORT_PARTICIPATION"
    elif price_delta < -eps and change_pct < -eps:
        interpretation = "LONG_LIQUIDATION"
    else:
        interpretation = "UNRESOLVED"

    return {
        "raw_oi_first": first_oi,
        "raw_oi_last": last_oi,
        "raw_oi_change_pct": change_pct,
        "raw_oi_window_minutes": window_minutes,
        "oi_interpretation": interpretation,
    }


def attach_market_context(
    movement: MovementDetection,
    snapshot: SymbolSnapshot,
    klines_5m: Iterable[list[Any]],
    now_ms: int,
    oi_hist: list[dict[str, Any]] | None,
    premium: dict[str, Any] | None,
    regime: RegimeContext | None,
    external_errors: Iterable[str] = (),
) -> MovementDetection:
    """Attach Stage 5 context without changing Stage 4 direction scores."""
    if not movement.is_moving:
        return replace(
            movement,
            market_context=None,
            market_context_version=MARKET_CONTEXT_VERSION,
        )

    rows = _closed_rows(klines_5m, now_ms)
    if len(rows) < 21:
        raise ValueError(
            f"{movement.symbol}: need >=21 closed 5m candles for Stage 5"
        )

    errors = list(external_errors)

    structure = _structure_context(rows)
    taker = _taker_context(rows[-1])

    oi_fields: dict[str, Any] = {
        "raw_oi_first": None,
        "raw_oi_last": None,
        "raw_oi_change_pct": None,
        "raw_oi_window_minutes": None,
        "oi_interpretation": None,
    }
    try:
        oi_fields = _raw_oi_context(
            oi_hist=oi_hist,
            candle_close_time_ms=movement.candle_close_time_ms,
            movement=movement,
        )
    except Exception as exc:
        errors.append(f"oi:{exc}")

    funding_rate: float | None = None
    if premium and premium.get("lastFundingRate") is not None:
        try:
            funding_rate = float(premium["lastFundingRate"])
        except (TypeError, ValueError):
            errors.append("funding:invalid lastFundingRate")
    else:
        errors.append("funding:unavailable")

    regime_fields: dict[str, Any] = {
        "market_regime": None,
        "regime_ema7": None,
        "regime_ema20": None,
        "regime_atr14": None,
        "regime_hh": None,
        "regime_hl": None,
        "regime_lh": None,
        "regime_ll": None,
        "regime_source_version": None,
        "regime_bar_close_time_ms": None,
    }
    if regime is not None:
        regime_fields = {
            "market_regime": regime.regime,
            "regime_ema7": regime.ema7,
            "regime_ema20": regime.ema20,
            "regime_atr14": regime.atr14,
            "regime_hh": regime.hh,
            "regime_hl": regime.hl,
            "regime_lh": regime.lh,
            "regime_ll": regime.ll,
            "regime_source_version": regime.source_version,
            "regime_bar_close_time_ms": regime.regime_bar_close_time_ms,
        }
    else:
        errors.append("regime:unavailable")

    context = MarketContext(
        context_version=MARKET_CONTEXT_VERSION,
        quote_volume_5m=snapshot.quote_volume_5m,
        quote_volume_24h=snapshot.quote_volume_24h,
        volume_ratio=movement.volume_ratio,
        volume_confirmed=movement.volume_ratio >= 1.5,
        prev_20_high=round(structure["prev_20_high"], 12),
        prev_20_low=round(structure["prev_20_low"], 12),
        breakout_up_pct=round(structure["breakout_up_pct"], 6),
        breakdown_down_pct=round(structure["breakdown_down_pct"], 6),
        breakout=structure["breakout"],
        breakdown=structure["breakdown"],
        failed_breakout=structure["failed_breakout"],
        failed_breakdown=structure["failed_breakdown"],
        structure_status=structure["structure_status"],
        taker_buy_quote_volume_5m=round(
            taker["taker_buy_quote_volume_5m"], 12
        ),
        taker_sell_quote_volume_5m=round(
            taker["taker_sell_quote_volume_5m"], 12
        ),
        taker_buy_sell_ratio=round(taker["taker_buy_sell_ratio"], 6),
        taker_buy_share=round(taker["taker_buy_share"], 6),
        taker_bias=taker["taker_bias"],
        raw_oi_first=(
            round(oi_fields["raw_oi_first"], 12)
            if oi_fields["raw_oi_first"] is not None
            else None
        ),
        raw_oi_last=(
            round(oi_fields["raw_oi_last"], 12)
            if oi_fields["raw_oi_last"] is not None
            else None
        ),
        raw_oi_change_pct=(
            round(oi_fields["raw_oi_change_pct"], 6)
            if oi_fields["raw_oi_change_pct"] is not None
            else None
        ),
        raw_oi_window_minutes=oi_fields["raw_oi_window_minutes"],
        oi_interpretation=oi_fields["oi_interpretation"],
        funding_rate=round(funding_rate, 10) if funding_rate is not None else None,
        **regime_fields,
        context_errors=tuple(errors),
    )

    return replace(
        movement,
        market_context=context,
        market_context_version=MARKET_CONTEXT_VERSION,
    )
