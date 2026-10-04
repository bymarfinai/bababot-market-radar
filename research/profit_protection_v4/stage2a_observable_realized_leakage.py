from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2a_observable_realized_leakage_evidence.json"
)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "min": None,
            "max": None,
            "sum": None,
        }
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "min": min(values),
        "max": max(values),
        "sum": sum(values),
    }


def group_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [
        row for row in rows
        if float(row["observable_net_peak_pct"]) > 0.0
    ]
    retention = [
        float(row["net_retention_ratio"])
        for row in positive
        if row.get("net_retention_ratio") is not None
    ]
    return {
        "n": len(rows),
        "positive_net_peak_n": len(positive),
        "net_peak_pct": describe(
            [float(row["observable_net_peak_pct"]) for row in rows]
        ),
        "realized_pct": describe(
            [float(row["actual_realized_net_pct"]) for row in rows]
        ),
        "leakage_pp": describe(
            [float(row["net_leakage_pp"]) for row in rows]
        ),
        "retention_ratio": describe(retention),
        "retention_ge90_share_pct": (
            100.0 * sum(value >= 0.90 for value in retention) / len(retention)
            if retention else None
        ),
        "retention_ge80_share_pct": (
            100.0 * sum(value >= 0.80 for value in retention) / len(retention)
            if retention else None
        ),
        "retention_50_80_share_pct": (
            100.0 * sum(0.50 <= value < 0.80 for value in retention)
            / len(retention)
            if retention else None
        ),
        "retention_0_50_share_pct": (
            100.0 * sum(0.0 <= value < 0.50 for value in retention)
            / len(retention)
            if retention else None
        ),
        "retention_negative_share_pct": (
            100.0 * sum(value < 0.0 for value in retention) / len(retention)
            if retention else None
        ),
        "sum_observable_net_peak_usdt": sum(
            float(row["observable_net_peak_usdt"]) for row in rows
        ),
        "sum_realized_usdt": sum(
            float(row["realized_pnl_usdt"]) for row in rows
        ),
        "sum_net_leakage_usdt": sum(
            float(row["observable_net_peak_usdt"])
            - float(row["realized_pnl_usdt"])
            for row in rows
        ),
    }


def band(value: float, bounds: list[tuple[float, float | None, str]]) -> str:
    for low, high, label in bounds:
        if value >= low and (high is None or value < high):
            return label
    return "OTHER"


