from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import psycopg2.extras

from market_radar.persistence import _postgres_connect

VERSION = "lq3gv3-velocity-action-replay-v1"
EXPECTED = 209
T60_MS = 60_000
T120_MS = 120_000

EARLY60_ETA_MAX = 1478.8772362732022
EARLY60_T_MFE_MIN = 33.321
STRONG120_V_MIN = 0.0008457198799203628
STRONG120_ETA_MAX = 1383.324562761091

def f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))

def load_positions(ids: list[str]) -> dict[str, dict[str, Any]]:
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """select position_id,symbol,side,opened_at_ms,closed_at_ms,
                          entry_price,exit_price,realized_pnl,raw_json
                   from positions
                   where position_id=any(%s)""",
                (ids,),
            )
            rows = [dict(x) for x in cur.fetchall()]
    out = {str(x["position_id"]): x for x in rows}
    if len(out) != len(ids):
        raise RuntimeError(f"position coverage {len(out)}/{len(ids)}")
    return out

def raw_obj(p: dict[str, Any]) -> dict[str, Any]:
    raw = p.get("raw_json")
    if isinstance(raw, dict):
        return raw
    return json.loads(raw or "{}")

def economics(p: dict[str, Any]) -> dict[str, float]:
    raw = raw_obj(p)
    qty = float(raw.get("initial_quantity") or 0.0)
    entry_fee = float(raw.get("entry_fee_total") or 0.0)
    fee_rate = float(raw.get("fee_rate") or 0.00075)
    slippage_bps = float(raw.get("slippage_bps") or 2.0)
    if qty <= 0:
        raise RuntimeError(f"invalid qty {p['position_id']}")
    return {
        "qty": qty,
        "entry_fee": entry_fee,
        "fee_rate": fee_rate,
        "slippage_bps": slippage_bps,
        "notional": qty * float(p["entry_price"]),
    }

def exit_net_from_original_entry(p: dict[str, Any], market_px: float) -> tuple[float, float]:
    eco = economics(p)
    side = str(p["side"]).upper()
    entry = float(p["entry_price"])
    slip = eco["slippage_bps"] / 10_000.0
    exit_fill = market_px * (1.0 - slip) if side == "LONG" else market_px * (1.0 + slip)
    gross = eco["qty"] * (exit_fill - entry) if side == "LONG" else eco["qty"] * (entry - exit_fill)
    exit_fee = eco["qty"] * exit_fill * eco["fee_rate"]
    return gross - eco["entry_fee"] - exit_fee, exit_fill

def delayed_trade_net(
    p: dict[str, Any],
    entry_market_px: float,
    exit_market_px: float,
) -> tuple[float, float, float]:
    eco = economics(p)
    side = str(p["side"]).upper()
    slip = eco["slippage_bps"] / 10_000.0
    delayed_entry_fill = entry_market_px * (1.0 + slip) if side == "LONG" else entry_market_px * (1.0 - slip)
    delayed_exit_fill = exit_market_px * (1.0 - slip) if side == "LONG" else exit_market_px * (1.0 + slip)
    qty = eco["notional"] / delayed_entry_fill
    entry_fee = qty * delayed_entry_fill * eco["fee_rate"]
    exit_fee = qty * delayed_exit_fill * eco["fee_rate"]
    gross = qty * (delayed_exit_fill - delayed_entry_fill) if side == "LONG" else qty * (delayed_entry_fill - delayed_exit_fill)
    return gross - entry_fee - exit_fee, delayed_entry_fill, delayed_exit_fill

def first_at_or_after(path: list[tuple[int, float]], ts: int) -> tuple[int, float] | None:
    for t, px in path:
        if t >= ts:
            return t, px
    return None

def last_at_or_before(path: list[tuple[int, float]], ts: int) -> tuple[int, float] | None:
    best = None
    for t, px in path:
        if t > ts:
            break
        best = (t, px)
    return best

