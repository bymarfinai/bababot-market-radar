from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from market_radar.persistence import _postgres_connect

DEFAULT_START_MS = 1790848801393
DEFAULT_CUTOFF_MS = 1791021852690
DEFAULT_ARM_PCT = 0.30
DEFAULT_HORIZONS_SECONDS = (15, 30, 45, 60)


@dataclass(frozen=True)
class FastObservation:
    evaluated_at_ms: int
    current_pnl_pct: float
    snapshot: dict[str, Any]
    danger_score: int = 0


@dataclass(frozen=True)
class PeakCandidate:
    position_id: str
    observation_index: int
    peak_pct: float
    label: str


def _pct(numerator: float, denominator: float) -> float:
    return 100.0 * float(numerator) / float(denominator) if denominator else 0.0


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def record_local_peak_candidates(
    position_id: str,
    stream: list[FastObservation],
    *,
    arm_pct: float = DEFAULT_ARM_PCT,
) -> list[PeakCandidate]:
    """
    Retrospectively extract record-high observations followed by a lower next poll.

    This is an offline anatomy labeler, not a live detector. A candidate is
    TERMINAL only when no later observed current PnL exceeds that candidate.
    Otherwise it is CONTINUED. Trades that end on a later rising record without
    another retracement remain right-censored rather than being mislabeled.
    """
    running_peak = float("-inf")
    candidates: list[PeakCandidate] = []
    for index, obs in enumerate(stream[:-1]):
        peak = float(obs.current_pnl_pct)
        is_new_record = peak > running_peak
        running_peak = max(running_peak, peak)
        if not is_new_record or peak < float(arm_pct):
            continue
        if float(stream[index + 1].current_pnl_pct) >= peak:
            continue
        future_max = max(
            (float(item.current_pnl_pct) for item in stream[index + 1 :]),
            default=float("-inf"),
        )
        candidates.append(
            PeakCandidate(
                position_id=str(position_id),
                observation_index=index,
                peak_pct=peak,
                label="CONTINUED" if future_max > peak else "TERMINAL",
            )
        )
    return candidates


def first_horizon_index(
    stream: list[FastObservation],
    *,
    candidate_index: int,
    horizon_seconds: int,
) -> int | None:
    target_ms = int(stream[candidate_index].evaluated_at_ms) + int(horizon_seconds) * 1000
    for index in range(candidate_index + 1, len(stream)):
        if int(stream[index].evaluated_at_ms) >= target_ms:
            return index
    return None


def candidate_metrics(
    stream: list[FastObservation],
    candidate: PeakCandidate,
    *,
    horizon_seconds: int,
) -> dict[str, Any] | None:
    horizon_index = first_horizon_index(
        stream,
        candidate_index=candidate.observation_index,
        horizon_seconds=horizon_seconds,
    )
    if horizon_index is None:
        return None

    peak = float(candidate.peak_pct)
    current = float(stream[horizon_index].current_pnl_pct)
    interim = stream[candidate.observation_index + 1 : horizon_index + 1]
    recovery = max(float(item.current_pnl_pct) for item in interim) / peak
    snapshot = stream[horizon_index].snapshot or {}

    return {
        "label": candidate.label,
        "giveback_ratio": (peak - current) / peak,
        "recovery_ratio": recovery,
        "flow_opposite": bool(snapshot.get("flow_opposite")),
        "flow_aligned": bool(snapshot.get("flow_aligned")),
        "opposite_micro_structure": bool(snapshot.get("opposite_micro_structure")),
        "positioning_opposite": bool(snapshot.get("positioning_opposite")),
        "contradictions": len(snapshot.get("contradictions") or []),
        "side_ret_1m_pct": float(snapshot.get("side_ret_1m_pct") or 0.0),
        "side_ret_3m_pct": float(snapshot.get("side_ret_3m_pct") or 0.0),
    }


