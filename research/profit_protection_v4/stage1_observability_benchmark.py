from __future__ import annotations

import argparse
import json
import math
import statistics
from typing import Any

from market_radar.persistence import _postgres_connect, persistence_backend
from market_radar.profit_protection_v4_observer import (
    PREREGISTERED_GATES,
    pp_v4_start_ms,
    pp_v4_summary,
)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * max(0.0, min(1.0, float(q)))
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return ordered[lo]
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def capture_distribution(ratios: list[float]) -> dict[str, Any]:
    if not ratios:
        return {
            "n": 0,
            "mean_pct": None,
            "median_pct": None,
            "p10_pct": None,
            "p25_pct": None,
            "ge80_share_pct": None,
            "ge90_share_pct": None,
            "ge95_share_pct": None,
            "lt80_share_pct": None,
            "gt100_share_pct": None,
        }
    n = len(ratios)
    return {
        "n": n,
        "mean_pct": 100.0 * sum(ratios) / n,
        "median_pct": 100.0 * statistics.median(ratios),
        "p10_pct": 100.0 * float(percentile(ratios, 0.10)),
        "p25_pct": 100.0 * float(percentile(ratios, 0.25)),
        "ge80_share_pct": 100.0 * sum(value >= 0.80 for value in ratios) / n,
        "ge90_share_pct": 100.0 * sum(value >= 0.90 for value in ratios) / n,
        "ge95_share_pct": 100.0 * sum(value >= 0.95 for value in ratios) / n,
        "lt80_share_pct": 100.0 * sum(value < 0.80 for value in ratios) / n,
        "gt100_share_pct": 100.0 * sum(value > 1.00 for value in ratios) / n,
    }


