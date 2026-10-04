from __future__ import annotations
import csv, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

RANDOM_STATE=4104
FEATURE_PATH=Path("/data/wd5h1_thesis_labeled_features.csv")
UNIVERSE_PATH=Path("/work/sd1c/research/short_detector/results/sd1a_short_universe_655.csv")
OUT=Path("/work/sd1c_out")
OUT.mkdir(parents=True,exist_ok=True)

EXCLUDED={
 "f_decision_hour_utc","f_decision_hour_sin","f_decision_hour_cos",
 "f_decision_weekday_utc","f_latency_ai_queue_s","f_latency_ai_execution_s",
 "f_latency_stage11c_s",
}
DIAGNOSTIC_FEATURES=[
 "f_gate_taker_share_for_selected","f_gate_side_ret_1m_pct",
 "f_new_flow_support","f_new_gate_price_x_flow_gap",
 "f_new_micro_accel_1_vs_3","f_micro_decay_5_vs_prev5",
 "f_f_coin_minus_market_5m","f_f_coin_minus_market_15m",
 "f_f_coin_minus_market_30m","f_f_coin_residual_5m_vs_btc",
 "f_f_selected_slope5_norm","f_new_accel_5_vs_15",
 "f_new_momentum_curvature","f_gate_side_adjusted_drift_pct",
 "f_context_raw_oi_change_pct","f_f_taker_selected_share_5m",
 "f_micro_side_ret_5m","f_micro_selected_vwap_extension_20",
]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def truth(v): return str(v).strip().lower() in {"1","true","yes"}
def as_float(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception: return None
def quant(vals,q):
    vals=sorted(float(x) for x in vals if x is not None and math.isfinite(float(x)))
    if not vals: return None
    pos=(len(vals)-1)*q
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)
def safe_auc(y,x):
    pairs=[(yy,xx) for yy,xx in zip(y,x) if xx is not None and math.isfinite(float(xx))]
    if not pairs or len({yy for yy,_ in pairs})<2: return None
    yy=[a for a,_ in pairs]; xx=[float(b) for _,b in pairs]
    try: return float(roc_auc_score(yy,xx))
    except Exception: return None

features=read_csv(FEATURE_PATH)
universe=read_csv(UNIVERSE_PATH)
assert len(universe)==655
fm={r["meta_position_id"]:r for r in features}
strong=[u for u in universe if truth(u["strong_win"])]
loss=[u for u in universe if u["primary_meta_label"]=="META_LOSS"]
assert len(strong)==99 and len(loss)==492
strong_by_split={s:[u for u in strong if u["split"]==s] for s in ("Discovery","Validation","Reserve")}
assert {s:len(v) for s,v in strong_by_split.items()}=={"Discovery":59,"Validation":27,"Reserve":13}

headers=list(features[0])
feature_cols=[c for c in headers if c.startswith("f_") and c not in EXCLUDED]
assert len(feature_cols)==224

# Match SD-1B type classification using all 655 frozen SHORT rows.
numeric=[]; categorical=[]
for c in feature_cols:
    vals=[fm[u["position_id"]].get(c) for u in universe if fm[u["position_id"]].get(c) not in ("",None)]
    good=sum(as_float(v) is not None for v in vals)
    (numeric if vals and good/len(vals)>=0.999 else categorical).append(c)
assert len(numeric)==210 and len(categorical)==14

D=strong_by_split["Discovery"]
D_ids=[u["position_id"] for u in D]

# Numeric preprocessing fit only on D strong winners.
eligible=[]
medians={}
for c in sorted(numeric):
    vals=[as_float(fm[pid].get(c)) for pid in D_ids]
    finite=[x for x in vals if x is not None]
    if len(finite)/len(vals)<0.95: continue
    med=float(statistics.median(finite)); medians[c]=med
    filled=np.array([med if x is None else x for x in vals],dtype=float)
    if float(np.std(filled))<=1e-12: continue
    eligible.append(c)

