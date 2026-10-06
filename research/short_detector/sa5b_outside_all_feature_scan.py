from __future__ import annotations
import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def truth(v):return str(v).strip().lower() in {"true","1","1.0","yes"}
def ff(v):
    if v is None:return None
    s=str(v).strip()
    if not s:return None
    if s.lower() in {"true","false"}:return 1.0 if s.lower()=="true" else 0.0
    try:
        x=float(s);return x if math.isfinite(x) else None
    except:return None
def auc(vals):
    pos=[x for x,y in vals if y];neg=[x for x,y in vals if not y]
    if not pos or not neg:return None
    z=sorted(vals,key=lambda a:a[0]);rs=0.0;i=0
    while i<len(z):
        j=i+1
        while j<len(z) and z[j][0]==z[i][0]:j+=1
        rank=((i+1)+j)/2.0
        rs+=rank*sum(1 for _,y in z[i:j] if y);i=j
    return (rs-len(pos)*(len(pos)+1)/2)/(len(pos)*len(neg))
def sep(a):return max(a,1-a) if a is not None else None
def same_dir(a,b):
    return a is not None and b is not None and a!=.5 and b!=.5 and (a-.5)*(b-.5)>0
def pct(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w

detail=list(csv.DictReader(open(RES/"ct6a_trade_detail.csv")))
dm={r["position_id"]:r for r in detail}
base={r["position_id"]:r for r in csv.DictReader(open(RES/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
arch={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7b_trade_membership.csv"))}
ct5=set(json.load(open(RES/"ct5b_summary.json"))["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(RES/"ct6c_veto_trade_detail.csv"))}
ct7={r["position_id"] for r in csv.DictReader(open(RES/"ct7c_trade_detail.csv"))}
q95={r["position_id"] for r in csv.DictReader(open(RES/"sa2_candidate_trade_detail.csv")) if truth(r["Q95_AGGRESSIVE"])}
rescue={r["position_id"] for r in csv.DictReader(open(RES/"sa3_rescue_trade_detail.csv"))}
hard=ct5|ct6
negative=ct7|q95
final_selected=(set(base)-hard-negative)|rescue

RROWS=list(csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv")))
FROWS=list(csv.DictReader(open("/tmp/s10h_fresh_features.csv")))
R={r["meta_position_id"]:r for r in RROWS};F={r["meta_position_id"]:r for r in FROWS}
def raw(pid):return R[pid] if dm[pid]["source"]=="research" else F[pid]

def outside_old(pid):
    a=arch[pid]
    return not any(truth(a[k]) for k in ("A1_LOW_DISPLACEMENT","A2_WEAK_RELATIVE_EXPANSION","A3_LOW_ENERGY_RESIDUAL"))

# Discovery universe = final-selected outside-old morphology, BAD vs TARGET only.
univ=[
    dm[pid] for pid in final_selected
    if outside_old(pid) and dm[pid]["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50","TARGET_GE_1P00")
]
bad=[r for r in univ if r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
target=[r for r in univ if r["mfe_bucket"]=="TARGET_GE_1P00"]
print("UNIV selected outside-old BAD",len(bad),"TARGET",len(target),"Research/Fresh BAD",sum(r["source"]=="research" for r in bad),sum(r["source"]=="fresh" for r in bad),"TARGET",sum(r["source"]=="research" for r in target),sum(r["source"]=="fresh" for r in target))

# Exclude temporal, metadata, selection-state, old morphology/Q95 direct basis.
OLD={
 "f_micro_distance_selected_extreme_15m",
 "f_ret_1h_pct_for_selected",
 "f_f_relative_overextension_30m",
 "f_median_abs_ret_5m_pct",
 "f_f_coin_residual_5m_vs_btc",
 "f_micro_selected_vwap_extension_20",
 "f_context_quote_volume_5m",
 "f_f_coin_minus_market_30m",
}
EXACT={"meta_position_id","meta_signal_id","meta_symbol","meta_opened_at_ms","f_side_is_long","f_decision_hour_utc","f_decision_weekday_utc"}
SEL_PREFIX=("f_long_score","f_short_score","f_selected_score","f_opposite_score","f_score_edge","f_decision_context_","f_evidence_count","f_score_component_","f_stage")
headers=[x for x in RROWS[0] if x in set(FROWS[0])]
features=[
 c for c in headers if c not in EXACT and c not in OLD and not c.startswith("meta_")
 and not c.startswith(("t1_","t2_","t3_"))
 and not any(c.startswith(p) for p in SEL_PREFIX)
]

BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]
records=[]
for k in features:
    vals=[]
    for r in univ:
        x=ff(raw(r["position_id"]).get(k))
        if x is not None:vals.append((x,r["mfe_bucket"]!="TARGET_GE_1P00",r))
    if len(vals)<.90*len(univ):continue
    a=auc([(x,y) for x,y,_ in vals])
    if a is None:continue
    src={}
    for s in ("research","fresh"):
        src[s]=auc([(x,y) for x,y,r in vals if r["source"]==s])
    ba={}
    for b in BLOCKS:
        ba[b]=auc([(x,y) for x,y,r in vals if r["block"]==b])
    valid=[v for v in ba.values() if v is not None]
    agree=sum(same_dir(a,v) for v in valid)
    sx=same_dir(a,src["research"]) and same_dir(a,src["fresh"])
    bx=[x for x,y,_ in vals if y];tx=[x for x,y,_ in vals if not y]
    records.append({
      "feature":k,"coverage":len(vals)/len(univ),"auc":a,"separation":sep(a),
      "direction":"HIGH_BAD" if a>.5 else "LOW_BAD",
      "bad_median":statistics.median(bx),"target_median":statistics.median(tx),
      "research_auc":src["research"],"fresh_auc":src["fresh"],
      "source_agree":sx,"block_agree":agree,"block_valid":len(valid),
      **{"auc_"+b:ba[b] for b in BLOCKS},
    })
ranked=sorted(records,key=lambda r:(r["source_agree"],r["block_agree"],r["separation"]),reverse=True)
stable=[r for r in ranked if r["coverage"]>=.95 and r["separation"]>=.57 and r["source_agree"] and r["block_agree"]>=4]
print("stable",len(stable))
for r in stable[:50]:
    print(r["feature"],r["direction"],"sep",round(r["separation"],3),"A",round(r["auc"],3),"R/F",None if r["research_auc"] is None else round(r["research_auc"],3),None if r["fresh_auc"] is None else round(r["fresh_auc"],3),"blocks",r["block_agree"],"/",r["block_valid"],"med",round(r["bad_median"],5),round(r["target_median"],5))

with open(RES/"sa5b_feature_separation.csv","w",newline="") as f:
    fields=list(records[0].keys()) if records else []
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(sorted(records,key=lambda r:r["separation"],reverse=True))
(RES/"sa5b_feature_scan.json").write_text(json.dumps({
 "universe":{"bad":len(bad),"target":len(target)},
 "excluded_old_features":sorted(OLD),
 "stable_count":len(stable),
 "stable_top":stable[:60],
},indent=2))