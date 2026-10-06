from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"research"/"short_detector"/"results"
truth=lambda v:str(v).lower()=="true"

base={r["position_id"]:r for r in csv.DictReader(open(R/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
labels={r["position_id"]:r for r in csv.DictReader(open(R/"ct6a_trade_detail.csv"))}
arch={r["position_id"]:r for r in csv.DictReader(open(R/"ct7b_trade_membership.csv"))}
ct5=set(json.load(open(R/"ct5b_summary.json"))["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(R/"ct6c_veto_trade_detail.csv"))}
ct7={r["position_id"] for r in csv.DictReader(open(R/"ct7c_trade_detail.csv"))}
rescue={r["position_id"]:r for r in csv.DictReader(open(R/"ct7d_rescue_detail.csv")) if truth(r["executable"])}
drop=ct5|ct6|ct7

def broad(pid):
    a=arch[pid]
    return any(a[k]=="True" for k in ("A1_LOW_DISPLACEMENT","A2_WEAK_RELATIVE_EXPANSION","A3_LOW_ENERGY_RESIDUAL"))

rows=[]
for pid,b in base.items():
    if pid in drop and pid not in rescue:
        continue
    cur=rescue.get(pid)
    executable=cur["executable"] if cur else b["executable"]
    if not truth(executable):
        continue
    pnl=float(cur["pnl"] if cur else b["pnl"])
    reason=cur["reason"] if cur else b["reason"]
    rows.append({
        "position_id":pid,"symbol":b["symbol"],"source":b["source"],"block":b["block"],"lane":int(b["lane"]),
        "strong":truth(b["strong"]),"pnl":pnl,"reason":reason,
        "mfe_bucket":labels[pid]["mfe_bucket"],"mfe_pct":float(labels[pid]["mfe_pct"]),
        "inside_broad":broad(pid),
    })

bad=lambda r:r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")
gray=lambda r:r["mfe_bucket"]=="GRAY_0P50_1P00"
target=lambda r:r["mfe_bucket"]=="TARGET_GE_1P00"

def m(q):
    q=list(q)
    return {"executable":len(q),"wins":sum(x["pnl"]>0 for x in q),"strong":sum(x["strong"] for x in q),"pnl":sum(x["pnl"] for x in q)}

summary={
 "stage":"SHORT-CT7E",
 "headline":{"executable":len(rows),"wins":sum(r["pnl"]>0 for r in rows),"strong_executable":sum(r["strong"] for r in rows),"pnl":sum(r["pnl"] for r in rows)},
 "mfe":{
   "BAD_A":m(r for r in rows if r["mfe_bucket"]=="BAD_A_LT_0P30"),
   "BAD_B":m(r for r in rows if r["mfe_bucket"]=="BAD_B_0P30_0P50"),
   "BAD_LT_0P50":m(r for r in rows if bad(r)),
   "GRAY":m(r for r in rows if gray(r)),
   "TARGET":m(r for r in rows if target(r)),
 },
 "reason":{k:m(r for r in rows if r["reason"]==k) for k in sorted(set(r["reason"] for r in rows))},
 "bad_split":{
   "inside_broad":m(r for r in rows if bad(r) and r["inside_broad"]),
   "outside_all":m(r for r in rows if bad(r) and not r["inside_broad"]),
   "fallback_inside_broad":m(r for r in rows if bad(r) and r["inside_broad"] and r["reason"]=="HIST_TIME_FALLBACK"),
   "fallback_outside_all":m(r for r in rows if bad(r) and not r["inside_broad"] and r["reason"]=="HIST_TIME_FALLBACK"),
 },
 "gray_fallback":{
   "inside_broad":m(r for r in rows if gray(r) and r["inside_broad"] and r["reason"]=="HIST_TIME_FALLBACK"),
   "outside_all":m(r for r in rows if gray(r) and not r["inside_broad"] and r["reason"]=="HIST_TIME_FALLBACK"),
 },
}

assert summary["headline"]["executable"]==794
assert summary["headline"]["wins"]==292
assert summary["headline"]["strong_executable"]==238
assert abs(summary["headline"]["pnl"]+136.316975469426)<1e-9
print(json.dumps(summary,indent=2))
