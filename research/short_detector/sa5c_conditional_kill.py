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
M=[r for r in csv.DictReader(open(RES/"sa5b_family_membership.csv")) if truth(r["B2_WEAK_PRESSURE_DRIFT_STALL"])]
R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}
def raw(pid):return R[pid] if D[pid]["source"]=="research" else F[pid]

SA3=json.load(open(RES/"sa3_summary.json"))
CURRENT=SA3["primary"]
CURRENT_BLOCK=SA3["block"]
CURRENT_SOURCE=SA3["source"]
CURRENT_MFE=SA3["mfe"]

# Exact current SA3 state for SA5B outside-old membership.
FINAL={
    r["position_id"]:{"pnl":float(r["pnl"]),"reason":r["reason"]}
    for r in csv.DictReader(open(RES/"sa5b_family_membership.csv"))
    if truth(r["executable"])
}
RESCUE={r["position_id"] for r in csv.DictReader(open(RES/"sa3_rescue_trade_detail.csv"))}

FEATURES=[
 ("f_micro_selected_taker_share_prev3m","HIGH"),
 ("f_f_market_dispersion_15m","LOW"),
 ("f_f_market_selected_ret_30m","LOW"),
 ("f_micro_price_flow_divergence","HIGH"),
]
TRAIN_TARGET=[
    r for r in M
    if r["block"]=="Research_Discovery" and r["mfe_bucket"]=="TARGET_GE_1P00"
]

def rule_for(p):
    th={
      k:percentile(
        [ff(raw(r["position_id"]).get(k)) for r in TRAIN_TARGET],
        p if direction=="HIGH" else 1-p
      )
      for k,direction in FEATURES
    }
    ids=set()
    for r in M:
        if all(
          ff(raw(r["position_id"]).get(k)) is not None
          and (
            ff(raw(r["position_id"]).get(k))>=th[k]
            if direction=="HIGH"
            else ff(raw(r["position_id"]).get(k))<=th[k]
          )
          for k,direction in FEATURES
        ):
            ids.add(r["position_id"])
    return th,ids

def summarize(p):
    th,ids=rule_for(p)
    rows=[r for r in M if r["position_id"] in ids]
    ex=[r for r in rows if r["position_id"] in FINAL]
    removed_pnl=sum(FINAL[r["position_id"]]["pnl"] for r in ex)
    removed_wins=sum(FINAL[r["position_id"]]["pnl"]>0 for r in ex)
    z={
      "percentile":p,"thresholds":th,
      "selected":len(rows),
      "bad_selected":sum(r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50") for r in rows),
      "gray_selected":sum(r["mfe_bucket"]=="GRAY_0P50_1P00" for r in rows),
      "target_selected":sum(r["mfe_bucket"]=="TARGET_GE_1P00" for r in rows),
      "strong_selected":sum(truth(r["strong"]) for r in rows),
      "executable":len(ex),"removed_pnl":removed_pnl,"removed_wins":removed_wins,
      "post_exec":CURRENT["exec"]-len(ex),
      "post_wins":CURRENT["wins"]-removed_wins,
      "post_wr":(CURRENT["wins"]-removed_wins)/(CURRENT["exec"]-len(ex)),
      "post_pnl":CURRENT["pnl"]-removed_pnl,
      "post_strong_exec":CURRENT["strong_exec"],
      "post_strong_retention":CURRENT["strong_retention_vs_ct4"],
      "post_target_exec":CURRENT["target_exec"],
      "post_target_retention":CURRENT["target_retention_vs_ct4"],
      "rescue_overlap":len(ids&RESCUE),
    }
    z["source"]={}
    for s in ("research","fresh"):
        q=[r for r in ex if r["source"]==s]
        rp=sum(FINAL[r["position_id"]]["pnl"] for r in q)
        z["source"][s]={"removed_exec":len(q),"removed_pnl":rp,"post_pnl":CURRENT_SOURCE[s]["pnl"]-rp}
    blocks=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]
    z["block"]={}
    for b in blocks:
        q=[r for r in ex if r["block"]==b]
        rp=sum(FINAL[r["position_id"]]["pnl"] for r in q)
        z["block"][b]={"removed_exec":len(q),"removed_pnl":rp,"post_pnl":CURRENT_BLOCK[b]["pnl"]-rp}
    z["mfe"]={}
    for lab in ("BAD_A_LT_0P30","BAD_B_0P30_0P50","GRAY_0P50_1P00","TARGET_GE_1P00"):
        q=[r for r in ex if r["mfe_bucket"]==lab]
        rp=sum(FINAL[r["position_id"]]["pnl"] for r in q)
        z["mfe"][lab]={
          "removed_exec":len(q),"removed_pnl":rp,
          "post_exec":CURRENT_MFE[lab]["exec"]-len(q),
          "post_pnl":CURRENT_MFE[lab]["pnl"]-rp,
        }
    z["_ids"]=ids
    return z

