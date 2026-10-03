from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable

from market_radar.persistence import _postgres_connect
from research.profit_protection_v3.stage2a_peak_continuation_anatomy import (
    DEFAULT_ARM_PCT,
    DEFAULT_CUTOFF_MS,
    DEFAULT_START_MS,
    _load_snapshot,
    record_local_peak_candidates,
)


def pct(numerator: float, denominator: float) -> float:
    return 100.0 * float(numerator) / float(denominator) if denominator else 0.0


def median(values: Iterable[float]) -> float | None:
    items = [float(value) for value in values]
    return statistics.median(items) if items else None


def quantile(values: Iterable[float], q: float) -> float | None:
    items = sorted(float(value) for value in values)
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    q = max(0.0, min(float(q), 1.0))
    position = (len(items) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return items[low]
    weight = position - low
    return items[low] * (1.0 - weight) + items[high] * weight


def ratio_band(ratio: float) -> str:
    value = float(ratio)
    if value < 0.50:
        return "<50"
    if value < 0.60:
        return "50-60"
    if value < 0.70:
        return "60-70"
    if value < 0.80:
        return "70-80"
    if value < 0.90:
        return "80-90"
    if value <= 1.00:
        return "90-100"
    if value <= 1.05:
        return "100-105"
    return ">105"


def analysis_group(ratio: float) -> str:
    value = float(ratio)
    if value < 0.70:
        return "SEVERE_LT70"
    if value < 0.80:
        return "LOW_70_80"
    if value < 0.90:
        return "MID_80_90"
    if value <= 1.00:
        return "GOOD_90_100"
    return "BENCHMARK_GT100"


def _side_return(side: str, entry: float, price: float) -> float:
    if entry <= 0.0 or price <= 0.0:
        return 0.0
    raw = 100.0 * (price / entry - 1.0)
    return raw if str(side).upper() == "LONG" else -raw


def _favorable_rolling_pct(
    *,
    side: str,
    entry: float,
    rolling_high: float | None,
    rolling_low: float | None,
) -> float | None:
    if entry <= 0.0:
        return None
    if str(side).upper() == "LONG":
        if rolling_high is None or float(rolling_high) <= 0.0:
            return None
        return 100.0 * (float(rolling_high) / entry - 1.0)
    if rolling_low is None or float(rolling_low) <= 0.0:
        return None
    return 100.0 * (entry - float(rolling_low)) / entry


def classify_observability_mechanism(row: dict[str, Any]) -> str:
    ratio = float(row["capture_ratio"])
    if ratio > 1.01:
        return "BENCHMARK_MISMATCH_GT101"

    true_mfe = float(row["true_mfe_pct"])
    max_v2_mfe = float(row["max_v2_mfe_pct"])
    if true_mfe <= 0.0 or max_v2_mfe <= 0.0:
        return "INSUFFICIENT_BENCHMARK"

    benchmark_coverage = max_v2_mfe / true_mfe
    executable_capture_of_v2 = float(row["terminal_peak_pct"]) / max_v2_mfe

    if benchmark_coverage >= 0.90 and executable_capture_of_v2 < 0.80:
        return "INTRAPOLL_EXCURSION_DOMINANT"
    if benchmark_coverage >= 0.90 and executable_capture_of_v2 < 0.90:
        return "INTRAPOLL_EXCURSION_MODERATE"
    if benchmark_coverage < 0.90:
        return "BENCHMARK_STREAM_MISMATCH"
    return "CURRENT_TICKER_NEAR_BENCHMARK"


def _load_position_metadata(ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select position_id,symbol,side,opened_at_ms,closed_at_ms,entry_price,
                       realized_pnl_pct,close_reason
                from positions
                where position_id=any(%s)
                """,
                (ids,),
            )
            return {
                str(position_id): {
                    "symbol": str(symbol),
                    "side": str(side).upper(),
                    "opened_at_ms": int(opened_at_ms),
                    "closed_at_ms": int(closed_at_ms or opened_at_ms),
                    "entry_price": float(entry_price),
                    "realized_pnl_pct": (
                        None if realized_pnl_pct is None else float(realized_pnl_pct)
                    ),
                    "close_reason": str(close_reason or ""),
                }
                for (
                    position_id,
                    symbol,
                    side,
                    opened_at_ms,
                    closed_at_ms,
                    entry_price,
                    realized_pnl_pct,
                    close_reason,
                ) in cur.fetchall()
            }


def _load_v2_rows(
    *,
    ids: list[str],
    cutoff_ms: int,
) -> dict[str, list[dict[str, Any]]]:
    if not ids:
        return {}
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select position_id,evaluated_at_ms,current_price,current_pnl_pct,mfe_pct,
                       snapshot_json
                from pp_decision_v2_observations
                where evaluated_at_ms<=%s and position_id=any(%s)
                order by position_id,evaluated_at_ms
                """,
                (int(cutoff_ms), ids),
            )
            for (
                position_id,
                evaluated_at_ms,
                current_price,
                current_pnl_pct,
                mfe_pct,
                snapshot_json,
            ) in cur.fetchall():
                try:
                    snapshot = (
                        snapshot_json
                        if isinstance(snapshot_json, dict)
                        else json.loads(snapshot_json or "{}")
                    )
                except (TypeError, json.JSONDecodeError):
                    snapshot = {}
                result[str(position_id)].append(
                    {
                        "evaluated_at_ms": int(evaluated_at_ms),
                        "current_price": float(current_price),
                        "current_pnl_pct": float(current_pnl_pct),
                        "mfe_pct": float(mfe_pct),
                        "snapshot": snapshot,
                    }
                )
    return result


def _terminal_peak_index(
    rows: list[dict[str, Any]],
    *,
    terminal_time_ms: int,
) -> int | None:
    if not rows:
        return None
    exact = [
        index
        for index, row in enumerate(rows)
        if int(row["evaluated_at_ms"]) == int(terminal_time_ms)
    ]
    if exact:
        return exact[-1]
    return min(
        range(len(rows)),
        key=lambda index: abs(int(rows[index]["evaluated_at_ms"]) - int(terminal_time_ms)),
    )


def _trade_row(
    *,
    position: dict[str, Any],
    terminal: Any,
    metadata: dict[str, Any],
    v2_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    true_mfe = float(position["true_mfe_pct"])
    terminal_peak = float(terminal.peak_pct)
    ratio = terminal_peak / true_mfe if true_mfe > 0.0 else 0.0
    terminal_time_ms = int(v2_rows[terminal.observation_index]["evaluated_at_ms"])
    terminal_index = _terminal_peak_index(
        v2_rows,
        terminal_time_ms=terminal_time_ms,
    )
    terminal_v2 = v2_rows[terminal_index] if terminal_index is not None else {}
    terminal_snapshot = terminal_v2.get("snapshot") or {}

    max_v2_mfe = max(
        (float(row["mfe_pct"]) for row in v2_rows),
        default=0.0,
    )
    max_current = max(
        (float(row["current_pnl_pct"]) for row in v2_rows),
        default=float("-inf"),
    )
    cadence = [
        int(v2_rows[index]["evaluated_at_ms"]) - int(v2_rows[index - 1]["evaluated_at_ms"])
        for index in range(1, len(v2_rows))
        if int(v2_rows[index]["evaluated_at_ms"]) > int(v2_rows[index - 1]["evaluated_at_ms"])
    ]

    first_max_mfe_row: dict[str, Any] | None = None
    if v2_rows and max_v2_mfe > 0.0:
        tolerance = max(1e-9, abs(max_v2_mfe) * 1e-9)
        for row in v2_rows:
            if float(row["mfe_pct"]) >= max_v2_mfe - tolerance:
                first_max_mfe_row = row
                break

    previous_mfe = 0.0
    mfe_jump = None
    if first_max_mfe_row is not None:
        index = v2_rows.index(first_max_mfe_row)
        if index > 0:
            previous_mfe = float(v2_rows[index - 1]["mfe_pct"])
        mfe_jump = max(0.0, max_v2_mfe - previous_mfe)

    rolling_high = terminal_snapshot.get("rolling_1m_high")
    rolling_low = terminal_snapshot.get("rolling_1m_low")
    rolling_favorable = _favorable_rolling_pct(
        side=str(metadata["side"]),
        entry=float(metadata["entry_price"]),
        rolling_high=None if rolling_high is None else float(rolling_high),
        rolling_low=None if rolling_low is None else float(rolling_low),
    )

    latest_high = terminal_snapshot.get("latest_1m_high")
    latest_low = terminal_snapshot.get("latest_1m_low")
    latest_open = terminal_snapshot.get("latest_1m_open")
    latest_close = terminal_snapshot.get("latest_1m_close")
    latest_range_pct = None
    if (
        latest_high is not None
        and latest_low is not None
        and latest_open is not None
        and float(latest_open) > 0.0
    ):
        latest_range_pct = (
            100.0
            * (float(latest_high) - float(latest_low))
            / float(latest_open)
        )

    row = {
        "position_id": str(position["position_id"]),
        "symbol": str(metadata["symbol"]),
        "side": str(metadata["side"]),
        "opened_at_ms": int(metadata["opened_at_ms"]),
        "closed_at_ms": int(metadata["closed_at_ms"]),
        "trade_duration_seconds": max(
            0.0,
            (int(metadata["closed_at_ms"]) - int(metadata["opened_at_ms"])) / 1000.0,
        ),
        "terminal_peak_at_ms": terminal_time_ms,
        "terminal_peak_age_seconds": max(
            0.0,
            (terminal_time_ms - int(metadata["opened_at_ms"])) / 1000.0,
        ),
        "terminal_peak_to_close_seconds": max(
            0.0,
            (int(metadata["closed_at_ms"]) - terminal_time_ms) / 1000.0,
        ),
        "true_mfe_pct": true_mfe,
        "terminal_peak_pct": terminal_peak,
        "capture_ratio": ratio,
        "capture_pct": 100.0 * ratio,
        "ratio_band": ratio_band(ratio),
        "analysis_group": analysis_group(ratio),
        "max_current_pnl_pct": max_current,
        "max_v2_mfe_pct": max_v2_mfe,
        "v2_mfe_vs_true_mfe_ratio": (
            max_v2_mfe / true_mfe if true_mfe > 0.0 else 0.0
        ),
        "terminal_peak_vs_v2_mfe_ratio": (
            terminal_peak / max_v2_mfe if max_v2_mfe > 0.0 else 0.0
        ),
        "mfe_minus_terminal_peak_pct_points": max_v2_mfe - terminal_peak,
        "true_mfe_minus_terminal_peak_pct_points": true_mfe - terminal_peak,
        "mfe_discovery_current_pnl_pct": (
            None
            if first_max_mfe_row is None
            else float(first_max_mfe_row["current_pnl_pct"])
        ),
        "mfe_discovery_gap_pct_points": (
            None
            if first_max_mfe_row is None
            else max_v2_mfe - float(first_max_mfe_row["current_pnl_pct"])
        ),
        "mfe_jump_pct_points": mfe_jump,
        "mfe_discovery_at_ms": (
            None
            if first_max_mfe_row is None
            else int(first_max_mfe_row["evaluated_at_ms"])
        ),
        "mfe_discovery_minus_terminal_peak_seconds": (
            None
            if first_max_mfe_row is None
            else (
                int(first_max_mfe_row["evaluated_at_ms"]) - terminal_time_ms
            )
            / 1000.0
        ),
        "observation_count": len(v2_rows),
        "median_fast_gap_seconds": (
            None if not cadence else float(statistics.median(cadence)) / 1000.0
        ),
        "terminal_v2_mfe_pct": (
            None if not terminal_v2 else float(terminal_v2["mfe_pct"])
        ),
        "terminal_hidden_gap_pct_points": (
            None
            if not terminal_v2
            else float(terminal_v2["mfe_pct"]) - terminal_peak
        ),
        "rolling_favorable_pct_at_terminal": rolling_favorable,
        "rolling_hidden_gap_pct_points": (
            None
            if rolling_favorable is None
            else float(rolling_favorable) - terminal_peak
        ),
        "latest_1m_range_pct": latest_range_pct,
        "side_ret_1m_pct": float(terminal_snapshot.get("side_ret_1m_pct") or 0.0),
        "side_ret_3m_pct": float(terminal_snapshot.get("side_ret_3m_pct") or 0.0),
        "flow_aligned": bool(terminal_snapshot.get("flow_aligned")),
        "flow_opposite": bool(terminal_snapshot.get("flow_opposite")),
        "opposite_micro_structure": bool(
            terminal_snapshot.get("opposite_micro_structure")
        ),
        "positioning_opposite": bool(
            terminal_snapshot.get("positioning_opposite")
        ),
        "realized_pnl_pct": metadata.get("realized_pnl_pct"),
        "close_reason": str(metadata.get("close_reason") or ""),
    }
    row["observability_mechanism"] = classify_observability_mechanism(row)
    return row


def _summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    ratios = [float(row["capture_ratio"]) for row in rows]
    true_mfe = [float(row["true_mfe_pct"]) for row in rows]
    absolute_gap = [
        float(row["true_mfe_minus_terminal_peak_pct_points"])
        for row in rows
    ]
    v2_gap = [
        float(row["mfe_minus_terminal_peak_pct_points"])
        for row in rows
    ]
    latest_ranges = [
        float(row["latest_1m_range_pct"])
        for row in rows
        if row.get("latest_1m_range_pct") is not None
    ]
    cadence = [
        float(row["median_fast_gap_seconds"])
        for row in rows
        if row.get("median_fast_gap_seconds") is not None
    ]
    jump = [
        float(row["mfe_jump_pct_points"])
        for row in rows
        if row.get("mfe_jump_pct_points") is not None
    ]
    mechanisms = Counter(str(row["observability_mechanism"]) for row in rows)
    return {
        "n": len(rows),
        "share_of_terminal_cohort_pct": None,
        "capture_mean_pct": 100.0 * sum(ratios) / len(ratios),
        "capture_median_pct": 100.0 * float(median(ratios) or 0.0),
        "capture_p10_pct": 100.0 * float(quantile(ratios, 0.10) or 0.0),
        "capture_p25_pct": 100.0 * float(quantile(ratios, 0.25) or 0.0),
        "capture_p75_pct": 100.0 * float(quantile(ratios, 0.75) or 0.0),
        "true_mfe_median_pct": float(median(true_mfe) or 0.0),
        "absolute_true_mfe_gap_median_pct_points": float(median(absolute_gap) or 0.0),
        "v2_mfe_gap_median_pct_points": float(median(v2_gap) or 0.0),
        "latest_1m_range_median_pct": (
            None if not latest_ranges else float(median(latest_ranges) or 0.0)
        ),
        "mfe_jump_median_pct_points": (
            None if not jump else float(median(jump) or 0.0)
        ),
        "terminal_peak_age_median_seconds": float(
            median(row["terminal_peak_age_seconds"] for row in rows) or 0.0
        ),
        "terminal_peak_to_close_median_seconds": float(
            median(row["terminal_peak_to_close_seconds"] for row in rows) or 0.0
        ),
        "trade_duration_median_seconds": float(
            median(row["trade_duration_seconds"] for row in rows) or 0.0
        ),
        "median_fast_gap_seconds": (
            None if not cadence else float(median(cadence) or 0.0)
        ),
        "long_share_pct": pct(
            sum(str(row["side"]) == "LONG" for row in rows),
            len(rows),
        ),
        "flow_aligned_pct": pct(
            sum(bool(row["flow_aligned"]) for row in rows),
            len(rows),
        ),
        "flow_opposite_pct": pct(
            sum(bool(row["flow_opposite"]) for row in rows),
            len(rows),
        ),
        "opposite_micro_structure_pct": pct(
            sum(bool(row["opposite_micro_structure"]) for row in rows),
            len(rows),
        ),
        "positioning_opposite_pct": pct(
            sum(bool(row["positioning_opposite"]) for row in rows),
            len(rows),
        ),
        "mechanisms": {
            key: {
                "n": value,
                "share_pct": pct(value, len(rows)),
            }
            for key, value in sorted(mechanisms.items())
        },
    }


def _chronological_thirds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (int(row["opened_at_ms"]), str(row["position_id"])))
    if not ordered:
        return {}
    n = len(ordered)
    result: dict[str, Any] = {}
    for label, left, right in (
        ("EARLY", 0, n // 3),
        ("MID", n // 3, 2 * n // 3),
        ("LATE", 2 * n // 3, n),
    ):
        subset = ordered[left:right]
        ratios = [float(row["capture_ratio"]) for row in subset]
        result[label] = {
            "n": len(subset),
            "mean_capture_pct": 100.0 * sum(ratios) / len(ratios),
            "median_capture_pct": 100.0 * float(median(ratios) or 0.0),
            "lt80_share_pct": pct(
                sum(float(row["capture_ratio"]) < 0.80 for row in subset),
                len(subset),
            ),
            "lt90_share_pct": pct(
                sum(float(row["capture_ratio"]) < 0.90 for row in subset),
                len(subset),
            ),
            "ge90_le100_share_pct": pct(
                sum(0.90 <= float(row["capture_ratio"]) <= 1.00 for row in subset),
                len(subset),
            ),
        }
    return result


def _top_symbols(rows: list[dict[str, Any]], *, minimum_count: int = 3) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["symbol"])].append(row)
    ranked = []
    for symbol, items in grouped.items():
        if len(items) < int(minimum_count):
            continue
        ratios = [float(row["capture_ratio"]) for row in items]
        ranked.append(
            {
                "symbol": symbol,
                "n": len(items),
                "mean_capture_pct": 100.0 * sum(ratios) / len(ratios),
                "lt80_share_pct": pct(
                    sum(float(row["capture_ratio"]) < 0.80 for row in items),
                    len(items),
                ),
                "lt90_share_pct": pct(
                    sum(float(row["capture_ratio"]) < 0.90 for row in items),
                    len(items),
                ),
            }
        )
    ranked.sort(key=lambda row: (-float(row["lt80_share_pct"]), -int(row["n"]), str(row["symbol"])))
    return ranked[:25]


def build_low_tail_anatomy(
    *,
    start_ms: int = DEFAULT_START_MS,
    cutoff_ms: int = DEFAULT_CUTOFF_MS,
    arm_pct: float = DEFAULT_ARM_PCT,
) -> dict[str, Any]:
    positions, observations = _load_snapshot(start_ms=start_ms, cutoff_ms=cutoff_ms)
    by_id = {str(position["position_id"]): position for position in positions}
    eligible = [
        position
        for position in positions
        if float(position["true_mfe_pct"]) >= float(arm_pct)
        and max(
            (
                float(item.current_pnl_pct)
                for item in observations[str(position["position_id"])]
            ),
            default=float("-inf"),
        )
        >= float(arm_pct)
    ]

    terminal_by_id: dict[str, Any] = {}
    for position in eligible:
        pid = str(position["position_id"])
        candidates = record_local_peak_candidates(
            pid,
            observations[pid],
            arm_pct=arm_pct,
        )
        terminals = [item for item in candidates if item.label == "TERMINAL"]
        if terminals:
            terminal_by_id[pid] = terminals[-1]

    ids = sorted(terminal_by_id)
    metadata = _load_position_metadata(ids)
    v2 = _load_v2_rows(ids=ids, cutoff_ms=cutoff_ms)

    rows: list[dict[str, Any]] = []
    for pid in ids:
        if pid not in metadata or not v2.get(pid):
            continue
        rows.append(
            _trade_row(
                position=by_id[pid],
                terminal=terminal_by_id[pid],
                metadata=metadata[pid],
                v2_rows=v2[pid],
            )
        )

    ratios = [float(row["capture_ratio"]) for row in rows]
    ratio_bins = Counter(str(row["ratio_band"]) for row in rows)
    groups: dict[str, Any] = {}
    for group_name in (
        "SEVERE_LT70",
        "LOW_70_80",
        "MID_80_90",
        "GOOD_90_100",
        "BENCHMARK_GT100",
    ):
        subset = [row for row in rows if str(row["analysis_group"]) == group_name]
        summary = _summarize_group(subset)
        summary["share_of_terminal_cohort_pct"] = pct(len(subset), len(rows))
        groups[group_name] = summary

    low_lt80 = [row for row in rows if float(row["capture_ratio"]) < 0.80]
    low_lt90 = [row for row in rows if float(row["capture_ratio"]) < 0.90]
    good_90_100 = [
        row for row in rows
        if 0.90 <= float(row["capture_ratio"]) <= 1.00
    ]

    mechanisms_all = Counter(str(row["observability_mechanism"]) for row in rows)
    mechanisms_low80 = Counter(
        str(row["observability_mechanism"]) for row in low_lt80
    )

    result: dict[str, Any] = {
        "stage": "PP-DECISION-V3-LOW-TAIL-STAGE-A",
        "status": "COMPLETE_RESEARCH_ONLY",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "terminal_trade_count": len(rows),
        "distribution": {
            "mean_capture_pct": 100.0 * sum(ratios) / len(ratios),
            "median_capture_pct": 100.0 * float(median(ratios) or 0.0),
            "p01_pct": 100.0 * float(quantile(ratios, 0.01) or 0.0),
            "p05_pct": 100.0 * float(quantile(ratios, 0.05) or 0.0),
            "p10_pct": 100.0 * float(quantile(ratios, 0.10) or 0.0),
            "p25_pct": 100.0 * float(quantile(ratios, 0.25) or 0.0),
            "p50_pct": 100.0 * float(quantile(ratios, 0.50) or 0.0),
            "p75_pct": 100.0 * float(quantile(ratios, 0.75) or 0.0),
            "p90_pct": 100.0 * float(quantile(ratios, 0.90) or 0.0),
            "p95_pct": 100.0 * float(quantile(ratios, 0.95) or 0.0),
            "p99_pct": 100.0 * float(quantile(ratios, 0.99) or 0.0),
            "minimum_pct": 100.0 * min(ratios),
            "maximum_pct": 100.0 * max(ratios),
            "lt80_n": len(low_lt80),
            "lt80_share_pct": pct(len(low_lt80), len(rows)),
            "lt90_n": len(low_lt90),
            "lt90_share_pct": pct(len(low_lt90), len(rows)),
            "ge90_n": sum(float(row["capture_ratio"]) >= 0.90 for row in rows),
            "ge90_share_pct": pct(
                sum(float(row["capture_ratio"]) >= 0.90 for row in rows),
                len(rows),
            ),
            "gt100_n": sum(float(row["capture_ratio"]) > 1.00 for row in rows),
            "gt100_share_pct": pct(
                sum(float(row["capture_ratio"]) > 1.00 for row in rows),
                len(rows),
            ),
            "ratio_bins": {
                band: {
                    "n": int(ratio_bins.get(band, 0)),
                    "share_pct": pct(int(ratio_bins.get(band, 0)), len(rows)),
                }
                for band in (
                    "<50",
                    "50-60",
                    "60-70",
                    "70-80",
                    "80-90",
                    "90-100",
                    "100-105",
                    ">105",
                )
            },
        },
        "groups": groups,
        "low_lt80_vs_good_90_100": {
            "low_lt80": _summarize_group(low_lt80),
            "good_90_100": _summarize_group(good_90_100),
        },
        "observability_mechanisms": {
            "all": {
                key: {"n": value, "share_pct": pct(value, len(rows))}
                for key, value in sorted(mechanisms_all.items())
            },
            "low_lt80": {
                key: {"n": value, "share_pct": pct(value, len(low_lt80))}
                for key, value in sorted(mechanisms_low80.items())
            },
        },
        "chronological_thirds": _chronological_thirds(rows),
        "symbol_diagnostics_min_3_trades": _top_symbols(rows, minimum_count=3),
        "extremes": {
            "lowest_20": [
                {
                    key: row[key]
                    for key in (
                        "position_id",
                        "symbol",
                        "side",
                        "capture_pct",
                        "true_mfe_pct",
                        "terminal_peak_pct",
                        "max_v2_mfe_pct",
                        "terminal_peak_vs_v2_mfe_ratio",
                        "latest_1m_range_pct",
                        "mfe_jump_pct_points",
                        "median_fast_gap_seconds",
                        "observability_mechanism",
                    )
                }
                for row in sorted(rows, key=lambda item: float(item["capture_ratio"]))[:20]
            ],
            "highest_10": [
                {
                    key: row[key]
                    for key in (
                        "position_id",
                        "symbol",
                        "side",
                        "capture_pct",
                        "true_mfe_pct",
                        "terminal_peak_pct",
                        "max_v2_mfe_pct",
                        "observability_mechanism",
                    )
                }
                for row in sorted(
                    rows,
                    key=lambda item: float(item["capture_ratio"]),
                    reverse=True,
                )[:10]
            ],
        },
        "trade_rows": rows,
    }

    low_summary = result["low_lt80_vs_good_90_100"]["low_lt80"]
    good_summary = result["low_lt80_vs_good_90_100"]["good_90_100"]
    result["conclusion"] = {
        "stage_b_ready": True,
        "primary_question": (
            "Can the low-tail mechanism be recognized causally before or at the "
            "excursion using only information available in the frozen stream?"
        ),
        "facts_to_carry_forward": {
            "low_lt80_count": len(low_lt80),
            "low_lt80_share_pct": pct(len(low_lt80), len(rows)),
            "low_lt90_count": len(low_lt90),
            "low_lt90_share_pct": pct(len(low_lt90), len(rows)),
            "mean_capture_pct": result["distribution"]["mean_capture_pct"],
            "median_capture_pct": result["distribution"]["median_capture_pct"],
            "low_lt80_median_true_mfe_pct": low_summary.get("true_mfe_median_pct"),
            "good_90_100_median_true_mfe_pct": good_summary.get("true_mfe_median_pct"),
            "low_lt80_median_v2_gap_pct_points": low_summary.get(
                "v2_mfe_gap_median_pct_points"
            ),
            "good_90_100_median_v2_gap_pct_points": good_summary.get(
                "v2_mfe_gap_median_pct_points"
            ),
        },
        "guardrail": (
            "Stage A is anatomy only. True MFE, terminal labels, and final capture "
            "ratio are offline labels and may not be used as live inputs."
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=DEFAULT_START_MS)
    parser.add_argument("--cutoff-ms", type=int, default=DEFAULT_CUTOFF_MS)
    parser.add_argument("--arm-pct", type=float, default=DEFAULT_ARM_PCT)
    parser.add_argument("--output", default="")
    parser.add_argument("--without-trade-rows", action="store_true")
    args = parser.parse_args()

    result = build_low_tail_anatomy(
        start_ms=args.start_ms,
        cutoff_ms=args.cutoff_ms,
        arm_pct=args.arm_pct,
    )
    if args.without_trade_rows:
        result = dict(result)
        result.pop("trade_rows", None)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
