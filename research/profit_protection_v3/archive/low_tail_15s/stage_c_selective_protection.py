# ARCHIVED TRACK: LOW_TAIL_15S — CLOSED/REJECTED. DO NOT PROMOTE OR RETUNE IN ACTIVE PATH.\nfrom __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

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
from research.profit_protection_v3.archive.low_tail_15s.stage_b_low_tail_prearm_exchange import (
    SLIPPAGE_BPS,
    _activation_price,
    _adverse_crossed,
    _apply_exit_slippage,
    _bars_from_observations,
    _features_at_index,
    _fit_logistic,
    _fractional_excursion_stop,
    _favorable_extreme,
    _load_execution_metadata,
    _more_favorable,
    _native_stop,
    _side_roi,
    _sigmoid,
    _threshold_for_fpr,
)

WINDOWS: dict[str, tuple[int, ...]] = {
    "T30_ONLY": (30,),
    "T30_60": (30, 45, 60),
    "T30_90": (30, 45, 60, 75, 90),
    "T30_120": (30, 45, 60, 75, 90, 105, 120),
}
FEATURE_KEYS = ("context_features", "path_features")
FPR_CAPS = (0.05, 0.10, 0.15, 0.20)
RUNNER_ESCAPE_PEAKS: tuple[float | None, ...] = (None, 0.75, 1.00, 1.50)


@dataclass(frozen=True)
class ProtectionConfig:
    name: str
    activation_roi_pct: float
    trail_value: float
    stop_function: Callable[..., float]
    trail_type: str


def protection_configs() -> list[ProtectionConfig]:
    result: list[ProtectionConfig] = []
    for activation in (0.30, 0.50, 0.75, 1.00):
        for callback in (0.10, 0.20):
            result.append(
                ProtectionConfig(
                    name=f"NATIVE_A{activation:.2f}_CB{callback:.2f}",
                    activation_roi_pct=activation,
                    trail_value=callback,
                    stop_function=_native_stop,
                    trail_type="BINANCE_NATIVE_PRICE_CALLBACK",
                )
            )
    for activation in (0.30, 0.50):
        for retain in (0.90, 0.95):
            result.append(
                ProtectionConfig(
                    name=f"IDEAL_A{activation:.2f}_R{retain:.2f}",
                    activation_roi_pct=activation,
                    trail_value=retain,
                    stop_function=_fractional_excursion_stop,
                    trail_type="IDEAL_FRACTION_OF_EXCURSION",
                )
            )
    return result


def _checkpoint_state_row(
    *,
    trade: dict[str, Any],
    observations: list[dict[str, Any]],
    checkpoint_seconds: int,
) -> dict[str, Any] | None:
    discovery = trade.get("mfe_discovery_at_ms")
    if discovery is None or not observations:
        return None

    target = int(trade["opened_at_ms"]) + int(checkpoint_seconds) * 1000
    if int(discovery) <= target:
        return None

    eligible = [
        index
        for index, row in enumerate(observations)
        if target - 30_000 <= int(row["evaluated_at_ms"]) <= target
    ]
    if not eligible:
        return None

    index = eligible[-1]
    features = _features_at_index(
        trade=trade,
        rows=observations,
        index=index,
    )
    features["checkpoint_seconds"] = int(checkpoint_seconds)
    return features


