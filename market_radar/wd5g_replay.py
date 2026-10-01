from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import psycopg2.extras

from .binance import BinancePublicClient
from .persistence import _postgres_connect
from .wd2_anatomy import WD2_CUTOFF_MS
from .wd4_resolution import NOTIONAL_USDT, opposite_from_entry
from .wd5b_discovery import Encoder, LogisticModel
from .wd5f_conditional_reversal import (
    BENCHMARKS,
    OVERHEAT_THRESHOLD,
    _types,
    derive_market_features,
    ensure_benchmark_cache,
)
from .wd5e_multihead import load_gate_times


WD5G_VERSION = "wd5g-end-to-end-historical-replay-v1"
BASE_PATH = Path("/app/data/wd5d_opportunity_exhaustion_features.csv")
WD5F_DATASET = Path("/app/data/wd5f_conditional_reversal_features.csv")
WD5F_RESULT = Path("/app/data/wd5f_conditional_reversal_results.json")
PREENTRY_CACHE = Path("/app/data/wd5g_preentry_1m_cache.jsonl")
POSTENTRY_CACHE = Path("/app/data/wd5g_postentry_1m_cache.jsonl")
OUTPUT_ROWS = Path("/app/data/wd5g_end_to_end_replay_rows.csv")
OUTPUT_JSON = Path("/app/data/wd5g_end_to_end_replay_results.json")
HORIZON_MIN = 30


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def load_base_rows() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASE_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 rows, got {len(rows)}")
    return rows


