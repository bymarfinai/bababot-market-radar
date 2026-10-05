from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from market_radar.parallel_protection_shadow_adapters import _evaluate_branch
from market_radar.parallel_protection_shadow_settlement import _settle_branch
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "research/profit_protection_v4/results/all_positive_mfe_v42c_replay.csv"
V43 = ROOT / "research/profit_protection_v4/results/v43_set2_full170_challenger_replay.csv"
OUT = ROOT / "research/profit_protection_v4/results/ps4_historical_settlement_parity.json"
EPS = 1e-8


def parent_from_position(pid: str, p: dict[str, Any]) -> dict[str, Any]:
    meta = json.loads(p.get("raw_json") or "{}")
    return {
        "parent_id": f"HIST:{pid}",
        "source_position_id": pid,
        "side": str(p["side"]).upper(),
        "entry_price": float(p["entry_price"]),
        "initial_quantity": float(meta.get("initial_quantity") or 0.0),
        "initial_notional_usdt": float(meta.get("initial_notional_usdt") or 500.0),
        "metadata_json": json.dumps(meta),
    }


def branch(key: str, parent: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent_id": parent["parent_id"],
        "branch_key": key,
        "status": "OPEN",
        "initial_quantity": parent["initial_quantity"],
        "remaining_quantity": parent["initial_quantity"],
        "mfe_pct": None,
        "mae_pct": None,
        "state_json": "{}",
    }


