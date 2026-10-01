from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.binance import BinancePublicClient
from market_radar.persistence import _postgres_connect
from .wd2_anatomy import WD2_CUTOFF_MS


WD4_VERSION = "wd4-resolution-mapping-v1"
WRONG = "TRUE_WRONG_DIRECTION"
NOTIONAL_USDT = 500.0
PRIMARY_HORIZON_MIN = 30
SENSITIVITY_HORIZONS_MIN = (15, 30, 60)
STRONG_WIN_PCT = 0.50
ROBUST_WIN_PCT = 1.00
CACHE_PATH = Path("/app/data/wd4_wrong_direction_1m_cache.jsonl")


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _entry_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 + slip if side == "LONG" else 1.0 - slip)


def _exit_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 - slip if side == "LONG" else 1.0 + slip)


def _gross(side: str, qty: float, entry: float, exit_price: float) -> float:
    return (
        qty * (exit_price - entry)
        if side == "LONG"
        else qty * (entry - exit_price)
    )


def _opposite(side: str) -> str:
    return "SHORT" if side == "LONG" else "LONG"


def _load_wrong_positions() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side,
            w.opened_at_ms, w.closed_at_ms, w.realized_pnl,
            p.entry_price, p.exit_price, p.raw_json
        from wd1_trade_labels w
        join positions p on p.position_id=w.position_id
        where w.outcome_label=%s
          and w.closed_at_ms <= %s
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WRONG, WD2_CUTOFF_MS))
            return [dict(row) for row in cur.fetchall()]


def _cache_load() -> dict[str, list[list[Any]]]:
    out: dict[str, list[list[Any]]] = {}
    if not CACHE_PATH.exists():
        return out
    for line in CACHE_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            pid = str(obj["position_id"])
            rows = obj.get("rows") or []
            if isinstance(rows, list):
                out[pid] = rows
        except Exception:
            continue
    return out


def _fetch_one(position: dict[str, Any]) -> tuple[str, list[list[Any]]]:
    pid = str(position["position_id"])
    symbol = str(position["symbol"])
    opened = int(position["opened_at_ms"])
    start_ms = (opened // 60_000) * 60_000
    end_ms = opened + 62 * 60_000
    client = BinancePublicClient(timeout=8.0, retries=3)
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 70,
        },
    )
    return pid, rows


def ensure_kline_cache(
    positions: list[dict[str, Any]],
    *,
    workers: int = 6,
) -> dict[str, list[list[Any]]]:
    cache = _cache_load()
    missing = [p for p in positions if str(p["position_id"]) not in cache]
    if not missing:
        return cache

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fetched: list[tuple[str, list[list[Any]]]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_fetch_one, p): p for p in missing}
        for i, future in enumerate(as_completed(futures), 1):
            p = futures[future]
            try:
                pid, rows = future.result()
                fetched.append((pid, rows))
                cache[pid] = rows
            except Exception as exc:
                errors.append(f"{p['position_id']}: {exc}")
            if i % 100 == 0:
                time.sleep(0.25)

    if fetched:
        with CACHE_PATH.open("a") as fh:
            for pid, rows in fetched:
                fh.write(json.dumps(
                    {"position_id": pid, "rows": rows},
                    separators=(",", ":"),
                ) + "\n")

    if errors:
        raise RuntimeError(
            f"failed to fetch {len(errors)} WD4 kline paths; sample={errors[:5]}"
        )
    return cache


def _closed_prices(
    rows: list[list[Any]],
    opened_at_ms: int,
    horizon_min: int,
) -> list[tuple[int, float]]:
    end_ms = opened_at_ms + horizon_min * 60_000
    out = []
    for row in rows:
        if len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms <= opened_at_ms or close_ms > end_ms:
            continue
        out.append((close_ms, float(row[4])))
    out.sort()
    return out


def _first_close_at_or_after(
    rows: list[list[Any]],
    target_ms: int,
    max_late_ms: int = 70_000,
) -> tuple[int, float] | None:
    candidates = []
    for row in rows:
        if len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms >= target_ms:
            candidates.append((close_ms, float(row[4])))
    if not candidates:
        return None
    chosen = min(candidates)
    if chosen[0] - target_ms > max_late_ms:
        return None
    return chosen


