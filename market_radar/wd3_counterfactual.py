from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

import psycopg2.extras

from .persistence import _postgres_connect
from .wd2_anatomy import (
    WD2_CUTOFF_MS,
    WRONG,
    RECOVERED,
    STALL,
    FAILURE,
    RUNNER,
    LABELS,
    _f,
    _j,
)


WD3_VERSION = "wd3-counterfactual-direction-fix-v1"
HORIZONS_MIN = (1, 3, 5)
TOLERANCE_SECONDS = 45.0

SIGNATURES = (
    "ret3neg_and_flow_opp",
    "ret3neg_and_positioning_opp",
    "ret3neg_and_micro_opp",
    "adverse_families_ge_2",
    "adverse_families_ge_3",
    "danger_ge_2",
    "danger_ge_4",
    "pnl_le_minus_035",
    "pnl_le_minus_035_and_adverse_ge_2",
)


def _exit_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 - slip if side == "LONG" else 1.0 + slip)


def _entry_fill(side: str, market: float, slippage_bps: float) -> float:
    slip = max(0.0, float(slippage_bps)) / 10000.0
    return market * (1.0 + slip if side == "LONG" else 1.0 - slip)


def _gross(side: str, quantity: float, entry: float, exit_price: float) -> float:
    return (
        quantity * (exit_price - entry)
        if side == "LONG"
        else quantity * (entry - exit_price)
    )


def _load_positions() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.outcome_label,
            w.symbol, w.side, w.opened_at_ms, w.closed_at_ms,
            p.entry_price, p.exit_price, p.realized_pnl,
            p.realized_pnl_pct, p.raw_json
        from wd1_trade_labels w
        join positions p on p.position_id=w.position_id
        where w.closed_at_ms <= %s
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS,))
            return [dict(row) for row in cur.fetchall()]


def _load_observations() -> dict[str, list[dict[str, Any]]]:
    query = """
        select
            o.position_id, o.evaluated_at_ms, o.current_price,
            o.current_pnl_pct, o.mfe_pct, o.danger_score,
            o.position_status, o.snapshot_json
        from pp_decision_v2_observations o
        join wd1_trade_labels w on w.position_id=o.position_id
        where w.closed_at_ms <= %s
          and o.evaluated_at_ms >= w.opened_at_ms
          and o.evaluated_at_ms <= w.closed_at_ms
        order by o.position_id, o.evaluated_at_ms
    """
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS,))
            for row in cur.fetchall():
                out[str(row["position_id"])].append(dict(row))
    return out


def _load_orders() -> dict[str, list[dict[str, Any]]]:
    query = """
        select
            o.position_id, o.action, o.status, o.executed_at_ms,
            o.executed_quantity, o.market_price, o.fill_price, o.fee
        from paper_orders o
        join wd1_trade_labels w on w.position_id=o.position_id
        where w.closed_at_ms <= %s
          and o.status='FILLED'
        order by o.position_id, o.executed_at_ms
    """
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS,))
            for row in cur.fetchall():
                out[str(row["position_id"])].append(dict(row))
    return out


def _raw_float(
    raw: dict[str, Any],
    key: str,
    default: float,
) -> float:
    value = raw.get(key)
    return default if value is None else float(value)


def _position_meta(position: dict[str, Any]) -> dict[str, float]:
    raw = _j(position.get("raw_json"))
    final_market = raw.get("last_exit_market_price")
    if final_market is None:
        final_market = position.get("exit_price")
    return {
        "initial_notional": _raw_float(raw, "initial_notional_usdt", 500.0),
        "initial_quantity": _raw_float(raw, "initial_quantity", 0.0),
        "entry_fee_total": _raw_float(raw, "entry_fee_total", 0.0),
        "fee_rate": _raw_float(raw, "fee_rate", 0.00075),
        "slippage_bps": _raw_float(raw, "slippage_bps", 2.0),
        "final_market_price": 0.0 if final_market is None else float(final_market),
    }


def _match_observation(
    position: dict[str, Any],
    observations: dict[str, list[dict[str, Any]]],
    horizon_min: int,
    tolerance_seconds: float = TOLERANCE_SECONDS,
) -> dict[str, Any] | None:
    target = int(position["opened_at_ms"]) + horizon_min * 60_000
    if int(position["closed_at_ms"]) < target:
        return None
    rows = observations.get(str(position["position_id"])) or []
    if not rows:
        return None
    chosen = min(
        rows,
        key=lambda row: abs(int(row["evaluated_at_ms"]) - target),
    )
    if abs(int(chosen["evaluated_at_ms"]) - target) > tolerance_seconds * 1000:
        return None
    return chosen


