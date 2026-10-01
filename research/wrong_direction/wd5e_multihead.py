from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.binance import BinancePublicClient
from market_radar.persistence import _postgres_connect
from .wd2_anatomy import WD2_CUTOFF_MS
from .wd5b_discovery import (
    Encoder,
    LogisticModel,
    RandomForestModel,
    auc_score,
    binary_metrics,
    choose_triage_thresholds,
    triage_metrics,
)


WD5E_VERSION = "wd5e-multihead-opportunity-detector-v1"
INPUT_PATH = Path("/app/data/wd5d_opportunity_exhaustion_features.csv")
WD4_PATH = Path("/app/data/wd4_resolution_results.json")
CACHE_PATH = Path("/app/data/wd5e_preentry_1m_cache.jsonl")
OUTPUT_DATASET = Path("/app/data/wd5e_multihead_features.csv")
OUTPUT_JSON = Path("/app/data/wd5e_multihead_results.json")

REVERSE = "OPPOSITE_FROM_ENTRY_WIN"
NO_TRADE = "NO_TRADE_TARGET"

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

MICRO_FEATURES = (
    "f_micro_bar_count",
    "f_micro_side_ret_1m",
    "f_micro_side_ret_3m",
    "f_micro_side_ret_5m",
    "f_micro_side_ret_10m",
    "f_micro_side_ret_15m",
    "f_micro_side_ret_30m",
    "f_micro_prev3_side_ret",
    "f_micro_prev5_side_ret",
    "f_micro_decay_3_vs_prev3",
    "f_micro_decay_5_vs_prev5",
    "f_micro_distance_selected_extreme_15m",
    "f_micro_distance_selected_extreme_30m",
    "f_micro_selected_clv_last",
    "f_micro_rejection_wick_last",
    "f_micro_selected_body_last",
    "f_micro_consecutive_selected_bars",
    "f_micro_range_ratio_last_vs_prev10",
    "f_micro_range_ratio_3_vs_prev3",
    "f_micro_volume_ratio_last_vs_prev10",
    "f_micro_volume_ratio_3_vs_prev3",
    "f_micro_trades_ratio_last_vs_prev10",
    "f_micro_selected_taker_share_1m",
    "f_micro_selected_taker_share_3m",
    "f_micro_selected_taker_share_prev3m",
    "f_micro_taker_decay_3_vs_prev3",
    "f_micro_price_flow_divergence",
    "f_micro_volume_climax_then_fade",
    "f_micro_range_contraction_after_impulse",
    "f_micro_close_z_20",
    "f_micro_selected_vwap_extension_20",
    "f_micro_reversal_pressure",
)


def _safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return a / (abs(b) + eps)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def load_base_rows() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(INPUT_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 base rows, got {len(rows)}")
    return rows


def load_wd4_targets() -> dict[str, str]:
    payload = json.loads(WD4_PATH.read_text())
    out = {}
    for row in payload["primary_mapping"]:
        target = row.get("strict_1_to_1_target")
        if target in {REVERSE, NO_TRADE}:
            out[str(row["position_id"])] = str(target)
    if len(out) != 821:
        raise RuntimeError(f"expected 821 reversal targets, got {len(out)}")
    return out


def load_gate_times(position_ids: set[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side, w.opened_at_ms,
            r.checked_at_ms as gate_checked_at_ms
        from wd1_trade_labels w
        join lateral (
            select checked_at_ms
            from entry_revalidations x
            where x.signal_id=w.signal_id
              and x.verdict='ENTER'
              and x.checked_at_ms <= w.opened_at_ms
            order by x.checked_at_ms desc
            limit 1
        ) r on true
        where w.closed_at_ms <= %s
          and w.position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS, list(position_ids)))
            rows = [dict(x) for x in cur.fetchall()]
    out = {str(r["position_id"]): r for r in rows}
    if len(out) != len(position_ids):
        raise RuntimeError(
            f"gate time coverage {len(out)}/{len(position_ids)}"
        )
    return out


def _cache_load() -> dict[str, list[list[Any]]]:
    out: dict[str, list[list[Any]]] = {}
    if not CACHE_PATH.exists():
        return out
    for line in CACHE_PATH.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def _fetch_one(meta: dict[str, Any]) -> tuple[str, list[list[Any]]]:
    pid = str(meta["position_id"])
    end_ms = int(meta["gate_checked_at_ms"])
    start_ms = end_ms - 40 * 60_000
    client = BinancePublicClient(timeout=8.0, retries=3)
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": str(meta["symbol"]),
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 60,
        },
    )
    # Causality guard: keep only candles fully closed by Stage11C decision.
    rows = [row for row in rows if len(row) >= 11 and int(row[6]) <= end_ms]
    return pid, rows