def _path_metrics(
    *,
    side: str,
    entry_market: float,
    path: list[tuple[int, float]],
    fee_rate: float,
    slippage_bps: float,
    prior_net: float = 0.0,
    notional: float = NOTIONAL_USDT,
) -> dict[str, Any]:
    entry_fill = _entry_fill(side, entry_market, slippage_bps)
    qty = notional / entry_fill
    entry_fee = qty * entry_fill * fee_rate

    best_net = -math.inf
    best_at_ms = None
    first_positive_at_ms = None
    first_strong_at_ms = None
    first_robust_at_ms = None
    final_net = None

    strong_usdt = notional * STRONG_WIN_PCT / 100.0
    robust_usdt = notional * ROBUST_WIN_PCT / 100.0
    stop_0p5_usdt = -notional * 0.50 / 100.0
    stop_1p0_usdt = -notional * 1.00 / 100.0
    first_stop_0p5_at_ms = 0 if prior_net <= stop_0p5_usdt else None
    first_stop_1p0_at_ms = 0 if prior_net <= stop_1p0_usdt else None

    for ts, market in path:
        exit_fill = _exit_fill(side, market, slippage_bps)
        exit_fee = qty * exit_fill * fee_rate
        net = prior_net + _gross(side, qty, entry_fill, exit_fill) - entry_fee - exit_fee
        final_net = net
        if net > best_net:
            best_net = net
            best_at_ms = ts
        if first_positive_at_ms is None and net > 0:
            first_positive_at_ms = ts
        if first_strong_at_ms is None and net >= strong_usdt:
            first_strong_at_ms = ts
        if first_robust_at_ms is None and net >= robust_usdt:
            first_robust_at_ms = ts
        if first_stop_0p5_at_ms is None and net <= stop_0p5_usdt:
            first_stop_0p5_at_ms = ts
        if first_stop_1p0_at_ms is None and net <= stop_1p0_usdt:
            first_stop_1p0_at_ms = ts

    if best_net == -math.inf:
        best_net = None
    return {
        "entry_fill": entry_fill,
        "quantity": qty,
        "prior_net": prior_net,
        "best_net": best_net,
        "best_net_pct_notional": (
            100.0 * best_net / notional if best_net is not None else None
        ),
        "best_at_ms": best_at_ms,
        "final_net": final_net,
        "first_positive_at_ms": first_positive_at_ms,
        "first_strong_at_ms": first_strong_at_ms,
        "first_robust_at_ms": first_robust_at_ms,
        "first_stop_0p5_at_ms": first_stop_0p5_at_ms,
        "first_stop_1p0_at_ms": first_stop_1p0_at_ms,
        "positive_win": first_positive_at_ms is not None,
        "strong_win_0p5": first_strong_at_ms is not None,
        "robust_win_1p0": first_robust_at_ms is not None,
        "tp0p5_before_sl0p5": (
            first_strong_at_ms is not None
            and (
                first_stop_0p5_at_ms is None
                or first_strong_at_ms < first_stop_0p5_at_ms
            )
        ),
        "tp0p5_before_sl1p0": (
            first_strong_at_ms is not None
            and (
                first_stop_1p0_at_ms is None
                or first_strong_at_ms < first_stop_1p0_at_ms
            )
        ),
        "tp1p0_before_sl1p0": (
            first_robust_at_ms is not None
            and (
                first_stop_1p0_at_ms is None
                or first_robust_at_ms < first_stop_1p0_at_ms
            )
        ),
    }


def opposite_from_entry(
    position: dict[str, Any],
    rows: list[list[Any]],
    horizon_min: int,
) -> dict[str, Any]:
    raw = _j(position.get("raw_json"))
    side = _opposite(str(position["side"]).upper())
    market = float(raw.get("entry_market_price") or position["entry_price"])
    fee_rate = float(raw.get("fee_rate") if raw.get("fee_rate") is not None else 0.00075)
    slippage = float(raw.get("slippage_bps") if raw.get("slippage_bps") is not None else 2.0)
    path = _closed_prices(rows, int(position["opened_at_ms"]), horizon_min)
    return _path_metrics(
        side=side,
        entry_market=market,
        path=path,
        fee_rate=fee_rate,
        slippage_bps=slippage,
    )


