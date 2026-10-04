from __future__ import annotations

import argparse
import json
import math
import statistics
from typing import Any, Callable

from market_radar.persistence import _postgres_connect, persistence_backend
from market_radar.profit_protection_v4_observer import PREREGISTERED_GATES


HISTORICAL_5S_LAST_OBSERVED_AT_MS = 1791043570111
MFE_MIN_PCT = 0.30
MAX_FIRST_5S_LAG_MS = 6_000
MAX_LAST_5S_LAG_MS = 6_000
MAX_FIRST_15S_LAG_MS = 20_000
MAX_LAST_15S_LAG_MS = 20_000


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


def distribution(ratios: list[float]) -> dict[str, Any]:
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
        "mean_pct": 100.0 * statistics.mean(ratios),
        "median_pct": 100.0 * statistics.median(ratios),
        "p10_pct": 100.0 * float(percentile(ratios, 0.10)),
        "p25_pct": 100.0 * float(percentile(ratios, 0.25)),
        "ge80_share_pct": 100.0 * sum(value >= 0.80 for value in ratios) / n,
        "ge90_share_pct": 100.0 * sum(value >= 0.90 for value in ratios) / n,
        "ge95_share_pct": 100.0 * sum(value >= 0.95 for value in ratios) / n,
        "lt80_share_pct": 100.0 * sum(value < 0.80 for value in ratios) / n,
        "gt100_share_pct": 100.0 * sum(value > 1.00 for value in ratios) / n,
    }