def early60(r: dict[str, str]) -> bool:
    eta = f(r["eta_nearest_supply_distance_pct_60s"])
    tm = f(r["t_mfe_60s"])
    return eta is not None and tm is not None and eta <= EARLY60_ETA_MAX and tm >= EARLY60_T_MFE_MIN

def strong120(r: dict[str, str]) -> bool:
    v = f(r["v_0_120s_pps"])
    eta = f(r["eta_nearest_supply_distance_pct_60s"])
    return v is not None and eta is not None and v >= STRONG120_V_MIN and eta <= STRONG120_ETA_MAX

def metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    vals = [float(r[key]) for r in rows]
    wins = sum(v > 0 for v in vals)
    c = Counter(str(r["clean_label"]) for r in rows)
    return {
        "n": len(rows),
        "wins": wins,
        "wr_pct": round(100.0 * wins / len(rows), 2),
        "net_pnl": round(sum(vals), 2),
        "avg_pnl": round(sum(vals) / len(vals), 4),
        "correct_runner": c["CORRECT_RUNNER"],
        "recovered": c["RECOVERED_DRAWDOWN"],
        "rtf": c["RIGHT_THEN_FAILURE"],
        "true_wrong": c["TRUE_WRONG_DIRECTION"],
        "stall": c["STALL_NO_EDGE"],
    }

