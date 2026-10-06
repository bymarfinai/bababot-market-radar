from __future__ import annotations

import argparse
import csv
import io
import itertools
import json
import math
import statistics
import threading
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2.extras
import requests

from market_radar.persistence import _postgres_connect


STAGE = "RD-0B-WD555-REVERSE-TP-SL-GRID"
EXPECTED_LONG_RESOLVED = 1236
EXPECTED_WRONG_DIRECTION = 555
NOTIONAL_USDT = 500.0
FEE_RATE = 0.0005
SLIPPAGE_BPS = 2.0
HORIZON_MIN = 30
TPS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
SLS = (0.3, 0.4, 0.5)

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        obj = json.loads(value or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _entry_fill(side: str, market: float, slip_bps: float) -> float:
    slip = max(0.0, float(slip_bps)) / 10000.0
    return market * (1.0 + slip if side == "LONG" else 1.0 - slip)


def _exit_fill(side: str, market: float, slip_bps: float) -> float:
    slip = max(0.0, float(slip_bps)) / 10000.0
    return market * (1.0 - slip if side == "LONG" else 1.0 + slip)


def _gross(side: str, qty: float, entry: float, exit_price: float) -> float:
    if side == "LONG":
        return qty * (exit_price - entry)
    return qty * (entry - exit_price)


def _load_resolved_long_ids(data_dir: Path) -> set[str]:
    path = data_dir / "wd5h4a_temporal_features.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing frozen temporal source: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [
            r for r in csv.DictReader(fh)
            if str(r.get("side") or "").upper() == "LONG"
            and str(r.get("primary_meta_label") or "") in {"META_WIN", "META_LOSS"}
        ]
    ids = {str(r["position_id"]) for r in rows}
    if len(ids) != EXPECTED_LONG_RESOLVED:
        raise RuntimeError(
            f"resolved LONG universe drift: expected {EXPECTED_LONG_RESOLVED}, got {len(ids)}"
        )
    return ids


