from __future__ import annotations

import argparse
import json
import os
import sys
import threading

from .ai_approval import start_pending_approval_worker
from .binance import BinancePublicClient
from .execution_handoff import (
    default_execution_handoff_path,
    write_execution_handoff_atomic,
)
from .paper_trading import start_paper_trading_loop
from .position_lifecycle import start_position_lifecycle_worker
from .persistence import (
    database_path,
    persistence_summary,
    record_actionable_signals,
)
from .read_api import serve_read_api
from .scheduler import run_forever
from .stage1_scanner import Stage1Config, scan_all_usdt_perpetuals, write_scan_atomic


def _print_candidates(scan) -> None:
    print(
        f"Stage 1+2+3+4+5+6 scan complete: {scan.completed_count}/{scan.universe_count} symbols, "
        f"moving={scan.moving_candidate_count}, "
        f"evaluated={scan.movement_evaluated_count}, "
        f"skipped={scan.movement_skipped_count}, "
        f"failed={scan.failed_count}, "
        f"IGNITION={scan.ignition_count}, "
        f"EXPANSION={scan.expansion_count}, "
        f"EXHAUSTION={scan.exhaustion_count}, "
        f"context_ok={scan.context_complete_count}, "
        f"context_partial={scan.context_partial_count}, "
        f"LONG={scan.long_decision_count}, "
        f"SHORT={scan.short_decision_count}, "
        f"NO_TRADE={scan.no_trade_decision_count}"
    )

    if not scan.moving_candidates:
        print("No moving candidates detected.")
        return

    print()
    print(
        f"{'SYMBOL':>14} {'DECISION':>10} {'STAGE':>12} {'LONG':>7} {'SHORT':>7} "
        f"{'STRUCT':>18} {'TAKER':>8} {'OI%':>8} {'REGIME':>10}"
    )
    print("-" * 90)
    for item in scan.moving_candidates:
        ctx = item.market_context
        oi = ctx.raw_oi_change_pct if ctx and ctx.raw_oi_change_pct is not None else 0.0
        print(
            f"{item.symbol:>14} {str(item.decision or 'N/A'):>10} {str(item.stage):>12} "
            f"{(item.long_score or 0.0):>7.1f} {(item.short_score or 0.0):>7.1f} "
            f"{(ctx.structure_status if ctx else 'N/A'):>18} "
            f"{(ctx.taker_bias if ctx else 'N/A'):>8} "
            f"{oi:>+8.3f} "
            f"{(ctx.market_regime if ctx and ctx.market_regime else 'N/A'):>10}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="BabaBot Market Radar — Stage 1+2+3+4+5+6")
    parser.add_argument("--once", action="store_true", help="run one full-universe scan and exit")
    parser.add_argument("--json", action="store_true", help="print the scan JSON")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--output", default="data/latest_scan.json")
    parser.add_argument("--offset-seconds", type=int, default=3)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="also expose the Stage 7 read-only HTTP API",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8080")),
        help="read-only API port (defaults to $PORT or 8080)",
    )
    args = parser.parse_args()

    cfg = Stage1Config(workers=max(1, args.workers), output_path=args.output)

    try:
        summary = persistence_summary()
        print(
            "Stage 10 persistence ready: "
            f"backend={summary.get('backend')} "
            f"signals={summary.get('signal_count')} "
            f"long={summary.get('long_count')} "
            f"short={summary.get('short_count')} "
            f"pending_outcomes={summary.get('pending_outcomes')}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"Stage 10 persistence startup check failed: {exc}",
            file=sys.stderr,
            flush=True,
        )

    start_pending_approval_worker()
    start_position_lifecycle_worker()
    start_paper_trading_loop()

    if args.once:
        client = BinancePublicClient(timeout=cfg.request_timeout, retries=cfg.retries)
        scan = scan_all_usdt_perpetuals(client=client, config=cfg)
        path = write_scan_atomic(scan, cfg.output_path)
        handoff_path = write_execution_handoff_atomic(
            scan,
            default_execution_handoff_path(cfg.output_path),
        )
        persistence_result = record_actionable_signals(scan)
        start_pending_approval_worker()
        start_position_lifecycle_worker()

        if args.json:
            print(json.dumps(scan.to_dict(), indent=2, sort_keys=True))
        else:
            _print_candidates(scan)
            print(f"Output: {path}")
            print(f"Execution handoff: {handoff_path}")
            print(
                f"Persistent DB: {database_path()} "
                f"(inserted={persistence_result['inserted']}, "
                f"updated={persistence_result['updated']})"
            )

        return 0 if scan.completed_count > 0 else 1

    if args.serve:
        api_thread = threading.Thread(
            target=serve_read_api,
            kwargs={
                "port": max(1, args.port),
                "scan_path": cfg.output_path,
            },
            daemon=True,
            name="market-radar-read-api",
        )
        api_thread.start()

    run_forever(config=cfg, offset_seconds=max(0, args.offset_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
