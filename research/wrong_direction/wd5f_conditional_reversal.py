from __future__ import annotations

import bisect
import csv
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from market_radar.binance import BinancePublicClient
from .wd5b_discovery import (
    Encoder,
    LogisticModel,
    RandomForestModel,
    auc_score,
    binary_metrics,
    choose_triage_thresholds,
    triage_metrics,
)
from .wd5e_multihead import (
    MICRO_FEATURES,
    NO_TRADE,
    REVERSE,
    derive_micro_features,
    ensure_micro_cache,
    load_base_rows,
    load_gate_times,
    load_wd4_targets,
)


WD5F_VERSION = "wd5f-conditional-reversal-confirmation-v1"
OVERHEAT_THRESHOLD = 5.481925222153388
BENCHMARKS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")

BENCHMARK_CACHE = Path("/app/data/wd5f_benchmark_1m_cache.json")
OI_CACHE = Path("/app/data/wd5f_oi_5m_cache.jsonl")
OUTPUT_DATASET = Path("/app/data/wd5f_conditional_reversal_features.csv")
OUTPUT_JSON = Path("/app/data/wd5f_conditional_reversal_results.json")

TIME_FEATURES = {
    "f_decision_hour_utc",
    "f_decision_hour_sin",
    "f_decision_hour_cos",
    "f_decision_weekday_utc",
}
SCALE_PROXY_FEATURES = {
    "f_context_quote_volume_5m",
    "f_context_quote_volume_24h",
    "f_context_regime_ema7",
    "f_context_regime_ema20",
}

MARKET_FEATURES = (
    "f_f_market_selected_ret_1m",
    "f_f_market_selected_ret_3m",
    "f_f_market_selected_ret_5m",
    "f_f_market_selected_ret_15m",
    "f_f_market_selected_ret_30m",
    "f_f_market_aligned_fraction_1m",
    "f_f_market_aligned_fraction_5m",
    "f_f_market_aligned_fraction_15m",
    "f_f_market_opposite_fraction_5m",
    "f_f_market_dispersion_5m",
    "f_f_market_dispersion_15m",
    "f_f_btc_selected_ret_5m",
    "f_f_eth_selected_ret_5m",
    "f_f_coin_minus_market_5m",
    "f_f_coin_minus_market_15m",
    "f_f_coin_minus_market_30m",
    "f_f_coin_beta20_btc",
    "f_f_coin_residual_5m_vs_btc",
    "f_f_coin_residual_15m_vs_btc",
    "f_f_relative_overextension_15m",
    "f_f_relative_overextension_30m",
)

FLOW_STRUCTURE_FEATURES = (
    "f_f_taker_selected_share_1m",
    "f_f_taker_selected_share_3m",
    "f_f_taker_selected_share_5m",
    "f_f_taker_selected_share_prev1m",
    "f_f_taker_selected_share_prev3m",
    "f_f_taker_selected_share_prev5m",
    "f_f_taker_accel_1m",
    "f_f_taker_accel_3m",
    "f_f_taker_accel_5m",
    "f_f_taker_delta_selected_5m",
    "f_f_taker_delta_selected_prev5m",
    "f_f_taker_delta_decay_5m",
    "f_f_opposite_break_prior3",
    "f_f_opposite_break_prior5",
    "f_f_two_bar_opposite_body",
    "f_f_last_body_opposite",
    "f_f_failed_selected_extreme",
    "f_f_selected_slope5_norm",
    "f_f_structure_reversal_score",
    "f_f_volume_climax_fade_10m",
    "f_f_range_climax_fade_10m",
)

OI_FEATURES = (
    "f_f_oi_change_5m_pct",
    "f_f_oi_prev_change_5m_pct",
    "f_f_oi_accel_5m_pct",
    "f_f_oi_change_15m_pct",
    "f_f_oi_change_30m_pct",
    "f_f_oi_unwind_with_selected_price",
    "f_f_oi_crowding_with_selected_price",
    "f_f_oi_accel_x_overheat",
    "f_f_oi_crowding_x_overheat",
)

ALL_NEW_FEATURES = MARKET_FEATURES + FLOW_STRUCTURE_FEATURES + OI_FEATURES


