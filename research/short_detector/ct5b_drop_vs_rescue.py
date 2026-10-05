from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"
CT4 = [r for r in csv.DictReader(open(RESULTS / "ct4_trade_detail.csv")) if r["candidate"] == "T0075"]
SHIFT = list(csv.DictReader(open(RESULTS / "ct5a_shift_detail.csv")))
TM = {r["position_id"]: r for r in csv.DictReader(open("/opt/core-app/data/wd5h4a_temporal_features.csv"))}
FRESH = {r["meta_position_id"]: r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}

BLOCKS = [
    "Research_Discovery",
    "Research_Validation",
    "Research_Reserve",
    "Fresh_2026-10-01",
    "Fresh_2026-10-02",
    "Fresh_2026-10-03",
]


def truth(v):
    return str(v).lower() == "true"


def ff(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def feature_row(src, pid):
    return TM[pid] if src == "research" else FRESH[pid]


def severe(row):
    return (
        truth(row["executable"])
        and not truth(row["strong"])
        and row["reason"] == "HIST_TIME_FALLBACK"
        and float(row["pnl"]) <= -2.0
    )


BASE = {r["position_id"]: r for r in CT4}
T23 = [r for r in SHIFT if r["transition"] == "T2_TO_T3"]
T3_SWITCH = [
    r for r in SHIFT
    if r["transition"] == "T3_SOURCE_SWITCH"
    and r["base_source"] == "LANE1_TEMPORAL"
    and r["new_source"] == "ALT_T3"
]

t23_delta = {}
for r in T23:
    fr = feature_row(r["source"], r["position_id"])
    t2 = ff(fr.get("t2_confirm_side_return_pct"))
    t3 = ff(fr.get("t3_confirm_side_return_pct"))
    t23_delta[r["position_id"]] = None if t2 is None or t3 is None else t3 - t2

switch_ids = {r["position_id"] for r in T3_SWITCH}
t23_ids = {r["position_id"] for r in T23}


def delta_drop(threshold):
    return {
        pid for pid, value in t23_delta.items()
        if value is not None and value < threshold
    }


CANDIDATES = {
    "BASE_0075": set(),
    "BLOCK_T3_ALT_BACKDOOR": switch_ids,
    "T23_DELTA_0050": delta_drop(0.050),
    "T23_DELTA_0075": delta_drop(0.075),
    "T23_DELTA_0100": delta_drop(0.100),
    "T23_DELTA_0125": delta_drop(0.125),
    "T23_DELTA_0150": delta_drop(0.150),
    "PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075": switch_ids | delta_drop(0.075),
    "DROP_ALL_T23": t23_ids,
    "STRESS_BLOCK_ALT_PLUS_DROP_ALL_T23": switch_ids | t23_ids,
}


def met(rows):
    ex = [r for r in rows if truth(r["executable"])]
    vals = [float(r["pnl"]) for r in ex]
    return {
        "selected": len(rows),
        "executable": len(ex),
        "strong_selected": sum(truth(r["strong"]) for r in rows),
        "strong_executable": sum(truth(r["strong"]) for r in ex),
        "non_target_executable": sum(not truth(r["strong"]) for r in ex),
        "wins": sum(v > 0 for v in vals),
        "wr": sum(v > 0 for v in vals) / len(vals) if vals else 0.0,
        "pnl": sum(vals),
        "strong_pnl": sum(float(r["pnl"]) for r in ex if truth(r["strong"])),
        "non_target_pnl": sum(float(r["pnl"]) for r in ex if not truth(r["strong"])),
        "severe_fallback_n": sum(severe(r) for r in ex),
        "severe_fallback_pnl": sum(float(r["pnl"]) for r in ex if severe(r)),
        "reasons": dict(Counter(r["reason"] for r in ex)),
    }


def evaluate(name, drop):
    kept = [r for r in CT4 if r["position_id"] not in drop]
    dropped = [r for r in CT4 if r["position_id"] in drop]
    z = {
        "name": name,
        "drop_ids": sorted(drop),
        "overall": met(kept),
        "dropped": met(dropped),
        "research": met([r for r in kept if r["source"] == "research"]),
        "fresh": met([r for r in kept if r["source"] == "fresh"]),
        "blocks": {},
        "lanes": {},
    }
    for b in BLOCKS:
        q = [r for r in kept if r["block"] == b]
        d = [r for r in dropped if r["block"] == b]
        z["blocks"][b] = {"kept": met(q), "dropped": met(d)}
    for lane in range(4):
        q = [r for r in kept if int(r["lane"]) == lane]
        d = [r for r in dropped if int(r["lane"]) == lane]
        z["lanes"][str(lane)] = {"kept": met(q), "dropped": met(d)}
    return z


summary = {
    "stage": "SHORT-CT5B",
    "status": "DROP_VS_RESCUE_ARCHITECTURE_COMPLETE",
    "frozen": {
        "confirmation_floor_pct": 0.075,
        "fast_t0": "S10D frozen",
        "lane0_recovery": "S10C frozen",
        "profit_protector": "V4.3 SHORT-LS4 + BE0.10 frozen",
        "execution_contract": "CT4 exact execution-realistic replay",
    },
    "gate_definition": {
        "primary_t23_rescue": "RESCUE T2->T3 only if t3_confirm_side_return_pct - t2_confirm_side_return_pct >= 0.075 percentage points",
        "alt_backdoor_block": "DROP T3 source-switch when stricter Lane-1 confirmation fails and source changes LANE1_TEMPORAL -> ALT_T3",
    },
    "cohorts": {
        "t2_to_t3_n": len(T23),
        "t2_to_t3_strong": sum(truth(r["strong"]) for r in T23),
        "t3_source_switch_n": len(T3_SWITCH),
        "t3_source_switch_strong": sum(truth(r["strong"]) for r in T3_SWITCH),
    },
    "candidates": {},
}

for name, drop in CANDIDATES.items():
    summary["candidates"][name] = evaluate(name, drop)

base = summary["candidates"]["BASE_0075"]
for name, z in summary["candidates"].items():
    for scope in ("overall", "research", "fresh"):
        z[scope]["delta_pnl_vs_base"] = z[scope]["pnl"] - base[scope]["pnl"]
        z[scope]["strong_exec_retention_vs_base"] = (
            z[scope]["strong_executable"] / base[scope]["strong_executable"]
            if base[scope]["strong_executable"] else 0.0
        )
    for b in BLOCKS:
        z["blocks"][b]["delta_pnl_vs_base"] = (
            z["blocks"][b]["kept"]["pnl"] - base["blocks"][b]["kept"]["pnl"]
        )

detail = []
for r in T23:
    pid = r["position_id"]
    fr = feature_row(r["source"], pid)
    detail.append({
        "position_id": pid,
        "symbol": r["symbol"],
        "source": r["source"],
        "block": r["block"],
        "transition": r["transition"],
        "strong": r["strong"],
        "new_executable": r["new_executable"],
        "new_pnl": r["new_pnl"],
        "new_reason": r["new_reason"],
        "t2_confirm_side_return_pct": fr.get("t2_confirm_side_return_pct", ""),
        "t3_confirm_side_return_pct": fr.get("t3_confirm_side_return_pct", ""),
        "t3_minus_t2_confirmation_pp": t23_delta[pid],
        "primary_drop": pid in CANDIDATES["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"],
    })
for r in T3_SWITCH:
    pid = r["position_id"]
    detail.append({
        "position_id": pid,
        "symbol": r["symbol"],
        "source": r["source"],
        "block": r["block"],
        "transition": r["transition"],
        "strong": r["strong"],
        "new_executable": r["new_executable"],
        "new_pnl": r["new_pnl"],
        "new_reason": r["new_reason"],
        "t2_confirm_side_return_pct": "",
        "t3_confirm_side_return_pct": "",
        "t3_minus_t2_confirmation_pp": "",
        "primary_drop": pid in CANDIDATES["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"],
    })

(RESULTS / "ct5b_summary.json").write_text(json.dumps(summary, indent=2))
with open(RESULTS / "ct5b_trade_detail.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(detail[0]))
    w.writeheader()
    w.writerows(detail)

print("BASE", base["research"]["pnl"], base["fresh"]["pnl"], base["overall"]["pnl"])
for name in [
    "BLOCK_T3_ALT_BACKDOOR",
    "T23_DELTA_0050",
    "T23_DELTA_0075",
    "T23_DELTA_0100",
    "PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075",
    "DROP_ALL_T23",
    "STRESS_BLOCK_ALT_PLUS_DROP_ALL_T23",
]:
    z = summary["candidates"][name]
    print(
        name,
        "R", round(z["research"]["pnl"], 4), "d", round(z["research"]["delta_pnl_vs_base"], 4),
        "F", round(z["fresh"]["pnl"], 4), "d", round(z["fresh"]["delta_pnl_vs_base"], 4),
        "ALL", round(z["overall"]["pnl"], 4), "d", round(z["overall"]["delta_pnl_vs_base"], 4),
        "dropStrong", z["dropped"]["strong_selected"],
        "dropSevere", z["dropped"]["severe_fallback_n"],
    )