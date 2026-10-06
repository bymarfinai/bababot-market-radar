from __future__ import annotations

import argparse
import csv
import gzip
import io
import itertools
import json
import math
import threading
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2.extras
import requests

from market_radar.persistence import _postgres_connect


VERSION = "lq3b-breakout-acceptance-retest-v1"
EXPECTED_COHORT = 102

NOTIONAL = 500.0
FEE_RATE = 0.0005
SLIPPAGE_BPS = 2.0

ACCEPT_BUFFERS = (0.00, 0.05, 0.10)
ACCEPT_HOLDS_S = (15, 30, 60)
RETEST_BANDS = (0.05, 0.10, 0.15)
RETEST_HOLDS_S = (15, 30)
RECLAIMS = (0.03, 0.05, 0.10)
SLS = (0.30, 0.40, 0.50)

MAX_ACCEPT_MS = 5 * 60_000
MAX_RETEST_MS = 5 * 60_000
ACCEPT_WIGGLE_PCT = 0.03
RETEST_LOWER_TOLERANCE_PCT = 0.03

REPRESENTATIVE_RULE = {
    "accept_buffer_pct": 0.05,
    "accept_hold_s": 15,
    "retest_band_pct": 0.10,
    "retest_hold_s": 15,
    "reclaim_pct": 0.03,
}

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_positions(ids: list[str]) -> dict[str, dict[str, Any]]:
    query = """
        select position_id, symbol, opened_at_ms, closed_at_ms
        from positions
        where position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (ids,))
            rows = [dict(x) for x in cur.fetchall()]
    out = {str(x["position_id"]): x for x in rows}
    if len(out) != len(ids):
        missing = sorted(set(ids) - set(out))
        raise RuntimeError(f"position coverage {len(out)}/{len(ids)} missing={missing[:5]}")
    return out


def _days(start_ms: int, end_ms: int) -> list[str]:
    start = datetime.fromtimestamp(start_ms / 1000.0, timezone.utc).date()
    end = datetime.fromtimestamp(end_ms / 1000.0, timezone.utc).date()
    out: list[str] = []
    d = start
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _download(symbol: str, day: str) -> list[tuple[int, float]]:
    url = (
        "https://data.binance.vision/data/futures/um/daily/aggTrades/"
        f"{symbol}/{symbol}-aggTrades-{day}.zip"
    )
    response = _session().get(url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP_{response.status_code} {symbol} {day}")
    out: list[tuple[int, float]] = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        with archive.open(archive.namelist()[0]) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8"))
            first = next(reader, None)
            iterator = (
                reader
                if first and first[0] == "agg_trade_id"
                else itertools.chain([first], reader)
            )
            for row in iterator:
                if not row:
                    continue
                try:
                    px = float(row[1])
                    ts = int(row[5])
                except (ValueError, IndexError, TypeError):
                    continue
                if px > 0 and math.isfinite(px):
                    out.append((ts, px))
    return out


def _load_paths(
    cohort: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
    cache_path: Path,
    workers: int,
) -> tuple[dict[str, list[tuple[int, float]]], list[str]]:
    if cache_path.exists():
        with gzip.open(cache_path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        paths = {
            pid: [(int(ts), float(px)) for ts, px in rows]
            for pid, rows in payload.get("paths", {}).items()
        }
        if len(paths) == len(cohort):
            return paths, list(payload.get("errors", []))

    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in cohort:
        pid = str(row["position_id"])
        p = positions[pid]
        for day in _days(int(p["opened_at_ms"]), int(p["closed_at_ms"])):
            groups[(str(p["symbol"]), day)].append(pid)

    archives: dict[tuple[str, str], list[tuple[int, float]]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_map = {
            pool.submit(_download, symbol, day): (symbol, day)
            for symbol, day in groups
        }
        for future in as_completed(future_map):
            key = future_map[future]
            try:
                archives[key] = future.result()
            except Exception as exc:
                errors.append(f"{key[0]} {key[1]}: {exc}")

    paths: dict[str, list[tuple[int, float]]] = {}
    for row in cohort:
        pid = str(row["position_id"])
        p = positions[pid]
        opened = int(p["opened_at_ms"])
        closed = int(p["closed_at_ms"])
        raw: list[tuple[int, float]] = []
        for day in _days(opened, closed):
            raw.extend(archives.get((str(p["symbol"]), day), []))
        paths[pid] = sorted((ts, px) for ts, px in raw if opened <= ts <= closed)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(cache_path, "wt", encoding="utf-8") as fh:
        json.dump({"version": VERSION, "paths": paths, "errors": errors}, fh)
    return paths, errors


def _index_at_or_after(
    path: list[tuple[int, float]],
    start_i: int,
    target_ts: int,
) -> int | None:
    for i in range(start_i, len(path)):
        if path[i][0] >= target_ts:
            return i
    return None


def _sequence(
    path: list[tuple[int, float]],
    *,
    opened_ms: int,
    lower: float,
    upper: float,
    accept_buffer_pct: float,
    accept_hold_s: int,
    retest_band_pct: float,
    retest_hold_s: int,
    reclaim_pct: float,
) -> dict[str, Any] | None:
    if not path:
        return None

    accept_threshold = upper * (1.0 + accept_buffer_pct / 100.0)
    accept_floor = upper * (1.0 - ACCEPT_WIGGLE_PCT / 100.0)

    cross_i = None
    for i, (ts, px) in enumerate(path):
        if ts > opened_ms + MAX_ACCEPT_MS:
            break
        if px >= accept_threshold:
            cross_i = i
            break
    if cross_i is None:
        return None

    cross_ts = path[cross_i][0]
    accept_i = _index_at_or_after(
        path,
        cross_i,
        cross_ts + accept_hold_s * 1000,
    )
    if accept_i is None:
        return None
    if min(px for _, px in path[cross_i : accept_i + 1]) < accept_floor:
        return None
    if path[accept_i][1] < upper:
        return None

    retest_ceiling = upper * (1.0 + retest_band_pct / 100.0)
    retest_i = None
    for i in range(accept_i + 1, len(path)):
        ts, px = path[i]
        if ts > path[accept_i][0] + MAX_RETEST_MS:
            break
        if px <= retest_ceiling:
            retest_i = i
            break
    if retest_i is None:
        return None

    retest_hold_i = _index_at_or_after(
        path,
        retest_i,
        path[retest_i][0] + retest_hold_s * 1000,
    )
    if retest_hold_i is None:
        return None

    lower_floor = lower * (1.0 - RETEST_LOWER_TOLERANCE_PCT / 100.0)
    retest_slice = path[retest_i : retest_hold_i + 1]
    if min(px for _, px in retest_slice) < lower_floor:
        return None

    local_low = min(px for _, px in retest_slice)
    reclaim_threshold = max(
        upper,
        local_low * (1.0 + reclaim_pct / 100.0),
    )

    entry_i = None
    for i in range(retest_hold_i, len(path)):
        ts, px = path[i]
        if ts > path[retest_i][0] + MAX_RETEST_MS:
            break
        if px < lower_floor:
            return None
        if px >= reclaim_threshold:
            entry_i = i
            break
    if entry_i is None:
        return None

    return {
        "entry_i": entry_i,
        "entry_ts": path[entry_i][0],
        "entry_market": path[entry_i][1],
        "time_to_entry_s": (path[entry_i][0] - opened_ms) / 1000.0,
    }


def _net(entry_market: float, exit_market: float) -> float:
    entry_fill = entry_market * (1.0 + SLIPPAGE_BPS / 10000.0)
    exit_fill = exit_market * (1.0 - SLIPPAGE_BPS / 10000.0)
    qty = NOTIONAL / entry_fill
    gross = qty * (exit_fill - entry_fill)
    return gross - qty * entry_fill * FEE_RATE - qty * exit_fill * FEE_RATE


def _replay(
    path: list[tuple[int, float]],
    seq: dict[str, Any],
    sl_pct: float,
) -> dict[str, Any] | None:
    entry_i = int(seq["entry_i"])
    entry = float(seq["entry_market"])
    future = path[entry_i + 1 :]
    if not future:
        return None

    stop = entry * (1.0 - sl_pct / 100.0)
    max_px = entry
    min_px = entry
    exit_market = future[-1][1]
    reason = "HISTORICAL_CLOSE"

    for _, px in future:
        max_px = max(max_px, px)
        min_px = min(min_px, px)
        if px <= stop:
            exit_market = px
            reason = "SL"
            break

    return {
        "net_pnl": _net(entry, exit_market),
        "reason": reason,
        "post_entry_mfe_pct": (max_px / entry - 1.0) * 100.0,
        "post_entry_mae_pct": (min_px / entry - 1.0) * 100.0,
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"entries": 0}
    pnls = [float(x["net_pnl"]) for x in rows]
    wins = sum(x > 0 for x in pnls)
    gross_win = sum(max(0.0, x) for x in pnls)
    gross_loss = -sum(min(0.0, x) for x in pnls)
    mfes = [float(x["post_entry_mfe_pct"]) for x in rows]
    return {
        "entries": len(rows),
        "net_pnl": round(sum(pnls), 2),
        "wr_pct": round(100.0 * wins / len(rows), 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "median_post_entry_mfe_pct": round(sorted(mfes)[len(mfes) // 2], 4),
        "post_entry_mfe_ge_0p5_pct": round(
            100.0 * sum(x >= 0.5 for x in mfes) / len(mfes), 2
        ),
        "post_entry_mfe_ge_1_pct": round(
            100.0 * sum(x >= 1.0 for x in mfes) / len(mfes), 2
        ),
        "class_mix": dict(Counter(str(x["future_outcome_label"]) for x in rows)),
        "group_mix": dict(Counter(str(x["outcome_group"]) for x in rows)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort-csv",
        default="research/liquidity_location/results/lq3a_fresh15m_trade_level.csv",
    )
    ap.add_argument(
        "--cache-path",
        default="/opt/core-app/data/lq3b_raw_paths.json.gz",
    )
    ap.add_argument(
        "--output-dir",
        default="research/liquidity_location/results",
    )
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    cohort = _load_csv(Path(args.cohort_csv))
    if len(cohort) != EXPECTED_COHORT:
        raise RuntimeError(f"expected cohort={EXPECTED_COHORT}, got={len(cohort)}")

    ids = [str(x["position_id"]) for x in cohort]
    positions = _load_positions(ids)
    paths, errors = _load_paths(
        cohort,
        positions,
        Path(args.cache_path),
        args.workers,
    )

    cells: list[dict[str, Any]] = []
    for ab in ACCEPT_BUFFERS:
        for ah in ACCEPT_HOLDS_S:
            for rb in RETEST_BANDS:
                for rh in RETEST_HOLDS_S:
                    for rc in RECLAIMS:
                        seqs: dict[str, dict[str, Any]] = {}
                        for row in cohort:
                            pid = str(row["position_id"])
                            seq = _sequence(
                                paths.get(pid) or [],
                                opened_ms=int(row["opened_at_ms"]),
                                lower=float(row["supply_lower"]),
                                upper=float(row["supply_upper"]),
                                accept_buffer_pct=ab,
                                accept_hold_s=ah,
                                retest_band_pct=rb,
                                retest_hold_s=rh,
                                reclaim_pct=rc,
                            )
                            if seq is not None:
                                seqs[pid] = seq

                        for sl in SLS:
                            replay_rows: list[dict[str, Any]] = []
                            for row in cohort:
                                pid = str(row["position_id"])
                                seq = seqs.get(pid)
                                if seq is None:
                                    continue
                                replay = _replay(paths[pid], seq, sl)
                                if replay is None:
                                    continue
                                replay_rows.append(
                                    {
                                        **replay,
                                        "position_id": pid,
                                        "chrono_split": row["chrono_split"],
                                        "future_outcome_label": row["future_outcome_label"],
                                        "outcome_group": row["outcome_group"],
                                    }
                                )
                            split = {
                                name: [
                                    x for x in replay_rows
                                    if x["chrono_split"] == name
                                ]
                                for name in ("TRAIN", "VALIDATION", "RESERVE")
                            }
                            cells.append(
                                {
                                    "accept_buffer_pct": ab,
                                    "accept_hold_s": ah,
                                    "retest_band_pct": rb,
                                    "retest_hold_s": rh,
                                    "reclaim_pct": rc,
                                    "sl_pct": sl,
                                    "TRAIN": _metrics(split["TRAIN"]),
                                    "VALIDATION": _metrics(split["VALIDATION"]),
                                    "RESERVE": _metrics(split["RESERVE"]),
                                    "ALL": _metrics(replay_rows),
                                }
                            )

    max_train = max(int(c["TRAIN"]["entries"]) for c in cells)
    eligible = [c for c in cells if int(c["TRAIN"]["entries"]) >= 8]
    positive_all_splits = [
        c for c in cells
        if float(c["TRAIN"].get("net_pnl") or 0) > 0
        and float(c["VALIDATION"].get("net_pnl") or 0) > 0
        and float(c["RESERVE"].get("net_pnl") or 0) > 0
    ]

    representative = [
        c for c in cells
        if float(c["accept_buffer_pct"]) == 0.05
        and int(c["accept_hold_s"]) == 15
        and float(c["retest_band_pct"]) == 0.10
        and int(c["retest_hold_s"]) == 15
        and float(c["reclaim_pct"]) == 0.03
    ]

    summary = {
        "version": VERSION,
        "coverage": {
            "cohort": len(cohort),
            "nonempty_paths": sum(bool(paths.get(pid)) for pid in ids),
            "archive_errors": errors,
        },
        "grid_cells": len(cells),
        "max_train_entries_any_cell": max_train,
        "eligible_train_ge8_cells": len(eligible),
        "positive_train_validation_reserve_cells": len(positive_all_splits),
        "representative_rule": REPRESENTATIVE_RULE,
        "representative_economics": representative,
        "production_authority": "NONE",
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lq3b_replay_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
