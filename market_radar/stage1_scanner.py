from __future__ import annotations

import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .binance import BinancePublicClient
from .direction_scorer import DIRECTION_SCORE_VERSION, score_directions
from .market_context import MARKET_CONTEXT_VERSION, attach_market_context
from .models import MarketScan, MovementDetection, SymbolSnapshot
from .moving_detector import (
    MOVEMENT_DETECTOR_VERSION,
    InsufficientHistoryError,
    MovementDetectorConfig,
    detect_movement,
)
from .regime_context import classify_regime
from .stage_classifier import MOVEMENT_STAGE_VERSION, classify_movement_stage


@dataclass(frozen=True)
class Stage1Config:
    interval: str = "5m"
    history_limit: int = 50
    regime_history_limit: int = 500
    workers: int = 12
    request_timeout: float = 8.0
    retries: int = 2
    output_path: str = "data/latest_scan.json"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def filter_usdt_perpetuals(exchange_info: dict[str, Any]) -> list[str]:
    """Return ALL currently trading Binance USD-M USDT perpetual symbols.

    Stage 1 intentionally has no liquidity, momentum, top-gainer, or other
    ranking filter. The frozen blueprint requires scanning the full universe.
    """
    symbols: list[str] = []
    for item in exchange_info.get("symbols", []):
        symbol = item.get("symbol")
        if not symbol:
            continue
        if item.get("status") != "TRADING":
            continue
        if item.get("quoteAsset") != "USDT":
            continue
        if item.get("contractType") != "PERPETUAL":
            continue
        symbols.append(str(symbol))
    return sorted(set(symbols))


def latest_closed_kline(rows: Iterable[list[Any]], now_ms: int) -> list[Any]:
    """Select the newest fully closed candle.

    Binance kline close-time is field index 6. Strict `< now_ms` avoids using
    an in-progress candle at the exact boundary.
    """
    closed = [row for row in rows if len(row) > 6 and int(row[6]) < now_ms]
    if not closed:
        raise ValueError("no closed kline available")
    return max(closed, key=lambda row: int(row[6]))


def snapshot_from_kline(
    symbol: str,
    row: list[Any],
    ticker: dict[str, Any] | None,
) -> SymbolSnapshot:
    if len(row) < 11:
        raise ValueError(f"{symbol}: malformed kline length={len(row)}")
    ticker = ticker or {}
    return SymbolSnapshot(
        symbol=symbol,
        candle_open_time_ms=int(row[0]),
        candle_close_time_ms=int(row[6]),
        open=_float(row[1]),
        high=_float(row[2]),
        low=_float(row[3]),
        close=_float(row[4]),
        base_volume_5m=_float(row[5]),
        quote_volume_5m=_float(row[7]),
        trades_5m=int(row[8]),
        taker_buy_base_volume_5m=_float(row[9]),
        taker_buy_quote_volume_5m=_float(row[10]),
        quote_volume_24h=_float(ticker.get("quoteVolume")),
        price_change_pct_24h=_float(ticker.get("priceChangePercent")),
    )


def scan_symbol(
    client: BinancePublicClient,
    symbol: str,
    ticker: dict[str, Any] | None,
    now_ms: int,
    interval: str,
    history_limit: int,
    regime_history_limit: int,
    movement_config: MovementDetectorConfig | None = None,
) -> tuple[SymbolSnapshot, MovementDetection | None]:
    rows = client.klines(
        symbol=symbol,
        interval=interval,
        limit=max(3, history_limit),
    )
    row = latest_closed_kline(rows, now_ms=now_ms)
    snapshot = snapshot_from_kline(symbol, row, ticker)

    try:
        movement = detect_movement(
            symbol=symbol,
            klines=rows,
            now_ms=now_ms,
            ret_24h_pct=snapshot.price_change_pct_24h,
            config=movement_config,
        )
    except InsufficientHistoryError:
        # Newly listed markets still remain part of Stage 1's full-universe
        # snapshot even when Stage 2 cannot yet establish a robust baseline.
        movement = None

    if movement is not None:
        movement = classify_movement_stage(movement)
        movement = score_directions(movement)

        # Stage 5 network-heavy context is candidate-only. The full universe
        # remains Stage 1 scanned, but OI/funding/regime requests are made only
        # after Stage 2 confirms that the symbol is moving.
        if movement.is_moving:
            context_errors: list[str] = []

            oi_hist = None
            try:
                oi_hist = client.open_interest_hist(symbol, period="5m", limit=7)
            except Exception as exc:
                context_errors.append(f"oi_fetch:{exc}")

            premium = None
            try:
                premium = client.premium_index(symbol)
            except Exception as exc:
                context_errors.append(f"funding_fetch:{exc}")

            regime = None
            try:
                klines_4h = client.klines(
                    symbol=symbol,
                    interval="4h",
                    limit=max(25, regime_history_limit),
                )
                regime = classify_regime(klines_4h, now_ms=now_ms)
            except Exception as exc:
                context_errors.append(f"regime_fetch:{exc}")

            movement = attach_market_context(
                movement=movement,
                snapshot=snapshot,
                klines_5m=rows,
                now_ms=now_ms,
                oi_hist=oi_hist,
                premium=premium,
                regime=regime,
                external_errors=context_errors,
            )

    return snapshot, movement