q70=summarize(.70)
q75=summarize(.75)

# Primary requirements.
assert q70["target_selected"]==0
assert q70["strong_selected"]==0
assert q70["rescue_overlap"]==0
assert q70["executable"]==11
assert q70["removed_wins"]==0
assert abs(q70["removed_pnl"]-(-12.542109828028785))<1e-10
assert q70["post_strong_retention"]>=.95
assert q70["post_target_retention"]>=.95
assert all(v["removed_pnl"]<0 for v in q70["block"].values() if v["removed_exec"]>0)

# Label-only percentile sensitivity; not used as PnL optimization.
sensitivity=[]
for pp in (.60,.65,.70,.75,.80):
    _,ii=rule_for(pp)
    rr=[r for r in M if r["position_id"] in ii]
    sensitivity.append({
      "percentile":pp,
      "selected":len(rr),
      "bad":sum(r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50") for r in rr),
      "gray":sum(r["mfe_bucket"]=="GRAY_0P50_1P00" for r in rr),
      "target":sum(r["mfe_bucket"]=="TARGET_GE_1P00" for r in rr),
      "strong":sum(truth(r["strong"]) for r in rr),
    })

summary={
 "stage":"SHORT-SA5C",
 "status":"B2_CONDITIONAL_KILL_RESEARCH_PASS_NOT_RUNTIME_READY",
 "runtime_change":False,
 "b1_result":{
   "status":"NO_SAFE_KILL_FOUND",
   "stable_conditional_features":[
     "f_f_range_climax_fade_10m",
     "f_micro_range_contraction_after_impulse",
   ],
   "finding":"No tested B1 conditional rule reached the strong/TARGET collateral guardrail.",
 },
 "b2_primary":{
   k:v for k,v in q70.items() if k!="_ids"
 },
 "b2_safety_comparator":{
   k:v for k,v in q75.items() if k!="_ids"
 },
 "threshold_sensitivity":sensitivity,
 "selection_logic":{
   "family":"B2_WEAK_PRESSURE_DRIFT_STALL only",
   "rule":"all 4 conditions true",
   "threshold_fit":"Research Discovery B2 TARGET quantiles",
   "primary_percentile":0.70,
   "why_q70":"Q65 still hits 2 TARGET/2 strong; Q70 is the first tested clean boundary with 0 TARGET/0 strong and meaningful BAD coverage; Q75 is the stricter safety comparator.",
   "pnl_used_for_threshold_selection":False,
 },
}
(RES/"sa5c_summary.json").write_text(json.dumps(summary,indent=2))

with open(RES/"sa5c_primary_trade_detail.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","mfe_bucket","strong","executable","pnl","reason","sa3_rescue_overlap"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in M:
        if r["position_id"] not in q70["_ids"]:continue
        pid=r["position_id"]
        w.writerow({
          "position_id":pid,"symbol":r["symbol"],"source":r["source"],"block":r["block"],
          "mfe_bucket":r["mfe_bucket"],"strong":r["strong"],
          "executable":pid in FINAL,"pnl":FINAL[pid]["pnl"] if pid in FINAL else "",
          "reason":FINAL[pid]["reason"] if pid in FINAL else "",
          "sa3_rescue_overlap":pid in RESCUE,
        })

with open(RES/"sa5c_comparison.csv","w",newline="") as f:
    fields=["architecture","exec","wins","wr","strong_exec","strong_retention","target_exec","target_retention","pnl"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    w.writerow({"architecture":"SA3_CURRENT","exec":CURRENT["exec"],"wins":CURRENT["wins"],"wr":CURRENT["wr"],"strong_exec":CURRENT["strong_exec"],"strong_retention":CURRENT["strong_retention_vs_ct4"],"target_exec":CURRENT["target_exec"],"target_retention":CURRENT["target_retention_vs_ct4"],"pnl":CURRENT["pnl"]})
    for name,z in (("SA5C_Q70_PRIMARY",q70),("SA5C_Q75_SAFETY",q75)):
        w.writerow({"architecture":name,"exec":z["post_exec"],"wins":z["post_wins"],"wr":z["post_wr"],"strong_exec":z["post_strong_exec"],"strong_retention":z["post_strong_retention"],"target_exec":z["post_target_exec"],"target_retention":z["post_target_retention"],"pnl":z["post_pnl"]})

print("PRIMARY",json.dumps({k:v for k,v in q70.items() if k!="_ids"},indent=2))
print("SAFETY",json.dumps({k:v for k,v in q75.items() if k!="_ids"},indent=2))