# Deterministic correlation pruning.
retained=[]
dropped_corr={}
Dmat_all=np.column_stack([
    np.array([medians[c] if as_float(fm[pid].get(c)) is None else as_float(fm[pid].get(c)) for pid in D_ids],dtype=float)
    for c in eligible
])
col_index={c:i for i,c in enumerate(eligible)}
for c in eligible:
    x=Dmat_all[:,col_index[c]]
    drop_against=None
    for keep in retained:
        y=Dmat_all[:,col_index[keep]]
        corr=float(np.corrcoef(x,y)[0,1])
        if math.isfinite(corr) and abs(corr)>0.95:
            drop_against=(keep,corr); break
    if drop_against is None:
        retained.append(c)
    else:
        dropped_corr[c]={"against":drop_against[0],"corr":drop_against[1]}

# Categorical levels fit only on D strong winners.
cat_levels={}
for c in sorted(categorical):
    levels=sorted({fm[pid].get(c,"") for pid in D_ids})
    cat_levels[c]=levels
cat_columns=[(c,lvl) for c in sorted(cat_levels) for lvl in cat_levels[c]]

model_columns=list(retained)+[f"{c}=={lvl}" for c,lvl in cat_columns]

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

XD_raw=build_matrix(D)
scaler=StandardScaler()
XD=scaler.fit_transform(XD_raw)
pca=PCA(n_components=0.80,svd_solver="full",random_state=RANDOM_STATE)
ZD=pca.fit_transform(XD)

# Search k before touching projected V/R composition.
rng=np.random.default_rng(RANDOM_STATE)
k_results=[]
full_models={}
for k in range(2,9):
    km=KMeans(n_clusters=k,n_init=50,random_state=RANDOM_STATE,algorithm="lloyd")
    labels=km.fit_predict(ZD)
    counts=Counter(int(x) for x in labels)
    if min(counts.values())<5:
        k_results.append({"k":k,"valid":False,"cluster_counts":dict(sorted(counts.items())),"reason":"min_cluster_lt5"})
        continue
    sil=float(silhouette_score(ZD,labels))
    aris=[]
    nsub=max(k*2,int(round(len(ZD)*0.80)))
    for b in range(100):
        idx=np.sort(rng.choice(len(ZD),size=nsub,replace=False))
        bkm=KMeans(n_clusters=k,n_init=20,random_state=RANDOM_STATE+b+1,algorithm="lloyd")
        bkm.fit(ZD[idx])
        pred=bkm.predict(ZD)
        aris.append(float(adjusted_rand_score(labels,pred)))
    kr={
        "k":k,"valid":True,"cluster_counts":dict(sorted(counts.items())),
        "silhouette":sil,"bootstrap_ari_median":float(np.median(aris)),
        "bootstrap_ari_p25":float(np.quantile(aris,0.25)),
        "bootstrap_ari_p10":float(np.quantile(aris,0.10)),
    }
    k_results.append(kr); full_models[k]=(km,labels)

valid=[r for r in k_results if r.get("valid")]
assert valid
best_s=max(r["silhouette"] for r in valid)
near=sorted([r for r in valid if best_s-r["silhouette"]<0.01],key=lambda r:r["k"])
selected=near[0]
for cand in near[1:]:
    if cand["bootstrap_ari_median"]>=selected["bootstrap_ari_median"]+0.10:
        selected=cand
k=selected["k"]
km,labD=full_models[k]

# Projection only after k frozen.
all_strong_sorted=[]
for s in ("Discovery","Validation","Reserve"): all_strong_sorted.extend(strong_by_split[s])
Xall=scaler.transform(build_matrix(all_strong_sorted))
Zall=pca.transform(Xall)
lab_all=km.predict(Zall)
dist_all=np.linalg.norm(Zall-km.cluster_centers_[lab_all],axis=1)

assign={}
for u,label,dist in zip(all_strong_sorted,lab_all,dist_all):
    assign[u["position_id"]]={"cluster":int(label),"distance":float(dist)}

