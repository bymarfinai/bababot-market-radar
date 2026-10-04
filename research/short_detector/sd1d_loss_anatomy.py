from __future__ import annotations
import csv, json, math, statistics, itertools
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

RANDOM_STATE=4104
FEATURE_PATH=Path("/data/wd5h1_thesis_labeled_features.csv")
UNIVERSE_PATH=Path("/work/sd1d/research/short_detector/results/sd1a_short_universe_655.csv")
WIN_ASSIGN_PATH=Path("/work/sd1d/research/short_detector/results/sd1c_strong_winner_assignments.csv")
OUT=Path("/work/sd1d_out")
OUT.mkdir(parents=True,exist_ok=True)

EXCLUDED={
 "f_decision_hour_utc","f_decision_hour_sin","f_decision_hour_cos",
 "f_decision_weekday_utc","f_latency_ai_queue_s","f_latency_ai_execution_s",
 "f_latency_stage11c_s",
}
SIGNATURE_FEATURES=[
 "f_gate_taker_share_for_selected",
 "f_gate_side_ret_1m_pct",
 "f_new_flow_support",
 "f_new_gate_price_x_flow_gap",
 "f_new_micro_accel_1_vs_3",
 "f_f_coin_minus_market_15m",
]
SPLITS=("Discovery","Validation","Reserve")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def truth(v): return str(v).strip().lower() in {"1","true","yes"}
def as_float(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception: return None
def q(vals,p):
    vals=sorted(float(x) for x in vals if x is not None and math.isfinite(float(x)))
    if not vals: return None
    pos=(len(vals)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)
def safe_auc(y,x):
    pairs=[(yy,xx) for yy,xx in zip(y,x) if xx is not None and math.isfinite(float(xx))]
    if len(pairs)<4 or len({yy for yy,_ in pairs})<2: return None
    try: return float(roc_auc_score([a for a,_ in pairs],[float(b) for _,b in pairs]))
    except Exception: return None
def oriented_auc(y,x,direction):
    a=safe_auc(y,x)
    if a is None: return None
    return a if direction=="HIGH" else 1-a

features=read_csv(FEATURE_PATH)
universe=read_csv(UNIVERSE_PATH)
win_assign_rows=read_csv(WIN_ASSIGN_PATH)
fm={r["meta_position_id"]:r for r in features}
losses=[u for u in universe if u["primary_meta_label"]=="META_LOSS"]
wins=[u for u in universe if truth(u["strong_win"])]
assert len(losses)==492 and len(wins)==99
assert {s:sum(u["split"]==s for u in losses) for s in SPLITS}=={"Discovery":295,"Validation":90,"Reserve":107}
assert {s:sum(u["split"]==s for u in wins) for s in SPLITS}=={"Discovery":59,"Validation":27,"Reserve":13}
win_cluster={r["position_id"]:int(r["cluster"]) for r in win_assign_rows}
assert set(win_cluster)=={u["position_id"] for u in wins}

headers=list(features[0])
feature_cols=[c for c in headers if c.startswith("f_") and c not in EXCLUDED]
assert len(feature_cols)==224
numeric=[]; categorical=[]
for c in feature_cols:
    vals=[fm[u["position_id"]].get(c) for u in universe if fm[u["position_id"]].get(c) not in ("",None)]
    good=sum(as_float(v) is not None for v in vals)
    (numeric if vals and good/len(vals)>=0.999 else categorical).append(c)
assert len(numeric)==210 and len(categorical)==14

Dloss=[u for u in losses if u["split"]=="Discovery"]
Dids=[u["position_id"] for u in Dloss]

# Fit preprocessing on Discovery loss only.
eligible=[]; medians={}
for c in sorted(numeric):
    vals=[as_float(fm[pid].get(c)) for pid in Dids]
    finite=[x for x in vals if x is not None]
    if len(finite)/len(vals)<0.95: continue
    med=float(statistics.median(finite)); medians[c]=med
    filled=np.array([med if x is None else x for x in vals],dtype=float)
    if float(np.std(filled))<=1e-12: continue
    eligible.append(c)

Dmat_all=np.column_stack([
    np.array([medians[c] if as_float(fm[pid].get(c)) is None else as_float(fm[pid].get(c)) for pid in Dids],dtype=float)
    for c in eligible
])
col_index={c:i for i,c in enumerate(eligible)}
retained=[]; dropped_corr={}
for c in eligible:
    x=Dmat_all[:,col_index[c]]
    drop=None
    for keep in retained:
        y=Dmat_all[:,col_index[keep]]
        corr=float(np.corrcoef(x,y)[0,1])
        if math.isfinite(corr) and abs(corr)>0.95:
            drop=(keep,corr); break
    if drop is None: retained.append(c)
    else: dropped_corr[c]={"against":drop[0],"corr":drop[1]}

cat_levels={}
for c in sorted(categorical):
    cat_levels[c]=sorted({fm[pid].get(c,"") for pid in Dids})
cat_columns=[(c,lvl) for c in sorted(cat_levels) for lvl in cat_levels[c]]

def build_matrix(us):
    out=[]
    for u in us:
        fr=fm[u["position_id"]]
        row=[]
        for c in retained:
            v=as_float(fr.get(c)); row.append(medians[c] if v is None else v)
        for c,lvl in cat_columns:
            row.append(1.0 if fr.get(c,"")==lvl else 0.0)
        out.append(row)
    return np.asarray(out,dtype=float)

XD_raw=build_matrix(Dloss)
scaler=StandardScaler()
XD=scaler.fit_transform(XD_raw)
pca=PCA(n_components=0.80,svd_solver="full",random_state=RANDOM_STATE)
ZD=pca.fit_transform(XD)

# Freeze k from Discovery loss only.
rng=np.random.default_rng(RANDOM_STATE)
k_results=[]; models={}
for k in range(2,9):
    km=KMeans(n_clusters=k,n_init=50,random_state=RANDOM_STATE,algorithm="lloyd")
    labels=km.fit_predict(ZD)
    counts=Counter(int(x) for x in labels)
    if min(counts.values())<15:
        k_results.append({"k":k,"valid":False,"cluster_counts":dict(sorted(counts.items())),"reason":"min_cluster_lt15"})
        continue
    sil=float(silhouette_score(ZD,labels))
    aris=[]
    nsub=max(k*15,int(round(len(ZD)*0.80)))
    for b in range(100):
        idx=np.sort(rng.choice(len(ZD),size=nsub,replace=False))
        bkm=KMeans(n_clusters=k,n_init=20,random_state=RANDOM_STATE+b+1,algorithm="lloyd")
        bkm.fit(ZD[idx])
        pred=bkm.predict(ZD)
        aris.append(float(adjusted_rand_score(labels,pred)))
    rec={
      "k":k,"valid":True,"cluster_counts":dict(sorted(counts.items())),
      "silhouette":sil,"bootstrap_ari_median":float(np.median(aris)),
      "bootstrap_ari_p25":float(np.quantile(aris,0.25)),
      "bootstrap_ari_p10":float(np.quantile(aris,0.10)),
    }
    k_results.append(rec); models[k]=(km,labels)

valid=[r for r in k_results if r.get("valid")]
assert valid
best_s=max(r["silhouette"] for r in valid)
near=sorted([r for r in valid if best_s-r["silhouette"]<0.01],key=lambda r:r["k"])
selected=near[0]
for cand in near[1:]:
    if cand["bootstrap_ari_median"]>=selected["bootstrap_ari_median"]+0.10:
        selected=cand
k=selected["k"]; km,labD=models[k]

# Project all losses only after k frozen.
all_losses=[]
for s in SPLITS: all_losses.extend([u for u in losses if u["split"]==s])
Zall=pca.transform(scaler.transform(build_matrix(all_losses)))
lab_all=km.predict(Zall)
dist_all=np.linalg.norm(Zall-km.cluster_centers_[lab_all],axis=1)
loss_assign={}
for u,l,d in zip(all_losses,lab_all,dist_all):
    loss_assign[u["position_id"]]={"cluster":int(l),"distance":float(d)}

# cluster summaries
clusters=[]
for cidx in range(k):
    g=[u for u in all_losses if loss_assign[u["position_id"]]["cluster"]==cidx]
    mfe=[float(u["historical_max_mfe_pct"]) for u in g]
    mae=[float(u["historical_min_mae_pct"]) for u in g]
    pnl=[float(u["historical_realized_pnl_usdt"]) for u in g]
    rets=[float(u["historical_realized_pnl_pct"]) for u in g]
    wd=Counter(u["historical_wd1_outcome"] for u in g)
    clusters.append({
      "cluster":cidx,"neutral_label":f"SHORT_LOSS_CLUSTER_{cidx}","n":len(g),
      "share_pct":100*len(g)/len(losses),
      "split_counts":{s:sum(u["split"]==s for u in g) for s in SPLITS},
      "mfe_median_pct":float(np.median(mfe)),"mfe_mean_pct":float(np.mean(mfe)),
      "mae_median_pct":float(np.median(mae)),"mae_mean_pct":float(np.mean(mae)),
      "historical_pnl_usdt":sum(pnl),"historical_avg_return_pct":float(np.mean(rets)),
      "historical_realized_positive_n":sum(x>0 for x in pnl),
      "wd1_outcomes":dict(wd),
      "centroid_distance_by_split":{
        s:{
          "n":len(ds:=[loss_assign[u["position_id"]]["distance"] for u in g if u["split"]==s]),
          "median":q(ds,0.5),"p90":q(ds,0.9),"max":max(ds) if ds else None
        } for s in SPLITS
      }
    })

gates={
 "selected_k_ge_2":k>=2,
 "discovery_silhouette_ge_0p10":selected["silhouette"]>=0.10,
 "bootstrap_ari_median_ge_0p50":selected["bootstrap_ari_median"]>=0.50,
 "min_discovery_cluster_ge_15":min(Counter(labD).values())>=15,
 "validation_not_single_cluster":len({loss_assign[u["position_id"]]["cluster"] for u in losses if u["split"]=="Validation"})>=2,
 "reserve_not_single_cluster":len({loss_assign[u["position_id"]]["cluster"] for u in losses if u["split"]=="Reserve"})>=2,
}
cluster_status="PASS_LOSS_HETEROGENEITY" if all(gates.values()) else "NO_PASS_UNSTABLE_LOSS_CLUSTERING"

# Signature mapping if k=2.
mapping=None; signature_payload={}
if k==2:
    pooledD=[u for u in wins+losses if u["split"]=="Discovery"]
    robust={}
    for feat in SIGNATURE_FEATURES:
        vals=[as_float(fm[u["position_id"]].get(feat)) for u in pooledD]
        vals=[v for v in vals if v is not None]
        med=float(np.median(vals)); iqr=float(np.quantile(vals,0.75)-np.quantile(vals,0.25))
        robust[feat]={"median":med,"iqr":iqr if iqr>1e-12 else 1.0}
    wvec={}; lvec={}
    for wc in (0,1):
        group=[u for u in wins if u["split"]=="Discovery" and win_cluster[u["position_id"]]==wc]
        raw={feat:float(np.median([as_float(fm[u["position_id"]].get(feat)) for u in group])) for feat in SIGNATURE_FEATURES}
        wvec[wc]=np.array([(raw[f]-robust[f]["median"])/robust[f]["iqr"] for f in SIGNATURE_FEATURES])
        signature_payload[f"winner_{wc}"]=raw
    for lc in (0,1):
        group=[u for u in losses if u["split"]=="Discovery" and loss_assign[u["position_id"]]["cluster"]==lc]
        raw={feat:float(np.median([as_float(fm[u["position_id"]].get(feat)) for u in group])) for feat in SIGNATURE_FEATURES}
        lvec[lc]=np.array([(raw[f]-robust[f]["median"])/robust[f]["iqr"] for f in SIGNATURE_FEATURES])
        signature_payload[f"loss_{lc}"]=raw
    costs={(wc,lc):float(np.linalg.norm(wvec[wc]-lvec[lc])) for wc in (0,1) for lc in (0,1)}
    total_a=costs[(0,0)]+costs[(1,1)]
    total_b=costs[(0,1)]+costs[(1,0)]
    if total_a<=total_b:
        mapping={0:0,1:1}
    else:
        mapping={0:1,1:0}
    signature_payload["robust_scale"]=robust
    signature_payload["pair_costs"]={f"winner_{wc}_loss_{lc}":v for (wc,lc),v in costs.items()}
    signature_payload["selected_mapping"]={f"winner_{wc}":f"loss_{lc}" for wc,lc in mapping.items()}
    signature_payload["selected_total_cost"]=min(total_a,total_b)
    signature_payload["alternative_total_cost"]=max(total_a,total_b)

# loss assignments csv
loss_rows=[]
for u in all_losses:
    pid=u["position_id"]
    loss_rows.append({
      "position_id":pid,"symbol":u["symbol"],"split":u["split"],
      "loss_cluster":loss_assign[pid]["cluster"],"neutral_label":f"SHORT_LOSS_CLUSTER_{loss_assign[pid]['cluster']}",
      "centroid_distance":loss_assign[pid]["distance"],
      "historical_max_mfe_pct":u["historical_max_mfe_pct"],
      "historical_min_mae_pct":u["historical_min_mae_pct"],
      "historical_realized_pnl_usdt":u["historical_realized_pnl_usdt"],
      "historical_realized_pnl_pct":u["historical_realized_pnl_pct"],
      "historical_wd1_outcome":u["historical_wd1_outcome"],
    })
with (OUT/"sd1d_loss_cluster_assignments.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(loss_rows[0]));w.writeheader();w.writerows(loss_rows)

# Within-regime separation after mapping freeze.
lane_results=[]
feature_rows=[]
aggregate_diag={}
if mapping is not None:
    # aggregate numeric Discovery reference for comparison
    for feat in numeric:
        dwin=[u for u in wins if u["split"]=="Discovery"]; dloss=[u for u in losses if u["split"]=="Discovery"]
        x=[as_float(fm[u["position_id"]].get(feat)) for u in dwin+dloss]
        y=[1]*len(dwin)+[0]*len(dloss)
        a=safe_auc(y,x)
        if a is not None: aggregate_diag[feat]=max(a,1-a)

    for wc in (0,1):
        lc=mapping[wc]
        per=[]
        for feat in feature_cols:
            if feat in numeric:
                # D: freeze direction
                wD=[u for u in wins if u["split"]=="Discovery" and win_cluster[u["position_id"]]==wc]
                lD=[u for u in losses if u["split"]=="Discovery" and loss_assign[u["position_id"]]["cluster"]==lc]
                xD=[as_float(fm[u["position_id"]].get(feat)) for u in wD+lD]
                yD=[1]*len(wD)+[0]*len(lD)
                rawD=safe_auc(yD,xD)
                if rawD is None: continue
                direction="HIGH" if rawD>=0.5 else "LOW"
                aucs={}
                raws={}
                for sp in SPLITS:
                    wg=[u for u in wins if u["split"]==sp and win_cluster[u["position_id"]]==wc]
                    lg=[u for u in losses if u["split"]==sp and loss_assign[u["position_id"]]["cluster"]==lc]
                    x=[as_float(fm[u["position_id"]].get(feat)) for u in wg+lg]
                    y=[1]*len(wg)+[0]*len(lg)
                    raw=safe_auc(y,x)
                    raws[sp]=raw
                    aucs[sp]=(raw if direction=="HIGH" else 1-raw) if raw is not None else None
                if aucs["Discovery"] is None or aucs["Validation"] is None: continue
                per.append({
                  "winner_cluster":wc,"loss_cluster":lc,"feature":feat,"feature_type":"numeric",
                  "frozen_direction":direction,"frozen_state":None,
                  "D_auc":aucs["Discovery"],"V_auc":aucs["Validation"],"R_auc":aucs["Reserve"],
                  "D_raw_auc":raws["Discovery"],"V_raw_auc":raws["Validation"],"R_raw_auc":raws["Reserve"],
                  "DV_floor":min(aucs["Discovery"],aucs["Validation"]),
                  "aggregate_discovery_separation_auc":aggregate_diag.get(feat),
                })
            else:
                # categorical: freeze best single state from D only.
                wD=[u for u in wins if u["split"]=="Discovery" and win_cluster[u["position_id"]]==wc]
                lD=[u for u in losses if u["split"]=="Discovery" and loss_assign[u["position_id"]]["cluster"]==lc]
                levels=sorted({fm[u["position_id"]].get(feat,"") for u in wD+lD})
                best=None
                for state in levels:
                    x=[1.0 if fm[u["position_id"]].get(feat,"")==state else 0.0 for u in wD+lD]
                    y=[1]*len(wD)+[0]*len(lD)
                    raw=safe_auc(y,x)
                    if raw is None: continue
                    sep=max(raw,1-raw)
                    if best is None or sep>best["sep"]:
                        best={"state":state,"raw":raw,"sep":sep,"direction":"HIGH" if raw>=0.5 else "LOW"}
                if best is None: continue
                aucs={};raws={}
                for sp in SPLITS:
                    wg=[u for u in wins if u["split"]==sp and win_cluster[u["position_id"]]==wc]
                    lg=[u for u in losses if u["split"]==sp and loss_assign[u["position_id"]]["cluster"]==lc]
                    x=[1.0 if fm[u["position_id"]].get(feat,"")==best["state"] else 0.0 for u in wg+lg]
                    y=[1]*len(wg)+[0]*len(lg)
                    raw=safe_auc(y,x); raws[sp]=raw
                    aucs[sp]=(raw if best["direction"]=="HIGH" else 1-raw) if raw is not None else None
                if aucs["Discovery"] is None or aucs["Validation"] is None: continue
                per.append({
                  "winner_cluster":wc,"loss_cluster":lc,"feature":feat,"feature_type":"categorical",
                  "frozen_direction":best["direction"],"frozen_state":best["state"],
                  "D_auc":aucs["Discovery"],"V_auc":aucs["Validation"],"R_auc":aucs["Reserve"],
                  "D_raw_auc":raws["Discovery"],"V_raw_auc":raws["Validation"],"R_raw_auc":raws["Reserve"],
                  "DV_floor":min(aucs["Discovery"],aucs["Validation"]),
                  "aggregate_discovery_separation_auc":None,
                })

        per.sort(key=lambda r:(r["DV_floor"], r["R_auc"] if r["R_auc"] is not None else -1),reverse=True)
        feature_rows.extend(per)
        top=per[0]
        lane_results.append({
          "winner_cluster":wc,"loss_cluster":lc,
          "counts":{
             sp:{
               "winner_n":sum(u["split"]==sp and win_cluster[u["position_id"]]==wc for u in wins),
               "loss_n":sum(u["split"]==sp and loss_assign[u["position_id"]]["cluster"]==lc for u in losses),
             } for sp in SPLITS
          },
          "best_feature":top,
          "features_DV_ge_0p60":sum(r["D_auc"]>=0.60 and r["V_auc"]>=0.60 for r in per),
          "features_DVR_ge_0p60":sum(r["D_auc"]>=0.60 and r["V_auc"]>=0.60 and r["R_auc"] is not None and r["R_auc"]>=0.60 for r in per),
          "top_20_features":per[:20],
        })

# write feature table
if feature_rows:
    cols=list(feature_rows[0])
    with (OUT/"sd1d_within_regime_auc.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(feature_rows)

payload={
 "stage":"SD-1D",
 "loss_cluster_status":cluster_status,
 "universe":{"meta_loss_n":492,"loss_splits":{"Discovery":295,"Validation":90,"Reserve":107},
             "strong_win_reference_n":99,"winner_splits":{"Discovery":59,"Validation":27,"Reserve":13}},
 "preprocessing":{"raw_t0_features":224,"numeric":len(numeric),"categorical":len(categorical),
                  "eligible_numeric_before_corr_prune":len(eligible),
                  "retained_numeric_after_corr_prune":len(retained),
                  "corr_pruned_numeric":len(dropped_corr),
                  "categorical_onehot_columns":len(cat_columns),
                  "model_columns":len(retained)+len(cat_columns),
                  "pca_components":int(pca.n_components_),
                  "pca_explained_variance":float(np.sum(pca.explained_variance_ratio_))},
 "k_search":k_results,"selected_k":k,"selected_k_metrics":selected,"gates":gates,
 "loss_clusters":clusters,
 "signature_mapping":signature_payload if mapping is not None else None,
 "within_regime_results":lane_results,
}
# overall verdict
if cluster_status=="PASS_LOSS_HETEROGENEITY" and mapping is not None and any(
    lr["best_feature"]["DV_floor"]>=0.60 and lr["best_feature"]["R_auc"] is not None and lr["best_feature"]["R_auc"]>=0.60
    for lr in lane_results
):
    payload["status"]="PASS_ANATOMY_WITH_WITHIN_REGIME_EDGE"
elif mapping is not None:
    payload["status"]="PASS_DIAGNOSTIC_ONLY"
else:
    payload["status"]="NO_PASS"

(OUT/"sd1d_summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
print(json.dumps(payload,indent=2))