def split_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out = {}
    for sp in ("TRAIN", "VALIDATION", "RESERVE"):
        out[sp] = metrics([r for r in rows if r["chrono_split"] == sp], key)
    out["ALL"] = metrics(rows, key)
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", default="research/liquidity_location/results/lq3gv2_trade_level.csv")
    ap.add_argument("--cache", default="/app/data/lq3f_open_lane_raw_paths.json.gz")
    ap.add_argument("--out", default="research/liquidity_location/results")
    args = ap.parse_args()

    base = load_csv(Path(args.v2))
    if len(base) != EXPECTED:
        raise RuntimeError(f"expected {EXPECTED}, got {len(base)}")
    ids = [r["position_id"] for r in base]
    pos = load_positions(ids)

    with gzip.open(args.cache, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    paths = {
        pid: [(int(ts), float(px)) for ts, px in rows]
        for pid, rows in payload["paths"].items()
    }

    rows: list[dict[str, Any]] = []
    for r in base:
        pid = r["position_id"]
        p = pos[pid]
        path = paths.get(pid) or []
        opened = int(p["opened_at_ms"])
        closed = int(p["closed_at_ms"])
        duration_ms = closed - opened
        alive60 = duration_ms >= T60_MS
        alive120 = duration_ms >= T120_MS

        e60 = early60(r) and alive60
        s120 = strong120(r) and alive120
        eligible_decay = e60 and alive120 and not s120
        premature_close_before_120 = e60 and not alive120

        hist_pnl = float(p.get("realized_pnl") or 0.0)
        action_pnl = hist_pnl
        profit_lock_pnl = hist_pnl
        loss_cut_pnl = hist_pnl
        action_reason = "HISTORICAL_CONTINUE"
        profit_lock_reason = "HISTORICAL_CONTINUE"
        loss_cut_reason = "HISTORICAL_CONTINUE"
        t120_market = None
        t120_fill = None
        t120_ts = None
        t120_candidate_pnl = None

        if eligible_decay:
            hit = first_at_or_after(path, opened + T120_MS)
            if hit is None:
                raise RuntimeError(f"missing T120 market trade {pid}")
            t120_ts, t120_market = hit
            t120_candidate_pnl, t120_fill = exit_net_from_original_entry(p, t120_market)

            action_pnl = t120_candidate_pnl
            action_reason = "CLOSE_ALL_DECAY_AT_T120"

            if t120_candidate_pnl > 0:
                profit_lock_pnl = t120_candidate_pnl
                profit_lock_reason = "BANK_POSITIVE_DECAY_AT_T120"

            if t120_candidate_pnl <= 0:
                loss_cut_pnl = t120_candidate_pnl
                loss_cut_reason = "CUT_NEGATIVE_DECAY_AT_T120"

        # Secondary: delayed-entry research.
        delayed60_pnl = None
        delayed120_pnl = None
        delayed60_entry_px = None
        delayed120_entry_px = None
        final_market = last_at_or_before(path, closed)
        if final_market is None:
            raise RuntimeError(f"missing final market {pid}")

        if e60:
            ent60 = first_at_or_after(path, opened + T60_MS)
            if ent60 is not None and ent60[0] <= closed:
                delayed60_pnl, delayed60_entry_px, _ = delayed_trade_net(p, ent60[1], final_market[1])

        if s120:
            ent120 = first_at_or_after(path, opened + T120_MS)
            if ent120 is not None and ent120[0] <= closed:
                delayed120_pnl, delayed120_entry_px, _ = delayed_trade_net(p, ent120[1], final_market[1])

        rows.append({
            "position_id": pid,
            "symbol": r["symbol"],
            "chrono_split": r["chrono_split"],
            "clean_label": r["clean_label"],
            "duration_s": round(duration_ms / 1000.0, 3),
            "alive60": alive60,
            "alive120": alive120,
            "early60_confirm": e60,
            "strong120_confirm": s120,
            "eligible_decay120": eligible_decay,
            "early60_closed_before_120": premature_close_before_120,
            "historical_pnl": hist_pnl,
            "action_pnl": action_pnl,
            "action_delta_pnl": action_pnl - hist_pnl,
            "action_reason": action_reason,
            "profit_lock_pnl": profit_lock_pnl,
            "profit_lock_delta_pnl": profit_lock_pnl - hist_pnl,
            "profit_lock_reason": profit_lock_reason,
            "loss_cut_pnl": loss_cut_pnl,
            "loss_cut_delta_pnl": loss_cut_pnl - hist_pnl,
            "loss_cut_reason": loss_cut_reason,
            "t120_candidate_pnl": t120_candidate_pnl,
            "t120_market_px": t120_market,
            "t120_exit_fill": t120_fill,
            "t120_exit_ts": t120_ts,
            "delayed60_pnl": delayed60_pnl,
            "delayed60_entry_fill": delayed60_entry_px,
            "delayed120_pnl": delayed120_pnl,
            "delayed120_entry_fill": delayed120_entry_px,
        })

    decay = [r for r in rows if r["eligible_decay120"]]
    both = [r for r in rows if r["early60_confirm"] and r["strong120_confirm"]]
    pre120 = [r for r in rows if r["early60_closed_before_120"]]

    delayed60 = [r for r in rows if r["delayed60_pnl"] is not None]
    delayed120 = [r for r in rows if r["delayed120_pnl"] is not None]

    # Compare historical vs action at full universe and actionable cohorts.
    summary = {
        "version": VERSION,
        "contract": {
            "rows": len(rows),
            "source": "authoritative LQ3GV2 states + Binance Vision aggTrades + position economics",
            "causality": [
                "EARLY60 requires position alive at T+60",
                "STRONG120 requires position alive at T+120",
                "DECAY120 is defined only when EARLY60 is true and position survives to T+120 but STRONG120 is false",
                "T+120 exit uses first aggTrade at or after checkpoint, then original position slippage/fees",
                "trades already closed before T+120 are never labeled DECAY120",
            ],
            "action_policy": "original entry unchanged; close only eligible DECAY120 at T+120; all others continue historical lifecycle",
            "delayed_entry_secondary": "enter only confirmed lanes at actual T+60/T+120 market; same initial notional; historical close time; fees/slippage applied",
            "production_authority": "NONE",
        },
        "eligibility_audit": {
            "open_lane_n": len(rows),
            "alive60_n": sum(r["alive60"] for r in rows),
            "alive120_n": sum(r["alive120"] for r in rows),
            "early60_n": sum(r["early60_confirm"] for r in rows),
            "early60_alive120_n": sum(r["early60_confirm"] and r["alive120"] for r in rows),
            "early60_closed_before120_n": len(pre120),
            "strong120_n": sum(r["strong120_confirm"] for r in rows),
            "eligible_decay120_n": len(decay),
            "early60_to_strong120_n": len(both),
        },
        "historical_full": split_metrics(rows, "historical_pnl"),
        "action_full": split_metrics(rows, "action_pnl"),
        "profit_lock_full": split_metrics(rows, "profit_lock_pnl"),
        "loss_cut_full": split_metrics(rows, "loss_cut_pnl"),
        "decay120_historical": split_metrics(decay, "historical_pnl"),
        "decay120_action": split_metrics(decay, "action_pnl"),
        "decay120_profit_lock": split_metrics(decay, "profit_lock_pnl"),
        "decay120_loss_cut": split_metrics(decay, "loss_cut_pnl"),
        "strong_path_historical": split_metrics(both, "historical_pnl"),
        "closed_before120_early60": split_metrics(pre120, "historical_pnl"),
        "delayed60": split_metrics(delayed60, "delayed60_pnl"),
        "delayed120_strong": split_metrics(delayed120, "delayed120_pnl"),
    }

    hist_all = summary["historical_full"]["ALL"]
    act_all = summary["action_full"]["ALL"]
    dec_h = summary["decay120_historical"]["ALL"]
    dec_a = summary["decay120_action"]["ALL"]
    pl_all = summary["profit_lock_full"]["ALL"]
    lc_all = summary["loss_cut_full"]["ALL"]
    dec_pl = summary["decay120_profit_lock"]["ALL"]
    dec_lc = summary["decay120_loss_cut"]["ALL"]
    d60 = summary["delayed60"]["ALL"]
    d120 = summary["delayed120_strong"]["ALL"]

    summary["verdict"] = {
        "full_delta_pnl": round(act_all["net_pnl"] - hist_all["net_pnl"], 2),
        "full_delta_wins": act_all["wins"] - hist_all["wins"],
        "full_delta_wr_pp": round(act_all["wr_pct"] - hist_all["wr_pct"], 2),
        "decay_delta_pnl": round(dec_a["net_pnl"] - dec_h["net_pnl"], 2),
        "decay_delta_wins": dec_a["wins"] - dec_h["wins"],
        "profit_lock_full_delta_pnl": round(pl_all["net_pnl"] - hist_all["net_pnl"], 2),
        "profit_lock_full_delta_wins": pl_all["wins"] - hist_all["wins"],
        "profit_lock_full_delta_wr_pp": round(pl_all["wr_pct"] - hist_all["wr_pct"], 2),
        "profit_lock_decay_delta_pnl": round(dec_pl["net_pnl"] - dec_h["net_pnl"], 2),
        "profit_lock_decay_delta_wins": dec_pl["wins"] - dec_h["wins"],
        "loss_cut_full_delta_pnl": round(lc_all["net_pnl"] - hist_all["net_pnl"], 2),
        "loss_cut_full_delta_wins": lc_all["wins"] - hist_all["wins"],
        "loss_cut_full_delta_wr_pp": round(lc_all["wr_pct"] - hist_all["wr_pct"], 2),
        "loss_cut_decay_delta_pnl": round(dec_lc["net_pnl"] - dec_h["net_pnl"], 2),
        "loss_cut_decay_delta_wins": dec_lc["wins"] - dec_h["wins"],
        "delayed60_wr_pct": d60.get("wr_pct"),
        "delayed60_net_pnl": d60.get("net_pnl"),
        "delayed120_wr_pct": d120.get("wr_pct"),
        "delayed120_net_pnl": d120.get("net_pnl"),
        "production": "HOLD",
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lq3gv3_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    with (out / "lq3gv3_trade_level.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()