def flip_after_minutes(
    position: dict[str, Any],
    rows: list[list[Any]],
    flip_min: int,
    horizon_min: int,
) -> dict[str, Any]:
    raw = _j(position.get("raw_json"))
    original_side = str(position["side"]).upper()
    opposite_side = _opposite(original_side)
    opened = int(position["opened_at_ms"])
    fee_rate = float(raw.get("fee_rate") if raw.get("fee_rate") is not None else 0.00075)
    slippage = float(raw.get("slippage_bps") if raw.get("slippage_bps") is not None else 2.0)
    original_entry_fill = float(position["entry_price"])
    original_qty = float(raw.get("initial_quantity") or 0.0)
    original_entry_fee = float(raw.get("entry_fee_total") or 0.0)

    flip = _first_close_at_or_after(rows, opened + flip_min * 60_000)
    if flip is None or original_qty <= 0:
        return {"available": False, "flip_min": flip_min}
    flip_at_ms, flip_market = flip

    original_exit_fill = _exit_fill(original_side, flip_market, slippage)
    original_exit_fee = original_qty * original_exit_fill * fee_rate
    first_leg_net = (
        _gross(
            original_side,
            original_qty,
            original_entry_fill,
            original_exit_fill,
        )
        - original_entry_fee
        - original_exit_fee
    )

    end_ms = opened + horizon_min * 60_000
    path = []
    for row in rows:
        if len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms <= flip_at_ms or close_ms > end_ms:
            continue
        path.append((close_ms, float(row[4])))
    path.sort()

    metrics = _path_metrics(
        side=opposite_side,
        entry_market=flip_market,
        path=path,
        fee_rate=fee_rate,
        slippage_bps=slippage,
        prior_net=first_leg_net,
    )
    return {
        "available": True,
        "flip_min": flip_min,
        "flip_at_ms": flip_at_ms,
        "flip_market_price": flip_market,
        "first_leg_net": first_leg_net,
        **metrics,
    }


def classify_resolution(
    paths: dict[str, dict[str, Any]],
) -> str:
    # Primary WD-4 mapping uses strong +0.5% net wins within 30 minutes.
    if paths["opposite_entry"]["strong_win_0p5"]:
        return "OPPOSITE_FROM_ENTRY_STRONG_WIN"
    if paths["flip_1m"].get("strong_win_0p5"):
        return "FLIP_1M_STRONG_WIN"
    if paths["flip_3m"].get("strong_win_0p5"):
        return "FLIP_3M_STRONG_WIN"
    if any(
        path.get("positive_win")
        for path in (
            paths["opposite_entry"],
            paths["flip_1m"],
            paths["flip_3m"],
        )
    ):
        return "WEAK_NET_WIN_ONLY"
    return "NO_TRADE_REQUIRED"


def resolution_for_metric(
    paths: dict[str, dict[str, Any]],
    metric: str,
) -> str:
    if paths["opposite_entry"].get(metric):
        return "OPPOSITE_FROM_ENTRY_WIN"
    if paths["flip_1m"].get(metric):
        return "FLIP_1M_WIN"
    if paths["flip_3m"].get(metric):
        return "FLIP_3M_WIN"
    return "NO_TRADE_TARGET"


def _mapping_for_horizon(
    positions: list[dict[str, Any]],
    cache: dict[str, list[list[Any]]],
    horizon_min: int,
) -> list[dict[str, Any]]:
    out = []
    for position in positions:
        pid = str(position["position_id"])
        rows = cache.get(pid) or []
        paths = {
            "opposite_entry": opposite_from_entry(position, rows, horizon_min),
            "flip_1m": flip_after_minutes(position, rows, 1, horizon_min),
            "flip_3m": flip_after_minutes(position, rows, 3, horizon_min),
        }
        resolution = (
            classify_resolution(paths)
            if horizon_min == PRIMARY_HORIZON_MIN
            else None
        )
        strict_target = (
            resolution_for_metric(paths, "tp0p5_before_sl0p5")
            if horizon_min == PRIMARY_HORIZON_MIN
            else None
        )
        extended_target = (
            resolution_for_metric(paths, "tp0p5_before_sl1p0")
            if horizon_min == PRIMARY_HORIZON_MIN
            else None
        )
        robust_target = (
            resolution_for_metric(paths, "tp1p0_before_sl1p0")
            if horizon_min == PRIMARY_HORIZON_MIN
            else None
        )
        out.append({
            "position_id": pid,
            "signal_id": position.get("signal_id"),
            "symbol": position["symbol"],
            "original_side": position["side"],
            "opened_at_ms": int(position["opened_at_ms"]),
            "actual_realized_pnl": float(position.get("realized_pnl") or 0.0),
            "horizon_min": horizon_min,
            "resolution": resolution,
            "strict_1_to_1_target": strict_target,
            "extended_stop_target": extended_target,
            "robust_1_to_1_target": robust_target,
            "paths": paths,
        })
    return out