def load_historical_rows() -> list[dict[str, Any]]:
    if persistence_backend() != "postgres":
        raise RuntimeError("V4-1H requires the core-prod Postgres research dataset")

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    p.position_id,
                    p.symbol,
                    p.side,
                    p.opened_at_ms,
                    p.closed_at_ms,
                    p.realized_pnl_pct,
                    f.peak5,
                    f.n5,
                    f.first5,
                    f.last5,
                    f.medgap5,
                    t.peak15,
                    t.n15,
                    t.first15,
                    t.last15,
                    m.true_mfe,
                    m.mfe_first_seen_ms
                from positions p
                join lateral (
                    select
                        max(current_pnl_pct) as peak5,
                        count(*) as n5,
                        min(observed_at_ms) as first5,
                        max(observed_at_ms) as last5,
                        percentile_cont(0.5) within group(order by sample_gap_ms)
                            filter(where sample_gap_ms is not null) as medgap5
                    from pp_v3_fast_peak_observations o
                    where o.position_id=p.position_id
                      and o.observed_at_ms between p.opened_at_ms and p.closed_at_ms
                ) f on f.n5 > 0
                join lateral (
                    select
                        max(current_pnl_pct) as peak15,
                        count(*) as n15,
                        min(evaluated_at_ms) as first15,
                        max(evaluated_at_ms) as last15
                    from pp_decision_v2_observations o
                    where o.position_id=p.position_id
                      and o.evaluated_at_ms between p.opened_at_ms and p.closed_at_ms
                ) t on t.n15 > 0
                join lateral (
                    select
                        max(e.mfe_pct) as true_mfe,
                        min(e.evaluated_at_ms) filter (
                            where e.mfe_pct >= (
                                select max(e2.mfe_pct)
                                from position_evaluations e2
                                where e2.position_id=p.position_id
                            ) - 1e-12
                        ) as mfe_first_seen_ms
                    from position_evaluations e
                    where e.position_id=p.position_id
                ) m on m.true_mfe is not null
                where p.status='CLOSED'
                  and p.mode='PAPER'
                order by p.opened_at_ms,p.position_id
                """
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def strict_coverage(row: dict[str, Any]) -> bool:
    if float(row["true_mfe"]) < MFE_MIN_PCT:
        return False
    if int(row["first5"]) - int(row["opened_at_ms"]) > MAX_FIRST_5S_LAG_MS:
        return False
    if int(row["closed_at_ms"]) - int(row["last5"]) > MAX_LAST_5S_LAG_MS:
        return False
    if int(row["first15"]) - int(row["opened_at_ms"]) > MAX_FIRST_15S_LAG_MS:
        return False
    if int(row["closed_at_ms"]) - int(row["last15"]) > MAX_LAST_15S_LAG_MS:
        return False
    return True


def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        true_mfe = float(row["true_mfe"])
        row["capture_5s_ratio"] = float(row["peak5"]) / true_mfe
        row["capture_15s_ratio"] = float(row["peak15"]) / true_mfe
        row["capture_delta_ratio"] = (
            row["capture_5s_ratio"] - row["capture_15s_ratio"]
        )
        duration = max(1, int(row["closed_at_ms"]) - int(row["opened_at_ms"]))
        mfe_seen = row.get("mfe_first_seen_ms")
        row["mfe_age_ratio"] = (
            None
            if mfe_seen is None
            else (int(mfe_seen) - int(row["opened_at_ms"])) / duration
        )
        output.append(row)
    return output


def group_delta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    old = distribution([float(row["capture_15s_ratio"]) for row in rows])
    new = distribution([float(row["capture_5s_ratio"]) for row in rows])
    true_sum = sum(float(row["true_mfe"]) for row in rows)
    old_aggregate = 100.0 * sum(float(row["peak15"]) for row in rows) / true_sum
    new_aggregate = 100.0 * sum(float(row["peak5"]) for row in rows) / true_sum
    return {
        "n": len(rows),
        "old15": {**old, "aggregate_capture_pct": old_aggregate},
        "fast5": {**new, "aggregate_capture_pct": new_aggregate},
        "delta": {
            "mean_capture_pp": float(new["mean_pct"]) - float(old["mean_pct"]),
            "median_capture_pp": float(new["median_pct"]) - float(old["median_pct"]),
            "p10_capture_pp": float(new["p10_pct"]) - float(old["p10_pct"]),
            "p25_capture_pp": float(new["p25_pct"]) - float(old["p25_pct"]),
            "ge80_share_pp": float(new["ge80_share_pct"]) - float(old["ge80_share_pct"]),
            "ge90_share_pp": float(new["ge90_share_pct"]) - float(old["ge90_share_pct"]),
            "ge95_share_pp": float(new["ge95_share_pct"]) - float(old["ge95_share_pct"]),
            "lt80_reduction_pp": float(old["lt80_share_pct"]) - float(new["lt80_share_pct"]),
            "aggregate_capture_pp": new_aggregate - old_aggregate,
        },
    }


def chronological_thirds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        rows,
        key=lambda row: (int(row["opened_at_ms"]), str(row["position_id"])),
    )
    n = len(ordered)
    return {
        "EARLY": group_delta(ordered[: n // 3]),
        "MID": group_delta(ordered[n // 3 : 2 * n // 3]),
        "LATE": group_delta(ordered[2 * n // 3 :]),
    }


def split_by(
    rows: list[dict[str, Any]],
    groups: list[tuple[str, Callable[[dict[str, Any]], bool]]],
) -> dict[str, Any]:
    return {
        name: group_delta([row for row in rows if predicate(row)])
        for name, predicate in groups
    }


def build_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mfe_eligible = [row for row in rows if float(row["true_mfe"]) >= MFE_MIN_PCT]
    strict = enrich([row for row in mfe_eligible if strict_coverage(row)])
    overall = group_delta(strict)

    capture_deltas = [float(row["capture_delta_ratio"]) for row in strict]
    medgaps = [
        float(row["medgap5"])
        for row in strict
        if row.get("medgap5") is not None
    ]

    gates = PREREGISTERED_GATES
    delta = overall["delta"]
    v42 = gates["v4_2_observability"]
    v43 = gates["v4_3_distribution"]

    gate_diagnostic = {
        "retrospective_only": True,
        "v4_2": {
            "median_capture_pass": delta["median_capture_pp"]
            >= float(v42["median_capture_uplift_min_pp"]),
            "aggregate_capture_pass": delta["aggregate_capture_pp"]
            >= float(v42["weighted_capture_uplift_min_pp"]),
        },
        "v4_3": {
            "ge90_share_pass": delta["ge90_share_pp"]
            >= float(v43["ge90_share_uplift_min_pp"]),
            "lt80_reduction_pass": delta["lt80_reduction_pp"]
            >= float(v43["lt80_share_reduction_min_pp"]),
            "p10_pass": delta["p10_capture_pp"]
            >= float(v43["p10_uplift_min_pp"]),
            "p25_pass": delta["p25_capture_pp"]
            >= float(v43["p25_uplift_min_pp"]),
        },
    }
    gate_diagnostic["v4_2"]["all_pass"] = all(
        gate_diagnostic["v4_2"].values()
    )
    gate_diagnostic["v4_3"]["all_distribution_pass"] = all(
        gate_diagnostic["v4_3"].values()
    )

    return {
        "stage": "PP-V4-1H",
        "status": "COMPLETE_RETROSPECTIVE_DIAGNOSTIC",
        "historical_5s_last_observed_at_ms": HISTORICAL_5S_LAST_OBSERVED_AT_MS,
        "population": {
            "matched_5s_15s_mfe_closed_paper": len(rows),
            "true_mfe_ge_0_30": len(mfe_eligible),
            "strict_full_lifecycle_coverage": len(strict),
        },
        "coverage_contract": {
            "mfe_min_pct": MFE_MIN_PCT,
            "max_first_5s_lag_ms": MAX_FIRST_5S_LAG_MS,
            "max_last_5s_lag_ms": MAX_LAST_5S_LAG_MS,
            "max_first_15s_lag_ms": MAX_FIRST_15S_LAG_MS,
            "max_last_15s_lag_ms": MAX_LAST_15S_LAG_MS,
            "observation_peaks_restricted_to_position_lifetime": True,
        },
        "overall": overall,
        "per_trade_delta": {
            "improved": sum(value > 1e-12 for value in capture_deltas),
            "equal": sum(abs(value) <= 1e-12 for value in capture_deltas),
            "worse": sum(value < -1e-12 for value in capture_deltas),
            "median_pp": 100.0 * statistics.median(capture_deltas),
            "p10_pp": 100.0 * float(percentile(capture_deltas, 0.10)),
            "p25_pp": 100.0 * float(percentile(capture_deltas, 0.25)),
            "p90_pp": 100.0 * float(percentile(capture_deltas, 0.90)),
        },
        "rescue": {
            "old15_lt80": sum(row["capture_15s_ratio"] < 0.80 for row in strict),
            "old15_lt80_to_5s_ge80": sum(
                row["capture_15s_ratio"] < 0.80
                and row["capture_5s_ratio"] >= 0.80
                for row in strict
            ),
            "old15_lt80_to_5s_ge90": sum(
                row["capture_15s_ratio"] < 0.80
                and row["capture_5s_ratio"] >= 0.90
                for row in strict
            ),
            "old15_lt90": sum(row["capture_15s_ratio"] < 0.90 for row in strict),
            "old15_lt90_to_5s_ge90": sum(
                row["capture_15s_ratio"] < 0.90
                and row["capture_5s_ratio"] >= 0.90
                for row in strict
            ),
            "old15_ge90_to_5s_lt90": sum(
                row["capture_15s_ratio"] >= 0.90
                and row["capture_5s_ratio"] < 0.90
                for row in strict
            ),
        },
        "by_side": split_by(
            strict,
            [
                ("LONG", lambda row: str(row["side"]).upper() == "LONG"),
                ("SHORT", lambda row: str(row["side"]).upper() == "SHORT"),
            ],
        ),
        "chronological_thirds": chronological_thirds(strict),
        "by_mfe_timing": split_by(
            strict,
            [
                (
                    "MFE_EARLY_FIRST_25PCT_DURATION",
                    lambda row: row["mfe_age_ratio"] is not None
                    and float(row["mfe_age_ratio"]) <= 0.25,
                ),
                (
                    "MFE_LATE_AFTER_25PCT_DURATION",
                    lambda row: row["mfe_age_ratio"] is not None
                    and float(row["mfe_age_ratio"]) > 0.25,
                ),
            ],
        ),
        "coverage_quality": {
            "first_5s_after_open_median_s": statistics.median(
                [
                    (int(row["first5"]) - int(row["opened_at_ms"])) / 1000.0
                    for row in strict
                ]
            ),
            "first_5s_after_open_p90_s": percentile(
                [
                    (int(row["first5"]) - int(row["opened_at_ms"])) / 1000.0
                    for row in strict
                ],
                0.90,
            ),
            "last_5s_before_close_median_s": statistics.median(
                [
                    (int(row["closed_at_ms"]) - int(row["last5"])) / 1000.0
                    for row in strict
                ]
            ),
            "last_5s_before_close_p90_s": percentile(
                [
                    (int(row["closed_at_ms"]) - int(row["last5"])) / 1000.0
                    for row in strict
                ],
                0.90,
            ),
            "median_trade_median_5s_gap_ms": statistics.median(medgaps),
            "p90_trade_median_5s_gap_ms": percentile(medgaps, 0.90),
            "median_5s_observations_per_trade": statistics.median(
                [int(row["n5"]) for row in strict]
            ),
            "median_15s_observations_per_trade": statistics.median(
                [int(row["n15"]) for row in strict]
            ),
        },
        "preregistered_gate_diagnostic": gate_diagnostic,
        "interpretation": {
            "v4_2_direction_supported": bool(
                gate_diagnostic["v4_2"]["all_pass"]
            ),
            "v4_3_full_distribution_target_supported": bool(
                gate_diagnostic["v4_3"]["all_distribution_pass"]
            ),
            "blocking_metric": (
                None
                if gate_diagnostic["v4_3"]["all_distribution_pass"]
                else "P10 capture uplift remains below preregistered +5pp target"
            ),
            "promotion_authority": "NONE_RETROSPECTIVE_ONLY",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = build_result(load_historical_rows())
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
