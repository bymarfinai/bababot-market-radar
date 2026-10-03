# ARCHIVED TRACK: LOW_TAIL_15S — CLOSED/REJECTED. DO NOT PROMOTE OR RETUNE IN ACTIVE PATH.\nfrom __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from typing import Any, Callable

from market_radar.persistence import _postgres_connect
from research.profit_protection_v3.archive.low_tail_15s.stage_a_low_tail_anatomy import (
    DEFAULT_ARM_PCT,
    DEFAULT_CUTOFF_MS,
    DEFAULT_START_MS,
    _load_v2_rows,
    build_low_tail_anatomy,
    median,
    pct,
    quantile,
)

SLIPPAGE_BPS = 2.0
FIXED_CHECKPOINT_SECONDS = (30, 60, 120)


def _sigmoid(value: float) -> float:
    clipped = max(-40.0, min(40.0, float(value)))
    return 1.0 / (1.0 + math.exp(-clipped))


def _standardize(
    train_x: list[list[float]],
    test_x: list[list[float]],
) -> tuple[list[list[float]], list[list[float]]]:
    width = len(train_x[0])
    means: list[float] = []
    stds: list[float] = []
    for column in range(width):
        values = [float(row[column]) for row in train_x]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        means.append(mean)
        stds.append(math.sqrt(variance) or 1.0)
    return (
        [
            [
                (float(row[column]) - means[column]) / stds[column]
                for column in range(width)
            ]
            for row in train_x
        ],
        [
            [
                (float(row[column]) - means[column]) / stds[column]
                for column in range(width)
            ]
            for row in test_x
        ],
    )


def _fit_logistic(
    features: list[list[float]],
    labels: list[int],
    *,
    learning_rate: float = 0.03,
    epochs: int = 900,
    l2: float = 0.02,
) -> list[float]:
    weights = [0.0] * (len(features[0]) + 1)
    count = len(features)
    for _ in range(int(epochs)):
        gradient = [0.0] * len(weights)
        for row, label in zip(features, labels):
            score = weights[0] + sum(
                weights[index + 1] * float(value)
                for index, value in enumerate(row)
            )
            error = _sigmoid(score) - int(label)
            gradient[0] += error
            for index, value in enumerate(row):
                gradient[index + 1] += error * float(value)
        for index in range(len(weights)):
            regularization = 0.0 if index == 0 else float(l2) * weights[index]
            weights[index] -= float(learning_rate) * (
                gradient[index] / count + regularization
            )
    return weights


def _model_scores(
    features: list[list[float]],
    weights: list[float],
) -> list[float]:
    return [
        _sigmoid(
            weights[0]
            + sum(
                weights[index + 1] * float(value)
                for index, value in enumerate(row)
            )
        )
        for row in features
    ]


def _auc(labels: list[int], scores: list[float]) -> float:
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    ranks = [0.0] * len(scores)
    index = 0
    while index < len(order):
        end = index
        while (
            end + 1 < len(order)
            and scores[order[end + 1]] == scores[order[index]]
        ):
            end += 1
        average_rank = ((index + 1) + (end + 1)) / 2.0
        for offset in range(index, end + 1):
            ranks[order[offset]] = average_rank
        index = end + 1
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return 0.0
    positive_rank_sum = sum(
        ranks[index]
        for index, label in enumerate(labels)
        if int(label) == 1
    )
    return (
        positive_rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)


def _threshold_for_fpr(
    labels: list[int],
    scores: list[float],
    *,
    max_fpr: float,
) -> float:
    negatives = len(labels) - sum(labels)
    positives = sum(labels)
    best_threshold = 1.1
    best_recall = -1.0
    for threshold in sorted(set(scores), reverse=True):
        tp = sum(
            label == 1 and score >= threshold
            for label, score in zip(labels, scores)
        )
        fp = sum(
            label == 0 and score >= threshold
            for label, score in zip(labels, scores)
        )
        fpr = fp / negatives if negatives else 0.0
        recall = tp / positives if positives else 0.0
        if fpr <= float(max_fpr) and recall >= best_recall:
            best_threshold = float(threshold)
            best_recall = recall
    return best_threshold


