from __future__ import annotations

import argparse
import csv
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

from market_radar.persistence import _postgres_connect
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
from research.profit_protection_v4.stage3c3_multicycle_volnorm_detector import (
    metrics as stage3c3_metrics,
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

LOOKBACK_SECONDS = (30, 60)
REQUIRED_VOTES = (2, 3, 4)
CONTEXT_MODES = ("PATH_ONLY", "CONTEXT_BONUS")

RUNNER_QUALIFY = 1.50
RUNNER_RETAIN = 0.90
RUNNER_CONFIRM = 2
GRACE_SECONDS = 10
MAX_VETOES = 2


def load_baseline() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASELINE_CSV.open(encoding="utf-8")))
    for row in rows:
        for key in ("clean_mfe_pct", "protected_pct", "opened_at_ms"):
            row[key] = None if row[key] == "" else float(row[key])
    return rows


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _ols_slope(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    x_mean = statistics.mean(x for x, _ in points)
    y_mean = statistics.mean(y for _, y in points)
    denom = sum((x - x_mean) ** 2 for x, _ in points)
    if denom <= 0:
        return None
    return sum(
        (x - x_mean) * (y - y_mean)
        for x, y in points
    ) / denom


def load_entry_context(
    position_ids: list[str],
    positions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct position_id, signal_id
                from trade_events
                where position_id=any(%s)
                  and signal_id is not null
                """,
                (position_ids,),
            )
            signal_by_position = {
                str(position_id): str(signal_id)
                for position_id, signal_id in cur.fetchall()
            }

            signal_ids = list(signal_by_position.values())
            cur.execute(
                """
                select
                    signal_id, score_edge, volume_ratio,
                    structure_status, taker_bias,
                    raw_oi_change_pct, funding_rate,
                    market_regime, decision_context_balance
                from signals
                where signal_id=any(%s)
                """,
                (signal_ids,),
            )
            signal_rows = {
                str(row[0]): {
                    "score_edge": row[1],
                    "volume_ratio": row[2],
                    "structure_status": row[3],
                    "taker_bias": row[4],
                    "raw_oi_change_pct": row[5],
                    "funding_rate": row[6],
                    "market_regime": row[7],
                    "decision_context_balance": row[8],
                }
                for row in cur.fetchall()
            }

    result: dict[str, dict[str, Any]] = {}
    for position_id in position_ids:
        signal_id = signal_by_position.get(position_id)
        signal = signal_rows.get(signal_id or "", {})
        raw = positions[position_id].get("raw_json") or "{}"
        metadata = raw if isinstance(raw, dict) else json.loads(raw)
        families = metadata.get("stage11c_evidence_families") or {}
        supportive_status = {"ALIGNED", "SUPPORTIVE"}
        supportive_count = sum(
            str(value).upper() in supportive_status
            for value in families.values()
        )
        context_balance = signal.get("decision_context_balance")
        strong = (
            supportive_count >= 3
            and context_balance is not None
            and int(context_balance) >= 3
        )
        result[position_id] = {
            "position_id": position_id,
            "signal_id": signal_id,
            "stage11c_supportive_family_count": supportive_count,
            "stage11c_price_structure": families.get("PRICE_STRUCTURE"),
            "stage11c_flow": families.get("FLOW"),
            "stage11c_positioning": families.get("POSITIONING"),
            "stage11c_regime": families.get("REGIME"),
            "decision_context_balance": context_balance,
            "market_regime": signal.get("market_regime"),
            "structure_status": signal.get("structure_status"),
            "taker_bias": signal.get("taker_bias"),
            "score_edge": signal.get("score_edge"),
            "volume_ratio": signal.get("volume_ratio"),
            "raw_oi_change_pct": signal.get("raw_oi_change_pct"),
            "funding_rate": signal.get("funding_rate"),
            "strong_entry_context": strong,
        }
    return result


def topology_votes(
    path: list[dict[str, Any]],
    index: int,
    *,
    running_peak: float,
    lookback_seconds: int,
    strong_entry_context: bool,
    context_mode: str,
) -> dict[str, Any]:
    now_ms = int(path[index]["observed_at_ms"])
    start_ms = now_ms - lookback_seconds * 1000
    split_ms = now_ms - (lookback_seconds * 1000) / 2.0

    window = [
        item
        for item in path[: index + 1]
        if int(item["observed_at_ms"]) >= start_ms
    ]
    older = [
        item for item in window
        if int(item["observed_at_ms"]) < split_ms
    ]
    recent = [
        item for item in window
        if int(item["observed_at_ms"]) >= split_ms
    ]

    older_pnls = [float(item["current_pnl_pct"]) for item in older]
    recent_pnls = [float(item["current_pnl_pct"]) for item in recent]

    higher_low_vote = (
        len(older_pnls) >= 2
        and len(recent_pnls) >= 2
        and min(recent_pnls) >= min(older_pnls)
    )

    points = [
        (
            (int(item["observed_at_ms"]) - now_ms) / 1000.0,
            float(item["current_pnl_pct"]),
        )
        for item in window
    ]
    slope = _ols_slope(points)
    positive_slope_vote = slope is not None and slope > 0.0

    def abs_changes(items: list[dict[str, Any]]) -> list[float]:
        return [
            abs(
                float(items[j]["current_pnl_pct"])
                - float(items[j - 1]["current_pnl_pct"])
            )
            for j in range(1, len(items))
        ]

    older_changes = abs_changes(older)
    recent_changes = abs_changes(recent)
    older_vol = _median(older_changes)
    recent_vol = _median(recent_changes)
    contraction_ratio = (
        recent_vol / older_vol
        if (
            recent_vol is not None
            and older_vol is not None
            and older_vol > 0.0
        )
        else None
    )
    volatility_contraction_vote = (
        contraction_ratio is not None
        and contraction_ratio <= 0.80
    )

    underwater_share = (
        sum(
            float(item["current_pnl_pct"]) <= running_peak * RUNNER_RETAIN
            for item in window
        )
        / len(window)
        if window
        else 1.0
    )
    brief_underwater_vote = underwater_share <= 0.50

    path_votes = {
        "higher_low": bool(higher_low_vote),
        "positive_recovery_slope": bool(positive_slope_vote),
        "volatility_contraction": bool(volatility_contraction_vote),
        "brief_underwater": bool(brief_underwater_vote),
    }
    context_vote = (
        context_mode == "CONTEXT_BONUS"
        and bool(strong_entry_context)
    )
    vote_count = sum(path_votes.values()) + int(context_vote)

    return {
        "path_votes": path_votes,
        "context_vote": context_vote,
        "vote_count": vote_count,
        "window_n": len(window),
        "slope_pp_per_sec": slope,
        "volatility_contraction_ratio": contraction_ratio,
        "underwater_share": underwater_share,
    }


def topology_veto_signal(
    path: list[dict[str, Any]],
    *,
    lookback_seconds: int,
    required_votes: int,
    context_mode: str,
    strong_entry_context: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    running_peak = float("-inf")
    runner_mode = False
    runner_consecutive = 0
    vetoes_started = 0

    grace: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] = []

    for index, item in enumerate(path):
        observed_at = int(item["observed_at_ms"])
        current = float(item["current_pnl_pct"])

        made_new_high = current > running_peak
        if made_new_high:
            running_peak = current
            runner_consecutive = 0
            if grace is not None:
                decisions.append(
                    {
                        **grace["decision"],
                        "veto_outcome": "SUCCESS_NEW_HIGH",
                        "veto_resolved_at_ms": observed_at,
                    }
                )
                grace = None

        if not runner_mode and running_peak >= RUNNER_QUALIFY:
            runner_mode = True
            runner_consecutive = 0

        if not runner_mode:
            continue

        if grace is not None:
            if grace is None:
                continue
            if observed_at >= int(grace["expires_at_ms"]):
                decision = {
                    **grace["decision"],
                    "veto_outcome": "GRACE_TIMEOUT_CLOSE",
                    "veto_resolved_at_ms": observed_at,
                }
                decisions.append(decision)
                return (
                    {
                        "signal_at_ms": observed_at,
                        "signal_pnl_pct": current,
                        "signal_running_peak_pct": float(
                            grace["running_peak_pct"]
                        ),
                        "close_reason": "GRACE_TIMEOUT_CLOSE",
                        "vetoes_started": vetoes_started,
                    },
                    decisions,
                )
            continue

        condition = current <= running_peak * RUNNER_RETAIN
        runner_consecutive = (
            runner_consecutive + 1 if condition else 0
        )
        if runner_consecutive < RUNNER_CONFIRM:
            continue

        votes = topology_votes(
            path,
            index,
            running_peak=running_peak,
            lookback_seconds=lookback_seconds,
            strong_entry_context=strong_entry_context,
            context_mode=context_mode,
        )
        base_decision = {
            "candidate_at_ms": observed_at,
            "candidate_pnl_pct": current,
            "candidate_running_peak_pct": running_peak,
            "lookback_seconds": lookback_seconds,
            "required_votes": required_votes,
            "context_mode": context_mode,
            **votes,
        }

        should_veto = (
            votes["vote_count"] >= required_votes
            and vetoes_started < MAX_VETOES
        )
        if not should_veto:
            decisions.append(
                {
                    **base_decision,
                    "veto_outcome": "ALLOW_CLOSE",
                    "veto_resolved_at_ms": observed_at,
                }
            )
            return (
                {
                    "signal_at_ms": observed_at,
                    "signal_pnl_pct": current,
                    "signal_running_peak_pct": running_peak,
                    "close_reason": "ALLOW_CLOSE",
                    "vetoes_started": vetoes_started,
                },
                decisions,
            )

        vetoes_started += 1
        grace = {
            "expires_at_ms": observed_at + GRACE_SECONDS * 1000,
            "running_peak_pct": running_peak,
            "decision": base_decision,
        }
        runner_consecutive = 0

    return None, decisions


def label_signal(
    path: list[dict[str, Any]],
    signal: dict[str, Any] | None,
    final_observed_peak_pct: float,
) -> dict[str, Any]:
    if signal is None:
        return {
            "label": "NO_SIGNAL",
            "retention_vs_final_observed_peak": None,
        }

    signal_at = int(signal["signal_at_ms"])
    signal_peak = float(signal["signal_running_peak_pct"])
    later = [
        float(item["current_pnl_pct"])
        for item in path
        if int(item["observed_at_ms"]) > signal_at
    ]
    premature = any(value > signal_peak for value in later)
    return {
        "label": (
            "PREMATURE_FALSE_REVERSAL"
            if premature
            else "CORRECT_FINAL_REVERSAL"
        ),
        "retention_vs_final_observed_peak": (
            float(signal["signal_pnl_pct"]) / final_observed_peak_pct
            if final_observed_peak_pct > 0.0
            else None
        ),
    }


def candidate_metrics(
    group: list[dict[str, Any]],
    paths: dict[str, list[dict[str, Any]]],
    contexts: dict[str, dict[str, Any]],
    params: tuple[int, int, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lookback_seconds, required_votes, context_mode = params
    details: list[dict[str, Any]] = []

    for row in group:
        position_id = str(row["position_id"])
        signal, decisions = topology_veto_signal(
            paths[position_id],
            lookback_seconds=lookback_seconds,
            required_votes=required_votes,
            context_mode=context_mode,
            strong_entry_context=bool(
                contexts[position_id]["strong_entry_context"]
            ),
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
                "strong_entry_context": bool(
                    contexts[position_id]["strong_entry_context"]
                ),
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
                "close_reason": (
                    signal["close_reason"] if signal else None
                ),
                "vetoes_started": (
                    signal["vetoes_started"]
                    if signal
                    else sum(
                        1 for item in decisions
                        if item["veto_outcome"] == "SUCCESS_NEW_HIGH"
                    )
                ),
                "successful_vetoes": sum(
                    item["veto_outcome"] == "SUCCESS_NEW_HIGH"
                    for item in decisions
                ),
                "grace_timeout_close_n": sum(
                    item["veto_outcome"] == "GRACE_TIMEOUT_CLOSE"
                    for item in decisions
                ),
                "retention_vs_final_observed_peak": (
                    outcome["retention_vs_final_observed_peak"]
                ),
                "decision_trace_json": json.dumps(
                    decisions,
                    sort_keys=True,
                    separators=(",", ":"),
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
        "vetoes_started_n": sum(
            int(row["vetoes_started"]) for row in details
        ),
        "successful_vetoes_n": sum(
            int(row["successful_vetoes"]) for row in details
        ),
        "grace_timeout_close_n": sum(
            int(row["grace_timeout_close_n"]) for row in details
        ),
    }
    return result, details


def build() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    baseline = load_baseline()
    triggered = [
        row for row in baseline
        if str(row["protection_actions"]) != "NO_ACTION"
    ]
    all_ids = [str(row["position_id"]) for row in triggered]
    positions, observations, _ = load_market_data(all_ids)

    paths: dict[str, list[dict[str, Any]]] = {}
    runner: list[dict[str, Any]] = []
    for row in triggered:
        position_id = str(row["position_id"])
        position = positions[position_id]
        opened = int(position["opened_at_ms"])
        closed = int(position["closed_at_ms"])
        path = [
            item for item in observations[position_id]
            if opened <= int(item["observed_at_ms"]) <= closed
        ]
        paths[position_id] = path
        if not path:
            continue
        final_peak = max(float(item["current_pnl_pct"]) for item in path)
        if final_peak < RUNNER_QUALIFY:
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

    runner_ids = [str(row["position_id"]) for row in runner]
    contexts = load_entry_context(runner_ids, positions)
    if len(contexts) != len(runner):
        raise RuntimeError(
            f"context coverage mismatch {len(contexts)} != {len(runner)}"
        )
    if any(contexts[pid]["signal_id"] is None for pid in runner_ids):
        raise RuntimeError("missing exact signal_id context join")

    stage3b = {
        row["position_id"]: row
        for row in csv.DictReader(
            STAGE3B_TRADES_CSV.open(encoding="utf-8")
        )
    }
    v42_dev, _ = v42_metrics(dev, paths, stage3b)
    v42_late, _ = v42_metrics(late, paths, stage3b)
    v42_all, _ = v42_metrics(runner, paths, stage3b)
    v42_dev_premature = int(v42_dev["premature_false_reversal_n"])

    candidate_space = list(
        itertools.product(
            LOOKBACK_SECONDS,
            REQUIRED_VOTES,
            CONTEXT_MODES,
        )
    )
    sweep: list[dict[str, Any]] = []
    details_cache: dict[
        tuple[int, int, str], list[dict[str, Any]]
    ] = {}

    for params in candidate_space:
        lookback, votes, context_mode = params
        result, details = candidate_metrics(
            dev, paths, contexts, params
        )
        gate = {
            "coverage": result["signal_coverage"] >= 0.50,
            "precision": result["precision"] >= 0.65,
            "premature": result["premature_share"] <= 0.35,
            "median_retention": (
                result["median_correct_retention"] is not None
                and result["median_correct_retention"] >= 0.80
            ),
            "ge80_share": result["correct_retention_ge80_share"] >= 0.50,
            "improves_premature": (
                result["premature_false_reversal_n"]
                < v42_dev_premature
            ),
        }
        sweep.append(
            {
                "lookback_seconds": lookback,
                "required_votes": votes,
                "context_mode": context_mode,
                **result,
                "gate_coverage": gate["coverage"],
                "gate_precision": gate["precision"],
                "gate_premature": gate["premature"],
                "gate_median_retention": gate["median_retention"],
                "gate_ge80_share": gate["ge80_share"],
                "gate_improves_premature": gate["improves_premature"],
                "gate_pass_count": sum(gate.values()),
                "eligible": all(gate.values()),
            }
        )
        details_cache[params] = details

    eligible = [row for row in sweep if bool(row["eligible"])]
    eligible.sort(
        key=lambda row: (
            float(row["precision"]),
            -int(row["premature_false_reversal_n"]),
            float(row["correct_retention_ge80_share"]),
            float(row["median_correct_retention"]),
            float(row["signal_coverage"]),
            -int(row["vetoes_started_n"]),
            -int(row["lookback_seconds"]),
            int(row["required_votes"]),
            row["context_mode"] == "PATH_ONLY",
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
            int(selected["lookback_seconds"]),
            int(selected["required_votes"]),
            str(selected["context_mode"]),
        )
        selected_dev_details = details_cache[params]
        selected_late_metrics, selected_late_details = candidate_metrics(
            late, paths, contexts, params
        )
        selected_all_metrics, _ = candidate_metrics(
            runner, paths, contexts, params
        )

    stage3c_dev, _ = stage3c_candidate_metrics(
        dev, paths, (0.80, 60, 0.03, 5)
    )
    stage3c2_dev, _ = stage3c2_metrics(
        dev, paths, (0.80, 15, 0.25, 0.00)
    )
    stage3c3_dev, _ = stage3c3_metrics(
        dev, paths, (0.90, 12, 0.25, 1, 3.0)
    )

    near_miss = [
        row for row in sweep
        if int(row["gate_pass_count"]) == 5
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
            -int(row["premature_false_reversal_n"]),
        ),
        reverse=True,
    )

    population = []
    context_rows = []
    for row in runner:
        pid = str(row["position_id"])
        context = contexts[pid]
        population.append(
            {
                "position_id": pid,
                "symbol": row["symbol"],
                "side": row["side"],
                "opened_at_ms": int(row["opened_at_ms"]),
                "split": row["split"],
                "final_observed_peak_pct": float(
                    row["final_observed_peak_pct"]
                ),
                "strong_entry_context": bool(
                    context["strong_entry_context"]
                ),
            }
        )
        context_rows.append(
            {
                **context,
                "symbol": row["symbol"],
                "side": row["side"],
                "opened_at_ms": int(row["opened_at_ms"]),
                "split": row["split"],
            }
        )

    gate_names = (
        "coverage",
        "precision",
        "premature",
        "median_retention",
        "ge80_share",
        "improves_premature",
    )

    summary = {
        "stage": "PP-V4-3C4",
        "status": (
            "PASS_CANDIDATE" if selected is not None else "NO_PASS"
        ),
        "baseline_name": "Profit Protector V4.2 - Hybrid Protection",
        "runner_capable_trade_n": len(runner),
        "dev_n": len(dev),
        "late_n": len(late),
        "candidate_n": len(sweep),
        "eligible_n": len(eligible),
        "context_join": {
            "exact_position_signal_match_n": sum(
                context["signal_id"] is not None
                for context in contexts.values()
            ),
            "strong_entry_context_n": sum(
                bool(context["strong_entry_context"])
                for context in contexts.values()
            ),
            "source_note": (
                "Exact trade_events signal_id + signals row + "
                "positions.raw_json Stage11C families. No WD5H "
                "symbol/time proxy join."
            ),
        },
        "gate_pass_candidate_counts": {
            name: sum(
                bool(row[f"gate_{name}"]) for row in sweep
            )
            for name in gate_names
        },
        "gate_pass_count_distribution": {
            str(count): sum(
                int(row["gate_pass_count"]) == count
                for row in sweep
            )
            for count in range(7)
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
            "stage3c2_highest_precision_dev": stage3c2_dev,
            "stage3c3_highest_precision_dev": stage3c3_dev,
        },
        "decision": {
            "proceed_to_stage3d": selected is not None,
            "runtime_change_authority": "NONE",
            "paper_or_shadow": False,
            "if_no_pass": (
                "Do not relax gates post hoc. Preserve V4.2 and "
                "record the topology/context hypothesis as rejected."
            ),
        },
    }
    return sweep, population, context_rows, summary


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
    parser.add_argument("--context-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    sweep, population, context_rows, summary = build()
    write_csv(args.sweep_csv, sweep)
    write_csv(args.population_csv, population)
    write_csv(args.context_csv, context_rows)
    Path(args.summary_json).write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
