from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.binance import BinancePublicClient
from market_radar.persistence import _postgres_connect
from .wd5e_multihead import (
    derive_micro_features,
)
from .wd5f_conditional_reversal import (
    BENCHMARKS,
    _fetch_klines_range,
    derive_flow_structure_features,
    derive_market_features,
    derive_oi_features,
)

WD5H4A_VERSION = "wd5h-stage4a-temporal-feature-reconstruction-v1"

BASE_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
LABEL_PATH = Path("/app/data/wd5h3a_triple_barrier_labels.csv")
PREENTRY_CACHE = Path("/app/data/wd5h1_preentry_1m_cache.jsonl")
POSTENTRY_CACHE = Path("/app/data/wd5h3a_postentry_1m_cache.jsonl")
BENCHMARK_CACHE = Path("/app/data/wd5h4a_benchmark_1m_cache.json")
OI_CACHE = Path("/app/data/wd5h4a_oi_5m_cache.jsonl")
OUTPUT_CSV = Path("/app/data/wd5h4a_temporal_features.csv")
OUTPUT_JSON = Path("/app/data/wd5h4a_temporal_feature_results.json")

HORIZONS_MIN = (1, 2, 3)
MAX_HORIZON_MIN = max(HORIZONS_MIN)

CURATED_DELTA_BASE = (
    "f_micro_side_ret_1m",
    "f_micro_side_ret_3m",
    "f_micro_side_ret_5m",
    "f_micro_selected_taker_share_1m",
    "f_micro_selected_taker_share_3m",
    "f_micro_distance_selected_extreme_15m",
    "f_micro_selected_vwap_extension_20",
    "f_micro_reversal_pressure",
    "f_f_coin_minus_market_5m",
    "f_f_coin_minus_market_15m",
    "f_f_coin_residual_5m_vs_btc",
    "f_f_taker_selected_share_1m",
    "f_f_taker_selected_share_3m",
    "f_f_oi_change_5m_pct",
    "f_f_oi_accel_5m_pct",
)


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _load_jsonl_rows(path: Path) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def load_base() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASE_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 base rows, got {len(rows)}")
    return rows


def load_labels() -> dict[str, dict[str, Any]]:
    out = {
        r["position_id"]: r
        for r in csv.DictReader(LABEL_PATH.open())
    }
    if len(out) != 2175:
        raise RuntimeError(f"expected 2175 labels, got {len(out)}")
    return out


