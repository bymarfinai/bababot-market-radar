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


WD5H3A_VERSION = "wd5h-stage3a-triple-barrier-meta-label-v1"

INPUT_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
POSTENTRY_CACHE = Path("/app/data/wd5h3a_postentry_1m_cache.jsonl")
OUTPUT_ROWS = Path("/app/data/wd5h3a_triple_barrier_labels.csv")
OUTPUT_JSON = Path("/app/data/wd5h3a_triple_barrier_results.json")

NOTIONAL_USDT = 500.0

# Frozen before inspecting Stage 3A labels. Primary mirrors the pre-existing
# WD-4 strict bounded-economic criterion.
BARRIER_CONFIGS = (
    {
        "name": "PRIMARY_NET_0P5_30M",
        "tp_pct": 0.50,
        "sl_pct": 0.50,
        "horizon_min": 30,
        "primary": True,
    },
    {
        "name": "SENS_NET_0P5_60M",
        "tp_pct": 0.50,
        "sl_pct": 0.50,
        "horizon_min": 60,
        "primary": False,
    },
    {
        "name": "SENS_NET_1P0_30M",
        "tp_pct": 1.00,
        "sl_pct": 1.00,
        "horizon_min": 30,
        "primary": False,
    },
    {
        "name": "SENS_NET_1P0_60M",
        "tp_pct": 1.00,
        "sl_pct": 1.00,
        "horizon_min": 60,
        "primary": False,
    },
)

PRIMARY_CONFIG = next(c for c in BARRIER_CONFIGS if c["primary"])
MAX_HORIZON_MIN = max(int(c["horizon_min"]) for c in BARRIER_CONFIGS)


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _entry_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = slippage_bps / 10_000.0
    return market * (1.0 + slip if side == "LONG" else 1.0 - slip)


def _exit_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = slippage_bps / 10_000.0
    return market * (1.0 - slip if side == "LONG" else 1.0 + slip)


def _gross(side: str, qty: float, entry: float, exit_: float) -> float:
    if side == "LONG":
        return qty * (exit_ - entry)
    return qty * (entry - exit_)


def net_pnl_at_market(
    *,
    side: str,
    entry_market: float,
    exit_market: float,
    fee_rate: float,
    slippage_bps: float,
    notional: float = NOTIONAL_USDT,
) -> float:
    entry_fill = _entry_fill(side, entry_market, slippage_bps)
    exit_fill = _exit_fill(side, exit_market, slippage_bps)
    qty = notional / entry_fill
    entry_fee = qty * entry_fill * fee_rate
    exit_fee = qty * exit_fill * fee_rate
    return _gross(side, qty, entry_fill, exit_fill) - entry_fee - exit_fee