def observation_flags(observation: dict[str, Any]) -> dict[str, bool]:
    snap = _j(observation.get("snapshot_json"))
    ret3 = _f(snap.get("side_ret_3m_pct"))
    ret3neg = ret3 is not None and ret3 < 0
    flow_opp = bool(snap.get("flow_opposite"))
    pos_opp = bool(snap.get("positioning_opposite"))
    micro_opp = bool(snap.get("opposite_micro_structure"))
    adverse_count = sum((ret3neg, flow_opp, pos_opp, micro_opp))
    danger = float(observation.get("danger_score") or 0.0)
    pnl = float(observation.get("current_pnl_pct") or 0.0)
    return {
        "ret3neg_and_flow_opp": ret3neg and flow_opp,
        "ret3neg_and_positioning_opp": ret3neg and pos_opp,
        "ret3neg_and_micro_opp": ret3neg and micro_opp,
        "adverse_families_ge_2": adverse_count >= 2,
        "adverse_families_ge_3": adverse_count >= 3,
        "danger_ge_2": danger >= 2,
        "danger_ge_4": danger >= 4,
        "pnl_le_minus_035": pnl <= -0.35,
        "pnl_le_minus_035_and_adverse_ge_2": (
            pnl <= -0.35 and adverse_count >= 2
        ),
    }


def _realized_before_horizon(
    position: dict[str, Any],
    orders: list[dict[str, Any]],
    target_ms: int,
) -> tuple[float, float, float]:
    """Return prior realized net, remaining qty, allocated entry fee."""
    meta = _position_meta(position)
    initial_qty = meta["initial_quantity"]
    entry = float(position["entry_price"])
    entry_fee_total = meta["entry_fee_total"]
    side = str(position["side"]).upper()
    remaining = initial_qty
    allocated_entry_fee = 0.0
    realized = 0.0

    for order in orders:
        executed_at = order.get("executed_at_ms")
        if executed_at is None or int(executed_at) >= target_ms:
            continue
        action = str(order.get("action") or "").upper()
        if action == "OPEN":
            continue
        qty = float(order.get("executed_quantity") or 0.0)
        fill = float(order.get("fill_price") or 0.0)
        fee = float(order.get("fee") or 0.0)
        if qty <= 0 or fill <= 0:
            continue
        qty = min(qty, remaining)
        entry_alloc = (
            entry_fee_total * (qty / initial_qty)
            if initial_qty > 0 else 0.0
        )
        realized += _gross(side, qty, entry, fill) - entry_alloc - fee
        allocated_entry_fee += entry_alloc
        remaining = max(0.0, remaining - qty)
    return realized, remaining, allocated_entry_fee


def dynamic_exit_net(
    position: dict[str, Any],
    orders: list[dict[str, Any]],
    observation: dict[str, Any],
) -> float:
    """Close remaining actual position at the matched observation price."""
    target_ms = int(observation["evaluated_at_ms"])
    prior_net, remaining, allocated = _realized_before_horizon(
        position,
        orders,
        target_ms,
    )
    if remaining <= 0:
        return float(position.get("realized_pnl") or 0.0)

    meta = _position_meta(position)
    side = str(position["side"]).upper()
    market = float(observation["current_price"])
    fill = _exit_fill(side, market, meta["slippage_bps"])
    remaining_entry_fee = max(0.0, meta["entry_fee_total"] - allocated)
    exit_fee = remaining * fill * meta["fee_rate"]
    gross = _gross(side, remaining, float(position["entry_price"]), fill)
    return prior_net + gross - remaining_entry_fee - exit_fee


def delayed_entry_censor_net(
    position: dict[str, Any],
    observation: dict[str, Any],
) -> float:
    """Enter at horizon, then hold to the original trade's final market censor.

    This is intentionally a benchmark, not a lifecycle replay.
    """
    meta = _position_meta(position)
    side = str(position["side"]).upper()
    market_entry = float(observation["current_price"])
    entry_fill = _entry_fill(side, market_entry, meta["slippage_bps"])
    notional = meta["initial_notional"]
    if entry_fill <= 0 or notional <= 0:
        return float("nan")
    qty = notional / entry_fill
    entry_fee = notional * meta["fee_rate"]

    market_exit = meta["final_market_price"]
    exit_fill = _exit_fill(side, market_exit, meta["slippage_bps"])
    exit_fee = qty * exit_fill * meta["fee_rate"]
    gross = _gross(side, qty, entry_fill, exit_fill)
    return gross - entry_fee - exit_fee


