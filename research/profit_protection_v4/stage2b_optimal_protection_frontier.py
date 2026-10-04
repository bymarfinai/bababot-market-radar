from __future__ import annotations

import argparse
import itertools
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_radar.persistence import _postgres_connect


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE2A = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2a_observable_realized_leakage_evidence.json"
)
DEFAULT_SWEEP = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2b_optimal_protection_frontier_sweep.json"
)
DEFAULT_RESULT = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2b_optimal_protection_frontier.json"
)

ARM_PCTS = (0.30, 0.50, 0.75, 1.00, 1.50, 2.00)
RETAIN_RATIOS = (0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.60, 0.50)
CONFIRM_SAMPLES = (1, 2, 3)


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def gross_pnl(
    side: str,
    entry_price: float,
    exit_price: float,
    quantity: float,
) -> float:
    if side.upper() == "LONG":
        return quantity * (exit_price - entry_price)
    return quantity * (entry_price - exit_price)


def exit_fill_price(
    side: str,
    market_price: float,
    slippage_bps: float,
) -> float:
    slip = slippage_bps / 10_000.0
    if side.upper() == "LONG":
        return market_price * (1.0 - slip)
    return market_price * (1.0 + slip)


def load_market_data(
    position_ids: list[str],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    position_id, side, opened_at_ms, closed_at_ms,
                    entry_price, realized_pnl, realized_pnl_pct, raw_json
                from positions
                where position_id=any(%s)
                """,
                (position_ids,),
            )
            cols = [item[0] for item in cur.description]
            positions = {
                row[0]: dict(zip(cols, row))
                for row in cur.fetchall()
            }

            cur.execute(
                """
                select
                    position_id, observed_at_ms, current_price, current_pnl_pct
                from pp_v3_fast_peak_observations
                where position_id=any(%s)
                order by position_id, observed_at_ms
                """,
                (position_ids,),
            )
            cols = [item[0] for item in cur.description]
            observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in cur.fetchall():
                observations[row[0]].append(dict(zip(cols, row)))

            cur.execute(
                """
                select
                    position_id, action, executed_at_ms,
                    executed_quantity, fill_price, fee
                from paper_orders
                where position_id=any(%s)
                  and status='FILLED'
                order by position_id, executed_at_ms
                """,
                (position_ids,),
            )
            cols = [item[0] for item in cur.description]
            orders: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in cur.fetchall():
                orders[row[0]].append(dict(zip(cols, row)))

    return positions, observations, orders


def simulate_trade(
    row: dict[str, Any],
    *,
    arm_pct: float,
    retain_ratio: float,
    confirm_samples: int,
    positions: dict[str, dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    orders: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    position_id = str(row["position_id"])
    position = positions[position_id]
    side = str(position["side"]).upper()
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    entry = float(position["entry_price"])
    metadata = json.loads(position.get("raw_json") or "{}")

    initial_quantity = float(metadata.get("initial_quantity") or 0.0)
    initial_notional = float(
        metadata.get("initial_notional_usdt") or 500.0
    )
    entry_fee_total = float(metadata.get("entry_fee_total") or 0.0)
    fee_rate = float(metadata.get("fee_rate") or 0.00075)
    slippage_bps = float(metadata.get("slippage_bps") or 2.0)

    path = [
        item
        for item in observations[position_id]
        if opened <= int(item["observed_at_ms"]) <= closed
    ]
    running_peak = float("-inf")
    consecutive = 0
    trigger: dict[str, Any] | None = None
    trigger_peak: float | None = None

    for item in path:
        current = float(item["current_pnl_pct"])
        running_peak = max(running_peak, current)
        condition = (
            running_peak >= arm_pct
            and current <= running_peak * retain_ratio
        )
        consecutive = consecutive + 1 if condition else 0
        if consecutive >= confirm_samples:
            trigger = item
            trigger_peak = running_peak
            break

    if trigger is None:
        return {
            "triggered": False,
            "sim_pct": float(position["realized_pnl_pct"]),
            "sim_usdt": float(position["realized_pnl"]),
            "trigger_at_ms": None,
            "trigger_delay_s": None,
            "trigger_peak_pct": None,
        }

    trigger_at = int(trigger["observed_at_ms"])
    realized_before = 0.0
    quantity_closed_before = 0.0
    entry_fee_allocated_before = 0.0

    for order in orders[position_id]:
        if str(order["action"]).upper() == "OPEN":
            continue
        if order["executed_at_ms"] is None:
            continue
        if int(order["executed_at_ms"]) > trigger_at:
            continue

        quantity = float(order["executed_quantity"] or 0.0)
        if quantity <= 0.0:
            continue

        allocated_entry_fee = (
            entry_fee_total * (quantity / initial_quantity)
            if initial_quantity > 0.0
            else 0.0
        )
        realized_before += (
            gross_pnl(
                side,
                entry,
                float(order["fill_price"]),
                quantity,
            )
            - allocated_entry_fee
            - float(order["fee"] or 0.0)
        )
        quantity_closed_before += quantity
        entry_fee_allocated_before += allocated_entry_fee

    remaining = max(0.0, initial_quantity - quantity_closed_before)
    fill = exit_fill_price(
        side,
        float(trigger["current_price"]),
        slippage_bps,
    )
    exit_fee = remaining * fill * fee_rate
    remaining_entry_fee = max(
        0.0,
        entry_fee_total - entry_fee_allocated_before,
    )
    net = (
        realized_before
        + gross_pnl(side, entry, fill, remaining)
        - remaining_entry_fee
        - exit_fee
    )
    simulated_pct = (
        100.0 * net / initial_notional
        if initial_notional > 0.0
        else 0.0
    )

    peak_timestamp: int | None = None
    seen_peak = float("-inf")
    for item in path:
        if int(item["observed_at_ms"]) > trigger_at:
            break
        pnl = float(item["current_pnl_pct"])
        if pnl > seen_peak + 1e-12:
            seen_peak = pnl
            peak_timestamp = int(item["observed_at_ms"])

    return {
        "triggered": True,
        "sim_pct": simulated_pct,
        "sim_usdt": net,
        "trigger_at_ms": trigger_at,
        "trigger_delay_s": (
            (trigger_at - peak_timestamp) / 1000.0
            if peak_timestamp is not None
            else None
        ),
        "trigger_peak_pct": trigger_peak,
    }


def subgroup_metrics(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    retention = [
        float(sim["sim_pct"]) / float(row["observable_net_peak_pct"])
        for row, sim in pairs
        if float(row["observable_net_peak_pct"]) > 0.0
    ]
    return {
        "n": len(pairs),
        "total_usdt": sum(float(sim["sim_usdt"]) for _, sim in pairs),
        "actual_total_usdt": sum(
            float(row["realized_pnl_usdt"]) for row, _ in pairs
        ),
        "median_retention": _median(retention),
        "ret_ge80_share": (
            sum(value >= 0.80 for value in retention) / len(retention)
            if retention else None
        ),
        "nonpositive_n": sum(
            float(sim["sim_pct"]) <= 0.0 for _, sim in pairs
        ),
    }


def metrics(
    rows: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pairs = [(row, results[str(row["position_id"])]) for row in rows]
    simulated_pct = [float(sim["sim_pct"]) for _, sim in pairs]
    simulated_usd = [float(sim["sim_usdt"]) for _, sim in pairs]
    actual_usd = [float(row["realized_pnl_usdt"]) for row, _ in pairs]
    retention = [
        float(sim["sim_pct"]) / float(row["observable_net_peak_pct"])
        for row, sim in pairs
        if float(row["observable_net_peak_pct"]) > 0.0
    ]

    peak_ge050 = [
        pair for pair in pairs
        if float(pair[0]["observable_net_peak_pct"]) >= 0.50
    ]
    runner_ge1 = [
        pair for pair in pairs
        if float(pair[0]["observable_net_peak_pct"]) >= 1.00
    ]
    runner_ge2 = [
        pair for pair in pairs
        if float(pair[0]["observable_net_peak_pct"]) >= 2.00
    ]

    delays = [
        float(sim["trigger_delay_s"])
        for _, sim in pairs
        if sim["triggered"] and sim["trigger_delay_s"] is not None
    ]

    return {
        "n": len(rows),
        "total_usdt": sum(simulated_usd),
        "actual_total_usdt": sum(actual_usd),
        "delta_usdt": sum(simulated_usd) - sum(actual_usd),
        "mean_pct": statistics.mean(simulated_pct),
        "median_pct": _median(simulated_pct),
        "win_n": sum(value > 0.0 for value in simulated_pct),
        "win_rate": (
            sum(value > 0.0 for value in simulated_pct) / len(simulated_pct)
        ),
        "trigger_n": sum(bool(sim["triggered"]) for _, sim in pairs),
        "median_trigger_delay_s": _median(delays),
        "median_retention": _median(retention),
        "ret_ge80_share": (
            sum(value >= 0.80 for value in retention) / len(retention)
            if retention else None
        ),
        "ret_ge50_share": (
            sum(value >= 0.50 for value in retention) / len(retention)
            if retention else None
        ),
        "negative_retention_share": (
            sum(value < 0.0 for value in retention) / len(retention)
            if retention else None
        ),
        "peak_ge050": subgroup_metrics(peak_ge050),
        "runner_ge1": subgroup_metrics(runner_ge1),
        "runner_ge2": subgroup_metrics(runner_ge2),
    }


def baseline_results(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(row["position_id"]): {
            "triggered": False,
            "sim_pct": float(row["actual_realized_net_pct"]),
            "sim_usdt": float(row["realized_pnl_usdt"]),
            "trigger_at_ms": None,
            "trigger_delay_s": None,
            "trigger_peak_pct": None,
        }
        for row in rows
    }


def pareto_frontier(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        values = (
            float(candidate["dev"]["total_usdt"]),
            float(candidate["dev"]["median_retention"]),
            float(candidate["dev"]["runner_ge1"]["median_retention"]),
        )
        dominated = False
        for other_index, other in enumerate(candidates):
            if index == other_index:
                continue
            other_values = (
                float(other["dev"]["total_usdt"]),
                float(other["dev"]["median_retention"]),
                float(other["dev"]["runner_ge1"]["median_retention"]),
            )
            if (
                all(
                    other_value >= value - 1e-12
                    for other_value, value in zip(other_values, values)
                )
                and any(
                    other_value > value + 1e-12
                    for other_value, value in zip(other_values, values)
                )
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def holdout_positive(
    candidate: dict[str, Any],
    baseline_late: dict[str, Any],
) -> bool:
    late = candidate["late"]
    return (
        float(late["total_usdt"])
        > float(baseline_late["total_usdt"]) + 1e-12
        and float(late["peak_ge050"]["median_retention"])
        > float(baseline_late["peak_ge050"]["median_retention"]) + 1e-12
        and float(late["runner_ge1"]["total_usdt"])
        >= float(baseline_late["runner_ge1"]["total_usdt"]) - 1e-12
        and int(late["peak_ge050"]["nonpositive_n"])
        <= int(baseline_late["peak_ge050"]["nonpositive_n"])
    )


def concentration_diagnostic(
    rows: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        sim = results[str(row["position_id"])]
        records.append(
            {
                "position_id": row["position_id"],
                "symbol": row["symbol"],
                "side": row["side"],
                "third": ("EARLY", "MID", "LATE")[min(index // 33, 2)],
                "triggered": bool(sim["triggered"]),
                "actual_pct": float(row["actual_realized_net_pct"]),
                "sim_pct": float(sim["sim_pct"]),
                "delta_usdt": (
                    float(sim["sim_usdt"])
                    - float(row["realized_pnl_usdt"])
                ),
                "observable_net_peak_pct": float(
                    row["observable_net_peak_pct"]
                ),
                "trigger_peak_pct": sim["trigger_peak_pct"],
            }
        )

    thirds: dict[str, Any] = {}
    for third in ("EARLY", "MID", "LATE"):
        group = [item for item in records if item["third"] == third]
        thirds[third] = {
            "delta_usdt": sum(float(item["delta_usdt"]) for item in group),
            "trigger_n": sum(bool(item["triggered"]) for item in group),
            "positive_changed_n": sum(
                bool(item["triggered"])
                and float(item["delta_usdt"]) > 1e-12
                for item in group
            ),
            "negative_changed_n": sum(
                bool(item["triggered"])
                and float(item["delta_usdt"]) < -1e-12
                for item in group
            ),
        }

    late_triggered = [
        item
        for item in records
        if item["third"] == "LATE" and item["triggered"]
    ]
    late_triggered.sort(
        key=lambda item: float(item["delta_usdt"]),
        reverse=True,
    )
    late_total = sum(float(item["delta_usdt"]) for item in late_triggered)
    positive = [
        float(item["delta_usdt"])
        for item in late_triggered
        if float(item["delta_usdt"]) > 0.0
    ]
    positive.sort(reverse=True)

    return {
        "chronological_thirds": thirds,
        "late_triggered": late_triggered,
        "late_delta_usdt": late_total,
        "late_top1_positive_contribution_share": (
            positive[0] / late_total
            if positive and late_total > 0.0
            else None
        ),
        "late_top3_positive_contribution_share": (
            sum(positive[:3]) / late_total
            if positive and late_total > 0.0
            else None
        ),
    }


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    rows = sorted(
        json.loads(DEFAULT_STAGE2A.read_text(encoding="utf-8")),
        key=lambda row: (
            int(row["opened_at_ms"]),
            str(row["position_id"]),
        ),
    )
    if len(rows) != 99:
        raise RuntimeError(f"expected 99 Stage2A rows, got {len(rows)}")

    ids = [str(row["position_id"]) for row in rows]
    positions, observations, orders = load_market_data(ids)

    dev = rows[:66]
    late = rows[66:]
    baseline = baseline_results(rows)
    baseline_metrics = {
        "dev": metrics(dev, baseline),
        "late": metrics(late, baseline),
        "all": metrics(rows, baseline),
    }

    candidates: list[dict[str, Any]] = []
    result_cache: dict[tuple[float, float, int], dict[str, dict[str, Any]]] = {}

    for arm_pct, retain_ratio, confirm_samples in itertools.product(
        ARM_PCTS,
        RETAIN_RATIOS,
        CONFIRM_SAMPLES,
    ):
        key = (arm_pct, retain_ratio, confirm_samples)
        simulated = {
            str(row["position_id"]): simulate_trade(
                row,
                arm_pct=arm_pct,
                retain_ratio=retain_ratio,
                confirm_samples=confirm_samples,
                positions=positions,
                observations=observations,
                orders=orders,
            )
            for row in rows
        }
        result_cache[key] = simulated
        candidates.append(
            {
                "arm_pct": arm_pct,
                "retain_ratio": retain_ratio,
                "confirm_samples": confirm_samples,
                "dev": metrics(dev, simulated),
                "late": metrics(late, simulated),
                "all": metrics(rows, simulated),
            }
        )

    frontier = pareto_frontier(candidates)
    for candidate in frontier:
        candidate["holdout_positive"] = holdout_positive(
            candidate,
            baseline_metrics["late"],
        )

    holdout = [
        candidate
        for candidate in frontier
        if candidate["holdout_positive"]
    ]

    if not holdout:
        references: dict[str, Any] = {}
        concentration: dict[str, Any] = {}
    else:
        best_total = max(
            holdout,
            key=lambda item: float(item["late"]["total_usdt"]),
        )
        best_retention = max(
            holdout,
            key=lambda item: float(
                item["late"]["peak_ge050"]["median_retention"]
            ),
        )
        safest_runner = max(
            holdout,
            key=lambda item: float(
                item["late"]["runner_ge1"]["total_usdt"]
            ),
        )
        references = {
            "best_holdout_total": best_total,
            "best_holdout_peak_ge050_retention": best_retention,
            "safest_runner_reference": safest_runner,
        }
        key = (
            float(best_total["arm_pct"]),
            float(best_total["retain_ratio"]),
            int(best_total["confirm_samples"]),
        )
        concentration = concentration_diagnostic(
            rows,
            result_cache[key],
        )

    sweep = {
        "stage": "PP-V4-2B",
        "status": "COMPLETE_CAUSAL_STATIC_FRONTIER",
        "grid": {
            "arm_pcts": list(ARM_PCTS),
            "retain_ratios": list(RETAIN_RATIOS),
            "confirm_samples": list(CONFIRM_SAMPLES),
            "candidate_count": len(candidates),
        },
        "split": {
            "development_n": len(dev),
            "late_holdout_n": len(late),
        },
        "baseline": baseline_metrics,
        "candidate_count": len(candidates),
        "frontier_count": len(frontier),
        "holdout_positive_count": len(holdout),
        "frontier": frontier,
        "all_candidates": candidates,
    }

    result = {
        "stage": "PP-V4-2B",
        "status": "COMPLETE_RESEARCH_ONLY",
        "candidate_count": len(candidates),
        "frontier_count": len(frontier),
        "holdout_positive_count": len(holdout),
        "baseline": baseline_metrics,
        "holdout_positive_candidates": sorted(
            holdout,
            key=lambda item: float(item["late"]["total_usdt"]),
            reverse=True,
        ),
        "references": references,
        "best_reference_concentration": concentration,
        "decision": {
            "holdout_positive_exists": bool(holdout),
            "proceed_to_v4_2c_runner_preservation": bool(holdout),
            "selected_runtime_policy": None,
            "runtime_change_authority": "NONE",
            "protection_authority": "NONE",
            "next_stage": (
                "V4-2C_RUNNER_PRESERVATION"
                if holdout
                else "PROTECTION_FEATURE_REDESIGN"
            ),
        },
    }
    return sweep, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-output", default=str(DEFAULT_SWEEP))
    parser.add_argument("--result-output", default=str(DEFAULT_RESULT))
    args = parser.parse_args()

    sweep, result = run()
    Path(args.sweep_output).write_text(
        json.dumps(sweep, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    Path(args.result_output).write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "frontier_count": result["frontier_count"],
                "holdout_positive_count": result["holdout_positive_count"],
                "decision": result["decision"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