def ensure_micro_cache(
    gate_meta: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[list[Any]]]:
    cache = _cache_load()
    missing = [
        meta for pid, meta in gate_meta.items()
        if pid not in cache
    ]
    if missing:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fetched: list[tuple[str, list[list[Any]]]] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(_fetch_one, meta): meta for meta in missing}
            for i, future in enumerate(as_completed(futures), 1):
                meta = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                    fetched.append((pid, rows))
                except Exception as exc:
                    errors.append(f"{meta['position_id']}: {exc}")
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
                f"micro cache fetch failed for {len(errors)} rows; "
                f"sample={errors[:5]}"
            )
    return cache


def _bar(row: list[Any]) -> dict[str, float]:
    return {
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
        "quote": float(row[7]),
        "trades": float(row[8]),
        "taker_buy_quote": float(row[10]),
    }


def derive_micro_features(
    raw_rows: list[list[Any]],
    side: str,
    overheat_pressure: float,
) -> dict[str, float]:
    bars = [_bar(row) for row in raw_rows[-30:]]
    sign = 1.0 if side == "LONG" else -1.0
    if len(bars) < 16:
        raise RuntimeError(f"insufficient pre-entry bars: {len(bars)}")

    closes = [b["close"] for b in bars]
    ranges = [max(1e-12, b["high"] - b["low"]) for b in bars]
    volumes = [b["volume"] for b in bars]
    trades = [b["trades"] for b in bars]

    def side_ret(minutes: int, end_offset: int = 0) -> float:
        end_idx = len(bars) - 1 - end_offset
        start_idx = max(0, end_idx - minutes)
        if start_idx == end_idx:
            return 0.0
        return sign * 100.0 * (
            bars[end_idx]["close"] / bars[start_idx]["close"] - 1.0
        )

    ret1 = side_ret(1)
    ret3 = side_ret(3)
    ret5 = side_ret(5)
    ret10 = side_ret(10)
    ret15 = side_ret(15)
    ret30 = side_ret(min(29, len(bars) - 1))
    prev3 = side_ret(3, end_offset=3)
    prev5 = side_ret(5, end_offset=5)

    last = bars[-1]
    range_last = ranges[-1]
    clv = (last["close"] - last["low"]) / range_last
    selected_clv = clv if side == "LONG" else 1.0 - clv
    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    rejection_wick = (
        upper_wick / range_last if side == "LONG"
        else lower_wick / range_last
    )
    selected_body = sign * (last["close"] - last["open"]) / range_last

    consecutive = 0
    for b in reversed(bars):
        selected = sign * (b["close"] - b["open"]) > 0
        if selected:
            consecutive += 1
        else:
            break

    last15 = bars[-15:]
    last30 = bars
    if side == "LONG":
        extreme15 = max(b["high"] for b in last15)
        extreme30 = max(b["high"] for b in last30)
        dist15 = 100.0 * (extreme15 - last["close"]) / last["close"]
        dist30 = 100.0 * (extreme30 - last["close"]) / last["close"]
    else:
        extreme15 = min(b["low"] for b in last15)
        extreme30 = min(b["low"] for b in last30)
        dist15 = 100.0 * (last["close"] - extreme15) / last["close"]
        dist30 = 100.0 * (last["close"] - extreme30) / last["close"]

    prev10_ranges = ranges[-11:-1]
    prev10_volumes = volumes[-11:-1]
    prev10_trades = trades[-11:-1]
    last3_ranges = ranges[-3:]
    prev3_ranges = ranges[-6:-3]
    last3_volumes = volumes[-3:]
    prev3_volumes = volumes[-6:-3]

    def selected_taker_share(sub: list[dict[str, float]]) -> float:
        quote = sum(b["quote"] for b in sub)
        buy = sum(b["taker_buy_quote"] for b in sub)
        buy_share = buy / quote if quote > 0 else 0.5
        return buy_share if side == "LONG" else 1.0 - buy_share

    taker1 = selected_taker_share(bars[-1:])
    taker3 = selected_taker_share(bars[-3:])
    taker_prev3 = selected_taker_share(bars[-6:-3])
    taker_decay = taker3 - taker_prev3

    close20 = closes[-20:]
    mean20 = _mean(close20)
    std20 = math.sqrt(_mean([(x - mean20) ** 2 for x in close20]))
    z20_raw = (last["close"] - mean20) / (std20 + 1e-9)
    z20 = sign * z20_raw

    total_vol20 = sum(b["volume"] for b in bars[-20:])
    vwap20 = (
        sum(b["close"] * b["volume"] for b in bars[-20:]) / total_vol20
        if total_vol20 > 0 else mean20
    )
    vwap_extension = sign * 100.0 * (
        last["close"] / vwap20 - 1.0
    )

    volume_ratio_last = _safe_div(volumes[-1], _median(prev10_volumes))
    volume_ratio_3 = _safe_div(_mean(last3_volumes), _mean(prev3_volumes))
    range_ratio_last = _safe_div(ranges[-1], _median(prev10_ranges))
    range_ratio_3 = _safe_div(_mean(last3_ranges), _mean(prev3_ranges))
    trades_ratio_last = _safe_div(trades[-1], _median(prev10_trades))

    # Reversal-specific patterns: selected price still extended, but flow /
    # micro-speed / activity are fading.
    price_flow_divergence = max(0.0, ret3) * max(0.0, taker_prev3 - taker3)
    volume_climax_fade = max(
        0.0,
        _safe_div(max(volumes[-6:-1]), _median(volumes[-15:-6])) - 1.0,
    ) * max(0.0, 1.0 - _safe_div(volumes[-1], max(volumes[-6:-1])))
    range_contraction = max(
        0.0,
        _safe_div(max(ranges[-6:-1]), _median(ranges[-15:-6])) - 1.0,
    ) * max(0.0, 1.0 - _safe_div(ranges[-1], max(ranges[-6:-1])))

    decay3 = prev3 - ret3
    decay5 = prev5 - ret5
    reversal_pressure = (
        max(0.0, overheat_pressure)
        * (1.0 + max(0.0, decay3) + max(0.0, decay5))
        * (1.0 + max(0.0, taker_prev3 - taker3))
        * (1.0 + rejection_wick)
        * (1.0 + max(0.0, z20))
    )

    return {
        "f_micro_bar_count": float(len(bars)),
        "f_micro_side_ret_1m": ret1,
        "f_micro_side_ret_3m": ret3,
        "f_micro_side_ret_5m": ret5,
        "f_micro_side_ret_10m": ret10,
        "f_micro_side_ret_15m": ret15,
        "f_micro_side_ret_30m": ret30,
        "f_micro_prev3_side_ret": prev3,
        "f_micro_prev5_side_ret": prev5,
        "f_micro_decay_3_vs_prev3": decay3,
        "f_micro_decay_5_vs_prev5": decay5,
        "f_micro_distance_selected_extreme_15m": dist15,
        "f_micro_distance_selected_extreme_30m": dist30,
        "f_micro_selected_clv_last": selected_clv,
        "f_micro_rejection_wick_last": rejection_wick,
        "f_micro_selected_body_last": selected_body,
        "f_micro_consecutive_selected_bars": float(consecutive),
        "f_micro_range_ratio_last_vs_prev10": range_ratio_last,
        "f_micro_range_ratio_3_vs_prev3": range_ratio_3,
        "f_micro_volume_ratio_last_vs_prev10": volume_ratio_last,
        "f_micro_volume_ratio_3_vs_prev3": volume_ratio_3,
        "f_micro_trades_ratio_last_vs_prev10": trades_ratio_last,
        "f_micro_selected_taker_share_1m": taker1,
        "f_micro_selected_taker_share_3m": taker3,
        "f_micro_selected_taker_share_prev3m": taker_prev3,
        "f_micro_taker_decay_3_vs_prev3": taker_decay,
        "f_micro_price_flow_divergence": price_flow_divergence,
        "f_micro_volume_climax_then_fade": volume_climax_fade,
        "f_micro_range_contraction_after_impulse": range_contraction,
        "f_micro_close_z_20": z20,
        "f_micro_selected_vwap_extension_20": vwap_extension,
        "f_micro_reversal_pressure": reversal_pressure,
    }


