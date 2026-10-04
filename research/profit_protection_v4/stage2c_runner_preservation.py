from __future__ import annotations

import argparse
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

from research.profit_protection_v4.stage2b_optimal_protection_frontier import (
    exit_fill_price,
    gross_pnl,
    load_market_data,
    simulate_trade as simulate_static,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE2A = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2a_observable_realized_leakage_evidence.json"
)
DEFAULT_SWEEP = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2c_runner_preservation_sweep.json"
)
DEFAULT_RESULT = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2c_runner_preservation.json"
)

SMALL_TEMPLATES = (
    (0.50, 0.60, 2),
    (0.50, 0.60, 3),
    (0.75, 0.80, 2),
    (0.75, 0.90, 3),
)
REDUCE_FRACTIONS = (0.25, 0.50, 0.75)
RUNNER_QUALIFY_PCTS = (1.00, 1.50)
RUNNER_RETAIN = 0.90
RUNNER_CONFIRM = 2

RUNNER_REFERENCE = (1.50, 0.90, 2)
AGGRESSIVE_REFERENCE = (0.50, 0.60, 2)


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def fallback_close_fill(
    position_id: str,
    positions: dict[str, dict[str, Any]],
    orders: dict[str, list[dict[str, Any]]],
) -> tuple[float, int]:
    closes = [
        order
        for order in orders[position_id]
        if str(order["action"]).upper() == "CLOSE"
        and order["executed_at_ms"] is not None
    ]
    if closes:
        final = closes[-1]
        return float(final["fill_price"]), int(final["executed_at_ms"])
    position = positions[position_id]
    return float(position["exit_price"]), int(position["closed_at_ms"])


def preserve_historical_before(
    position_id: str,
    at_ms: int,
    *,
    side: str,
    entry_price: float,
    initial_quantity: float,
    entry_fee_total: float,
    orders: dict[str, list[dict[str, Any]]],
) -> tuple[float, float, float]:
    realized = 0.0
    quantity_closed = 0.0
    entry_fee_allocated = 0.0

    for order in orders[position_id]:
        if str(order["action"]).upper() == "OPEN":
            continue
        if order["executed_at_ms"] is None:
            continue
        if int(order["executed_at_ms"]) > at_ms:
            continue

        quantity = float(order["executed_quantity"] or 0.0)
        if quantity <= 0.0:
            continue

        allocated = (
            entry_fee_total * (quantity / initial_quantity)
            if initial_quantity > 0.0
            else 0.0
        )
        realized += (
            gross_pnl(
                side,
                entry_price,
                float(order["fill_price"]),
                quantity,
            )
            - allocated
            - float(order["fee"] or 0.0)
        )
        quantity_closed += quantity
        entry_fee_allocated += allocated

    return realized, quantity_closed, entry_fee_allocated


