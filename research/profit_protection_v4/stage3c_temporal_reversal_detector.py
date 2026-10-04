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

ROOT = Path(__file__).resolve().parents[2]
BASELINE_CSV = (
    ROOT
    / "research/profit_protection_v4/results/"
    "all_positive_mfe_v42c_replay.csv"
)
STAGE3B_TRADES_CSV = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage3b_giveback_window_trades.csv"
)

FLOORS = (0.90, 0.85, 0.80)
AGES = (10, 20, 30, 60)
VELOCITIES = (0.00, 0.02, 0.03, 0.04)
WAITS = (0, 5, 10)


def load_baseline() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASELINE_CSV.open(encoding="utf-8")))
    for row in rows:
        for key in (
            "clean_mfe_pct",
            "protected_pct",
            "opened_at_ms",
        ):
            row[key] = None if row[key] == "" else float(row[key])
        mfe = float(row["clean_mfe_pct"])
        row["retention_vs_true_mfe"] = (
            float(row["protected_pct"]) / mfe if mfe > 0.0 else None
        )
    return rows


def detector_signal(
    path: list[dict[str, Any]],
    *,
    floor: float,
    min_age_seconds: int,
    min_velocity_pp_per_sec: float,
    reclaim_wait_seconds: int,
) -> dict[str, Any] | None:
    running_peak = float("-inf")
    running_peak_at: int | None = None
    pending: dict[str, Any] | None = None

    for index, item in enumerate(path):
        observed_at = int(item["observed_at_ms"])
        current = float(item["current_pnl_pct"])

        if current > running_peak:
            running_peak = current
            running_peak_at = observed_at
            pending = None
            continue

        if running_peak < 1.50 or running_peak_at is None:
            continue

        if pending is not None:
            elapsed = (observed_at - int(pending["start_at_ms"])) / 1000.0
            if elapsed >= reclaim_wait_seconds:
                if current <= float(pending["peak_pct"]) * floor:
                    return {
                        "signal_at_ms": observed_at,
                        "signal_pnl_pct": current,
                        "signal_running_peak_pct": float(
                            pending["peak_pct"]
                        ),
                        "signal_running_peak_at_ms": int(
                            pending["peak_at_ms"]
                        ),
                    }
                pending = None

            if pending is not None:
                continue

        previous = path[index - 1] if index > 0 else item
        previous_at = int(previous["observed_at_ms"])
        previous_pnl = float(previous["current_pnl_pct"])
        sample_seconds = max(
            (observed_at - previous_at) / 1000.0,
            1e-9,
        )
        downward_velocity = (
            previous_pnl - current
        ) / sample_seconds

        age_seconds = (
            observed_at - running_peak_at
        ) / 1000.0

        if not (
            current <= running_peak * floor
            and age_seconds >= min_age_seconds
            and downward_velocity >= min_velocity_pp_per_sec
        ):
            continue

        if reclaim_wait_seconds == 0:
            return {
                "signal_at_ms": observed_at,
                "signal_pnl_pct": current,
                "signal_running_peak_pct": running_peak,
                "signal_running_peak_at_ms": running_peak_at,
            }

        pending = {
            "start_at_ms": observed_at,
            "peak_pct": running_peak,
            "peak_at_ms": running_peak_at,
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
        }

    later = [
        float(item["current_pnl_pct"])
        for item in path
        if int(item["observed_at_ms"]) > int(signal["signal_at_ms"])
    ]
    premature = any(
        value > float(signal["signal_running_peak_pct"])
        for value in later
    )
    label = (
        "PREMATURE_FALSE_REVERSAL"
        if premature
        else "CORRECT_FINAL_REVERSAL"
    )

    return {
        "label": label,
        "retention_vs_final_observed_peak": (
            float(signal["signal_pnl_pct"])
            / final_observed_peak_pct
            if final_observed_peak_pct > 0.0
            else None
        ),
    }


