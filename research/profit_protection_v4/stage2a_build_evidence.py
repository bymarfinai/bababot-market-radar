from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_radar.persistence import _postgres_connect


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE1J = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1j_clean_post_entry_mfe_evidence.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage2a_observable_realized_leakage_evidence.json"
)


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
    slip = float(slippage_bps) / 10_000.0
    if side.upper() == "LONG":
        return market_price * (1.0 - slip)
    return market_price * (1.0 + slip)


def load_db(
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
                    position_id, symbol, side, opened_at_ms, closed_at_ms,
                    entry_price, exit_price, realized_pnl, realized_pnl_pct,
                    close_reason, raw_json
                from positions
                where position_id=any(%s)
                """,
                (position_ids,),
            )
            columns = [item[0] for item in cur.description]
            positions = {
                row[0]: dict(zip(columns, row))
                for row in cur.fetchall()
            }

            cur.execute(
                """
                select
                    position_id, observed_at_ms, current_price,
                    current_pnl_pct, running_peak_pct, running_peak_at_ms,
                    giveback_ratio, seconds_since_peak, sample_gap_ms,
                    armed, position_status
                from pp_v3_fast_peak_observations
                where position_id=any(%s)
                order by position_id, observed_at_ms
                """,
                (position_ids,),
            )
            columns = [item[0] for item in cur.description]
            observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in cur.fetchall():
                observations[row[0]].append(dict(zip(columns, row)))

            cur.execute(
                """
                select
                    position_id, action, status, executed_at_ms,
                    executed_quantity, market_price, fill_price, fee, reason
                from paper_orders
                where position_id=any(%s)
                  and status='FILLED'
                order by position_id, executed_at_ms
                """,
                (position_ids,),
            )
            columns = [item[0] for item in cur.description]
            orders: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in cur.fetchall():
                orders[row[0]].append(dict(zip(columns, row)))

    return positions, observations, orders


def threshold_hit(
    observations: list[dict[str, Any]],
    start_index: int,
    predicate: Any,
    peak_at_ms: int,
    closed_at_ms: int,
) -> dict[str, Any] | None:
    for observation in observations[start_index + 1 :]:
        if predicate(float(observation["current_pnl_pct"])):
            observed_at_ms = int(observation["observed_at_ms"])
            return {
                "at_ms": observed_at_ms,
                "seconds_from_peak": (observed_at_ms - peak_at_ms) / 1000.0,
                "seconds_to_close": (closed_at_ms - observed_at_ms) / 1000.0,
                "pnl_pct": float(observation["current_pnl_pct"]),
            }
    return None


def build_evidence(
    stage1j_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cohort = [
        dict(row)
        for row in stage1j_rows
        if float(row["clean_post_entry_mfe_pct"]) >= 0.30
    ]
    ids = [str(row["position_id"]) for row in cohort]
    positions, observations, orders = load_db(ids)

    output: list[dict[str, Any]] = []
    for source in cohort:
        position_id = str(source["position_id"])
        position = positions[position_id]
        side = str(position["side"]).upper()
        opened_at_ms = int(position["opened_at_ms"])
        closed_at_ms = int(position["closed_at_ms"])
        entry_price = float(position["entry_price"])
        realized_pct = float(position["realized_pnl_pct"])

        metadata = json.loads(position.get("raw_json") or "{}")
        initial_quantity = float(metadata.get("initial_quantity") or 0.0)
        initial_notional = float(
            metadata.get("initial_notional_usdt") or 500.0
        )
        entry_fee_total = float(metadata.get("entry_fee_total") or 0.0)
        fee_rate = float(metadata.get("fee_rate") or 0.00075)
        slippage_bps = float(metadata.get("slippage_bps") or 2.0)

        path = [
            row
            for row in observations[position_id]
            if opened_at_ms
            <= int(row["observed_at_ms"])
            <= closed_at_ms
        ]
        if not path:
            raise RuntimeError(f"missing 5s path: {position_id}")

        observable_peak = max(float(row["current_pnl_pct"]) for row in path)
        peak_index = next(
            index
            for index, row in enumerate(path)
            if abs(float(row["current_pnl_pct"]) - observable_peak) <= 1e-12
        )
        peak = path[peak_index]
        peak_at_ms = int(peak["observed_at_ms"])
        peak_market_price = float(peak["current_price"])

        realized_before_peak = 0.0
        quantity_closed_before_peak = 0.0
        entry_fee_allocated_before_peak = 0.0
        reductions_before_peak = 0

        for order in orders[position_id]:
            if str(order["action"]).upper() == "OPEN":
                continue
            if order["executed_at_ms"] is None:
                continue
            if int(order["executed_at_ms"]) > peak_at_ms:
                continue
            quantity = float(order["executed_quantity"] or 0.0)
            if quantity <= 0.0:
                continue

            allocated_entry_fee = (
                entry_fee_total * (quantity / initial_quantity)
                if initial_quantity > 0.0
                else 0.0
            )
            realized_before_peak += (
                gross_pnl(
                    side,
                    entry_price,
                    float(order["fill_price"]),
                    quantity,
                )
                - allocated_entry_fee
                - float(order["fee"] or 0.0)
            )
            quantity_closed_before_peak += quantity
            entry_fee_allocated_before_peak += allocated_entry_fee
            if str(order["action"]).upper() == "REDUCE":
                reductions_before_peak += 1

        remaining_quantity = max(
            0.0,
            initial_quantity - quantity_closed_before_peak,
        )
        peak_fill = exit_fill_price(
            side,
            peak_market_price,
            slippage_bps,
        )
        peak_exit_fee = remaining_quantity * peak_fill * fee_rate
        remaining_entry_fee = max(
            0.0,
            entry_fee_total - entry_fee_allocated_before_peak,
        )
        remaining_peak_net = (
            gross_pnl(
                side,
                entry_price,
                peak_fill,
                remaining_quantity,
            )
            - remaining_entry_fee
            - peak_exit_fee
        )
        observable_net_peak_pct = (
            100.0
            * (realized_before_peak + remaining_peak_net)
            / initial_notional
            if initial_notional > 0.0
            else 0.0
        )
        retention = (
            realized_pct / observable_net_peak_pct
            if observable_net_peak_pct > 0.0
            else None
        )

        thresholds: dict[str, Any] = {}
        if observable_peak > 0.0:
            for ratio, key in (
                (0.90, "r90"),
                (0.80, "r80"),
                (0.70, "r70"),
                (0.50, "r50"),
            ):
                thresholds[key] = threshold_hit(
                    path,
                    peak_index,
                    lambda pnl, limit=observable_peak * ratio: pnl <= limit,
                    peak_at_ms,
                    closed_at_ms,
                )
            thresholds["breakeven"] = threshold_hit(
                path,
                peak_index,
                lambda pnl: pnl <= 0.0,
                peak_at_ms,
                closed_at_ms,
            )

        last = path[-1]
        clean_mfe = float(source["clean_post_entry_mfe_pct"])
        output.append(
            {
                "position_id": position_id,
                "symbol": position["symbol"],
                "side": side,
                "opened_at_ms": opened_at_ms,
                "closed_at_ms": closed_at_ms,
                "close_reason": position["close_reason"],
                "clean_mfe_pct": clean_mfe,
                "observable_gross_peak_pct": observable_peak,
                "observable_peak_at_ms": peak_at_ms,
                "observable_peak_market_price": peak_market_price,
                "observable_net_peak_pct": observable_net_peak_pct,
                "actual_realized_net_pct": realized_pct,
                "net_leakage_pp": observable_net_peak_pct - realized_pct,
                "net_retention_ratio": retention,
                "raw_gross_peak_to_realized_leakage_pp": (
                    observable_peak - realized_pct
                ),
                "positive_observability_gap_pp": max(
                    0.0,
                    clean_mfe - observable_peak,
                ),
                "peak_age_seconds": (
                    peak_at_ms - opened_at_ms
                ) / 1000.0,
                "peak_to_close_seconds": (
                    closed_at_ms - peak_at_ms
                ) / 1000.0,
                "last_5s_pnl_pct": float(last["current_pnl_pct"]),
                "last_5s_gap_to_close_seconds": (
                    closed_at_ms - int(last["observed_at_ms"])
                ) / 1000.0,
                "peak_position_status": peak["position_status"],
                "reductions_before_peak": reductions_before_peak,
                "quantity_closed_before_peak": quantity_closed_before_peak,
                "remaining_quantity_at_peak": remaining_quantity,
                "initial_notional_usdt": initial_notional,
                "realized_pnl_usdt": float(
                    position.get("realized_pnl") or 0.0
                ),
                "observable_net_peak_usdt": (
                    initial_notional * observable_net_peak_pct / 100.0
                ),
                "thresholds": thresholds,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1j", default=str(DEFAULT_STAGE1J))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    rows = json.loads(Path(args.stage1j).read_text(encoding="utf-8"))
    evidence = build_evidence(rows)
    Path(args.output).write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(evidence), "output": args.output}))


if __name__ == "__main__":
    main()