def _safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return a / (abs(b) + eps)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def _stdev(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = _mean(xs)
    return math.sqrt(_mean([(x - m) ** 2 for x in xs]))


def _bar(row: list[Any]) -> dict[str, float]:
    return {
        "open_time": float(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
        "close_time": float(row[6]),
        "quote": float(row[7]),
        "trades": float(row[8]),
        "taker_buy_quote": float(row[10]),
    }


def _fetch_klines_range(
    client: BinancePublicClient,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> list[list[Any]]:
    out: list[list[Any]] = []
    cursor = start_ms
    while cursor <= end_ms:
        rows = client.get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": "1m",
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1000,
            },
        )
        if not rows:
            break
        out.extend(rows)
        next_cursor = int(rows[-1][6]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(rows) < 1000:
            break
        time.sleep(0.05)
    seen = {}
    for row in out:
        seen[int(row[0])] = row
    return [seen[k] for k in sorted(seen)]


def ensure_benchmark_cache(
    min_gate_ms: int,
    max_gate_ms: int,
) -> dict[str, list[list[Any]]]:
    if BENCHMARK_CACHE.exists():
        payload = json.loads(BENCHMARK_CACHE.read_text())
        if (
            int(payload.get("start_ms", 0)) <= min_gate_ms - 45 * 60_000
            and int(payload.get("end_ms", 0)) >= max_gate_ms
            and all(s in payload.get("symbols", {}) for s in BENCHMARKS)
        ):
            return payload["symbols"]

    client = BinancePublicClient(timeout=10.0, retries=3)
    start_ms = min_gate_ms - 45 * 60_000
    end_ms = max_gate_ms
    symbols = {}
    for symbol in BENCHMARKS:
        symbols[symbol] = _fetch_klines_range(
            client, symbol, start_ms, end_ms
        )
    BENCHMARK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_CACHE.write_text(json.dumps({
        "start_ms": start_ms,
        "end_ms": end_ms,
        "symbols": symbols,
    }, separators=(",", ":")))
    return symbols


def _oi_cache_load() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not OI_CACHE.exists():
        return out
    for line in OI_CACHE.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def _fetch_oi_one(meta: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    end_ms = int(meta["gate_checked_at_ms"])
    start_ms = end_ms - 45 * 60_000
    rows = client.get(
        "/futures/data/openInterestHist",
        {
            "symbol": str(meta["symbol"]),
            "period": "5m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 20,
        },
    )
    rows = [
        row for row in rows
        if int(row.get("timestamp", 0)) <= end_ms
    ]
    return str(meta["position_id"]), rows


def ensure_oi_cache(
    gate_meta: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    cache = _oi_cache_load()
    missing = [
        meta for pid, meta in gate_meta.items()
        if pid not in cache
    ]
    fetched = []
    errors = []
    if missing:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(_fetch_oi_one, meta): meta
                for meta in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                meta = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                    fetched.append((pid, rows))
                except Exception as exc:
                    errors.append(f"{meta['position_id']}: {exc}")
                if i % 50 == 0:
                    time.sleep(0.2)
        if fetched:
            OI_CACHE.parent.mkdir(parents=True, exist_ok=True)
            with OI_CACHE.open("a") as fh:
                for pid, rows in fetched:
                    fh.write(json.dumps(
                        {"position_id": pid, "rows": rows},
                        separators=(",", ":"),
                    ) + "\n")
        if errors:
            raise RuntimeError(
                f"OI fetch failed for {len(errors)} rows; sample={errors[:5]}"
            )
    return cache


def _closed_bars_before(
    rows: list[list[Any]],
    gate_ms: int,
    count: int = 30,
) -> list[dict[str, float]]:
    close_times = [int(row[6]) for row in rows]
    idx = bisect.bisect_right(close_times, gate_ms)
    selected = rows[max(0, idx - count):idx]
    return [_bar(row) for row in selected]


def _ret(bars: list[dict[str, float]], minutes: int) -> float:
    if len(bars) < 2:
        return 0.0
    end = len(bars) - 1
    start = max(0, end - minutes)
    if start == end:
        return 0.0
    return 100.0 * (
        bars[end]["close"] / bars[start]["close"] - 1.0
    )


def _selected_taker_share(
    bars: list[dict[str, float]],
    side: str,
) -> float:
    quote = sum(x["quote"] for x in bars)
    buy = sum(x["taker_buy_quote"] for x in bars)
    share = buy / quote if quote > 0 else 0.5
    return share if side == "LONG" else 1.0 - share


def derive_market_features(
    coin_raw: list[list[Any]],
    benchmark_rows: dict[str, list[list[Any]]],
    gate_ms: int,
    side: str,
) -> dict[str, float]:
    sign = 1.0 if side == "LONG" else -1.0
    coin = [_bar(row) for row in coin_raw[-30:]]
    benches = {
        symbol: _closed_bars_before(rows, gate_ms, 30)
        for symbol, rows in benchmark_rows.items()
    }
    if min(len(x) for x in benches.values()) < 20:
        raise RuntimeError("insufficient benchmark coverage")

    horizons = (1, 3, 5, 15, 30)
    selected_returns: dict[int, list[float]] = {}
    raw_returns: dict[int, list[float]] = {}
    for h in horizons:
        raws = [_ret(benches[s], h) for s in BENCHMARKS]
        raw_returns[h] = raws
        selected_returns[h] = [sign * x for x in raws]

    market = {
        h: _median(selected_returns[h])
        for h in horizons
    }
    coin_sel = {h: sign * _ret(coin, h) for h in horizons}

    # 20-bar beta to BTC using raw 1m returns.
    coin_close = [x["close"] for x in coin[-21:]]
    btc_close = [x["close"] for x in benches["BTCUSDT"][-21:]]
    n = min(len(coin_close), len(btc_close))
    coin_close = coin_close[-n:]
    btc_close = btc_close[-n:]
    coin_r = [
        coin_close[i] / coin_close[i - 1] - 1.0
        for i in range(1, n)
    ]
    btc_r = [
        btc_close[i] / btc_close[i - 1] - 1.0
        for i in range(1, n)
    ]
    mb = _mean(btc_r)
    mc = _mean(coin_r)
    cov = _mean([
        (a - mc) * (b - mb)
        for a, b in zip(coin_r, btc_r)
    ])
    varb = _mean([(b - mb) ** 2 for b in btc_r])
    beta = cov / (varb + 1e-12)

    btc5_raw = _ret(benches["BTCUSDT"], 5)
    btc15_raw = _ret(benches["BTCUSDT"], 15)
    coin5_raw = _ret(coin, 5)
    coin15_raw = _ret(coin, 15)

    return {
        "f_f_market_selected_ret_1m": market[1],
        "f_f_market_selected_ret_3m": market[3],
        "f_f_market_selected_ret_5m": market[5],
        "f_f_market_selected_ret_15m": market[15],
        "f_f_market_selected_ret_30m": market[30],
        "f_f_market_aligned_fraction_1m": (
            sum(x > 0 for x in selected_returns[1]) / len(BENCHMARKS)
        ),
        "f_f_market_aligned_fraction_5m": (
            sum(x > 0 for x in selected_returns[5]) / len(BENCHMARKS)
        ),
        "f_f_market_aligned_fraction_15m": (
            sum(x > 0 for x in selected_returns[15]) / len(BENCHMARKS)
        ),
        "f_f_market_opposite_fraction_5m": (
            sum(x < 0 for x in selected_returns[5]) / len(BENCHMARKS)
        ),
        "f_f_market_dispersion_5m": _stdev(raw_returns[5]),
        "f_f_market_dispersion_15m": _stdev(raw_returns[15]),
        "f_f_btc_selected_ret_5m": sign * btc5_raw,
        "f_f_eth_selected_ret_5m": sign * _ret(
            benches["ETHUSDT"], 5
        ),
        "f_f_coin_minus_market_5m": coin_sel[5] - market[5],
        "f_f_coin_minus_market_15m": coin_sel[15] - market[15],
        "f_f_coin_minus_market_30m": coin_sel[30] - market[30],
        "f_f_coin_beta20_btc": beta,
        "f_f_coin_residual_5m_vs_btc": sign * (
            coin5_raw - beta * btc5_raw
        ),
        "f_f_coin_residual_15m_vs_btc": sign * (
            coin15_raw - beta * btc15_raw
        ),
        "f_f_relative_overextension_15m": max(
            0.0, coin_sel[15] - market[15]
        ),
        "f_f_relative_overextension_30m": max(
            0.0, coin_sel[30] - market[30]
        ),
    }


def derive_flow_structure_features(
    coin_raw: list[list[Any]],
    side: str,
) -> dict[str, float]:
    bars = [_bar(row) for row in coin_raw[-30:]]
    sign = 1.0 if side == "LONG" else -1.0

    last1 = bars[-1:]
    last3 = bars[-3:]
    last5 = bars[-5:]
    prev1 = bars[-2:-1]
    prev3 = bars[-6:-3]
    prev5 = bars[-10:-5]

    t1 = _selected_taker_share(last1, side)
    t3 = _selected_taker_share(last3, side)
    t5 = _selected_taker_share(last5, side)
    p1 = _selected_taker_share(prev1, side)
    p3 = _selected_taker_share(prev3, side)
    p5 = _selected_taker_share(prev5, side)

    def selected_delta(sub: list[dict[str, float]]) -> float:
        q = sum(x["quote"] for x in sub)
        if q <= 0:
            return 0.0
        buy = sum(x["taker_buy_quote"] for x in sub)
        raw = 2.0 * buy / q - 1.0
        return raw if side == "LONG" else -raw

    delta5 = selected_delta(last5)
    delta_prev5 = selected_delta(prev5)

    last = bars[-1]
    prior3 = bars[-4:-1]
    prior5 = bars[-6:-1]
    if side == "LONG":
        break3 = last["close"] < min(x["low"] for x in prior3)
        break5 = last["close"] < min(x["low"] for x in prior5)
        prior_selected_extreme = max(x["high"] for x in prior5)
        current_selected_extreme = max(x["high"] for x in last3)
        failed_extreme = current_selected_extreme <= prior_selected_extreme
    else:
        break3 = last["close"] > max(x["high"] for x in prior3)
        break5 = last["close"] > max(x["high"] for x in prior5)
        prior_selected_extreme = min(x["low"] for x in prior5)
        current_selected_extreme = min(x["low"] for x in last3)
        failed_extreme = current_selected_extreme >= prior_selected_extreme

    bodies = [
        sign * (x["close"] - x["open"])
        / max(1e-12, x["high"] - x["low"])
        for x in bars
    ]
    two_bar_opp = max(0.0, -_mean(bodies[-2:]))
    last_body_opp = max(0.0, -bodies[-1])

    closes = [x["close"] for x in bars[-5:]]
    xs = list(range(len(closes)))
    mx = _mean(xs)
    my = _mean(closes)
    slope = _safe_div(
        sum((x - mx) * (y - my) for x, y in zip(xs, closes)),
        sum((x - mx) ** 2 for x in xs),
    )
    slope_norm = sign * 100.0 * slope / closes[-1]

    vols = [x["volume"] for x in bars]
    ranges = [
        max(1e-12, x["high"] - x["low"])
        for x in bars
    ]
    climax_vol = max(vols[-10:-1])
    climax_range = max(ranges[-10:-1])
    vol_fade = max(
        0.0, 1.0 - _safe_div(vols[-1], climax_vol)
    )
    range_fade = max(
        0.0, 1.0 - _safe_div(ranges[-1], climax_range)
    )

    structure_score = (
        float(break3)
        + float(break5)
        + float(failed_extreme)
        + two_bar_opp
        + last_body_opp
        + max(0.0, p3 - t3)
    )

    return {
        "f_f_taker_selected_share_1m": t1,
        "f_f_taker_selected_share_3m": t3,
        "f_f_taker_selected_share_5m": t5,
        "f_f_taker_selected_share_prev1m": p1,
        "f_f_taker_selected_share_prev3m": p3,
        "f_f_taker_selected_share_prev5m": p5,
        "f_f_taker_accel_1m": t1 - p1,
        "f_f_taker_accel_3m": t3 - p3,
        "f_f_taker_accel_5m": t5 - p5,
        "f_f_taker_delta_selected_5m": delta5,
        "f_f_taker_delta_selected_prev5m": delta_prev5,
        "f_f_taker_delta_decay_5m": delta5 - delta_prev5,
        "f_f_opposite_break_prior3": float(break3),
        "f_f_opposite_break_prior5": float(break5),
        "f_f_two_bar_opposite_body": two_bar_opp,
        "f_f_last_body_opposite": last_body_opp,
        "f_f_failed_selected_extreme": float(failed_extreme),
        "f_f_selected_slope5_norm": slope_norm,
        "f_f_structure_reversal_score": structure_score,
        "f_f_volume_climax_fade_10m": vol_fade,
        "f_f_range_climax_fade_10m": range_fade,
    }


def derive_oi_features(
    oi_rows: list[dict[str, Any]],
    side_ret5: float,
    overheat: float,
) -> dict[str, float]:
    values = [
        float(row["sumOpenInterest"])
        for row in sorted(
            oi_rows,
            key=lambda x: int(x.get("timestamp", 0)),
        )
        if float(row.get("sumOpenInterest", 0)) > 0
    ]

    def pct(a: float, b: float) -> float:
        return 100.0 * (a / b - 1.0) if b else 0.0

    if len(values) < 3:
        changes = {
            "c5": 0.0,
            "p5": 0.0,
            "c15": 0.0,
            "c30": 0.0,
        }
    else:
        c5 = pct(values[-1], values[-2])
        p5 = pct(values[-2], values[-3])
        c15 = pct(values[-1], values[max(0, len(values)-4)])
        c30 = pct(values[-1], values[max(0, len(values)-7)])
        changes = {"c5": c5, "p5": p5, "c15": c15, "c30": c30}

    accel = changes["c5"] - changes["p5"]
    selected_move = max(0.0, side_ret5)
    unwind = selected_move * max(0.0, -changes["c5"])
    crowding = selected_move * max(0.0, changes["c15"])

    return {
        "f_f_oi_change_5m_pct": changes["c5"],
        "f_f_oi_prev_change_5m_pct": changes["p5"],
        "f_f_oi_accel_5m_pct": accel,
        "f_f_oi_change_15m_pct": changes["c15"],
        "f_f_oi_change_30m_pct": changes["c30"],
        "f_f_oi_unwind_with_selected_price": unwind,
        "f_f_oi_crowding_with_selected_price": crowding,
        "f_f_oi_accel_x_overheat": accel * overheat,
        "f_f_oi_crowding_x_overheat": crowding * overheat,
    }


def build_conditional_dataset() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = load_base_rows()
    byid = {str(r["meta_position_id"]): r for r in base}
    targets = load_wd4_targets()
    conditional_ids = {
        pid for pid in targets
        if float(byid[pid]["f_new_overheat_pressure"]) >= OVERHEAT_THRESHOLD
    }

    gate_meta = load_gate_times(conditional_ids)
    micro_cache = ensure_micro_cache(gate_meta)
    oi_cache = ensure_oi_cache(gate_meta)

    min_gate = min(int(x["gate_checked_at_ms"]) for x in gate_meta.values())
    max_gate = max(int(x["gate_checked_at_ms"]) for x in gate_meta.values())
    benchmarks = ensure_benchmark_cache(min_gate, max_gate)

    rows = []
    oi_missing = 0
    for pid in sorted(
        conditional_ids,
        key=lambda x: int(byid[x]["meta_opened_at_ms"]),
    ):
        row = dict(byid[pid])
        meta = gate_meta[pid]
        side = str(row["meta_original_side"])
        coin_raw = micro_cache[pid]
        micro = derive_micro_features(
            coin_raw,
            side,
            float(row["f_new_overheat_pressure"]),
        )
        market = derive_market_features(
            coin_raw,
            benchmarks,
            int(meta["gate_checked_at_ms"]),
            side,
        )
        flow = derive_flow_structure_features(coin_raw, side)
        oi_rows = oi_cache.get(pid) or []
        if len(oi_rows) < 3:
            oi_missing += 1
        oi = derive_oi_features(
            oi_rows,
            float(micro["f_micro_side_ret_5m"]),
            float(row["f_new_overheat_pressure"]),
        )

        row.update({k: str(v) for k, v in micro.items()})
        row.update({k: str(v) for k, v in market.items()})
        row.update({k: str(v) for k, v in flow.items()})
        row.update({k: str(v) for k, v in oi.items()})
        row["target_wd5f_reverse"] = (
            1 if targets[pid] == REVERSE else 0
        )
        row["target_wd5f_name"] = (
            "REVERSE" if targets[pid] == REVERSE else "NO_TRADE"
        )
        row["meta_gate_checked_at_ms"] = int(meta["gate_checked_at_ms"])
        rows.append(row)

    counts = Counter(r["target_wd5f_name"] for r in rows)
    return rows, {
        "overheat_threshold": OVERHEAT_THRESHOLD,
        "eligible_wd4_primary_n": len(targets),
        "conditional_n": len(rows),
        "conditional_share_pct": 100.0 * len(rows) / len(targets),
        "class_counts": dict(counts),
        "reverse_rate_pct": 100.0 * counts["REVERSE"] / len(rows),
        "oi_rows_lt3": oi_missing,
        "benchmark_symbols": list(BENCHMARKS),
        "gate_min_ms": min_gate,
        "gate_max_ms": max_gate,
    }


def _is_numeric(rows: list[dict[str, Any]], feature: str) -> bool:
    for row in rows[:100]:
        try:
            float(row[feature])
        except (TypeError, ValueError):
            return False
    return True


def _types(rows: list[dict[str, Any]], features: list[str]) -> dict[str, str]:
    return {
        f: "numeric" if _is_numeric(rows, f) else "categorical"
        for f in features
    }


def _numeric_sep(
    rows: list[dict[str, Any]],
    feature: str,
) -> float:
    y = [int(r["target_wd5f_reverse"]) for r in rows]
    p = [float(r[feature]) for r in rows]
    auc = auc_score(y, p)
    return 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0


def _categorical_sep(
    rows: list[dict[str, Any]],
    feature: str,
) -> float:
    base = sum(int(r["target_wd5f_reverse"]) for r in rows) / len(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[str(row[feature])].append(
            int(row["target_wd5f_reverse"])
        )
    weighted = 0.0
    for ys in groups.values():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
    return min(1.0, 2.0 * weighted)


def rank_features(
    train: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
) -> list[str]:
    ranked = []
    for feature in features:
        score = (
            _numeric_sep(train, feature)
            if types[feature] == "numeric"
            else _categorical_sep(train, feature)
        )
        ranked.append((score, feature))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [f for _, f in ranked]


def _split(rows: list[dict[str, Any]]) -> tuple[list, list, list]:
    rr = sorted(rows, key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(rr)
    return rr[:3*n//5], rr[3*n//5:4*n//5], rr[4*n//5:]


def _portable_existing(rows: list[dict[str, Any]]) -> list[str]:
    return [
        key for key in rows[0]
        if key.startswith("f_")
        and not key.startswith("f_f_")
        and key not in TIME_FEATURES
        and key not in SCALE_PROXY_FEATURES
        and not key.startswith("f_latency_")
        and len({str(r[key]) for r in rows}) > 1
    ]


def _evaluate_logistic_variant(
    train: list[dict[str, Any]],
    val: list[dict[str, Any]],
    test: list[dict[str, Any]],
    candidates: list[str],
) -> dict[str, Any]:
    types = _types(train + val + test, candidates)
    ordered = rank_features(train, candidates, types)
    grid = []
    for k in (5, 10, 20, 30, 40, 60):
        if k > len(ordered):
            continue
        chosen = ordered[:k]
        for l2 in (0.1, 1.0, 4.0):
            encoder = Encoder(chosen, types).fit(train)
            model = LogisticModel(
                l2=l2, epochs=700, lr=0.12
            ).fit(
                encoder.transform(train),
                [int(r["target_wd5f_reverse"]) for r in train],
            )
            pv = model.predict_proba(encoder.transform(val))
            yv = [int(r["target_wd5f_reverse"]) for r in val]
            vm = binary_metrics(yv, pv)
            grid.append({
                "k": len(chosen),
                "l2": l2,
                "features": chosen,
                "validation": vm,
                "_encoder": encoder,
                "_model": model,
            })
    grid.sort(
        key=lambda x: (
            x["validation"]["auc"]
            if x["validation"]["auc"] is not None else -1.0,
            x["validation"]["balanced_accuracy"]
            if x["validation"]["balanced_accuracy"] is not None else -1.0,
            -x["k"],
        ),
        reverse=True,
    )
    selected = grid[0]
    encoder = selected["_encoder"]
    model = selected["_model"]

    pv = model.predict_proba(encoder.transform(val))
    yv = [int(r["target_wd5f_reverse"]) for r in val]
    triage = choose_triage_thresholds(yv, pv)

    pt = model.predict_proba(encoder.transform(test))
    yt = [int(r["target_wd5f_reverse"]) for r in test]
    test_metrics = binary_metrics(yt, pt)

    one_sided = choose_one_sided_reverse_threshold(
        yv, pv, precision_floor=0.80, min_flags=5
    )
    one_sided_test = None
    if one_sided["selected"] is not None:
        one_sided_test = one_sided_reverse_metrics(
            yt,
            pt,
            float(one_sided["selected"]["threshold"]),
        )

    test_triage = None
    if triage["selected"] is not None:
        t = triage["selected"]
        test_triage = triage_metrics(
            yt, pt, float(t["lower"]), float(t["upper"])
        )

    seen = {str(r["meta_symbol"]) for r in train + val}
    novel = [
        r for r in test
        if str(r["meta_symbol"]) not in seen
    ]
    novel_metrics = None
    novel_triage = None
    novel_one_sided = None
    if novel:
        yn = [int(r["target_wd5f_reverse"]) for r in novel]
        pn = model.predict_proba(encoder.transform(novel))
        novel_metrics = binary_metrics(yn, pn)
        if one_sided["selected"] is not None:
            novel_one_sided = one_sided_reverse_metrics(
                yn,
                pn,
                float(one_sided["selected"]["threshold"]),
            )
        if triage["selected"] is not None:
            t = triage["selected"]
            novel_triage = triage_metrics(
                yn, pn, float(t["lower"]), float(t["upper"])
            )

    return {
        "selected_k": selected["k"],
        "selected_l2": selected["l2"],
        "selected_features": selected["features"],
        "validation": selected["validation"],
        "validation_triage": triage,
        "one_sided_reverse_gate": one_sided,
        "test": test_metrics,
        "test_triage": test_triage,
        "test_one_sided_reverse_gate": one_sided_test,
        "novel_symbol_n": len(novel),
        "novel_symbol_unique": len({
            str(r["meta_symbol"]) for r in novel
        }),
        "novel_symbol_metrics": novel_metrics,
        "novel_symbol_triage": novel_triage,
        "novel_symbol_one_sided_reverse_gate": novel_one_sided,
    }


def _evaluate_forest(
    train: list[dict[str, Any]],
    val: list[dict[str, Any]],
    test: list[dict[str, Any]],
    candidates: list[str],
) -> dict[str, Any]:
    types = _types(train + val + test, candidates)
    ordered = rank_features(train, candidates, types)
    grid = []
    for k in (10, 20, 30, min(40, len(ordered))):
        if k <= 0 or k > len(ordered):
            continue
        chosen = ordered[:k]
        encoder = Encoder(chosen, types).fit(train)
        xtr = encoder.transform(train)
        xv = encoder.transform(val)
        xt = encoder.transform(test)
        ytr = [int(r["target_wd5f_reverse"]) for r in train]
        yv = [int(r["target_wd5f_reverse"]) for r in val]
        yt = [int(r["target_wd5f_reverse"]) for r in test]
        for depth in (2, 3, 4):
            for leaf in (10, 15, 25):
                model = RandomForestModel(
                    trees=100,
                    max_depth=depth,
                    min_leaf=leaf,
                    seed=20261001,
                ).fit(xtr, ytr)
                vm = binary_metrics(yv, model.predict_proba(xv))
                tm = binary_metrics(yt, model.predict_proba(xt))
                grid.append({
                    "k": len(chosen),
                    "depth": depth,
                    "min_leaf": leaf,
                    "features": chosen,
                    "validation": vm,
                    "test": tm,
                })
    grid.sort(
        key=lambda x: (
            x["validation"]["auc"]
            if x["validation"]["auc"] is not None else -1.0,
            x["validation"]["balanced_accuracy"]
            if x["validation"]["balanced_accuracy"] is not None else -1.0,
            -x["k"],
        ),
        reverse=True,
    )
    return {
        "selected": grid[0],
        "top_grid": grid[:10],
    }


def feature_stability(
    rows: list[dict[str, Any]],
    features: list[str],
) -> list[dict[str, Any]]:
    types = _types(rows, features)
    n = len(rows)
    fifths = [
        rows[i*n//5:(i+1)*n//5]
        for i in range(5)
    ]
    out = []
    for feature in features:
        full = (
            _numeric_sep(rows, feature)
            if types[feature] == "numeric"
            else _categorical_sep(rows, feature)
        )
        scores = []
        directions = []
        for block in fifths:
            y = [int(r["target_wd5f_reverse"]) for r in block]
            if not y or sum(y) in (0, len(y)):
                continue
            if types[feature] == "numeric":
                vals = [float(r[feature]) for r in block]
                auc = auc_score(y, vals)
                score = (
                    0.0 if auc is None
                    else abs(float(auc) - 0.5) * 2.0
                )
                pos = [
                    float(r[feature]) for r in block
                    if int(r["target_wd5f_reverse"]) == 1
                ]
                neg = [
                    float(r[feature]) for r in block
                    if int(r["target_wd5f_reverse"]) == 0
                ]
                directions.append(
                    1 if _median(pos) > _median(neg)
                    else -1 if _median(pos) < _median(neg)
                    else 0
                )
            else:
                score = _categorical_sep(block, feature)
            scores.append(score)
        nonzero = [x for x in directions if x]
        out.append({
            "feature": feature,
            "type": types[feature],
            "full_separation": full,
            "fifth_scores": scores,
            "median_fifth_separation": (
                _median(scores) if scores else None
            ),
            "min_fifth_separation": min(scores) if scores else None,
            "numeric_direction_consistent": (
                len(set(nonzero)) <= 1 if nonzero else None
            ),
        })
    out.sort(
        key=lambda x: (
            x["median_fifth_separation"]
            if x["median_fifth_separation"] is not None else -1.0,
            x["min_fifth_separation"]
            if x["min_fifth_separation"] is not None else -1.0,
            x["full_separation"],
        ),
        reverse=True,
    )
    return out


def one_sided_reverse_metrics(
    y: list[int],
    p: list[float],
    threshold: float,
) -> dict[str, Any]:
    flagged = [
        i for i, prob in enumerate(p)
        if prob >= threshold
    ]
    positives = sum(y)
    negatives = len(y) - positives
    tp = sum(y[i] == 1 for i in flagged)
    fp = len(flagged) - tp
    return {
        "n": len(y),
        "flagged_n": len(flagged),
        "flagged_pct": (
            100.0 * len(flagged) / len(y) if y else None
        ),
        "reverse_precision": (
            tp / len(flagged) if flagged else None
        ),
        "reverse_recall": (
            tp / positives if positives else None
        ),
        "false_reverse_rate_on_no_trade": (
            fp / negatives if negatives else None
        ),
        "tp_reverse": tp,
        "fp_reverse": fp,
        "default_no_trade_n": len(y) - len(flagged),
    }


def choose_one_sided_reverse_threshold(
    y: list[int],
    p: list[float],
    precision_floor: float = 0.80,
    min_flags: int = 5,
) -> dict[str, Any]:
    candidates = []
    for threshold in sorted(set(p)):
        metrics = one_sided_reverse_metrics(
            y, p, threshold
        )
        precision = metrics["reverse_precision"]
        if (
            metrics["flagged_n"] >= min_flags
            and precision is not None
            and precision >= precision_floor
        ):
            candidates.append((
                metrics["reverse_recall"],
                metrics["flagged_n"],
                precision,
                threshold,
                metrics,
            ))
    if not candidates:
        return {
            "precision_floor": precision_floor,
            "min_flags": min_flags,
            "selected": None,
        }
    candidates.sort(reverse=True)
    _, _, _, threshold, metrics = candidates[0]
    return {
        "precision_floor": precision_floor,
        "min_flags": min_flags,
        "selected": {
            "threshold": threshold,
            **metrics,
        },
    }


def promotion_assessment(
    selected: dict[str, Any],
) -> dict[str, Any]:
    val_auc = float(selected["validation"]["auc"])
    test_auc = float(selected["test"]["auc"])
    novel = selected.get("novel_symbol_metrics")
    novel_auc = (
        float(novel["auc"])
        if novel and novel.get("auc") is not None
        else None
    )

    val_gate = selected.get("one_sided_reverse_gate", {}).get(
        "selected"
    )
    test_gate = selected.get("test_one_sided_reverse_gate")
    novel_gate = selected.get(
        "novel_symbol_one_sided_reverse_gate"
    )

    requirements = {
        "validation_auc_ge_0p65": val_auc >= 0.65,
        "test_auc_ge_0p55": test_auc >= 0.55,
        "novel_symbol_auc_ge_0p55": (
            novel_auc is not None and novel_auc >= 0.55
        ),
        "validation_reverse_precision_ge_0p80": (
            val_gate is not None
            and val_gate.get("reverse_precision") is not None
            and float(val_gate["reverse_precision"]) >= 0.80
        ),
        "test_reverse_precision_ge_0p70": (
            test_gate is not None
            and test_gate.get("reverse_precision") is not None
            and float(test_gate["reverse_precision"]) >= 0.70
        ),
        "test_reverse_recall_ge_0p15": (
            test_gate is not None
            and test_gate.get("reverse_recall") is not None
            and float(test_gate["reverse_recall"]) >= 0.15
        ),
        "novel_reverse_precision_ge_0p65": (
            novel_gate is not None
            and novel_gate.get("reverse_precision") is not None
            and float(novel_gate["reverse_precision"]) >= 0.65
        ),
        "novel_flagged_n_ge_3": (
            novel_gate is not None
            and int(novel_gate.get("flagged_n", 0)) >= 3
        ),
    }
    research_candidate = all(requirements.values())

    return {
        "status": (
            "ONE_SIDED_REVERSAL_CANDIDATE_FOUND"
            if research_candidate
            else "CONDITIONAL_REVERSAL_NOT_READY"
        ),
        "decision_semantics": (
            "REVERSE only above the validation-selected high-precision "
            "threshold; otherwise default to NO TRADE."
        ),
        "requirements": requirements,
        "validation_auc": val_auc,
        "test_auc": test_auc,
        "novel_symbol_auc": novel_auc,
        "production_authority": "NONE",
        "prospective_shadow_required": True,
        "holdout_caveat": (
            "The one-sided objective was formalized after the initial "
            "symmetric WD-5F test inspection. Therefore this is a research "
            "candidate, not a pristine promotion result."
        ),
    }


def run_wd5f() -> dict[str, Any]:
    rows, cohort = build_conditional_dataset()
    train, val, test = _split(rows)

    existing = _portable_existing(rows)
    micro = [
        f for f in MICRO_FEATURES
        if f in rows[0]
    ]
    engineered = [
        f for f in existing
        if f.startswith("f_new_")
    ]

    variants = {
        "wd5e_micro": micro,
        "market_relative": list(MARKET_FEATURES),
        "flow_structure": list(FLOW_STRUCTURE_FEATURES),
        "oi_dynamics": list(OI_FEATURES),
        "new_all": list(ALL_NEW_FEATURES),
        "engineered_plus_new": engineered + list(ALL_NEW_FEATURES),
        "conditional_all": existing + list(ALL_NEW_FEATURES),
    }

    results = {
        name: _evaluate_logistic_variant(
            train, val, test, features
        )
        for name, features in variants.items()
    }
    selected_name = max(
        results,
        key=lambda n: (
            results[n]["validation"]["auc"]
            if results[n]["validation"]["auc"] is not None
            else -1.0
        ),
    )
    selected = results[selected_name]

    nonlinear = _evaluate_forest(
        train,
        val,
        test,
        list(ALL_NEW_FEATURES) + micro + engineered,
    )

    stability = feature_stability(
        rows,
        list(ALL_NEW_FEATURES),
    )

    promotion = promotion_assessment(selected)

    with OUTPUT_DATASET.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    result = {
        "version": WD5F_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "cohort": cohort,
        "split": {
            "train_n": len(train),
            "validation_n": len(val),
            "test_n": len(test),
            "train_classes": dict(Counter(
                r["target_wd5f_name"] for r in train
            )),
            "validation_classes": dict(Counter(
                r["target_wd5f_name"] for r in val
            )),
            "test_classes": dict(Counter(
                r["target_wd5f_name"] for r in test
            )),
        },
        "new_feature_count": len(ALL_NEW_FEATURES),
        "feature_groups": {
            "market_relative": list(MARKET_FEATURES),
            "flow_structure": list(FLOW_STRUCTURE_FEATURES),
            "oi_dynamics": list(OI_FEATURES),
        },
        "variants": results,
        "selected_variant": selected_name,
        "selected": selected,
        "nonlinear_sensitivity": nonlinear,
        "new_feature_stability": stability,
        "promotion_assessment": promotion,
        "outputs": {
            "dataset": str(OUTPUT_DATASET),
            "json": str(OUTPUT_JSON),
            "benchmark_cache": str(BENCHMARK_CACHE),
            "oi_cache": str(OI_CACHE),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(
        result, indent=2, allow_nan=False
    ))
    return result