def _chronological_thirds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (int(row["opened_at_ms"]), str(row["position_id"])))
    if not ordered:
        return {}
    n = len(ordered)
    result: dict[str, Any] = {}
    for name, left, right in (
        ("EARLY", 0, n // 3),
        ("MID", n // 3, 2 * n // 3),
        ("LATE", 2 * n // 3, n),
    ):
        subset = ordered[left:right]
        old_ratios = [float(row["old15_capture_ratio"]) for row in subset]
        v4_ratios = [float(row["v4_capture_ratio"]) for row in subset]
        old_dist = capture_distribution(old_ratios)
        v4_dist = capture_distribution(v4_ratios)
        result[name] = {
            "n": len(subset),
            "old15": old_dist,
            "v4": v4_dist,
            "delta": {
                "ge90_share_pp": (
                    None
                    if not subset
                    else float(v4_dist["ge90_share_pct"]) - float(old_dist["ge90_share_pct"])
                ),
                "lt80_share_pp": (
                    None
                    if not subset
                    else float(v4_dist["lt80_share_pct"]) - float(old_dist["lt80_share_pct"])
                ),
                "p10_pp": (
                    None
                    if not subset
                    else float(v4_dist["p10_pct"]) - float(old_dist["p10_pct"])
                ),
                "p25_pp": (
                    None
                    if not subset
                    else float(v4_dist["p25_pct"]) - float(old_dist["p25_pct"])
                ),
            },
        }
    return result


def evaluate_rows(rows: list[dict[str, Any]], *, data_quality: dict[str, Any]) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if float(row["true_mfe_pct"]) >= 0.30
        and row.get("v4_peak_pct") is not None
        and row.get("old15_peak_pct") is not None
    ]
    for row in eligible:
        true_mfe = float(row["true_mfe_pct"])
        row["v4_capture_ratio"] = float(row["v4_peak_pct"]) / true_mfe
        row["old15_capture_ratio"] = float(row["old15_peak_pct"]) / true_mfe

    v4_ratios = [float(row["v4_capture_ratio"]) for row in eligible]
    old_ratios = [float(row["old15_capture_ratio"]) for row in eligible]
    v4_dist = capture_distribution(v4_ratios)
    old_dist = capture_distribution(old_ratios)

    old_aggregate = (
        100.0 * sum(float(row["old15_peak_pct"]) for row in eligible)
        / sum(float(row["true_mfe_pct"]) for row in eligible)
        if eligible
        else None
    )
    v4_aggregate = (
        100.0 * sum(float(row["v4_peak_pct"]) for row in eligible)
        / sum(float(row["true_mfe_pct"]) for row in eligible)
        if eligible
        else None
    )

    delta = {
        "median_capture_uplift_pp": (
            None
            if not eligible
            else float(v4_dist["median_pct"]) - float(old_dist["median_pct"])
        ),
        "aggregate_capture_uplift_pp": (
            None if not eligible else float(v4_aggregate) - float(old_aggregate)
        ),
        "ge90_share_uplift_pp": (
            None
            if not eligible
            else float(v4_dist["ge90_share_pct"]) - float(old_dist["ge90_share_pct"])
        ),
        "lt80_share_reduction_pp": (
            None
            if not eligible
            else float(old_dist["lt80_share_pct"]) - float(v4_dist["lt80_share_pct"])
        ),
        "p10_uplift_pp": (
            None if not eligible else float(v4_dist["p10_pct"]) - float(old_dist["p10_pct"])
        ),
        "p25_uplift_pp": (
            None if not eligible else float(v4_dist["p25_pct"]) - float(old_dist["p25_pct"])
        ),
    }

    qgate = PREREGISTERED_GATES["data_quality"]
    cohort_ready = (
        len(rows) >= int(PREREGISTERED_GATES["minimum_closed_matched_trades"])
        and len(eligible) >= int(PREREGISTERED_GATES["minimum_true_mfe_ge_0_30_trades"])
    )
    data_quality_pass = (
        float(data_quality.get("cycle_error_rate_pct") or 0.0)
        <= float(qgate["cycle_error_rate_max_pct"])
        and float(data_quality.get("missing_position_rate_pct") or 0.0)
        <= float(qgate["missing_position_rate_max_pct"])
        and (
            data_quality.get("cycle_gap_ms", {}).get("median") is None
            or float(data_quality["cycle_gap_ms"]["median"])
            <= float(qgate["median_cycle_gap_max_ms"])
        )
        and (
            data_quality.get("cycle_gap_ms", {}).get("p90") is None
            or float(data_quality["cycle_gap_ms"]["p90"])
            <= float(qgate["p90_cycle_gap_max_ms"])
        )
        and (
            data_quality.get("cycle_gap_ms", {}).get("max") is None
            or float(data_quality["cycle_gap_ms"]["max"])
            <= float(qgate["max_cycle_gap_ms"])
        )
    )

    v42 = PREREGISTERED_GATES["v4_2_observability"]
    v43 = PREREGISTERED_GATES["v4_3_distribution"]
    chronological = _chronological_thirds(eligible)
    late = chronological.get("LATE") or {}
    late_delta = late.get("delta") or {}

    v42_pass = bool(
        cohort_ready
        and data_quality_pass
        and delta["median_capture_uplift_pp"] is not None
        and float(delta["median_capture_uplift_pp"]) >= float(v42["median_capture_uplift_min_pp"])
        and float(delta["aggregate_capture_uplift_pp"]) >= float(v42["weighted_capture_uplift_min_pp"])
    )
    v43_pass = bool(
        v42_pass
        and float(delta["ge90_share_uplift_pp"]) >= float(v43["ge90_share_uplift_min_pp"])
        and float(delta["lt80_share_reduction_pp"]) >= float(v43["lt80_share_reduction_min_pp"])
        and float(delta["p10_uplift_pp"]) >= float(v43["p10_uplift_min_pp"])
        and float(delta["p25_uplift_pp"]) >= float(v43["p25_uplift_min_pp"])
        and late_delta.get("ge90_share_pp") is not None
        and float(late_delta["ge90_share_pp"]) >= float(v43["late_cohort_ge90_uplift_min_pp"])
        and float(late_delta["lt80_share_pp"]) <= float(v43["late_cohort_lt80_change_max_pp"])
    )

    return {
        "matched_closed_trades": len(rows),
        "eligible_true_mfe_ge_0_30": len(eligible),
        "cohort_ready": cohort_ready,
        "data_quality_pass": data_quality_pass,
        "old15": {
            **old_dist,
            "aggregate_capture_pct": old_aggregate,
        },
        "v4": {
            **v4_dist,
            "aggregate_capture_pct": v4_aggregate,
        },
        "delta": delta,
        "chronological_thirds": chronological,
        "gates": {
            "v4_2_observability_pass": v42_pass,
            "v4_3_distribution_pass": v43_pass,
        },
    }


def load_matched_rows(start_ms: int) -> list[dict[str, Any]]:
    if persistence_backend() != "postgres":
        raise RuntimeError("V4 Stage1 benchmark currently requires the core-prod Postgres dataset")

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with closed as (
                    select position_id,symbol,side,opened_at_ms,closed_at_ms
                    from positions
                    where mode='PAPER'
                      and status='CLOSED'
                      and opened_at_ms>%s
                ),
                mfe as (
                    select position_id,max(mfe_pct) as true_mfe_pct
                    from position_evaluations
                    group by position_id
                ),
                v4 as (
                    select position_id,max(current_pnl_pct) as v4_peak_pct,
                           count(*) as v4_observations
                    from pp_v4_peak_observations
                    group by position_id
                ),
                old15 as (
                    select position_id,max(current_pnl_pct) as old15_peak_pct,
                           count(*) as old15_observations
                    from pp_decision_v2_observations
                    group by position_id
                )
                select c.position_id,c.symbol,c.side,c.opened_at_ms,c.closed_at_ms,
                       m.true_mfe_pct,v.v4_peak_pct,o.old15_peak_pct,
                       v.v4_observations,o.old15_observations
                from closed c
                join mfe m on m.position_id=c.position_id
                join v4 v on v.position_id=c.position_id
                join old15 o on o.position_id=c.position_id
                order by c.opened_at_ms,c.position_id
                """,
                (int(start_ms),),
            )
            return [
                {
                    "position_id": row[0],
                    "symbol": row[1],
                    "side": row[2],
                    "opened_at_ms": int(row[3]),
                    "closed_at_ms": int(row[4]),
                    "true_mfe_pct": float(row[5]),
                    "v4_peak_pct": float(row[6]),
                    "old15_peak_pct": float(row[7]),
                    "v4_observations": int(row[8]),
                    "old15_observations": int(row[9]),
                }
                for row in cur.fetchall()
            ]


def build_snapshot(start_ms: int | None = None) -> dict[str, Any]:
    boundary = int(start_ms or pp_v4_start_ms())
    if boundary <= 0:
        return {
            "stage": "PP-V4-1",
            "status": "WAITING_FOR_START_BOUNDARY",
            "start_ms": boundary,
            "preregistered_gates": PREREGISTERED_GATES,
        }
    quality = pp_v4_summary()
    rows = load_matched_rows(boundary)
    evaluation = evaluate_rows(rows, data_quality=quality)
    return {
        "stage": "PP-V4-1",
        "status": "READY_FOR_GATE" if evaluation["cohort_ready"] else "COLLECTING",
        "start_ms": boundary,
        "data_quality": quality,
        "evaluation": evaluation,
        "preregistered_gates": PREREGISTERED_GATES,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    payload = build_snapshot(args.start_ms or None)
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