def load_positions(position_ids: set[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side,
            w.opened_at_ms, w.closed_at_ms, w.realized_pnl,
            w.realized_pnl_pct, w.outcome_label,
            p.entry_price, p.exit_price, p.raw_json
        from wd1_trade_labels w
        join positions p on p.position_id=w.position_id
        where w.closed_at_ms <= %s
          and w.position_id = any(%s)
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(query, (WD2_CUTOFF_MS, list(position_ids)))
            rows = [dict(r) for r in cur.fetchall()]
    out = {str(r["position_id"]): r for r in rows}
    if len(out) != len(position_ids):
        raise RuntimeError(
            f"position coverage {len(out)}/{len(position_ids)}"
        )
    return out


def _cache_load(path: Path) -> dict[str, list[list[Any]]]:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def _fetch_preentry(meta: dict[str, Any]) -> tuple[str, list[list[Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    gate = int(meta["gate_checked_at_ms"])
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": str(meta["symbol"]),
            "interval": "1m",
            "startTime": gate - 40 * 60_000,
            "endTime": gate,
            "limit": 60,
        },
    )
    rows = [r for r in rows if len(r) >= 7 and int(r[6]) <= gate]
    return str(meta["position_id"]), rows


def _fetch_postentry(position: dict[str, Any]) -> tuple[str, list[list[Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    opened = int(position["opened_at_ms"])
    start_ms = (opened // 60_000) * 60_000
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": str(position["symbol"]),
            "interval": "1m",
            "startTime": start_ms,
            "endTime": opened + 32 * 60_000,
            "limit": 40,
        },
    )
    return str(position["position_id"]), rows


def _ensure_cache(
    path: Path,
    items: list[dict[str, Any]],
    fetcher,
    workers: int = 6,
) -> dict[str, list[list[Any]]]:
    cache = _cache_load(path)
    missing = [
        item for item in items
        if str(item["position_id"]) not in cache
    ]
    fetched = []
    errors = []
    if missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(fetcher, item): item
                for item in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                    fetched.append((pid, rows))
                except Exception as exc:
                    errors.append(f"{item['position_id']}: {exc}")
                if i % 100 == 0:
                    time.sleep(0.25)
        if fetched:
            with path.open("a") as fh:
                for pid, rows in fetched:
                    fh.write(json.dumps(
                        {"position_id": pid, "rows": rows},
                        separators=(",", ":"),
                    ) + "\n")
        if errors:
            raise RuntimeError(
                f"cache fetch failures={len(errors)} sample={errors[:5]}"
            )
    return cache


def fit_frozen_wd5f_model():
    rows = list(csv.DictReader(WD5F_DATASET.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(rows)
    train = rows[:3*n//5]

    result = json.loads(WD5F_RESULT.read_text())
    selected = result["selected"]
    features = list(selected["selected_features"])
    l2 = float(selected["selected_l2"])
    threshold = float(
        selected["one_sided_reverse_gate"]["selected"]["threshold"]
    )
    types = _types(rows, features)
    encoder = Encoder(features, types).fit(train)
    model = LogisticModel(
        l2=l2,
        epochs=700,
        lr=0.12,
    ).fit(
        encoder.transform(train),
        [int(r["target_wd5f_reverse"]) for r in train],
    )
    return {
        "features": features,
        "l2": l2,
        "threshold": threshold,
        "encoder": encoder,
        "model": model,
        "train_n": len(train),
    }


def reverse_bounded_pnl(
    position: dict[str, Any],
    post_rows: list[list[Any]],
) -> tuple[float, dict[str, Any]]:
    metrics = opposite_from_entry(
        position,
        post_rows,
        HORIZON_MIN,
    )
    tp = metrics.get("first_strong_at_ms")
    sl = metrics.get("first_stop_0p5_at_ms")
    if tp is not None and (sl is None or tp < sl):
        pnl = NOTIONAL_USDT * 0.005
        exit_mode = "TP_0P5"
    elif sl is not None and (tp is None or sl < tp):
        pnl = -NOTIONAL_USDT * 0.005
        exit_mode = "SL_0P5"
    else:
        pnl = float(metrics.get("final_net") or 0.0)
        exit_mode = "HORIZON_FINAL"
    return pnl, {
        "exit_mode": exit_mode,
        "path_best_net": metrics.get("best_net"),
        "path_final_net": metrics.get("final_net"),
        "tp_before_sl": bool(metrics.get("tp0p5_before_sl0p5")),
        "first_tp_ms": tp,
        "first_sl_ms": sl,
    }


def summarize_policy(rows: list[dict[str, Any]], pnl_key: str) -> dict[str, Any]:
    pnls = [float(r[pnl_key]) for r in rows]
    traded = [
        r for r in rows
        if r[f"{pnl_key}_action"] != "SKIP"
    ]
    traded_pnls = [float(r[pnl_key]) for r in traded]
    positive = sum(p > 0 for p in traded_pnls)
    negative = sum(p < 0 for p in traded_pnls)
    return {
        "all_signal_n": len(rows),
        "trade_n": len(traded),
        "skip_n": len(rows) - len(traded),
        "trade_rate_pct": 100.0 * len(traded) / len(rows),
        "net_pnl": sum(pnls),
        "avg_pnl_per_original_signal": sum(pnls) / len(rows),
        "avg_pnl_per_trade": (
            sum(traded_pnls) / len(traded) if traded else None
        ),
        "win_n": positive,
        "loss_n": negative,
        "flat_n": len(traded) - positive - negative,
        "win_rate_pct": (
            100.0 * positive / len(traded) if traded else None
        ),
        "profit_factor": (
            sum(p for p in traded_pnls if p > 0)
            / abs(sum(p for p in traded_pnls if p < 0))
            if any(p < 0 for p in traded_pnls)
            else None
        ),
        "actions": dict(Counter(
            r[f"{pnl_key}_action"] for r in rows
        )),
    }


def subgroup_summary(
    rows: list[dict[str, Any]],
    pnl_key: str,
    group_key: str,
) -> dict[str, Any]:
    groups = defaultdict(list)
    for r in rows:
        groups[str(r[group_key])].append(r)
    return {
        key: summarize_policy(group, pnl_key)
        for key, group in sorted(groups.items())
    }


def _bounded_reverse_from_row(row: dict[str, Any]) -> float:
    mode = row.get("reverse_exit_mode")
    if mode == "TP_0P5":
        return NOTIONAL_USDT * 0.005
    if mode == "SL_0P5":
        return -NOTIONAL_USDT * 0.005
    value = row.get("reverse_path_final_net")
    return float(value or 0.0)


def threshold_sensitivity(
    replay: list[dict[str, Any]],
    thresholds: list[float],
) -> list[dict[str, Any]]:
    out = []
    for threshold in thresholds:
        total = 0.0
        reverse_n = reverse_win = reverse_loss = 0
        wrong_win = wrong_skip = wrong_loss = 0
        runner_keep = runner_reverse = runner_skip = 0
        runner_pnl = 0.0

        for row in replay:
            is_hot = bool(row["overheated"])
            actual = float(row["actual_realized_pnl"])
            if not is_hot:
                action = "KEEP"
                pnl = actual
            else:
                prob = float(row["reverse_probability"])
                if prob >= threshold:
                    action = "REVERSE"
                    pnl = _bounded_reverse_from_row(row)
                    reverse_n += 1
                    reverse_win += pnl > 0
                    reverse_loss += pnl < 0
                else:
                    action = "SKIP"
                    pnl = 0.0
            total += pnl

            if row["wd1_outcome"] == "TRUE_WRONG_DIRECTION":
                if action == "SKIP":
                    wrong_skip += 1
                elif pnl > 0:
                    wrong_win += 1
                elif pnl < 0:
                    wrong_loss += 1

            if row["opportunity_tier"] in {"RUNNER", "BIG_RUNNER"}:
                runner_pnl += pnl
                if action == "KEEP":
                    runner_keep += 1
                elif action == "REVERSE":
                    runner_reverse += 1
                else:
                    runner_skip += 1

        out.append({
            "threshold": threshold,
            "net_pnl": total,
            "reverse_n": reverse_n,
            "reverse_win_rate_pct": (
                100.0 * reverse_win / reverse_n if reverse_n else None
            ),
            "reverse_net_pnl": sum(
                _bounded_reverse_from_row(r)
                for r in replay
                if r["overheated"]
                and float(r["reverse_probability"]) >= threshold
            ),
            "wrong_direction_win_n": wrong_win,
            "wrong_direction_skip_n": wrong_skip,
            "wrong_direction_loss_n": wrong_loss,
            "wrong_direction_win_or_skip_pct": (
                100.0 * (wrong_win + wrong_skip) / 849.0
            ),
            "runner_keep_n": runner_keep,
            "runner_reverse_n": runner_reverse,
            "runner_skip_n": runner_skip,
            "runner_pnl": runner_pnl,
        })
    return out


def promotion_assessment(
    baseline: dict[str, Any],
    health_only: dict[str, Any],
    primary: dict[str, Any],
    wrong: dict[str, Any],
    runner: dict[str, Any],
    winners: dict[str, Any],
    reverse: dict[str, Any],
) -> dict[str, Any]:
    requirements = {
        "primary_pnl_better_than_baseline": (
            primary["net_pnl"] > baseline["net_pnl"]
        ),
        "primary_pnl_not_worse_than_health_only": (
            primary["net_pnl"] >= health_only["net_pnl"]
        ),
        "wrong_direction_win_or_skip_ge_50pct": (
            wrong["win_or_skip_pct"] >= 50.0
        ),
        "runner_keep_ge_80pct": (
            runner["kept_original_pct"] >= 80.0
        ),
        "realized_winner_keep_ge_80pct": (
            winners["kept_original_pct"] >= 80.0
        ),
        "reverse_execution_nonnegative": (
            reverse["net_pnl"] >= 0.0
        ),
    }
    return {
        "status": (
            "END_TO_END_POLICY_CANDIDATE"
            if all(requirements.values())
            else "END_TO_END_POLICY_NOT_READY"
        ),
        "requirements": requirements,
        "production_authority": "NONE",
        "diagnosis": (
            "Health filtering improves the loss profile, but the frozen "
            "reversal gate is not portable across the full trade population. "
            "It reverses trades whose original direction was valid but whose "
            "later lifecycle failed."
        ),
    }


def run_wd5g() -> dict[str, Any]:
    base = load_base_rows()
    hot = [
        r for r in base
        if float(r["f_new_overheat_pressure"]) >= OVERHEAT_THRESHOLD
    ]
    hot_ids = {str(r["meta_position_id"]) for r in hot}

    gate_meta = load_gate_times(hot_ids)
    positions = load_positions(hot_ids)

    pre_cache = _ensure_cache(
        PREENTRY_CACHE,
        list(gate_meta.values()),
        _fetch_preentry,
    )
    post_cache = _ensure_cache(
        POSTENTRY_CACHE,
        list(positions.values()),
        _fetch_postentry,
    )

    min_gate = min(int(x["gate_checked_at_ms"]) for x in gate_meta.values())
    max_gate = max(int(x["gate_checked_at_ms"]) for x in gate_meta.values())
    benchmarks = ensure_benchmark_cache(min_gate, max_gate)

    frozen = fit_frozen_wd5f_model()
    features = frozen["features"]
    encoder = frozen["encoder"]
    model = frozen["model"]
    threshold = frozen["threshold"]

    scored_hot = {}
    for row in hot:
        pid = str(row["meta_position_id"])
        meta = gate_meta[pid]
        x = dict(row)
        market = derive_market_features(
            pre_cache[pid],
            benchmarks,
            int(meta["gate_checked_at_ms"]),
            str(row["meta_original_side"]),
        )
        x.update({k: str(v) for k, v in market.items()})
        prob = model.predict_proba(
            encoder.transform([x])
        )[0]
        reverse_pnl, reverse_meta = reverse_bounded_pnl(
            positions[pid],
            post_cache[pid],
        )
        scored_hot[pid] = {
            "reverse_probability": prob,
            "reverse_confirmed": prob >= threshold,
            "reverse_pnl": reverse_pnl,
            **reverse_meta,
        }

    replay = []
    for row in base:
        pid = str(row["meta_position_id"])
        actual = float(row["future_realized_pnl"])
        is_hot = pid in scored_hot

        # Baseline: observed historical trade.
        baseline_pnl = actual
        baseline_action = "KEEP"

        # Health-only ablation: do not enter any overheated trade.
        if is_hot:
            health_only_pnl = 0.0
            health_only_action = "SKIP"
        else:
            health_only_pnl = actual
            health_only_action = "KEEP"

        # WD5G primary policy.
        if not is_hot:
            policy_pnl = actual
            policy_action = "KEEP"
            reverse_prob = None
            reverse_meta = {}
        else:
            score = scored_hot[pid]
            reverse_prob = float(score["reverse_probability"])
            reverse_meta = score
            if score["reverse_confirmed"]:
                policy_pnl = float(score["reverse_pnl"])
                policy_action = "REVERSE"
            else:
                policy_pnl = 0.0
                policy_action = "SKIP"

        replay.append({
            "position_id": pid,
            "signal_id": row["meta_signal_id"],
            "symbol": row["meta_symbol"],
            "original_side": row["meta_original_side"],
            "opened_at_ms": int(row["meta_opened_at_ms"]),
            "wd1_outcome": row["future_outcome_label"],
            "opportunity_tier": row["label_opportunity_tier"],
            "path_style": row["label_path_style"],
            "actual_realized_pnl": actual,
            "actual_realized_pnl_pct": float(
                row["future_realized_pnl_pct"]
            ),
            "max_mfe_pct": float(row["future_max_mfe_pct"]),
            "min_mae_pct": float(row["future_min_mae_pct"]),
            "overheat_pressure": float(
                row["f_new_overheat_pressure"]
            ),
            "overheated": is_hot,
            "reverse_probability": reverse_prob,
            "reverse_threshold": threshold if is_hot else None,
            "reverse_exit_mode": reverse_meta.get("exit_mode"),
            "reverse_path_best_net": reverse_meta.get("path_best_net"),
            "reverse_path_final_net": reverse_meta.get("path_final_net"),
            "reverse_tp_before_sl": reverse_meta.get("tp_before_sl"),
            "baseline": baseline_pnl,
            "baseline_action": baseline_action,
            "health_only": health_only_pnl,
            "health_only_action": health_only_action,
            "wd5g_policy": policy_pnl,
            "wd5g_policy_action": policy_action,
        })

    OUTPUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_ROWS.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(replay[0].keys())
        )
        writer.writeheader()
        writer.writerows(replay)

    baseline = summarize_policy(replay, "baseline")
    health_only = summarize_policy(replay, "health_only")
    primary = summarize_policy(replay, "wd5g_policy")

    wrong = [
        r for r in replay
        if r["wd1_outcome"] == "TRUE_WRONG_DIRECTION"
    ]
    runners = [
        r for r in replay
        if r["opportunity_tier"] in {"RUNNER", "BIG_RUNNER"}
    ]
    realized_winners = [
        r for r in replay
        if float(r["actual_realized_pnl"]) > 0
    ]

    wrong_actions = Counter(
        r["wd5g_policy_action"] for r in wrong
    )
    wrong_policy_win = sum(
        float(r["wd5g_policy"]) > 0 for r in wrong
    )
    wrong_policy_loss = sum(
        float(r["wd5g_policy"]) < 0 for r in wrong
    )
    wrong_policy_skip = sum(
        r["wd5g_policy_action"] == "SKIP" for r in wrong
    )

    runner_preserved = sum(
        r["wd5g_policy_action"] == "KEEP"
        for r in runners
    )
    winner_preserved = sum(
        r["wd5g_policy_action"] == "KEEP"
        for r in realized_winners
    )

    reverse_rows = [
        r for r in replay
        if r["wd5g_policy_action"] == "REVERSE"
    ]
    reverse_win = sum(float(r["wd5g_policy"]) > 0 for r in reverse_rows)
    reverse_loss = sum(float(r["wd5g_policy"]) < 0 for r in reverse_rows)

    sensitivity = threshold_sensitivity(
        replay,
        [
            threshold,
            0.55,
            0.59,
            0.65,
            0.67,
            0.72,
        ],
    )

    assessment = promotion_assessment(
        baseline,
        health_only,
        primary,
        {
            "win_or_skip_pct": 100.0 * (
                wrong_policy_win + wrong_policy_skip
            ) / len(wrong),
        },
        {
            "kept_original_pct": (
                100.0 * runner_preserved / len(runners)
            ),
        },
        {
            "kept_original_pct": (
                100.0 * winner_preserved / len(realized_winners)
            ),
        },
        {
            "net_pnl": sum(
                float(r["wd5g_policy"]) for r in reverse_rows
            ),
        },
    )

    result = {
        "version": WD5G_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "policy_definition": {
            "health_gate": (
                f"OVERHEATED when f_new_overheat_pressure >= "
                f"{OVERHEAT_THRESHOLD}"
            ),
            "healthy_action": "KEEP original historical trade",
            "overheated_action": (
                "REVERSE only when frozen WD5F market-relative probability "
                f">= {threshold}; otherwise SKIP"
            ),
            "reverse_execution": (
                "Opposite from original entry; 30m 1m-close simulation; "
                "net TP +0.5% / SL -0.5%; if neither hit, close at horizon"
            ),
            "notional_usdt": NOTIONAL_USDT,
        },
        "coverage": {
            "all_trades": len(replay),
            "overheated_n": len(hot),
            "overheated_pct": 100.0 * len(hot) / len(replay),
            "preentry_cache_n": len(pre_cache),
            "postentry_cache_n": len(post_cache),
            "frozen_wd5f_train_n": frozen["train_n"],
            "frozen_wd5f_features": features,
        },
        "baseline": baseline,
        "health_only_ablation": health_only,
        "wd5g_primary": primary,
        "deltas_vs_baseline": {
            "net_pnl": primary["net_pnl"] - baseline["net_pnl"],
            "trade_n": primary["trade_n"] - baseline["trade_n"],
            "win_rate_pp": (
                primary["win_rate_pct"] - baseline["win_rate_pct"]
            ),
        },
        "incremental_reverse_vs_health_only": {
            "net_pnl": primary["net_pnl"] - health_only["net_pnl"],
            "trade_n": primary["trade_n"] - health_only["trade_n"],
        },
        "wrong_direction": {
            "n": len(wrong),
            "actual_net_pnl": sum(
                float(r["actual_realized_pnl"]) for r in wrong
            ),
            "policy_net_pnl": sum(
                float(r["wd5g_policy"]) for r in wrong
            ),
            "actions": dict(wrong_actions),
            "policy_win_n": wrong_policy_win,
            "policy_skip_n": wrong_policy_skip,
            "policy_loss_n": wrong_policy_loss,
            "win_or_skip_n": wrong_policy_win + wrong_policy_skip,
            "win_or_skip_pct": 100.0 * (
                wrong_policy_win + wrong_policy_skip
            ) / len(wrong),
            "remaining_loss_pct": (
                100.0 * wrong_policy_loss / len(wrong)
            ),
        },
        "runner_preservation": {
            "runner_or_big_n": len(runners),
            "kept_original_n": runner_preserved,
            "kept_original_pct": (
                100.0 * runner_preserved / len(runners)
            ),
            "actions": dict(Counter(
                r["wd5g_policy_action"] for r in runners
            )),
            "actual_net_pnl": sum(
                float(r["actual_realized_pnl"]) for r in runners
            ),
            "policy_net_pnl": sum(
                float(r["wd5g_policy"]) for r in runners
            ),
        },
        "realized_winner_preservation": {
            "n": len(realized_winners),
            "kept_original_n": winner_preserved,
            "kept_original_pct": (
                100.0 * winner_preserved / len(realized_winners)
            ),
            "actions": dict(Counter(
                r["wd5g_policy_action"]
                for r in realized_winners
            )),
            "actual_net_pnl": sum(
                float(r["actual_realized_pnl"])
                for r in realized_winners
            ),
            "policy_net_pnl": sum(
                float(r["wd5g_policy"])
                for r in realized_winners
            ),
        },
        "posthoc_threshold_sensitivity": sensitivity,
        "promotion_assessment": assessment,
        "reverse_execution": {
            "reverse_n": len(reverse_rows),
            "win_n": reverse_win,
            "loss_n": reverse_loss,
            "flat_n": len(reverse_rows) - reverse_win - reverse_loss,
            "win_rate_pct": (
                100.0 * reverse_win / len(reverse_rows)
                if reverse_rows else None
            ),
            "net_pnl": sum(
                float(r["wd5g_policy"]) for r in reverse_rows
            ),
            "exit_modes": dict(Counter(
                r["reverse_exit_mode"] for r in reverse_rows
            )),
            "by_original_outcome": dict(Counter(
                r["wd1_outcome"] for r in reverse_rows
            )),
        },
        "subgroups": {
            "baseline_by_wd1": subgroup_summary(
                replay, "baseline", "wd1_outcome"
            ),
            "policy_by_wd1": subgroup_summary(
                replay, "wd5g_policy", "wd1_outcome"
            ),
            "policy_by_opportunity": subgroup_summary(
                replay, "wd5g_policy", "opportunity_tier"
            ),
        },
        "caveats": [
            (
                "The WD5F one-sided objective was formalized after the "
                "initial symmetric WD5F holdout inspection. WD5G is therefore "
                "a research replay, not a pristine promotion test."
            ),
            (
                "Reverse execution uses a standardized 30-minute 1m-close "
                "TP/SL counterfactual, not the full live Stage12 lifecycle."
            ),
            (
                "The health gate is the frozen deterministic WD5D overheat "
                "threshold, not a newly trained all-trade health classifier."
            ),
        ],
        "outputs": {
            "rows": str(OUTPUT_ROWS),
            "json": str(OUTPUT_JSON),
            "preentry_cache": str(PREENTRY_CACHE),
            "postentry_cache": str(POSTENTRY_CACHE),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
