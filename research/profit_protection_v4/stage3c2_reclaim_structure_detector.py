from __future__ import annotations

import argparse
import csv
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

from research.profit_protection_v4.stage2b_optimal_protection_frontier import (
    load_market_data,
)
from research.profit_protection_v4.stage3c_temporal_reversal_detector import (
    candidate_metrics as stage3c_candidate_metrics,
    v42_metrics,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE_CSV = (
    ROOT / "research/profit_protection_v4/results/"
    "all_positive_mfe_v42c_replay.csv"
)
STAGE3B_TRADES_CSV = (
    ROOT / "research/profit_protection_v4/results/"
    "stage3b_giveback_window_trades.csv"
)

FLOORS = (0.90, 0.85, 0.80)
WINDOWS = (5, 10, 15)
RECLAIM_FRACTIONS = (0.25, 0.50, 0.75)
REBOUND_VELOCITIES = (0.00, 0.01, 0.02)


def load_baseline() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASELINE_CSV.open(encoding="utf-8")))
    for row in rows:
        for key in ("clean_mfe_pct", "protected_pct", "opened_at_ms"):
            row[key] = None if row[key] == "" else float(row[key])
    return rows


def reclaim_signal(
    path: list[dict[str, Any]],
    *,
    floor: float,
    probe_window_seconds: int,
    reclaim_fraction_threshold: float,
    rebound_velocity_threshold: float,
) -> dict[str, Any] | None:
    running_peak = float("-inf")
    running_peak_at: int | None = None
    probe: dict[str, Any] | None = None
    was_above_floor = True

    for item in path:
        observed_at = int(item["observed_at_ms"])
        current = float(item["current_pnl_pct"])

        if current > running_peak:
            running_peak = current
            running_peak_at = observed_at
            probe = None
            was_above_floor = True
            continue

        if running_peak < 1.50 or running_peak_at is None:
            continue

        current_floor = running_peak * floor

        if probe is None:
            if current > current_floor:
                was_above_floor = True
                continue
            if not was_above_floor:
                continue

            probe = {
                "start_at_ms": observed_at,
                "peak_pct": running_peak,
                "peak_at_ms": running_peak_at,
                "cross_pnl_pct": current,
                "trough_pct": current,
                "trough_at_ms": observed_at,
                "best_rebound_pct": current,
                "best_rebound_at_ms": observed_at,
            }
            was_above_floor = False
            continue

        # Any new high would have been handled above and cancelled probe.
        if current < float(probe["trough_pct"]):
            probe["trough_pct"] = current
            probe["trough_at_ms"] = observed_at
            probe["best_rebound_pct"] = current
            probe["best_rebound_at_ms"] = observed_at
        elif current > float(probe["best_rebound_pct"]):
            probe["best_rebound_pct"] = current
            probe["best_rebound_at_ms"] = observed_at

        elapsed = (
            observed_at - int(probe["start_at_ms"])
        ) / 1000.0
        if elapsed < probe_window_seconds:
            continue

        peak = float(probe["peak_pct"])
        trough = float(probe["trough_pct"])
        rebound = float(probe["best_rebound_pct"])
        drawdown = max(peak - trough, 1e-12)
        reclaim_fraction = max(0.0, rebound - trough) / drawdown

        rebound_seconds = (
            int(probe["best_rebound_at_ms"])
            - int(probe["trough_at_ms"])
        ) / 1000.0
        rebound_velocity = (
            (rebound - trough) / rebound_seconds
            if rebound_seconds > 0.0
            else 0.0
        )

        reclaim_succeeded = (
            reclaim_fraction >= reclaim_fraction_threshold
            and rebound_velocity >= rebound_velocity_threshold
        )
        if reclaim_succeeded:
            probe = None
            was_above_floor = current > current_floor
            continue

        return {
            "signal_at_ms": observed_at,
            "signal_pnl_pct": current,
            "probe_running_peak_pct": peak,
            "probe_running_peak_at_ms": int(probe["peak_at_ms"]),
            "probe_start_at_ms": int(probe["start_at_ms"]),
            "probe_cross_pnl_pct": float(probe["cross_pnl_pct"]),
            "probe_trough_pct": trough,
            "probe_best_rebound_pct": rebound,
            "reclaim_fraction": reclaim_fraction,
            "rebound_velocity_pp_per_sec": rebound_velocity,
            "probe_elapsed_seconds": elapsed,
        }

    return None


