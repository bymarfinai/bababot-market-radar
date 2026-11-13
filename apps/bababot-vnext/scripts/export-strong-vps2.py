#!/usr/bin/env python3
"""Read-only, causal PAPER ledger snapshot for BabaBot vNext (schema v1).

Only reads SQLite. Writes no DB tables, takes no orders, performs no network.
Use on VPS2: python3 export-strong-vps2.py --root <research-workspace>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
from collections import defaultdict

STRATEGIES = [
    ("A", "Original A", "original", "REFERENCE", "Original A baseline"),
    ("P01", "P01", "p-series", "ACTIVE", "F + UPP30 + SPR + EARLY65"),
    ("P02", "P02", "p-series", "PAUSED", "P-series research branch"),
    ("P03", "P03", "p-series", "PAUSED", "P-series research branch"),
    ("P04", "P04", "p-series", "PAUSED", "P-series research branch"),
    ("P05", "P05", "p-series", "ACTIVE", "F + UPP30 + SPR + SFD"),
    ("P06", "P06", "p-series", "PAUSED", "P-series research branch"),
    ("P07", "P07", "p-series", "ACTIVE", "F + UPP30 + SPR + EFD90"),
    ("M01", "M01", "master", "ACTIVE", "F + UPP30 + SPR + SFD + TIME602"),
    ("M02", "M02", "master", "ACTIVE", "M01 + TP040"),
    ("M03", "M03", "master", "ACTIVE", "M01 + F15 + AT10 + QD90R"),
    ("M04", "M04", "master", "ACTIVE", "M03 + E1 pre-entry gate"),
    ("M05", "M05", "master", "ACTIVE", "M03 + D1_T90_WEAK exit"),
]
LEDGERS = [
    ("A", "ip01-independent-paper/v2_a_independent_paper.sqlite3"),
    ("P", "strong-seven-modular-20261107/seven_forward.sqlite3"),
    ("M12", "strong-master-matrix-20261108/master_forward.sqlite3"),
    ("M3", "strong-m03-modular-20261108/m03_forward.sqlite3"),
    ("M45", "strong-m04-m05-modular-20261109/m45_forward.sqlite3"),
]


def ro_connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required ledger: {path.name}")
    uri = path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=4)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA busy_timeout=4000")
    return con


def finite(value):
    if value is None:
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def maybe_state(value):
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def status_name(value):
    status = str(value or "").upper()
    if status in ("OPEN", "CLOSED", "DATA_GAP", "CENSORED_30MIN"):
        return status
    return "DATA_GAP"


def normalize(root: Path):
    all_trades = []
    for family, relative in LEDGERS:
        with ro_connect(root / relative) as con:
            if family == "A":
                for r in con.execute(
                    "SELECT source_event_id,symbol,status,opened_at_ms,closed_at_ms,"
                    "entry_fill_price,exit_fill_price,realized_pnl,close_reason "
                    "FROM paper_a ORDER BY opened_at_ms"
                ):
                    row = dict(r)
                    all_trades.append({
                        "id": "A::" + row["source_event_id"],
                        "strategyId": "A",
                        "sourceEventId": row["source_event_id"],
                        "symbol": row["symbol"],
                        "status": status_name(row["status"]),
                        "openedAtMs": row["opened_at_ms"],
                        "closedAtMs": row["closed_at_ms"],
                        "entryPrice": finite(row["entry_fill_price"]),
                        "exitPrice": finite(row["exit_fill_price"]),
                        "netPnl": finite(row["realized_pnl"]) if row["status"] == "CLOSED" else None,
                        "closeReason": row["close_reason"] or None,
                        "decision": None,
                        "decisionReason": None,
                    })
                continue
            signal_rows = {
                r["source_id"]: dict(r) for r in con.execute("SELECT * FROM signals")
            }
            decision_rows = {}
            if family == "M45":
                decision_rows = {
                    (r["paper"], r["source_id"]): dict(r)
                    for r in con.execute("SELECT paper,source_id,decision,reason FROM decisions")
                }
            for r in con.execute("SELECT * FROM positions ORDER BY opened_ms,paper"):
                row = dict(r)
                label = str(row["paper"]).replace("SL-", "").upper()
                if label not in {s[0] for s in STRATEGIES}:
                    raise ValueError(f"Unknown paper branch: {label}")
                signal = signal_rows.get(row["source_id"], {})
                state = maybe_state(signal.get("state_json"))
                raw_entry = signal.get("entry_fill")
                if raw_entry is None:
                    raw_entry = state.get("entry_fill") or state.get("entry_price")
                decision = decision_rows.get((row["paper"], row["source_id"]), {})
                status = status_name(row["status"])
                all_trades.append({
                    "id": label + "::" + row["source_id"],
                    "strategyId": label,
                    "sourceEventId": row["source_id"],
                    "symbol": row["symbol"],
                    "status": status,
                    "openedAtMs": row["opened_ms"],
                    "closedAtMs": row["close_ms"],
                    "entryPrice": finite(raw_entry),
                    "exitPrice": finite(row["exit_price"]),
                    "netPnl": finite(row["pnl"]) if status == "CLOSED" else None,
                    "closeReason": row.get("reason") or None,
                    "decision": decision.get("decision") or None,
                    "decisionReason": decision.get("reason") or None,
                })

    if len({t["id"] for t in all_trades}) != len(all_trades):
        raise ValueError("Duplicate paper/qualification ID detected")
    metrics = defaultdict(list)
    for trade in all_trades:
        metrics[trade["strategyId"]].append(trade)
    strategies = []
    for code, label, family, activity, module in STRATEGIES:
        rows = metrics[code]
        closed = [t for t in rows if t["status"] == "CLOSED" and t["netPnl"] is not None]
        wins = sum(1 for t in closed if t["netPnl"] > 0)
        losses = sum(1 for t in closed if t["netPnl"] < 0)
        last = max([max(t["openedAtMs"], t["closedAtMs"] or 0) for t in rows], default=None)
        strategies.append({
            "id": code,
            "label": label,
            "family": family,
            "activity": activity,
            "moduleLabel": module,
            "closed": len(closed),
            "open": sum(1 for t in rows if t["status"] == "OPEN"),
            "wins": wins,
            "losses": losses,
            "dataGap": sum(1 for t in rows if t["status"] not in ("OPEN", "CLOSED")),
            "netPnl": sum(t["netPnl"] for t in closed),
            "winRate": wins / len(closed) * 100.0 if closed else None,
            "lastActivityAtMs": last,
        })
    return {
        "schemaVersion": 1,
        "origin": "vps2-independent-paper",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "strategies": strategies,
        "trades": sorted(all_trades, key=lambda t: (t["openedAtMs"], t["strategyId"]), reverse=True),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/ubuntu/market-detektor-research"))
    parser.add_argument("--summary", action="store_true", help="Print only counts (for health checks)")
    args = parser.parse_args()
    snapshot = normalize(args.root)
    if args.summary:
        print(json.dumps({
            "generatedAt": snapshot["generatedAt"],
            "strategies": len(snapshot["strategies"]),
            "trades": len(snapshot["trades"]),
            "closed": sum(s["closed"] for s in snapshot["strategies"]),
            "open": sum(s["open"] for s in snapshot["strategies"]),
        }))
    else:
        print(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"strong-export: {exc}", file=sys.stderr)
        raise SystemExit(1)