# Summary per neutral archetype.
clusters=[]
for cidx in range(k):
    g=[u for u in all_strong_sorted if assign[u["position_id"]]["cluster"]==cidx]
    split_counts={s:sum(u["split"]==s for u in g) for s in ("Discovery","Validation","Reserve")}
    mfe=[float(u["historical_max_mfe_pct"]) for u in g]
    pnl=[float(u["historical_realized_pnl_usdt"]) for u in g]
    rets=[float(u["historical_realized_pnl_pct"]) for u in g]
    wd=Counter(u["historical_wd1_outcome"] for u in g)
    distances_by_split={}
    for s in ("Discovery","Validation","Reserve"):
        ds=[assign[u["position_id"]]["distance"] for u in g if u["split"]==s]
        distances_by_split[s]={
            "n":len(ds),"median":quant(ds,0.5),"p90":quant(ds,0.9),"max":max(ds) if ds else None
        }
    clusters.append({
        "cluster":cidx,"neutral_label":f"SHORT_ARCHETYPE_{cidx}",
        "n":len(g),"share_pct":100*len(g)/99,
        "split_counts":split_counts,
        "mfe_median_pct":float(np.median(mfe)),"mfe_mean_pct":float(np.mean(mfe)),
        "historical_pnl_usdt":sum(pnl),"historical_avg_return_pct":float(np.mean(rets)),
        "historical_positive_n":sum(x>0 for x in pnl),
        "historical_positive_rate_pct":100*sum(x>0 for x in pnl)/len(g),
        "wd1_outcomes":dict(wd),
        "centroid_distance_by_split":distances_by_split,
    })

# Original numeric feature separation between clusters (Discovery only).
sep_features=[]
for c in numeric:
    vals=[as_float(fm[u["position_id"]].get(c)) for u in D]
    if sum(v is not None for v in vals)<0.95*len(vals): continue
    for cidx in range(k):
        y=[1 if int(lbl)==cidx else 0 for lbl in labD]
        auc=safe_auc(y,vals)
        if auc is None: continue
        sep_features.append({
            "feature":c,"cluster":cidx,"raw_auc_cluster_vs_other":auc,
            "separation_auc":max(auc,1-auc),
            "direction":"HIGH_IN_CLUSTER" if auc>=0.5 else "LOW_IN_CLUSTER",
            "cluster_median":float(np.median([v for v,lbl in zip(vals,labD) if v is not None and int(lbl)==cidx])),
            "other_median":float(np.median([v for v,lbl in zip(vals,labD) if v is not None and int(lbl)!=cidx])),
        })
sep_features.sort(key=lambda r:r["separation_auc"],reverse=True)

# Diagnostics for named feature families.
diag=[]
for feat in DIAGNOSTIC_FEATURES:
    if feat not in headers: continue
    rec={"feature":feat}
    for cidx in range(k):
        vals=[as_float(fm[u["position_id"]].get(feat)) for u in all_strong_sorted if assign[u["position_id"]]["cluster"]==cidx]
        vals=[v for v in vals if v is not None]
        rec[f"cluster_{cidx}_median"]=float(np.median(vals)) if vals else None
    diag.append(rec)

# Cancellation tests on top unique cluster-separating features.
top_unique=[]
for r in sep_features:
    if r["feature"] not in top_unique:
        top_unique.append(r["feature"])
    if len(top_unique)>=20: break

cancellation=[]
for feat in top_unique:
    loss_vals=[as_float(fm[u["position_id"]].get(feat)) for u in loss]
    agg_vals=[as_float(fm[u["position_id"]].get(feat)) for u in all_strong_sorted]+loss_vals
    agg_y=[1]*len(all_strong_sorted)+[0]*len(loss)
    agg_auc=safe_auc(agg_y,agg_vals)
    rec={"feature":feat,"aggregate_raw_auc_strong_vs_loss":agg_auc,
         "aggregate_separation_auc":max(agg_auc,1-agg_auc) if agg_auc is not None else None}
    raw_cluster_aucs=[]
    for cidx in range(k):
        cg=[u for u in all_strong_sorted if assign[u["position_id"]]["cluster"]==cidx]
        x=[as_float(fm[u["position_id"]].get(feat)) for u in cg]+loss_vals
        y=[1]*len(cg)+[0]*len(loss)
        auc=safe_auc(y,x)
        rec[f"cluster_{cidx}_raw_auc_vs_loss"]=auc
        rec[f"cluster_{cidx}_separation_auc_vs_loss"]=max(auc,1-auc) if auc is not None else None
        raw_cluster_aucs.append(auc)
    signs=[(a-0.5) for a in raw_cluster_aucs if a is not None]
    rec["opposite_direction_across_archetypes"]=bool(signs and min(signs)<0 and max(signs)>0)
    best_arch=max([max(a,1-a) for a in raw_cluster_aucs if a is not None],default=None)
    rec["dilution_gap_best_archetype_minus_aggregate"]=(best_arch-rec["aggregate_separation_auc"]) if best_arch is not None and rec["aggregate_separation_auc"] is not None else None
    cancellation.append(rec)