def _load_555(data_dir: Path) -> list[dict[str, Any]]:
    resolved_ids = _load_resolved_long_ids(data_dir)
    query = """
        select
            w.position_id, w.symbol, w.side, w.opened_at_ms, w.closed_at_ms,
            w.outcome_label, w.max_mfe_pct, w.min_mae_pct,
            w.realized_pnl, w.realized_pnl_pct,
            p.entry_price, p.raw_json
        from wd1_trade_labels w
        join positions p on p.position_id=w.position_id
        where w.position_id = any(%s)
          and w.side='LONG'
          and w.outcome_label='TRUE_WRONG_DIRECTION'
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (list(resolved_ids),))
            rows = [dict(r) for r in cur.fetchall()]
    if len(rows) != EXPECTED_WRONG_DIRECTION:
        raise RuntimeError(
            f"wrong-direction universe drift: expected {EXPECTED_WRONG_DIRECTION}, got {len(rows)}"
        )
    return rows


def _entry_market(position: dict[str, Any]) -> float:
    raw = _j(position.get("raw_json"))
    value = raw.get("entry_market_price")
    if value is not None:
        x = float(value)
        if math.isfinite(x) and x > 0:
            return x

    # Historical LONG entry fill already includes adverse +slippage. Undo it
    # to recover the market point used for the mirror SHORT.
    fill = float(position["entry_price"])
    historical_slip = float(raw.get("slippage_bps") or 2.0) / 10000.0
    market = fill / (1.0 + historical_slip)
    if not math.isfinite(market) or market <= 0:
        raise RuntimeError(f"invalid reconstructed entry market for {position['position_id']}")
    return market


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).date().isoformat()


def _needed_days(start_ms: int, end_ms: int) -> list[str]:
    start = datetime.fromtimestamp(start_ms / 1000.0, timezone.utc).date()
    end = datetime.fromtimestamp(end_ms / 1000.0, timezone.utc).date()
    out: list[str] = []
    day = start
    while day <= end:
        out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def _download_aggtrades(symbol: str, day: str) -> list[tuple[int, float]]:
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
                    price = float(row[1])
                    ts = int(row[5])
                except (ValueError, IndexError, TypeError):
                    continue
                if price > 0 and math.isfinite(price):
                    out.append((ts, price))
    return out


def _load_paths(
    positions: list[dict[str, Any]],
    *,
    workers: int,
) -> tuple[dict[str, list[tuple[int, float]]], list[str]]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_id = {str(p["position_id"]): p for p in positions}
    for p in positions:
        pid = str(p["position_id"])
        opened = int(p["opened_at_ms"])
        closed = int(p["closed_at_ms"])
        for day in _needed_days(opened, closed):
            groups[(str(p["symbol"]), day)].append(pid)

    archives: dict[tuple[str, str], list[tuple[int, float]]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_map = {
            pool.submit(_download_aggtrades, symbol, day): (symbol, day)
            for symbol, day in groups
        }
        for future in as_completed(future_map):
            key = future_map[future]
            try:
                archives[key] = future.result()
            except Exception as exc:
                errors.append(f"{key[0]} {key[1]}: {exc}")

    paths: dict[str, list[tuple[int, float]]] = {}
    for pid, p in by_id.items():
        opened = int(p["opened_at_ms"])
        end = int(p["closed_at_ms"])
        rows: list[tuple[int, float]] = []
        for day in _needed_days(opened, end):
            rows.extend(archives.get((str(p["symbol"]), day), []))
        rows = sorted((ts, px) for ts, px in rows if opened < ts <= end)
        paths[pid] = rows
    return paths, errors


def _net_at(
    *,
    side: str,
    qty: float,
    entry_fill: float,
    market: float,
    fee_rate: float,
    slip_bps: float,
) -> float:
    exit_fill = _exit_fill(side, market, slip_bps)
    entry_fee = qty * entry_fill * fee_rate
    exit_fee = qty * exit_fill * fee_rate
    return _gross(side, qty, entry_fill, exit_fill) - entry_fee - exit_fee


def _price_return_pct(side: str, entry_market: float, market: float) -> float:
    if side == "LONG":
        return 100.0 * (market / entry_market - 1.0)
    return 100.0 * ((entry_market - market) / entry_market)


def _run_cell(
    position: dict[str, Any],
    path: list[tuple[int, float]],
    *,
    tp_pct: float,
    sl_pct: float,
    threshold_mode: str,
    fee_rate: float,
    slip_bps: float,
    notional: float,
) -> dict[str, Any]:
    side = "SHORT"
    entry_market = _entry_market(position)
    entry_fill = _entry_fill(side, entry_market, slip_bps)
    qty = notional / entry_fill
    tp_usdt = notional * tp_pct / 100.0
    sl_usdt = -notional * sl_pct / 100.0

    reason = "NO_PATH"
    exit_ts = None
    exit_market = None
    net = float("nan")
    last = None

    for ts, market in path:
        last = (ts, market)
        candidate_net = _net_at(
            side=side,
            qty=qty,
            entry_fill=entry_fill,
            market=market,
            fee_rate=fee_rate,
            slip_bps=slip_bps,
        )
        price_ret = _price_return_pct(side, entry_market, market)

        if threshold_mode == "NET":
            tp_hit = candidate_net >= tp_usdt
            sl_hit = candidate_net <= sl_usdt
        elif threshold_mode == "PRICE":
            tp_hit = price_ret >= tp_pct
            sl_hit = price_ret <= -sl_pct
        else:
            raise ValueError(threshold_mode)

        if tp_hit or sl_hit:
            reason = "TP" if tp_hit else "SL"
            exit_ts = ts
            exit_market = market
            net = candidate_net
            break

    if reason == "NO_PATH" and last is not None:
        reason = "HORIZON"
        exit_ts, exit_market = last
        net = _net_at(
            side=side,
            qty=qty,
            entry_fill=entry_fill,
            market=exit_market,
            fee_rate=fee_rate,
            slip_bps=slip_bps,
        )

    return {
        "reason": reason,
        "exit_ts": exit_ts,
        "exit_market": exit_market,
        "net_pnl": net,
        "positive": bool(math.isfinite(net) and net > 0),
    }


def _gross_sanity(position: dict[str, Any], path: list[tuple[int, float]]) -> dict[str, Any]:
    entry = _entry_market(position)
    best = -math.inf
    worst = math.inf
    first_tp03 = None
    first_sl04 = None
    first_sl05 = None
    for ts, market in path:
        ret = _price_return_pct("SHORT", entry, market)
        best = max(best, ret)
        worst = min(worst, ret)
        if first_tp03 is None and ret >= 0.3:
            first_tp03 = ts
        if first_sl04 is None and ret <= -0.4:
            first_sl04 = ts
        if first_sl05 is None and ret <= -0.5:
            first_sl05 = ts
    return {
        "best_short_price_pct": None if best == -math.inf else best,
        "worst_short_price_pct": None if worst == math.inf else worst,
        "tp03_before_sl04": (
            first_tp03 is not None
            and (first_sl04 is None or first_tp03 < first_sl04)
        ),
        "tp03_before_sl05": (
            first_tp03 is not None
            and (first_sl05 is None or first_tp03 < first_sl05)
        ),
    }


def _summarize(detail: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in detail if math.isfinite(float(r["net_pnl"]))]
    pnl = [float(r["net_pnl"]) for r in valid]
    positives = sum(x > 0 for x in pnl)
    gains = sum(x for x in pnl if x > 0)
    losses = -sum(x for x in pnl if x < 0)
    return {
        "n": len(detail),
        "valid_n": len(valid),
        "tp_n": sum(r["reason"] == "TP" for r in detail),
        "sl_n": sum(r["reason"] == "SL" for r in detail),
        "horizon_n": sum(r["reason"] == "HORIZON" for r in detail),
        "no_path_n": sum(r["reason"] == "NO_PATH" for r in detail),
        "positive_n": positives,
        "win_rate_pct": 100.0 * positives / len(valid) if valid else None,
        "net_pnl": sum(pnl),
        "avg_pnl": statistics.mean(pnl) if pnl else None,
        "profit_factor": gains / losses if losses > 0 else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="/app/data")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "results"))
    parser.add_argument("--workers", type=int, default=2)
    # Primary RD-0B is deliberately bounded by each trade's original
    # historical close timestamp. This isolates the effect of direction and
    # TP/SL without inventing a new holding period.
    args = parser.parse_args()

    positions = _load_555(Path(args.data_dir))
    paths, errors = _load_paths(
        positions,
        workers=args.workers,
    )
    if errors:
        raise RuntimeError(f"archive fetch errors={len(errors)} sample={errors[:5]}")

    missing = [p["position_id"] for p in positions if not paths.get(str(p["position_id"]))]
    if missing:
        raise RuntimeError(f"missing aggregate-trade paths={len(missing)} sample={missing[:5]}")

    sanity = []
    for p in positions:
        pid = str(p["position_id"])
        check = _gross_sanity(p, paths[pid])
        sanity.append({"position_id": pid, **check})

    # Diagnostic only. TRUE_WRONG_DIRECTION is based on the lifecycle's
    # observed MFE/MAE series, while this replay uses archived aggTrades.
    # Boundary and sub-evaluation micro-path can therefore differ from the
    # observed taxonomy path. Report the discrepancy instead of rejecting an
    # otherwise complete raw replay.
    sanity_04 = sum(bool(r["tp03_before_sl04"]) for r in sanity)
    sanity_05 = sum(bool(r["tp03_before_sl05"]) for r in sanity)

    all_detail: list[dict[str, Any]] = []
    grid: list[dict[str, Any]] = []

    # PRICE lane = familiar TP/SL as market move; realized dollars still include
    # fee + slippage. NET lane = WD-4 convention, where TP/SL are thresholds on
    # net PnL after execution friction.
    for mode in ("PRICE", "NET"):
        for tp in TPS:
            for sl in SLS:
                cell = []
                for p in positions:
                    pid = str(p["position_id"])
                    r = _run_cell(
                        p,
                        paths[pid],
                        tp_pct=tp,
                        sl_pct=sl,
                        threshold_mode=mode,
                        fee_rate=FEE_RATE,
                        slip_bps=SLIPPAGE_BPS,
                        notional=NOTIONAL_USDT,
                    )
                    row = {
                        "mode": mode,
                        "tp_pct": tp,
                        "sl_pct": sl,
                        "position_id": pid,
                        "symbol": p["symbol"],
                        "opened_at_ms": p["opened_at_ms"],
                        "historical_pnl": p["realized_pnl"],
                        "historical_pnl_pct": p["realized_pnl_pct"],
                        "historical_mfe_pct": p["max_mfe_pct"],
                        "historical_mae_pct": p["min_mae_pct"],
                        **r,
                    }
                    cell.append(row)
                    all_detail.append(row)
                grid.append({
                    "mode": mode,
                    "tp_pct": tp,
                    "sl_pct": sl,
                    **_summarize(cell),
                })

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with (out / "RD0B_WD555_TP_SL_GRID.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)

    with (out / "RD0B_WD555_TRADE_DETAIL.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_detail[0].keys()))
        writer.writeheader()
        writer.writerows(all_detail)

    result = {
        "stage": STAGE,
        "authority": "RESEARCH_ONLY",
        "universe": {
            "resolved_long_n": EXPECTED_LONG_RESOLVED,
            "true_wrong_direction_long_n": len(positions),
        },
        "execution": {
            "side": "SHORT",
            "entry": "same original market-entry point",
            "notional_usdt": NOTIONAL_USDT,
            "fee_rate_per_side": FEE_RATE,
            "slippage_bps_per_side": SLIPPAGE_BPS,
            "holding_window": "original opened_at_ms -> original closed_at_ms",
            "path": "Binance USD-M archived aggregate trades; true first-touch ordering",
            "fallback": "last aggregate trade at/before the original historical close",
            "price_lane": "TP/SL thresholds are market-price returns; reported PnL includes costs",
            "net_lane": "TP/SL thresholds are net PnL % of $500 after fees/slippage",
        },
        "sanity": {
            "gross_tp0p3_before_sl0p4_n": sanity_04,
            "gross_tp0p3_before_sl0p5_n": sanity_05,
            "expected_n": EXPECTED_WRONG_DIRECTION,
        },
        "grid": grid,
    }
    (out / "RD0B_WD555_TP_SL_GRID.json").write_text(
        json.dumps(result, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
