from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.binance import BinancePublicClient
from market_radar.persistence import _postgres_connect
from .wd5h_stage3a import (
    NOTIONAL_USDT,
    _entry_fill,
    _exit_fill,
    _gross,
    net_pnl_at_market,
)

WD5H4D_VERSION = "wd5h-stage4d-delayed-entry-economic-replay-v1"

PREDICTIONS_PATH = Path("/app/data/wd5h4c_temporal_gate_predictions.csv")
TEMPORAL_PATH = Path("/app/data/wd5h4a_temporal_features.csv")
STATIC_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
POSTENTRY_CACHE = Path("/app/data/wd5h3a_postentry_1m_cache.jsonl")
ENTRY_CACHE = Path("/app/data/wd5h4d_delayed_entry_agg_cache.jsonl")
OUTPUT_CSV = Path("/app/data/wd5h4d_delayed_entry_replay.csv")
OUTPUT_JSON = Path("/app/data/wd5h4d_delayed_entry_results.json")

FROZEN_HORIZON_MIN = 3
FROZEN_THRESHOLD = 0.6028066188778062
TP_PCT = 0.50
SL_PCT = 0.50
PRIMARY_HORIZON_MIN = 30
RUNNER_HORIZON_MIN = 60


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def load_selected_predictions() -> list[dict[str, Any]]:
    rows = []
    for r in csv.DictReader(PREDICTIONS_PATH.open()):
        if str(r["formal_selected_horizon"]).lower() != "true":
            continue
        if str(r["take"]).lower() != "true":
            continue
        if int(r["horizon_min"]) != FROZEN_HORIZON_MIN:
            raise RuntimeError("selected prediction horizon drift")
        threshold = _f(r.get("formal_threshold"))
        if threshold is None or abs(threshold - FROZEN_THRESHOLD) > 1e-12:
            raise RuntimeError("selected prediction threshold drift")
        rows.append(r)
    rows.sort(key=lambda r: (r["split"], int(r["gate_checked_at_ms"])))
    if len(rows) != 62:
        raise RuntimeError(f"expected 62 frozen TAKE rows, got {len(rows)}")
    return rows


def load_temporal() -> dict[str, dict[str, Any]]:
    return {
        r["position_id"]: r
        for r in csv.DictReader(TEMPORAL_PATH.open())
    }


def load_static() -> dict[str, dict[str, Any]]:
    return {
        r["meta_position_id"]: r
        for r in csv.DictReader(STATIC_PATH.open())
    }


def load_postentry_cache() -> dict[str, list[list[Any]]]:
    out = {}
    for line in POSTENTRY_CACHE.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj["rows"]
    return out


def load_positions(position_ids: set[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            position_id, symbol, side, opened_at_ms, entry_price,
            realized_pnl, realized_pnl_pct, raw_json
        from positions
        where position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (list(position_ids),))
            rows = [dict(r) for r in cur.fetchall()]
    out = {str(r["position_id"]): r for r in rows}
    if len(out) != len(position_ids):
        raise RuntimeError(
            f"position coverage {len(out)}/{len(position_ids)}"
        )
    return out


def _load_entry_cache() -> dict[str, dict[str, Any]]:
    out = {}
    if not ENTRY_CACHE.exists():
        return out
    for line in ENTRY_CACHE.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj
    return out


def _fetch_first_trade(
    pred: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    pid = pred["position_id"]
    symbol = pred["symbol"]
    target_ms = int(pred["gate_checked_at_ms"]) + FROZEN_HORIZON_MIN * 60_000
    client = BinancePublicClient(timeout=8.0, retries=3)

    windows = (5_000, 60_000, 300_000)
    trades = []
    for width in windows:
        trades = client.get(
            "/fapi/v1/aggTrades",
            {
                "symbol": symbol,
                "startTime": target_ms,
                "endTime": target_ms + width,
                "limit": 1000,
            },
        )
        trades = [
            x for x in trades
            if int(x.get("T", -1)) >= target_ms
        ]
        if trades:
            break
    if not trades:
        raise RuntimeError(f"no delayed aggTrade for {pid}")
    trade = min(trades, key=lambda x: int(x["T"]))
    return pid, {
        "position_id": pid,
        "symbol": symbol,
        "target_ms": target_ms,
        "trade_ts_ms": int(trade["T"]),
        "market_price": float(trade["p"]),
        "agg_trade_id": int(trade["a"]),
    }


def ensure_entry_cache(
    selected: list[dict[str, Any]],
    workers: int = 6,
) -> dict[str, dict[str, Any]]:
    cache = _load_entry_cache()
    missing = [
        r for r in selected
        if r["position_id"] not in cache
        or int(cache[r["position_id"]].get("target_ms", -1))
        != int(r["gate_checked_at_ms"]) + FROZEN_HORIZON_MIN * 60_000
    ]
    if missing:
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_first_trade, r): r
                for r in missing
            }
            for future in as_completed(futures):
                r = futures[future]
                try:
                    pid, item = future.result()
                    cache[pid] = item
                except Exception as exc:
                    errors.append(f"{r['position_id']}: {exc}")
        if errors:
            raise RuntimeError(
                f"delayed-entry fetch failures={len(errors)} sample={errors[:5]}"
            )
    with ENTRY_CACHE.open("w") as fh:
        for r in selected:
            fh.write(json.dumps(
                cache[r["position_id"]],
                separators=(",", ":"),
            ) + "\n")
    return {r["position_id"]: cache[r["position_id"]] for r in selected}


