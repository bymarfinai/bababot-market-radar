from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAPPING_CSV = ROOT / "research/profit_protection_v4/results/stage3d1_retention_failure_mapping.csv"
DATA_ROOT = Path(os.environ.get("CORE_DATA_DIR", "/opt/core-app/data"))
MARKET_JSON = DATA_ROOT / "pp3d2_market_data.json"
SUB5S_JSON = ROOT / "research/profit_protection_v4/results/stage1k_sub5s_phase_benchmark_evidence.json"

TARGETS = (0.80, 0.90, 0.95)

BASELINE = {
    "small_arm": 0.50,
    "small_retain": 0.60,
    "small_confirm": 3,
    "reduce_fraction": 0.25,
    "runner_qualify": 1.50,
    "runner_retain": 0.90,
    "runner_confirm": 2,
}


def f(value: Any) -> float:
    return float(value)


def gross_pnl(side: str, entry: float, exit_price: float, quantity: float) -> float:
    if side.upper() == "LONG":
        return quantity * (exit_price - entry)
    return quantity * (entry - exit_price)


def exit_fill_price(side: str, market_price: float, slippage_bps: float) -> float:
    slip = slippage_bps / 10_000.0
    if side.upper() == "LONG":
        return market_price * (1.0 - slip)
    return market_price * (1.0 + slip)


def full_close_net_pct_at_price(position: dict[str, Any], market_price: float) -> float:
    side = str(position["side"]).upper()
    entry = f(position["entry_price"])
    metadata = position["metadata"]
    initial_quantity = f(metadata.get("initial_quantity") or 0.0)
    initial_notional = f(metadata.get("initial_notional_usdt") or 500.0)
    entry_fee_total = f(metadata.get("entry_fee_total") or 0.0)
    fee_rate = f(metadata.get("fee_rate") or 0.00075)
    slippage_bps = f(metadata.get("slippage_bps") or 2.0)
    fill = exit_fill_price(side, market_price, slippage_bps)
    exit_fee = initial_quantity * fill * fee_rate
    realized = (
        gross_pnl(side, entry, fill, initial_quantity)
        - entry_fee_total
        - exit_fee
    )
    return 100.0 * realized / initial_notional if initial_notional > 0 else 0.0


