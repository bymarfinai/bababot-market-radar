from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from research.profit_protection_v4.stage2b_optimal_protection_frontier import (
    load_market_data,
)
from research.profit_protection_v4.stage2c_runner_preservation import (
    simulate_hybrid,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE_CSV = (
    ROOT
    / "research/profit_protection_v4/results/"
    "all_positive_mfe_v42c_replay.csv"
)
STAGE3A_CSV = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage3a_low_retention_anatomy.csv"
)
STAGE1J_JSON = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1j_clean_post_entry_mfe_evidence.json"
)

LEVELS = (0.95, 0.90, 0.85, 0.80, 0.75)


def _quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "median": None, "p75": None}
    if len(values) == 1:
        value = float(values[0])
        return {"p25": value, "median": value, "p75": value}
    q = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "p25": float(q[0]),
        "median": float(statistics.median(values)),
        "p75": float(q[2]),
    }


def peak_regime(peak_pct: float) -> str:
    if peak_pct < 1.0:
        return "LT1"
    if peak_pct < 1.5:
        return "1_TO_1_5"
    if peak_pct < 3.0:
        return "1_5_TO_3"
    return "GE3"


def classify_crossing_outcome(
    later_pnls: list[float],
    peak_at_crossing: float,
) -> str:
    return (
        "RECOVERED_NEW_HIGH"
        if any(value > peak_at_crossing for value in later_pnls)
        else "FINAL_REVERSAL"
    )