def candidate_metrics(
    group: list[dict[str, Any]],
    paths: dict[str, list[dict[str, Any]]],
    params: tuple[float, int, float, int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    floor, age, velocity, wait = params
    details: list[dict[str, Any]] = []

    for row in group:
        signal = detector_signal(
            paths[str(row["position_id"])],
            floor=floor,
            min_age_seconds=age,
            min_velocity_pp_per_sec=velocity,
            reclaim_wait_seconds=wait,
        )
        outcome = label_signal(
            paths[str(row["position_id"])],
            signal,
            float(row["final_observed_peak_pct"]),
        )
        details.append(
            {
                "position_id": row["position_id"],
                "symbol": row["symbol"],
                "split": row["split"],
                "label": outcome["label"],
                "final_observed_peak_pct": float(
                    row["final_observed_peak_pct"]
                ),
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
                "signal_running_peak_pct": (
                    signal["signal_running_peak_pct"]
                    if signal is not None
                    else None
                ),
                "retention_vs_final_observed_peak": (
                    outcome[
                        "retention_vs_final_observed_peak"
                    ]
                ),
            }
        )

    signals = [
        row for row in details
        if row["label"] != "NO_SIGNAL"
    ]
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

    metrics = {
        "n": len(group),
        "signals_n": len(signals),
        "signal_coverage": (
            len(signals) / len(group) if group else 0.0
        ),
        "correct_final_reversal_n": len(correct),
        "premature_false_reversal_n": len(premature),
        "precision": (
            len(correct) / len(signals) if signals else 0.0
        ),
        "premature_share": (
            len(premature) / len(signals) if signals else 0.0
        ),
        "median_correct_retention": (
            statistics.median(retention)
            if retention
            else None
        ),
        "correct_retention_ge80_share": (
            sum(value >= 0.80 for value in retention)
            / len(retention)
            if retention
            else 0.0
        ),
        "correct_retention_ge75_share": (
            sum(value >= 0.75 for value in retention)
            / len(retention)
            if retention
            else 0.0
        ),
    }
    return metrics, details


def v42_metrics(
    group: list[dict[str, Any]],
    paths: dict[str, list[dict[str, Any]]],
    stage3b: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    details: list[dict[str, Any]] = []

    for row in group:
        position_id = str(row["position_id"])
        stage = stage3b[position_id]
        timing = stage["runner_close_timing_vs_final_peak"]

        if not timing:
            details.append(
                {
                    "position_id": position_id,
                    "symbol": row["symbol"],
                    "split": row["split"],
                    "label": "NO_SIGNAL",
                    "retention_vs_final_observed_peak": None,
                }
            )
            continue

        label = (
            "PREMATURE_FALSE_REVERSAL"
            if timing == "BEFORE_LATER_HIGHER_PEAK"
            else "CORRECT_FINAL_REVERSAL"
        )
        runner_at = int(stage["v42_runner_close_at_ms"])
        observation = next(
            item
            for item in paths[position_id]
            if int(item["observed_at_ms"]) == runner_at
        )
        retention = (
            float(observation["current_pnl_pct"])
            / float(row["final_observed_peak_pct"])
        )
        details.append(
            {
                "position_id": position_id,
                "symbol": row["symbol"],
                "split": row["split"],
                "label": label,
                "retention_vs_final_observed_peak": retention,
            }
        )

    signals = [
        row for row in details if row["label"] != "NO_SIGNAL"
    ]
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

    metrics = {
        "n": len(group),
        "signals_n": len(signals),
        "signal_coverage": (
            len(signals) / len(group) if group else 0.0
        ),
        "correct_final_reversal_n": len(correct),
        "premature_false_reversal_n": len(premature),
        "precision": (
            len(correct) / len(signals) if signals else 0.0
        ),
        "premature_share": (
            len(premature) / len(signals) if signals else 0.0
        ),
        "median_correct_retention": (
            statistics.median(retention)
            if retention
            else None
        ),
        "correct_retention_ge80_share": (
            sum(value >= 0.80 for value in retention)
            / len(retention)
            if retention
            else 0.0
        ),
        "correct_retention_ge75_share": (
            sum(value >= 0.75 for value in retention)
            / len(retention)
            if retention
            else 0.0
        ),
    }
    return metrics, details


def gates(metrics: dict[str, Any]) -> dict[str, bool]:
    return {
        "coverage": float(metrics["signal_coverage"]) >= 0.50,
        "precision": float(metrics["precision"]) >= 0.60,
        "premature": float(metrics["premature_share"]) <= 0.40,
        "retention": (
            metrics["median_correct_retention"] is not None
            and float(metrics["median_correct_retention"]) >= 0.75
        ),
    }


def build() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    baseline = load_baseline()
    triggered = [
        row
        for row in baseline
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
            item
            for item in observations[position_id]
            if opened <= int(item["observed_at_ms"]) <= closed
        ]
        paths[position_id] = path

        if not path:
            continue

        pnls = [float(item["current_pnl_pct"]) for item in path]
        final_peak = max(pnls)
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

    sweep: list[dict[str, Any]] = []
    detail_by_params: dict[
        tuple[float, int, float, int],
        list[dict[str, Any]],
    ] = {}

    params_space = list(
        itertools.product(
            FLOORS,
            AGES,
            VELOCITIES,
            WAITS,
        )
    )

    for params in params_space:
        floor, age, velocity, wait = params
        metrics, details = candidate_metrics(
            dev,
            paths,
            params,
        )
        gate_results = gates(metrics)
        sweep.append(
            {
                "floor": floor,
                "min_age_seconds": age,
                "min_velocity_pp_per_sec": velocity,
                "reclaim_wait_seconds": wait,
                **metrics,
                "gate_coverage": gate_results["coverage"],
                "gate_precision": gate_results["precision"],
                "gate_premature": gate_results["premature"],
                "gate_retention": gate_results["retention"],
                "gate_pass_count": sum(gate_results.values()),
                "eligible": all(gate_results.values()),
            }
        )
        detail_by_params[params] = details

    eligible = [
        row for row in sweep if bool(row["eligible"])
    ]

    selected: dict[str, Any] | None = None
    selected_late_metrics: dict[str, Any] | None = None
    selected_late_details: list[dict[str, Any]] = []

    if eligible:
        eligible.sort(
            key=lambda row: (
                float(row["precision"]),
                float(row["correct_retention_ge80_share"]),
                float(row["median_correct_retention"]),
                float(row["signal_coverage"]),
                -int(row["reclaim_wait_seconds"]),
                -int(row["min_age_seconds"]),
                -float(row["min_velocity_pp_per_sec"]),
                float(row["floor"]),
            ),
            reverse=True,
        )
        selected = dict(eligible[0])
        selected_params = (
            float(selected["floor"]),
            int(selected["min_age_seconds"]),
            float(selected["min_velocity_pp_per_sec"]),
            int(selected["reclaim_wait_seconds"]),
        )
        selected_late_metrics, selected_late_details = (
            candidate_metrics(
                late,
                paths,
                selected_params,
            )
        )

    stage3b = {
        row["position_id"]: row
        for row in csv.DictReader(
            STAGE3B_TRADES_CSV.open(encoding="utf-8")
        )
    }
    v42_dev, _ = v42_metrics(dev, paths, stage3b)
    v42_late, _ = v42_metrics(late, paths, stage3b)
    v42_all, v42_details = v42_metrics(
        runner,
        paths,
        stage3b,
    )

    naive: dict[str, Any] = {}
    for floor in FLOORS:
        params = (floor, 0, 0.0, 0)
        dev_metrics, _ = candidate_metrics(
            dev,
            paths,
            params,
        )
        late_metrics, _ = candidate_metrics(
            late,
            paths,
            params,
        )
        naive[str(int(floor * 100))] = {
            "dev": dev_metrics,
            "late": late_metrics,
        }

    near_miss = [
        row for row in sweep
        if int(row["gate_pass_count"]) == 3
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

    population_rows = []
    for row, v42 in zip(runner, v42_details):
        population_rows.append(
            {
                "position_id": row["position_id"],
                "symbol": row["symbol"],
                "side": row["side"],
                "opened_at_ms": int(row["opened_at_ms"]),
                "split": row["split"],
                "final_observed_peak_pct": float(
                    row["final_observed_peak_pct"]
                ),
                "v42_label": v42["label"],
                "v42_retention_vs_final_observed_peak": (
                    v42["retention_vs_final_observed_peak"]
                ),
            }
        )

    gate_pass_counts = {
        name: sum(bool(row[f"gate_{name}"]) for row in sweep)
        for name in (
            "coverage",
            "precision",
            "premature",
            "retention",
        )
    }

    summary = {
        "stage": "PP-V4-3C",
        "status": (
            "PASS_CANDIDATE"
            if selected is not None
            else "NO_PASS"
        ),
        "baseline_name": (
            "Profit Protector V4.2 - Hybrid Protection"
        ),
        "runner_capable_trade_n": len(runner),
        "dev_n": len(dev),
        "late_n": len(late),
        "candidate_n": len(sweep),
        "eligible_n": len(eligible),
        "gate_pass_candidate_counts": gate_pass_counts,
        "gate_pass_count_distribution": {
            str(count): sum(
                int(row["gate_pass_count"]) == count
                for row in sweep
            )
            for count in range(5)
        },
        "selected_dev_candidate": selected,
        "selected_late_metrics": selected_late_metrics,
        "selected_late_details": selected_late_details,
        "near_miss_top10": near_miss[:10],
        "v42": {
            "dev": v42_dev,
            "late": v42_late,
            "all": v42_all,
        },
        "naive_floor_baselines": naive,
        "decision": {
            "proceed_to_stage3d_with_temporal_detector": (
                selected is not None
            ),
            "runtime_change_authority": "NONE",
            "paper_or_shadow": False,
            "if_no_pass": (
                "Do not relax gates post hoc. Expand causal "
                "feature design in a new preregistered stage."
            ),
        },
    }

    return sweep, population_rows, summary


def write_csv(
    path: str,
    rows: list[dict[str, Any]],
) -> None:
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
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