def _portable_base_features(
    rows: list[dict[str, Any]],
) -> list[str]:
    features = [
        key for key in rows[0]
        if key.startswith("f_")
        and not key.startswith("f_micro_")
        and key not in TIME_FEATURES
        and key not in SCALE_PROXY_FEATURES
        and not key.startswith("f_latency_")
    ]
    return [
        feature for feature in features
        if len({str(r.get(feature, "")) for r in rows}) > 1
    ]


def _is_numeric(rows: list[dict[str, Any]], feature: str) -> bool:
    for row in rows[:200]:
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


def _categorical_sep(
    rows: list[dict[str, Any]],
    feature: str,
    target_key: str,
) -> float:
    base = sum(int(r[target_key]) for r in rows) / len(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[str(row[feature])].append(int(row[target_key]))
    weighted = 0.0
    for ys in groups.values():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
    return min(1.0, 2.0 * weighted)


def _numeric_sep(
    rows: list[dict[str, Any]],
    feature: str,
    target_key: str,
) -> float:
    y = [int(r[target_key]) for r in rows]
    p = [float(r[feature]) for r in rows]
    auc = auc_score(y, p)
    return 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0


def rank_features(
    rows: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
    target_key: str,
) -> list[str]:
    scores = []
    for feature in features:
        score = (
            _numeric_sep(rows, feature, target_key)
            if types[feature] == "numeric"
            else _categorical_sep(rows, feature, target_key)
        )
        scores.append((score, feature))
    scores.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [feature for _, feature in scores]


def _split(rows: list[dict[str, Any]]) -> tuple[list, list, list]:
    rr = sorted(rows, key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(rr)
    return rr[:3*n//5], rr[3*n//5:4*n//5], rr[4*n//5:]


def fit_head(
    rows: list[dict[str, Any]],
    target_key: str,
    variants: dict[str, list[str]],
) -> dict[str, Any]:
    train, val, test = _split(rows)
    all_features = sorted(set(f for fs in variants.values() for f in fs))
    types = _types(rows, all_features)

    variant_results = {}
    for name, candidates in variants.items():
        ordered = rank_features(train, candidates, types, target_key)
        grid = []
        for k in (5, 10, 20, 40, 60):
            if k > len(ordered):
                continue
            chosen = ordered[:k]
            for l2 in (0.1, 1.0, 4.0):
                encoder = Encoder(chosen, types).fit(train)
                model = LogisticModel(
                    l2=l2,
                    epochs=700,
                    lr=0.12,
                ).fit(
                    encoder.transform(train),
                    [int(r[target_key]) for r in train],
                )
                val_p = model.predict_proba(encoder.transform(val))
                val_y = [int(r[target_key]) for r in val]
                metrics = binary_metrics(val_y, val_p)
                grid.append({
                    "k": len(chosen),
                    "l2": l2,
                    "features": chosen,
                    "validation": metrics,
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
        val_p = model.predict_proba(encoder.transform(val))
        val_y = [int(r[target_key]) for r in val]
        triage = choose_triage_thresholds(val_y, val_p)

        test_p = model.predict_proba(encoder.transform(test))
        test_y = [int(r[target_key]) for r in test]
        test_metrics = binary_metrics(test_y, test_p)
        test_triage = None
        if triage["selected"] is not None:
            t = triage["selected"]
            test_triage = triage_metrics(
                test_y, test_p, float(t["lower"]), float(t["upper"])
            )

        variant_results[name] = {
            "selected_k": selected["k"],
            "selected_l2": selected["l2"],
            "selected_features": selected["features"],
            "validation": selected["validation"],
            "validation_triage": triage,
            "test": test_metrics,
            "test_triage": test_triage,
        }

    best_name = max(
        variant_results,
        key=lambda name: (
            variant_results[name]["validation"]["auc"]
            if variant_results[name]["validation"]["auc"] is not None
            else -1.0
        ),
    )
    return {
        "n": len(rows),
        "train_n": len(train),
        "validation_n": len(val),
        "test_n": len(test),
        "target_prevalence": (
            sum(int(r[target_key]) for r in rows) / len(rows)
        ),
        "variants": variant_results,
        "selected_variant": best_name,
        "selected": variant_results[best_name],
    }


def augment_reversal_rows(
    base_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets = load_wd4_targets()
    byid = {str(r["meta_position_id"]): r for r in base_rows}
    gate_meta = load_gate_times(set(targets))
    cache = ensure_micro_cache(gate_meta)

    out = []
    coverage = Counter()
    for pid, target in targets.items():
        row = dict(byid[pid])
        micro = derive_micro_features(
            cache[pid],
            str(row["meta_original_side"]),
            float(row["f_new_overheat_pressure"]),
        )
        row.update({k: str(v) for k, v in micro.items()})
        row["target_head_reversal"] = 1 if target == REVERSE else 0
        row["target_head_reversal_name"] = (
            "REVERSE" if target == REVERSE else "NO_TRADE"
        )
        out.append(row)
        coverage[len(cache[pid])] += 1

    out.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    return out, {
        "rows": len(out),
        "cache_rows": len(cache),
        "bar_count_distribution": dict(coverage),
        "minimum_bars": min(int(float(r["f_micro_bar_count"])) for r in out),
    }


def prepare_head_rows(
    base_rows: list[dict[str, Any]],
) -> tuple[list, list]:
    health = []
    path = []
    for source in base_rows:
        opp = source["label_opportunity_tier"]
        path_style = source["label_path_style"]
        realized = float(source["future_realized_pnl_pct"])

        if opp in {"RUNNER", "BIG_RUNNER"} and (
            realized > 0 or path_style == "MISSED_OPPORTUNITY"
        ):
            row = dict(source)
            row["target_head_health"] = (
                1 if realized > 0 else 0
            )
            row["target_head_health_name"] = (
                "HEALTHY" if realized > 0 else "OVERHEATED_FAILURE"
            )
            health.append(row)

        if path_style in {"CLEAN_WINNER", "RECOVERED_WINNER"}:
            row = dict(source)
            row["target_head_recovered"] = (
                1 if path_style == "RECOVERED_WINNER" else 0
            )
            row["target_head_recovered_name"] = (
                "RECOVERED" if row["target_head_recovered"] else "CLEAN"
            )
            path.append(row)

    health.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    path.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    return health, path


def reversal_nonlinear_sensitivity(
    reversal_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    train, val, test = _split(reversal_rows)
    features = list(MICRO_FEATURES)
    types = _types(reversal_rows, features)
    ordered = rank_features(
        train,
        features,
        types,
        "target_head_reversal",
    )

    y_train = [int(r["target_head_reversal"]) for r in train]
    y_val = [int(r["target_head_reversal"]) for r in val]
    y_test = [int(r["target_head_reversal"]) for r in test]
    grid = []
    for k in (5, 10, 20, len(ordered)):
        chosen = ordered[:k]
        encoder = Encoder(chosen, types).fit(train)
        x_train = encoder.transform(train)
        x_val = encoder.transform(val)
        x_test = encoder.transform(test)
        for depth in (2, 3, 4):
            for min_leaf in (15, 25, 35):
                model = RandomForestModel(
                    trees=80,
                    max_depth=depth,
                    min_leaf=min_leaf,
                    seed=20261001,
                ).fit(x_train, y_train)
                val_metrics = binary_metrics(
                    y_val,
                    model.predict_proba(x_val),
                )
                test_metrics = binary_metrics(
                    y_test,
                    model.predict_proba(x_test),
                )
                grid.append({
                    "k": len(chosen),
                    "max_depth": depth,
                    "min_leaf": min_leaf,
                    "features": chosen,
                    "validation": val_metrics,
                    "test": test_metrics,
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
        "model": "shallow_random_forest",
        "selected": grid[0],
        "top_grid": grid[:10],
    }


def reversal_novel_symbol_sensitivity(
    reversal_rows: list[dict[str, Any]],
    selected: dict[str, Any],
) -> dict[str, Any]:
    train, val, test = _split(reversal_rows)
    features = list(selected["selected_features"])
    types = _types(reversal_rows, features)
    encoder = Encoder(features, types).fit(train)
    model = LogisticModel(
        l2=float(selected["selected_l2"]),
        epochs=700,
        lr=0.12,
    ).fit(
        encoder.transform(train),
        [int(r["target_head_reversal"]) for r in train],
    )
    seen_symbols = {
        str(r["meta_symbol"])
        for r in train + val
    }
    novel = [
        r for r in test
        if str(r["meta_symbol"]) not in seen_symbols
    ]
    y = [int(r["target_head_reversal"]) for r in novel]
    p = model.predict_proba(encoder.transform(novel))
    return {
        "n": len(novel),
        "unique_symbols": len({
            str(r["meta_symbol"]) for r in novel
        }),
        "metrics": binary_metrics(y, p),
    }


def wd5e_conclusion(
    heads: dict[str, Any],
    nonlinear: dict[str, Any],
    novel: dict[str, Any],
) -> dict[str, Any]:
    health = heads["continuation_health"]
    path = heads["path_expectation_recovered"]
    reversal = heads["reversal_thesis"]

    health_selected = health["selected"]
    health_stable = (
        float(health_selected["validation"]["auc"]) >= 0.70
        and float(health_selected["test"]["auc"]) >= 0.70
    )

    # Path feature-space status considers whether any predeclared feature
    # variant stays >=0.70 in both chronological windows. This is not used
    # to replace the validation-selected model; it only diagnoses whether
    # the feature family itself is promising.
    path_variant_pairs = [
        (
            float(v["validation"]["auc"]),
            float(v["test"]["auc"]),
        )
        for v in path["variants"].values()
    ]
    path_feature_space_promising = any(
        min(pair) >= 0.70
        for pair in path_variant_pairs
    )
    path_selected_stable = (
        float(path["selected"]["validation"]["auc"]) >= 0.70
        and float(path["selected"]["test"]["auc"]) >= 0.70
    )

    reversal_pairs = [
        (
            float(v["validation"]["auc"]),
            float(v["test"]["auc"]),
        )
        for v in reversal["variants"].values()
    ]
    nonlinear_pair = (
        float(nonlinear["selected"]["validation"]["auc"]),
        float(nonlinear["selected"]["test"]["auc"]),
    )
    reversal_best_min_auc = max(
        [min(pair) for pair in reversal_pairs]
        + [min(nonlinear_pair)]
    )
    novel_auc = novel["metrics"]["auc"]
    reversal_robust = (
        reversal_best_min_auc >= 0.65
        and novel_auc is not None
        and float(novel_auc) >= 0.55
    )

    return {
        "overall_status": "PARTIAL_PASS_NOT_PRODUCTION_READY",
        "continuation_health_status": (
            "PROMISING_STABLE"
            if health_stable
            else "UNSTABLE"
        ),
        "path_expectation_status": (
            "PROMISING_BUT_MODEL_SELECTION_UNSTABLE"
            if path_feature_space_promising and not path_selected_stable
            else "PROMISING_STABLE"
            if path_feature_space_promising and path_selected_stable
            else "UNSTABLE"
        ),
        "reversal_thesis_status": (
            "PROMISING_STABLE"
            if reversal_robust
            else "NO_ROBUST_REVERSAL_HEAD"
        ),
        "reversal_best_min_chronological_auc": reversal_best_min_auc,
        "reversal_novel_symbol_auc": novel_auc,
        "production_authority": "NONE",
        "next_stage_gate": (
            "Do not run full multi-head production replay as an action policy "
            "until the reversal head is improved or explicitly allowed to "
            "ABSTAIN and fall back to NO TRADE."
        ),
    }


def run_wd5e() -> dict[str, Any]:
    base_rows = load_base_rows()
    base_features = _portable_base_features(base_rows)
    new_features = [
        f for f in base_features if f.startswith("f_new_")
    ]
    legacy_features = [
        f for f in base_features if not f.startswith("f_new_")
    ]

    health_rows, path_rows = prepare_head_rows(base_rows)
    reversal_rows, micro_coverage = augment_reversal_rows(base_rows)

    with OUTPUT_DATASET.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(reversal_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(reversal_rows)

    health = fit_head(
        health_rows,
        "target_head_health",
        {
            "legacy": legacy_features,
            "wd5d_engineered": new_features,
            "combined": legacy_features + new_features,
        },
    )
    path = fit_head(
        path_rows,
        "target_head_recovered",
        {
            "legacy": legacy_features,
            "wd5d_engineered": new_features,
            "combined": legacy_features + new_features,
        },
    )
    reversal = fit_head(
        reversal_rows,
        "target_head_reversal",
        {
            "legacy": legacy_features,
            "wd5d_engineered": new_features,
            "micro_only": list(MICRO_FEATURES),
            "engineered_plus_micro": new_features + list(MICRO_FEATURES),
            "all_portable": legacy_features + new_features + list(MICRO_FEATURES),
        },
    )
    heads = {
        "continuation_health": health,
        "path_expectation_recovered": path,
        "reversal_thesis": reversal,
    }
    reversal_nonlinear = reversal_nonlinear_sensitivity(reversal_rows)
    reversal_novel = reversal_novel_symbol_sensitivity(
        reversal_rows,
        reversal["selected"],
    )
    conclusion = wd5e_conclusion(
        heads,
        reversal_nonlinear,
        reversal_novel,
    )

    result = {
        "version": WD5E_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "heads": heads,
        "reversal_nonlinear_sensitivity": reversal_nonlinear,
        "reversal_novel_symbol_sensitivity": reversal_novel,
        "conclusion": conclusion,
        "micro_features": list(MICRO_FEATURES),
        "micro_feature_count": len(MICRO_FEATURES),
        "micro_coverage": micro_coverage,
        "architecture": {
            "health_positive": "HEALTHY continuation among MFE>=1% runner opportunities",
            "path_positive": "RECOVERED path among clean/recovered winners",
            "reversal_positive": "REVERSE among WD4 strict reverse/no-trade targets",
        },
        "outputs": {
            "dataset": str(OUTPUT_DATASET),
            "json": str(OUTPUT_JSON),
            "cache": str(CACHE_PATH),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
