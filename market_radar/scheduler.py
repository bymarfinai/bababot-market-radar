from __future__ import annotations

import time
from collections.abc import Callable

from .binance import BinancePublicClient
from .execution_handoff import (
    default_execution_handoff_path,
    write_execution_handoff_atomic,
)
from .stage1_scanner import Stage1Config, scan_all_usdt_perpetuals, write_scan_atomic


FIVE_MINUTES_MS = 5 * 60 * 1000


def next_five_minute_run_ms(now_ms: int, offset_seconds: int = 3) -> int:
    """Return next 5-minute UTC boundary plus a small close-confirmation offset."""
    offset_ms = max(0, offset_seconds) * 1000
    boundary = ((now_ms // FIVE_MINUTES_MS) + 1) * FIVE_MINUTES_MS
    return boundary + offset_ms


def run_forever(
    config: Stage1Config | None = None,
    offset_seconds: int = 3,
    on_scan: Callable[[dict], None] | None = None,
) -> None:
    """Run one full-universe scan after each 5m candle boundary.

    The scheduler is boundary-based instead of `sleep(300)`, so scan duration
    cannot cause cadence drift. One candle close is processed at most once.
    """
    cfg = config or Stage1Config()
    client = BinancePublicClient(timeout=cfg.request_timeout, retries=cfg.retries)
    last_processed_close: int | None = None

    while True:
        now_ms = int(time.time() * 1000)
        target_ms = next_five_minute_run_ms(now_ms, offset_seconds=offset_seconds)
        time.sleep(max(0.0, (target_ms - now_ms) / 1000.0))

        scan = scan_all_usdt_perpetuals(client=client, config=cfg)
        close_time = scan.candle_close_time_ms

        if close_time is not None and close_time == last_processed_close:
            continue

        write_scan_atomic(scan, cfg.output_path)
        write_execution_handoff_atomic(
            scan,
            default_execution_handoff_path(cfg.output_path),
        )
        if close_time is not None:
            last_processed_close = close_time

        if on_scan:
            on_scan(scan.to_dict())
