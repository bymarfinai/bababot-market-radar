from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1k_sub5s_phase_benchmark_evidence.json"
)
DEFAULT_STAGE1J = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1j_clean_post_entry_mfe_evidence.json"
)

CLEAN_ELIGIBLE_TOTAL = 99
BASELINE_RESIDUAL_N = 24
TARGET_OVERALL_LT80_PCT = 10.0
REQUIRED_RESCUES_GE80 = 15


def _cadence_summary(rows: list[dict[str, Any]], cadence: str) -> dict[str, Any]:
    p80 = [
        float(row["cadences"][cadence]["ge80_phase_probability"])
        for row in rows
    ]
    p90 = [
        float(row["cadences"][cadence]["ge90_phase_probability"])
        for row in rows
    ]
    p95 = [
        float(row["cadences"][cadence]["ge95_phase_probability"])
        for row in rows
    ]
    expected80 = sum(p80)
    expected90 = sum(p90)
    expected95 = sum(p95)
    return {
        "n": len(rows),
        "expected_rescues_ge80": expected80,
        "expected_rescues_ge90": expected90,
        "expected_rescues_ge95": expected95,
        "projected_overall_lt80_pct": (
            100.0 * (BASELINE_RESIDUAL_N - expected80) / CLEAN_ELIGIBLE_TOTAL
        ),
        "trade_phase_probability_ge80_median": statistics.median(p80),
        "trade_phase_probability_ge90_median": statistics.median(p90),
        "trade_phase_probability_ge95_median": statistics.median(p95),
        "trades_ge80_probability_100pct": sum(value >= 0.999999 for value in p80),
        "trades_ge80_probability_ge80pct": sum(value >= 0.80 for value in p80),
        "trades_ge80_probability_ge50pct": sum(value >= 0.50 for value in p80),
        "trades_ge80_probability_zero": sum(value <= 1e-12 for value in p80),
    }


def _stage1j_residual_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        mfe = float(row["clean_post_entry_mfe_pct"])
        if mfe < 0.30:
            continue
        if float(row["peak5"]) / mfe < 0.80:
            ids.add(str(row["position_id"]))
    return ids


def build_result(
    evidence: list[dict[str, Any]],
    stage1j_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_ids = {str(row["position_id"]) for row in evidence}
    stage1j_ids = _stage1j_residual_ids(stage1j_rows)
    population_match = evidence_ids == stage1j_ids

    cadences = {
        cadence: _cadence_summary(evidence, cadence)
        for cadence in ("5000", "2000", "1000")
    }
    by_side: dict[str, Any] = {}
    for side in ("LONG", "SHORT"):
        subset = [
            row for row in evidence
            if str(row["side"]).upper() == side
        ]
        by_side[side] = {
            cadence: _cadence_summary(subset, cadence)
            for cadence in ("2000", "1000")
        }

    hard_1s = [
        {
            "position_id": row["position_id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "actual_5s_capture_pct": (
                100.0 * float(row["actual_5s_capture_ratio"])
            ),
            "clean_mfe_pct": float(row["clean_mfe_pct"]),
        }
        for row in evidence
        if float(
            row["cadences"]["1000"]["ge80_phase_probability"]
        ) <= 1e-12
    ]

    decision_by_cadence = {
        cadence: (
            "PASS"
            if cadences[cadence]["expected_rescues_ge80"]
            >= REQUIRED_RESCUES_GE80
            and cadences[cadence]["projected_overall_lt80_pct"]
            <= TARGET_OVERALL_LT80_PCT
            else "FAIL"
        )
        for cadence in ("2000", "1000")
    }

    if decision_by_cadence["2000"] == "PASS":
        selected = "2S_PERIODIC"
    elif decision_by_cadence["1000"] == "PASS":
        selected = "1S_PERIODIC"
    else:
        selected = "EVENT_DRIVEN_NEXT_RESEARCH_CANDIDATE"

    return {
        "stage": "PP-V4-1K",
        "status": "COMPLETE_OFFLINE_SUB5S_BENCHMARK",
        "population": {
            "clean_eligible_total": CLEAN_ELIGIBLE_TOTAL,
            "baseline_clean_lt80_n": BASELINE_RESIDUAL_N,
            "baseline_clean_lt80_pct": (
                100.0 * BASELINE_RESIDUAL_N / CLEAN_ELIGIBLE_TOTAL
            ),
            "phase_benchmark_rows": len(evidence),
            "stage1j_residual_ids_match_exactly": population_match,
            "missing_from_evidence": sorted(stage1j_ids - evidence_ids),
            "extra_in_evidence": sorted(evidence_ids - stage1j_ids),
        },
        "method": {
            "price_source": "Binance USD-M Futures aggregate trades",
            "phase_grid_ms": 100,
            "cadences_ms": [5000, 2000, 1000],
            "decision_samples_are_independent_of_archived_5s_floor": True,
            "event_driven_is_observability_upper_bound_only": True,
        },
        "decision_target": {
            "baseline_lt80_pct": (
                100.0 * BASELINE_RESIDUAL_N / CLEAN_ELIGIBLE_TOTAL
            ),
            "target_overall_lt80_max_pct": TARGET_OVERALL_LT80_PCT,
            "required_residual_rescues_ge80": REQUIRED_RESCUES_GE80,
        },
        "cadences": cadences,
        "by_side": by_side,
        "one_second_zero_probability_ge80": {
            "n": len(hard_1s),
            "trades": hard_1s,
        },
        "event_driven": {
            "expected_rescues_ge80": float(BASELINE_RESIDUAL_N),
            "expected_rescues_ge90": float(BASELINE_RESIDUAL_N),
            "expected_rescues_ge95": float(BASELINE_RESIDUAL_N),
            "projected_overall_lt80_pct": 0.0,
            "observability_upper_bound_only": True,
            "execution_claim": False,
        },
        "decision": {
            "two_second_periodic": decision_by_cadence["2000"],
            "one_second_periodic": decision_by_cadence["1000"],
            "selected_next_research_path": selected,
            "protection_authority": "NONE",
            "runtime_change_authority": "NONE",
            "reason": (
                "Neither 2s nor 1s periodic polling rescues the preregistered "
                "minimum 15/24 clean residual trades in phase-averaged expectation. "
                "The next information-layer experiment should therefore be "
                "event-driven/tick observation, not protection tuning."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--stage1j", default=str(DEFAULT_STAGE1J))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    stage1j = json.loads(Path(args.stage1j).read_text(encoding="utf-8"))
    result = build_result(evidence, stage1j)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
