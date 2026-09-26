from __future__ import annotations

import argparse
import json

from .binance import BinancePublicClient
from .scheduler import run_forever
from .stage1_scanner import Stage1Config, scan_all_usdt_perpetuals, write_scan_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="BabaBot Market Radar — Stage 1 scanner")
    parser.add_argument("--once", action="store_true", help="run one full-universe scan and exit")
    parser.add_argument("--json", action="store_true", help="print the scan JSON")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--output", default="data/latest_scan.json")
    parser.add_argument("--offset-seconds", type=int, default=3)
    args = parser.parse_args()

    cfg = Stage1Config(workers=max(1, args.workers), output_path=args.output)

    if args.once:
        client = BinancePublicClient(timeout=cfg.request_timeout, retries=cfg.retries)
        scan = scan_all_usdt_perpetuals(client=client, config=cfg)
        path = write_scan_atomic(scan, cfg.output_path)
        if args.json:
            print(json.dumps(scan.to_dict(), indent=2, sort_keys=True))
        else:
            print(
                f"Stage 1 scan complete: {scan.completed_count}/{scan.universe_count} "
                f"symbols, failed={scan.failed_count}, output={path}"
            )
        return 0 if scan.completed_count > 0 else 1

    run_forever(config=cfg, offset_seconds=max(0, args.offset_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