def load_gate_meta(position_ids: set[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side, w.opened_at_ms,
            r.checked_at_ms as gate_checked_at_ms,
            r.snapshot_json,
            e.stage11c_finished_at_ms
        from wd1_trade_labels w
        join lateral (
            select checked_at_ms, snapshot_json
            from entry_revalidations x
            where x.signal_id=w.signal_id
              and x.verdict='ENTER'
              and x.checked_at_ms <= w.opened_at_ms
            order by x.checked_at_ms desc
            limit 1
        ) r on true
        left join entry_latency e on e.signal_id=w.signal_id
        where w.position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (list(position_ids),))
            rows = [dict(x) for x in cur.fetchall()]
    out = {}
    for row in rows:
        snap = row.get("snapshot_json")
        if isinstance(snap, str):
            snap = json.loads(snap or "{}")
        row["snapshot"] = snap if isinstance(snap, dict) else {}
        out[str(row["position_id"])] = row
    if len(out) != len(position_ids):
        raise RuntimeError(
            f"gate coverage {len(out)}/{len(position_ids)}"
        )
    return out


def merge_closed_rows(
    pre_rows: list[list[Any]],
    post_rows: list[list[Any]],
    target_ms: int,
) -> list[list[Any]]:
    by_open: dict[int, list[Any]] = {}
    for row in list(pre_rows) + list(post_rows):
        if len(row) < 11:
            continue
        if int(row[6]) <= target_ms:
            by_open[int(row[0])] = row
    return [by_open[k] for k in sorted(by_open)]


def new_closed_rows(
    post_rows: list[list[Any]],
    gate_ms: int,
    target_ms: int,
) -> list[list[Any]]:
    return sorted(
        [
            row for row in post_rows
            if len(row) >= 11
            and int(row[6]) > gate_ms
            and int(row[6]) <= target_ms
        ],
        key=lambda r: int(r[6]),
    )


def selected_taker_share(rows: list[list[Any]], side: str) -> float | None:
    if not rows:
        return None
    total_vol = sum(float(r[5]) for r in rows)
    if total_vol <= 0:
        return None
    taker_buy = sum(float(r[9]) for r in rows)
    buy_share = taker_buy / total_vol
    return buy_share if side == "LONG" else 1.0 - buy_share


def temporal_path_features(
    rows: list[list[Any]],
    *,
    side: str,
    gate_price: float,
) -> dict[str, Any]:
    if not rows:
        return {
            "confirm_closed_bars": 0,
            "confirm_side_return_pct": None,
            "confirm_mfe_pct": None,
            "confirm_mae_pct": None,
            "confirm_selected_taker_share": None,
            "confirm_volume": 0.0,
            "confirm_trades": 0.0,
            "confirm_last_clv_selected": None,
            "confirm_last_body_selected": None,
            "confirm_last_rejection_wick": None,
        }
    sign = 1.0 if side == "LONG" else -1.0
    latest = rows[-1]
    latest_close = float(latest[4])
    side_return = sign * (latest_close / gate_price - 1.0) * 100.0

    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    if side == "LONG":
        mfe = (max(highs) / gate_price - 1.0) * 100.0
        mae = (min(lows) / gate_price - 1.0) * 100.0
    else:
        mfe = (gate_price / min(lows) - 1.0) * 100.0
        mae = (gate_price / max(highs) - 1.0) * 100.0

    o, h, l, c = map(float, (latest[1], latest[2], latest[3], latest[4]))
    span = max(1e-12, h - l)
    clv_long = (c - l) / span
    clv_selected = clv_long if side == "LONG" else 1.0 - clv_long
    body_selected = sign * (c - o) / span
    rejection = (
        (h - max(o, c)) / span
        if side == "LONG"
        else (min(o, c) - l) / span
    )

    return {
        "confirm_closed_bars": len(rows),
        "confirm_side_return_pct": side_return,
        "confirm_mfe_pct": mfe,
        "confirm_mae_pct": mae,
        "confirm_selected_taker_share": selected_taker_share(rows, side),
        "confirm_volume": sum(float(r[5]) for r in rows),
        "confirm_trades": sum(float(r[8]) for r in rows),
        "confirm_last_clv_selected": clv_selected,
        "confirm_last_body_selected": body_selected,
        "confirm_last_rejection_wick": rejection,
    }


def ensure_benchmark_cache(
    min_gate_ms: int,
    max_target_ms: int,
) -> dict[str, list[list[Any]]]:
    start = min_gate_ms - 45 * 60_000
    end = max_target_ms + 60_000
    if BENCHMARK_CACHE.exists():
        payload = json.loads(BENCHMARK_CACHE.read_text())
        if (
            int(payload.get("start_ms", 0)) <= start
            and int(payload.get("end_ms", 0)) >= max_target_ms
            and all(
                s in payload.get("symbols", {})
                for s in BENCHMARKS
            )
        ):
            return payload["symbols"]

    client = BinancePublicClient(timeout=10.0, retries=3)
    symbols = {}
    for symbol in BENCHMARKS:
        symbols[symbol] = _fetch_klines_range(
            client, symbol, start, end
        )
    payload = {
        "start_ms": start,
        "end_ms": end,
        "symbols": symbols,
    }
    BENCHMARK_CACHE.write_text(
        json.dumps(payload, separators=(",", ":"))
    )
    return symbols


def _fetch_oi_one(
    meta: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    gate = int(meta["gate_checked_at_ms"])
    target = gate + MAX_HORIZON_MIN * 60_000
    client = BinancePublicClient(timeout=8.0, retries=3)
    rows = client.get(
        "/futures/data/openInterestHist",
        {
            "symbol": str(meta["symbol"]),
            "period": "5m",
            "startTime": gate - 45 * 60_000,
            "endTime": target,
            "limit": 20,
        },
    )
    rows = [
        r for r in rows
        if int(r.get("timestamp", 0)) <= target
    ]
    return str(meta["position_id"]), rows


def ensure_oi_cache(
    gate_meta: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    cache: dict[str, list[dict[str, Any]]] = {}
    if OI_CACHE.exists():
        cache = _load_jsonl_rows(OI_CACHE)

    def complete(meta: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
        if not rows:
            return False
        gate = int(meta["gate_checked_at_ms"])
        target = gate + MAX_HORIZON_MIN * 60_000
        # A 5m OI series is considered complete if it reaches the
        # latest 5-minute observation boundary not after target.
        required = (target // 300_000) * 300_000
        return max(int(r.get("timestamp", 0)) for r in rows) >= required

    missing = [
        meta for pid, meta in gate_meta.items()
        if pid not in cache or not complete(meta, cache[pid])
    ]
    if missing:
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_oi_one, meta): meta
                for meta in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                meta = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                except Exception as exc:
                    errors.append(f"{meta['position_id']}: {exc}")
                if i % 100 == 0:
                    time.sleep(0.2)
        if errors:
            raise RuntimeError(
                f"OI fetch failures={len(errors)} sample={errors[:5]}"
            )

    with OI_CACHE.open("w") as fh:
        for pid in sorted(
            gate_meta,
            key=lambda x: int(gate_meta[x]["gate_checked_at_ms"]),
        ):
            fh.write(json.dumps(
                {"position_id": pid, "rows": cache[pid]},
                separators=(",", ":"),
            ) + "\n")
    return {pid: cache[pid] for pid in gate_meta}


def oi_rows_at(
    rows: list[dict[str, Any]],
    target_ms: int,
) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if int(r.get("timestamp", 0)) <= target_ms
    ]


def build_temporal_dataset() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = load_base()
    labels = load_labels()
    ids = {str(r["meta_position_id"]) for r in base}
    gate_meta = load_gate_meta(ids)
    pre_cache = _load_jsonl_rows(PREENTRY_CACHE)
    post_cache = _load_jsonl_rows(POSTENTRY_CACHE)

    if set(pre_cache) < ids:
        raise RuntimeError("preentry cache missing frozen positions")
    if set(post_cache) < ids:
        raise RuntimeError("postentry cache missing frozen positions")

    min_gate = min(
        int(m["gate_checked_at_ms"]) for m in gate_meta.values()
    )
    max_target = max(
        int(m["gate_checked_at_ms"]) + MAX_HORIZON_MIN * 60_000
        for m in gate_meta.values()
    )
    benchmarks = ensure_benchmark_cache(min_gate, max_target)
    oi_cache = ensure_oi_cache(gate_meta)

    out = []
    causality_violations = []
    horizon_bar_counts = {h: Counter() for h in HORIZONS_MIN}
    oi_new_point = {h: 0 for h in HORIZONS_MIN}
    exact_gate_match = 0
    fill_latencies = []

    for source in base:
        pid = str(source["meta_position_id"])
        meta = gate_meta[pid]
        gate_ms = int(meta["gate_checked_at_ms"])
        opened_ms = int(source["meta_opened_at_ms"])
        fill_latencies.append(opened_ms - gate_ms)
        if (
            meta.get("stage11c_finished_at_ms") is not None
            and int(meta["stage11c_finished_at_ms"]) == gate_ms
        ):
            exact_gate_match += 1

        snap = meta["snapshot"]
        gate_price = _f(snap.get("current_price"))
        if gate_price is None or gate_price <= 0:
            gate_price = _f(source.get("f_gate_current_price"))
        if gate_price is None or gate_price <= 0:
            raise RuntimeError(f"missing gate price {pid}")

        side = str(source["meta_original_side"]).upper()
        base_oi_rows = oi_rows_at(oi_cache[pid], gate_ms)
        base_oi_last = (
            max(int(r["timestamp"]) for r in base_oi_rows)
            if base_oi_rows else None
        )

        row: dict[str, Any] = {
            "position_id": pid,
            "signal_id": source["meta_signal_id"],
            "symbol": source["meta_symbol"],
            "side": side,
            "gate_checked_at_ms": gate_ms,
            "opened_at_ms": opened_ms,
            "fill_latency_ms": opened_ms - gate_ms,
            "gate_current_price": gate_price,
            "gate_signal_price": _f(snap.get("signal_price")),
            "primary_meta_label": labels[pid]["primary_meta_label"],
            "primary_label_end_ms": int(labels[pid]["primary_label_end_ms"]),
            "primary_uniqueness_weight": float(
                labels[pid]["primary_uniqueness_weight"]
            ),
        }

        overheat = float(source["f_new_overheat_pressure"])

        for horizon in HORIZONS_MIN:
            target = gate_ms + horizon * 60_000
            prefix = f"t{horizon}"
            combined = merge_closed_rows(
                pre_cache[pid], post_cache[pid], target
            )
            new_rows = new_closed_rows(
                post_cache[pid], gate_ms, target
            )
            horizon_bar_counts[horizon][len(new_rows)] += 1

            for rr in combined:
                if int(rr[6]) > target:
                    causality_violations.append(
                        f"{pid}:{prefix}:kline"
                    )

            temporal = temporal_path_features(
                new_rows, side=side, gate_price=gate_price
            )
            micro = derive_micro_features(
                combined, side, overheat
            )
            market = derive_market_features(
                combined, benchmarks, target, side
            )
            flow = derive_flow_structure_features(
                combined, side
            )

            oi_rows = oi_rows_at(oi_cache[pid], target)
            latest_oi = (
                max(int(r["timestamp"]) for r in oi_rows)
                if oi_rows else None
            )
            if (
                latest_oi is not None
                and base_oi_last is not None
                and latest_oi > base_oi_last
            ):
                oi_new_point[horizon] += 1
            for rr in oi_rows:
                if int(rr["timestamp"]) > target:
                    causality_violations.append(
                        f"{pid}:{prefix}:oi"
                    )

            oi = derive_oi_features(
                oi_rows,
                float(micro["f_micro_side_ret_5m"]),
                overheat,
            )

            for key, value in temporal.items():
                row[f"{prefix}_{key}"] = value
            row[f"{prefix}_target_ms"] = target
            row[f"{prefix}_latest_closed_ms"] = (
                int(new_rows[-1][6]) if new_rows else None
            )
            row[f"{prefix}_oi_latest_timestamp_ms"] = latest_oi
            row[f"{prefix}_oi_new_point_since_t0"] = int(
                latest_oi is not None
                and base_oi_last is not None
                and latest_oi > base_oi_last
            )
            row[f"{prefix}_oi_age_s"] = (
                (target - latest_oi) / 1000.0
                if latest_oi is not None else None
            )

            families = {}
            families.update(micro)
            families.update(market)
            families.update(flow)
            families.update(oi)
            for key, value in families.items():
                row[f"{prefix}_{key}"] = value

            for key in CURATED_DELTA_BASE:
                if key not in families or key not in source:
                    continue
                now = _f(families[key])
                old = _f(source[key])
                row[f"{prefix}_delta_{key[2:]}"] = (
                    now - old
                    if now is not None and old is not None
                    else None
                )

        out.append(row)

    out.sort(key=lambda r: int(r["gate_checked_at_ms"]))

    fields = []
    seen = set()
    for r in out:
        for k in r:
            if k not in seen:
                fields.append(k)
                seen.add(k)
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    temporal_features = [
        k for k in fields
        if k.startswith(("t1_", "t2_", "t3_"))
        and not k.endswith((
            "_target_ms",
            "_latest_closed_ms",
            "_oi_latest_timestamp_ms",
        ))
    ]
    family_counts = {}
    for h in HORIZONS_MIN:
        p = f"t{h}_"
        family_counts[str(h)] = {
            "total": sum(k.startswith(p) for k in temporal_features),
            "micro": sum(k.startswith(p + "f_micro_") for k in temporal_features),
            "market": sum(
                k.startswith(p + "f_f_market_")
                or k.startswith(p + "f_f_coin_")
                or k.startswith(p + "f_f_btc_")
                or k.startswith(p + "f_f_eth_")
                or k.startswith(p + "f_f_relative_")
                for k in temporal_features
            ),
            "flow": sum(
                k.startswith(p + "f_f_taker_")
                or "flow" in k[len(p):]
                for k in temporal_features
            ),
            "oi": sum(
                k.startswith(p + "f_f_oi_")
                or k.startswith(p + "oi_")
                for k in temporal_features
            ),
            "confirmation_path": sum(
                k.startswith(p + "confirm_")
                for k in temporal_features
            ),
            "delta": sum(
                k.startswith(p + "delta_")
                for k in temporal_features
            ),
        }

    summary = {
        "version": WD5H4A_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "coverage": {
            "rows": len(out),
            "gate_exact_stage11c_match_n": exact_gate_match,
            "gate_exact_stage11c_match_pct": (
                100.0 * exact_gate_match / len(out)
            ),
            "fill_latency_ms_median": statistics.median(fill_latencies),
            "fill_latency_ms_p90": sorted(fill_latencies)[
                int(0.90 * (len(fill_latencies) - 1))
            ],
            "preentry_cache_n": len(pre_cache),
            "postentry_cache_n": len(post_cache),
            "oi_cache_n": len(oi_cache),
            "benchmark_symbols": list(BENCHMARKS),
            "causality_violations_n": len(causality_violations),
            "causality_violation_sample": causality_violations[:10],
        },
        "horizon_closed_bar_counts": {
            str(h): dict(sorted(c.items()))
            for h, c in horizon_bar_counts.items()
        },
        "oi_temporal_update_coverage": {
            str(h): {
                "new_5m_oi_point_n": oi_new_point[h],
                "new_5m_oi_point_pct": 100.0 * oi_new_point[h] / len(out),
            }
            for h in HORIZONS_MIN
        },
        "feature_counts": {
            "output_columns": len(fields),
            "temporal_feature_columns": len(temporal_features),
            "per_horizon": family_counts,
        },
        "labels_carried_for_stage4b": dict(Counter(
            r["primary_meta_label"] for r in out
        )),
        "method": {
            "t0": "exact latest Stage11C ENTER checked_at_ms; equals stage11c_finished_at_ms",
            "horizons_min": list(HORIZONS_MIN),
            "kline_causality": "only 1m candles with close_time <= T0+horizon",
            "benchmark_causality": "benchmark 1m data evaluated only through target timestamp",
            "oi_causality": "5m openInterestHist rows with timestamp <= target; temporal update availability reported explicitly",
            "no_model_training": True,
            "no_threshold_selection": True,
        },
        "stage_conclusion": {
            "status": "TEMPORAL_FEATURE_RECONSTRUCTION_COMPLETE",
            "next_stage": "WD-5H Stage 4B — Temporal Confirmation Pattern Discovery",
            "production_authority": "NONE",
        },
        "outputs": {
            "csv": str(OUTPUT_CSV),
            "json": str(OUTPUT_JSON),
            "benchmark_cache": str(BENCHMARK_CACHE),
            "oi_cache": str(OI_CACHE),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(
        summary, indent=2, allow_nan=False
    ))
    return out, summary


def run_wd5h_stage4a() -> dict[str, Any]:
    _, summary = build_temporal_dataset()
    return summary
