from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.binance import BinancePublicClient
from market_radar.persistence import _postgres_connect


LQ1_VERSION = "lq1-causal-structural-liquidity-v1"
EXPECTED_LONG_UNIVERSE = 1236

TF_CONFIG = {
    "5m": {"lookback_ms": 36 * 3600_000, "left": 3, "right": 2, "min_departure_atr": 0.75},
    "15m": {"lookback_ms": 72 * 3600_000, "left": 3, "right": 2, "min_departure_atr": 0.75},
    "1h": {"lookback_ms": 168 * 3600_000, "left": 3, "right": 2, "min_departure_atr": 0.75},
}


@dataclass(frozen=True)
class Bar:
    open_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_ms: int


@dataclass
class Zone:
    side: str
    timeframe: str
    base_open_ms: int
    born_ms: int
    lower: float
    upper: float
    atr_at_birth: float
    departure_atr: float
    base_volume_ratio: float
    zone_width_atr: float
    base_index: int
    born_index: int


def _f(v: Any, default: float = float("nan")) -> float:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _load_universe(data_dir: Path) -> list[dict[str, str]]:
    path = data_dir / "wd5h4a_temporal_features.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [
            r for r in csv.DictReader(fh)
            if str(r.get("side") or "").upper() == "LONG"
            and str(r.get("primary_meta_label") or "") in {"META_WIN", "META_LOSS"}
        ]
    rows.sort(key=lambda r: (int(r["opened_at_ms"]), r["position_id"]))
    if len(rows) != EXPECTED_LONG_UNIVERSE:
        raise RuntimeError(f"LQ-1 requires frozen LONG universe={EXPECTED_LONG_UNIVERSE}, got {len(rows)}")
    if len({r["position_id"] for r in rows}) != len(rows):
        raise RuntimeError("duplicate position_id in frozen LONG universe")
    return rows