def _empty_label_metrics() -> dict[str, dict[str, float]]:
    return {
        label: {
            "n": 0,
            "actual_net": 0.0,
            "policy_net": 0.0,
            "flagged": 0,
        }
        for label in LABELS
    }


def _finalize_policy(
    *,
    policy: str,
    horizon_min: int,
    signature: str,
    per_trade: list[dict[str, Any]],
) -> dict[str, Any]:
    actual_total = sum(float(x["actual_net"]) for x in per_trade)
    policy_total = sum(float(x["policy_net"]) for x in per_trade)
    matched = [x for x in per_trade if x["matched"]]
    flagged = [x for x in matched if x["flagged"]]
    by_label = _empty_label_metrics()
    for x in per_trade:
        rec = by_label[str(x["label"])]
        rec["n"] += 1
        rec["actual_net"] += float(x["actual_net"])
        rec["policy_net"] += float(x["policy_net"])
        rec["flagged"] += int(bool(x["flagged"]))

    label_counts = Counter(str(x["label"]) for x in matched)
    flagged_counts = Counter(str(x["label"]) for x in flagged)
    for label, rec in by_label.items():
        rec["delta_net"] = rec["policy_net"] - rec["actual_net"]
        rec["flag_rate_of_matched_pct"] = (
            100.0 * flagged_counts[label] / label_counts[label]
            if label_counts[label] else None
        )

    winners_actual = sum(float(x["actual_net"]) > 0 for x in per_trade)
    winners_policy = sum(float(x["policy_net"]) > 0 for x in per_trade)
    return {
        "policy": policy,
        "horizon_min": horizon_min,
        "signature": signature,
        "full_cohort_n": len(per_trade),
        "matched_n": len(matched),
        "flagged_n": len(flagged),
        "flag_rate_of_matched_pct": (
            100.0 * len(flagged) / len(matched) if matched else None
        ),
        "actual_net": actual_total,
        "policy_net": policy_total,
        "delta_net": policy_total - actual_total,
        "actual_positive_trades": winners_actual,
        "policy_positive_trades": winners_policy,
        "actual_positive_rate_pct": (
            100.0 * winners_actual / len(per_trade) if per_trade else None
        ),
        "policy_positive_rate_pct": (
            100.0 * winners_policy / len(per_trade) if per_trade else None
        ),
        "wrong_capture_pct_of_matched": (
            100.0 * flagged_counts[WRONG] / label_counts[WRONG]
            if label_counts[WRONG] else None
        ),
        "recovered_harm_pct_of_matched": (
            100.0 * flagged_counts[RECOVERED] / label_counts[RECOVERED]
            if label_counts[RECOVERED] else None
        ),
        "runner_harm_pct_of_matched": (
            100.0 * flagged_counts[RUNNER] / label_counts[RUNNER]
            if label_counts[RUNNER] else None
        ),
        "by_label": by_label,
    }