# Proportion stability vs D.
cluster_stability=[]
for cidx in range(k):
    d=sum(assign[u["position_id"]]["cluster"]==cidx for u in strong_by_split["Discovery"])/59
    v=sum(assign[u["position_id"]]["cluster"]==cidx for u in strong_by_split["Validation"])/27
    r=sum(assign[u["position_id"]]["cluster"]==cidx for u in strong_by_split["Reserve"])/13
    cluster_stability.append({"cluster":cidx,"D_share":d,"V_share":v,"R_share":r,
                              "max_abs_shift_pp":100*max(abs(v-d),abs(r-d))})

gates={
 "selected_k_ge_2":k>=2,
 "discovery_silhouette_ge_0p10":selected["silhouette"]>=0.10,
 "bootstrap_ari_median_ge_0p50":selected["bootstrap_ari_median"]>=0.50,
 "min_discovery_cluster_ge_5":min(Counter(labD).values())>=5,
 "validation_not_single_cluster":len({assign[u["position_id"]]["cluster"] for u in strong_by_split["Validation"]})>=2,
 "reserve_not_single_cluster":len({assign[u["position_id"]]["cluster"] for u in strong_by_split["Reserve"]})>=2,
}
status="PASS_WINNER_HETEROGENEITY" if all(gates.values()) else "NO_PASS_UNSTABLE_CLUSTERING"

# trade-level assignments
assignment_rows=[]
for u in all_strong_sorted:
    pid=u["position_id"]
    assignment_rows.append({
        "position_id":pid,"symbol":u["symbol"],"split":u["split"],
        "cluster":assign[pid]["cluster"],"neutral_label":f"SHORT_ARCHETYPE_{assign[pid]['cluster']}",
        "centroid_distance":assign[pid]["distance"],
        "historical_max_mfe_pct":u["historical_max_mfe_pct"],
        "historical_realized_pnl_usdt":u["historical_realized_pnl_usdt"],
        "historical_realized_pnl_pct":u["historical_realized_pnl_pct"],
        "historical_wd1_outcome":u["historical_wd1_outcome"],
    })
with (OUT/"sd1c_strong_winner_assignments.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(assignment_rows[0])); w.writeheader(); w.writerows(assignment_rows)
with (OUT/"sd1c_top_separating_features.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(sep_features[0])); w.writeheader(); w.writerows(sep_features)
with (OUT/"sd1c_cancellation_tests.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(cancellation[0])); w.writeheader(); w.writerows(cancellation)

payload={
 "stage":"SD-1C","status":status,
 "universe":{"strong_win_n":99,"Discovery":59,"Validation":27,"Reserve":13},
 "preprocessing":{
   "raw_t0_features":224,"numeric":len(numeric),"categorical":len(categorical),
   "eligible_numeric_before_corr_prune":len(eligible),"retained_numeric_after_corr_prune":len(retained),
   "corr_pruned_numeric":len(dropped_corr),"categorical_onehot_columns":len(cat_columns),
   "model_columns":len(model_columns),"pca_components":int(pca.n_components_),
   "pca_explained_variance":float(np.sum(pca.explained_variance_ratio_)),
 },
 "k_search":k_results,"selected_k":k,"selected_k_metrics":selected,
 "gates":gates,"clusters":clusters,"cluster_proportion_stability":cluster_stability,
 "top_30_cluster_separating_features":sep_features[:30],
 "diagnostic_feature_medians":diag,
 "cancellation_tests":cancellation,
 "model_feature_columns":model_columns,
}
(OUT/"sd1c_summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
print(json.dumps(payload,indent=2))