from __future__ import annotations

import argparse
import json

from .binance import BinancePublicClient
from .scheduler import run_forever
from .stage1_scanner import Stage1Config, scan_all_usdt_perpetuals, write_scan_atomic


def _print_candidates(scan) -> None:
    print(
        f"Stage 1+2+3 scan complete: {scan.completed_count}/{scan.universe_count} symbols, "
        f"moving={scan.moving_candidate_count}, "
        f"evaluated={scan.movement_evaluated_count}, "
        f"skipped={scan.movement_skipped_count}, "
        f"failed={scan.failed_count}, "
        f"IGNITION={scan.ignition_count}, "
        f"EXPANSION={scan.expansion_count}, "
        f"EXHAUSTION={scan.exhaustion_count}"
    )

    if not scan.moving_candidates:
        print("No moving candidates detected.")
        return

    print()
    print(
        f"{'SYMBOL':>14} {'STAGE':>12} {'STATE':>20} {'DIR':>6} {'5M%':>8} "
        f"{'RET-X':>8} {'VOL-X':>8} {'RANGE-X':>8} {'EVID':>6}"
    )
    print("-" * 90)
    for item in scan.moving_candidates:
        print(
            f"{item.symbol:>14} {str(item.stage):>12} {item.movement_state:>20} {item.direction_hint:>6} "
            f"{item.ret_5m_pct:>+8.3f} {item.return_expansion_ratio:>8.2f} "
            f"{item.volume_ratio:>8.2f} {item.range_ratio:>8.2f} "
            f"{item.evidence_count:>6}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="BabaBot Market Radar — Stage 1+2+3")
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
            _print_candidates(scan)
            print(f"Output: {path}")

        return 0 if scan.completed_count > 0 else 1

    run_forever(config=cfg, offset_seconds=max(0, args.offset_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