def label_signal(
    path: list[dict[str, Any]],
    signal: dict[str, Any] | None,
    final_observed_peak_pct: float,
) -> dict[str, Any]:
    if signal is None:
        return {
            "label": "NO_SIGNAL",
            "retention_vs_final_observed_peak": None,
            "future_higher_peak_pct": None,
            "seconds_signal_to_future_higher_peak": None,
        }

    signal_at = int(signal["signal_at_ms"])
    probe_peak = float(signal["probe_running_peak_pct"])
    later = [
        item for item in path
        if int(item["observed_at_ms"]) > signal_at
    ]
    higher = next(
        (
            item for item in later
            if float(item["current_pnl_pct"]) > probe_peak
        ),
        None,
    )
    premature = higher is not None

    return {
        "label": (
            "PREMATURE_FALSE_REVERSAL"
            if premature
            else "CORRECT_FINAL_REVERSAL"
        ),
        "retention_vs_final_observed_peak": (
            float(signal["signal_pnl_pct"]) / final_observed_peak_pct
            if final_observed_peak_pct > 0.0
            else None
        ),
        "future_higher_peak_pct": (
            max(
                [
                    float(item["current_pnl_pct"])
                    for item in later
                ],
                default=None,
            )
            if premature
            else None
        ),
        "seconds_signal_to_future_higher_peak": (
            (
                int(higher["observed_at_ms"]) - signal_at
            ) / 1000.0
            if higher is not None
            else None
        ),
    }


