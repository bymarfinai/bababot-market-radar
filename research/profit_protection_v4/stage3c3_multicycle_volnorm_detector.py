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
from research.profit_protection_v4.stage3c2_reclaim_structure_detector import (
    metrics as stage3c2_metrics,
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

FLOORS = (0.90, 0.85)
NOISE_LOOKBACKS = (6, 12)
RECLAIM_FRACTIONS = (0.25, 0.50)
FAILED_CYCLES = (1, 2)
DRAWNDOWN_Z = (2.0, 3.0)
NOISE_EPSILON = 0.01


def load_baseline() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASELINE_CSV.open(encoding="utf-8")))
    for row in rows:
        for key in ("clean_mfe_pct", "protected_pct", "opened_at_ms"):
            row[key] = None if row[key] == "" else float(row[key])
    return rows


def local_noise_scale(
    path: list[dict[str, Any]],
    index: int,
    lookback_intervals: int,
) -> float:
    if index <= 0:
        return NOISE_EPSILON
    start = max(1, index - lookback_intervals + 1)
    changes = [
        abs(
            float(path[j]["current_pnl_pct"])
            - float(path[j - 1]["current_pnl_pct"])
        )
        for j in range(start, index + 1)
    ]
    if not changes:
        return NOISE_EPSILON
    return max(float(statistics.median(changes)), NOISE_EPSILON)