def event_stream(
    pid: str,
    position: dict[str, Any],
    observations: dict[str, list[dict[str, Any]]],
    orders: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    opened = int(position["opened_at_ms"])
    closed = int(position["closed_at_ms"])
    raw: list[tuple[int, int, dict[str, Any]]] = []

    for i, o in enumerate(orders[pid]):
        action = str(o["action"]).upper()
        if action == "OPEN" or o["executed_at_ms"] is None:
            continue
        ts = int(o["executed_at_ms"])
        if not (opened <= ts <= closed):
            continue
        if action == "CLOSE":
            typ = "SOURCE_POSITION_CLOSE"
            payload = {
                "reason": "historical_source_close",
                "fill_price": float(o["fill_price"]),
                "fee": float(o["fee"] or 0.0),
            }
        else:
            typ = "SOURCE_POSITION_REDUCE"
            payload = {
                "reason": f"historical_source_{action.lower()}",
                "executed_quantity": float(o["executed_quantity"] or 0.0),
                "fill_price": float(o["fill_price"]),
                "fee": float(o["fee"] or 0.0),
            }
        raw.append(
            (
                ts,
                0,  # historical executed source order before same-ms observation
                {
                    "event_type": typ,
                    "market_price": float(o["fill_price"]),
                    "payload_json": json.dumps(payload),
                    "source_event_id": f"SRC:{i}:{ts}:{action}",
                    "event_time_ms": ts,
                },
            )
        )

    for i, x in enumerate(observations[pid]):
        ts = int(x["observed_at_ms"])
        if not (opened <= ts <= closed):
            continue
        raw.append(
            (
                ts,
                1,
                {
                    "event_type": "PROTECTION_SAMPLE_5S",
                    "market_price": float(x["current_price"]),
                    "payload_json": "{}",
                    "source_event_id": f"OBS:{i}:{ts}",
                    "event_time_ms": ts,
                },
            )
        )

    raw.sort(key=lambda x: (x[0], x[1], x[2]["source_event_id"]))
    return [item[2] for item in raw]


def replay(
    key: str,
    parent: dict[str, Any],
    stream: list[dict[str, Any]],
) -> dict[str, Any]:
    b = branch(key, parent)
    events: dict[int, dict[str, Any]] = {}
    settlements: list[dict[str, Any]] = []

    for seq, e0 in enumerate(stream, 1):
        e = {**e0, "event_seq": seq}
        events[seq] = e
        state, mfe, mae, current_state = _evaluate_branch(
            parent=parent,
            branch=b,
            event=e,
        )
        b["state_json"] = json.dumps(state)
        b["mfe_pct"] = mfe
        b["mae_pct"] = mae
        b["current_state"] = current_state

    if not events:
        raise RuntimeError(f"no replay events for {parent['source_position_id']}")

    # Settle once at the end. Intent history preserves every protection action,
    # so this validates PS-4 restart/catch-up semantics without O(n^2) rescans.
    new_rows, state, remaining, status, current_state = _settle_branch(
        parent=parent,
        branch=b,
        events=events,
        upto_event_seq=max(events),
        existing=settlements,
    )
    settlements.extend(new_rows)
    settlements.sort(
        key=lambda r: (int(r["event_seq"]), str(r["intent_source"]), str(r["action"]))
    )
    b["state_json"] = json.dumps(state)
    b["remaining_quantity"] = remaining
    b["status"] = status
    b["current_state"] = current_state

    state = json.loads(b["state_json"])
    return {
        "status": b["status"],
        "remaining_quantity": float(b["remaining_quantity"]),
        "realized_pnl_usdt": float(state.get("realized_pnl_usdt") or 0.0),
        "realized_pnl_pct": float(state.get("realized_pnl_pct") or 0.0),
        "current_pnl_usdt": float(state.get("current_pnl_usdt") or 0.0),
        "settlement_n": len(settlements),
        "protection_filled_n": sum(
            r["intent_source"] == "PROTECTION" and r["status"] == "VIRTUAL_FILLED"
            for r in settlements
        ),
        "source_filled_n": sum(
            r["intent_source"] == "SOURCE_LIFECYCLE" and r["status"] == "VIRTUAL_FILLED"
            for r in settlements
        ),
        "intent_history": state.get("intent_history") or [],
    }


def main() -> None:
    base = list(csv.DictReader(BASE.open(encoding="utf-8")))
    v43_rows = {
        r["position_id"]: r
        for r in csv.DictReader(V43.open(encoding="utf-8"))
    }
    ids = [r["position_id"] for r in base]
    positions, observations, orders = load_market_data(ids)

    v42_mismatch = []
    v42_total = 0.0
    v43_causal_total = 0.0
    v43_causal_wins = 0
    v43_frozen_total = 0.0
    v43_frozen_wins = 0
    v43_diff = []
    v43_changed_vs_frozen = 0
    v43_changed_by_action = Counter()

    for row in base:
        pid = row["position_id"]
        p = positions[pid]
        parent = parent_from_position(pid, p)
        stream = event_stream(pid, p, observations, orders)

        a = replay("V42_BASELINE", parent, stream)
        expected_v42 = float(row["protected_usdt"])
        delta = a["realized_pnl_usdt"] - expected_v42
        v42_total += a["realized_pnl_usdt"]
        if abs(delta) > EPS:
            v42_mismatch.append(
                {
                    "position_id": pid,
                    "expected": expected_v42,
                    "got": a["realized_pnl_usdt"],
                    "delta": delta,
                    "expected_action": row["protection_actions"],
                    "status": a["status"],
                    "remaining": a["remaining_quantity"],
                }
            )

        b = replay("V43_LS", parent, stream)
        frozen = float(v43_rows[pid]["challenger_usdt"])
        causal = b["realized_pnl_usdt"]
        v43_causal_total += causal
        v43_causal_wins += causal > 0
        v43_frozen_total += frozen
        v43_frozen_wins += frozen > 0
        if abs(causal - frozen) > EPS:
            v43_changed_vs_frozen += 1
            v43_changed_by_action[row["protection_actions"]] += 1
            if len(v43_diff) < 30:
                v43_diff.append(
                    {
                        "position_id": pid,
                        "side": row["side"],
                        "v42_action": row["protection_actions"],
                        "frozen_v43_usdt": frozen,
                        "causal_v43_usdt": causal,
                        "delta": causal - frozen,
                        "causal_intents": b["intent_history"],
                    }
                )

    out = {
        "stage": "PS-4-HISTORICAL-SETTLEMENT-PARITY",
        "v42": {
            "n": len(base),
            "mismatch_n": len(v42_mismatch),
            "mismatches": v42_mismatch[:30],
            "ps4_total_usdt": v42_total,
            "frozen_total_usdt": sum(float(r["protected_usdt"]) for r in base),
            "exact_within_1e_8": not v42_mismatch,
        },
        "v43_forward_causal_diagnostic": {
            "n": len(base),
            "causal_total_usdt": v43_causal_total,
            "causal_wins": v43_causal_wins,
            "causal_wr_pct": 100.0 * v43_causal_wins / len(base),
            "frozen_ex_post_scope_total_usdt": v43_frozen_total,
            "frozen_ex_post_scope_wins": v43_frozen_wins,
            "frozen_ex_post_scope_wr_pct": 100.0 * v43_frozen_wins / len(base),
            "changed_vs_frozen_n": v43_changed_vs_frozen,
            "changed_by_v42_action": dict(v43_changed_by_action),
            "frozen_reduce25_target_n": sum(
                r["protection_actions"] == "REDUCE25" for r in base
            ),
            "frozen_reduce25_target_mismatch_n": int(
                v43_changed_by_action.get("REDUCE25", 0)
            ),
            "note": (
                "Frozen V4.3 replaced only ex-post V4.2 REDUCE25 trades. "
                "PS-3/PS-4 forward branch is causal and cannot know that future lane."
            ),
            "sample_differences": v43_diff,
        },
        "status": "PASS" if not v42_mismatch else "FAIL",
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(out, sort_keys=True))
    if out["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