def scan_all_usdt_perpetuals(
    client: BinancePublicClient | None = None,
    config: Stage1Config | None = None,
    movement_config: MovementDetectorConfig | None = None,
) -> MarketScan:
    cfg = config or Stage1Config()
    client = client or BinancePublicClient(timeout=cfg.request_timeout, retries=cfg.retries)

    started = int(time.time() * 1000)
    server_time = client.server_time_ms()
    exchange_info = client.exchange_info()
    universe = filter_usdt_perpetuals(exchange_info)

    tickers_raw = client.ticker_24h()
    tickers = {
        str(item.get("symbol")): item
        for item in tickers_raw
        if isinstance(item, dict) and item.get("symbol")
    }

    snapshots: list[SymbolSnapshot] = []
    moving_candidates: list[MovementDetection] = []
    errors: list[str] = []
    movement_evaluated_count = 0
    movement_skipped_count = 0

    with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
        futures = {
            pool.submit(
                scan_symbol,
                client,
                symbol,
                tickers.get(symbol),
                server_time,
                cfg.interval,
                cfg.history_limit,
                cfg.regime_history_limit,
                movement_config,
            ): symbol
            for symbol in universe
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                snapshot, movement = future.result()
                snapshots.append(snapshot)

                if movement is None:
                    movement_skipped_count += 1
                else:
                    movement_evaluated_count += 1
                    if movement.is_moving:
                        moving_candidates.append(movement)
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")

    snapshots.sort(key=lambda item: item.symbol)
    errors.sort()

    # Stage 4 scores are evidence only, not a trade decision. Sorting is for
    # operator visibility: strongest directional evidence first.
    moving_candidates.sort(
        key=lambda item: (
            max(item.long_score or 0.0, item.short_score or 0.0),
            item.score_edge or 0.0,
            item.evidence_count,
        ),
        reverse=True,
    )

    context_complete_count = sum(
        1
        for item in moving_candidates
        if item.market_context is not None
        and not item.market_context.context_errors
    )
    context_partial_count = sum(
        1
        for item in moving_candidates
        if item.market_context is not None
        and bool(item.market_context.context_errors)
    )

    ignition_count = sum(1 for item in moving_candidates if item.stage == "IGNITION")
    expansion_count = sum(1 for item in moving_candidates if item.stage == "EXPANSION")
    exhaustion_count = sum(1 for item in moving_candidates if item.stage == "EXHAUSTION")

    finished = int(time.time() * 1000)

    close_times = {item.candle_close_time_ms for item in snapshots}
    common_close = next(iter(close_times)) if len(close_times) == 1 else None

    return MarketScan(
        scan_started_at_ms=started,
        scan_finished_at_ms=finished,
        binance_server_time_ms=server_time,
        interval=cfg.interval,
        universe_count=len(universe),
        completed_count=len(snapshots),
        failed_count=len(errors),
        candle_close_time_ms=common_close,
        movement_detector_version=MOVEMENT_DETECTOR_VERSION,
        movement_evaluated_count=movement_evaluated_count,
        movement_skipped_count=movement_skipped_count,
        moving_candidate_count=len(moving_candidates),
        movement_stage_version=MOVEMENT_STAGE_VERSION,
        direction_score_version=DIRECTION_SCORE_VERSION,
        market_context_version=MARKET_CONTEXT_VERSION,
        context_complete_count=context_complete_count,
        context_partial_count=context_partial_count,
        ignition_count=ignition_count,
        expansion_count=expansion_count,
        exhaustion_count=exhaustion_count,
        symbols=snapshots,
        moving_candidates=moving_candidates,
        errors=errors,
    )


def write_scan_atomic(scan: MarketScan, output_path: str | os.PathLike[str]) -> Path:
    """Atomically replace the latest scan so readers never see partial JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(scan.to_dict(), separators=(",", ":"), sort_keys=True)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return path