def multicycle_signal(
    path: list[dict[str, Any]],
    *,
    floor: float,
    noise_lookback: int,
    reclaim_fraction: float,
    required_failed_cycles: int,
    min_drawdown_z: float,
) -> dict[str, Any] | None:
    running_peak = float("-inf")
    running_peak_at: int | None = None

    active = False
    initial_floor = None
    trough = None
    trough_at = None
    reclaim_armed = False
    reclaim_armed_at = None
    failed_reclaim_count = 0
    was_above_floor = True

    for index, item in enumerate(path):
        observed_at = int(item["observed_at_ms"])
        current = float(item["current_pnl_pct"])

        if current > running_peak:
            running_peak = current
            running_peak_at = observed_at
            active = False
            initial_floor = None
            trough = None
            trough_at = None
            reclaim_armed = False
            reclaim_armed_at = None
            failed_reclaim_count = 0
            was_above_floor = True
            continue

        if running_peak < 1.50 or running_peak_at is None:
            continue

        floor_value = running_peak * floor

        if not active:
            if current > floor_value:
                was_above_floor = True
                continue
            if not was_above_floor:
                continue

            active = True
            initial_floor = floor_value
            trough = current
            trough_at = observed_at
            reclaim_armed = False
            reclaim_armed_at = None
            failed_reclaim_count = 0
            was_above_floor = False
            continue

        assert initial_floor is not None
        assert trough is not None
        assert trough_at is not None

        previous_trough = float(trough)
        made_new_trough = current < previous_trough

        if made_new_trough:
            trough = current
            trough_at = observed_at

        reclaim_level = float(trough) + reclaim_fraction * (
            running_peak - float(trough)
        )

        if not reclaim_armed and current >= reclaim_level:
            reclaim_armed = True
            reclaim_armed_at = observed_at

        failure_event = (
            reclaim_armed
            and reclaim_armed_at is not None
            and observed_at > int(reclaim_armed_at)
            and (
                current <= float(initial_floor)
                or made_new_trough
            )
        )

        if not failure_event:
            continue

        failed_reclaim_count += 1
        noise = local_noise_scale(path, index, noise_lookback)
        drawdown = running_peak - current
        drawdown_z = drawdown / noise

        if (
            failed_reclaim_count >= required_failed_cycles
            and current <= float(initial_floor)
            and drawdown_z >= min_drawdown_z
        ):
            return {
                "signal_at_ms": observed_at,
                "signal_pnl_pct": current,
                "signal_running_peak_pct": running_peak,
                "signal_running_peak_at_ms": running_peak_at,
                "failed_reclaim_count": failed_reclaim_count,
                "local_noise_scale_pp": noise,
                "drawdown_pp": drawdown,
                "drawdown_z": drawdown_z,
                "last_trough_pct": float(trough),
                "last_trough_at_ms": int(trough_at),
            }

        # Start measuring the next reclaim cycle from the current local trough.
        trough = current
        trough_at = observed_at
        reclaim_armed = False
        reclaim_armed_at = None

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
    signal_peak = float(signal["signal_running_peak_pct"])
    later = [
        item
        for item in path
        if int(item["observed_at_ms"]) > signal_at
    ]
    higher = next(
        (
            item
            for item in later
            if float(item["current_pnl_pct"]) > signal_peak
        ),
        None,
    )

    return {
        "label": (
            "PREMATURE_FALSE_REVERSAL"
            if higher is not None
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
            if higher is not None
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
    params: tuple[float, int, float, int, float],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    (
        floor,
        noise_lookback,
        reclaim_fraction,
        required_failed_cycles,
        min_drawdown_z,
    ) = params

    details: list[dict[str, Any]] = []

    for row in group:
        position_id = str(row["position_id"])
        signal = multicycle_signal(
            paths[position_id],
            floor=floor,
            noise_lookback=noise_lookback,
            reclaim_fraction=reclaim_fraction,
            required_failed_cycles=required_failed_cycles,
            min_drawdown_z=min_drawdown_z,
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
                    signal["signal_at_ms"] if signal else None
                ),
                "signal_pnl_pct": (
                    signal["signal_pnl_pct"] if signal else None
                ),
                "signal_running_peak_pct": (
                    signal["signal_running_peak_pct"]
                    if signal
                    else None
                ),
                "failed_reclaim_count": (
                    signal["failed_reclaim_count"] if signal else None
                ),
                "local_noise_scale_pp": (
                    signal["local_noise_scale_pp"] if signal else None
                ),
                "drawdown_pp": (
                    signal["drawdown_pp"] if signal else None
                ),
                "drawdown_z": (
                    signal["drawdown_z"] if signal else None
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
            if retention
            else 0.0
        ),
        "correct_retention_ge75_share": (
            sum(value >= 0.75 for value in retention) / len(retention)
            if retention
            else 0.0
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
            item
            for item in observations[position_id]
            if opened <= int(item["observed_at_ms"]) <= closed
        ]
        paths[position_id] = path
        if not path:
            continue

        final_peak = max(
            float(item["current_pnl_pct"]) for item in path
        )
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
            NOISE_LOOKBACKS,
            RECLAIM_FRACTIONS,
            FAILED_CYCLES,
            DRAWNDOWN_Z,
        )
    )

    sweep: list[dict[str, Any]] = []
    for params in candidate_space:
        (
            floor,
            noise_lookback,
            reclaim_fraction,
            required_failed_cycles,
            min_drawdown_z,
        ) = params
        result, _ = metrics(dev, paths, params)
        gate = gates(result)
        sweep.append(
            {
                "floor": floor,
                "noise_lookback_samples": noise_lookback,
                "reclaim_fraction": reclaim_fraction,
                "required_failed_cycles": required_failed_cycles,
                "min_drawdown_z": min_drawdown_z,
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
            -int(row["required_failed_cycles"]),
            float(row["floor"]),
            -int(row["noise_lookback_samples"]),
            -float(row["reclaim_fraction"]),
            -float(row["min_drawdown_z"]),
        ),
        reverse=True,
    )

    selected = dict(eligible[0]) if eligible else None
    selected_dev_details: list[dict[str, Any]] = []
    selected_late_metrics: dict[str, Any] | None = None
    selected_late_details: list[dict[str, Any]] = []
    selected_all_metrics: dict[str, Any] | None = None

    if selected is not None:
        params = (
            float(selected["floor"]),
            int(selected["noise_lookback_samples"]),
            float(selected["reclaim_fraction"]),
            int(selected["required_failed_cycles"]),
            float(selected["min_drawdown_z"]),
        )
        _, selected_dev_details = metrics(dev, paths, params)
        selected_late_metrics, selected_late_details = metrics(
            late, paths, params
        )
        selected_all_metrics, _ = metrics(runner, paths, params)

    stage3b = {
        row["position_id"]: row
        for row in csv.DictReader(
            STAGE3B_TRADES_CSV.open(encoding="utf-8")
        )
    }
    v42_dev, _ = v42_metrics(dev, paths, stage3b)
    v42_late, _ = v42_metrics(late, paths, stage3b)
    v42_all, _ = v42_metrics(runner, paths, stage3b)

    stage3c_dev, _ = stage3c_candidate_metrics(
        dev, paths, (0.80, 60, 0.03, 5)
    )
    stage3c2_precision_dev, _ = stage3c2_metrics(
        dev, paths, (0.80, 15, 0.25, 0.00)
    )
    stage3c2_retention_dev, _ = stage3c2_metrics(
        dev, paths, (0.85, 5, 0.75, 0.00)
    )

    naive: dict[str, Any] = {}
    for floor in (0.90, 0.85, 0.80):
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
        "stage": "PP-V4-3C3",
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
            name: sum(bool(row[f"gate_{name}"]) for row in sweep)
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
        "selected_late_metrics": selected_late_metrics,
        "selected_late_details": selected_late_details,
        "selected_all_metrics": selected_all_metrics,
        "near_miss_top10": near_miss[:10],
        "baselines": {
            "v42": {
                "dev": v42_dev,
                "late": v42_late,
                "all": v42_all,
            },
            "stage3c_closest_near_miss_dev": stage3c_dev,
            "stage3c2_highest_precision_dev": (
                stage3c2_precision_dev
            ),
            "stage3c2_high_retention_dev": (
                stage3c2_retention_dev
            ),
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