def _load_snapshot(
    *,
    start_ms: int,
    cutoff_ms: int,
) -> tuple[list[dict[str, Any]], dict[str, list[FastObservation]]]:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with e as (
                    select position_id, max(mfe_pct) as true_mfe_pct
                    from position_evaluations
                    group by position_id
                )
                select p.position_id,p.opened_at_ms,e.true_mfe_pct,p.raw_json
                from positions p
                join e on e.position_id=p.position_id
                where p.opened_at_ms>%s and p.status='CLOSED' and p.closed_at_ms<=%s
                order by p.opened_at_ms
                """,
                (int(start_ms), int(cutoff_ms)),
            )
            positions = []
            ids: list[str] = []
            for position_id, opened_at_ms, true_mfe_pct, raw_json in cur.fetchall():
                meta = raw_json if isinstance(raw_json, dict) else json.loads(raw_json or "{}")
                item = {
                    "position_id": str(position_id),
                    "opened_at_ms": int(opened_at_ms),
                    "true_mfe_pct": float(true_mfe_pct),
                    "initial_notional_usdt": float(meta.get("initial_notional_usdt") or 0.0),
                }
                positions.append(item)
                ids.append(str(position_id))

            cur.execute(
                """
                select position_id,evaluated_at_ms,current_pnl_pct,snapshot_json,danger_score
                from pp_decision_v2_observations
                where evaluated_at_ms<=%s and position_id=any(%s)
                order by position_id,evaluated_at_ms
                """,
                (int(cutoff_ms), ids),
            )
            observations: dict[str, list[FastObservation]] = defaultdict(list)
            for position_id, evaluated_at_ms, pnl, snapshot_json, danger_score in cur.fetchall():
                try:
                    snapshot = (
                        snapshot_json
                        if isinstance(snapshot_json, dict)
                        else json.loads(snapshot_json or "{}")
                    )
                except (TypeError, json.JSONDecodeError):
                    snapshot = {}
                observations[str(position_id)].append(
                    FastObservation(
                        evaluated_at_ms=int(evaluated_at_ms),
                        current_pnl_pct=float(pnl),
                        snapshot=snapshot,
                        danger_score=int(danger_score or 0),
                    )
                )
    return positions, observations


def _peak_band(peak_pct: float) -> str:
    if peak_pct < 0.50:
        return "0.30-0.50"
    if peak_pct < 1.00:
        return "0.50-1.00"
    if peak_pct < 2.00:
        return "1.00-2.00"
    return ">=2.00"


def _rule_metric(
    terminal_rows: list[dict[str, Any]],
    continued_rows: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    true_positive = sum(bool(predicate(row)) for row in terminal_rows)
    false_positive = sum(bool(predicate(row)) for row in continued_rows)
    return {
        "fired": true_positive + false_positive,
        "terminal_precision_pct": _pct(true_positive, true_positive + false_positive),
        "terminal_recall_pct": _pct(true_positive, len(terminal_rows)),
        "continued_false_exit_pct": _pct(false_positive, len(continued_rows)),
    }


def _label_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "median_giveback_pct": 100.0 * (_median([r["giveback_ratio"] for r in rows]) or 0.0),
        "median_recovery_of_peak_pct": 100.0 * (_median([r["recovery_ratio"] for r in rows]) or 0.0),
        "giveback_le_20_share_pct": _pct(sum(r["giveback_ratio"] <= 0.20 for r in rows), len(rows)),
        "giveback_gt_20_share_pct": _pct(sum(r["giveback_ratio"] > 0.20 for r in rows), len(rows)),
        "new_high_by_horizon_pct": _pct(sum(r["recovery_ratio"] > 1.0 for r in rows), len(rows)),
        "flow_opposite_pct": _pct(sum(r["flow_opposite"] for r in rows), len(rows)),
        "flow_aligned_pct": _pct(sum(r["flow_aligned"] for r in rows), len(rows)),
        "opposite_micro_structure_pct": _pct(
            sum(r["opposite_micro_structure"] for r in rows), len(rows)
        ),
        "positioning_opposite_pct": _pct(sum(r["positioning_opposite"] for r in rows), len(rows)),
        "median_side_ret_1m_pct": _median([r["side_ret_1m_pct"] for r in rows]),
        "median_side_ret_3m_pct": _median([r["side_ret_3m_pct"] for r in rows]),
        "median_contradictions": _median([float(r["contradictions"]) for r in rows]),
    }


def build_anatomy(
    *,
    start_ms: int = DEFAULT_START_MS,
    cutoff_ms: int = DEFAULT_CUTOFF_MS,
    arm_pct: float = DEFAULT_ARM_PCT,
    horizons_seconds: tuple[int, ...] = DEFAULT_HORIZONS_SECONDS,
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

    candidates: list[PeakCandidate] = []
    for position in eligible:
        pid = str(position["position_id"])
        candidates.extend(
            record_local_peak_candidates(pid, observations[pid], arm_pct=arm_pct)
        )

    terminal = [item for item in candidates if item.label == "TERMINAL"]
    terminal_ratios = [
        float(item.peak_pct) / float(by_id[item.position_id]["true_mfe_pct"])
        for item in terminal
        if float(by_id[item.position_id]["true_mfe_pct"]) > 0.0
    ]
    weighted_terminal_peak = sum(
        float(by_id[item.position_id]["initial_notional_usdt"]) * float(item.peak_pct) / 100.0
        for item in terminal
    )
    weighted_true_peak = sum(
        float(by_id[item.position_id]["initial_notional_usdt"])
        * float(by_id[item.position_id]["true_mfe_pct"])
        / 100.0
        for item in terminal
    )

    result: dict[str, Any] = {
        "stage": "PP-DECISION-V3-STAGE2A-PEAK-CONTINUATION-ANATOMY",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "observable_arm_trades": len(eligible),
        "trades_with_record_local_peak": len({item.position_id for item in candidates}),
        "trades_with_terminal_peak": len({item.position_id for item in terminal}),
        "right_censored_after_local_peak": (
            len({item.position_id for item in candidates})
            - len({item.position_id for item in terminal})
        ),
        "censored_no_record_local_peak": len(eligible) - len({item.position_id for item in candidates}),
        "record_local_peak_candidates": len(candidates),
        "continued_candidates": sum(item.label == "CONTINUED" for item in candidates),
        "terminal_candidates": len(terminal),
        "terminal_observed_peak_vs_true_mfe_median_pct": (
            100.0 * (_median(terminal_ratios) or 0.0)
        ),
        "terminal_observed_peak_vs_true_mfe_weighted_pct": (
            100.0 * weighted_terminal_peak / weighted_true_peak if weighted_true_peak else 0.0
        ),
        "terminal_peak_at_least_80pct_true_mfe_share_pct": _pct(
            sum(ratio >= 0.80 for ratio in terminal_ratios),
            len(terminal_ratios),
        ),
        "peak_bands": {},
        "horizons": {},
    }

    for band in ("0.30-0.50", "0.50-1.00", "1.00-2.00", ">=2.00"):
        rows = [item for item in candidates if _peak_band(float(item.peak_pct)) == band]
        terminal_count = sum(item.label == "TERMINAL" for item in rows)
        result["peak_bands"][band] = {
            "n": len(rows),
            "terminal": terminal_count,
            "continued": len(rows) - terminal_count,
            "terminal_rate_pct": _pct(terminal_count, len(rows)),
        }

    for horizon in horizons_seconds:
        rows = []
        for candidate in candidates:
            metrics = candidate_metrics(
                observations[candidate.position_id],
                candidate,
                horizon_seconds=int(horizon),
            )
            if metrics is not None:
                rows.append(metrics)

        terminal_rows = [row for row in rows if row["label"] == "TERMINAL"]
        continued_rows = [row for row in rows if row["label"] == "CONTINUED"]
        rules: dict[str, Callable[[dict[str, Any]], bool]] = {
            "giveback_ge_10": lambda row: row["giveback_ratio"] >= 0.10,
            "giveback_ge_15": lambda row: row["giveback_ratio"] >= 0.15,
            "giveback_ge_20": lambda row: row["giveback_ratio"] >= 0.20,
            "giveback_ge_20_and_flow_opposite": (
                lambda row: row["giveback_ratio"] >= 0.20 and row["flow_opposite"]
            ),
            "giveback_ge_15_and_not_flow_aligned": (
                lambda row: row["giveback_ratio"] >= 0.15 and not row["flow_aligned"]
            ),
        }
        result["horizons"][str(horizon)] = {
            "covered": len(rows),
            "coverage_pct": _pct(len(rows), len(candidates)),
            "labels": {
                "CONTINUED": _label_summary(continued_rows),
                "TERMINAL": _label_summary(terminal_rows),
            },
            "rule_diagnostics": {
                name: _rule_metric(terminal_rows, continued_rows, predicate)
                for name, predicate in rules.items()
            },
        }

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=DEFAULT_START_MS)
    parser.add_argument("--cutoff-ms", type=int, default=DEFAULT_CUTOFF_MS)
    parser.add_argument("--arm-pct", type=float, default=DEFAULT_ARM_PCT)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = build_anatomy(
        start_ms=args.start_ms,
        cutoff_ms=args.cutoff_ms,
        arm_pct=args.arm_pct,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