def _load_positions(position_ids: list[str]) -> dict[str, dict[str, Any]]:
    q = """
        select position_id, symbol, side, opened_at_ms, entry_price
        from positions
        where position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, (position_ids,))
            rows = [dict(r) for r in cur.fetchall()]
    return {str(r["position_id"]): r for r in rows}


def _bar(raw: list[Any]) -> Bar:
    return Bar(
        open_ms=int(raw[0]),
        open=float(raw[1]),
        high=float(raw[2]),
        low=float(raw[3]),
        close=float(raw[4]),
        volume=float(raw[5]),
        close_ms=int(raw[6]),
    )


def _fetch_range(client: BinancePublicClient, symbol: str, tf: str, start_ms: int, end_ms: int) -> list[Bar]:
    out: list[Bar] = []
    cursor = int(start_ms)
    while cursor <= end_ms:
        payload = client.get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": tf,
                "startTime": cursor,
                "endTime": int(end_ms),
                "limit": 500,
            },
        )
        if not isinstance(payload, list) or not payload:
            break
        batch = [_bar(x) for x in payload]
        out.extend(batch)
        next_cursor = batch[-1].close_ms + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(batch) < 500:
            break
        time.sleep(0.02)
    dedup = {b.open_ms: b for b in out if b.close_ms <= end_ms}
    return [dedup[k] for k in sorted(dedup)]


def _load_or_fetch(
    client: BinancePublicClient,
    cache_dir: Path,
    symbol: str,
    tf: str,
    start_ms: int,
    end_ms: int,
) -> list[Bar]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol}_{tf}.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if int(payload["start_ms"]) <= start_ms and int(payload["end_ms"]) >= end_ms:
                return [Bar(**x) for x in payload["bars"]]
        except Exception:
            pass
    bars = _fetch_range(client, symbol, tf, start_ms, end_ms)
    path.write_text(
        json.dumps(
            {
                "version": LQ1_VERSION,
                "symbol": symbol,
                "timeframe": tf,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "bars": [asdict(x) for x in bars],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return bars


def _true_ranges(bars: list[Bar]) -> list[float]:
    out: list[float] = []
    for i, b in enumerate(bars):
        prev = bars[i - 1].close if i else b.open
        out.append(max(b.high - b.low, abs(b.high - prev), abs(b.low - prev)))
    return out


def _atr_at(trs: list[float], i: int, period: int = 14) -> float:
    lo = max(0, i - period + 1)
    vals = [x for x in trs[lo : i + 1] if x > 0]
    return sum(vals) / len(vals) if vals else float("nan")


def _volume_ratio(bars: list[Bar], i: int, period: int = 20) -> float:
    lo = max(0, i - period)
    hist = [b.volume for b in bars[lo:i] if b.volume > 0]
    if not hist:
        return float("nan")
    med = statistics.median(hist)
    return bars[i].volume / med if med > 0 else float("nan")


def build_zones(bars: list[Bar], timeframe: str) -> list[Zone]:
    cfg = TF_CONFIG[timeframe]
    left = int(cfg["left"])
    right = int(cfg["right"])
    dep_floor = float(cfg["min_departure_atr"])
    trs = _true_ranges(bars)
    zones: list[Zone] = []

    for i in range(max(left, 14), len(bars) - right):
        base = bars[i]
        atr = _atr_at(trs, i)
        if not math.isfinite(atr) or atr <= 0:
            continue
        left_bars = bars[i - left : i]
        right_bars = bars[i + 1 : i + right + 1]
        born_i = i + right
        body_hi = max(base.open, base.close)
        body_lo = min(base.open, base.close)
        vol_ratio = _volume_ratio(bars, i)

        is_swing_high = base.high >= max(b.high for b in left_bars) and base.high >= max(b.high for b in right_bars)
        if is_swing_high:
            lower, upper = body_hi, base.high
            departure = max(0.0, lower - min(b.low for b in right_bars))
            dep_atr = departure / atr
            if upper > lower and dep_atr >= dep_floor and right_bars[-1].close < lower:
                zones.append(
                    Zone(
                        side="SUPPLY",
                        timeframe=timeframe,
                        base_open_ms=base.open_ms,
                        born_ms=bars[born_i].close_ms,
                        lower=lower,
                        upper=upper,
                        atr_at_birth=atr,
                        departure_atr=dep_atr,
                        base_volume_ratio=vol_ratio,
                        zone_width_atr=(upper - lower) / atr,
                        base_index=i,
                        born_index=born_i,
                    )
                )

        is_swing_low = base.low <= min(b.low for b in left_bars) and base.low <= min(b.low for b in right_bars)
        if is_swing_low:
            lower, upper = base.low, body_lo
            departure = max(0.0, max(b.high for b in right_bars) - upper)
            dep_atr = departure / atr
            if upper > lower and dep_atr >= dep_floor and right_bars[-1].close > upper:
                zones.append(
                    Zone(
                        side="DEMAND",
                        timeframe=timeframe,
                        base_open_ms=base.open_ms,
                        born_ms=bars[born_i].close_ms,
                        lower=lower,
                        upper=upper,
                        atr_at_birth=atr,
                        departure_atr=dep_atr,
                        base_volume_ratio=vol_ratio,
                        zone_width_atr=(upper - lower) / atr,
                        base_index=i,
                        born_index=born_i,
                    )
                )
    return zones


def _touches(bar: Bar, z: Zone) -> bool:
    return bar.high >= z.lower and bar.low <= z.upper


def zone_state(z: Zone, bars: list[Bar], asof_ms: int) -> dict[str, Any]:
    if z.born_ms > asof_ms:
        return {"state": "UNBORN", "touch_count": 0, "broken_ms": None, "flip_ms": None}
    touch_count = 0
    in_touch = False
    broken_ms: int | None = None
    flip_ms: int | None = None

    for b in bars[z.born_index + 1 :]:
        if b.close_ms > asof_ms:
            break
        touched = _touches(b, z)
        if touched and not in_touch:
            touch_count += 1
        in_touch = touched

        if broken_ms is None:
            broken = b.close > z.upper if z.side == "SUPPLY" else b.close < z.lower
            if broken:
                broken_ms = b.close_ms
                in_touch = False
                continue
        else:
            if z.side == "SUPPLY" and b.low <= z.upper and b.close > z.upper:
                flip_ms = b.close_ms
            elif z.side == "DEMAND" and b.high >= z.lower and b.close < z.lower:
                flip_ms = b.close_ms

    if broken_ms is not None:
        state = "FLIPPED" if flip_ms is not None else "BROKEN"
    else:
        state = "TESTED" if touch_count else "FRESH"
    return {"state": state, "touch_count": touch_count, "broken_ms": broken_ms, "flip_ms": flip_ms}


def _distance_pct(price: float, z: Zone) -> float | None:
    if z.lower <= price <= z.upper:
        return 0.0
    if z.side == "SUPPLY":
        if price < z.lower:
            return (z.lower / price - 1.0) * 100.0
        return None
    if price > z.upper:
        return (1.0 - z.upper / price) * 100.0
    return None


def snapshot(
    bars_by_tf: dict[str, list[Bar]],
    zones_by_tf: dict[str, list[Zone]],
    asof_ms: int,
    price: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    combined: list[tuple[float, Zone, dict[str, Any]]] = []

    for tf in ("5m", "15m", "1h"):
        bars = bars_by_tf.get(tf, [])
        active: list[tuple[float, Zone, dict[str, Any]]] = []
        supply_count = 0
        demand_count = 0
        for z in zones_by_tf.get(tf, []):
            if z.born_ms > asof_ms:
                continue
            st = zone_state(z, bars, asof_ms)
            if st["state"] in {"BROKEN", "FLIPPED"}:
                continue
            dist = _distance_pct(price, z)
            if dist is None:
                continue
            if z.side == "SUPPLY":
                supply_count += 1
            else:
                demand_count += 1
            active.append((dist, z, st))
            combined.append((dist, z, st))

        for side in ("SUPPLY", "DEMAND"):
            candidates = [x for x in active if x[1].side == side]
            candidates.sort(key=lambda x: (x[0], -x[1].departure_atr, -x[1].born_ms))
            key = f"{tf}_{side.lower()}"
            result[f"{key}_active_count"] = supply_count if side == "SUPPLY" else demand_count
            if not candidates:
                for suffix in ("distance_pct", "lower", "upper", "departure_atr", "volume_ratio", "width_atr", "touch_count", "state", "born_ms"):
                    result[f"{key}_{suffix}"] = None
                continue
            dist, z, st = candidates[0]
            result.update(
                {
                    f"{key}_distance_pct": dist,
                    f"{key}_lower": z.lower,
                    f"{key}_upper": z.upper,
                    f"{key}_departure_atr": z.departure_atr,
                    f"{key}_volume_ratio": z.base_volume_ratio,
                    f"{key}_width_atr": z.zone_width_atr,
                    f"{key}_touch_count": st["touch_count"],
                    f"{key}_state": st["state"],
                    f"{key}_born_ms": z.born_ms,
                }
            )

    for side in ("SUPPLY", "DEMAND"):
        candidates = [x for x in combined if x[1].side == side]
        candidates.sort(key=lambda x: (x[0], {"1h": 0, "15m": 1, "5m": 2}[x[1].timeframe]))
        key = f"nearest_{side.lower()}"
        if not candidates:
            result.update({f"{key}_distance_pct": None, f"{key}_timeframe": None, f"{key}_lower": None, f"{key}_upper": None})
        else:
            dist, z, st = candidates[0]
            result.update(
                {
                    f"{key}_distance_pct": dist,
                    f"{key}_timeframe": z.timeframe,
                    f"{key}_lower": z.lower,
                    f"{key}_upper": z.upper,
                    f"{key}_departure_atr": z.departure_atr,
                    f"{key}_touch_count": st["touch_count"],
                    f"{key}_state": st["state"],
                    f"{key}_born_ms": z.born_ms,
                }
            )
    return result


def _synthetic_causality_test() -> None:
    step = 300_000
    bars: list[Bar] = []
    prices = [100, 101, 102, 104, 103, 101, 100, 99, 98, 99, 100, 101, 102, 101, 100, 99, 98, 97, 98, 99]
    for i, c in enumerate(prices):
        o = prices[i - 1] if i else c
        bars.append(Bar(i * step, o, max(o, c) + 0.6, min(o, c) - 0.6, c, 100 + i, (i + 1) * step - 1))
    # Sanity check the causal contract itself: no zone may be visible before born_ms.
    zones = build_zones(bars, "5m")
    for z in zones:
        assert z.born_ms > bars[z.base_index].close_ms
        assert zone_state(z, bars, z.born_ms - 1)["state"] == "UNBORN"
        assert zone_state(z, bars, z.born_ms)["state"] != "UNBORN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/opt/core-app/data")
    ap.add_argument("--cache-dir", default="/opt/core-app/data/lq1_klines_cache")
    ap.add_argument("--output-dir", default="research/liquidity_location/results")
    ap.add_argument("--max-trades", type=int, default=0)
    args = ap.parse_args()

    _synthetic_causality_test()
    data_dir = Path(args.data_dir)
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    universe = _load_universe(data_dir)
    if args.max_trades > 0:
        universe = universe[: args.max_trades]
    positions = _load_positions([r["position_id"] for r in universe])
    missing_positions = [r["position_id"] for r in universe if r["position_id"] not in positions]
    if missing_positions:
        raise RuntimeError(f"positions coverage {len(positions)}/{len(universe)}; sample missing={missing_positions[:5]}")

    by_symbol: dict[str, list[dict[str, str]]] = {}
    for r in universe:
        by_symbol.setdefault(r["symbol"], []).append(r)

    client = BinancePublicClient(timeout=12.0, retries=4)
    output_rows: list[dict[str, Any]] = []
    symbol_errors: dict[str, str] = {}
    zone_totals = {"5m": 0, "15m": 0, "1h": 0}

    for n, (symbol, rows) in enumerate(sorted(by_symbol.items()), 1):
        first_ms = min(int(r["opened_at_ms"]) for r in rows)
        last_ms = max(int(r["opened_at_ms"]) for r in rows)
        bars_by_tf: dict[str, list[Bar]] = {}
        zones_by_tf: dict[str, list[Zone]] = {}
        try:
            for tf, cfg in TF_CONFIG.items():
                bars = _load_or_fetch(
                    client,
                    cache_dir,
                    symbol,
                    tf,
                    first_ms - int(cfg["lookback_ms"]),
                    last_ms,
                )
                bars_by_tf[tf] = bars
                zones = build_zones(bars, tf)
                zones_by_tf[tf] = zones
                zone_totals[tf] += len(zones)
        except Exception as exc:
            symbol_errors[symbol] = str(exc)
            bars_by_tf = {}
            zones_by_tf = {}

        for r in rows:
            p = positions[r["position_id"]]
            entry_price = _f(p.get("entry_price"))
            opened_ms = int(p["opened_at_ms"])
            base = {
                "position_id": r["position_id"],
                "signal_id": r["signal_id"],
                "symbol": symbol,
                "opened_at_ms": opened_ms,
                "entry_price": entry_price,
                "primary_meta_label": r["primary_meta_label"],
            }
            if bars_by_tf and math.isfinite(entry_price) and entry_price > 0:
                base.update(snapshot(bars_by_tf, zones_by_tf, opened_ms, entry_price))
            output_rows.append(base)

        if n % 25 == 0 or n == len(by_symbol):
            print(f"symbols={n}/{len(by_symbol)} rows={len(output_rows)} errors={len(symbol_errors)}", flush=True)

    keys: list[str] = []
    seen: set[str] = set()
    for row in output_rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)

    csv_path = out_dir / "lq1_entry_zone_features.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(output_rows)

    supply_cov = sum(1 for r in output_rows if r.get("nearest_supply_distance_pct") is not None)
    demand_cov = sum(1 for r in output_rows if r.get("nearest_demand_distance_pct") is not None)
    both_cov = sum(
        1 for r in output_rows
        if r.get("nearest_supply_distance_pct") is not None and r.get("nearest_demand_distance_pct") is not None
    )
    inside_supply = sum(1 for r in output_rows if r.get("nearest_supply_distance_pct") == 0)
    inside_demand = sum(1 for r in output_rows if r.get("nearest_demand_distance_pct") == 0)

    summary = {
        "version": LQ1_VERSION,
        "contract": {
            "universe_rows": len(output_rows),
            "expected_full_universe": EXPECTED_LONG_UNIVERSE,
            "symbols": len(by_symbol),
            "timeframes": list(TF_CONFIG),
            "entry_snapshot_only": True,
            "outcome_threshold_optimization": False,
        },
        "causality": {
            "zone_birth_requires_right_bars_closed": True,
            "zone_visible_only_when_born_ms_lte_asof": True,
            "state_uses_only_bars_close_ms_lte_asof": True,
            "synthetic_causality_test": "PASS",
        },
        "coverage": {
            "position_rows": len(positions),
            "symbol_errors": len(symbol_errors),
            "nearest_supply_rows": supply_cov,
            "nearest_demand_rows": demand_cov,
            "both_sides_rows": both_cov,
            "nearest_supply_pct": round(100 * supply_cov / len(output_rows), 4) if output_rows else 0,
            "nearest_demand_pct": round(100 * demand_cov / len(output_rows), 4) if output_rows else 0,
            "both_sides_pct": round(100 * both_cov / len(output_rows), 4) if output_rows else 0,
            "inside_supply_rows": inside_supply,
            "inside_demand_rows": inside_demand,
        },
        "zone_candidates_total": zone_totals,
        "symbol_errors": symbol_errors,
        "output_csv": str(csv_path),
    }
    (out_dir / "lq1_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()