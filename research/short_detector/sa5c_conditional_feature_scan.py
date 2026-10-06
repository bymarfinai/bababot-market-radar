from __future__ import annotations
import csv,json,math,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def truth(v): return str(v).strip().lower() in {"true","1","1.0","yes"}
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
        rank=((i+1)+j)/2
        rs+=rank*sum(1 for _,y in z[i:j] if y);i=j
    return (rs-len(pos)*(len(pos)+1)/2)/(len(pos)*len(neg))
def same(a,b):return a is not None and b is not None and a!=.5 and b!=.5 and (a-.5)*(b-.5)>0
def percentile(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w

D={r["position_id"]:r for r in csv.DictReader(open(RES/"ct6a_trade_detail.csv"))}
M=list(csv.DictReader(open(RES/"sa5b_family_membership.csv")))
RROWS=list(csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv")))
FROWS=list(csv.DictReader(open("/tmp/s10h_fresh_features.csv")))
R={r["meta_position_id"]:r for r in RROWS};F={r["meta_position_id"]:r for r in FROWS}
def raw(pid):return R[pid] if D[pid]["source"]=="research" else F[pid]

BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]

# Exclude family-defining features, old broad/Q95 direct basis, temporal, selection state.
EXCLUDE={
 "f_micro_distance_selected_extreme_30m",
 "f_new_overheat_pressure","f_gate_price_drift_pct","f_gate_side_ret_3m_pct",
 "f_micro_distance_selected_extreme_15m","f_ret_1h_pct_for_selected",
 "f_f_relative_overextension_30m","f_median_abs_ret_5m_pct",
 "f_f_coin_residual_5m_vs_btc","f_micro_selected_vwap_extension_20",
 "f_context_quote_volume_5m","f_f_coin_minus_market_30m",
}
EXACT={"meta_position_id","meta_signal_id","meta_symbol","meta_opened_at_ms","f_side_is_long","f_decision_hour_utc","f_decision_weekday_utc"}
SELP=("f_long_score","f_short_score","f_selected_score","f_opposite_score","f_score_edge","f_decision_context_","f_evidence_count","f_score_component_","f_stage")
common=set(FROWS[0])
FEATURES=[c for c in RROWS[0] if c in common and c not in EXCLUDE and c not in EXACT and not c.startswith(("meta_","t1_","t2_","t3_")) and not any(c.startswith(p) for p in SELP)]

families={
 "B1":[r for r in M if truth(r["B1_30M_PROXIMITY_STALL"])],
 "B2":[r for r in M if truth(r["B2_WEAK_PRESSURE_DRIFT_STALL"])],
}
out={}
for fname,rows in families.items():
    binary=[r for r in rows if r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50","TARGET_GE_1P00")]
    recs=[]
    for k in FEATURES:
        vals=[]
        for r in binary:
            x=ff(raw(r["position_id"]).get(k))
            if x is not None:vals.append((x,r["mfe_bucket"]!="TARGET_GE_1P00",r))
        if len(vals)<.90*len(binary):continue
        a=auc([(x,y) for x,y,_ in vals])
        if a is None:continue
        src={s:auc([(x,y) for x,y,r in vals if r["source"]==s]) for s in ("research","fresh")}
        block={b:auc([(x,y) for x,y,r in vals if r["block"]==b]) for b in BLOCKS}
        agree=sum(same(a,v) for v in block.values() if v is not None)
        source_agree=same(a,src["research"]) and same(a,src["fresh"])
        bx=[x for x,y,_ in vals if y];tx=[x for x,y,_ in vals if not y]
        recs.append({
          "feature":k,"coverage":len(vals)/len(binary),"auc":a,"separation":max(a,1-a),
          "direction":"HIGH_BAD" if a>.5 else "LOW_BAD",
          "bad_median":statistics.median(bx),"target_median":statistics.median(tx),
          "research_auc":src["research"],"fresh_auc":src["fresh"],
          "source_agree":source_agree,"block_agree":agree,
          **{"auc_"+b:block[b] for b in BLOCKS}
        })
    stable=[r for r in recs if r["coverage"]>=.95 and r["separation"]>=.57 and r["source_agree"] and r["block_agree"]>=4]
    stable.sort(key=lambda r:(r["separation"],r["block_agree"]),reverse=True)
    out[fname]={"binary_n":len(binary),"bad_n":sum(r["mfe_bucket"]!="TARGET_GE_1P00" for r in binary),"target_n":sum(r["mfe_bucket"]=="TARGET_GE_1P00" for r in binary),"stable":stable}
    print("\n",fname,"binary",len(binary),"BAD",out[fname]["bad_n"],"T",out[fname]["target_n"],"stable",len(stable))
    for r in stable[:45]:
        print(r["feature"],r["direction"],"sep",round(r["separation"],3),"R/F",None if r["research_auc"] is None else round(r["research_auc"],3),None if r["fresh_auc"] is None else round(r["fresh_auc"],3),"blocks",r["block_agree"],"med",round(r["bad_median"],5),round(r["target_median"],5))
(RES/"sa5c_conditional_feature_scan.json").write_text(json.dumps(out,indent=2))