def build_state_rows(
    *,
    trades: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    checkpoints: tuple[int, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for trade in trades:
        pid = str(trade["position_id"])
        stream = observations.get(pid) or []
        for checkpoint in checkpoints:
            row = _checkpoint_state_row(
                trade=trade,
                observations=stream,
                checkpoint_seconds=int(checkpoint),
            )
            if row is None:
                continue
            key = (pid, int(row["evaluated_at_ms"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row["opened_at_ms"]),
            int(row["evaluated_at_ms"]),
            str(row["position_id"]),
        )
    )
    return rows


def _fit_state_model(
    rows: list[dict[str, Any]],
    *,
    feature_key: str,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot fit Stage C state model without rows")
    features = [list(row[feature_key]) for row in rows]
    labels = [int(row["label"]) for row in rows]
    if len(set(labels)) < 2:
        raise ValueError("Stage C state model requires both labels")

    width = len(features[0])
    means: list[float] = []
    stds: list[float] = []
    standardized: list[list[float]] = []

    for column in range(width):
        values = [float(row[column]) for row in features]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        means.append(mean)
        stds.append(math.sqrt(variance) or 1.0)

    for row in features:
        standardized.append(
            [
                (float(row[column]) - means[column]) / stds[column]
                for column in range(width)
            ]
        )

    weights = _fit_logistic(standardized, labels)
    return {
        "feature_key": feature_key,
        "means": means,
        "stds": stds,
        "weights": weights,
        "train_rows": len(rows),
        "train_low_tail_rows": sum(labels),
    }


def _score_state(model: dict[str, Any], row: dict[str, Any]) -> float:
    feature_key = str(model["feature_key"])
    values = list(row[feature_key])
    means = list(model["means"])
    stds = list(model["stds"])
    weights = list(model["weights"])
    standardized = [
        (float(value) - float(means[index])) / float(stds[index])
        for index, value in enumerate(values)
    ]
    linear = float(weights[0]) + sum(
        float(weights[index + 1]) * value
        for index, value in enumerate(standardized)
    )
    return _sigmoid(linear)


def _trade_scores(
    *,
    model: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, list[tuple[int, float, dict[str, Any]]]]:
    result: dict[str, list[tuple[int, float, dict[str, Any]]]] = defaultdict(list)
    for row in rows:
        pid = str(row["position_id"])
        result[pid].append(
            (
                int(row["evaluated_at_ms"]),
                float(_score_state(model, row)),
                row,
            )
        )
    for pid in result:
        result[pid].sort(key=lambda item: item[0])
    return result


def _threshold_from_trade_scores(
    *,
    trades: list[dict[str, Any]],
    scored: dict[str, list[tuple[int, float, dict[str, Any]]]],
    max_fpr: float,
) -> float:
    labels: list[int] = []
    scores: list[float] = []
    for trade in trades:
        pid = str(trade["position_id"])
        states = scored.get(pid) or []
        if not states:
            continue
        labels.append(1 if float(trade["capture_ratio"]) < 0.80 else 0)
        scores.append(max(score for _, score, _ in states))
    return _threshold_for_fpr(labels, scores, max_fpr=max_fpr)


def select_trades(
    *,
    model: dict[str, Any],
    rows: list[dict[str, Any]],
    threshold: float,
    runner_escape_peak_pct: float | None,
) -> dict[str, dict[str, Any]]:
    scored = _trade_scores(model=model, rows=rows)
    selected: dict[str, dict[str, Any]] = {}
    for pid, states in scored.items():
        for evaluated_at_ms, score, row in states:
            if score < float(threshold):
                continue
            if (
                runner_escape_peak_pct is not None
                and float(row["running_current_peak_pct"])
                >= float(runner_escape_peak_pct)
            ):
                continue
            selected[pid] = {
                "selected_at_ms": int(evaluated_at_ms),
                "score": float(score),
                "checkpoint_seconds": int(row["checkpoint_seconds"]),
                "running_current_peak_pct": float(row["running_current_peak_pct"]),
                "current_pnl_pct": float(row["current_pnl_pct"]),
                "current_mfe_pct": float(row["current_mfe_pct"]),
            }
            break
    return selected


def selector_metrics(
    *,
    trades: list[dict[str, Any]],
    selected: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    labeled = [
        trade
        for trade in trades
        if float(trade["capture_ratio"]) < 0.80
        or 0.90 <= float(trade["capture_ratio"]) <= 1.00
    ]
    low = [trade for trade in labeled if float(trade["capture_ratio"]) < 0.80]
    good = [trade for trade in labeled if 0.90 <= float(trade["capture_ratio"]) <= 1.00]
    selected_low = sum(str(trade["position_id"]) in selected for trade in low)
    selected_good = sum(str(trade["position_id"]) in selected for trade in good)
    total_selected_labeled = selected_low + selected_good
    return {
        "labeled_n": len(labeled),
        "low_tail_n": len(low),
        "good_n": len(good),
        "selected_labeled": total_selected_labeled,
        "precision_low_tail_pct": pct(selected_low, total_selected_labeled),
        "recall_low_tail_pct": pct(selected_low, len(low)),
        "false_positive_good_pct": pct(selected_good, len(good)),
    }


def replay_exchange_trail_after_selection(
    *,
    position: dict[str, Any],
    bars: list[dict[str, Any]],
    selected_at_ms: int,
    config: ProtectionConfig,
) -> dict[str, Any]:
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    activation = _activation_price(
        side=side,
        entry=entry,
        activation_roi_pct=float(config.activation_roi_pct),
    )
    eligible_bars = [
        bar
        for bar in bars
        if int(bar["open_time_ms"]) >= int(selected_at_ms)
    ]

    active = False
    peak = entry
    stop: float | None = None
    activated_at_ms: int | None = None
    ambiguous_same_bar_events = 0

    for bar in eligible_bars:
        if active and stop is not None and _adverse_crossed(side, bar, stop):
            fill = _apply_exit_slippage(side, stop)
            return {
                "triggered": True,
                "trigger_kind": "DEFINITE_PRIOR_BAR_STOP",
                "exit_at_ms": int(bar["close_time_ms"]),
                "fill_price": float(fill),
                "gross_exit_roi_pct": float(_side_roi(side, entry, fill)),
                "activated_at_ms": activated_at_ms,
                "ambiguous_same_bar_events": ambiguous_same_bar_events,
            }

        favorable = _favorable_extreme(side, bar)
        if not active:
            activation_touched = (
                favorable >= activation
                if side == "LONG"
                else favorable <= activation
            )
            if not activation_touched:
                continue
            active = True
            activated_at_ms = int(bar["close_time_ms"])
            peak = favorable
        elif _more_favorable(side, favorable, peak):
            peak = favorable

        stop = config.stop_function(
            side=side,
            peak_price=peak,
            callback_rate_pct=float(config.trail_value),
            entry=entry,
        )
        if _adverse_crossed(side, bar, stop):
            # High/low ordering inside the activation/new-peak minute is unknown.
            # Stage C remains conservative and waits for a later bar to cross the
            # already-known stop.
            ambiguous_same_bar_events += 1

    return {
        "triggered": False,
        "trigger_kind": "NO_DEFINITE_TRIGGER",
        "exit_at_ms": None,
        "fill_price": None,
        "gross_exit_roi_pct": None,
        "activated_at_ms": activated_at_ms,
        "ambiguous_same_bar_events": ambiguous_same_bar_events,
    }


def _distribution(rows: list[dict[str, Any]], *, key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in rows]
    return {
        "n": len(rows),
        "mean_capture_pct": 100.0 * sum(values) / len(values),
        "median_capture_pct": 100.0 * float(median(values) or 0.0),
        "p10_capture_pct": 100.0 * float(quantile(values, 0.10) or 0.0),
        "p25_capture_pct": 100.0 * float(quantile(values, 0.25) or 0.0),
        "ge90_share_pct": pct(sum(value >= 0.90 for value in values), len(values)),
        "lt80_share_pct": pct(sum(value < 0.80 for value in values), len(values)),
        "lt90_share_pct": pct(sum(value < 0.90 for value in values), len(values)),
    }


def evaluate_selective_policy(
    *,
    trades: list[dict[str, Any]],
    selected: dict[str, dict[str, Any]],
    protection: ProtectionConfig,
    positions: dict[str, dict[str, Any]],
    bars_by_id: dict[str, list[dict[str, Any]]],
    replay_cache: dict[tuple[str, int, str], dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    triggered = 0
    selected_count = 0
    ambiguous_selected = 0
    early_final_mfe_exits = 0

    baseline_low = 0
    baseline_good = 0
    low_rescue80 = 0
    low_rescue90 = 0
    good_destroyed90 = 0

    for trade in trades:
        pid = str(trade["position_id"])
        baseline_ratio = float(trade["capture_ratio"])
        hybrid_ratio = baseline_ratio
        intervention = selected.get(pid)
        replay: dict[str, Any] | None = None

        if intervention is not None and pid in positions:
            selected_count += 1
            cache_key = (
                pid,
                int(intervention["selected_at_ms"]),
                str(protection.name),
            )
            replay = replay_cache.get(cache_key)
            if replay is None:
                replay = replay_exchange_trail_after_selection(
                    position=positions[pid],
                    bars=bars_by_id.get(pid) or [],
                    selected_at_ms=int(intervention["selected_at_ms"]),
                    config=protection,
                )
                replay_cache[cache_key] = replay
            if int(replay.get("ambiguous_same_bar_events") or 0) > 0:
                ambiguous_selected += 1
            if bool(replay.get("triggered")):
                triggered += 1
                true_mfe = float(trade["true_mfe_pct"])
                hybrid_ratio = (
                    float(replay["gross_exit_roi_pct"]) / true_mfe
                    if true_mfe > 0.0
                    else baseline_ratio
                )
                discovery = trade.get("mfe_discovery_at_ms")
                if (
                    discovery is not None
                    and replay.get("exit_at_ms") is not None
                    and int(replay["exit_at_ms"]) < int(discovery)
                ):
                    early_final_mfe_exits += 1

        if baseline_ratio < 0.80:
            baseline_low += 1
            if hybrid_ratio >= 0.80:
                low_rescue80 += 1
            if hybrid_ratio >= 0.90:
                low_rescue90 += 1
        if baseline_ratio >= 0.90:
            baseline_good += 1
            if hybrid_ratio < 0.90:
                good_destroyed90 += 1

        rows.append(
            {
                "position_id": pid,
                "baseline_capture_ratio": baseline_ratio,
                "hybrid_capture_ratio": hybrid_ratio,
            }
        )

    baseline = _distribution(rows, key="baseline_capture_ratio")
    hybrid = _distribution(rows, key="hybrid_capture_ratio")
    return {
        "baseline": baseline,
        "hybrid": hybrid,
        "delta": {
            "mean_capture_pp": hybrid["mean_capture_pct"] - baseline["mean_capture_pct"],
            "median_capture_pp": hybrid["median_capture_pct"] - baseline["median_capture_pct"],
            "p10_capture_pp": hybrid["p10_capture_pct"] - baseline["p10_capture_pct"],
            "p25_capture_pp": hybrid["p25_capture_pct"] - baseline["p25_capture_pct"],
            "ge90_share_pp": hybrid["ge90_share_pct"] - baseline["ge90_share_pct"],
            "lt80_share_pp": hybrid["lt80_share_pct"] - baseline["lt80_share_pct"],
        },
        "selected_n": selected_count,
        "selected_share_pct": pct(selected_count, len(trades)),
        "triggered_n": triggered,
        "triggered_share_of_selected_pct": pct(triggered, selected_count),
        "ambiguous_same_bar_selected_pct": pct(ambiguous_selected, selected_count),
        "triggered_exit_before_final_mfe_discovery_pct": pct(
            early_final_mfe_exits,
            triggered,
        ),
        "low_tail_rescue_to_ge80_pct": pct(low_rescue80, baseline_low),
        "low_tail_rescue_to_ge90_pct": pct(low_rescue90, baseline_low),
        "baseline_good_destroyed_below90_pct": pct(
            good_destroyed90,
            baseline_good,
        ),
    }


def _labeled(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        trade
        for trade in trades
        if float(trade["capture_ratio"]) < 0.80
        or 0.90 <= float(trade["capture_ratio"]) <= 1.00
    ]


def _train_model_and_threshold(
    *,
    train_trades: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    checkpoints: tuple[int, ...],
    feature_key: str,
    max_fpr: float,
) -> tuple[dict[str, Any], float, list[dict[str, Any]]]:
    train_labeled = _labeled(train_trades)
    state_rows = build_state_rows(
        trades=train_labeled,
        observations=observations,
        checkpoints=checkpoints,
    )
    model = _fit_state_model(state_rows, feature_key=feature_key)
    scored = _trade_scores(model=model, rows=state_rows)
    threshold = _threshold_from_trade_scores(
        trades=train_labeled,
        scored=scored,
        max_fpr=max_fpr,
    )
    return model, threshold, state_rows


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, ...]:
    result = candidate["policy"]
    delta = result["delta"]
    return (
        1.0 if candidate["qualification"]["passes_runner_gate"] else 0.0,
        1.0 if candidate["qualification"]["non_degrading_mean"] else 0.0,
        float(delta["ge90_share_pp"]),
        -float(delta["lt80_share_pp"]),
        float(delta["p25_capture_pp"]),
        float(result["low_tail_rescue_to_ge90_pct"]),
        -float(result["baseline_good_destroyed_below90_pct"]),
    )


def build_stage_c(
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
    all_trades = sorted(
        list(stage_a["trade_rows"]),
        key=lambda row: (int(row["opened_at_ms"]), str(row["position_id"])),
    )
    ids = [str(row["position_id"]) for row in all_trades]
    observations = _load_v2_rows(ids=ids, cutoff_ms=cutoff_ms)
    positions = _load_execution_metadata(ids)

    bars_by_id: dict[str, list[dict[str, Any]]] = {}
    for pid, position in positions.items():
        bars_by_id[pid] = _bars_from_observations(
            position=position,
            rows=observations.get(pid) or [],
        )

    third = len(all_trades) // 3
    early = all_trades[:third]
    mid = all_trades[third : 2 * third]
    late = all_trades[2 * third :]

    protections = protection_configs()
    replay_cache: dict[tuple[str, int, str], dict[str, Any]] = {}
    tuning_candidates: list[dict[str, Any]] = []

    for window_name, checkpoints in WINDOWS.items():
        for feature_key in FEATURE_KEYS:
            base_model, _, _ = _train_model_and_threshold(
                train_trades=early,
                observations=observations,
                checkpoints=checkpoints,
                feature_key=feature_key,
                max_fpr=0.10,
            )
            train_state_rows = build_state_rows(
                trades=_labeled(early),
                observations=observations,
                checkpoints=checkpoints,
            )
            scored_train = _trade_scores(model=base_model, rows=train_state_rows)

            mid_state_rows = build_state_rows(
                trades=mid,
                observations=observations,
                checkpoints=checkpoints,
            )

            for max_fpr in FPR_CAPS:
                threshold = _threshold_from_trade_scores(
                    trades=_labeled(early),
                    scored=scored_train,
                    max_fpr=max_fpr,
                )
                for runner_escape in RUNNER_ESCAPE_PEAKS:
                    selected_mid = select_trades(
                        model=base_model,
                        rows=mid_state_rows,
                        threshold=threshold,
                        runner_escape_peak_pct=runner_escape,
                    )
                    selector = selector_metrics(
                        trades=mid,
                        selected=selected_mid,
                    )
                    for protection in protections:
                        policy = evaluate_selective_policy(
                            trades=mid,
                            selected=selected_mid,
                            protection=protection,
                            positions=positions,
                            bars_by_id=bars_by_id,
                            replay_cache=replay_cache,
                        )
                        tuning_candidates.append(
                            {
                                "window": window_name,
                                "checkpoints": list(checkpoints),
                                "feature_key": feature_key,
                                "max_train_fpr": max_fpr,
                                "runner_escape_peak_pct": runner_escape,
                                "protection": {
                                    "name": protection.name,
                                    "trail_type": protection.trail_type,
                                    "activation_roi_pct": protection.activation_roi_pct,
                                    "trail_value": protection.trail_value,
                                },
                                "selector": selector,
                                "policy": policy,
                                "qualification": {
                                    "passes_runner_gate": (
                                        float(
                                            policy[
                                                "baseline_good_destroyed_below90_pct"
                                            ]
                                        )
                                        <= 5.0
                                    ),
                                    "non_degrading_mean": (
                                        float(policy["delta"]["mean_capture_pp"])
                                        >= -0.50
                                    ),
                                    "improves_ge90": (
                                        float(policy["delta"]["ge90_share_pp"]) > 0.0
                                    ),
                                    "reduces_lt80": (
                                        float(policy["delta"]["lt80_share_pp"]) < 0.0
                                    ),
                                },
                            }
                        )

    frontier = {
        "candidate_count": len(tuning_candidates),
        "improves_ge90_count": sum(
            bool(item["qualification"]["improves_ge90"])
            for item in tuning_candidates
        ),
        "reduces_lt80_count": sum(
            bool(item["qualification"]["reduces_lt80"])
            for item in tuning_candidates
        ),
        "improves_both_count": sum(
            bool(item["qualification"]["improves_ge90"])
            and bool(item["qualification"]["reduces_lt80"])
            for item in tuning_candidates
        ),
        "passes_all_tuning_gates_count": sum(
            all(bool(value) for value in item["qualification"].values())
            for item in tuning_candidates
        ),
    }
    frontier["best_ge90_delta"] = max(
        tuning_candidates,
        key=lambda item: float(item["policy"]["delta"]["ge90_share_pp"]),
    )
    frontier["best_lt80_delta"] = min(
        tuning_candidates,
        key=lambda item: float(item["policy"]["delta"]["lt80_share_pp"]),
    )
    frontier["best_low_tail_rescue80"] = max(
        tuning_candidates,
        key=lambda item: float(item["policy"]["low_tail_rescue_to_ge80_pct"]),
    )

    tuning_candidates.sort(key=_candidate_sort_key, reverse=True)
    qualified = [
        item
        for item in tuning_candidates
        if all(bool(value) for value in item["qualification"].values())
    ]
    best = qualified[0] if qualified else tuning_candidates[0]

    best_protection = next(
        config
        for config in protections
        if config.name == str(best["protection"]["name"])
    )
    best_window = tuple(int(value) for value in best["checkpoints"])

    final_train = early + mid
    final_model, final_threshold, final_train_rows = _train_model_and_threshold(
        train_trades=final_train,
        observations=observations,
        checkpoints=best_window,
        feature_key=str(best["feature_key"]),
        max_fpr=float(best["max_train_fpr"]),
    )
    late_state_rows = build_state_rows(
        trades=late,
        observations=observations,
        checkpoints=best_window,
    )
    selected_late = select_trades(
        model=final_model,
        rows=late_state_rows,
        threshold=final_threshold,
        runner_escape_peak_pct=(
            None
            if best["runner_escape_peak_pct"] is None
            else float(best["runner_escape_peak_pct"])
        ),
    )
    late_selector = selector_metrics(
        trades=late,
        selected=selected_late,
    )
    late_policy = evaluate_selective_policy(
        trades=late,
        selected=selected_late,
        protection=best_protection,
        positions=positions,
        bars_by_id=bars_by_id,
        replay_cache=replay_cache,
    )

    test_gate = {
        "improves_ge90": float(late_policy["delta"]["ge90_share_pp"]) > 0.0,
        "reduces_lt80": float(late_policy["delta"]["lt80_share_pp"]) < 0.0,
        "runner_damage_le5": float(
            late_policy["baseline_good_destroyed_below90_pct"]
        )
        <= 5.0,
        "mean_not_down_more_than_0_5pp": float(
            late_policy["delta"]["mean_capture_pp"]
        )
        >= -0.50,
    }
    test_gate["stage_d_unblocked"] = all(test_gate.values())

    top_tuning = [
        {
            "window": candidate["window"],
            "feature_key": candidate["feature_key"],
            "max_train_fpr": candidate["max_train_fpr"],
            "runner_escape_peak_pct": candidate["runner_escape_peak_pct"],
            "protection": candidate["protection"],
            "selector": candidate["selector"],
            "policy": candidate["policy"],
            "qualification": candidate["qualification"],
        }
        for candidate in tuning_candidates[:20]
    ]

    return {
        "stage": "PP-DECISION-V3-LOW-TAIL-STAGE-C",
        "status": "COMPLETE_RESEARCH_ONLY",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "methodology": {
            "chronological_split": {
                "EARLY_TRAIN": len(early),
                "MID_TUNE": len(mid),
                "LATE_TEST": len(late),
            },
            "selector_windows": {
                key: list(value) for key, value in WINDOWS.items()
            },
            "feature_keys": list(FEATURE_KEYS),
            "fpr_caps": list(FPR_CAPS),
            "runner_escape_peak_options": list(RUNNER_ESCAPE_PEAKS),
            "protection_config_count": len(protections),
            "candidate_count": len(tuning_candidates),
            "hybrid_metric_note": (
                "Unselected/no-trigger trades retain the Stage A terminal observed-peak "
                "benchmark. Triggered selected trades replace that numerator with the "
                "conservative exchange-side replay exit. This measures whether selective "
                "intervention improves the peak-capture opportunity distribution; it is "
                "not a full realized-PnL backtest."
            ),
            "execution_guardrail": (
                "Protection starts only after a causal selector observation. Only fully "
                "post-selection 1m bars are eligible. Same-bar activation/new-peak stop "
                "crosses are treated as ambiguous and are not executed."
            ),
        },
        "baseline_full": {
            "terminal_trade_count": int(stage_a["terminal_trade_count"]),
            "mean_capture_pct": float(stage_a["distribution"]["mean_capture_pct"]),
            "median_capture_pct": float(stage_a["distribution"]["median_capture_pct"]),
            "p10_capture_pct": float(stage_a["distribution"]["p10_pct"]),
            "p25_capture_pct": float(stage_a["distribution"]["p25_pct"]),
            "ge90_share_pct": float(stage_a["distribution"]["ge90_share_pct"]),
            "lt80_share_pct": float(stage_a["distribution"]["lt80_share_pct"]),
        },
        "tuning": {
            "frontier": frontier,
            "best_candidate": best,
            "top_20": top_tuning,
        },
        "late_test": {
            "selected_config": {
                "window": best["window"],
                "checkpoints": list(best_window),
                "feature_key": best["feature_key"],
                "max_train_fpr": best["max_train_fpr"],
                "runner_escape_peak_pct": best["runner_escape_peak_pct"],
                "threshold_refit_early_plus_mid": final_threshold,
                "protection": best["protection"],
                "final_train_state_rows": len(final_train_rows),
            },
            "selector": late_selector,
            "policy": late_policy,
            "gate": test_gate,
        },
        "conclusion": {
            "production_promotion": False,
            "stage_d_unblocked": bool(test_gate["stage_d_unblocked"]),
            "primary_result": (
                "Selective protection passes the Stage C late-test gate."
                if test_gate["stage_d_unblocked"]
                else "Selective protection does not pass the full Stage C late-test gate."
            ),
            "guardrail": (
                "Low-tail labels, terminal capture ratios, and true MFE are offline "
                "targets only. No Stage C selector or protection rule has production authority."
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

    result = build_stage_c(
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
