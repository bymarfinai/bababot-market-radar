from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.persistence import _postgres_connect


RD0_VERSION = "rd0-exact-pnl-reconciliation-v1"
EXPECTED_LONG_UNIVERSE = 1236
EXPECTED_WRONG_DIRECTION = 555
DEFAULT_NOTIONAL_USDT = 500.0
BINANCE_REGULAR_TAKER_FEE = 0.0005
BINANCE_BNB_TAKER_FEE = 0.00045
DEFAULT_SLIPPAGE_BPS = 2.0


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        obj = json.loads(value or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _opposite(side: str) -> str:
    side = str(side).upper()
    if side == "LONG":
        return "SHORT"
    if side == "SHORT":
        return "LONG"
    raise ValueError(f"unsupported side={side!r}")


def _entry_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 + slip if side == "LONG" else 1.0 - slip)


def _exit_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 - slip if side == "LONG" else 1.0 + slip)


def _market_from_entry_fill(side: str, fill: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    denom = 1.0 + slip if side == "LONG" else 1.0 - slip
    return fill / denom


def _market_from_exit_fill(side: str, fill: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    denom = 1.0 - slip if side == "LONG" else 1.0 + slip
    return fill / denom


def _gross(side: str, quantity: float, entry: float, exit_price: float) -> float:
    if side == "LONG":
        return quantity * (exit_price - entry)
    return quantity * (entry - exit_price)


def _load_universe(data_dir: Path) -> list[dict[str, str]]:
    path = data_dir / "wd5h4a_temporal_features.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing frozen temporal universe: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [
            r for r in csv.DictReader(fh)
            if str(r.get("side") or "").upper() == "LONG"
            and str(r.get("primary_meta_label") or "") in {"META_WIN", "META_LOSS"}
        ]
    rows.sort(key=lambda r: (int(r["opened_at_ms"]), r["position_id"]))
    if len(rows) != EXPECTED_LONG_UNIVERSE:
        raise RuntimeError(
            f"RD-0 requires frozen LONG universe={EXPECTED_LONG_UNIVERSE}, got {len(rows)}"
        )
    if len({r["position_id"] for r in rows}) != len(rows):
        raise RuntimeError("duplicate position_id in frozen LONG universe")
    return rows


def _load_positions(position_ids: list[str]) -> dict[str, dict[str, Any]]:
    query = """
        select
            p.position_id, p.signal_id, p.symbol, p.side,
            p.opened_at_ms, p.closed_at_ms,
            p.entry_price, p.exit_price,
            p.realized_pnl, p.realized_pnl_pct,
            p.raw_json,
            w.outcome_label
        from positions p
        left join wd1_trade_labels w on w.position_id=p.position_id
        where p.position_id = any(%s)
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (position_ids,))
            rows = [dict(r) for r in cur.fetchall()]
    out = {str(r["position_id"]): r for r in rows}
    missing = [pid for pid in position_ids if pid not in out]
    if missing:
        raise RuntimeError(
            f"positions coverage {len(out)}/{len(position_ids)}; "
            f"sample missing={missing[:5]}"
        )
    return out


def _load_orders(position_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    query = """
        select
            position_id, action, status, executed_at_ms,
            executed_quantity, market_price, fill_price, fee
        from paper_orders
        where position_id = any(%s)
          and status='FILLED'
        order by position_id, executed_at_ms
    """
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (position_ids,))
            for row in cur.fetchall():
                out[str(row["position_id"])].append(dict(row))
    return out


def _exit_legs(
    position: dict[str, Any],
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, float]], bool]:
    """Return historical REDUCE/CLOSE legs with market and fill prices."""
    side = str(position["side"]).upper()
    raw = _j(position.get("raw_json"))
    slip = _f(raw.get("slippage_bps"), DEFAULT_SLIPPAGE_BPS)
    legs: list[dict[str, float]] = []
    reconstructed_market = False
    for order in orders:
        action = str(order.get("action") or "").upper()
        if action not in {"REDUCE", "CLOSE"}:
            continue
        qty = _f(order.get("executed_quantity"))
        fill = _f(order.get("fill_price"))
        if qty <= 0 or fill <= 0:
            continue
        market_raw = order.get("market_price")
        if market_raw is None or _f(market_raw) <= 0:
            market = _market_from_exit_fill(side, fill, slip)
            reconstructed_market = True
        else:
            market = _f(market_raw)
        legs.append({
            "quantity": qty,
            "market_price": market,
            "fill_price": fill,
            "fee": max(0.0, _f(order.get("fee"))),
        })

    if not legs:
        initial_qty = _f(raw.get("initial_quantity"))
        fill = _f(position.get("exit_price"))
        if initial_qty > 0 and fill > 0:
            market_raw = raw.get("last_exit_market_price")
            if market_raw is None or _f(market_raw) <= 0:
                market = _market_from_exit_fill(side, fill, slip)
                reconstructed_market = True
            else:
                market = _f(market_raw)
            legs.append({
                "quantity": initial_qty,
                "market_price": market,
                "fill_price": fill,
                "fee": 0.0,
            })
    return legs, reconstructed_market


def _scenario_same_qty(
    *,
    side: str,
    quantity: float,
    entry_market: float,
    exit_legs: list[dict[str, float]],
    fee_rate: float,
    slippage_bps: float,
) -> tuple[float, float, float]:
    entry = _entry_fill(side, entry_market, slippage_bps)
    entry_fee = quantity * entry * fee_rate
    gross = 0.0
    exit_fee = 0.0
    for leg in exit_legs:
        q = leg["quantity"]
        exit_fill = _exit_fill(side, leg["market_price"], slippage_bps)
        gross += _gross(side, q, entry, exit_fill)
        exit_fee += q * exit_fill * fee_rate
    return gross - entry_fee - exit_fee, gross, entry_fee + exit_fee


def _scenario_fixed_notional(
    *,
    side: str,
    historical_quantity: float,
    entry_market: float,
    exit_legs: list[dict[str, float]],
    notional: float,
    fee_rate: float,
    slippage_bps: float,
) -> tuple[float, float, float]:
    entry = _entry_fill(side, entry_market, slippage_bps)
    if entry <= 0 or historical_quantity <= 0:
        return float("nan"), float("nan"), float("nan")
    quantity = notional / entry
    entry_fee = quantity * entry * fee_rate
    gross = 0.0
    exit_fee = 0.0
    exited_fraction = 0.0
    for leg in exit_legs:
        fraction = max(0.0, leg["quantity"] / historical_quantity)
        mirror_q = quantity * fraction
        exited_fraction += fraction
        exit_fill = _exit_fill(side, leg["market_price"], slippage_bps)
        gross += _gross(side, mirror_q, entry, exit_fill)
        exit_fee += mirror_q * exit_fill * fee_rate
    if abs(exited_fraction - 1.0) > 0.02:
        return float("nan"), float("nan"), float("nan")
    return gross - entry_fee - exit_fee, gross, entry_fee + exit_fee


def _reconcile_trade(
    position: dict[str, Any],
    orders: list[dict[str, Any]],
) -> dict[str, Any]:
    side = str(position["side"]).upper()
    opposite = _opposite(side)
    raw = _j(position.get("raw_json"))

    hist_qty = _f(raw.get("initial_quantity"))
    hist_entry_fill = _f(position.get("entry_price"))
    hist_entry_fee = max(0.0, _f(raw.get("entry_fee_total")))
    stored_slip = _f(raw.get("slippage_bps"), DEFAULT_SLIPPAGE_BPS)
    entry_market_raw = raw.get("entry_market_price")
    entry_market_reconstructed = (
        entry_market_raw is None or _f(entry_market_raw) <= 0
    )
    entry_market = (
        _market_from_entry_fill(side, hist_entry_fill, stored_slip)
        if entry_market_reconstructed
        else _f(entry_market_raw)
    )

    legs, exit_market_reconstructed = _exit_legs(position, orders)
    if hist_qty <= 0 or hist_entry_fill <= 0 or entry_market <= 0 or not legs:
        raise RuntimeError(
            f"incomplete execution data for {position['position_id']}"
        )

    hist_gross_fill = sum(
        _gross(side, leg["quantity"], hist_entry_fill, leg["fill_price"])
        for leg in legs
    )
    hist_exit_fee = sum(leg["fee"] for leg in legs)
    historical_replay_net = hist_gross_fill - hist_entry_fee - hist_exit_fee
    historical_db_net = _f(position.get("realized_pnl"))
    replay_error = historical_replay_net - historical_db_net

    original_raw = sum(
        _gross(side, leg["quantity"], entry_market, leg["market_price"])
        for leg in legs
    )
    mirror_raw = sum(
        _gross(opposite, leg["quantity"], entry_market, leg["market_price"])
        for leg in legs
    )
    raw_symmetry_error = original_raw + mirror_raw

    mirror_fee_only, mirror_fee_only_gross, mirror_fee_only_fees = (
        _scenario_same_qty(
            side=opposite,
            quantity=hist_qty,
            entry_market=entry_market,
            exit_legs=legs,
            fee_rate=BINANCE_REGULAR_TAKER_FEE,
            slippage_bps=0.0,
        )
    )
    mirror_taker_2bps, mirror_taker_2bps_gross, mirror_taker_2bps_fees = (
        _scenario_same_qty(
            side=opposite,
            quantity=hist_qty,
            entry_market=entry_market,
            exit_legs=legs,
            fee_rate=BINANCE_REGULAR_TAKER_FEE,
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    )
    mirror_bnb_2bps, _, _ = _scenario_same_qty(
        side=opposite,
        quantity=hist_qty,
        entry_market=entry_market,
        exit_legs=legs,
        fee_rate=BINANCE_BNB_TAKER_FEE,
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
    )
    mirror_500_taker_2bps, mirror_500_gross, mirror_500_fees = (
        _scenario_fixed_notional(
            side=opposite,
            historical_quantity=hist_qty,
            entry_market=entry_market,
            exit_legs=legs,
            notional=DEFAULT_NOTIONAL_USDT,
            fee_rate=BINANCE_REGULAR_TAKER_FEE,
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    )

    return {
        "position_id": str(position["position_id"]),
        "symbol": str(position["symbol"]),
        "side": side,
        "outcome_label": str(position.get("outcome_label") or "UNKNOWN"),
        "opened_at_ms": int(position["opened_at_ms"]),
        "closed_at_ms": int(position["closed_at_ms"]),
        "historical_db_net": historical_db_net,
        "historical_replay_net": historical_replay_net,
        "historical_replay_error": replay_error,
        "original_raw_same_market": original_raw,
        "mirror_raw_same_market": mirror_raw,
        "raw_symmetry_error": raw_symmetry_error,
        "mirror_taker_fee_only_same_qty": mirror_fee_only,
        "mirror_taker_fee_only_gross": mirror_fee_only_gross,
        "mirror_taker_fee_only_fees": mirror_fee_only_fees,
        "mirror_taker_2bps_same_qty": mirror_taker_2bps,
        "mirror_taker_2bps_gross": mirror_taker_2bps_gross,
        "mirror_taker_2bps_fees": mirror_taker_2bps_fees,
        "mirror_bnb_2bps_same_qty": mirror_bnb_2bps,
        "mirror_500_taker_2bps": mirror_500_taker_2bps,
        "mirror_500_taker_2bps_gross": mirror_500_gross,
        "mirror_500_taker_2bps_fees": mirror_500_fees,
        "initial_quantity": hist_qty,
        "exit_leg_n": len(legs),
        "entry_market_reconstructed": entry_market_reconstructed,
        "exit_market_reconstructed": exit_market_reconstructed,
    }


def _metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    vals = [float(r[key]) for r in rows if math.isfinite(float(r[key]))]
    wins = sum(v > 0 for v in vals)
    losses = sum(v < 0 for v in vals)
    return {
        "n": len(vals),
        "net_pnl": sum(vals),
        "avg_pnl": sum(vals) / len(vals) if vals else None,
        "win_n": wins,
        "loss_n": losses,
        "flat_n": len(vals) - wins - losses,
        "win_rate_pct": 100.0 * wins / len(vals) if vals else None,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scenarios = [
        "historical_db_net",
        "historical_replay_net",
        "original_raw_same_market",
        "mirror_raw_same_market",
        "mirror_taker_fee_only_same_qty",
        "mirror_taker_2bps_same_qty",
        "mirror_bnb_2bps_same_qty",
        "mirror_500_taker_2bps",
    ]
    scenario_metrics = {k: _metrics(rows, k) for k in scenarios}
    by_label: dict[str, Any] = {}
    for label in sorted({str(r["outcome_label"]) for r in rows}):
        subset = [r for r in rows if str(r["outcome_label"]) == label]
        by_label[label] = {
            "n": len(subset),
            **{k: _metrics(subset, k) for k in scenarios},
        }

    historical = scenario_metrics["historical_db_net"]["net_pnl"]
    raw_mirror = scenario_metrics["mirror_raw_same_market"]["net_pnl"]
    fee_only = scenario_metrics["mirror_taker_fee_only_same_qty"]["net_pnl"]
    taker_2bps = scenario_metrics["mirror_taker_2bps_same_qty"]["net_pnl"]

    return {
        "stage": "RD-0",
        "version": RD0_VERSION,
        "status": "RESEARCH_ONLY_NO_PRODUCTION_AUTHORITY",
        "contract": {
            "universe": (
                "frozen 1,236 resolved LONG trades from "
                "wd5h4a_temporal_features.csv"
            ),
            "direction_control": (
                "same entry market and same historical REDUCE/CLOSE market "
                "endpoints; same quantities"
            ),
            "raw_control": (
                "zero fees, zero slippage; mirror must be exact negative of "
                "original raw PnL"
            ),
            "binance_regular_taker_fee_per_side": BINANCE_REGULAR_TAKER_FEE,
            "binance_bnb_taker_fee_per_side": BINANCE_BNB_TAKER_FEE,
            "slippage_bps_per_side": DEFAULT_SLIPPAGE_BPS,
            "fixed_notional_usdt": DEFAULT_NOTIONAL_USDT,
        },
        "coverage": {
            "trade_n": len(rows),
            "entry_market_reconstructed_n": sum(
                bool(r["entry_market_reconstructed"]) for r in rows
            ),
            "exit_market_reconstructed_n": sum(
                bool(r["exit_market_reconstructed"]) for r in rows
            ),
            "historical_replay_max_abs_error": max(
                abs(float(r["historical_replay_error"])) for r in rows
            ),
            "raw_symmetry_max_abs_error": max(
                abs(float(r["raw_symmetry_error"])) for r in rows
            ),
        },
        "scenarios": scenario_metrics,
        "reconciliation": {
            "historical_net": historical,
            "mirror_raw_same_market": raw_mirror,
            "gap_from_plus_abs_historical_to_raw_mirror": (
                abs(historical) - raw_mirror
            ),
            "regular_taker_fee_drag_vs_raw": raw_mirror - fee_only,
            "slippage_incremental_drag_vs_fee_only": fee_only - taker_2bps,
            "total_regular_taker_plus_2bps_drag_vs_raw": (
                raw_mirror - taker_2bps
            ),
        },
        "by_outcome_label": by_label,
    }


def _write_result_md(path: Path, summary: dict[str, Any]) -> None:
    s = summary["scenarios"]
    r = summary["reconciliation"]
    c = summary["coverage"]
    lines = [
        "# RD-0 Exact PnL Reconciliation",
        "",
        f"Status: **{summary['status']}**",
        "",
        "## Core result",
        "",
        "| Scenario | Net PnL | Wins | WR |",
        "|---|---:|---:|---:|",
    ]
    order = [
        ("Historical DB net", "historical_db_net"),
        ("Historical stored-fill replay", "historical_replay_net"),
        ("Original raw / same market", "original_raw_same_market"),
        ("Mirror raw / same market", "mirror_raw_same_market"),
        (
            "Mirror + Binance taker 0.05% / no slip",
            "mirror_taker_fee_only_same_qty",
        ),
        (
            "Mirror + Binance taker 0.05% + 2bps/side",
            "mirror_taker_2bps_same_qty",
        ),
        (
            "Mirror + BNB taker 0.045% + 2bps/side",
            "mirror_bnb_2bps_same_qty",
        ),
        (
            "Mirror $500 + taker 0.05% + 2bps/side",
            "mirror_500_taker_2bps",
        ),
    ]
    for name, key in order:
        m = s[key]
        lines.append(
            f"| {name} | ${m['net_pnl']:.2f} | {m['win_n']} | "
            f"{m['win_rate_pct']:.2f}% |"
        )
    lines += [
        "",
        "## Reconciliation",
        "",
        f"- Historical net: **${r['historical_net']:.2f}**",
        (
            "- Pure mirror raw at identical market endpoints: "
            f"**${r['mirror_raw_same_market']:.2f}**"
        ),
        (
            "- Gap versus naive `+abs(historical)` expectation: "
            f"**${r['gap_from_plus_abs_historical_to_raw_mirror']:.2f}**"
        ),
        (
            "- Binance regular taker fee drag: "
            f"**${r['regular_taker_fee_drag_vs_raw']:.2f}**"
        ),
        (
            "- Incremental 2bps/side slippage drag: "
            f"**${r['slippage_incremental_drag_vs_fee_only']:.2f}**"
        ),
        (
            "- Total taker+slippage drag versus raw mirror: "
            f"**${r['total_regular_taker_plus_2bps_drag_vs_raw']:.2f}**"
        ),
        "",
        "## Integrity gates",
        "",
        f"- trade_n: **{c['trade_n']}**",
        (
            "- historical replay max absolute error: "
            f"**{c['historical_replay_max_abs_error']:.12f}**"
        ),
        (
            "- raw LONG+SHORT symmetry max absolute error: "
            f"**{c['raw_symmetry_max_abs_error']:.12f}**"
        ),
        (
            "- reconstructed entry market rows: "
            f"**{c['entry_market_reconstructed_n']}**"
        ),
        (
            "- reconstructed exit market rows: "
            f"**{c['exit_market_reconstructed_n']}**"
        ),
        "",
        (
            "RD-0 does not change detector, Health, profit protection, "
            "or execution authority."
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/app/data")
    ap.add_argument(
        "--scope",
        choices=("wrong_direction", "all_long"),
        default="wrong_direction",
        help="RD-0 defaults to the frozen 555 TRUE_WRONG_DIRECTION LONG trades.",
    )
    ap.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "results"),
    )
    args = ap.parse_args()

    universe = _load_universe(Path(args.data_dir))
    ids = [r["position_id"] for r in universe]
    positions = _load_positions(ids)
    if args.scope == "wrong_direction":
        ids = [
            pid for pid in ids
            if str(positions[pid].get("outcome_label") or "")
            == "TRUE_WRONG_DIRECTION"
        ]
        if len(ids) != EXPECTED_WRONG_DIRECTION:
            raise RuntimeError(
                f"RD-0 wrong-direction scope expected "
                f"{EXPECTED_WRONG_DIRECTION}, got {len(ids)}"
            )
        positions = {pid: positions[pid] for pid in ids}
    orders = _load_orders(ids)

    detail = [
        _reconcile_trade(positions[pid], orders.get(pid) or [])
        for pid in ids
    ]
    summary = _summary(detail)

    expected_n = (
        EXPECTED_WRONG_DIRECTION
        if args.scope == "wrong_direction"
        else EXPECTED_LONG_UNIVERSE
    )
    if summary["coverage"]["trade_n"] != expected_n:
        raise RuntimeError(
            f"RD-0 universe drift: expected {expected_n}, "
            f"got {summary['coverage']['trade_n']}"
        )
    summary["scope"] = args.scope
    if summary["coverage"]["raw_symmetry_max_abs_error"] > 1e-8:
        raise RuntimeError("raw direction inversion symmetry failed")
    if summary["coverage"]["historical_replay_max_abs_error"] > 0.02:
        raise RuntimeError(
            "stored execution replay does not reconcile to DB realized PnL"
        )

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "RD0_TRADE_DETAIL.csv").open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(detail[0].keys()))
        writer.writeheader()
        writer.writerows(detail)
    (out / "RD0_EXACT_PNL_RECONCILIATION.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    _write_result_md(out / "RD0_RESULT.md", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