def prepare_market(raw: dict[str, Any]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    positions = raw["positions"]
    observations = raw["observations"]
    orders = raw["orders"]
    for position in positions.values():
        for key in (
            "opened_at_ms",
            "closed_at_ms",
            "entry_price",
            "exit_price",
            "realized_pnl",
            "realized_pnl_pct",
        ):
            position[key] = f(position[key])
        raw_json = position.get("raw_json") or "{}"
        position["metadata"] = (
            raw_json if isinstance(raw_json, dict) else json.loads(raw_json)
        )
    for rows in observations.values():
        for item in rows:
            item["observed_at_ms"] = int(item["observed_at_ms"])
            item["current_price"] = f(item["current_price"])
            item["current_pnl_pct"] = f(item["current_pnl_pct"])
    for rows in orders.values():
        for item in rows:
            if item["executed_at_ms"] is not None:
                item["executed_at_ms"] = int(item["executed_at_ms"])
            for key in ("executed_quantity", "fill_price", "fee"):
                if item[key] is not None:
                    item[key] = f(item[key])
    return positions, observations, orders


def fallback_close_fill(
    pid: str,
    positions: dict[str, dict[str, Any]],
    orders: dict[str, list[dict[str, Any]]],
) -> tuple[float, int]:
    closes = [
        item
        for item in orders[pid]
        if str(item["action"]).upper() == "CLOSE"
        and item["executed_at_ms"] is not None
        and str(item.get("status") or "").upper() == "FILLED"
    ]
    if closes:
        final = closes[-1]
        return f(final["fill_price"]), int(final["executed_at_ms"])
    position = positions[pid]
    return f(position["exit_price"]), int(position["closed_at_ms"])


def preserve_historical_before(
    pid: str,
    at_ms: int,
    *,
    side: str,
    entry: float,
    initial_quantity: float,
    entry_fee_total: float,
    orders: dict[str, list[dict[str, Any]]],
) -> tuple[float, float, float]:
    realized = 0.0
    quantity_closed = 0.0
    entry_fee_allocated = 0.0
    for order in orders[pid]:
        if str(order["action"]).upper() == "OPEN":
            continue
        if str(order.get("status") or "").upper() != "FILLED":
            continue
        if order["executed_at_ms"] is None or int(order["executed_at_ms"]) > at_ms:
            continue
        quantity = f(order["executed_quantity"] or 0.0)
        if quantity <= 0:
            continue
        allocated = (
            entry_fee_total * quantity / initial_quantity
            if initial_quantity > 0
            else 0.0
        )
        realized += (
            gross_pnl(side, entry, f(order["fill_price"]), quantity)
            - allocated
            - f(order["fee"] or 0.0)
        )
        quantity_closed += quantity
        entry_fee_allocated += allocated
    return realized, quantity_closed, entry_fee_allocated


def simulate_hybrid(
    pid: str,
    params: dict[str, float | int],
    *,
    positions: dict[str, dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    orders: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    position = positions[pid]
    side = str(position["side"]).upper()
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    entry = f(position["entry_price"])
    metadata = position["metadata"]

    initial_quantity = f(metadata.get("initial_quantity") or 0.0)
    initial_notional = f(metadata.get("initial_notional_usdt") or 500.0)
    entry_fee_total = f(metadata.get("entry_fee_total") or 0.0)
    fee_rate = f(metadata.get("fee_rate") or 0.00075)
    slippage_bps = f(metadata.get("slippage_bps") or 2.0)

    path = [
        item
        for item in observations[pid]
        if opened <= int(item["observed_at_ms"]) <= closed
    ]

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
        at = int(item["observed_at_ms"])
        pnl = f(item["current_pnl_pct"])
        running_peak = max(running_peak, pnl)

        if not runner_mode and running_peak >= f(params["runner_qualify"]):
            runner_mode = True
            small_consecutive = 0

        if runner_mode:
            cond = pnl <= running_peak * f(params["runner_retain"])
            runner_consecutive = runner_consecutive + 1 if cond else 0
            if runner_consecutive < int(params["runner_confirm"]):
                continue

            if not diverged:
                realized, quantity_closed, entry_fee_allocated = preserve_historical_before(
                    pid,
                    at,
                    side=side,
                    entry=entry,
                    initial_quantity=initial_quantity,
                    entry_fee_total=entry_fee_total,
                    orders=orders,
                )
                diverged = True
                first_overlay_at = at

            remaining = max(0.0, initial_quantity - quantity_closed)
            fill = exit_fill_price(side, f(item["current_price"]), slippage_bps)
            exit_fee = remaining * fill * fee_rate
            remaining_entry_fee = max(0.0, entry_fee_total - entry_fee_allocated)
            realized += (
                gross_pnl(side, entry, fill, remaining)
                - remaining_entry_fee
                - exit_fee
            )
            return {
                "sim_usdt": realized,
                "sim_pct": 100.0 * realized / initial_notional if initial_notional > 0 else 0.0,
                "small_fired": small_fired,
                "runner_closed": True,
                "small_at_ms": small_at,
                "runner_at_ms": at,
                "first_overlay_at_ms": first_overlay_at,
            }

        if small_fired:
            continue

        cond = (
            running_peak >= f(params["small_arm"])
            and pnl <= running_peak * f(params["small_retain"])
        )
        small_consecutive = small_consecutive + 1 if cond else 0
        if small_consecutive < int(params["small_confirm"]):
            continue

        if not diverged:
            realized, quantity_closed, entry_fee_allocated = preserve_historical_before(
                pid,
                at,
                side=side,
                entry=entry,
                initial_quantity=initial_quantity,
                entry_fee_total=entry_fee_total,
                orders=orders,
            )
            diverged = True
            first_overlay_at = at

        remaining = max(0.0, initial_quantity - quantity_closed)
        quantity = remaining * f(params["reduce_fraction"])
        fill = exit_fill_price(side, f(item["current_price"]), slippage_bps)
        exit_fee = quantity * fill * fee_rate
        allocated_entry_fee = (
            entry_fee_total * quantity / initial_quantity
            if initial_quantity > 0
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
        small_at = at
        small_consecutive = 0

    if not diverged:
        return {
            "sim_usdt": f(position["realized_pnl"]),
            "sim_pct": f(position["realized_pnl_pct"]),
            "small_fired": False,
            "runner_closed": False,
            "small_at_ms": None,
            "runner_at_ms": None,
            "first_overlay_at_ms": None,
        }

    remaining = max(0.0, initial_quantity - quantity_closed)
    close_fill, _ = fallback_close_fill(pid, positions, orders)
    exit_fee = remaining * close_fill * fee_rate
    remaining_entry_fee = max(0.0, entry_fee_total - entry_fee_allocated)
    realized += (
        gross_pnl(side, entry, close_fill, remaining)
        - remaining_entry_fee
        - exit_fee
    )
    return {
        "sim_usdt": realized,
        "sim_pct": 100.0 * realized / initial_notional if initial_notional > 0 else 0.0,
        "small_fired": small_fired,
        "runner_closed": False,
        "small_at_ms": small_at,
        "runner_at_ms": None,
        "first_overlay_at_ms": first_overlay_at,
    }


def simulate_full_close_trailing(
    pid: str,
    *,
    arm: float,
    retain: float,
    confirm: int,
    positions: dict[str, dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    position = positions[pid]
    side = str(position["side"]).upper()
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    entry = f(position["entry_price"])
    metadata = position["metadata"]
    initial_quantity = f(metadata.get("initial_quantity") or 0.0)
    initial_notional = f(metadata.get("initial_notional_usdt") or 500.0)
    entry_fee_total = f(metadata.get("entry_fee_total") or 0.0)
    fee_rate = f(metadata.get("fee_rate") or 0.00075)
    slippage_bps = f(metadata.get("slippage_bps") or 2.0)

    path = [
        item for item in observations[pid]
        if opened <= int(item["observed_at_ms"]) <= closed
    ]
    running_peak = float("-inf")
    consecutive = 0
    trigger = None
    for item in path:
        pnl = f(item["current_pnl_pct"])
        running_peak = max(running_peak, pnl)
        condition = running_peak >= arm and pnl <= running_peak * retain
        consecutive = consecutive + 1 if condition else 0
        if consecutive >= confirm:
            trigger = item
            break

    if trigger is None:
        return {
            "sim_pct": f(position["realized_pnl_pct"]),
            "triggered": False,
            "trigger_at_ms": None,
        }

    fill = exit_fill_price(side, f(trigger["current_price"]), slippage_bps)
    exit_fee = initial_quantity * fill * fee_rate
    realized = (
        gross_pnl(side, entry, fill, initial_quantity)
        - entry_fee_total
        - exit_fee
    )
    return {
        "sim_pct": 100.0 * realized / initial_notional if initial_notional > 0 else 0.0,
        "triggered": True,
        "trigger_at_ms": int(trigger["observed_at_ms"]),
    }


def generic_full_close_ceiling(
    pid: str,
    true_mfe: float,
    *,
    positions: dict[str, dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    arms = (0.30, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00, 4.00, 5.00)
    retains = (0.995, 0.99, 0.985, 0.98, 0.97, 0.95, 0.925, 0.90, 0.875, 0.85, 0.80, 0.75, 0.70, 0.60)
    confirms = (1, 2, 3)
    best = None
    best_params = None
    for arm, retain, confirm in itertools.product(arms, retains, confirms):
        sim = simulate_full_close_trailing(
            pid,
            arm=arm,
            retain=retain,
            confirm=confirm,
            positions=positions,
            observations=observations,
        )
        retention = f(sim["sim_pct"]) / true_mfe if true_mfe > 0 else -999.0
        if best is None or retention > f(best["retention"]):
            best = {**sim, "retention": retention}
            best_params = {"arm": arm, "retain": retain, "confirm": confirm}
    assert best is not None and best_params is not None
    return best, best_params


def candidate_params(mechanism: str) -> list[dict[str, float | int]]:
    base = dict(BASELINE)
    out: list[dict[str, float | int]] = []

    if mechanism.startswith("PARTIAL_REDUCE"):
        for arm, retain, confirm, fraction in itertools.product(
            (0.30, 0.40, 0.50, 0.60, 0.75),
            (0.97, 0.95, 0.90, 0.85, 0.80, 0.70, 0.60),
            (1, 2, 3),
            (0.25, 0.50, 0.75, 1.00),
        ):
            p = dict(base)
            p.update(
                small_arm=arm,
                small_retain=retain,
                small_confirm=confirm,
                reduce_fraction=fraction,
            )
            out.append(p)
        return out

    if mechanism in {
        "PREMATURE_RUNNER_CLOSE_CONTINUATION",
        "POST_PEAK_RUNNER_GIVEBACK",
        "RUNNER_TRANSITION_OBSERVATION_MISS",
    }:
        qualifies = (
            (0.75, 1.00, 1.25, 1.50)
            if mechanism == "RUNNER_TRANSITION_OBSERVATION_MISS"
            else (1.00, 1.25, 1.50)
        )
        for qualify, retain, confirm in itertools.product(
            qualifies,
            (0.97, 0.95, 0.925, 0.90, 0.875, 0.85, 0.80, 0.75, 0.70),
            (1, 2, 3),
        ):
            p = dict(base)
            p.update(
                runner_qualify=qualify,
                runner_retain=retain,
                runner_confirm=confirm,
            )
            out.append(p)
        return out

    if mechanism == "EXECUTION_ACCOUNTING_DRAG":
        for fraction, qualify, retain, confirm in itertools.product(
            (0.00, 0.10, 0.25, 0.50),
            (1.00, 1.25, 1.50),
            (0.97, 0.95, 0.925, 0.90, 0.875, 0.85),
            (1, 2),
        ):
            p = dict(base)
            p.update(
                reduce_fraction=fraction,
                runner_qualify=qualify,
                runner_retain=retain,
                runner_confirm=confirm,
            )
            out.append(p)
        return out

    if mechanism == "PEAK_OBSERVATION_MISS":
        return []

    return [base]


def path_information(
    pid: str,
    true_mfe: float,
    observations: dict[str, list[dict[str, Any]]],
    positions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    position = positions[pid]
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    path = [
        item
        for item in observations[pid]
        if opened <= int(item["observed_at_ms"]) <= closed
    ]
    if not path:
        return {
            "observed_peak_pct": None,
            "observed_capture_ratio": None,
            "final_observed_peak_at_ms": None,
            "oracle_post_peak_ge80_window_s": None,
            "oracle_post_peak_ge90_window_s": None,
            "oracle_post_peak_ge95_window_s": None,
        }

    peak_index = max(range(len(path)), key=lambda i: f(path[i]["current_pnl_pct"]))
    peak_item = path[peak_index]
    peak = f(peak_item["current_pnl_pct"])
    peak_at = int(peak_item["observed_at_ms"])
    next_item = path[peak_index + 1] if peak_index + 1 < len(path) else None

    side = str(position["side"]).upper()
    entry = f(position["entry_price"])
    true_peak_market_price = (
        entry * (1.0 + true_mfe / 100.0)
        if side == "LONG"
        else entry * (1.0 - true_mfe / 100.0)
    )
    exact_true_peak_net_pct = full_close_net_pct_at_price(
        position,
        true_peak_market_price,
    )
    observed_peak_net_pct = full_close_net_pct_at_price(
        position,
        f(peak_item["current_price"]),
    )
    next_post_peak_net_pct = (
        full_close_net_pct_at_price(position, f(next_item["current_price"]))
        if next_item is not None
        else None
    )

    result = {
        "observed_peak_pct": peak,
        "observed_capture_ratio": peak / true_mfe if true_mfe > 0 else None,
        "final_observed_peak_at_ms": peak_at,
        "exact_true_peak_net_pct": exact_true_peak_net_pct,
        "exact_true_peak_net_retention": (
            exact_true_peak_net_pct / true_mfe if true_mfe > 0 else None
        ),
        "observed_peak_net_pct": observed_peak_net_pct,
        "observed_peak_net_retention": (
            observed_peak_net_pct / true_mfe if true_mfe > 0 else None
        ),
        "next_post_peak_at_ms": (
            int(next_item["observed_at_ms"]) if next_item is not None else None
        ),
        "next_post_peak_gap_s": (
            (int(next_item["observed_at_ms"]) - peak_at) / 1000.0
            if next_item is not None else None
        ),
        "next_post_peak_net_pct": next_post_peak_net_pct,
        "next_post_peak_net_retention": (
            next_post_peak_net_pct / true_mfe
            if next_post_peak_net_pct is not None and true_mfe > 0
            else None
        ),
    }

    for target in TARGETS:
        level = true_mfe * target
        after = path[peak_index:]
        ge = [item for item in after if f(item["current_pnl_pct"]) >= level]
        last_at = int(ge[-1]["observed_at_ms"]) if ge else None
        result[f"oracle_post_peak_ge{int(target*100)}_window_s"] = (
            (last_at - peak_at) / 1000.0 if last_at is not None else None
        )
        result[f"observed_ge{int(target*100)}"] = peak >= level
    return result


def load_sub5s() -> dict[str, dict[str, Any]]:
    rows = json.loads(SUB5S_JSON.read_text(encoding="utf-8"))
    return {str(row["position_id"]): row for row in rows}


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with MAPPING_CSV.open(encoding="utf-8") as handle:
        mapping = list(csv.DictReader(handle))
    active = [row for row in mapping if row["protection_actions"] != "NO_ACTION"]
    raw_market = json.loads(MARKET_JSON.read_text(encoding="utf-8"))
    positions, observations, orders = prepare_market(raw_market)
    sub5s = load_sub5s()

    details: list[dict[str, Any]] = []
    baseline_errors: list[float] = []

    for row in active:
        pid = str(row["position_id"])
        true_mfe = f(row["clean_mfe_pct"])
        current_retention = f(row["retention_vs_true_pct"]) / 100.0
        baseline_sim = simulate_hybrid(
            pid,
            BASELINE,
            positions=positions,
            observations=observations,
            orders=orders,
        )
        baseline_error = f(baseline_sim["sim_pct"]) - f(row["protected_pct"])
        baseline_errors.append(abs(baseline_error))

        info = path_information(pid, true_mfe, observations, positions)
        mechanism = str(row["mechanism"])
        grid = candidate_params(mechanism)
        best_result: dict[str, Any] | None = None
        best_params: dict[str, Any] | None = None
        for params in grid:
            sim = simulate_hybrid(
                pid,
                params,
                positions=positions,
                observations=observations,
                orders=orders,
            )
            retention = f(sim["sim_pct"]) / true_mfe if true_mfe > 0 else -999.0
            if best_result is None or retention > f(best_result["retention"]):
                best_result = {**sim, "retention": retention}
                best_params = dict(params)

        generic_best, generic_params = generic_full_close_ceiling(
            pid,
            true_mfe,
            positions=positions,
            observations=observations,
        )
        generic_retention = f(generic_best["retention"])

        sub = sub5s.get(pid)
        p2s80 = (
            f(sub["cadences"]["2000"]["ge80_phase_probability"])
            if sub is not None
            else None
        )
        p1s80 = (
            f(sub["cadences"]["1000"]["ge80_phase_probability"])
            if sub is not None
            else None
        )
        event_capture = (
            f(sub["event_driven_tick_capture_ratio"])
            if sub is not None
            else None
        )

        best_retention = (
            f(best_result["retention"]) if best_result is not None else None
        )
        five_s_info_ge80 = bool(info["observed_ge80"])
        bounded_family_ge80 = bool(
            best_retention is not None and best_retention >= 0.80
        )

        generic_ge80 = generic_retention >= 0.80
        cost_feasible_ge80 = f(info["exact_true_peak_net_retention"]) >= 0.80
        observed_peak_net_ge80 = f(info["observed_peak_net_retention"]) >= 0.80
        one_step_net_ge80 = (
            info["next_post_peak_net_retention"] is not None
            and f(info["next_post_peak_net_retention"]) >= 0.80
        )
        if not cost_feasible_ge80:
            engineering_lane = "COST_INFEASIBLE_80_NET_VS_GROSS_MFE"
        elif one_step_net_ge80:
            engineering_lane = "5S_ONE_STEP_POST_PEAK_EXECUTABLE"
        elif observed_peak_net_ge80:
            engineering_lane = "5S_PEAK_ONLY_NEEDS_SUB5S_OR_ANTICIPATION"
        else:
            engineering_lane = "COST_FEASIBLE_NEEDS_BETTER_OBSERVABILITY"

        if not cost_feasible_ge80:
            recoverability = "TARGET80_NET_INFEASIBLE_AT_CURRENT_COSTS"
        elif bounded_family_ge80:
            recoverability = "RECOVERABLE_WITHIN_V42_ARCHITECTURE"
        elif generic_ge80:
            recoverability = "RECOVERABLE_5S_REQUIRES_ARCHITECTURE_CHANGE"
        elif not five_s_info_ge80 and sub is not None and event_capture is not None and event_capture >= 0.80:
            recoverability = "COST_FEASIBLE_BUT_INFORMATION_BOUND_EVENT_DRIVEN"
        elif five_s_info_ge80:
            recoverability = "COST_FEASIBLE_OBSERVABLE_5S_BUT_NOT_CAUSALLY_GE80_IN_TESTED_FAMILY"
        else:
            recoverability = "COST_FEASIBLE_NOT_RECOVERABLE_WITH_AVAILABLE_5S_INFORMATION"

        detail = {
            "position_id": pid,
            "symbol": row["symbol"],
            "side": row["side"],
            "mechanism": mechanism,
            "protection_actions": row["protection_actions"],
            "clean_mfe_pct": true_mfe,
            "current_protected_pct": f(row["protected_pct"]),
            "current_retention_pct": current_retention * 100.0,
            "baseline_replay_pct": f(baseline_sim["sim_pct"]),
            "baseline_replay_error_pp": baseline_error,
            "observed_peak_pct": info["observed_peak_pct"],
            "observed_capture_of_true_pct": (
                f(info["observed_capture_ratio"]) * 100.0
                if info["observed_capture_ratio"] is not None
                else None
            ),
            "exact_true_peak_net_retention_pct": (
                f(info["exact_true_peak_net_retention"]) * 100.0
            ),
            "cost_feasible_ge80": cost_feasible_ge80,
            "observed_peak_net_retention_pct": (
                f(info["observed_peak_net_retention"]) * 100.0
            ),
            "observed_peak_net_ge80": observed_peak_net_ge80,
            "next_post_peak_gap_s": info["next_post_peak_gap_s"],
            "next_post_peak_net_retention_pct": (
                f(info["next_post_peak_net_retention"]) * 100.0
                if info["next_post_peak_net_retention"] is not None
                else None
            ),
            "one_step_post_peak_net_ge80": one_step_net_ge80,
            "engineering_lane": engineering_lane,
            "five_s_information_ge80": five_s_info_ge80,
            "oracle_post_peak_ge80_window_s": info["oracle_post_peak_ge80_window_s"],
            "oracle_post_peak_ge90_window_s": info["oracle_post_peak_ge90_window_s"],
            "oracle_post_peak_ge95_window_s": info["oracle_post_peak_ge95_window_s"],
            "bounded_family_candidate_n": len(grid),
            "bounded_family_best_pct": (
                f(best_result["sim_pct"]) if best_result is not None else None
            ),
            "bounded_family_best_retention_pct": (
                best_retention * 100.0 if best_retention is not None else None
            ),
            "bounded_family_ge80": bounded_family_ge80,
            "bounded_family_ge90": bool(
                best_retention is not None and best_retention >= 0.90
            ),
            "bounded_family_ge95": bool(
                best_retention is not None and best_retention >= 0.95
            ),
            "best_params_json": (
                json.dumps(best_params, sort_keys=True, separators=(",", ":"))
                if best_params is not None
                else ""
            ),
            "generic_full_close_best_pct": f(generic_best["sim_pct"]),
            "generic_full_close_best_retention_pct": generic_retention * 100.0,
            "generic_full_close_ge80": generic_ge80,
            "generic_full_close_ge90": generic_retention >= 0.90,
            "generic_full_close_ge95": generic_retention >= 0.95,
            "generic_full_close_best_params_json": json.dumps(
                generic_params, sort_keys=True, separators=(",", ":")
            ),
            "sub5s_evidence": sub is not None,
            "two_s_phase_probability_ge80": p2s80,
            "one_s_phase_probability_ge80": p1s80,
            "event_driven_tick_capture_pct": (
                event_capture * 100.0 if event_capture is not None else None
            ),
            "recoverability_class": recoverability,
        }
        details.append(detail)

    if max(baseline_errors, default=0.0) > 1e-9:
        raise RuntimeError(
            f"baseline replay mismatch max_abs_pp={max(baseline_errors)}"
        )

    mechanism_stats: dict[str, Any] = {}
    for mechanism in sorted({str(row["mechanism"]) for row in details}):
        group = [row for row in details if row["mechanism"] == mechanism]
        best = [
            f(row["bounded_family_best_retention_pct"])
            for row in group
            if row["bounded_family_best_retention_pct"] is not None
        ]
        generic_best = [
            f(row["generic_full_close_best_retention_pct"])
            for row in group
        ]
        windows = [
            f(row["oracle_post_peak_ge80_window_s"])
            for row in group
            if row["oracle_post_peak_ge80_window_s"] is not None
        ]
        mechanism_stats[mechanism] = {
            "n": len(group),
            "five_s_information_ge80_n": sum(
                bool(row["five_s_information_ge80"]) for row in group
            ),
            "cost_feasible_ge80_n": sum(
                bool(row["cost_feasible_ge80"]) for row in group
            ),
            "observed_peak_net_ge80_n": sum(
                bool(row["observed_peak_net_ge80"]) for row in group
            ),
            "one_step_post_peak_net_ge80_n": sum(
                bool(row["one_step_post_peak_net_ge80"]) for row in group
            ),
            "bounded_family_ge80_n": sum(
                bool(row["bounded_family_ge80"]) for row in group
            ),
            "bounded_family_ge90_n": sum(
                bool(row["bounded_family_ge90"]) for row in group
            ),
            "bounded_family_ge95_n": sum(
                bool(row["bounded_family_ge95"]) for row in group
            ),
            "generic_full_close_ge80_n": sum(
                bool(row["generic_full_close_ge80"]) for row in group
            ),
            "generic_full_close_ge90_n": sum(
                bool(row["generic_full_close_ge90"]) for row in group
            ),
            "generic_full_close_ge95_n": sum(
                bool(row["generic_full_close_ge95"]) for row in group
            ),
            "median_best_retention_pct": median(best),
            "median_generic_full_close_best_retention_pct": median(generic_best),
            "median_oracle_post_peak_ge80_window_s": median(windows),
        }

    windows80 = [
        f(row["oracle_post_peak_ge80_window_s"])
        for row in details
        if row["oracle_post_peak_ge80_window_s"] is not None
    ]

    sub_rows = [row for row in details if row["sub5s_evidence"]]
    sub_cost_feasible = [
        row for row in sub_rows if bool(row["cost_feasible_ge80"])
    ]
    summary = {
        "stage": "PP-V4-3D2",
        "status": "COMPLETE_RESEARCH_ONLY",
        "baseline_name": "Profit Protector V4.2 - Hybrid Protection",
        "active_failure_n": len(details),
        "baseline_replay_validation": {
            "matched_n": len(details),
            "max_abs_error_pp": max(baseline_errors, default=0.0),
            "exact_within_1e_9": max(baseline_errors, default=0.0) <= 1e-9,
        },
        "cost_adjusted_true_peak_ceiling": {
            "ge80_n": sum(bool(row["cost_feasible_ge80"]) for row in details),
            "lt80_n": sum(not bool(row["cost_feasible_ge80"]) for row in details),
            "ge80_share_pct": 100.0 * sum(
                bool(row["cost_feasible_ge80"]) for row in details
            ) / len(details),
            "median_exact_true_peak_net_retention_pct": median([
                f(row["exact_true_peak_net_retention_pct"]) for row in details
            ]),
            "note": (
                "Maximum net retention if the entire position could exit exactly at the clean true peak, "
                "using current fee and slippage assumptions. LT80 here is mathematically incompatible "
                "with an 80% net-vs-gross-MFE target even under perfect timing."
            ),
        },
        "five_s_execution_ceiling": {
            "observed_peak_net_ge80_n": sum(
                bool(row["observed_peak_net_ge80"]) for row in details
            ),
            "one_step_post_peak_net_ge80_n": sum(
                bool(row["one_step_post_peak_net_ge80"]) for row in details
            ),
            "one_step_post_peak_net_ge75_n": sum(
                row["next_post_peak_net_retention_pct"] is not None
                and f(row["next_post_peak_net_retention_pct"]) >= 75.0
                for row in details
            ),
            "median_next_post_peak_gap_s": median([
                f(row["next_post_peak_gap_s"]) for row in details
                if row["next_post_peak_gap_s"] is not None
            ]),
            "note": (
                "Observed-peak exit is a non-causal oracle upper bound. One-step post-peak assumes a perfect "
                "reversal classifier that can act at the first 5s observation after the final observed peak."
            ),
        },
        "five_s_information_ceiling": {
            "ge80_n": sum(bool(row["five_s_information_ge80"]) for row in details),
            "ge80_share_pct": 100.0 * sum(
                bool(row["five_s_information_ge80"]) for row in details
            ) / len(details),
            "oracle_post_peak_ge80_window_s_median": median(windows80),
            "oracle_post_peak_ge80_window_ge5s_n": sum(v >= 5.0 for v in windows80),
            "oracle_post_peak_ge80_window_ge10s_n": sum(v >= 10.0 for v in windows80),
            "oracle_post_peak_ge80_window_ge20s_n": sum(v >= 20.0 for v in windows80),
            "note": (
                "These windows are ex-post information ceilings relative to true MFE; "
                "they are not causal production triggers."
            ),
        },
        "bounded_causal_hybrid_family_ceiling": {
            "ge80_n": sum(bool(row["bounded_family_ge80"]) for row in details),
            "ge90_n": sum(bool(row["bounded_family_ge90"]) for row in details),
            "ge95_n": sum(bool(row["bounded_family_ge95"]) for row in details),
            "ge80_share_pct": 100.0 * sum(
                bool(row["bounded_family_ge80"]) for row in details
            ) / len(details),
            "selection_note": (
                "Per-trade oracle selection over a pre-bounded V4.2-style causal parameter family. "
                "This is a recoverability ceiling, not a globally valid rule."
            ),
        },
        "generic_5s_full_close_causal_ceiling": {
            "ge80_n": sum(bool(row["generic_full_close_ge80"]) for row in details),
            "ge90_n": sum(bool(row["generic_full_close_ge90"]) for row in details),
            "ge95_n": sum(bool(row["generic_full_close_ge95"]) for row in details),
            "ge80_share_pct": 100.0 * sum(
                bool(row["generic_full_close_ge80"]) for row in details
            ) / len(details),
            "selection_note": (
                "Per-trade oracle selection over a broad but causal 5s full-close trailing family. "
                "This measures whether the information path can support >=80% if the V4.2 hybrid architecture is changed."
            ),
        },
        "sub5s_information_bound_subset": {
            "n": len(sub_rows),
            "two_s_expected_ge80_rescues": sum(
                f(row["two_s_phase_probability_ge80"]) for row in sub_rows
                if row["two_s_phase_probability_ge80"] is not None
            ),
            "one_s_expected_ge80_rescues": sum(
                f(row["one_s_phase_probability_ge80"]) for row in sub_rows
                if row["one_s_phase_probability_ge80"] is not None
            ),
            "two_s_certain_ge80_n": sum(
                row["two_s_phase_probability_ge80"] is not None
                and f(row["two_s_phase_probability_ge80"]) >= 0.999999
                for row in sub_rows
            ),
            "one_s_certain_ge80_n": sum(
                row["one_s_phase_probability_ge80"] is not None
                and f(row["one_s_phase_probability_ge80"]) >= 0.999999
                for row in sub_rows
            ),
            "event_driven_information_ge80_n": sum(
                row["event_driven_tick_capture_pct"] is not None
                and f(row["event_driven_tick_capture_pct"]) >= 80.0
                for row in sub_rows
            ),
            "cost_feasible_subset_n": len(sub_cost_feasible),
            "cost_feasible_two_s_expected_ge80_rescues": sum(
                f(row["two_s_phase_probability_ge80"]) for row in sub_cost_feasible
                if row["two_s_phase_probability_ge80"] is not None
            ),
            "cost_feasible_one_s_expected_ge80_rescues": sum(
                f(row["one_s_phase_probability_ge80"]) for row in sub_cost_feasible
                if row["one_s_phase_probability_ge80"] is not None
            ),
            "cost_feasible_event_driven_information_ge80_n": sum(
                row["event_driven_tick_capture_pct"] is not None
                and f(row["event_driven_tick_capture_pct"]) >= 80.0
                for row in sub_cost_feasible
            ),
            "event_driven_execution_claim": False,
        },
        "recoverability_classes": dict(
            Counter(str(row["recoverability_class"]) for row in details)
        ),
        "engineering_lanes": dict(
            Counter(str(row["engineering_lane"]) for row in details)
        ),
        "mechanism_stats": mechanism_stats,
        "hard_cases": sorted(
            [
                row for row in details
                if not bool(row["generic_full_close_ge80"])
            ],
            key=lambda row: f(row["generic_full_close_best_retention_pct"]),
        ),
        "decision": {
            "proceed_to_v4_3d3_mechanism_specific_fix": True,
            "runtime_change_authority": "NONE",
            "do_not_globalize_per_trade_best_params": True,
            "priority": (
                "Engineer only mechanisms with demonstrated >=80% recoverability, "
                "while handling the information-bound subset separately."
            ),
        },
    }
    return details, summary


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-output", required=True)
    parser.add_argument("--json-output", required=True)
    args = parser.parse_args()
    rows, summary = build()
    write_csv(args.csv_output, rows)
    Path(args.json_output).write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
