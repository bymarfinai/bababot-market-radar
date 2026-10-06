from __future__ import annotations
import csv,itertools,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def truth(v):return str(v).strip().lower() in {"true","1","1.0","yes"}
def ff(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def pct(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w

D={r["position_id"]:r for r in csv.DictReader(open(RES/"ct6a_trade_detail.csv"))}
M=list(csv.DictReader(open(RES/"sa5b_family_membership.csv")))
R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}
def raw(pid):return R[pid] if D[pid]["source"]=="research" else F[pid]

BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]
PCTS=[.55,.60,.65,.70,.75,.80,.85,.90]

FAMILIES={
 "B1":{
   "rows":[r for r in M if truth(r["B1_30M_PROXIMITY_STALL"])],
   "features":{
     "f_f_range_climax_fade_10m":"HIGH",
     "f_micro_range_contraction_after_impulse":"HIGH",
   },
 },
 "B2":{
   "rows":[r for r in M if truth(r["B2_WEAK_PRESSURE_DRIFT_STALL"])],
   "features":{
     "f_gate_positioning_oi_change_pct":"HIGH",
     "f_micro_selected_taker_share_prev3m":"HIGH",
     "f_f_market_dispersion_15m":"LOW",
     "f_context_breakdown_down_pct":"LOW",
     "f_f_market_selected_ret_30m":"LOW",
     "f_micro_price_flow_divergence":"HIGH",
     "f_f_market_aligned_fraction_5m":"HIGH",
     "f_new_family_balance":"HIGH",
   },
 },
}

def metrics(rows,ids):
    rows=list(rows);ids=set(ids)
    z=[r for r in rows if r["position_id"] in ids]
    bad=[r for r in rows if r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
    tar=[r for r in rows if r["mfe_bucket"]=="TARGET_GE_1P00"]
    db=[r for r in z if r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
    dt=[r for r in z if r["mfe_bucket"]=="TARGET_GE_1P00"]
    return {
      "selected":len(z),"bad":len(db),"target":len(dt),
      "gray":sum(r["mfe_bucket"]=="GRAY_0P50_1P00" for r in z),
      "strong":sum(truth(r["strong"]) for r in z),
      "bad_recall":len(db)/len(bad) if bad else 0,
      "target_hit":len(dt)/len(tar) if tar else 0,
      "precision":len(db)/(len(db)+len(dt)) if len(db)+len(dt) else 0,
    }

allc=[]
for fam,spec in FAMILIES.items():
    rows=spec["rows"];features=spec["features"]
    binary=[r for r in rows if r["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50","TARGET_GE_1P00")]
    train_target=[r for r in binary if r["block"]=="Research_Discovery" and r["mfe_bucket"]=="TARGET_GE_1P00"]
    TH={}
    for k,direction in features.items():
        xs=[ff(raw(r["position_id"]).get(k)) for r in train_target if ff(raw(r["position_id"]).get(k)) is not None]
        TH[k]={p:pct(xs,p if direction=="HIGH" else 1-p) for p in PCTS}
    def cond(r,k,p):
        x=ff(raw(r["position_id"]).get(k));th=TH[k][p]
        return x is not None and (x>=th if features[k]=="HIGH" else x<=th)
    print("\n",fam,"binary",len(binary),"train target",len(train_target))
    cands=[]
    for n in range(1,min(4,len(features))+1):
        for fs in itertools.combinations(features,n):
            for p in PCTS:
                needs=[1] if n==1 else ([n] if n==2 else ([2,3] if n==3 else [3,4]))
                for need in needs:
                    ids={r["position_id"] for r in rows if sum(cond(r,k,p) for k in fs)>=need}
                    ma=metrics(rows,ids)
                    if ma["bad"]<3:continue
                    md=metrics([r for r in rows if r["block"]=="Research_Discovery"],ids)
                    mh=metrics([r for r in rows if r["block"] in ("Research_Validation","Research_Reserve")],ids)
                    mf=metrics([r for r in rows if r["source"]=="fresh"],ids)
                    bm={b:metrics([r for r in rows if r["block"]==b],ids) for b in BLOCKS}
                    # transport: negative selector should hit BAD relatively more often than TARGET.
                    agree=sum(v["bad_recall"]>v["target_hit"] for v in bm.values() if (v["bad"]+v["target"])>0)
                    transport=(
                      ma["precision"]>=.70
                      and ma["target_hit"]<=.12
                      and ma["strong"]<=4
                      and md["bad_recall"]>=md["target_hit"]
                      and mf["bad_recall"]>mf["target_hit"]
                      and agree>=4
                    )
                    rec={
                      "family":fam,"features":"|".join(fs),"n_features":n,"need":need,"percentile":p,
                      **ma,
                      "discovery_bad":md["bad"],"discovery_target":md["target"],
                      "holdout_bad":mh["bad"],"holdout_target":mh["target"],
                      "fresh_bad":mf["bad"],"fresh_target":mf["target"],
                      "block_agree":agree,"transport":transport,
                      "thresholds":{k:TH[k][p] for k in fs},"ids":ids,
                    }
                    cands.append(rec);allc.append(rec)
    good=[x for x in cands if x["transport"]]
    good.sort(key=lambda x:(x["precision"],x["bad"],-x["strong"],x["block_agree"]),reverse=True)
    print("transport",len(good))
    for x in good[:50]:
        print("BAD",x["bad"],"T",x["target"],"G",x["gray"],"S",x["strong"],"prec",round(x["precision"],3),"Brec",round(x["bad_recall"],3),"Thit",round(x["target_hit"],3),"agree",x["block_agree"],"p",x["percentile"],"need",x["need"],x["features"],"D",x["discovery_bad"],x["discovery_target"],"H",x["holdout_bad"],x["holdout_target"],"F",x["fresh_bad"],x["fresh_target"])

with open(RES/"sa5c_candidate_scan.csv","w",newline="") as f:
    fields=["family","features","n_features","need","percentile","selected","bad","target","gray","strong","bad_recall","target_hit","precision","discovery_bad","discovery_target","holdout_bad","holdout_target","fresh_bad","fresh_target","block_agree","transport","thresholds"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for x in allc:w.writerow({k:(json.dumps(x[k]) if k=="thresholds" else x[k]) for k in fields})