def close_path(
    rows: list[list[Any]],
    entry_ts_ms: int,
    horizon_min: int,
) -> list[tuple[int, float]]:
    end_ms = entry_ts_ms + horizon_min * 60_000
    out = []
    for row in rows:
        if len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms < entry_ts_ms:
            continue
        if close_ms > end_ms:
            continue
        out.append((close_ms, float(row[4])))
    out.sort()
    return out


def replay_from_market_entry(
    *,
    side: str,
    entry_market: float,
    entry_ts_ms: int,
    rows: list[list[Any]],
    fee_rate: float,
    slippage_bps: float,
    horizon_min: int,
) -> dict[str, Any]:
    path = close_path(rows, entry_ts_ms, horizon_min)
    if not path:
        raise RuntimeError("empty post-delayed-entry close path")

    tp_usdt = NOTIONAL_USDT * TP_PCT / 100.0
    sl_usdt = -NOTIONAL_USDT * SL_PCT / 100.0

    first_tp = None
    first_sl = None
    pnls = []
    for ts, market in path:
        net = net_pnl_at_market(
            side=side,
            entry_market=entry_market,
            exit_market=market,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
        )
        pnls.append((ts, market, net))
        if first_tp is None and net >= tp_usdt:
            first_tp = (ts, market, net)
        if first_sl is None and net <= sl_usdt:
            first_sl = (ts, market, net)

    if first_tp is not None and (
        first_sl is None or first_tp[0] < first_sl[0]
    ):
        label = "META_WIN"
        exit_ts, exit_market, exit_net = first_tp
    elif first_sl is not None and (
        first_tp is None or first_sl[0] < first_tp[0]
    ):
        label = "META_LOSS"
        exit_ts, exit_market, exit_net = first_sl
    else:
        label = "TIMEOUT"
        exit_ts, exit_market, exit_net = pnls[-1]

    best = max(pnls, key=lambda x: x[2])
    worst = min(pnls, key=lambda x: x[2])

    return {
        "label": label,
        "exit_ts_ms": exit_ts,
        "exit_market_price": exit_market,
        "actual_exit_net_usdt": exit_net,
        "minutes_to_exit": (exit_ts - entry_ts_ms) / 60_000.0,
        "best_net_usdt": best[2],
        "worst_net_usdt": worst[2],
        "final_net_usdt": pnls[-1][2],
        "path_points": len(path),
    }


def close_side_return_pct(
    side: str,
    entry_market: float,
    exit_market: float,
) -> float:
    if side == "LONG":
        return (exit_market / entry_market - 1.0) * 100.0
    return (entry_market / exit_market - 1.0) * 100.0


def close_runner_mfe_pct(
    *,
    side: str,
    entry_market: float,
    entry_ts_ms: int,
    rows: list[list[Any]],
    horizon_min: int,
) -> float:
    path = close_path(rows, entry_ts_ms, horizon_min)
    vals = [
        close_side_return_pct(side, entry_market, market)
        for _, market in path
    ]
    return max(vals) if vals else float("nan")