def simulate_hybrid(
    row: dict[str, Any],
    *,
    small_template: tuple[float, float, int],
    reduce_fraction: float,
    runner_qualify_pct: float,
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

    small_arm, small_retain, small_confirm = small_template
    running_peak = float("-inf")
    small_consecutive = 0
    runner_consecutive = 0
    runner_mode = False
    small_fired = False
    diverged = False

    realized = 0.0
    quantity_closed = 0.0
    entry_fee_allocated = 0.0
    first_overlay_at: int | None = None
    small_at: int | None = None

    for item in path:
        observed_at = int(item["observed_at_ms"])
        current_pnl = float(item["current_pnl_pct"])
        running_peak = max(running_peak, current_pnl)

        if not runner_mode and running_peak >= runner_qualify_pct:
            runner_mode = True
            small_consecutive = 0

        if runner_mode:
            condition = current_pnl <= running_peak * RUNNER_RETAIN
            runner_consecutive = (
                runner_consecutive + 1 if condition else 0
            )
            if runner_consecutive < RUNNER_CONFIRM:
                continue

            if not diverged:
                (
                    realized,
                    quantity_closed,
                    entry_fee_allocated,
                ) = preserve_historical_before(
                    position_id,
                    observed_at,
                    side=side,
                    entry_price=entry,
                    initial_quantity=initial_quantity,
                    entry_fee_total=entry_fee_total,
                    orders=orders,
                )
                diverged = True
                first_overlay_at = observed_at

            remaining = max(0.0, initial_quantity - quantity_closed)
            fill = exit_fill_price(
                side,
                float(item["current_price"]),
                slippage_bps,
            )
            exit_fee = remaining * fill * fee_rate
            remaining_entry_fee = max(
                0.0,
                entry_fee_total - entry_fee_allocated,
            )
            realized += (
                gross_pnl(side, entry, fill, remaining)
                - remaining_entry_fee
                - exit_fee
            )
            return {
                "sim_usdt": realized,
                "sim_pct": (
                    100.0 * realized / initial_notional
                    if initial_notional > 0.0
                    else 0.0
                ),
                "small_fired": small_fired,
                "runner_closed": True,
                "small_at_ms": small_at,
                "runner_at_ms": observed_at,
                "first_overlay_at_ms": first_overlay_at,
            }

        if small_fired:
            continue

        condition = (
            running_peak >= small_arm
            and current_pnl <= running_peak * small_retain
        )
        small_consecutive = small_consecutive + 1 if condition else 0
        if small_consecutive < small_confirm:
            continue

        if not diverged:
            (
                realized,
                quantity_closed,
                entry_fee_allocated,
            ) = preserve_historical_before(
                position_id,
                observed_at,
                side=side,
                entry_price=entry,
                initial_quantity=initial_quantity,
                entry_fee_total=entry_fee_total,
                orders=orders,
            )
            diverged = True
            first_overlay_at = observed_at

        remaining = max(0.0, initial_quantity - quantity_closed)
        quantity = remaining * reduce_fraction
        fill = exit_fill_price(
            side,
            float(item["current_price"]),
            slippage_bps,
        )
        exit_fee = quantity * fill * fee_rate
        allocated_entry_fee = (
            entry_fee_total * (quantity / initial_quantity)
            if initial_quantity > 0.0
            else 0.0
        )
        realized += (
            gross_pnl(side, entry, fill, quantity)
            - allocated_entry_fee
            - exit_fee
        )
        quantity_closed += quantity
        entry_fee_allocated += allocated_entry_fee
        small_fired = True
        small_at = observed_at
        small_consecutive = 0

    if not diverged:
        return {
            "sim_usdt": float(position["realized_pnl"]),
            "sim_pct": float(position["realized_pnl_pct"]),
            "small_fired": False,
            "runner_closed": False,
            "small_at_ms": None,
            "runner_at_ms": None,
            "first_overlay_at_ms": None,
        }

    remaining = max(0.0, initial_quantity - quantity_closed)
    close_fill, _ = fallback_close_fill(position_id, positions, orders)
    exit_fee = remaining * close_fill * fee_rate
    remaining_entry_fee = max(
        0.0,
        entry_fee_total - entry_fee_allocated,
    )
    realized += (
        gross_pnl(side, entry, close_fill, remaining)
        - remaining_entry_fee
        - exit_fee
    )

    return {
        "sim_usdt": realized,
        "sim_pct": (
            100.0 * realized / initial_notional
            if initial_notional > 0.0
            else 0.0
        ),
        "small_fired": small_fired,
        "runner_closed": False,
        "small_at_ms": small_at,
        "runner_at_ms": None,
        "first_overlay_at_ms": first_overlay_at,
    }


def normalized_static(
    row: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sim_usdt": float(result["sim_usdt"]),
        "sim_pct": float(result["sim_pct"]),
        "small_fired": False,
        "runner_closed": bool(result["triggered"]),
        "small_at_ms": None,
        "runner_at_ms": result.get("trigger_at_ms"),
        "first_overlay_at_ms": result.get("trigger_at_ms"),
    }


def group_metrics(
    rows: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pairs = [(row, results[str(row["position_id"])]) for row in rows]
    simulated_pct = [float(result["sim_pct"]) for _, result in pairs]
    retention = [
        float(result["sim_pct"])
        / float(row["observable_net_peak_pct"])
        for row, result in pairs
        if float(row["observable_net_peak_pct"]) > 0.0
    ]
    return {
        "n": len(rows),
        "total_usdt": sum(
            float(result["sim_usdt"]) for _, result in pairs
        ),
        "mean_pct": (
            statistics.mean(simulated_pct) if simulated_pct else None
        ),
        "median_pct": _median(simulated_pct),
        "win_n": sum(value > 0.0 for value in simulated_pct),
        "win_rate": (
            sum(value > 0.0 for value in simulated_pct)
            / len(simulated_pct)
            if simulated_pct else None
        ),
        "nonpositive_n": sum(value <= 0.0 for value in simulated_pct),
        "median_retention": _median(retention),
        "ret_ge80_share": (
            sum(value >= 0.80 for value in retention) / len(retention)
            if retention else None
        ),
        "small_reduce_n": sum(
            bool(result.get("small_fired")) for _, result in pairs
        ),
        "runner_close_n": sum(
            bool(result.get("runner_closed")) for _, result in pairs
        ),
    }


def metric_bundle(
    rows: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    small_medium = [
        row
        for row in rows
        if 0.30 <= float(row["observable_net_peak_pct"]) < 1.00
    ]
    runner_ge1 = [
        row
        for row in rows
        if float(row["observable_net_peak_pct"]) >= 1.00
    ]
    runner_ge2 = [
        row
        for row in rows
        if float(row["observable_net_peak_pct"]) >= 2.00
    ]
    thirds = {
        "EARLY": rows[:33],
        "MID": rows[33:66],
        "LATE": rows[66:],
    }

    return {
        "all": group_metrics(rows, results),
        "small_medium_030_100": group_metrics(
            small_medium,
            results,
        ),
        "runner_ge1": group_metrics(runner_ge1, results),
        "runner_ge2": group_metrics(runner_ge2, results),
        "thirds": {
            name: group_metrics(group, results)
            for name, group in thirds.items()
        },
        "helped_n": sum(
            float(results[str(row["position_id"])]["sim_usdt"])
            > float(row["realized_pnl_usdt"]) + 1e-12
            for row in rows
        ),
        "harmed_n": sum(
            float(results[str(row["position_id"])]["sim_usdt"])
            < float(row["realized_pnl_usdt"]) - 1e-12
            for row in rows
        ),
    }


def actual_results(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(row["position_id"]): {
            "sim_usdt": float(row["realized_pnl_usdt"]),
            "sim_pct": float(row["actual_realized_net_pct"]),
            "small_fired": False,
            "runner_closed": False,
            "small_at_ms": None,
            "runner_at_ms": None,
            "first_overlay_at_ms": None,
        }
        for row in rows
    }


def concentration(
    rows: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        result = results[str(row["position_id"])]
        records.append(
            {
                "position_id": row["position_id"],
                "symbol": row["symbol"],
                "side": row["side"],
                "third": ("EARLY", "MID", "LATE")[min(index // 33, 2)],
                "actual_usdt": float(row["realized_pnl_usdt"]),
                "sim_usdt": float(result["sim_usdt"]),
                "delta_usdt": (
                    float(result["sim_usdt"])
                    - float(row["realized_pnl_usdt"])
                ),
                "small_fired": bool(result.get("small_fired")),
                "runner_closed": bool(result.get("runner_closed")),
            }
        )

    thirds: dict[str, Any] = {}
    for third in ("EARLY", "MID", "LATE"):
        group = [record for record in records if record["third"] == third]
        thirds[third] = {
            "delta_usdt": sum(
                float(record["delta_usdt"]) for record in group
            ),
            "helped_n": sum(
                float(record["delta_usdt"]) > 1e-12 for record in group
            ),
            "harmed_n": sum(
                float(record["delta_usdt"]) < -1e-12 for record in group
            ),
        }

    changed = [
        record
        for record in records
        if abs(float(record["delta_usdt"])) > 1e-12
    ]
    positive = sorted(
        (
            float(record["delta_usdt"])
            for record in changed
            if float(record["delta_usdt"]) > 0.0
        ),
        reverse=True,
    )
    total_delta = sum(float(record["delta_usdt"]) for record in records)

    return {
        "thirds": thirds,
        "total_delta_usdt": total_delta,
        "top1_positive_contribution_share": (
            positive[0] / total_delta
            if positive and total_delta > 0.0
            else None
        ),
        "top3_positive_contribution_share": (
            sum(positive[:3]) / total_delta
            if positive and total_delta > 0.0
            else None
        ),
        "top_improvements": sorted(
            changed,
            key=lambda record: float(record["delta_usdt"]),
            reverse=True,
        )[:15],
        "top_deteriorations": sorted(
            changed,
            key=lambda record: float(record["delta_usdt"]),
        )[:15],
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
        raise RuntimeError(f"expected 99 rows, got {len(rows)}")

    ids = [str(row["position_id"]) for row in rows]
    positions, observations, orders = load_market_data(ids)

    baseline_results = actual_results(rows)
    baseline = metric_bundle(rows, baseline_results)

    references: dict[str, Any] = {}
    for name, params in (
        ("runner_static", RUNNER_REFERENCE),
        ("aggressive_static", AGGRESSIVE_REFERENCE),
    ):
        arm, retain, confirm = params
        static = {
            str(row["position_id"]): normalized_static(
                row,
                simulate_static(
                    row,
                    arm_pct=arm,
                    retain_ratio=retain,
                    confirm_samples=confirm,
                    positions=positions,
                    observations=observations,
                    orders=orders,
                ),
            )
            for row in rows
        }
        references[name] = {
            "params": {
                "arm_pct": arm,
                "retain_ratio": retain,
                "confirm_samples": confirm,
            },
            "metrics": metric_bundle(rows, static),
        }

    runner_reference = references["runner_static"]["metrics"]
    candidates: list[dict[str, Any]] = []
    result_cache: dict[
        tuple[tuple[float, float, int], float, float],
        dict[str, dict[str, Any]],
    ] = {}

    for small_template, reduce_fraction, runner_qualify in itertools.product(
        SMALL_TEMPLATES,
        REDUCE_FRACTIONS,
        RUNNER_QUALIFY_PCTS,
    ):
        results = {
            str(row["position_id"]): simulate_hybrid(
                row,
                small_template=small_template,
                reduce_fraction=reduce_fraction,
                runner_qualify_pct=runner_qualify,
                positions=positions,
                observations=observations,
                orders=orders,
            )
            for row in rows
        }
        key = (small_template, reduce_fraction, runner_qualify)
        result_cache[key] = results
        metrics = metric_bundle(rows, results)

        third_delta = {
            third: (
                float(metrics["thirds"][third]["total_usdt"])
                - float(baseline["thirds"][third]["total_usdt"])
            )
            for third in ("EARLY", "MID", "LATE")
        }

        balanced = (
            float(metrics["all"]["total_usdt"])
            > float(baseline["all"]["total_usdt"])
            and float(metrics["all"]["win_rate"])
            > float(runner_reference["all"]["win_rate"])
            and float(metrics["runner_ge1"]["median_retention"])
            >= float(
                runner_reference["runner_ge1"]["median_retention"]
            ) - 0.05
            and float(metrics["runner_ge2"]["median_retention"])
            >= float(
                runner_reference["runner_ge2"]["median_retention"]
            ) - 0.05
            and int(metrics["small_medium_030_100"]["nonpositive_n"])
            < int(
                runner_reference[
                    "small_medium_030_100"
                ]["nonpositive_n"]
            )
            and all(value > 0.0 for value in third_delta.values())
        )

        candidates.append(
            {
                "small_arm_pct": small_template[0],
                "small_retain_ratio": small_template[1],
                "small_confirm_samples": small_template[2],
                "reduce_fraction": reduce_fraction,
                "runner_qualify_pct": runner_qualify,
                "runner_retain_ratio": RUNNER_RETAIN,
                "runner_confirm_samples": RUNNER_CONFIRM,
                "metrics": metrics,
                "third_delta_usdt": third_delta,
                "minimum_third_delta_usdt": min(third_delta.values()),
                "balanced_pass": balanced,
            }
        )

    passers = [
        candidate for candidate in candidates if candidate["balanced_pass"]
    ]
    ranked = sorted(
        passers,
        key=lambda candidate: (
            float(candidate["minimum_third_delta_usdt"]),
            float(candidate["metrics"]["all"]["total_usdt"]),
            float(candidate["metrics"]["all"]["win_rate"]),
        ),
        reverse=True,
    )

    selected = ranked[0] if ranked else None
    selected_concentration: dict[str, Any] = {}
    if selected is not None:
        selected_key = (
            (
                float(selected["small_arm_pct"]),
                float(selected["small_retain_ratio"]),
                int(selected["small_confirm_samples"]),
            ),
            float(selected["reduce_fraction"]),
            float(selected["runner_qualify_pct"]),
        )
        selected_concentration = concentration(
            rows,
            result_cache[selected_key],
        )

    sweep = {
        "stage": "PP-V4-2C",
        "status": "COMPLETE_TWO_REGIME_SWEEP",
        "grid": {
            "small_templates": [list(item) for item in SMALL_TEMPLATES],
            "reduce_fractions": list(REDUCE_FRACTIONS),
            "runner_qualify_pcts": list(RUNNER_QUALIFY_PCTS),
            "runner_retain_ratio": RUNNER_RETAIN,
            "runner_confirm_samples": RUNNER_CONFIRM,
            "candidate_count": len(candidates),
        },
        "baseline": baseline,
        "references": references,
        "candidates": candidates,
        "balanced_pass_count": len(passers),
    }

    result = {
        "stage": "PP-V4-2C",
        "status": "COMPLETE_RESEARCH_ONLY",
        "candidate_count": len(candidates),
        "balanced_pass_count": len(passers),
        "baseline": baseline,
        "references": references,
        "balanced_pass_candidates": ranked,
        "selected_research_reference": selected,
        "selected_concentration": selected_concentration,
        "decision": {
            "balanced_pass_exists": bool(ranked),
            "proceed_to_v4_2d_full_replay": bool(ranked),
            "selected_runtime_policy": None,
            "runtime_change_authority": "NONE",
            "protection_authority": "NONE",
            "next_stage": (
                "V4-2D_FULL_REPLAY_PROSPECTIVE_SHADOW_SPEC"
                if ranked
                else "PROTECTION_STATE_MACHINE_REDESIGN"
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
                "balanced_pass_count": result["balanced_pass_count"],
                "selected": result["selected_research_reference"],
                "decision": result["decision"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
