from __future__ import annotations
import csv,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def truth(v):return str(v).strip().lower() in {"true","1","1.0","yes"}
def ff(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def percentile(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w

D={r["position_id"]:r for r in csv.DictReader(open(RES/"ct6a_trade_detail.csv"))}
B={r["position_id"]:r for r in csv.DictReader(open(RES/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
A={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7b_trade_membership.csv"))}
ct5=set(json.load(open(RES/"ct5b_summary.json"))["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(RES/"ct6c_veto_trade_detail.csv"))}
ct7={r["position_id"] for r in csv.DictReader(open(RES/"ct7c_trade_detail.csv"))}
q95={r["position_id"] for r in csv.DictReader(open(RES/"sa2_candidate_trade_detail.csv")) if truth(r["Q95_AGGRESSIVE"])}
rescue={r["position_id"]:r for r in csv.DictReader(open(RES/"sa3_rescue_trade_detail.csv"))}

R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}
def raw(pid):return R[pid] if D[pid]["source"]=="research" else F[pid]

def outside_old(pid):
    a=A[pid]
    return not any(truth(a[k]) for k in (
        "A1_LOW_DISPLACEMENT",
        "A2_WEAK_RELATIVE_EXPANSION",
        "A3_LOW_ENERGY_RESIDUAL",
    ))

hard=ct5|ct6
negative=ct7|q95
final_selected=(set(B)-hard-negative)|set(rescue)

# Exact SA3 executable state.
final={}
for pid,b in B.items():
    if pid in hard:continue
    if pid in negative:
        if pid not in rescue:continue
        final[pid]={"pnl":float(rescue[pid]["pnl"]),"reason":rescue[pid]["reason"]}
    elif truth(b["executable"]):
        final[pid]={"pnl":float(b["pnl"]),"reason":b["reason"]}

U=[D[pid] for pid in final_selected if outside_old(pid)]
BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]

# B1: broad 30m proximity stall.
discovery_target=[
    q for q in U
    if q["block"]=="Research_Discovery" and q["mfe_bucket"]=="TARGET_GE_1P00"
]
B1_THRESHOLD=percentile([
    ff(raw(q["position_id"]).get("f_micro_distance_selected_extreme_30m"))
    for q in discovery_target
],.45)
b1={
    q["position_id"] for q in U
    if ff(raw(q["position_id"]).get("f_micro_distance_selected_extreme_30m")) is not None
    and ff(raw(q["position_id"]).get("f_micro_distance_selected_extreme_30m"))<=B1_THRESHOLD
}

# B2: conditional family only among B1 survivors.
U2=[q for q in U if q["position_id"] not in b1]
discovery_target_2=[
    q for q in U2
    if q["block"]=="Research_Discovery" and q["mfe_bucket"]=="TARGET_GE_1P00"
]
B2_FEATURES=[
    "f_new_overheat_pressure",
    "f_gate_price_drift_pct",
    "f_gate_side_ret_3m_pct",
]
B2_THRESHOLDS={
    k:percentile([ff(raw(q["position_id"]).get(k)) for q in discovery_target_2],.50)
    for k in B2_FEATURES
}
b2={
    q["position_id"] for q in U2
    if sum(
        ff(raw(q["position_id"]).get(k)) is not None
        and ff(raw(q["position_id"]).get(k))<=B2_THRESHOLDS[k]
        for k in B2_FEATURES
    )>=2
}
union=b1|b2

def selected_metrics(rows,ids):
    rows=list(rows);ids=set(ids)
    z=[q for q in rows if q["position_id"] in ids]
    bad=[q for q in rows if q["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
    tar=[q for q in rows if q["mfe_bucket"]=="TARGET_GE_1P00"]
    db=[q for q in z if q["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
    dt=[q for q in z if q["mfe_bucket"]=="TARGET_GE_1P00"]
    br=len(db)/len(bad) if bad else 0
    th=len(dt)/len(tar) if tar else 0
    return {
      "selected":len(z),
      "bad":len(db),"bad_recall":br,
      "gray":sum(q["mfe_bucket"]=="GRAY_0P50_1P00" for q in z),
      "target":len(dt),"target_hit_rate":th,
      "bad_recall_minus_target_hit":br-th,
      "strong_selected":sum(truth(q["strong"]) for q in z),
    }

def exact_metrics(ids):
    ids=set(ids)&set(final)
    vals=[final[i] for i in ids]
    return {
      "executable":len(ids),
      "wins":sum(x["pnl"]>0 for x in vals),
      "pnl":sum(x["pnl"] for x in vals),
      "bad_executable":sum(D[i]["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50") for i in ids),
      "bad_pnl":sum(final[i]["pnl"] for i in ids if D[i]["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")),
      "gray_executable":sum(D[i]["mfe_bucket"]=="GRAY_0P50_1P00" for i in ids),
      "gray_pnl":sum(final[i]["pnl"] for i in ids if D[i]["mfe_bucket"]=="GRAY_0P50_1P00"),
      "target_executable":sum(D[i]["mfe_bucket"]=="TARGET_GE_1P00" for i in ids),
      "target_pnl":sum(final[i]["pnl"] for i in ids if D[i]["mfe_bucket"]=="TARGET_GE_1P00"),
      "strong_executable":sum(truth(B[i]["strong"]) for i in ids),
      "fallback":sum(final[i]["reason"]=="HIST_TIME_FALLBACK" for i in ids),
      "fallback_pnl":sum(final[i]["pnl"] for i in ids if final[i]["reason"]=="HIST_TIME_FALLBACK"),
    }

outside_bad_selected={
    q["position_id"] for q in U
    if q["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")
}
outside_target_selected={q["position_id"] for q in U if q["mfe_bucket"]=="TARGET_GE_1P00"}
outside_strong_selected={q["position_id"] for q in U if truth(q["strong"])}
outside_bad_exec={
    i for i in final if outside_old(i)
    and D[i]["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")
}
outside_target_exec={i for i in final if outside_old(i) and D[i]["mfe_bucket"]=="TARGET_GE_1P00"}

summary={
 "stage":"SHORT-SA5B",
 "status":"OUTSIDE_ALL_FAILURE_FAMILY_DISCOVERY_PASS_NOT_VETO_READY",
 "runtime_change":False,
 "contract":{
   "population":"SA3 final-selected trades outside frozen A1/A2/A3",
   "t_features_used":False,
   "future_mfe_use":"research label only",
   "pnl_use":"evaluation only",
   "threshold_fit":"Research Discovery TARGET quantiles only",
   "old_direct_basis_reused":False,
 },
 "universe":{
   "selected":len(U),
   "bad_selected":len(outside_bad_selected),
   "target_selected":len(outside_target_selected),
   "gray_selected":sum(q["mfe_bucket"]=="GRAY_0P50_1P00" for q in U),
   "strong_selected":len(outside_strong_selected),
   "bad_executable":len(outside_bad_exec),
   "bad_executable_pnl":sum(final[i]["pnl"] for i in outside_bad_exec),
 },
 "families":{
   "B1_30M_PROXIMITY_STALL":{
     "definition":"f_micro_distance_selected_extreme_30m <= Research Discovery outside-old TARGET Q45",
     "threshold":B1_THRESHOLD,
     "selected":selected_metrics(U,b1),
     "exact":exact_metrics(b1),
     "by_block":{b:selected_metrics([q for q in U if q["block"]==b],b1) for b in BLOCKS},
   },
   "B2_WEAK_PRESSURE_DRIFT_STALL":{
     "scope":"B1 survivors only",
     "definition":"at least 2 of 3 low: overheat pressure, price drift, 3m side return",
     "percentile":0.50,
     "thresholds":B2_THRESHOLDS,
     "selected":selected_metrics(U2,b2),
     "exact":exact_metrics(b2),
     "by_block":{b:selected_metrics([q for q in U2 if q["block"]==b],b2) for b in BLOCKS},
   },
 },
 "union":{
   "selected":selected_metrics(U,union),
   "exact":exact_metrics(union),
   "outside_bad_selected_coverage":len(union&outside_bad_selected)/len(outside_bad_selected),
   "outside_bad_exec_coverage":len(union&outside_bad_exec)/len(outside_bad_exec),
   "outside_bad_exec_pnl_covered":sum(final[i]["pnl"] for i in union&outside_bad_exec),
   "outside_bad_exec_pnl_total":sum(final[i]["pnl"] for i in outside_bad_exec),
   "outside_target_selected_hit":len(union&outside_target_selected)/len(outside_target_selected),
   "outside_strong_selected_hit":len(union&outside_strong_selected)/len(outside_strong_selected),
   "by_block":{b:selected_metrics([q for q in U if q["block"]==b],union) for b in BLOCKS},
 },
}
uncovered=outside_bad_exec-union
summary["uncovered_bad_exec"]={
 "count":len(uncovered),
 "pnl":sum(final[i]["pnl"] for i in uncovered),
 "fallback":sum(final[i]["reason"]=="HIST_TIME_FALLBACK" for i in uncovered),
 "fallback_pnl":sum(final[i]["pnl"] for i in uncovered if final[i]["reason"]=="HIST_TIME_FALLBACK"),
 "symbols":[B[i]["symbol"] for i in sorted(uncovered)],
}

# Discovery assertions.
assert abs(B1_THRESHOLD-0.2502502502502574)<1e-12
assert len(outside_bad_selected)==110
assert len(outside_bad_exec)==97
assert len(union&outside_bad_selected)==100
assert len(union&outside_bad_exec)==88
assert summary["union"]["selected"]["bad_recall_minus_target_hit"]>0
assert all(summary["families"]["B1_30M_PROXIMITY_STALL"]["by_block"][b]["bad_recall_minus_target_hit"]>0 for b in BLOCKS)

(RES/"sa5b_summary.json").write_text(json.dumps(summary,indent=2))

with open(RES/"sa5b_family_membership.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","mfe_bucket","strong","B1_30M_PROXIMITY_STALL","B2_WEAK_PRESSURE_DRIFT_STALL","family_union","executable","pnl","reason"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for q in U:
        pid=q["position_id"]
        w.writerow({
          "position_id":pid,"symbol":B[pid]["symbol"],"source":q["source"],"block":q["block"],"mfe_bucket":q["mfe_bucket"],"strong":q["strong"],
          "B1_30M_PROXIMITY_STALL":pid in b1,
          "B2_WEAK_PRESSURE_DRIFT_STALL":pid in b2,
          "family_union":pid in union,
          "executable":pid in final,
          "pnl":final[pid]["pnl"] if pid in final else "",
          "reason":final[pid]["reason"] if pid in final else "",
        })

print("B1 TH",B1_THRESHOLD)
print("B2 TH",B2_THRESHOLDS)
print("UNIVERSE",summary["universe"])
print("B1",summary["families"]["B1_30M_PROXIMITY_STALL"]["selected"],summary["families"]["B1_30M_PROXIMITY_STALL"]["exact"])
print("B2",summary["families"]["B2_WEAK_PRESSURE_DRIFT_STALL"]["selected"],summary["families"]["B2_WEAK_PRESSURE_DRIFT_STALL"]["exact"])
print("UNION",summary["union"])
print("UNCOVERED",summary["uncovered_bad_exec"])