def _count_path(rows: list[dict[str, Any]], path_name: str, field: str) -> int:
    return sum(
        bool(row["paths"][path_name].get(field))
        for row in rows
    )


def summarize(rows: list[dict[str, Any]], horizon_min: int) -> dict[str, Any]:
    n = len(rows)
    path_summary = {}
    for name in ("opposite_entry", "flip_1m", "flip_3m"):
        path_summary[name] = {
            "positive_win_n": _count_path(rows, name, "positive_win"),
            "strong_win_0p5_n": _count_path(rows, name, "strong_win_0p5"),
            "robust_win_1p0_n": _count_path(rows, name, "robust_win_1p0"),
            "tp0p5_before_sl0p5_n": _count_path(rows, name, "tp0p5_before_sl0p5"),
            "tp0p5_before_sl1p0_n": _count_path(rows, name, "tp0p5_before_sl1p0"),
            "tp1p0_before_sl1p0_n": _count_path(rows, name, "tp1p0_before_sl1p0"),
        }
        for key in (
            "positive_win_n",
            "strong_win_0p5_n",
            "robust_win_1p0_n",
            "tp0p5_before_sl0p5_n",
            "tp0p5_before_sl1p0_n",
            "tp1p0_before_sl1p0_n",
        ):
            path_summary[name][key.replace("_n", "_pct")] = (
                100.0 * path_summary[name][key] / n if n else None
            )

    union_positive = sum(
        any(
            row["paths"][name].get("positive_win")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )
    union_strong = sum(
        any(
            row["paths"][name].get("strong_win_0p5")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )
    union_robust = sum(
        any(
            row["paths"][name].get("robust_win_1p0")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )
    union_tp05_sl05 = sum(
        any(
            row["paths"][name].get("tp0p5_before_sl0p5")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )
    union_tp05_sl10 = sum(
        any(
            row["paths"][name].get("tp0p5_before_sl1p0")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )
    union_tp10_sl10 = sum(
        any(
            row["paths"][name].get("tp1p0_before_sl1p0")
            for name in ("opposite_entry", "flip_1m", "flip_3m")
        )
        for row in rows
    )

    resolution_counts: dict[str, int] = {}
    if horizon_min == PRIMARY_HORIZON_MIN:
        for row in rows:
            label = str(row["resolution"])
            resolution_counts[label] = resolution_counts.get(label, 0) + 1

    return {
        "horizon_min": horizon_min,
        "n": n,
        "path_summary": path_summary,
        "union": {
            "positive_win_n": union_positive,
            "positive_win_pct": 100.0 * union_positive / n if n else None,
            "strong_win_0p5_n": union_strong,
            "strong_win_0p5_pct": 100.0 * union_strong / n if n else None,
            "robust_win_1p0_n": union_robust,
            "robust_win_1p0_pct": 100.0 * union_robust / n if n else None,
            "tp0p5_before_sl0p5_n": union_tp05_sl05,
            "tp0p5_before_sl0p5_pct": 100.0 * union_tp05_sl05 / n if n else None,
            "tp0p5_before_sl1p0_n": union_tp05_sl10,
            "tp0p5_before_sl1p0_pct": 100.0 * union_tp05_sl10 / n if n else None,
            "tp1p0_before_sl1p0_n": union_tp10_sl10,
            "tp1p0_before_sl1p0_pct": 100.0 * union_tp10_sl10 / n if n else None,
            "no_positive_resolution_n": n - union_positive,
            "no_positive_resolution_pct": (
                100.0 * (n - union_positive) / n if n else None
            ),
        },
        "exclusive_resolution_counts": resolution_counts,
        "exclusive_resolution_pct": {
            k: 100.0 * v / n for k, v in resolution_counts.items()
        } if n else {},
    }


def exclusive_metric_mapping(
    rows: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    counts = {
        "OPPOSITE_FROM_ENTRY_WIN": 0,
        "FLIP_1M_WIN": 0,
        "FLIP_3M_WIN": 0,
        "NO_TRADE_TARGET": 0,
    }
    for row in rows:
        paths = row["paths"]
        if paths["opposite_entry"].get(metric):
            counts["OPPOSITE_FROM_ENTRY_WIN"] += 1
        elif paths["flip_1m"].get(metric):
            counts["FLIP_1M_WIN"] += 1
        elif paths["flip_3m"].get(metric):
            counts["FLIP_3M_WIN"] += 1
        else:
            counts["NO_TRADE_TARGET"] += 1
    n = len(rows)
    return {
        "metric": metric,
        "n": n,
        "counts": counts,
        "pct": {
            key: 100.0 * value / n if n else None
            for key, value in counts.items()
        },
        "win_capable_n": n - counts["NO_TRADE_TARGET"],
        "win_capable_pct": (
            100.0 * (n - counts["NO_TRADE_TARGET"]) / n if n else None
        ),
    }


def run_wd4() -> dict[str, Any]:
    positions = _load_wrong_positions()
    if len(positions) != 849:
        raise RuntimeError(
            f"WD4 frozen TRUE_WRONG_DIRECTION cohort expected 849, got {len(positions)}"
        )
    cache = ensure_kline_cache(positions)
    if len(cache) < len(positions):
        raise RuntimeError(
            f"WD4 cache incomplete: {len(cache)}/{len(positions)}"
        )

    mappings = {
        str(h): _mapping_for_horizon(positions, cache, h)
        for h in SENSITIVITY_HORIZONS_MIN
    }
    summaries = {
        str(h): summarize(mappings[str(h)], h)
        for h in SENSITIVITY_HORIZONS_MIN
    }
    primary_rows = mappings[str(PRIMARY_HORIZON_MIN)]

    by_side: dict[str, dict[str, int]] = {}
    for side in ("LONG", "SHORT"):
        subset = [r for r in primary_rows if r["original_side"] == side]
        counts: dict[str, int] = {}
        for row in subset:
            counts[str(row["resolution"])] = counts.get(str(row["resolution"]), 0) + 1
        by_side[side] = {
            "n": len(subset),
            **counts,
        }

    return {
        "version": WD4_VERSION,
        "authority": "RESEARCH_ONLY",
        "discovery_cutoff_ms": WD2_CUTOFF_MS,
        "wrong_direction_n": len(positions),
        "primary_horizon_min": PRIMARY_HORIZON_MIN,
        "strong_win_threshold_pct_notional": STRONG_WIN_PCT,
        "robust_win_threshold_pct_notional": ROBUST_WIN_PCT,
        "definition": {
            "primary_success": (
                "Counterfactual sequence reaches cumulative net +0.5% of "
                "$500 notional after fee/slippage within 30 minutes."
            ),
            "weak_success": "Cumulative net becomes > $0 at a closed 1m candle.",
            "robust_success": (
                "Counterfactual sequence reaches cumulative net +1.0% of "
                "$500 notional after fee/slippage."
            ),
            "no_trade_required": (
                "None of opposite-from-entry, flip+1m, or flip+3m becomes "
                "net positive within the primary horizon."
            ),
        },
        "summaries": summaries,
        "primary_resolution_targets": {
            "strict_1_to_1": exclusive_metric_mapping(
                primary_rows,
                "tp0p5_before_sl0p5",
            ),
            "extended_stop": exclusive_metric_mapping(
                primary_rows,
                "tp0p5_before_sl1p0",
            ),
            "robust_1_to_1": exclusive_metric_mapping(
                primary_rows,
                "tp1p0_before_sl1p0",
            ),
        },
        "by_original_side_primary": by_side,
        "primary_mapping": primary_rows,
    }
