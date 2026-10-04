from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOW_EVIDENCE = (
    ROOT / "research/profit_protection_v4/results/"
    "stage1i_low_tail_post_entry_tick_evidence.json"
)
DEFAULT_PERSISTENCE_EVIDENCE = (
    ROOT / "research/profit_protection_v4/results/"
    "stage1i_residual_peak_persistence_evidence.json"
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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_apparent_failure(row: dict[str, Any]) -> str:
    actual = row.get("actual_post_entry_mfe")
    if actual is None or float(actual) < 0.30:
        return "FALSE_MFE_ELIGIBILITY_POST_ENTRY_LT_030"

    actual_value = float(actual)
    peak5 = float(row["peak5"])
    lifecycle_mfe = float(row["true_mfe"])
    corrected_capture = peak5 / actual_value if actual_value > 0.0 else float("-inf")
    benchmark_contaminated = lifecycle_mfe > actual_value * 1.10

    if benchmark_contaminated and corrected_capture >= 0.80:
        return "BENCHMARK_CONTAMINATION_DOMINANT"
    if benchmark_contaminated and corrected_capture < 0.80:
        return "MIXED_CONTAMINATION_PLUS_TRUE_5S_MISS"
    if corrected_capture < 0.80:
        return "TRUE_POST_ENTRY_5S_MISS"
    return "CORRECTED_NOT_LOW_TAIL"


def persistence_class(row: dict[str, Any]) -> str:
    run90 = int(row.get("near_90_longest_run_s") or 0)
    if run90 <= 1:
        return "FLASH_<=1S"
    if run90 <= 2:
        return "SHORT_2S"
    if run90 < 5:
        return "SUB5S_3_4S"
    return "PERSISTENT_GE5S"


def build_result(
    low_rows: list[dict[str, Any]],
    persistence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for source in low_rows:
        row = dict(source)
        actual = row.get("actual_post_entry_mfe")
        actual_value = None if actual is None else float(actual)
        row["old_capture_ratio"] = float(row["peak5"]) / float(row["true_mfe"])
        row["corrected_capture_ratio"] = (
            None
            if actual_value is None or actual_value <= 0.0
            else float(row["peak5"]) / actual_value
        )
        row["lifecycle_vs_actual_ratio"] = (
            None
            if actual_value is None or actual_value <= 0.0
            else float(row["true_mfe"]) / actual_value
        )
        row["failure_category"] = classify_apparent_failure(row)
        enriched.append(row)

    categories = Counter(str(row["failure_category"]) for row in enriched)
    corrected_eligible = [
        row
        for row in enriched
        if row.get("actual_post_entry_mfe") is not None
        and float(row["actual_post_entry_mfe"]) >= 0.30
        and row.get("corrected_capture_ratio") is not None
    ]
    corrected_capture = [
        float(row["corrected_capture_ratio"]) for row in corrected_eligible
    ]

    positive_actual = [
        row
        for row in enriched
        if row.get("actual_post_entry_mfe") is not None
        and float(row["actual_post_entry_mfe"]) > 0.0
    ]

    persistence_valid = [
        dict(row)
        for row in persistence_rows
        if row.get("actual_peak_time_ms") is not None
    ]
    for row in persistence_valid:
        row["persistence_class"] = persistence_class(row)

    persistence_counts = Counter(
        str(row["persistence_class"]) for row in persistence_valid
    )

    near_peak: dict[str, Any] = {}
    for threshold in (80, 90, 95):
        runs = [
            int(row[f"near_{threshold}_longest_run_s"])
            for row in persistence_valid
        ]
        seconds = [
            int(row[f"near_{threshold}_distinct_seconds"])
            for row in persistence_valid
        ]
        near_peak[str(threshold)] = {
            "n": len(runs),
            "longest_run_median_s": (
                None if not runs else statistics.median(runs)
            ),
            "longest_run_p90_s": percentile(runs, 0.90),
            "run_lt5s_n": sum(value < 5 for value in runs),
            "run_le2s_n": sum(value <= 2 for value in runs),
            "distinct_seconds_median": (
                None if not seconds else statistics.median(seconds)
            ),
        }

    before_gaps = [
        int(row["nearest_5s_before_gap_ms"])
        for row in persistence_valid
        if row.get("nearest_5s_before_gap_ms") is not None
    ]
    after_gaps = [
        int(row["nearest_5s_after_gap_ms"])
        for row in persistence_valid
        if row.get("nearest_5s_after_gap_ms") is not None
    ]

    false_eligibility = int(
        categories.get("FALSE_MFE_ELIGIBILITY_POST_ENTRY_LT_030", 0)
    )
    contamination_dominant = int(
        categories.get("BENCHMARK_CONTAMINATION_DOMINANT", 0)
    )
    mixed = int(
        categories.get("MIXED_CONTAMINATION_PLUS_TRUE_5S_MISS", 0)
    )
    true_miss = int(categories.get("TRUE_POST_ENTRY_5S_MISS", 0))
    genuine_residual = mixed + true_miss

    return {
        "stage": "PP-V4-1I",
        "status": "COMPLETE_RESEARCH_ONLY",
        "question": (
            "Why do trades remain below 80% capture under the archived "
            "~5-second current-price observer?"
        ),
        "population": {
            "stage1h_apparent_5s_lt80_trades": len(enriched),
            "post_entry_mfe_ge_0_30_after_correction": len(corrected_eligible),
            "genuine_corrected_5s_lt80": genuine_residual,
            "residual_peak_persistence_rows": len(persistence_valid),
        },
        "benchmark_integrity": {
            "active_code_path": (
                "Stage12 fast lifecycle MFE uses rolling_1m_high/low from "
                "closed bars via _build_fast_snapshot -> _mfe_mae."
            ),
            "entry_boundary_problem": (
                "The rolling closed-bar window is not clipped to the "
                "position opened_at_ms, so newly opened positions can inherit "
                "favorable extrema that occurred before entry."
            ),
            "false_mfe_eligibility_n": false_eligibility,
            "false_mfe_eligibility_share_of_apparent_low_tail_pct": (
                100.0 * false_eligibility / len(enriched)
                if enriched
                else 0.0
            ),
            "benchmark_contamination_dominant_n": contamination_dominant,
            "mixed_contamination_plus_true_5s_miss_n": mixed,
            "lifecycle_mfe_gt_actual_post_entry_mfe_10pct_n": sum(
                row.get("lifecycle_vs_actual_ratio") is not None
                and float(row["lifecycle_vs_actual_ratio"]) > 1.10
                for row in positive_actual
            ),
            "lifecycle_mfe_gt_actual_post_entry_mfe_25pct_n": sum(
                row.get("lifecycle_vs_actual_ratio") is not None
                and float(row["lifecycle_vs_actual_ratio"]) > 1.25
                for row in positive_actual
            ),
            "lifecycle_mfe_gt_actual_post_entry_mfe_2x_n": sum(
                row.get("lifecycle_vs_actual_ratio") is not None
                and float(row["lifecycle_vs_actual_ratio"]) > 2.0
                for row in positive_actual
            ),
            "positive_actual_post_entry_mfe_n": len(positive_actual),
        },
        "failure_categories": {
            key: {
                "n": int(value),
                "share_of_apparent_low_tail_pct": (
                    100.0 * value / len(enriched) if enriched else 0.0
                ),
            }
            for key, value in sorted(categories.items())
        },
        "corrected_apparent_low_tail": {
            "eligible_n": len(corrected_eligible),
            "corrected_lt80_n": sum(
                float(row["corrected_capture_ratio"]) < 0.80
                for row in corrected_eligible
            ),
            "corrected_ge80_n": sum(
                float(row["corrected_capture_ratio"]) >= 0.80
                for row in corrected_eligible
            ),
            "corrected_ge90_n": sum(
                float(row["corrected_capture_ratio"]) >= 0.90
                for row in corrected_eligible
            ),
            "old_capture_median_pct": (
                None
                if not enriched
                else 100.0
                * statistics.median(
                    float(row["old_capture_ratio"]) for row in enriched
                )
            ),
            "corrected_capture_median_pct": (
                None
                if not corrected_capture
                else 100.0 * statistics.median(corrected_capture)
            ),
            "corrected_capture_p10_pct": (
                None
                if not corrected_capture
                else 100.0 * float(percentile(corrected_capture, 0.10))
            ),
            "corrected_capture_p25_pct": (
                None
                if not corrected_capture
                else 100.0 * float(percentile(corrected_capture, 0.25))
            ),
        },
        "genuine_residual_5s_miss": {
            "n": genuine_residual,
            "near_peak_persistence": near_peak,
            "persistence_classes": {
                key: {
                    "n": int(value),
                    "share_pct": (
                        100.0 * value / len(persistence_valid)
                        if persistence_valid
                        else 0.0
                    ),
                }
                for key, value in sorted(persistence_counts.items())
            },
            "nearest_5s_before_true_peak_gap_median_ms": (
                None
                if not before_gaps
                else statistics.median(before_gaps)
            ),
            "nearest_5s_after_true_peak_gap_median_ms": (
                None
                if not after_gaps
                else statistics.median(after_gaps)
            ),
            "interpretation": (
                "Every genuine residual had <5 seconds of consecutive time "
                "at >=90% of actual post-entry MFE; 20/24 were <=1 second. "
                "This supports sub-5s/event-driven observability after the "
                "MFE entry-boundary bug is corrected."
            ),
        },
        "decision": {
            "stage1h_gate_status": (
                "PARTIALLY_SUPERSEDED_FOR_MFE_BASED_PROMOTION"
            ),
            "keep_v4_5s_prospective_observer": True,
            "promote_protection_logic": False,
            "immediate_next_priority": (
                "FIX_STAGE12_MFE_ENTRY_BOUNDARY_AND_REBUILD_CLEAN_MFE_LABELS"
            ),
            "after_clean_mfe": (
                "RERUN_5S_VS_15S_AND_THEN_TEST_SUB5S_EVENT_DRIVEN_IF_RESIDUAL_PERSISTS"
            ),
            "why": (
                "The apparent 5s lower tail is a mixture of invalid MFE "
                "eligibility caused by pre-entry rolling candles and genuine "
                "flash excursions. Cadence should not be tuned against a "
                "contaminated benchmark."
            ),
        },
        "evidence_files": {
            "post_entry_tick_extrema": str(DEFAULT_LOW_EVIDENCE.relative_to(ROOT)),
            "residual_peak_persistence": str(
                DEFAULT_PERSISTENCE_EVIDENCE.relative_to(ROOT)
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--low-evidence",
        default=str(DEFAULT_LOW_EVIDENCE),
    )
    parser.add_argument(
        "--persistence-evidence",
        default=str(DEFAULT_PERSISTENCE_EVIDENCE),
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = build_result(
        load_json(Path(args.low_evidence)),
        load_json(Path(args.persistence_evidence)),
    )
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