def standardized_net(
    label: str,
    timeout_net_usdt: float,
) -> float:
    if label == "META_WIN":
        return NOTIONAL_USDT * TP_PCT / 100.0
    if label == "META_LOSS":
        return -NOTIONAL_USDT * SL_PCT / 100.0
    return timeout_net_usdt


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    c = Counter(r["delayed_label"] for r in rows)
    pnl = [float(r["delayed_actual_exit_net_usdt"]) for r in rows]
    std = [float(r["delayed_standardized_net_usdt"]) for r in rows]
    chase = [float(r["entry_degradation_side_pct"]) for r in rows]
    waits = [float(r["agg_entry_wait_ms"]) for r in rows]
    return {
        "n": len(rows),
        "delayed_labels": dict(c),
        "resolved_precision_pct": (
            100.0 * c["META_WIN"] / (c["META_WIN"] + c["META_LOSS"])
            if c["META_WIN"] + c["META_LOSS"] else None
        ),
        "all_take_win_rate_pct": 100.0 * c["META_WIN"] / len(rows),
        "timeout_rate_pct": 100.0 * c["TIMEOUT"] / len(rows),
        "actual_exit_net_usdt": sum(pnl),
        "actual_exit_avg_usdt": statistics.mean(pnl),
        "standardized_net_usdt": sum(std),
        "standardized_avg_usdt": statistics.mean(std),
        "positive_actual_exit_n": sum(x > 0 for x in pnl),
        "positive_actual_exit_rate_pct": (
            100.0 * sum(x > 0 for x in pnl) / len(pnl)
        ),
        "entry_degradation_side_pct_median": statistics.median(chase),
        "entry_degradation_side_pct_mean": statistics.mean(chase),
        "entry_degradation_side_pct_p90": sorted(chase)[
            int(0.90 * (len(chase) - 1))
        ],
        "agg_entry_wait_ms_median": statistics.median(waits),
        "agg_entry_wait_ms_p90": sorted(waits)[
            int(0.90 * (len(waits) - 1))
        ],
    }


def transition_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = defaultdict(Counter)
    for r in rows:
        out[r["original_meta_label"]][r["delayed_label"]] += 1
    return {
        k: dict(v)
        for k, v in sorted(out.items())
    }