def load_base_rows() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(INPUT_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 rows, got {len(rows)}")
    return rows


def load_positions(position_ids: set[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            position_id, signal_id, symbol, side, opened_at_ms, closed_at_ms,
            entry_price, exit_price, realized_pnl, realized_pnl_pct, raw_json
        from positions
        where position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (list(position_ids),))
            rows = [dict(r) for r in cur.fetchall()]
    out = {str(r["position_id"]): r for r in rows}
    if len(out) != len(position_ids):
        missing = sorted(position_ids - set(out))
        raise RuntimeError(
            f"position coverage {len(out)}/{len(position_ids)}; "
            f"missing sample={missing[:5]}"
        )
    return out


def _load_cache() -> dict[str, list[list[Any]]]:
    out: dict[str, list[list[Any]]] = {}
    if not POSTENTRY_CACHE.exists():
        return out
    for line in POSTENTRY_CACHE.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def _cache_has_full_horizon(
    position: dict[str, Any],
    rows: list[list[Any]],
) -> bool:
    if not rows:
        return False
    opened = int(position["opened_at_ms"])
    needed = opened + MAX_HORIZON_MIN * 60_000
    max_close = max(int(r[6]) for r in rows if len(r) >= 7)
    return max_close >= needed


def _fetch_postentry(
    position: dict[str, Any],
) -> tuple[str, list[list[Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    opened = int(position["opened_at_ms"])
    start_ms = (opened // 60_000) * 60_000
    end_ms = opened + (MAX_HORIZON_MIN + 3) * 60_000
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": str(position["symbol"]),
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 100,
        },
    )
    rows = [r for r in rows if len(r) >= 7]
    return str(position["position_id"]), rows


def ensure_postentry_cache(
    positions: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[list[Any]]]:
    cache = _load_cache()
    missing = [
        pos for pid, pos in positions.items()
        if pid not in cache or not _cache_has_full_horizon(pos, cache[pid])
    ]
    if missing:
        fetched: list[tuple[str, list[list[Any]]]] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_postentry, pos): pos
                for pos in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                pos = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                    fetched.append((pid, rows))
                except Exception as exc:
                    errors.append(f"{pos['position_id']}: {exc}")
                if i % 100 == 0:
                    time.sleep(0.2)
        if errors:
            raise RuntimeError(
                f"postentry fetch failures={len(errors)} sample={errors[:5]}"
            )

    POSTENTRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with POSTENTRY_CACHE.open("w") as fh:
        for pid in sorted(
            positions,
            key=lambda x: int(positions[x]["opened_at_ms"]),
        ):
            fh.write(json.dumps(
                {"position_id": pid, "rows": cache[pid]},
                separators=(",", ":"),
            ) + "\n")

    final = {pid: cache[pid] for pid in positions}
    incomplete = [
        pid for pid, rows in final.items()
        if not _cache_has_full_horizon(positions[pid], rows)
    ]
    if incomplete:
        raise RuntimeError(
            f"incomplete 60m coverage for {len(incomplete)} positions; "
            f"sample={incomplete[:5]}"
        )
    return final


def close_path(
    rows: list[list[Any]],
    opened_at_ms: int,
    horizon_min: int,
) -> list[tuple[int, float]]:
    end_ms = opened_at_ms + horizon_min * 60_000
    out: list[tuple[int, float]] = []
    for row in rows:
        if len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms < opened_at_ms:
            continue
        if close_ms > end_ms:
            continue
        out.append((close_ms, float(row[4])))
    out.sort()
    return out


def triple_barrier_label(
    position: dict[str, Any],
    rows: list[list[Any]],
    *,
    tp_pct: float,
    sl_pct: float,
    horizon_min: int,
) -> dict[str, Any]:
    raw = _j(position.get("raw_json"))
    side = str(position["side"]).upper()
    entry_market = float(
        raw.get("entry_market_price") or position["entry_price"]
    )
    fee_rate = float(
        raw.get("fee_rate")
        if raw.get("fee_rate") is not None
        else 0.00075
    )
    slippage_bps = float(
        raw.get("slippage_bps")
        if raw.get("slippage_bps") is not None
        else 2.0
    )
    opened = int(position["opened_at_ms"])
    path = close_path(rows, opened, horizon_min)

    tp_usdt = NOTIONAL_USDT * tp_pct / 100.0
    sl_usdt = -NOTIONAL_USDT * sl_pct / 100.0

    first_tp_ms = None
    first_sl_ms = None
    final_net = None
    best_net = -math.inf
    worst_net = math.inf
    best_at_ms = None
    worst_at_ms = None

    for ts, market in path:
        net = net_pnl_at_market(
            side=side,
            entry_market=entry_market,
            exit_market=market,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
        )
        final_net = net
        if net > best_net:
            best_net = net
            best_at_ms = ts
        if net < worst_net:
            worst_net = net
            worst_at_ms = ts
        if first_tp_ms is None and net >= tp_usdt:
            first_tp_ms = ts
        if first_sl_ms is None and net <= sl_usdt:
            first_sl_ms = ts

    if first_tp_ms is not None and (
        first_sl_ms is None or first_tp_ms < first_sl_ms
    ):
        label = "META_WIN"
        end_ms = first_tp_ms
    elif first_sl_ms is not None and (
        first_tp_ms is None or first_sl_ms < first_tp_ms
    ):
        label = "META_LOSS"
        end_ms = first_sl_ms
    else:
        label = "TIMEOUT"
        end_ms = opened + horizon_min * 60_000

    return {
        "label": label,
        "label_end_ms": end_ms,
        "first_tp_ms": first_tp_ms,
        "first_sl_ms": first_sl_ms,
        "minutes_to_label": (end_ms - opened) / 60_000.0,
        "final_net_usdt": final_net,
        "best_net_usdt": None if best_net == -math.inf else best_net,
        "worst_net_usdt": None if worst_net == math.inf else worst_net,
        "best_at_ms": best_at_ms,
        "worst_at_ms": worst_at_ms,
        "path_points": len(path),
        "entry_market_price": entry_market,
        "fee_rate": fee_rate,
        "slippage_bps": slippage_bps,
    }


def add_uniqueness_weights(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    # One-minute event-time grid, consistent with label resolution.
    minute_events: dict[int, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        start = int(row["opened_at_ms"]) // 60_000
        end = int(row["primary_label_end_ms"]) // 60_000
        for minute in range(start, end + 1):
            minute_events[minute].append(i)

    concurrency = {
        minute: len(indices)
        for minute, indices in minute_events.items()
    }
    for i, row in enumerate(rows):
        start = int(row["opened_at_ms"]) // 60_000
        end = int(row["primary_label_end_ms"]) // 60_000
        cs = [concurrency[m] for m in range(start, end + 1)]
        row["primary_avg_concurrency"] = (
            sum(cs) / len(cs) if cs else 1.0
        )
        row["primary_uniqueness_weight"] = (
            sum(1.0 / c for c in cs) / len(cs) if cs else 1.0
        )

    weights = [float(r["primary_uniqueness_weight"]) for r in rows]
    conc = [float(r["primary_avg_concurrency"]) for r in rows]
    return {
        "minute_grid_n": len(concurrency),
        "median_avg_concurrency": statistics.median(conc),
        "mean_avg_concurrency": sum(conc) / len(conc),
        "median_uniqueness_weight": statistics.median(weights),
        "mean_uniqueness_weight": sum(weights) / len(weights),
        "effective_unique_sample_sum": sum(weights),
        "max_concurrency": max(concurrency.values()) if concurrency else 0,
    }


def _cross_tab(
    rows: list[dict[str, Any]],
    group_key: str,
    label_key: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups = sorted({str(r[group_key]) for r in rows})
    for group in groups:
        subset = [r for r in rows if str(r[group_key]) == group]
        counts = Counter(str(r[label_key]) for r in subset)
        out[group] = {
            "n": len(subset),
            "counts": dict(counts),
            "rates_pct": {
                label: 100.0 * count / len(subset)
                for label, count in sorted(counts.items())
            },
        }
    return out


def _label_summary(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    out = {}
    for label in ("META_WIN", "META_LOSS", "TIMEOUT"):
        subset = [r for r in rows if r[key] == label]
        out[label] = {
            "n": len(subset),
            "share_pct": 100.0 * len(subset) / len(rows),
            "actual_positive_n": sum(
                float(r["historical_realized_pnl"]) > 0
                for r in subset
            ),
            "actual_positive_rate_pct": (
                100.0 * sum(
                    float(r["historical_realized_pnl"]) > 0
                    for r in subset
                ) / len(subset)
                if subset else None
            ),
            "historical_net_pnl": sum(
                float(r["historical_realized_pnl"]) for r in subset
            ),
            "median_minutes_to_label": (
                statistics.median(
                    float(r["primary_minutes_to_label"])
                    for r in subset
                )
                if key == "primary_meta_label" and subset
                else None
            ),
        }
    return out


def run_wd5h_stage3a() -> dict[str, Any]:
    base = load_base_rows()
    ids = {str(r["meta_position_id"]) for r in base}
    positions = load_positions(ids)
    cache = ensure_postentry_cache(positions)

    output: list[dict[str, Any]] = []
    for source in base:
        pid = str(source["meta_position_id"])
        position = positions[pid]
        record: dict[str, Any] = {
            "position_id": pid,
            "signal_id": source["meta_signal_id"],
            "symbol": source["meta_symbol"],
            "side": source["meta_original_side"],
            "opened_at_ms": int(source["meta_opened_at_ms"]),
            "historical_wd1_outcome": source["future_outcome_label"],
            "historical_thesis_class": source["label_thesis_class"],
            "historical_realized_pnl": float(source["future_realized_pnl"]),
            "historical_realized_pnl_pct": float(
                source["future_realized_pnl_pct"]
            ),
            "historical_max_mfe_pct": float(source["future_max_mfe_pct"]),
            "historical_min_mae_pct": float(source["future_min_mae_pct"]),
        }

        for config in BARRIER_CONFIGS:
            result = triple_barrier_label(
                position,
                cache[pid],
                tp_pct=float(config["tp_pct"]),
                sl_pct=float(config["sl_pct"]),
                horizon_min=int(config["horizon_min"]),
            )
            prefix = (
                "primary"
                if config["primary"]
                else config["name"].lower()
            )
            record[f"{prefix}_meta_label"] = result["label"]
            record[f"{prefix}_label_end_ms"] = result["label_end_ms"]
            record[f"{prefix}_minutes_to_label"] = result["minutes_to_label"]
            record[f"{prefix}_first_tp_ms"] = result["first_tp_ms"]
            record[f"{prefix}_first_sl_ms"] = result["first_sl_ms"]
            record[f"{prefix}_final_net_usdt"] = result["final_net_usdt"]
            record[f"{prefix}_best_net_usdt"] = result["best_net_usdt"]
            record[f"{prefix}_worst_net_usdt"] = result["worst_net_usdt"]
            record[f"{prefix}_path_points"] = result["path_points"]

        output.append(record)

    overlap = add_uniqueness_weights(output)

    OUTPUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_ROWS.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(output[0].keys())
        )
        writer.writeheader()
        writer.writerows(output)

    sensitivity = {}
    for config in BARRIER_CONFIGS:
        key = (
            "primary_meta_label"
            if config["primary"]
            else f"{config['name'].lower()}_meta_label"
        )
        sensitivity[config["name"]] = {
            "config": config,
            "label_summary": _label_summary(output, key),
            "by_wd1": _cross_tab(output, "historical_wd1_outcome", key),
            "by_thesis_class": _cross_tab(
                output, "historical_thesis_class", key
            ),
        }

    primary_summary = _label_summary(output, "primary_meta_label")
    by_wd1 = _cross_tab(
        output, "historical_wd1_outcome", "primary_meta_label"
    )
    by_thesis = _cross_tab(
        output, "historical_thesis_class", "primary_meta_label"
    )

    # Key relabeling diagnostics.
    rtf = [
        r for r in output
        if r["historical_wd1_outcome"] == "RIGHT_THEN_FAILURE"
    ]
    true_wrong = [
        r for r in output
        if r["historical_wd1_outcome"] == "TRUE_WRONG_DIRECTION"
    ]
    old_positive = [
        r for r in output
        if float(r["historical_realized_pnl"]) > 0
    ]
    old_negative = [
        r for r in output
        if float(r["historical_realized_pnl"]) <= 0
    ]

    result = {
        "version": WD5H3A_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "method": {
            "path_resolution": "1m close-confirmed",
            "entry_origin": "actual historical paper entry/open timestamp",
            "primary_config": PRIMARY_CONFIG,
            "sensitivity_configs": [
                c for c in BARRIER_CONFIGS if not c["primary"]
            ],
            "economics": {
                "notional_usdt": NOTIONAL_USDT,
                "fee_rate": "per-position raw_json fee_rate; fallback 0.00075",
                "slippage_bps": (
                    "per-position raw_json slippage_bps; fallback 2.0"
                ),
                "barriers_are_net_of_fee_slippage": True,
            },
        },
        "coverage": {
            "rows": len(output),
            "positions": len(positions),
            "postentry_cache_n": len(cache),
            "max_horizon_min": MAX_HORIZON_MIN,
            "path_points_min_primary": min(
                int(r["primary_path_points"]) for r in output
            ),
            "path_points_min_60m": min(
                int(r["sens_net_0p5_60m_path_points"])
                for r in output
            ),
        },
        "primary_label_summary": primary_summary,
        "primary_by_wd1": by_wd1,
        "primary_by_thesis_class": by_thesis,
        "key_relabeling": {
            "right_then_failure_n": len(rtf),
            "right_then_failure_to_meta_win_n": sum(
                r["primary_meta_label"] == "META_WIN" for r in rtf
            ),
            "right_then_failure_to_meta_win_pct": (
                100.0 * sum(
                    r["primary_meta_label"] == "META_WIN" for r in rtf
                ) / len(rtf)
            ),
            "true_wrong_n": len(true_wrong),
            "true_wrong_to_meta_loss_n": sum(
                r["primary_meta_label"] == "META_LOSS"
                for r in true_wrong
            ),
            "true_wrong_to_meta_loss_pct": (
                100.0 * sum(
                    r["primary_meta_label"] == "META_LOSS"
                    for r in true_wrong
                ) / len(true_wrong)
            ),
            "historical_positive_n": len(old_positive),
            "historical_positive_but_meta_loss_n": sum(
                r["primary_meta_label"] == "META_LOSS"
                for r in old_positive
            ),
            "historical_negative_n": len(old_negative),
            "historical_negative_but_meta_win_n": sum(
                r["primary_meta_label"] == "META_WIN"
                for r in old_negative
            ),
        },
        "overlap_uniqueness": overlap,
        "sensitivity": sensitivity,
        "stage_conclusion": {
            "status": "META_LABEL_RESET_COMPLETE",
            "model_training_authority": "NONE_STAGE3A_LABEL_ONLY",
            "next_stage": (
                "WD-5H Stage 3B: purged/embargoed meta-model with "
                "overlap uniqueness weighting; exclude TIMEOUT or model it "
                "explicitly without collapsing it into META_LOSS."
            ),
        },
        "outputs": {
            "rows": str(OUTPUT_ROWS),
            "json": str(OUTPUT_JSON),
            "postentry_cache": str(POSTENTRY_CACHE),
        },
    }

    OUTPUT_JSON.write_text(json.dumps(
        result, indent=2, allow_nan=False
    ))
    return result
