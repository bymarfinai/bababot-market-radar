from __future__ import annotations
import csv, itertools, json, math, statistics, time
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

RANDOM_STATE=4104
CS=[0.01,0.1,1.0,10.0,100.0]
FEATURE_PATH=Path("/data/wd5h1_thesis_labeled_features.csv")
UNIVERSE_PATH=Path("/work/sd2a/research/short_detector/results/sd1a_short_universe_655.csv")
WIN_ASSIGN_PATH=Path("/work/sd2a/research/short_detector/results/sd1c_strong_winner_assignments.csv")
LOSS_ASSIGN_PATH=Path("/work/sd2a/research/short_detector/results/sd1d_loss_cluster_assignments.csv")
SD1D_AUC_PATH=Path("/work/sd2a/research/short_detector/results/sd1d_within_regime_auc.csv")
OUT=Path("/work/sd2a_out")
OUT.mkdir(parents=True,exist_ok=True)

EXCLUDED={
 "f_decision_hour_utc","f_decision_hour_sin","f_decision_hour_cos",
 "f_decision_weekday_utc","f_latency_ai_queue_s","f_latency_ai_execution_s",
 "f_latency_stage11c_s",
}
SPLITS=("Discovery","Validation","Reserve")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def truth(v): return str(v).strip().lower() in {"1","true","yes"}
def as_float(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None
def safe_auc(y,s):
    if len(set(int(x) for x in y))<2: return None
    return float(roc_auc_score(y,s))
def corr(a,b):
    if len(a)<2 or np.std(a)==0 or np.std(b)==0: return 0.0
    return float(np.corrcoef(a,b)[0,1])
def median(vals):
    vals=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
    return float(statistics.median(vals)) if vals else None
def q(vals,p):
    vals=sorted(float(x) for x in vals)
    pos=(len(vals)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)

features=read_csv(FEATURE_PATH)
universe=read_csv(UNIVERSE_PATH)
win_as=read_csv(WIN_ASSIGN_PATH)
loss_as=read_csv(LOSS_ASSIGN_PATH)
sd1d_auc=read_csv(SD1D_AUC_PATH)
fm={r["meta_position_id"]:r for r in features}
win_cluster={r["position_id"]:int(r["cluster"]) for r in win_as}
loss_cluster={r["position_id"]:int(r["loss_cluster"]) for r in loss_as}

headers=list(features[0])
feature_cols=[c for c in headers if c.startswith("f_") and c not in EXCLUDED]
assert len(feature_cols)==224
numeric=[]
for c in feature_cols:
    vals=[fm[u["position_id"]].get(c) for u in universe if fm[u["position_id"]].get(c) not in ("",None)]
    good=sum(as_float(v) is not None for v in vals)
    if vals and good/len(vals)>=0.999:
        numeric.append(c)
assert len(numeric)==210

wins=[u for u in universe if truth(u["strong_win"])]
losses=[u for u in universe if u["primary_meta_label"]=="META_LOSS"]

expected={
 0:{"Discovery":(17,82),"Validation":(8,24),"Reserve":(5,17)},
 1:{"Discovery":(42,213),"Validation":(19,66),"Reserve":(8,90)},
}

# SD1D best single-feature frozen D+V reference per lane.
single_refs={}
for lane in (0,1):
    rows=[r for r in sd1d_auc if int(r["winner_cluster"])==lane]
    rows.sort(key=lambda r:float(r["DV_floor"]),reverse=True)
    x=rows[0]
    single_refs[lane]={
      "feature":x["feature"],"direction":x["frozen_direction"],
      "D_auc":float(x["D_auc"]),"V_auc":float(x["V_auc"]),
      "R_auc":float(x["R_auc"]) if x["R_auc"] not in ("","None") else None,
      "DV_floor":float(x["DV_floor"])
    }

all_grid=[]
lane_summaries=[]
started=time.time()

for lane in (0,1):
    lane_rows={}
    for sp in SPLITS:
        w=[u for u in wins if u["split"]==sp and win_cluster[u["position_id"]]==lane]
        l=[u for u in losses if u["split"]==sp and loss_cluster[u["position_id"]]==lane]
        assert (len(w),len(l))==expected[lane][sp],(lane,sp,len(w),len(l))
        lane_rows[sp]=[(u,1) for u in w]+[(u,0) for u in l]

    D=lane_rows["Discovery"]
    # Discovery-only eligible numeric & univariate ranking.
    eligible=[]
    medians={}
    discovery_auc={}
    discovery_dir={}
    for c in numeric:
        vals=[as_float(fm[u["position_id"]].get(c)) for u,_ in D]
        finite=[x for x in vals if x is not None]
        if len(finite)/len(vals)<0.95: continue
        med=float(statistics.median(finite)); medians[c]=med
        x=np.array([med if v is None else v for v in vals],dtype=float)
        if np.std(x)<=1e-12: continue
        y=np.array([yy for _,yy in D],dtype=int)
        a=safe_auc(y,x)
        if a is None: continue
        eligible.append(c)
        discovery_auc[c]=max(a,1-a)
        discovery_dir[c]="HIGH" if a>=0.5 else "LOW"

    ranked=sorted(eligible,key=lambda c:(-discovery_auc[c],c))
    # Greedy correlation pruning <=.85
    selected=[]
    Xdisc_cache={}
    for c in ranked:
        vals=[as_float(fm[u["position_id"]].get(c)) for u,_ in D]
        x=np.array([medians[c] if v is None else v for v in vals],dtype=float)
        Xdisc_cache[c]=x
        ok=True
        for k in selected:
            if abs(corr(x,Xdisc_cache[k]))>0.85:
                ok=False; break
        if ok:
            selected.append(c)
            if len(selected)==18: break
    assert len(selected)==18,(lane,len(selected))

    # Freeze imputation medians for selected and scale from D only.
    impute={c:medians[c] for c in selected}
    def matrix(sp):
        rows=lane_rows[sp]
        X=[]
        y=[]
        pnl=[]
        ret=[]
        ids=[]
        for u,yy in rows:
            fr=fm[u["position_id"]]
            X.append([impute[c] if as_float(fr.get(c)) is None else as_float(fr.get(c)) for c in selected])
            y.append(yy)
            pnl.append(float(u["historical_realized_pnl_usdt"]))
            ret.append(float(u["historical_realized_pnl_pct"]))
            ids.append(u["position_id"])
        return np.asarray(X,float),np.asarray(y,int),np.asarray(pnl,float),np.asarray(ret,float),ids

    XD,yD,pnlD,retD,idD=matrix("Discovery")
    XV,yV,pnlV,retV,idV=matrix("Validation")
    XR,yR,pnlR,retR,idR=matrix("Reserve")
    scaler=StandardScaler().fit(XD)
    XD=scaler.transform(XD); XV=scaler.transform(XV); XR=scaler.transform(XR)

    grid=[]
    best_by_size={}
    for size in (2,3,4):
        best=None
        for combo_idx in itertools.combinations(range(18),size):
            feats=tuple(selected[i] for i in combo_idx)
            for C in CS:
                model=LogisticRegression(
                  penalty="l2",C=C,class_weight="balanced",solver="liblinear",
                  max_iter=5000,random_state=RANDOM_STATE
                )
                model.fit(XD[:,combo_idx],yD)
                pD=model.predict_proba(XD[:,combo_idx])[:,1]
                pV=model.predict_proba(XV[:,combo_idx])[:,1]
                aD=safe_auc(yD,pD); aV=safe_auc(yV,pV)
                floor=min(aD,aV)
                rec={
                  "lane":lane,"size":size,"C":C,"features":"|".join(feats),
                  "D_auc":aD,"V_auc":aV,"DV_floor":floor,
                }
                grid.append(rec); all_grid.append(rec)
                key=(floor,aV,-size,-C,tuple(reversed(feats)))
                # implement contract tie break directly below rather than reversed lexical hack
                if best is None:
                    best={"rec":rec,"combo_idx":combo_idx,"model":model,"features":feats}
                else:
                    b=best["rec"]
                    better=False
                    if floor>b["DV_floor"]+1e-12: better=True
                    elif abs(floor-b["DV_floor"])<=1e-12:
                        if aV>b["V_auc"]+1e-12: better=True
                        elif abs(aV-b["V_auc"])<=1e-12:
                            if size<b["size"]: better=True
                            elif size==b["size"]:
                                if C<b["C"]-1e-12: better=True
                                elif abs(C-b["C"])<=1e-12 and feats<best["features"]: better=True
                    if better:
                        best={"rec":rec,"combo_idx":combo_idx,"model":model,"features":feats}
        best_by_size[size]=best
        print(f"lane={lane} size={size} done fits={len([r for r in grid if r['size']==size])}",flush=True)

    # Freeze overall candidate from D/V only.
    candidates=list(best_by_size.values())
    frozen=candidates[0]
    for cand in candidates[1:]:
        r=cand["rec"]; b=frozen["rec"]
        better=False
        if r["DV_floor"]>b["DV_floor"]+1e-12: better=True
        elif abs(r["DV_floor"]-b["DV_floor"])<=1e-12:
            if r["V_auc"]>b["V_auc"]+1e-12: better=True
            elif abs(r["V_auc"]-b["V_auc"])<=1e-12:
                if r["size"]<b["size"]: better=True
                elif r["size"]==b["size"]:
                    if r["C"]<b["C"]-1e-12: better=True
                    elif abs(r["C"]-b["C"])<=1e-12 and r["features"]<b["features"]: better=True
        if better:frozen=cand

    # Reserve opens only now for each already-frozen best-by-size model + overall.
    evaluated={}
    for label,cand in [(f"best_{s}",best_by_size[s]) for s in (2,3,4)]+[("frozen_overall",frozen)]:
        combo_idx=cand["combo_idx"]; model=cand["model"]; feats=cand["features"]
        pD=model.predict_proba(XD[:,combo_idx])[:,1]
        pV=model.predict_proba(XV[:,combo_idx])[:,1]
        pR=model.predict_proba(XR[:,combo_idx])[:,1]
        coefs={feat:float(coef) for feat,coef in zip(feats,model.coef_[0])}
        ev={
          **cand["rec"],
          "R_auc":safe_auc(yR,pR),
          "D_score_target_corr":corr(pD,yD),
          "V_score_target_corr":corr(pV,yV),
          "R_score_target_corr":corr(pR,yR),
          "intercept":float(model.intercept_[0]),
          "coefficients":coefs,
        }
        evaluated[label]=ev

    f=evaluated["frozen_overall"]
    if f["D_auc"]>=.70 and f["V_auc"]>=.70 and f["R_auc"]>=.70:
        lane_status="STRONG"
    elif f["D_auc"]>=.65 and f["V_auc"]>=.65 and f["R_auc"]>=.65:
        lane_status="PROMISING"
    else:
        lane_status="WEAK_FAIL"

    # Discovery score quintiles frozen from overall model; apply thresholds to all splits.
    combo_idx=frozen["combo_idx"]; model=frozen["model"]
    preds={
      "Discovery":model.predict_proba(XD[:,combo_idx])[:,1],
      "Validation":model.predict_proba(XV[:,combo_idx])[:,1],
      "Reserve":model.predict_proba(XR[:,combo_idx])[:,1],
    }
    ys={"Discovery":yD,"Validation":yV,"Reserve":yR}
    pnls={"Discovery":pnlD,"Validation":pnlV,"Reserve":pnlR}
    disc_pred=preds["Discovery"]
    cuts=[q(disc_pred,z) for z in (.2,.4,.6,.8)]
    quintile=[]
    for sp in SPLITS:
        p=preds[sp]; yy=ys[sp]; pnl={"Discovery":pnlD,"Validation":pnlV,"Reserve":pnlR}[sp]
        bins=np.digitize(p,cuts,right=True)+1
        for b in range(1,6):
            mask=bins==b
            quintile.append({
              "split":sp,"quintile":b,"n":int(mask.sum()),
              "winner_n":int(yy[mask].sum()) if mask.any() else 0,
              "winner_rate":float(yy[mask].mean()) if mask.any() else None,
              "historical_pnl_usdt":float(pnl[mask].sum()) if mask.any() else 0.0,
              "score_min":float(p[mask].min()) if mask.any() else None,
              "score_max":float(p[mask].max()) if mask.any() else None,
            })

    lane_summaries.append({
      "lane":lane,
      "population":{sp:{"win":expected[lane][sp][0],"loss":expected[lane][sp][1]} for sp in SPLITS},
      "eligible_numeric_n":len(eligible),
      "frozen_18_feature_pool":[
        {"rank":i+1,"feature":c,"discovery_separation_auc":discovery_auc[c],"discovery_direction":discovery_dir[c]}
        for i,c in enumerate(selected)
      ],
      "single_feature_reference":single_refs[lane],
      "best_by_size":evaluated,
      "frozen_overall":f,
      "lane_status":lane_status,
      "discovery_score_quintile_cuts":cuts,
      "score_quintile_diagnostics":quintile,
    })

# write full D/V grid (Reserve absent by design)
with (OUT/"sd2a_dv_model_grid.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["lane","size","C","features","D_auc","V_auc","DV_floor"])
    w.writeheader();w.writerows(all_grid)

payload={
 "stage":"SD-2A",
 "status":"COMPLETE",
 "fit_count":len(all_grid),
 "expected_fit_count":40290,
 "reserve_policy":"Reserve evaluated only for per-size and overall models frozen from D+V",
 "lanes":lane_summaries,
 "runtime_seconds":time.time()-started,
}
assert len(all_grid)==40290,len(all_grid)
(OUT/"sd2a_summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
print(json.dumps(payload,indent=2),flush=True)