def metrics(
    group: list[dict[str, Any]],
    paths: dict[str, list[dict[str, Any]]],
    params: tuple[float, int, float, float],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    floor, window, reclaim_fraction, rebound_velocity = params
    details: list[dict[str, Any]] = []

    for row in group:
        position_id = str(row["position_id"])
        signal = reclaim_signal(
            paths[position_id],
            floor=floor,
            probe_window_seconds=window,
            reclaim_fraction_threshold=reclaim_fraction,
            rebound_velocity_threshold=rebound_velocity,
        )
        outcome = label_signal(
            paths[position_id],
            signal,
            float(row["final_observed_peak_pct"]),
        )
        details.append(
            {
                "position_id": position_id,
                "symbol": row["symbol"],
                "side": row["side"],
                "split": row["split"],
                "final_observed_peak_pct": float(
                    row["final_observed_peak_pct"]
                ),
                "label": outcome["label"],
                "signal_at_ms": (
                    signal["signal_at_ms"]
                    if signal is not None
                    else None
                ),
                "signal_pnl_pct": (
                    signal["signal_pnl_pct"]
                    if signal is not None
                    else None
                ),
                "probe_running_peak_pct": (
                    signal["probe_running_peak_pct"]
                    if signal is not None
                    else None
                ),
                "probe_cross_pnl_pct": (
                    signal["probe_cross_pnl_pct"]
                    if signal is not None
                    else None
                ),
                "probe_trough_pct": (
                    signal["probe_trough_pct"]
                    if signal is not None
                    else None
                ),
                "probe_best_rebound_pct": (
                    signal["probe_best_rebound_pct"]
                    if signal is not None
                    else None
                ),
                "reclaim_fraction": (
                    signal["reclaim_fraction"]
                    if signal is not None
                    else None
                ),
                "rebound_velocity_pp_per_sec": (
                    signal["rebound_velocity_pp_per_sec"]
                    if signal is not None
                    else None
                ),
                "probe_elapsed_seconds": (
                    signal["probe_elapsed_seconds"]
                    if signal is not None
                    else None
                ),
                "retention_vs_final_observed_peak": (
                    outcome["retention_vs_final_observed_peak"]
                ),
                "future_higher_peak_pct": (
                    outcome["future_higher_peak_pct"]
                ),
                "seconds_signal_to_future_higher_peak": (
                    outcome["seconds_signal_to_future_higher_peak"]
                ),
            }
        )

    signals = [row for row in details if row["label"] != "NO_SIGNAL"]
    correct = [
        row for row in details
        if row["label"] == "CORRECT_FINAL_REVERSAL"
    ]
    premature = [
        row for row in details
        if row["label"] == "PREMATURE_FALSE_REVERSAL"
    ]
    retention = [
        float(row["retention_vs_final_observed_peak"])
        for row in correct
        if row["retention_vs_final_observed_peak"] is not None
    ]

    result = {
        "n": len(group),
        "signals_n": len(signals),
        "signal_coverage": len(signals) / len(group) if group else 0.0,
        "correct_final_reversal_n": len(correct),
        "premature_false_reversal_n": len(premature),
        "precision": len(correct) / len(signals) if signals else 0.0,
        "premature_share": (
            len(premature) / len(signals) if signals else 0.0
        ),
        "median_correct_retention": (
            statistics.median(retention) if retention else None
        ),
        "correct_retention_ge80_share": (
            sum(value >= 0.80 for value in retention) / len(retention)
            if retention else 0.0
        ),
        "correct_retention_ge75_share": (
            sum(value >= 0.75 for value in retention) / len(retention)
            if retention else 0.0
        ),
    }
    return result, details


def gates(result: dict[str, Any]) -> dict[str, bool]:
    return {
        "coverage": float(result["signal_coverage"]) >= 0.50,
        "precision": float(result["precision"]) >= 0.65,
        "premature": float(result["premature_share"]) <= 0.35,
        "median_retention": (
            result["median_correct_retention"] is not None
            and float(result["median_correct_retention"]) >= 0.80
        ),
        "ge80_share": (
            float(result["correct_retention_ge80_share"]) >= 0.50
        ),
    }


def build() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    baseline = load_baseline()
    triggered = [
        row for row in baseline
        if str(row["protection_actions"]) != "NO_ACTION"
    ]
    ids = [str(row["position_id"]) for row in triggered]
    positions, observations, _ = load_market_data(ids)

    paths: dict[str, list[dict[str, Any]]] = {}
    runner: list[dict[str, Any]] = []
    for row in triggered:
        position_id = str(row["position_id"])
        position = positions[position_id]
        opened = int(position["opened_at_ms"])
        closed = int(position["closed_at_ms"])
        path = [
            item for item in observations[position_id]
            if opened <= int(item["observed_at_ms"]) <= closed
        ]
        paths[position_id] = path
        if not path:
            continue
        final_peak = max(float(x["current_pnl_pct"]) for x in path)
        if final_peak < 1.50:
            continue
        enriched = dict(row)
        enriched["opened_at_ms"] = opened
        enriched["final_observed_peak_pct"] = final_peak
        runner.append(enriched)

    runner.sort(
        key=lambda row: (
            int(row["opened_at_ms"]),
            str(row["position_id"]),
        )
    )
    dev_n = (2 * len(runner)) // 3
    for index, row in enumerate(runner):
        row["split"] = "DEV" if index < dev_n else "LATE"
    dev = [row for row in runner if row["split"] == "DEV"]
    late = [row for row in runner if row["split"] == "LATE"]

    candidate_space = list(
        itertools.product(
            FLOORS,
            WINDOWS,
            RECLAIM_FRACTIONS,
            REBOUND_VELOCITIES,
        )
    )

    sweep: list[dict[str, Any]] = []
    for params in candidate_space:
        floor, window, reclaim_fraction, rebound_velocity = params
        result, _ = metrics(dev, paths, params)
        gate = gates(result)
        sweep.append(
            {
                "floor": floor,
                "probe_window_seconds": window,
                "reclaim_fraction_threshold": reclaim_fraction,
                "rebound_velocity_threshold": rebound_velocity,
                **result,
                "gate_coverage": gate["coverage"],
                "gate_precision": gate["precision"],
                "gate_premature": gate["premature"],
                "gate_median_retention": gate["median_retention"],
                "gate_ge80_share": gate["ge80_share"],
                "gate_pass_count": sum(gate.values()),
                "eligible": all(gate.values()),
            }
        )

    eligible = [row for row in sweep if bool(row["eligible"])]
    eligible.sort(
        key=lambda row: (
            float(row["precision"]),
            -float(row["premature_share"]),
            float(row["correct_retention_ge80_share"]),
            float(row["median_correct_retention"]),
            float(row["signal_coverage"]),
            -int(row["probe_window_seconds"]),
            float(row["floor"]),
            -float(row["reclaim_fraction_threshold"]),
            -float(row["rebound_velocity_threshold"]),
        ),
        reverse=True,
    )

    selected = dict(eligible[0]) if eligible else None
    selected_params: tuple[float, int, float, float] | None = None
    selected_dev_details: list[dict[str, Any]] = []
    selected_late_result: dict[str, Any] | None = None
    selected_late_details: list[dict[str, Any]] = []
    selected_all_result: dict[str, Any] | None = None

    if selected is not None:
        selected_params = (
            float(selected["floor"]),
            int(selected["probe_window_seconds"]),
            float(selected["reclaim_fraction_threshold"]),
            float(selected["rebound_velocity_threshold"]),
        )
        _, selected_dev_details = metrics(dev, paths, selected_params)
        selected_late_result, selected_late_details = metrics(
            late, paths, selected_params
        )
        selected_all_result, _ = metrics(runner, paths, selected_params)

    stage3b = {
        row["position_id"]: row
        for row in csv.DictReader(
            STAGE3B_TRADES_CSV.open(encoding="utf-8")
        )
    }
    v42_dev, _ = v42_metrics(dev, paths, stage3b)
    v42_late, _ = v42_metrics(late, paths, stage3b)
    v42_all, _ = v42_metrics(runner, paths, stage3b)

    stage3c_near_miss = (0.80, 60, 0.03, 5)
    stage3c_dev, _ = stage3c_candidate_metrics(
        dev, paths, stage3c_near_miss
    )
    stage3c_late, _ = stage3c_candidate_metrics(
        late, paths, stage3c_near_miss
    )

    naive: dict[str, Any] = {}
    for floor in FLOORS:
        # Stage3C candidate helper with zero age/velocity/wait is the naive floor.
        dev_result, _ = stage3c_candidate_metrics(
            dev, paths, (floor, 0, 0.0, 0)
        )
        late_result, _ = stage3c_candidate_metrics(
            late, paths, (floor, 0, 0.0, 0)
        )
        naive[str(int(floor * 100))] = {
            "dev": dev_result,
            "late": late_result,
        }

    near_miss = [
        row for row in sweep
        if int(row["gate_pass_count"]) == 4
    ]
    near_miss.sort(
        key=lambda row: (
            float(row["precision"]),
            float(row["correct_retention_ge80_share"]),
            float(
                row["median_correct_retention"]
                if row["median_correct_retention"] is not None
                else -999.0
            ),
            float(row["signal_coverage"]),
        ),
        reverse=True,
    )

    population = [
        {
            "position_id": row["position_id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "opened_at_ms": int(row["opened_at_ms"]),
            "split": row["split"],
            "final_observed_peak_pct": float(
                row["final_observed_peak_pct"]
            ),
        }
        for row in runner
    ]

    gate_names = (
        "coverage",
        "precision",
        "premature",
        "median_retention",
        "ge80_share",
    )
    summary = {
        "stage": "PP-V4-3C2",
        "status": (
            "PASS_CANDIDATE" if selected is not None else "NO_PASS"
        ),
        "baseline_name": "Profit Protector V4.2 - Hybrid Protection",
        "runner_capable_trade_n": len(runner),
        "dev_n": len(dev),
        "late_n": len(late),
        "candidate_n": len(sweep),
        "eligible_n": len(eligible),
        "gate_pass_candidate_counts": {
            name: sum(
                bool(row[f"gate_{name}"]) for row in sweep
            )
            for name in gate_names
        },
        "gate_pass_count_distribution": {
            str(count): sum(
                int(row["gate_pass_count"]) == count
                for row in sweep
            )
            for count in range(6)
        },
        "selected_dev_candidate": selected,
        "selected_dev_details": selected_dev_details,
        "selected_late_metrics": selected_late_result,
        "selected_late_details": selected_late_details,
        "selected_all_metrics": selected_all_result,
        "near_miss_top10": near_miss[:10],
        "baselines": {
            "v42": {
                "dev": v42_dev,
                "late": v42_late,
                "all": v42_all,
            },
            "stage3c_closest_near_miss": {
                "params": {
                    "floor": 0.80,
                    "min_age_seconds": 60,
                    "min_velocity_pp_per_sec": 0.03,
                    "reclaim_wait_seconds": 5,
                },
                "dev": stage3c_dev,
                "late": stage3c_late,
            },
            "naive_floors": naive,
        },
        "decision": {
            "proceed_to_stage3d": selected is not None,
            "runtime_change_authority": "NONE",
            "paper_or_shadow": False,
            "if_no_pass": (
                "Do not relax gates post hoc. Preserve V4.2 and "
                "open a new preregistered research stage."
            ),
        },
    }
    return sweep, population, summary


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if not rows:
            return
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-csv", required=True)
    parser.add_argument("--population-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    sweep, population, summary = build()
    write_csv(args.sweep_csv, sweep)
    write_csv(args.population_csv, population)
    Path(args.summary_json).write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
