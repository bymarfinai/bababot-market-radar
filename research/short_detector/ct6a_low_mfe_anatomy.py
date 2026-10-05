from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

CT4 = [
    r for r in csv.DictReader(open(RESULTS / "ct4_trade_detail.csv"))
    if r["candidate"] == "T0075"
]
RESEARCH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))
}
FRESH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))
}

BLOCKS = [
    "Research_Discovery",
    "Research_Validation",
    "Research_Reserve",
    "Fresh_2026-10-01",
    "Fresh_2026-10-02",
    "Fresh_2026-10-03",
]

BUCKETS = [
    ("BAD_A_LT_0P30", 0.0, 0.30),
    ("BAD_B_0P30_0P50", 0.30, 0.50),
    ("GRAY_0P50_1P00", 0.50, 1.00),
    ("TARGET_GE_1P00", 1.00, float("inf")),
]


def truth(v):
    return str(v).lower() == "true"


def ff(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def mfe(row):
    if row["source"] == "research":
        return ff(RESEARCH[row["position_id"]].get("future_max_mfe_pct"))
    return ff(FRESH[row["position_id"]].get("fresh_max_mfe_pct"))


def bucket_for(x):
    for name, lo, hi in BUCKETS:
        if lo <= x < hi:
            return name
    raise ValueError(x)


def severe(row):
    return (
        truth(row["executable"])
        and not truth(row["strong"])
        and row["reason"] == "HIST_TIME_FALLBACK"
        and float(row["pnl"]) <= -2.0
    )


ROWS = []
for r in CT4:
    x = mfe(r)
    if x is None:
        continue
    q = dict(r)
    q["mfe_pct"] = x
    q["mfe_bucket"] = bucket_for(x)
    ROWS.append(q)


def stats(rows):
    ex = [r for r in rows if truth(r["executable"])]
    strong_sel = [r for r in rows if truth(r["strong"])]
    strong_ex = [r for r in ex if truth(r["strong"])]
    nt_ex = [r for r in ex if not truth(r["strong"])]
    vals = [float(r["pnl"]) for r in ex]
    return {
        "selected": len(rows),
        "executable": len(ex),
        "selected_share": len(rows) / len(ROWS) if ROWS else 0.0,
        "strong_selected": len(strong_sel),
        "strong_executable": len(strong_ex),
        "non_target_executable": len(nt_ex),
        "wins": sum(v > 0 for v in vals),
        "wr": sum(v > 0 for v in vals) / len(vals) if vals else 0.0,
        "pnl": sum(vals),
        "avg_pnl": sum(vals) / len(vals) if vals else 0.0,
        "strong_pnl": sum(float(r["pnl"]) for r in strong_ex),
        "non_target_pnl": sum(float(r["pnl"]) for r in nt_ex),
        "severe_fallback_n": sum(severe(r) for r in ex),
        "severe_fallback_pnl": sum(float(r["pnl"]) for r in ex if severe(r)),
        "reasons": dict(Counter(r["reason"] for r in ex)),
    }


summary = {
    "stage": "SHORT-CT6A",
    "status": "LOW_MFE_ANATOMY_COMPLETE",
    "contract": {
        "baseline": "CT4 +0.075% confirmation architecture",
        "protector": "V4.3 SHORT-LS4 + BE0.10",
        "mfe_usage": "research label/anatomy only; never a runtime or entry feature",
        "bucket_definition": {
            "BAD_A_LT_0P30": "MFE < 0.30%",
            "BAD_B_0P30_0P50": "0.30% <= MFE < 0.50%",
            "GRAY_0P50_1P00": "0.50% <= MFE < 1.00%",
            "TARGET_GE_1P00": "MFE >= 1.00%",
        },
    },
    "coverage": {
        "ct4_selected": len(CT4),
        "mfe_available": len(ROWS),
        "coverage": len(ROWS) / len(CT4) if CT4 else 0.0,
    },
    "overall": stats(ROWS),
    "by_bucket": {},
    "by_lane": {},
    "by_block": {},
    "by_source": {},
    "bucket_by_lane": {},
    "bucket_by_block": {},
}

for name, _, _ in BUCKETS:
    summary["by_bucket"][name] = stats([r for r in ROWS if r["mfe_bucket"] == name])

for lane in range(4):
    lane_rows = [r for r in ROWS if int(r["lane"]) == lane]
    summary["by_lane"][str(lane)] = stats(lane_rows)
    summary["bucket_by_lane"][str(lane)] = {
        name: stats([r for r in lane_rows if r["mfe_bucket"] == name])
        for name, _, _ in BUCKETS
    }

for block in BLOCKS:
    block_rows = [r for r in ROWS if r["block"] == block]
    summary["by_block"][block] = stats(block_rows)
    summary["bucket_by_block"][block] = {
        name: stats([r for r in block_rows if r["mfe_bucket"] == name])
        for name, _, _ in BUCKETS
    }

for source in ("research", "fresh"):
    summary["by_source"][source] = stats([r for r in ROWS if r["source"] == source])

bad = [r for r in ROWS if r["mfe_pct"] < 0.50]
target = [r for r in ROWS if r["mfe_pct"] >= 1.00]
summary["headline"] = {
    "low_mfe_lt_0p50": stats(bad),
    "target_mfe_ge_1p00": stats(target),
    "oracle_keep_ge_0p50": stats([r for r in ROWS if r["mfe_pct"] >= 0.50]),
    "oracle_keep_ge_1p00": stats(target),
}

detail_fields = [
    "position_id", "symbol", "source", "block", "lane",
    "mfe_pct", "mfe_bucket", "strong", "executable", "pnl", "reason",
]
with open(RESULTS / "ct6a_trade_detail.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=detail_fields)
    w.writeheader()
    for r in ROWS:
        w.writerow({k: r.get(k, "") for k in detail_fields})

lane_fields = [
    "lane", "bucket", "selected", "executable", "selected_share",
    "strong_selected", "strong_executable", "non_target_executable",
    "wr", "pnl", "avg_pnl", "strong_pnl", "non_target_pnl",
    "severe_fallback_n", "severe_fallback_pnl",
]
with open(RESULTS / "ct6a_lane_bucket.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=lane_fields)
    w.writeheader()
    for lane in range(4):
        for name, _, _ in BUCKETS:
            z = summary["bucket_by_lane"][str(lane)][name]
            w.writerow({"lane": lane, "bucket": name, **{k: z[k] for k in lane_fields if k not in ("lane", "bucket")}})

block_fields = [
    "block", "bucket", "selected", "executable", "selected_share",
    "strong_selected", "strong_executable", "non_target_executable",
    "wr", "pnl", "avg_pnl", "strong_pnl", "non_target_pnl",
    "severe_fallback_n", "severe_fallback_pnl",
]
with open(RESULTS / "ct6a_block_bucket.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=block_fields)
    w.writeheader()
    for block in BLOCKS:
        for name, _, _ in BUCKETS:
            z = summary["bucket_by_block"][block][name]
            w.writerow({"block": block, "bucket": name, **{k: z[k] for k in block_fields if k not in ("block", "bucket")}})

(RESULTS / "ct6a_summary.json").write_text(json.dumps(summary, indent=2))

print("coverage", summary["coverage"])
print("overall", summary["overall"])
print("\nBUCKETS")
for name, _, _ in BUCKETS:
    print(name, summary["by_bucket"][name])
print("\nLANE x BUCKET")
for lane in range(4):
    print("LANE", lane)
    for name, _, _ in BUCKETS:
        z = summary["bucket_by_lane"][str(lane)][name]
        print(name, {k: z[k] for k in ["selected","executable","strong_executable","pnl","severe_fallback_n","severe_fallback_pnl"]})
print("\nBLOCK x BUCKET")
for block in BLOCKS:
    print("BLOCK", block)
    for name, _, _ in BUCKETS:
        z = summary["bucket_by_block"][block][name]
        print(name, {k: z[k] for k in ["selected","executable","strong_executable","pnl","severe_fallback_n","severe_fallback_pnl"]})