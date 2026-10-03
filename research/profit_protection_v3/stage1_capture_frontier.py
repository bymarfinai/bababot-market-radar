from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from market_radar.persistence import _postgres_connect

DEFAULT_START_MS = 1790848801393
DEFAULT_CUTOFF_MS = 1791021852690
DEFAULT_ARM_MFE_PCT = 0.30
DEFAULT_RATIOS = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
DIAGNOSTIC_RATIOS = (0.925, 0.95, 0.975)
DEFAULT_FEE_RATE = 0.00075
DEFAULT_SLIPPAGE_BPS = 2.0


@dataclass(frozen=True)
class Observation:
    evaluated_at_ms: int
    current_price: float
    current_pnl_pct: float


@dataclass(frozen=True)
class ReplayDecision:
    armed: bool
    arm_at_ms: int | None
    triggered: bool
    trigger_at_ms: int | None
    trigger_market_price: float | None
    trigger_current_pnl_pct: float | None
    running_peak_pct: float


def exit_fill_price(*, side: str, market_price: float, slippage_bps: float) -> float:
    slip = float(slippage_bps) / 10_000.0
    return float(market_price) * (1.0 - slip if str(side).upper() == "LONG" else 1.0 + slip)


def gross_pnl(*, side: str, quantity: float, entry_price: float, exit_price: float) -> float:
    if str(side).upper() == "LONG":
        return float(quantity) * (float(exit_price) - float(entry_price))
    return float(quantity) * (float(entry_price) - float(exit_price))


def net_exit_pnl(
    *,
    side: str,
    quantity: float,
    entry_price: float,
    entry_fee: float,
    market_price: float,
    fee_rate: float,
    slippage_bps: float,
) -> tuple[float, float]:
    fill = exit_fill_price(side=side, market_price=market_price, slippage_bps=slippage_bps)
    gross = gross_pnl(side=side, quantity=quantity, entry_price=entry_price, exit_price=fill)
    exit_fee = float(quantity) * fill * float(fee_rate)
    return gross - float(entry_fee) - exit_fee, gross


def market_price_for_roi(*, side: str, entry_price: float, roi_pct: float) -> float:
    move = float(roi_pct) / 100.0
    if str(side).upper() == "LONG":
        return float(entry_price) * (1.0 + move)
    return float(entry_price) * (1.0 - move)


def replay_static_floor(
    observations: Iterable[Observation],
    *,
    ratio: float,
    arm_pct: float,
) -> ReplayDecision:
    running_peak = float("-inf")
    arm_at: int | None = None
    for obs in observations:
        running_peak = max(running_peak, float(obs.current_pnl_pct))
        if running_peak >= float(arm_pct) and arm_at is None:
            arm_at = int(obs.evaluated_at_ms)
        if arm_at is not None and float(obs.current_pnl_pct) <= float(ratio) * running_peak:
            return ReplayDecision(
                armed=True,
                arm_at_ms=arm_at,
                triggered=True,
                trigger_at_ms=int(obs.evaluated_at_ms),
                trigger_market_price=float(obs.current_price),
                trigger_current_pnl_pct=float(obs.current_pnl_pct),
                running_peak_pct=float(running_peak),
            )
    return ReplayDecision(
        armed=arm_at is not None,
        arm_at_ms=arm_at,
        triggered=False,
        trigger_at_ms=None,
        trigger_market_price=None,
        trigger_current_pnl_pct=None,
        running_peak_pct=float(running_peak if running_peak != float("-inf") else 0.0),
    )