def _classification_metrics(
    labels: list[int],
    scores: list[float],
    threshold: float,
) -> dict[str, Any]:
    selected = [
        index
        for index, score in enumerate(scores)
        if float(score) >= float(threshold)
    ]
    positives = sum(labels)
    negatives = len(labels) - positives
    tp = sum(labels[index] == 1 for index in selected)
    fp = len(selected) - tp
    return {
        "fired": len(selected),
        "precision_pct": pct(tp, len(selected)),
        "recall_low_tail_pct": pct(tp, positives),
        "false_positive_good_pct": pct(fp, negatives),
    }


def _fit_holdout(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    feature_key: str,
    max_fpr: float,
) -> dict[str, Any]:
    if (
        len(train_rows) < 20
        or len(test_rows) < 10
        or len({int(row["label"]) for row in train_rows}) < 2
        or len({int(row["label"]) for row in test_rows}) < 2
    ):
        return {
            "status": "INSUFFICIENT_CLASS_BALANCE",
            "train_n": len(train_rows),
            "test_n": len(test_rows),
        }
    train_x = [list(row[feature_key]) for row in train_rows]
    test_x = [list(row[feature_key]) for row in test_rows]
    train_y = [int(row["label"]) for row in train_rows]
    test_y = [int(row["label"]) for row in test_rows]
    train_z, test_z = _standardize(train_x, test_x)
    weights = _fit_logistic(train_z, train_y)
    train_scores = _model_scores(train_z, weights)
    test_scores = _model_scores(test_z, weights)
    threshold = _threshold_for_fpr(
        train_y,
        train_scores,
        max_fpr=max_fpr,
    )
    return {
        "status": "COMPLETE",
        "feature_set": feature_key,
        "max_train_fpr": float(max_fpr),
        "train_n": len(train_rows),
        "train_low_tail": sum(train_y),
        "test_n": len(test_rows),
        "test_low_tail": sum(test_y),
        "train_auc": _auc(train_y, train_scores),
        "test_auc": _auc(test_y, test_scores),
        "threshold": threshold,
        "train_metrics": _classification_metrics(
            train_y,
            train_scores,
            threshold,
        ),
        "test_metrics": _classification_metrics(
            test_y,
            test_scores,
            threshold,
        ),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(result):
        return float(default)
    return result


def _latest_range_pct(snapshot: dict[str, Any]) -> float:
    high = _safe_float(snapshot.get("latest_1m_high"))
    low = _safe_float(snapshot.get("latest_1m_low"))
    open_price = _safe_float(snapshot.get("latest_1m_open"))
    if min(high, low, open_price) <= 0.0:
        return 0.0
    return 100.0 * max(0.0, high - low) / open_price


def _features_at_index(
    *,
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    row = rows[index]
    snapshot = row.get("snapshot") or {}
    side = str(trade["side"]).upper()
    current = float(row["current_pnl_pct"])
    current_mfe = max(0.0, float(row["mfe_pct"]))
    running_peak = max(
        float(item["current_pnl_pct"])
        for item in rows[: index + 1]
    )
    previous = rows[index - 1] if index > 0 else None
    previous_pnl = current if previous is None else float(previous["current_pnl_pct"])
    previous_mfe = current_mfe if previous is None else float(previous["mfe_pct"])
    age_seconds = max(
        0.0,
        (int(row["evaluated_at_ms"]) - int(trade["opened_at_ms"])) / 1000.0,
    )
    taker_buy = _safe_float(snapshot.get("taker_buy_share_1m"), 0.5)
    aligned_taker = taker_buy if side == "LONG" else 1.0 - taker_buy
    oi = _safe_float(snapshot.get("fresh_oi_change_pct"), 0.0)
    drawdown = (
        max(0.0, (running_peak - current) / running_peak)
        if running_peak > 0.0
        else 0.0
    )
    hidden_gap = max(0.0, current_mfe - running_peak)
    context_features = [
        age_seconds / 60.0,
        _latest_range_pct(snapshot),
        _safe_float(snapshot.get("side_ret_1m_pct")),
        _safe_float(snapshot.get("side_ret_3m_pct")),
        aligned_taker,
        float(bool(snapshot.get("flow_aligned"))),
        float(bool(snapshot.get("flow_opposite"))),
        oi,
        abs(oi),
        float(bool(snapshot.get("positioning_opposite"))),
        float(side == "SHORT"),
    ]
    path_features = context_features + [
        current,
        running_peak,
        current_mfe,
        hidden_gap,
        drawdown,
        current - previous_pnl,
        max(0.0, current_mfe - previous_mfe),
    ]
    return {
        "position_id": str(trade["position_id"]),
        "opened_at_ms": int(trade["opened_at_ms"]),
        "evaluated_at_ms": int(row["evaluated_at_ms"]),
        "label": 1 if float(trade["capture_ratio"]) < 0.80 else 0,
        "context_features": context_features,
        "path_features": path_features,
        "current_pnl_pct": current,
        "running_current_peak_pct": running_peak,
        "current_mfe_pct": current_mfe,
        "current_hidden_gap_pct_points": hidden_gap,
        "latest_1m_range_pct": _latest_range_pct(snapshot),
        "age_seconds": age_seconds,
    }


def _checkpoint_rows(
    *,
    labeled_trades: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    checkpoint_seconds: int | None,
    pre_spike_last: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for trade in labeled_trades:
        pid = str(trade["position_id"])
        rows = observations.get(pid) or []
        discovery = trade.get("mfe_discovery_at_ms")
        if discovery is None or not rows:
            continue
        discovery_ms = int(discovery)
        index: int | None = None
        if pre_spike_last:
            eligible = [
                i
                for i, row in enumerate(rows)
                if int(row["evaluated_at_ms"]) < discovery_ms
            ]
            if eligible:
                index = eligible[-1]
        else:
            target = int(trade["opened_at_ms"]) + int(checkpoint_seconds or 0) * 1000
            # A fixed checkpoint is valid only when the final MFE excursion has
            # not happened yet. Do not silently back off to an earlier
            # pre-spike row and call it T+N.
            if discovery_ms <= target:
                continue
            eligible = [
                i
                for i, row in enumerate(rows)
                if target - 30_000 <= int(row["evaluated_at_ms"]) <= target
            ]
            if eligible:
                index = eligible[-1]
        if index is None:
            continue
        result.append(
            _features_at_index(
                trade=trade,
                rows=rows,
                index=index,
            )
        )
    return result


def build_b1_prearm_detector(
    *,
    trade_rows: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    labeled = [
        row
        for row in sorted(
            trade_rows,
            key=lambda item: (int(item["opened_at_ms"]), str(item["position_id"])),
        )
        if float(row["capture_ratio"]) < 0.80
        or 0.90 <= float(row["capture_ratio"]) <= 1.00
    ]
    ids = [str(row["position_id"]) for row in labeled]
    cut = 2 * len(ids) // 3
    train_ids = set(ids[:cut])
    test_ids = set(ids[cut:])

    checkpoints: dict[str, Any] = {}
    specs: list[tuple[str, int | None, bool]] = [
        (f"T+{seconds}s", seconds, False)
        for seconds in FIXED_CHECKPOINT_SECONDS
    ]
    specs.append(("PRE_SPIKE_LAST_ORACLE_TIMED", None, True))

    for name, seconds, pre_spike in specs:
        rows = _checkpoint_rows(
            labeled_trades=labeled,
            observations=observations,
            checkpoint_seconds=seconds,
            pre_spike_last=pre_spike,
        )
        train = [
            row for row in rows if str(row["position_id"]) in train_ids
        ]
        test = [
            row for row in rows if str(row["position_id"]) in test_ids
        ]
        checkpoints[name] = {
            "timing_note": (
                "Retrospectively selected immediately before final MFE discovery; "
                "features are causal but checkpoint timing is oracle-selected and "
                "cannot be used as a production trigger."
                if pre_spike
                else "Fixed post-entry causal checkpoint; trades whose final MFE "
                "was already discovered before the checkpoint are excluded."
            ),
            "covered": len(rows),
            "low_tail": sum(int(row["label"]) for row in rows),
            "good": len(rows) - sum(int(row["label"]) for row in rows),
            "coverage_of_labeled_pct": pct(len(rows), len(labeled)),
            "models": {
                "context_fpr10": _fit_holdout(
                    train,
                    test,
                    feature_key="context_features",
                    max_fpr=0.10,
                ),
                "path_fpr10": _fit_holdout(
                    train,
                    test,
                    feature_key="path_features",
                    max_fpr=0.10,
                ),
                "context_fpr20": _fit_holdout(
                    train,
                    test,
                    feature_key="context_features",
                    max_fpr=0.20,
                ),
                "path_fpr20": _fit_holdout(
                    train,
                    test,
                    feature_key="path_features",
                    max_fpr=0.20,
                ),
            },
        }

    return {
        "labeled_trade_count": len(labeled),
        "low_tail_lt80": sum(float(row["capture_ratio"]) < 0.80 for row in labeled),
        "good_90_100": sum(
            0.90 <= float(row["capture_ratio"]) <= 1.00
            for row in labeled
        ),
        "train_position_count": len(train_ids),
        "test_position_count": len(test_ids),
        "checkpoints": checkpoints,
    }


def _load_execution_metadata(ids: list[str]) -> dict[str, dict[str, Any]]:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select position_id,entry_price,exit_price,opened_at_ms,closed_at_ms,
                       side,symbol
                from positions
                where position_id=any(%s)
                """,
                (ids,),
            )
            return {
                str(pid): {
                    "entry_price": float(entry),
                    "exit_price": float(exit_price),
                    "opened_at_ms": int(opened),
                    "closed_at_ms": int(closed),
                    "side": str(side).upper(),
                    "symbol": str(symbol),
                }
                for pid, entry, exit_price, opened, closed, side, symbol in cur.fetchall()
                if exit_price is not None
            }


def _bars_from_observations(
    *,
    position: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_close: dict[int, dict[str, Any]] = {}
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    for row in rows:
        snapshot = row.get("snapshot") or {}
        close_ms = int(snapshot.get("candle_close_time_ms") or 0)
        if close_ms <= 0:
            continue
        open_ms = close_ms - 59_999
        # Exclude the entry-straddling minute because its OHLC contains
        # pre-entry price action. This intentionally biases replay conservatively.
        if open_ms < opened or close_ms > closed:
            continue
        open_price = _safe_float(snapshot.get("latest_1m_open"))
        high = _safe_float(snapshot.get("latest_1m_high"))
        low = _safe_float(snapshot.get("latest_1m_low"))
        close_price = _safe_float(snapshot.get("latest_1m_close"))
        if min(open_price, high, low, close_price) <= 0.0:
            continue
        by_close.setdefault(
            close_ms,
            {
                "open_time_ms": open_ms,
                "close_time_ms": close_ms,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
            },
        )
    return [by_close[key] for key in sorted(by_close)]


def _side_roi(side: str, entry: float, price: float) -> float:
    if min(float(entry), float(price)) <= 0.0:
        return 0.0
    raw = 100.0 * (float(price) / float(entry) - 1.0)
    return raw if str(side).upper() == "LONG" else -raw


def _activation_price(
    *,
    side: str,
    entry: float,
    activation_roi_pct: float,
) -> float:
    if str(side).upper() == "LONG":
        return float(entry) * (1.0 + float(activation_roi_pct) / 100.0)
    return float(entry) * (1.0 - float(activation_roi_pct) / 100.0)


def _native_stop(
    *,
    side: str,
    peak_price: float,
    callback_rate_pct: float,
    entry: float,
) -> float:
    del entry
    if str(side).upper() == "LONG":
        return float(peak_price) * (1.0 - float(callback_rate_pct) / 100.0)
    return float(peak_price) * (1.0 + float(callback_rate_pct) / 100.0)


def _fractional_excursion_stop(
    *,
    side: str,
    peak_price: float,
    callback_rate_pct: float,
    entry: float,
) -> float:
    retain = float(callback_rate_pct)
    if str(side).upper() == "LONG":
        return float(entry) + retain * (float(peak_price) - float(entry))
    return float(entry) - retain * (float(entry) - float(peak_price))


def _adverse_crossed(side: str, bar: dict[str, Any], stop: float) -> bool:
    if str(side).upper() == "LONG":
        return float(bar["low"]) <= float(stop)
    return float(bar["high"]) >= float(stop)


def _favorable_extreme(side: str, bar: dict[str, Any]) -> float:
    return float(bar["high"]) if str(side).upper() == "LONG" else float(bar["low"])


def _more_favorable(side: str, candidate: float, peak: float) -> bool:
    if str(side).upper() == "LONG":
        return float(candidate) > float(peak)
    return float(candidate) < float(peak)


def _apply_exit_slippage(side: str, trigger_price: float) -> float:
    slip = float(SLIPPAGE_BPS) / 10_000.0
    if str(side).upper() == "LONG":
        return float(trigger_price) * (1.0 - slip)
    return float(trigger_price) * (1.0 + slip)


def replay_exchange_trail(
    *,
    position: dict[str, Any],
    bars: list[dict[str, Any]],
    activation_roi_pct: float,
    trail_value: float,
    stop_function: Callable[..., float],
    optimistic_same_bar: bool,
) -> dict[str, Any]:
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    activation = _activation_price(
        side=side,
        entry=entry,
        activation_roi_pct=activation_roi_pct,
    )
    active = False
    peak = entry
    stop: float | None = None
    ambiguous_events = 0
    activated_at_ms: int | None = None

    for bar in bars:
        if active and stop is not None and _adverse_crossed(side, bar, stop):
            fill = _apply_exit_slippage(side, stop)
            return {
                "triggered": True,
                "trigger_kind": "DEFINITE_PRIOR_BAR_STOP",
                "exit_at_ms": int(bar["close_time_ms"]),
                "fill_price": fill,
                "gross_exit_roi_pct": _side_roi(side, entry, fill),
                "ambiguous_same_bar_events_before_exit": ambiguous_events,
                "activated_at_ms": activated_at_ms,
            }

        favorable = _favorable_extreme(side, bar)
        activated_this_bar = False
        if not active:
            activation_touched = (
                favorable >= activation
                if side == "LONG"
                else favorable <= activation
            )
            if not activation_touched:
                continue
            active = True
            activated_this_bar = True
            activated_at_ms = int(bar["close_time_ms"])
            peak = favorable
        elif _more_favorable(side, favorable, peak):
            peak = favorable

        if active:
            stop = stop_function(
                side=side,
                peak_price=peak,
                callback_rate_pct=trail_value,
                entry=entry,
            )
            if _adverse_crossed(side, bar, stop):
                ambiguous_events += 1
                if optimistic_same_bar:
                    fill = _apply_exit_slippage(side, stop)
                    return {
                        "triggered": True,
                        "trigger_kind": (
                            "AMBIGUOUS_ACTIVATION_BAR"
                            if activated_this_bar
                            else "AMBIGUOUS_NEW_PEAK_SAME_BAR"
                        ),
                        "exit_at_ms": int(bar["close_time_ms"]),
                        "fill_price": fill,
                        "gross_exit_roi_pct": _side_roi(side, entry, fill),
                        "ambiguous_same_bar_events_before_exit": ambiguous_events,
                        "activated_at_ms": activated_at_ms,
                    }

    fill = float(position["exit_price"])
    return {
        "triggered": False,
        "trigger_kind": "ACTUAL_EXIT_FALLBACK",
        "exit_at_ms": int(position["closed_at_ms"]),
        "fill_price": fill,
        "gross_exit_roi_pct": _side_roi(side, entry, fill),
        "ambiguous_same_bar_events_before_exit": ambiguous_events,
        "activated_at_ms": activated_at_ms,
    }


def _capture_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ratios = [float(row["capture_ratio"]) for row in rows]
    exit_rois = [float(row["gross_exit_roi_pct"]) for row in rows]
    return {
        "n": len(rows),
        "mean_capture_pct": 100.0 * sum(ratios) / len(ratios),
        "median_capture_pct": 100.0 * float(median(ratios) or 0.0),
        "p10_capture_pct": 100.0 * float(quantile(ratios, 0.10) or 0.0),
        "p25_capture_pct": 100.0 * float(quantile(ratios, 0.25) or 0.0),
        "ge90_share_pct": pct(sum(ratio >= 0.90 for ratio in ratios), len(ratios)),
        "lt80_share_pct": pct(sum(ratio < 0.80 for ratio in ratios), len(ratios)),
        "lt90_share_pct": pct(sum(ratio < 0.90 for ratio in ratios), len(ratios)),
        "triggered_share_pct": pct(sum(bool(row["triggered"]) for row in rows), len(rows)),
        "ambiguous_event_trade_share_pct": pct(
            sum(int(row["ambiguous_same_bar_events_before_exit"]) > 0 for row in rows),
            len(rows),
        ),
        "median_exit_roi_pct": float(median(exit_rois) or 0.0),
        "exit_before_final_mfe_discovery_pct": pct(
            sum(
                bool(row["triggered"])
                and row.get("final_mfe_discovery_at_ms") is not None
                and int(row["exit_at_ms"]) < int(row["final_mfe_discovery_at_ms"])
                for row in rows
            ),
            sum(bool(row["triggered"]) for row in rows),
        ),
    }


def build_b2_exchange_replay(
    *,
    trade_rows: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ids = [str(row["position_id"]) for row in trade_rows]
    positions = _load_execution_metadata(ids)
    configs: list[tuple[str, float, float, Callable[..., float]]] = []
    for activation in (0.30, 0.50, 0.75, 1.00):
        for callback in (0.10, 0.20, 0.30, 0.50):
            configs.append(
                (
                    f"NATIVE_A{activation:.2f}_CB{callback:.2f}",
                    activation,
                    callback,
                    _native_stop,
                )
            )
    for activation in (0.30, 0.50):
        for retain in (0.80, 0.85, 0.90, 0.95):
            configs.append(
                (
                    f"IDEAL_FRACTION_A{activation:.2f}_R{retain:.2f}",
                    activation,
                    retain,
                    _fractional_excursion_stop,
                )
            )

    trade_by_id = {str(row["position_id"]): row for row in trade_rows}
    bar_coverage = []
    bars_by_id: dict[str, list[dict[str, Any]]] = {}
    for pid in ids:
        if pid not in positions:
            continue
        bars = _bars_from_observations(
            position=positions[pid],
            rows=observations.get(pid) or [],
        )
        bars_by_id[pid] = bars
        bar_coverage.append(len(bars))

    result_configs: dict[str, Any] = {}
    for name, activation, trail_value, stop_fn in configs:
        modes: dict[str, Any] = {}
        for mode_name, optimistic in (
            ("CONSERVATIVE_DEFINITE_ONLY", False),
            ("OPTIMISTIC_SAME_BAR_BOUND", True),
        ):
            replay_rows = []
            for pid, trade in trade_by_id.items():
                position = positions.get(pid)
                if position is None:
                    continue
                replay = replay_exchange_trail(
                    position=position,
                    bars=bars_by_id.get(pid) or [],
                    activation_roi_pct=activation,
                    trail_value=trail_value,
                    stop_function=stop_fn,
                    optimistic_same_bar=optimistic,
                )
                true_mfe = float(trade["true_mfe_pct"])
                replay["position_id"] = pid
                replay["true_mfe_pct"] = true_mfe
                replay["capture_ratio"] = (
                    float(replay["gross_exit_roi_pct"]) / true_mfe
                    if true_mfe > 0.0
                    else 0.0
                )
                replay["baseline_terminal_capture_ratio"] = float(
                    trade["capture_ratio"]
                )
                replay["final_mfe_discovery_at_ms"] = trade.get(
                    "mfe_discovery_at_ms"
                )
                replay_rows.append(replay)
            modes[mode_name] = _capture_summary(replay_rows)
        result_configs[name] = {
            "activation_roi_pct": activation,
            "trail_value": trail_value,
            "trail_type": (
                "BINANCE_NATIVE_PRICE_CALLBACK"
                if stop_fn is _native_stop
                else "IDEAL_FRACTION_OF_EXCURSION"
            ),
            "modes": modes,
        }

    return {
        "trade_count": len(trade_rows),
        "bars_per_trade_median": float(median(bar_coverage) or 0.0),
        "bars_per_trade_p10": float(quantile(bar_coverage, 0.10) or 0.0),
        "bars_per_trade_p90": float(quantile(bar_coverage, 0.90) or 0.0),
        "replay_guardrail": (
            "Only fully post-entry closed 1m bars are used. Entry-straddling bars "
            "are excluded. Conservative mode never assumes favorable same-bar "
            "high/low ordering. Optimistic mode is an upper feasibility bound, "
            "not a production claim."
        ),
        "slippage_bps": SLIPPAGE_BPS,
        "configs": result_configs,
    }


def build_stage_b(
    *,
    start_ms: int = DEFAULT_START_MS,
    cutoff_ms: int = DEFAULT_CUTOFF_MS,
    arm_pct: float = DEFAULT_ARM_PCT,
) -> dict[str, Any]:
    stage_a = build_low_tail_anatomy(
        start_ms=start_ms,
        cutoff_ms=cutoff_ms,
        arm_pct=arm_pct,
    )
    trade_rows = list(stage_a["trade_rows"])
    ids = [str(row["position_id"]) for row in trade_rows]
    observations = _load_v2_rows(ids=ids, cutoff_ms=cutoff_ms)

    b1 = build_b1_prearm_detector(
        trade_rows=trade_rows,
        observations=observations,
    )
    b2 = build_b2_exchange_replay(
        trade_rows=trade_rows,
        observations=observations,
    )

    native = [
        (name, config)
        for name, config in b2["configs"].items()
        if config["trail_type"] == "BINANCE_NATIVE_PRICE_CALLBACK"
    ]
    ideal = [
        (name, config)
        for name, config in b2["configs"].items()
        if config["trail_type"] == "IDEAL_FRACTION_OF_EXCURSION"
    ]
    best_native_conservative = max(
        native,
        key=lambda item: float(
            item[1]["modes"]["CONSERVATIVE_DEFINITE_ONLY"]["ge90_share_pct"]
        ),
    )
    best_native_optimistic = max(
        native,
        key=lambda item: float(
            item[1]["modes"]["OPTIMISTIC_SAME_BAR_BOUND"]["ge90_share_pct"]
        ),
    )
    best_ideal_conservative = max(
        ideal,
        key=lambda item: float(
            item[1]["modes"]["CONSERVATIVE_DEFINITE_ONLY"]["ge90_share_pct"]
        ),
    )

    fixed_checkpoint_auc = {}
    for checkpoint, payload in b1["checkpoints"].items():
        if checkpoint.startswith("PRE_SPIKE"):
            continue
        fixed_checkpoint_auc[checkpoint] = {
            key: (
                None
                if model.get("status") != "COMPLETE"
                else model.get("test_auc")
            )
            for key, model in payload["models"].items()
        }

    return {
        "stage": "PP-DECISION-V3-LOW-TAIL-STAGE-B",
        "status": "COMPLETE_RESEARCH_ONLY",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "stage_a_baseline": {
            "terminal_trade_count": int(stage_a["terminal_trade_count"]),
            "mean_capture_pct": float(stage_a["distribution"]["mean_capture_pct"]),
            "median_capture_pct": float(stage_a["distribution"]["median_capture_pct"]),
            "ge90_share_pct": float(stage_a["distribution"]["ge90_share_pct"]),
            "lt80_share_pct": float(stage_a["distribution"]["lt80_share_pct"]),
        },
        "b1_prearm_detector": b1,
        "b2_exchange_side_replay": b2,
        "conclusion": {
            "fixed_checkpoint_test_auc": fixed_checkpoint_auc,
            "best_native_conservative": {
                "config": best_native_conservative[0],
                **best_native_conservative[1]["modes"]["CONSERVATIVE_DEFINITE_ONLY"],
            },
            "best_native_optimistic_bound": {
                "config": best_native_optimistic[0],
                **best_native_optimistic[1]["modes"]["OPTIMISTIC_SAME_BAR_BOUND"],
            },
            "best_ideal_fractional_conservative": {
                "config": best_ideal_conservative[0],
                **best_ideal_conservative[1]["modes"]["CONSERVATIVE_DEFINITE_ONLY"],
            },
            "production_promotion": False,
            "guardrail": (
                "B1 final labels and B2 true MFE are offline research targets only. "
                "B2 optimistic same-bar outcomes are upper bounds. No runtime "
                "threshold or trading authority is changed."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=DEFAULT_START_MS)
    parser.add_argument("--cutoff-ms", type=int, default=DEFAULT_CUTOFF_MS)
    parser.add_argument("--arm-pct", type=float, default=DEFAULT_ARM_PCT)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = build_stage_b(
        start_ms=args.start_ms,
        cutoff_ms=args.cutoff_ms,
        arm_pct=args.arm_pct,
    )
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
