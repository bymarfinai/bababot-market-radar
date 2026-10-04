from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from market_radar.profit_protection_v4_observer import PREREGISTERED_GATES


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1j_clean_post_entry_mfe_evidence.json"
)
CLEAN_MFE_ARM_PCT = 0.30


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


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
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
    n = len(values)
    return {
        "n": n,
        "mean_pct": 100.0 * statistics.mean(values),
        "median_pct": 100.0 * statistics.median(values),
        "p10_pct": 100.0 * float(percentile(values, 0.10)),
        "p25_pct": 100.0 * float(percentile(values, 0.25)),
        "ge80_share_pct": 100.0 * sum(value >= 0.80 for value in values) / n,
        "ge90_share_pct": 100.0 * sum(value >= 0.90 for value in values) / n,
        "ge95_share_pct": 100.0 * sum(value >= 0.95 for value in values) / n,
        "lt80_share_pct": 100.0 * sum(value < 0.80 for value in values) / n,
        "gt100_share_pct": 100.0 * sum(value > 1.00 for value in values) / n,
    }


def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        clean_mfe = float(source["clean_post_entry_mfe_pct"])
        if clean_mfe < CLEAN_MFE_ARM_PCT:
            continue
        row = dict(source)
        row["capture_5s_ratio"] = float(row["peak5"]) / clean_mfe
        row["capture_15s_ratio"] = float(row["peak15"]) / clean_mfe
        row["capture_delta_ratio"] = (
            row["capture_5s_ratio"] - row["capture_15s_ratio"]
        )
        output.append(row)
    return output


def group_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    old15 = distribution([float(row["capture_15s_ratio"]) for row in rows])
    fast5 = distribution([float(row["capture_5s_ratio"]) for row in rows])
    denominator = sum(float(row["clean_post_entry_mfe_pct"]) for row in rows)
    aggregate15 = 100.0 * sum(float(row["peak15"]) for row in rows) / denominator
    aggregate5 = 100.0 * sum(float(row["peak5"]) for row in rows) / denominator
    return {
        "n": len(rows),
        "old15": {**old15, "aggregate_capture_pct": aggregate15},
        "fast5": {**fast5, "aggregate_capture_pct": aggregate5},
        "delta": {
            "mean_capture_pp": float(fast5["mean_pct"]) - float(old15["mean_pct"]),
            "median_capture_pp": float(fast5["median_pct"]) - float(old15["median_pct"]),
            "p10_capture_pp": float(fast5["p10_pct"]) - float(old15["p10_pct"]),
            "p25_capture_pp": float(fast5["p25_pct"]) - float(old15["p25_pct"]),
            "ge80_share_pp": float(fast5["ge80_share_pct"]) - float(old15["ge80_share_pct"]),
            "ge90_share_pp": float(fast5["ge90_share_pct"]) - float(old15["ge90_share_pct"]),
            "ge95_share_pp": float(fast5["ge95_share_pct"]) - float(old15["ge95_share_pct"]),
            "lt80_reduction_pp": float(old15["lt80_share_pct"]) - float(fast5["lt80_share_pct"]),
            "aggregate_capture_pp": aggregate5 - aggregate15,
        },
    }