def _load_snapshot(*, start_ms: int, cutoff_ms: int) -> tuple[list[dict[str, Any]], dict[str, list[Observation]]]:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with e as (
                    select position_id, max(mfe_pct) as true_mfe_pct
                    from position_evaluations
                    group by position_id
                )
                select p.position_id,p.symbol,p.side,p.entry_price,p.realized_pnl,
                       p.raw_json,e.true_mfe_pct,p.opened_at_ms,p.closed_at_ms
                from positions p
                join e on e.position_id=p.position_id
                where p.opened_at_ms>%s and p.status='CLOSED' and p.closed_at_ms<=%s
                order by p.opened_at_ms
                """,
                (int(start_ms), int(cutoff_ms)),
            )
            cols = [item[0] for item in cur.description]
            positions = [dict(zip(cols, row)) for row in cur.fetchall()]
            ids = [str(p["position_id"]) for p in positions]
            cur.execute(
                """
                select position_id,evaluated_at_ms,current_price,current_pnl_pct
                from pp_decision_v2_observations
                where evaluated_at_ms<=%s and position_id=any(%s)
                order by position_id,evaluated_at_ms
                """,
                (int(cutoff_ms), ids),
            )
            observations: dict[str, list[Observation]] = defaultdict(list)
            for pid, evaluated_at, price, pnl in cur.fetchall():
                observations[str(pid)].append(
                    Observation(
                        evaluated_at_ms=int(evaluated_at),
                        current_price=float(price),
                        current_pnl_pct=float(pnl),
                    )
                )
    return positions, observations


def _metadata(position: dict[str, Any]) -> dict[str, Any]:
    raw = position.get("raw_json")
    if isinstance(raw, dict):
        return raw
    return json.loads(raw or "{}")


def _observed_peak(stream: list[Observation]) -> float:
    return max((float(item.current_pnl_pct) for item in stream), default=float("-inf"))


def _position_inputs(position: dict[str, Any]) -> tuple[dict[str, Any], float, float, float, float, str]:
    meta = _metadata(position)
    return (
        meta,
        float(meta["initial_quantity"]),
        float(meta["initial_notional_usdt"]),
        float(meta["entry_fee_total"]),
        float(position["entry_price"]),
        str(position["side"]).upper(),
    )


def _full_close_at_final_market(
    position: dict[str, Any],
    *,
    fee_rate: float,
    slippage_bps: float,
) -> tuple[float, float]:
    meta, qty, _notional, entry_fee, entry, side = _position_inputs(position)
    market = float(meta["last_exit_market_price"])
    return net_exit_pnl(
        side=side,
        quantity=qty,
        entry_price=entry,
        entry_fee=entry_fee,
        market_price=market,
        fee_rate=fee_rate,
        slippage_bps=slippage_bps,
    )


def _evaluate_ratio(
    armed_positions: list[dict[str, Any]],
    observations: dict[str, list[Observation]],
    *,
    ratio: float,
    arm_pct: float,
    fee_rate: float,
    slippage_bps: float,
) -> dict[str, Any]:
    actual_net = sum(float(p["realized_pnl"] or 0.0) for p in armed_positions)
    poll_net = 0.0
    ideal_net = 0.0
    poll_gross = 0.0
    ideal_gross = 0.0
    true_peak_gross = 0.0
    observable_peak_gross = 0.0
    poll_wins = 0
    triggers = 0
    pre1_runner_exits = 0
    pre2_runner_exits = 0
    better = 0
    worse = 0
    ties = 0
    delays_seconds: list[float] = []
    trigger_retention: list[float] = []

    for position in armed_positions:
        pid = str(position["position_id"])
        stream = observations[pid]
        meta, qty, notional, entry_fee, entry, side = _position_inputs(position)
        true_mfe = float(position["true_mfe_pct"])
        obs_peak = _observed_peak(stream)
        true_peak_gross += notional * true_mfe / 100.0
        observable_peak_gross += notional * obs_peak / 100.0
        decision = replay_static_floor(stream, ratio=ratio, arm_pct=arm_pct)

        if decision.triggered:
            triggers += 1
            floor_roi = float(ratio) * float(decision.running_peak_pct)
            ideal_market = market_price_for_roi(side=side, entry_price=entry, roi_pct=floor_roi)
            ideal_trade_net, ideal_trade_gross = net_exit_pnl(
                side=side,
                quantity=qty,
                entry_price=entry,
                entry_fee=entry_fee,
                market_price=ideal_market,
                fee_rate=fee_rate,
                slippage_bps=slippage_bps,
            )
            poll_trade_net, poll_trade_gross = net_exit_pnl(
                side=side,
                quantity=qty,
                entry_price=entry,
                entry_fee=entry_fee,
                market_price=float(decision.trigger_market_price),
                fee_rate=fee_rate,
                slippage_bps=slippage_bps,
            )
            if decision.arm_at_ms is not None and decision.trigger_at_ms is not None:
                delays_seconds.append((decision.trigger_at_ms - decision.arm_at_ms) / 1000.0)
            if decision.running_peak_pct > 0 and decision.trigger_current_pnl_pct is not None:
                trigger_retention.append(
                    float(decision.trigger_current_pnl_pct) / float(decision.running_peak_pct)
                )
            if true_mfe >= 1.0 and decision.running_peak_pct < 1.0:
                pre1_runner_exits += 1
            if true_mfe >= 2.0 and decision.running_peak_pct < 2.0:
                pre2_runner_exits += 1
        else:
            poll_trade_net, poll_trade_gross = _full_close_at_final_market(
                position, fee_rate=fee_rate, slippage_bps=slippage_bps
            )
            ideal_trade_net, ideal_trade_gross = poll_trade_net, poll_trade_gross

        poll_net += poll_trade_net
        ideal_net += ideal_trade_net
        poll_gross += poll_trade_gross
        ideal_gross += ideal_trade_gross
        poll_wins += int(poll_trade_net > 0)
        delta = poll_trade_net - float(position["realized_pnl"] or 0.0)
        if delta > 1e-9:
            better += 1
        elif delta < -1e-9:
            worse += 1
        else:
            ties += 1

    n = len(armed_positions)
    return {
        "ratio": float(ratio),
        "n": n,
        "actual_net": actual_net,
        "poll_net": poll_net,
        "poll_delta_vs_actual": poll_net - actual_net,
        "ideal_floor_net": ideal_net,
        "poll_latency_cost_vs_ideal": poll_net - ideal_net,
        "poll_win_rate_pct": 100.0 * poll_wins / n if n else 0.0,
        "ideal_capture_true_peak_pct": 100.0 * ideal_gross / true_peak_gross if true_peak_gross else 0.0,
        "poll_capture_true_peak_pct": 100.0 * poll_gross / true_peak_gross if true_peak_gross else 0.0,
        "ideal_capture_observable_peak_pct": 100.0 * ideal_gross / observable_peak_gross if observable_peak_gross else 0.0,
        "poll_capture_observable_peak_pct": 100.0 * poll_gross / observable_peak_gross if observable_peak_gross else 0.0,
        "triggered": triggers,
        "better_than_actual": better,
        "worse_than_actual": worse,
        "ties_vs_actual": ties,
        "future_runner_exited_before_1pct": pre1_runner_exits,
        "future_runner_exited_before_2pct": pre2_runner_exits,
        "median_arm_to_trigger_seconds": statistics.median(delays_seconds) if delays_seconds else None,
        "median_trigger_retention_pct": (
            100.0 * statistics.median(trigger_retention) if trigger_retention else None
        ),
    }
def build_frontier(
    *,
    start_ms: int = DEFAULT_START_MS,
    cutoff_ms: int = DEFAULT_CUTOFF_MS,
    arm_pct: float = DEFAULT_ARM_MFE_PCT,
    ratios: Iterable[float] = DEFAULT_RATIOS,
    include_diagnostics: bool = True,
    fee_rate: float = DEFAULT_FEE_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> dict[str, Any]:
    positions, observations = _load_snapshot(start_ms=start_ms, cutoff_ms=cutoff_ms)
    true_eligible = [p for p in positions if float(p["true_mfe_pct"]) >= float(arm_pct)]
    armed = [
        p
        for p in true_eligible
        if _observed_peak(observations[str(p["position_id"])]) >= float(arm_pct)
    ]
    unobserved = [p for p in true_eligible if p not in armed]

    true_peak_gross = sum(
        float(_metadata(p)["initial_notional_usdt"]) * float(p["true_mfe_pct"]) / 100.0
        for p in true_eligible
    )
    observed_peak_gross = sum(
        float(_metadata(p)["initial_notional_usdt"])
        * max(_observed_peak(observations[str(p["position_id"])]), 0.0)
        / 100.0
        for p in true_eligible
    )
    observed_ratios = [
        _observed_peak(observations[str(p["position_id"])]) / float(p["true_mfe_pct"])
        for p in true_eligible
        if float(p["true_mfe_pct"]) > 0
    ]
    requested = list(float(r) for r in ratios)
    all_ratios = requested + ([float(r) for r in DIAGNOSTIC_RATIOS] if include_diagnostics else [])
    all_ratios = list(dict.fromkeys(all_ratios))

    frontier = [
        _evaluate_ratio(
            armed,
            observations,
            ratio=ratio,
            arm_pct=arm_pct,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
        )
        for ratio in all_ratios
    ]

    chrono: dict[str, Any] = {}
    n = len(armed)
    groups = {
        "EARLY": armed[: n // 3],
        "MID": armed[n // 3 : 2 * n // 3],
        "LATE": armed[2 * n // 3 :],
    }
    for ratio in (0.80, 0.90, 0.925):
        split_rows = {}
        for label, group in groups.items():
            metric = _evaluate_ratio(
                group,
                observations,
                ratio=ratio,
                arm_pct=arm_pct,
                fee_rate=fee_rate,
                slippage_bps=slippage_bps,
            )
            split_rows[label] = {
                "n": metric["n"],
                "actual_net": metric["actual_net"],
                "poll_net": metric["poll_net"],
                "delta_vs_actual": metric["poll_delta_vs_actual"],
                "win_rate_pct": metric["poll_win_rate_pct"],
            }
        chrono[str(ratio)] = split_rows

    return {
        "stage": "PP-DECISION-V3-STAGE1-CAPTURE-FRONTIER",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "fee_rate": float(fee_rate),
        "slippage_bps": float(slippage_bps),
        "total_closed": len(positions),
        "actual_total_net": sum(float(p["realized_pnl"] or 0.0) for p in positions),
        "true_mfe_eligible": len(true_eligible),
        "observable_armed": len(armed),
        "true_mfe_eligible_but_never_observed_at_arm": len(unobserved),
        "observable_share_of_true_eligible_pct": (
            100.0 * len(armed) / len(true_eligible) if true_eligible else 0.0
        ),
        "true_peak_gross": true_peak_gross,
        "observable_peak_gross": observed_peak_gross,
        "weighted_observable_peak_vs_true_peak_pct": (
            100.0 * observed_peak_gross / true_peak_gross if true_peak_gross else 0.0
        ),
        "median_observable_peak_vs_true_peak_pct": (
            100.0 * statistics.median(observed_ratios) if observed_ratios else 0.0
        ),
        "unobserved_actual_net": sum(float(p["realized_pnl"] or 0.0) for p in unobserved),
        "unobserved_true_peak_gross": sum(
            float(_metadata(p)["initial_notional_usdt"]) * float(p["true_mfe_pct"]) / 100.0
            for p in unobserved
        ),
        "frontier": frontier,
        "chronological_checks": chrono,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=DEFAULT_START_MS)
    parser.add_argument("--cutoff-ms", type=int, default=DEFAULT_CUTOFF_MS)
    parser.add_argument("--arm-pct", type=float, default=DEFAULT_ARM_MFE_PCT)
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = build_frontier(
        start_ms=args.start_ms,
        cutoff_ms=args.cutoff_ms,
        arm_pct=args.arm_pct,
        include_diagnostics=not args.no_diagnostics,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
