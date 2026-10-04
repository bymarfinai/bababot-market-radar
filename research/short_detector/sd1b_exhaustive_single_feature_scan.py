from __future__ import annotations
import bisect, csv, itertools, json, math, time
from pathlib import Path

VERSION="sd1b-exhaustive-single-feature-purepy-v1"
FEATURE_PATH=Path("/opt/core-app/data/wd5h1_thesis_labeled_features.csv")
UNIVERSE_PATH=Path("/tmp/sd1b/research/short_detector/results/sd1a_short_universe_655.csv")
OUT_DIR=Path("/tmp/sd1b_out")
OUT_DIR.mkdir(parents=True,exist_ok=True)

EXCLUDED={
    "f_decision_hour_utc","f_decision_hour_sin","f_decision_hour_cos",
    "f_decision_weekday_utc","f_latency_ai_queue_s",
    "f_latency_ai_execution_s","f_latency_stage11c_s",
}
SPLITS=("Discovery","Validation","Reserve")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def truth(v):
    return str(v).strip().lower() in {"1","true","yes"}

def as_float(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def phi(tp,selected,targets,n):
    if selected<=0 or selected>=n or targets<=0 or targets>=n: return 0.0
    fp=selected-tp; fn=targets-tp; tn=n-selected-fn
    den=math.sqrt(selected*targets*(n-targets)*(n-selected))
    return (tp*tn-fp*fn)/den if den else 0.0

features=read_csv(FEATURE_PATH)
universe=read_csv(UNIVERSE_PATH)
assert len(universe)==655
assert sum(truth(r["strong_win"]) for r in universe)==99
assert {s:sum(r["split"]==s for r in universe) for s in SPLITS}=={"Discovery":393,"Validation":131,"Reserve":131}

raw_map={r["meta_position_id"]:r for r in features}
rows=[]
for u in universe:
    rr=raw_map[u["position_id"]]
    rows.append({
        "raw":rr,
        "split":u["split"],
        "target":int(truth(u["strong_win"])),
        "pnl":float(u["historical_realized_pnl_usdt"]),
        "ret":float(u["historical_realized_pnl_pct"]),
    })
split_indices={s:[i for i,r in enumerate(rows) if r["split"]==s] for s in SPLITS}
targets={s:sum(rows[i]["target"] for i in split_indices[s]) for s in SPLITS}
sizes={s:len(split_indices[s]) for s in SPLITS}

headers=list(features[0])
feature_cols=[c for c in headers if c.startswith("f_") and c not in EXCLUDED]
assert len(feature_cols)==224,len(feature_cols)

numeric=[]; categorical=[]
for c in feature_cols:
    vals=[r["raw"].get(c) for r in rows if r["raw"].get(c) not in ("",None)]
    good=0
    for v in vals:
        if as_float(v) is not None: good+=1
    (numeric if vals and good/len(vals)>=0.999 else categorical).append(c)

def rule_select(rule,row):
    v=row["raw"].get(rule["feature"])
    if rule["rule_type"]=="in":
        return v in set(rule["values"])
    x=as_float(v)
    if x is None: return False
    if rule["rule_type"]=="<=": return x<=rule["high"]
    if rule["rule_type"]==">=": return x>=rule["low"]
    return rule["low"]<=x<=rule["high"]

def calc_metrics(rule,indices):
    n=len(indices); t=sum(rows[i]["target"] for i in indices)
    sel=[i for i in indices if rule_select(rule,rows[i])]
    selected=len(sel); tp=sum(rows[i]["target"] for i in sel)
    return {
        "n":n,"targets":t,"selected":selected,"captured":tp,
        "false_pos":selected-tp,
        "recall":tp/t if t else 0.0,
        "precision":tp/selected if selected else 0.0,
        "selection_rate":selected/n if n else 0.0,
        "phi":phi(tp,selected,t,n),
        "pnl":sum(rows[i]["pnl"] for i in sel),
        "avg_return":sum(rows[i]["ret"] for i in sel)/selected if selected else 0.0,
    }

tuned=[]
candidate_count=0
global_best_discovery={"phi":-999.0}
started=time.time()

D=split_indices["Discovery"]; V=split_indices["Validation"]
nd,nv=sizes["Discovery"],sizes["Validation"]; td,tv=targets["Discovery"],targets["Validation"]

for fi,c in enumerate(numeric,1):
    dpairs=sorted((as_float(rows[i]["raw"][c]),rows[i]["target"]) for i in D)
    vpairs=sorted((as_float(rows[i]["raw"][c]),rows[i]["target"]) for i in V)
    dpairs=[p for p in dpairs if p[0] is not None]
    vpairs=[p for p in vpairs if p[0] is not None]
    if len(dpairs)<10 or dpairs[0][0]==dpairs[-1][0]:
        continue

    # Discovery unique groups: value, cumulative count, cumulative target
    uvals=[]; cumcnt=[]; cumtp=[]
    totalc=0; totalt=0; j=0
    while j<len(dpairs):
        value=dpairs[j][0]; gc=0; gt=0
        while j<len(dpairs) and dpairs[j][0]==value:
            gc+=1; gt+=dpairs[j][1]; j+=1
        totalc+=gc; totalt+=gt
        uvals.append(value); cumcnt.append(totalc); cumtp.append(totalt)
    k=len(uvals)

    vvals=[p[0] for p in vpairs]
    vprefix=[0]
    for _,yy in vpairs: vprefix.append(vprefix[-1]+yy)

    # Precompute V boundaries corresponding to each D unique threshold.
    vle=[bisect.bisect_left(vvals,x) for x in uvals]
    vre=[bisect.bisect_right(vvals,x) for x in uvals]

    best=None
    best_score=-999.0

    def maybe_freeze(rule_type,low,high,dsel,dtp,vsel,vtp):
        nonlocal_marker=None
        return

    # <= and >=
    candidate_count += 2*k
    for a in range(k):
        # <=
        dsel=cumcnt[a]; dtp=cumtp[a]
        vsel=vre[a]; vtp=vprefix[vsel]
        dph=phi(dtp,dsel,td,nd); vph=phi(vtp,vsel,tv,nv)
        if 5<=dsel<=nd-5 and dph>global_best_discovery["phi"]:
            global_best_discovery={"feature":c,"rule_type":"<=","low":None,"high":uvals[a],"phi":dph,"selected":dsel,"captured":dtp}
        if 5<=dsel<=nd-5 and 5<=vsel<=nv-5:
            sc=min(dph,vph)
            if sc>best_score:
                best_score=sc; best={"feature":c,"rule_type":"<=","low":None,"high":uvals[a],"score":sc,"discovery_phi":dph,"validation_phi":vph}
        # >=
        d_before=cumcnt[a-1] if a else 0; t_before=cumtp[a-1] if a else 0
        dsel=len(dpairs)-d_before; dtp=totalt-t_before
        vleft=vle[a]; vsel=len(vpairs)-vleft; vtp=vprefix[-1]-vprefix[vleft]
        dph=phi(dtp,dsel,td,nd); vph=phi(vtp,vsel,tv,nv)
        if 5<=dsel<=nd-5 and dph>global_best_discovery["phi"]:
            global_best_discovery={"feature":c,"rule_type":">=","low":uvals[a],"high":None,"phi":dph,"selected":dsel,"captured":dtp}
        if 5<=dsel<=nd-5 and 5<=vsel<=nv-5:
            sc=min(dph,vph)
            if sc>best_score:
                best_score=sc; best={"feature":c,"rule_type":">=","low":uvals[a],"high":None,"score":sc,"discovery_phi":dph,"validation_phi":vph}

    # exact contiguous bands
    candidate_count += k*(k+1)//2
    for a in range(k):
        d_before=cumcnt[a-1] if a else 0; t_before=cumtp[a-1] if a else 0
        vleft=vle[a]
        for b in range(a,k):
            dsel=cumcnt[b]-d_before; dtp=cumtp[b]-t_before
            vright=vre[b]; vsel=vright-vleft; vtp=vprefix[vright]-vprefix[vleft]
            dph=phi(dtp,dsel,td,nd)
            if 5<=dsel<=nd-5 and dph>global_best_discovery["phi"]:
                global_best_discovery={"feature":c,"rule_type":"band","low":uvals[a],"high":uvals[b],"phi":dph,"selected":dsel,"captured":dtp}
            if not (5<=dsel<=nd-5 and 5<=vsel<=nv-5):
                continue
            vph=phi(vtp,vsel,tv,nv); sc=min(dph,vph)
            if sc>best_score:
                best_score=sc; best={"feature":c,"rule_type":"band","low":uvals[a],"high":uvals[b],"score":sc,"discovery_phi":dph,"validation_phi":vph}

    if best is None:
        continue
    # Rule is now frozen on D+V. Only now open Reserve for this feature.
    for s in SPLITS: best[s.lower()]=calc_metrics(best,split_indices[s])
    best["full"]=calc_metrics(best,list(range(len(rows))))
    best["reserve_opened_after_freeze"]=True
    tuned.append(best)
    if fi%20==0:
        print(f"NUMERIC {fi}/{len(numeric)} candidates={candidate_count} elapsed={time.time()-started:.1f}s",flush=True)

for c in categorical:
    arr_d=[rows[i]["raw"].get(c,"") for i in D]
    vals=sorted(set(arr_d))
    subsets=([comb for kk in range(1,len(vals)) for comb in itertools.combinations(vals,kk)] if 1<len(vals)<=8 else [(v,) for v in vals])
    best=None; best_score=-999.0
    for comb in subsets:
        candidate_count+=1
        rule={"feature":c,"rule_type":"in","values":list(comb)}
        dm=calc_metrics(rule,D); vm=calc_metrics(rule,V)
        if 5<=dm["selected"]<=nd-5 and dm["phi"]>global_best_discovery["phi"]:
            global_best_discovery={"feature":c,"rule_type":"in","values":list(comb),"phi":dm["phi"],"selected":dm["selected"],"captured":dm["captured"]}
        if not (5<=dm["selected"]<=nd-5 and 5<=vm["selected"]<=nv-5): continue
        sc=min(dm["phi"],vm["phi"])
        if sc>best_score:
            best_score=sc; best={**rule,"score":sc,"discovery_phi":dm["phi"],"validation_phi":vm["phi"]}
    if best is None: continue
    for s in SPLITS: best[s.lower()]=calc_metrics(best,split_indices[s])
    best["full"]=calc_metrics(best,list(range(len(rows))))
    best["reserve_opened_after_freeze"]=True
    tuned.append(best)

tuned.sort(key=lambda r:(r["score"],r["reserve"]["phi"]),reverse=True)
strong=[r for r in tuned if r["discovery"]["phi"]>=0.50 and r["validation"]["phi"]>=0.50 and r["reserve"]["phi"]>=0.50]

flat=[]
for rank,r in enumerate(tuned,1):
    flat.append({
        "rank":rank,"feature":r["feature"],"rule_type":r["rule_type"],
        "low":r.get("low"),"high":r.get("high"),"values":"|".join(map(str,r.get("values",[]))),
        "dv_stability_score":r["score"],
        "d_selected":r["discovery"]["selected"],"d_captured":r["discovery"]["captured"],"d_precision":r["discovery"]["precision"],"d_recall":r["discovery"]["recall"],"d_phi":r["discovery"]["phi"],
        "v_selected":r["validation"]["selected"],"v_captured":r["validation"]["captured"],"v_precision":r["validation"]["precision"],"v_recall":r["validation"]["recall"],"v_phi":r["validation"]["phi"],
        "r_selected":r["reserve"]["selected"],"r_captured":r["reserve"]["captured"],"r_precision":r["reserve"]["precision"],"r_recall":r["reserve"]["recall"],"r_phi":r["reserve"]["phi"],
        "full_selected":r["full"]["selected"],"full_captured":r["full"]["captured"],"full_precision":r["full"]["precision"],"full_recall":r["full"]["recall"],"full_phi":r["full"]["phi"],
        "full_pnl":r["full"]["pnl"],"full_avg_return":r["full"]["avg_return"],
        "strong_all_splits":r in strong,
    })
with (OUT_DIR/"sd1b_frozen_single_feature_rules.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)

payload={
    "stage":"SD-1B","version":VERSION,
    "status":"PASS_STRONG_SINGLE_FEATURE" if strong else "FAIL_NO_STRONG_SINGLE_FEATURE",
    "universe":{"n":655,"strong_win_n":99,"non_target_n":556,"splits":{"Discovery":393,"Validation":131,"Reserve":131}},
    "features":{"raw_f_fields":231,"excluded":sorted(EXCLUDED),"modeled":len(feature_cols),"numeric":len(numeric),"categorical":len(categorical)},
    "candidate_rules":candidate_count,
    "selection":"per-feature candidate maximizes min(D phi, V phi); Reserve evaluated only after freeze",
    "strong_phi_threshold":0.50,
    "strong_rule_count":len(strong),
    "evaluable_frozen_feature_rules":len(tuned),
    "unevaluable_or_constant_features":len(feature_cols)-len(tuned),
    "global_best_discovery_only":global_best_discovery,
    "best_frozen_rule":tuned[0],
    "top_25_frozen_rules":tuned[:25],
    "runtime_seconds":time.time()-started,
}
(OUT_DIR/"sd1b_summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
print(json.dumps(payload,indent=2),flush=True)