def load_baseline() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASELINE_CSV.open(encoding="utf-8")))
    for row in rows:
        for key in (
            "clean_mfe_pct",
            "observed_gross_peak_pct",
            "observable_net_peak_pct",
            "actual_realized_pct",
            "actual_realized_usdt",
            "protected_pct",
            "protected_usdt",
            "delta_usdt",
        ):
            row[key] = None if row[key] == "" else float(row[key])
        mfe = float(row["clean_mfe_pct"])
        row["retention_vs_true_mfe"] = (
            float(row["protected_pct"]) / mfe if mfe > 0.0 else None
        )
    return rows


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
    stage3a = {
        row["position_id"]: row
        for row in csv.DictReader(STAGE3A_CSV.open(encoding="utf-8"))
    }
    stage1j = {
        row["position_id"]: row
        for row in json.loads(STAGE1J_JSON.read_text(encoding="utf-8"))
    }

    ids = [str(row["position_id"]) for row in triggered]
    positions, observations, orders = load_market_data(ids)

    event_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

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
        if not path:
            continue

        failure = float(row["retention_vs_true_mfe"]) < 0.75
        stage3a_class = (
            stage3a[position_id]["primary_class"]
            if position_id in stage3a
            else "CONTROL_GE75"
        )

        simulation = simulate_hybrid(
            stage1j[position_id],
            small_template=(0.50, 0.60, 3),
            reduce_fraction=0.25,
            runner_qualify_pct=1.50,
            positions=positions,
            observations=observations,
            orders=orders,
        )

        running_peak = float("-inf")
        running_peak_at: int | None = None
        crossed = {level: False for level in LEVELS}

        for index, item in enumerate(path):
            observed_at = int(item["observed_at_ms"])
            current = float(item["current_pnl_pct"])

            if current > running_peak:
                running_peak = current
                running_peak_at = observed_at
                crossed = {level: False for level in LEVELS}
                continue

            if running_peak <= 0.0 or running_peak_at is None:
                continue

            for level in LEVELS:
                if crossed[level] or current > running_peak * level:
                    continue

                crossed[level] = True
                later = [
                    float(other["current_pnl_pct"])
                    for other in path[index + 1 :]
                ]
                outcome = classify_crossing_outcome(
                    later,
                    running_peak,
                )
                recovered = next(
                    (
                        other
                        for other in path[index + 1 :]
                        if float(other["current_pnl_pct"]) > running_peak
                    ),
                    None,
                )

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

                streak_index = index
                streak_count = 0
                while (
                    streak_index > 0
                    and float(
                        path[streak_index]["current_pnl_pct"]
                    )
                    <= float(
                        path[streak_index - 1]["current_pnl_pct"]
                    )
                ):
                    streak_count += 1
                    streak_index -= 1

                streak_seconds = (
                    observed_at
                    - int(path[streak_index]["observed_at_ms"])
                ) / 1000.0

                thresholds_crossed_same_sample = sum(
                    1
                    for candidate in LEVELS
                    if (
                        previous_pnl > running_peak * candidate
                        and current <= running_peak * candidate
                    )
                )

                event_rows.append(
                    {
                        "position_id": position_id,
                        "symbol": row["symbol"],
                        "side": row["side"],
                        "failure_lt75": failure,
                        "stage3a_class": stage3a_class,
                        "protection_actions": row["protection_actions"],
                        "threshold_pct_of_running_peak": int(
                            level * 100
                        ),
                        "running_peak_regime": peak_regime(
                            running_peak
                        ),
                        "running_peak_pct": running_peak,
                        "running_peak_at_ms": running_peak_at,
                        "cross_at_ms": observed_at,
                        "seconds_peak_to_cross": (
                            observed_at - running_peak_at
                        ) / 1000.0,
                        "current_pnl_pct_at_cross": current,
                        "current_to_peak_ratio": (
                            current / running_peak
                            if running_peak > 0.0
                            else None
                        ),
                        "previous_pnl_pct": previous_pnl,
                        "sample_seconds": sample_seconds,
                        "downward_velocity_pp_per_sec": (
                            downward_velocity
                        ),
                        "monotonic_down_streak_n": streak_count,
                        "monotonic_down_streak_seconds": (
                            streak_seconds
                        ),
                        "thresholds_crossed_same_sample": (
                            thresholds_crossed_same_sample
                        ),
                        "outcome": outcome,
                        "recover_new_high_at_ms": (
                            int(recovered["observed_at_ms"])
                            if recovered is not None
                            else None
                        ),
                        "seconds_cross_to_new_high": (
                            (
                                int(recovered["observed_at_ms"])
                                - observed_at
                            )
                            / 1000.0
                            if recovered is not None
                            else None
                        ),
                    }
                )

        pnls = [float(item["current_pnl_pct"]) for item in path]
        final_peak_index = max(
            range(len(pnls)),
            key=lambda index: pnls[index],
        )
        final_peak = pnls[final_peak_index]
        final_peak_at = int(
            path[final_peak_index]["observed_at_ms"]
        )

        trade_result: dict[str, Any] = {
            "position_id": position_id,
            "symbol": row["symbol"],
            "side": row["side"],
            "failure_lt75": failure,
            "stage3a_class": stage3a_class,
            "protection_actions": row["protection_actions"],
            "clean_mfe_pct": float(row["clean_mfe_pct"]),
            "protected_pct": float(row["protected_pct"]),
            "retention_vs_true_mfe_pct": (
                100.0 * float(row["retention_vs_true_mfe"])
            ),
            "final_observed_peak_pct": final_peak,
            "final_observed_peak_regime": peak_regime(final_peak),
            "final_observed_peak_at_ms": final_peak_at,
            "v42_first_overlay_at_ms": simulation.get(
                "first_overlay_at_ms"
            ),
            "v42_small_reduce_at_ms": simulation.get("small_at_ms"),
            "v42_runner_close_at_ms": simulation.get(
                "runner_at_ms"
            ),
        }

        for level in LEVELS:
            crossing = next(
                (
                    item
                    for item in path[final_peak_index + 1 :]
                    if float(item["current_pnl_pct"])
                    <= final_peak * level
                ),
                None,
            )
            suffix = str(int(level * 100))
            trade_result[
                f"seconds_final_peak_to_{suffix}"
            ] = (
                (
                    int(crossing["observed_at_ms"])
                    - final_peak_at
                )
                / 1000.0
                if crossing is not None
                else None
            )
            trade_result[
                f"final_path_{suffix}_cross_at_ms"
            ] = (
                int(crossing["observed_at_ms"])
                if crossing is not None
                else None
            )

        for name, timestamp in (
            ("small_reduce", simulation.get("small_at_ms")),
            ("runner_close", simulation.get("runner_at_ms")),
        ):
            if timestamp is None:
                trade_result[f"{name}_timing_vs_final_peak"] = None
                trade_result[
                    f"seconds_{name}_to_final_peak"
                ] = None
            else:
                timestamp = int(timestamp)
                trade_result[
                    f"{name}_timing_vs_final_peak"
                ] = (
                    "BEFORE_LATER_HIGHER_PEAK"
                    if timestamp < final_peak_at
                    else "AFTER_FINAL_PEAK"
                )
                trade_result[
                    f"seconds_{name}_to_final_peak"
                ] = (
                    final_peak_at - timestamp
                ) / 1000.0

        trade_rows.append(trade_result)

    threshold_summary: dict[str, Any] = {}
    for level in LEVELS:
        threshold = int(level * 100)
        group = [
            item
            for item in event_rows
            if item["threshold_pct_of_running_peak"] == threshold
        ]
        recovered = [
            item
            for item in group
            if item["outcome"] == "RECOVERED_NEW_HIGH"
        ]
        final = [
            item
            for item in group
            if item["outcome"] == "FINAL_REVERSAL"
        ]
        threshold_summary[str(threshold)] = {
            "events_n": len(group),
            "recovered_new_high_n": len(recovered),
            "recovered_new_high_share_pct": (
                100.0 * len(recovered) / len(group)
                if group
                else None
            ),
            "final_reversal_n": len(final),
            "peak_to_cross_seconds_all": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in group
                ]
            ),
            "peak_to_cross_seconds_recovered": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in recovered
                ]
            ),
            "peak_to_cross_seconds_final": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in final
                ]
            ),
            "cross_to_new_high_seconds_recovered": _quantiles(
                [
                    float(item["seconds_cross_to_new_high"])
                    for item in recovered
                    if item["seconds_cross_to_new_high"] is not None
                ]
            ),
        }

    final_path_summary: dict[str, Any] = {}
    for level in LEVELS:
        threshold = int(level * 100)
        key = f"seconds_final_peak_to_{threshold}"
        values = [
            float(item[key])
            for item in trade_rows
            if item[key] is not None
        ]
        final_path_summary[str(threshold)] = {
            "trades_reaching_threshold_n": len(values),
            "seconds_from_final_observed_peak": _quantiles(values),
        }

    threshold80_by_regime: dict[str, Any] = {}
    for regime in ("LT1", "1_TO_1_5", "1_5_TO_3", "GE3"):
        group = [
            item
            for item in event_rows
            if (
                item["threshold_pct_of_running_peak"] == 80
                and item["running_peak_regime"] == regime
            )
        ]
        recovered = [
            item for item in group
            if item["outcome"] == "RECOVERED_NEW_HIGH"
        ]
        final = [
            item for item in group
            if item["outcome"] == "FINAL_REVERSAL"
        ]
        threshold80_by_regime[regime] = {
            "events_n": len(group),
            "recovered_new_high_n": len(recovered),
            "recovered_new_high_share_pct": (
                100.0 * len(recovered) / len(group)
                if group
                else None
            ),
            "recovered_peak_to_cross_seconds": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in recovered
                ]
            ),
            "final_peak_to_cross_seconds": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in final
                ]
            ),
        }

    final_path_by_regime: dict[str, Any] = {}
    for regime in ("LT1", "1_TO_1_5", "1_5_TO_3", "GE3"):
        group = [
            item
            for item in trade_rows
            if item["final_observed_peak_regime"] == regime
        ]
        final_path_by_regime[regime] = {
            "trades_n": len(group),
            **{
                f"peak_to_{threshold}_seconds": _quantiles(
                    [
                        float(
                            item[
                                f"seconds_final_peak_to_{threshold}"
                            ]
                        )
                        for item in group
                        if item[
                            f"seconds_final_peak_to_{threshold}"
                        ]
                        is not None
                    ]
                )
                for threshold in (90, 85, 80, 75)
            },
        }

    eighty_events = [
        item
        for item in event_rows
        if item["threshold_pct_of_running_peak"] == 80
    ]
    eighty_recovered = [
        item for item in eighty_events
        if item["outcome"] == "RECOVERED_NEW_HIGH"
    ]
    eighty_final = [
        item for item in eighty_events
        if item["outcome"] == "FINAL_REVERSAL"
    ]

    age_bins = (
        (0, 5),
        (5, 10),
        (10, 15),
        (15, 20),
        (20, 30),
        (30, 60),
        (60, 120),
        (120, 10**12),
    )
    eighty_age_bins = []
    for lower, upper in age_bins:
        group = [
            item
            for item in eighty_events
            if (
                lower <= float(item["seconds_peak_to_cross"]) < upper
            )
        ]
        if not group:
            continue
        recovered_n = sum(
            item["outcome"] == "RECOVERED_NEW_HIGH"
            for item in group
        )
        eighty_age_bins.append(
            {
                "lower_seconds": lower,
                "upper_seconds": (
                    upper if upper < 10**12 else None
                ),
                "events_n": len(group),
                "recovered_new_high_n": recovered_n,
                "recovered_new_high_share_pct": (
                    100.0 * recovered_n / len(group)
                ),
            }
        )

    recovered80_by_trade = Counter(
        item["position_id"]
        for item in eighty_recovered
    )
    recovered80_counts = [
        recovered80_by_trade[str(row["position_id"])]
        for row in triggered
    ]

    runner_rows = [
        item for item in trade_rows
        if item["v42_runner_close_at_ms"] is not None
    ]
    small_rows = [
        item for item in trade_rows
        if item["v42_small_reduce_at_ms"] is not None
    ]
    stage3a_runner_delay = [
        item for item in runner_rows
        if item["stage3a_class"] == "RUNNER_TRIGGER_DELAY"
    ]

    summary = {
        "stage": "PP-V4-3B",
        "status": "COMPLETE_RESEARCH_ONLY",
        "baseline_name": "Profit Protector V4.2 - Hybrid Protection",
        "triggered_trade_n": len(triggered),
        "failure_lt75_n": sum(
            bool(item["failure_lt75"]) for item in trade_rows
        ),
        "control_ge75_n": sum(
            not bool(item["failure_lt75"]) for item in trade_rows
        ),
        "giveback_event_n": len(event_rows),
        "thresholds": threshold_summary,
        "final_peak_path": final_path_summary,
        "threshold80_by_running_peak_regime": (
            threshold80_by_regime
        ),
        "final_peak_path_by_regime": final_path_by_regime,
        "threshold80_temporal_features": {
            "recovered_peak_to_cross_seconds": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in eighty_recovered
                ]
            ),
            "final_peak_to_cross_seconds": _quantiles(
                [
                    float(item["seconds_peak_to_cross"])
                    for item in eighty_final
                ]
            ),
            "recovered_downward_velocity_pp_per_sec": _quantiles(
                [
                    float(item["downward_velocity_pp_per_sec"])
                    for item in eighty_recovered
                ]
            ),
            "final_downward_velocity_pp_per_sec": _quantiles(
                [
                    float(item["downward_velocity_pp_per_sec"])
                    for item in eighty_final
                ]
            ),
            "recovered_monotonic_down_streak_n": _quantiles(
                [
                    float(item["monotonic_down_streak_n"])
                    for item in eighty_recovered
                ]
            ),
            "final_monotonic_down_streak_n": _quantiles(
                [
                    float(item["monotonic_down_streak_n"])
                    for item in eighty_final
                ]
            ),
            "age_bins": eighty_age_bins,
        },
        "recovered_80_crossings_per_trade": {
            **_quantiles(
                [float(value) for value in recovered80_counts]
            ),
            "zero_n": sum(value == 0 for value in recovered80_counts),
            "ge1_n": sum(value >= 1 for value in recovered80_counts),
            "ge3_n": sum(value >= 3 for value in recovered80_counts),
            "ge5_n": sum(value >= 5 for value in recovered80_counts),
            "max": max(recovered80_counts),
        },
        "v42_runner_close_timing": {
            "runner_close_n": len(runner_rows),
            "before_later_higher_peak_n": sum(
                item["runner_close_timing_vs_final_peak"]
                == "BEFORE_LATER_HIGHER_PEAK"
                for item in runner_rows
            ),
            "after_final_peak_n": sum(
                item["runner_close_timing_vs_final_peak"]
                == "AFTER_FINAL_PEAK"
                for item in runner_rows
            ),
            "failure_before_later_higher_peak_n": sum(
                bool(item["failure_lt75"])
                and item["runner_close_timing_vs_final_peak"]
                == "BEFORE_LATER_HIGHER_PEAK"
                for item in runner_rows
            ),
            "failure_after_final_peak_n": sum(
                bool(item["failure_lt75"])
                and item["runner_close_timing_vs_final_peak"]
                == "AFTER_FINAL_PEAK"
                for item in runner_rows
            ),
        },
        "stage3a_runner_trigger_delay_refinement": {
            "n": len(stage3a_runner_delay),
            "before_later_higher_peak_n": sum(
                item["runner_close_timing_vs_final_peak"]
                == "BEFORE_LATER_HIGHER_PEAK"
                for item in stage3a_runner_delay
            ),
            "after_final_peak_n": sum(
                item["runner_close_timing_vs_final_peak"]
                == "AFTER_FINAL_PEAK"
                for item in stage3a_runner_delay
            ),
        },
        "v42_small_reduce_timing": {
            "small_reduce_n": len(small_rows),
            "before_later_higher_peak_n": sum(
                item["small_reduce_timing_vs_final_peak"]
                == "BEFORE_LATER_HIGHER_PEAK"
                for item in small_rows
            ),
            "after_final_peak_n": sum(
                item["small_reduce_timing_vs_final_peak"]
                == "AFTER_FINAL_PEAK"
                for item in small_rows
            ),
        },
        "interpretation": {
            "fixed_80_trailing_is_not_safe": True,
            "reason": (
                "Most 80% running-peak crossings are transient and "
                "later recover to a new high."
            ),
            "stage3c_candidate_features": [
                "running_peak_regime",
                "seconds_since_running_peak",
                "downward_velocity_pp_per_sec",
                "reclaim_or_new_high behavior",
            ],
            "weak_feature_in_stage3b": (
                "monotonic_down_streak_count_alone"
            ),
            "runtime_change_authority": "NONE",
            "next_stage": "PP-V4-3C TEMPORAL REVERSAL DETECTOR",
        },
        "research_label_note": (
            "RECOVERED_NEW_HIGH and final observed peak use future "
            "historical path only as retrospective research labels. "
            "They are not causal runtime inputs."
        ),
    }

    return event_rows, trade_rows, summary


def write_csv(
    path: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--trades-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    events, trades, summary = build()
    write_csv(args.events_csv, events)
    write_csv(args.trades_csv, trades)
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