def timing_metrics(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    hits = [
        row["thresholds"][key]
        for row in rows
        if row.get("thresholds", {}).get(key) is not None
    ]
    return {
        "crossed_n": len(hits),
        "crossed_share_pct": 100.0 * len(hits) / len(rows),
        "seconds_from_peak": describe(
            [float(hit["seconds_from_peak"]) for hit in hits]
        ),
        "seconds_to_close_after_cross": describe(
            [float(hit["seconds_to_close"]) for hit in hits]
        ),
    }


def build_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mfe_bounds = [
        (0.30, 0.50, "0.30-0.50"),
        (0.50, 1.00, "0.50-1.00"),
        (1.00, 2.00, "1.00-2.00"),
        (2.00, None, ">=2.00"),
    ]
    peak_bounds = [
        (-1e9, 0.0, "<=0"),
        (0.0, 0.30, "0-0.30"),
        (0.30, 0.50, "0.30-0.50"),
        (0.50, 1.00, "0.50-1.00"),
        (1.00, 2.00, "1.00-2.00"),
        (2.00, None, ">=2.00"),
    ]

    protectable_030 = [
        row for row in rows
        if float(row["observable_net_peak_pct"]) >= 0.30
    ]
    protectable_050 = [
        row for row in rows
        if float(row["observable_net_peak_pct"]) >= 0.50
    ]

    mean_obs_gap = statistics.mean(
        float(row["positive_observability_gap_pp"]) for row in rows
    )
    mean_leakage = statistics.mean(
        float(row["net_leakage_pp"]) for row in rows
    )
    sum_obs_gap = sum(
        float(row["positive_observability_gap_pp"]) for row in rows
    )
    sum_positive_leakage = sum(
        max(0.0, float(row["net_leakage_pp"])) for row in rows
    )

    top20 = sorted(
        rows,
        key=lambda row: float(row["net_leakage_pp"]),
        reverse=True,
    )[:20]

    severity = {
        "net_peak_ge030_realized_le0_n": sum(
            float(row["observable_net_peak_pct"]) >= 0.30
            and float(row["actual_realized_net_pct"]) <= 0.0
            for row in rows
        ),
        "net_peak_ge050_realized_le0_n": sum(
            float(row["observable_net_peak_pct"]) >= 0.50
            and float(row["actual_realized_net_pct"]) <= 0.0
            for row in rows
        ),
        "net_peak_ge100_realized_le0_n": sum(
            float(row["observable_net_peak_pct"]) >= 1.00
            and float(row["actual_realized_net_pct"]) <= 0.0
            for row in rows
        ),
        "net_peak_ge200_realized_le0_n": sum(
            float(row["observable_net_peak_pct"]) >= 2.00
            and float(row["actual_realized_net_pct"]) <= 0.0
            for row in rows
        ),
        "net_peak_ge050_retention_lt50_n": sum(
            float(row["observable_net_peak_pct"]) >= 0.50
            and row.get("net_retention_ratio") is not None
            and float(row["net_retention_ratio"]) < 0.50
            for row in rows
        ),
        "net_peak_ge050_retention_lt80_n": sum(
            float(row["observable_net_peak_pct"]) >= 0.50
            and row.get("net_retention_ratio") is not None
            and float(row["net_retention_ratio"]) < 0.80
            for row in rows
        ),
    }

    evidence_for_frontier = (
        len(protectable_050) >= 30
        and severity["net_peak_ge050_retention_lt80_n"] >= 20
    )

    return {
        "stage": "PP-V4-2A",
        "status": "COMPLETE_RESEARCH_ONLY",
        "population": {
            "n": len(rows),
            "positive_observable_net_peak_n": sum(
                float(row["observable_net_peak_pct"]) > 0.0 for row in rows
            ),
            "observable_net_peak_ge030_n": len(protectable_030),
            "observable_net_peak_ge050_n": len(protectable_050),
            "peak_after_prior_reduce_n": sum(
                int(row["reductions_before_peak"]) > 0 for row in rows
            ),
        },
        "overall": group_metrics(rows),
        "protectable_ge030": group_metrics(protectable_030),
        "protectable_ge050": group_metrics(protectable_050),
        "observability_vs_realization": {
            "positive_observability_gap_pp": describe(
                [
                    float(row["positive_observability_gap_pp"])
                    for row in rows
                ]
            ),
            "net_leakage_pp": describe(
                [float(row["net_leakage_pp"]) for row in rows]
            ),
            "mean_positive_observability_gap_pp": mean_obs_gap,
            "mean_net_leakage_pp": mean_leakage,
            "mean_leakage_to_observability_gap_ratio": (
                mean_leakage / mean_obs_gap if mean_obs_gap > 0 else None
            ),
            "sum_positive_observability_gap_pp": sum_obs_gap,
            "sum_positive_net_leakage_pp": sum_positive_leakage,
            "sum_leakage_to_observability_gap_ratio": (
                sum_positive_leakage / sum_obs_gap if sum_obs_gap > 0 else None
            ),
        },
        "missed_profit_severity": severity,
        "timing": {
            key: timing_metrics(rows, key)
            for key in ("r90", "r80", "r70", "r50", "breakeven")
        },
        "peak_to_close_seconds": describe(
            [float(row["peak_to_close_seconds"]) for row in rows]
        ),
        "peak_age_seconds": describe(
            [float(row["peak_age_seconds"]) for row in rows]
        ),
        "by_side": {
            side: group_metrics(
                [row for row in rows if str(row["side"]).upper() == side]
            )
            for side in ("LONG", "SHORT")
        },
        "by_clean_mfe_band": {
            label: group_metrics(
                [
                    row for row in rows
                    if band(float(row["clean_mfe_pct"]), mfe_bounds) == label
                ]
            )
            for _, _, label in mfe_bounds
        },
        "by_observable_net_peak_band": {
            label: group_metrics(
                [
                    row for row in rows
                    if band(
                        float(row["observable_net_peak_pct"]),
                        peak_bounds,
                    ) == label
                ]
            )
            for _, _, label in peak_bounds
        },
        "runner_ge1": group_metrics(
            [
                row for row in rows
                if float(row["observable_net_peak_pct"]) >= 1.00
            ]
        ),
        "runner_ge2": group_metrics(
            [
                row for row in rows
                if float(row["observable_net_peak_pct"]) >= 2.00
            ]
        ),
        "close_reasons": dict(
            Counter(str(row["close_reason"]) for row in rows)
        ),
        "top20_net_leakage": [
            {
                key: row[key]
                for key in (
                    "position_id",
                    "symbol",
                    "side",
                    "clean_mfe_pct",
                    "observable_gross_peak_pct",
                    "observable_net_peak_pct",
                    "actual_realized_net_pct",
                    "net_leakage_pp",
                    "net_retention_ratio",
                    "peak_to_close_seconds",
                    "reductions_before_peak",
                )
            }
            for row in top20
        ],
        "decision": {
            "leakage_is_larger_than_remaining_observability_gap": (
                mean_leakage > mean_obs_gap
            ),
            "proceed_to_v4_2b_optimal_protection_frontier": evidence_for_frontier,
            "protection_authority": "NONE",
            "runtime_change_authority": "NONE",
            "next_stage": (
                "V4-2B_OPTIMAL_PROTECTION_FRONTIER"
                if evidence_for_frontier
                else "MORE_LEAKAGE_EVIDENCE"
            ),
            "threshold_selected": None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    rows = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    result = build_result(rows)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