def simulate_dynamic_exit(
    positions: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    orders: dict[str, list[dict[str, Any]]],
    horizon_min: int,
    signature: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for position in positions:
        actual = float(position.get("realized_pnl") or 0.0)
        obs = _match_observation(position, observations, horizon_min)
        matched = obs is not None
        flagged = bool(obs and observation_flags(obs).get(signature))
        policy_net = actual
        if obs is not None and flagged:
            policy_net = dynamic_exit_net(
                position,
                orders.get(str(position["position_id"])) or [],
                obs,
            )
        rows.append({
            "position_id": position["position_id"],
            "opened_at_ms": int(position["opened_at_ms"]),
            "label": position["outcome_label"],
            "actual_net": actual,
            "policy_net": policy_net,
            "matched": matched,
            "flagged": flagged,
        })
    return _finalize_policy(
        policy="DYNAMIC_EXIT",
        horizon_min=horizon_min,
        signature=signature,
        per_trade=rows,
    )


def simulate_delay_confirm(
    positions: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    horizon_min: int,
    signature: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for position in positions:
        actual = float(position.get("realized_pnl") or 0.0)
        obs = _match_observation(position, observations, horizon_min)
        matched = obs is not None
        flagged = bool(obs and observation_flags(obs).get(signature))
        policy_net = actual
        if obs is not None:
            policy_net = 0.0 if flagged else delayed_entry_censor_net(position, obs)
        rows.append({
            "position_id": position["position_id"],
            "opened_at_ms": int(position["opened_at_ms"]),
            "label": position["outcome_label"],
            "actual_net": actual,
            "policy_net": policy_net,
            "matched": matched,
            "flagged": flagged,
        })
    result = _finalize_policy(
        policy="DELAY_CONFIRM_FIXED_CENSOR",
        horizon_min=horizon_min,
        signature=signature,
        per_trade=rows,
    )
    result["matched_entered_n"] = result["matched_n"] - result["flagged_n"]
    result["matched_entry_retention_pct"] = (
        100.0 * result["matched_entered_n"] / result["matched_n"]
        if result["matched_n"] else None
    )
    return result


def chronological_robustness(
    positions: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    orders: dict[str, list[dict[str, Any]]],
    *,
    policy: str,
    horizon_min: int,
    signature: str,
) -> list[dict[str, Any]]:
    ordered = sorted(positions, key=lambda row: int(row["opened_at_ms"]))
    n = len(ordered)
    cuts = [0, n // 3, (2 * n) // 3, n]
    out: list[dict[str, Any]] = []
    for i in range(3):
        subset = ordered[cuts[i]:cuts[i + 1]]
        if policy == "DYNAMIC_EXIT":
            result = simulate_dynamic_exit(
                subset, observations, orders, horizon_min, signature
            )
        else:
            result = simulate_delay_confirm(
                subset, observations, horizon_min, signature
            )
        out.append({
            "slice": i + 1,
            "n": len(subset),
            "opened_min_ms": min(int(x["opened_at_ms"]) for x in subset),
            "opened_max_ms": max(int(x["opened_at_ms"]) for x in subset),
            "matched_n": result["matched_n"],
            "flagged_n": result["flagged_n"],
            "delta_net": result["delta_net"],
            "wrong_capture_pct_of_matched": result["wrong_capture_pct_of_matched"],
            "recovered_harm_pct_of_matched": result["recovered_harm_pct_of_matched"],
        })
    return out


def run_wd3() -> dict[str, Any]:
    positions = _load_positions()
    observations = _load_observations()
    orders = _load_orders()

    policies: list[dict[str, Any]] = []
    for horizon in HORIZONS_MIN:
        for signature in SIGNATURES:
            policies.append(
                simulate_dynamic_exit(
                    positions, observations, orders, horizon, signature
                )
            )
            policies.append(
                simulate_delay_confirm(
                    positions, observations, horizon, signature
                )
            )

    ranked_dynamic = sorted(
        [x for x in policies if x["policy"] == "DYNAMIC_EXIT"],
        key=lambda x: x["delta_net"],
        reverse=True,
    )
    ranked_delay = sorted(
        [x for x in policies if x["policy"] == "DELAY_CONFIRM_FIXED_CENSOR"],
        key=lambda x: x["delta_net"],
        reverse=True,
    )

    top_candidates = []
    for result in (ranked_dynamic[:5] + ranked_delay[:5]):
        top_candidates.append({
            **result,
            "chrono_thirds": chronological_robustness(
                positions,
                observations,
                orders,
                policy=result["policy"],
                horizon_min=int(result["horizon_min"]),
                signature=str(result["signature"]),
            ),
        })

    return {
        "version": WD3_VERSION,
        "authority": "RESEARCH_ONLY",
        "discovery_cutoff_ms": WD2_CUTOFF_MS,
        "full_cohort_n": len(positions),
        "actual_net": sum(float(x.get("realized_pnl") or 0.0) for x in positions),
        "methodology": {
            "dynamic_exit": (
                "Keep actual entry and any already-filled reductions; when the "
                "signature fires at the matched horizon, close only remaining "
                "quantity at observed market price with recorded fee/slippage."
            ),
            "delay_confirm": (
                "For matched trades, skip flagged signals; otherwise enter $500 "
                "at observed horizon market price and hold to original final "
                "market censor. This is a fixed-censor benchmark, not lifecycle replay."
            ),
            "unmatched_policy": "UNCHANGED_ACTUAL_PNL_CONSERVATIVE",
            "horizon_tolerance_seconds": TOLERANCE_SECONDS,
        },
        "ranked_dynamic_exit": ranked_dynamic,
        "ranked_delay_confirm": ranked_delay,
        "top_candidates_with_chrono_thirds": top_candidates,
    }
