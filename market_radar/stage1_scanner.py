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
from .models import MarketScan, SymbolSnapshot


@dataclass(frozen=True)
class Stage1Config:
    interval: str = "5m"
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
) -> SymbolSnapshot:
    rows = client.klines(symbol=symbol, interval=interval, limit=3)
    row = latest_closed_kline(rows, now_ms=now_ms)
    return snapshot_from_kline(symbol, row, ticker)


def scan_all_usdt_perpetuals(
    client: BinancePublicClient | None = None,
    config: Stage1Config | None = None,
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
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
        futures = {
            pool.submit(
                scan_symbol,
                client,
                symbol,
                tickers.get(symbol),
                server_time,
                cfg.interval,
            ): symbol
            for symbol in universe
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                snapshots.append(future.result())
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")

    snapshots.sort(key=lambda item: item.symbol)
    errors.sort()
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
        symbols=snapshots,
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