def early_resolution_accounting(
    temporal_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    # 4C operates on the final 40% (validation + historical test).
    n = len(temporal_rows)
    p60 = 3 * n // 5
    pool = temporal_rows[p60:]
    c = Counter()
    for r in pool:
        label = r["primary_meta_label"]
        if label not in {"META_WIN", "META_LOSS"}:
            continue
        target = int(r["t3_target_ms"])
        end = int(r["primary_label_end_ms"])
        if end <= target:
            c[f"early_{label}"] += 1
        else:
            c[f"survivor_{label}"] += 1
    return {
        "population_n": len(pool),
        "early_meta_win_n": c["early_META_WIN"],
        "early_meta_loss_n": c["early_META_LOSS"],
        "survivor_meta_win_n": c["survivor_META_WIN"],
        "survivor_meta_loss_n": c["survivor_META_LOSS"],
        "early_loss_to_win_ratio": (
            c["early_META_LOSS"] / c["early_META_WIN"]
            if c["early_META_WIN"] else None
        ),
    }




def zero_cost_sensitivity(
    rows: list[dict[str, Any]],
    post: dict[str, list[list[Any]]],
) -> dict[str, Any]:
    replayed = []
    for r in rows:
        z = replay_from_market_entry(
            side=r["side"],
            entry_market=float(r["delayed_entry_market_price"]),
            entry_ts_ms=int(r["delayed_entry_ts_ms"]),
            rows=post[r["position_id"]],
            fee_rate=0.0,
            slippage_bps=0.0,
            horizon_min=PRIMARY_HORIZON_MIN,
        )
        replayed.append({
            **r,
            "delayed_label": z["label"],
            "delayed_actual_exit_net_usdt": z["actual_exit_net_usdt"],
            "delayed_standardized_net_usdt": standardized_net(
                z["label"], z["final_net_usdt"]
            ),
        })
    return {
        "overall": summarize(replayed),
        "validation": summarize(
            [r for r in replayed if r["split"] == "validation"]
        ),
        "test": summarize(
            [r for r in replayed if r["split"] == "test"]
        ),
    }

def run_wd5h_stage4d() -> dict[str, Any]:
    selected = load_selected_predictions()
    temporal = load_temporal()
    static = load_static()
    post = load_postentry_cache()
    ids = {r["position_id"] for r in selected}
    positions = load_positions(ids)
    entries = ensure_entry_cache(selected)

    out = []
    for pred in selected:
        pid = pred["position_id"]
        pos = positions[pid]
        raw = _j(pos["raw_json"])
        side = str(pos["side"]).upper()
        delayed = entries[pid]
        entry_market = float(delayed["market_price"])
        entry_ts = int(delayed["trade_ts_ms"])
        target_ms = int(delayed["target_ms"])

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
        original_market = float(
            raw.get("entry_market_price") or pos["entry_price"]
        )
        sign = 1.0 if side == "LONG" else -1.0
        degradation = sign * (
            entry_market / original_market - 1.0
        ) * 100.0

        replay30 = replay_from_market_entry(
            side=side,
            entry_market=entry_market,
            entry_ts_ms=entry_ts,
            rows=post[pid],
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
            horizon_min=PRIMARY_HORIZON_MIN,
        )
        delayed_mfe60 = close_runner_mfe_pct(
            side=side,
            entry_market=entry_market,
            entry_ts_ms=entry_ts,
            rows=post[pid],
            horizon_min=RUNNER_HORIZON_MIN,
        )

        orig_entry_ts = int(pos["opened_at_ms"])
        orig_mfe60 = close_runner_mfe_pct(
            side=side,
            entry_market=original_market,
            entry_ts_ms=orig_entry_ts,
            rows=post[pid],
            horizon_min=RUNNER_HORIZON_MIN,
        )

        record = {
            "split": pred["split"],
            "position_id": pid,
            "symbol": pred["symbol"],
            "side": side,
            "score_meta_win": float(pred["score_meta_win"]),
            "gate_checked_at_ms": int(pred["gate_checked_at_ms"]),
            "t3_target_ms": target_ms,
            "delayed_entry_ts_ms": entry_ts,
            "agg_entry_wait_ms": entry_ts - target_ms,
            "original_entry_market_price": original_market,
            "delayed_entry_market_price": entry_market,
            "entry_degradation_side_pct": degradation,
            "fee_rate": fee_rate,
            "slippage_bps": slippage_bps,
            "original_meta_label": pred["primary_meta_label"],
            "delayed_label": replay30["label"],
            "delayed_exit_ts_ms": replay30["exit_ts_ms"],
            "delayed_minutes_to_exit": replay30["minutes_to_exit"],
            "delayed_actual_exit_net_usdt": replay30["actual_exit_net_usdt"],
            "delayed_standardized_net_usdt": standardized_net(
                replay30["label"],
                replay30["final_net_usdt"],
            ),
            "delayed_best_net_usdt_30m": replay30["best_net_usdt"],
            "delayed_worst_net_usdt_30m": replay30["worst_net_usdt"],
            "delayed_final_net_usdt_30m": replay30["final_net_usdt"],
            "delayed_path_points_30m": replay30["path_points"],
            "original_close_mfe_pct_60m": orig_mfe60,
            "delayed_close_mfe_pct_60m": delayed_mfe60,
            "original_future_max_mfe_pct": float(
                static[pid]["future_max_mfe_pct"]
            ),
        }
        out.append(record)

    out.sort(key=lambda r: (r["split"], r["gate_checked_at_ms"]))

    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    by_split = {
        split: summarize([r for r in out if r["split"] == split])
        for split in ("validation", "test")
    }
    overall = summarize(out)

    original_counts = Counter(r["original_meta_label"] for r in out)
    original_std = sum(
        standardized_net(
            r["original_meta_label"],
            float(temporal[r["position_id"]][
                "t3_confirm_side_return_pct"
            ]) * 0.0,  # timeout original standardized economic is not reused.
        )
        for r in out
        if r["original_meta_label"] in {"META_WIN", "META_LOSS"}
    )
    # Compare resolved-only barrier-unit economics apples-to-apples.
    delayed_resolved_std = sum(
        float(r["delayed_standardized_net_usdt"])
        for r in out
        if r["delayed_label"] in {"META_WIN", "META_LOSS"}
    )

    runner = {}
    for threshold in (1.0, 2.0):
        orig = [
            r for r in out
            if float(r["original_close_mfe_pct_60m"]) >= threshold
        ]
        retained = [
            r for r in orig
            if float(r["delayed_close_mfe_pct_60m"]) >= threshold
        ]
        runner[str(threshold)] = {
            "original_runner_n": len(orig),
            "retained_after_delay_n": len(retained),
            "retention_pct": (
                100.0 * len(retained) / len(orig) if orig else None
            ),
        }

    temporal_rows = list(temporal.values())
    temporal_rows.sort(key=lambda r: int(r["gate_checked_at_ms"]))

    original_win_chase = [
        float(r["entry_degradation_side_pct"])
        for r in out
        if r["original_meta_label"] == "META_WIN"
    ]
    all_chase = [
        float(r["entry_degradation_side_pct"])
        for r in out
    ]
    zero_cost = zero_cost_sensitivity(out, post)

    result = {
        "version": WD5H4D_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "frozen_gate": {
            "horizon_min": FROZEN_HORIZON_MIN,
            "threshold": FROZEN_THRESHOLD,
            "selected_n": len(out),
            "validation_n": sum(r["split"] == "validation" for r in out),
            "test_n": sum(r["split"] == "test" for r in out),
        },
        "method": {
            "delayed_market_entry": (
                "first Binance futures aggTrade timestamp >= exact T0+3m"
            ),
            "entry_execution": (
                "historical market price plus per-position slippage; "
                "historical fee_rate applied"
            ),
            "primary_replay": (
                "net +0.5% / -0.5% / 30m using 1m close-confirmed path "
                "starting after delayed entry"
            ),
            "runner_replay": (
                "60m close-based MFE from original and delayed entry"
            ),
            "gate_retuning": False,
        },
        "entry_execution_quality": {
            "agg_trade_coverage_n": len(entries),
            "agg_trade_coverage_pct": 100.0 * len(entries) / len(out),
            "wait_ms_median": statistics.median(
                r["agg_entry_wait_ms"] for r in out
            ),
            "wait_ms_p90": sorted(
                r["agg_entry_wait_ms"] for r in out
            )[int(0.90 * (len(out) - 1))],
            "wait_ms_max": max(r["agg_entry_wait_ms"] for r in out),
        },
        "original_selected_labels": dict(original_counts),
        "delayed_results_overall": overall,
        "delayed_results_by_split": by_split,
        "label_transition": transition_matrix(out),
        "confirmation_chase_diagnostics": {
            "all_selected_median_side_move_pct": statistics.median(all_chase),
            "all_selected_median_fraction_of_original_0p5_barrier_pct": (
                100.0 * statistics.median(all_chase) / TP_PCT
            ),
            "original_meta_win_median_side_move_pct": (
                statistics.median(original_win_chase)
            ),
            "original_meta_win_median_fraction_of_original_0p5_barrier_pct": (
                100.0 * statistics.median(original_win_chase) / TP_PCT
            ),
        },
        "zero_cost_sensitivity": zero_cost,
        "resolved_barrier_unit_comparison": {
            "original_resolved_standardized_net_usdt": original_std,
            "delayed_resolved_standardized_net_usdt": delayed_resolved_std,
        },
        "runner_retention_close_based_60m": runner,
        "early_resolution_opportunity_accounting_final40": (
            early_resolution_accounting(temporal_rows)
        ),
        "stage_conclusion": {
            "status": None,
            "production_authority": "NONE",
            "next_stage": None,
        },
        "outputs": {
            "csv": str(OUTPUT_CSV),
            "json": str(OUTPUT_JSON),
            "entry_cache": str(ENTRY_CACHE),
        },
    }

    test = by_split["test"]
    # Economic pass is deliberately stricter than classification:
    # delayed test should remain majority-WIN and positive under both
    # actual close exits and standardized barrier accounting.
    if (
        test["n"] >= 10
        and test["all_take_win_rate_pct"] >= 50.0
        and test["resolved_precision_pct"] >= 60.0
        and test["actual_exit_net_usdt"] > 0
        and test["standardized_net_usdt"] > 0
    ):
        status = "DELAYED_ENTRY_ECONOMICS_PROMISING"
        next_stage = "WD-5H Stage 4E — Fresh Prospective Shadow Validation"
    else:
        status = "DELAYED_ENTRY_ECONOMICS_NOT_READY"
        next_stage = "Reassess temporal confirmation economics before shadow"
    result["stage_conclusion"]["status"] = status
    result["stage_conclusion"]["next_stage"] = next_stage

    OUTPUT_JSON.write_text(json.dumps(
        result, indent=2, allow_nan=False
    ))
    return result