def chronological_thirds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        rows,
        key=lambda row: (int(row["opened_at_ms"]), str(row["position_id"])),
    )
    n = len(ordered)
    return {
        "EARLY": group_result(ordered[: n // 3]),
        "MID": group_result(ordered[n // 3 : 2 * n // 3]),
        "LATE": group_result(ordered[2 * n // 3 :]),
    }


def build_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = enrich(rows)
    overall = group_result(clean)
    thirds = chronological_thirds(clean)
    long_rows = [row for row in clean if str(row["side"]).upper() == "LONG"]
    short_rows = [row for row in clean if str(row["side"]).upper() == "SHORT"]

    old_false_eligible = [
        row
        for row in rows
        if float(row["old_mfe"]) >= CLEAN_MFE_ARM_PCT
        and float(row["clean_post_entry_mfe_pct"]) < CLEAN_MFE_ARM_PCT
    ]
    new_only = [
        row
        for row in rows
        if float(row["old_mfe"]) < CLEAN_MFE_ARM_PCT
        and float(row["clean_post_entry_mfe_pct"]) >= CLEAN_MFE_ARM_PCT
    ]

    deltas = [float(row["capture_delta_ratio"]) for row in clean]
    v42 = PREREGISTERED_GATES["v4_2_observability"]
    v43 = PREREGISTERED_GATES["v4_3_distribution"]
    delta = overall["delta"]
    late_delta = thirds["LATE"]["delta"]

    gate = {
        "cohort": {
            "closed_matched_pass": len(rows)
            >= int(PREREGISTERED_GATES["minimum_closed_matched_trades"]),
            "true_mfe_ge_0_30_pass": len(clean)
            >= int(PREREGISTERED_GATES["minimum_true_mfe_ge_0_30_trades"]),
        },
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
            "late_ge90_non_decrease_pass": late_delta["ge90_share_pp"]
            >= float(v43["late_cohort_ge90_uplift_min_pp"]),
            "late_lt80_non_increase_pass": (
                -late_delta["lt80_reduction_pp"]
                <= float(v43["late_cohort_lt80_change_max_pp"])
            ),
        },
    }
    gate["cohort"]["all_pass"] = all(gate["cohort"].values())
    gate["v4_2"]["all_pass"] = all(gate["v4_2"].values())
    gate["v4_3"]["all_pass"] = all(gate["v4_3"].values())

    return {
        "stage": "PP-V4-1J",
        "status": "COMPLETE_CLEAN_LABEL_REBUILD",
        "label_contract": {
            "mfe_definition": "maximum favorable traded-price excursion strictly after opened_at_ms",
            "partial_boundary_minutes": "Binance USD-M aggregate trades",
            "full_in_lifecycle_minutes": "Binance USD-M 1m klines",
            "entry_price_included_as_zero_excursion_baseline": True,
            "clean_mfe_arm_pct": CLEAN_MFE_ARM_PCT,
        },
        "population": {
            "strict_matched_5s_15s_rows": len(rows),
            "clean_mfe_ge_0_30": len(clean),
            "old_mfe_ge_0_30_but_clean_lt_0_30": len(old_false_eligible),
            "old_mfe_lt_0_30_but_clean_ge_0_30": len(new_only),
        },
        "overall": overall,
        "per_trade_delta": {
            "improved": sum(value > 1e-12 for value in deltas),
            "equal": sum(abs(value) <= 1e-12 for value in deltas),
            "worse": sum(value < -1e-12 for value in deltas),
            "median_pp": 100.0 * statistics.median(deltas),
            "p90_pp": 100.0 * float(percentile(deltas, 0.90)),
        },
        "rescue": {
            "old15_lt80": sum(row["capture_15s_ratio"] < 0.80 for row in clean),
            "old15_lt80_to_5s_ge80": sum(
                row["capture_15s_ratio"] < 0.80
                and row["capture_5s_ratio"] >= 0.80
                for row in clean
            ),
            "old15_lt90": sum(row["capture_15s_ratio"] < 0.90 for row in clean),
            "old15_lt90_to_5s_ge90": sum(
                row["capture_15s_ratio"] < 0.90
                and row["capture_5s_ratio"] >= 0.90
                for row in clean
            ),
            "old15_ge90_to_5s_lt90": sum(
                row["capture_15s_ratio"] >= 0.90
                and row["capture_5s_ratio"] < 0.90
                for row in clean
            ),
        },
        "by_side": {
            "LONG": group_result(long_rows),
            "SHORT": group_result(short_rows),
        },
        "chronological_thirds": thirds,
        "preregistered_gate_diagnostic": gate,
        "decision": {
            "clean_label_observability_direction": "PASS",
            "v4_2_clean_label_gate": (
                "PASS" if gate["cohort"]["all_pass"] and gate["v4_2"]["all_pass"] else "FAIL"
            ),
            "v4_3_clean_label_distribution_gate": (
                "PASS" if gate["cohort"]["all_pass"] and gate["v4_3"]["all_pass"] else "FAIL"
            ),
            "protection_authority": "NONE",
            "next_research_question": (
                "Quantify the remaining clean 5s low tail and test sub-5s/event-driven observation before protection engineering."
            ),
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
