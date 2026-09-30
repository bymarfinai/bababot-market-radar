#!/usr/bin/env python3
import csv, json, math, statistics, hashlib, zipfile, random, os
from pathlib import Path
from collections import defaultdict

ROOT=Path("/opt/core-app/app")
S1ZIP=ROOT/"dashboard/audit/stage1_adaptive_profit_protection_497trades.zip"
S3ZIP=ROOT/"dashboard/audit/stage3_static_frontier_497trades.zip"
OUT=Path("/tmp/stage4_adaptive_feature_discovery")
OUT.mkdir(parents=True,exist_ok=True)

S1SHA="bd6491e74c45a0859cc4b998f4e2aa85902cca76db45e4ecee028a5b552ca4a4"
S3SHA="985bdc104c6bb9d23ab9383d8dacd694491dc1ce4133a5f92becfbae90e6ea57"
CUTOFF=1790687518406
THRESHOLDS=[0.20,0.30,0.40,0.50]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def f(x):
    try:
        if x is None or x=="": return None
        return float(x)
    except:return None
def ii(x):
    try:return int(float(x))
    except:return None
def truth(x):return str(x).lower()=="true"
def med(xs):
    z=sorted(x for x in xs if x is not None and math.isfinite(x))
    if not z:return None
    n=len(z);return z[n//2] if n%2 else (z[n//2-1]+z[n//2])/2
def mean(xs):
    z=[x for x in xs if x is not None and math.isfinite(x)]
    return sum(z)/len(z) if z else None
def std(xs,mu=None):
    z=[x for x in xs if x is not None and math.isfinite(x)]
    if len(z)<2:return 1.0
    mu=sum(z)/len(z) if mu is None else mu
    s=math.sqrt(sum((x-mu)**2 for x in z)/len(z))
    return s if s>1e-12 else 1.0
def pct(a,b):return 100*a/b if b else None
def side_adjust(side,x):
    if x is None:return None
    return x if side=="LONG" else -x
def safe_ratio(a,b):
    if a is None or b is None or abs(b)<1e-12:return None
    return a/b
def parse_json(x,default=None):
    if default is None:default={}
    try:
        if x is None or x=="":return default
        return json.loads(x)
    except:return default
def write_csv(path,rows):
    rows=list(rows)
    if not rows:
        Path(path).write_text("",encoding="utf-8");return
    fields=[];seen=set()
    for r in rows:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    with open(path,"w",newline="",encoding="utf-8-sig") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)

assert sha(S1ZIP)==S1SHA,(sha(S1ZIP),S1SHA)
assert sha(S3ZIP)==S3SHA,(sha(S3ZIP),S3SHA)

def readzipcsv(zpath,name):
    with zipfile.ZipFile(zpath) as z:
        raw=z.read(name).decode("utf-8-sig").splitlines()
    return list(csv.DictReader(raw))

MASTER_ROWS=readzipcsv(S1ZIP,"stage1_trade_master.csv")
TIMELINE_RAW=readzipcsv(S1ZIP,"stage1_timeline_1m.csv")
EVENTS=readzipcsv(S1ZIP,"stage1_events.csv")
MASTER={str(r["position_id"]):r for r in MASTER_ROWS}

TL=defaultdict(list); excluded_postclose=0
for r in TIMELINE_RAW:
    pid=str(r["position_id"]);m=MASTER.get(pid)
    if not m:continue
    if ii(r["candle_close_ms"])<=ii(m["closed_at_ms"]):
        TL[pid].append(r)
    else:
        excluded_postclose+=1
for pid in TL:TL[pid].sort(key=lambda x:ii(x["candle_close_ms"]) or 0)

EV=defaultdict(list)
for e in EVENTS:EV[str(e["position_id"])].append(e)
for pid in EV:EV[pid].sort(key=lambda x:ii(x.get("event_time_ms")) or 0)

def first_reduce_ts(pid):
    z=[ii(e.get("event_time_ms")) for e in EV.get(pid,[]) if e.get("event_type")=="ORDER" and e.get("action")=="REDUCE"]
    z=[x for x in z if x is not None]
    return min(z) if z else None

def latest_thesis(pid,ts,max_age_min=10):
    best=None
    for e in EV.get(pid,[]):
        et=ii(e.get("event_time_ms"))
        if et is None or et>ts:break
        if e.get("event_type")=="EVALUATION" and e.get("layer")=="THESIS_5M":
            best=e
    if not best:return None
    age=(ts-ii(best["event_time_ms"]))/60000.0
    return best if age<=max_age_min else None

def htf_features(pid,side,ts):
    e=latest_thesis(pid,ts)
    empty={
      "htf_available":0.0,"htf_age_min":None,"htf_ret_5m_side":None,"htf_ret_15m_side":None,"htf_ret_1h_side":None,
      "htf_regime_score":None,"htf_structure_score":None,"htf_taker_score":None,"htf_oi_score":None,
      "htf_stage_score":None,"htf_opposing_score":None,"htf_score_edge":None,"htf_health_score":None,
      "htf_contradiction_count":None
    }
    if not e:return empty
    snap=parse_json(e.get("snapshot_json"),{})
    sign=1.0 if side=="LONG" else -1.0
    regime=str(snap.get("market_regime") or "SIDEWAYS")
    ar="BULL" if side=="LONG" else "BEAR";orr="BEAR" if side=="LONG" else "BULL"
    regime_score=1.0 if regime==ar else -1.0 if regime==orr else 0.0
    structure=str(snap.get("structure_status") or "")
    favorable={"LONG":{"BREAKOUT","FAILED_BREAKDOWN"},"SHORT":{"BREAKDOWN","FAILED_BREAKOUT"}}[side]
    adverse={"LONG":{"BREAKDOWN"},"SHORT":{"BREAKOUT"}}[side]
    structure_score=1.0 if structure in favorable else -1.0 if structure in adverse else 0.0
    taker=str(snap.get("taker_bias") or "BALANCED")
    at="BUY" if side=="LONG" else "SELL";ot="SELL" if side=="LONG" else "BUY"
    taker_score=1.0 if taker==at else -1.0 if taker==ot else 0.0
    oi=str(snap.get("oi_interpretation") or "UNRESOLVED")
    aio="FRESH_LONG_PARTICIPATION" if side=="LONG" else "FRESH_SHORT_PARTICIPATION"
    oio="FRESH_SHORT_PARTICIPATION" if side=="LONG" else "FRESH_LONG_PARTICIPATION"
    oi_score=1.0 if oi==aio else -1.0 if oi==oio else 0.0
    stage=str(snap.get("stage") or "")
    stage_score=1.0 if stage=="EXPANSION" else 0.5 if stage=="IGNITION" else -1.0 if stage=="EXHAUSTION" else 0.0
    ls=f(snap.get("long_score")) or 0.0;ss=f(snap.get("short_score")) or 0.0
    opposing=ss if side=="LONG" else ls
    contradictions=parse_json(e.get("contradictions_json"),[])
    return {
      "htf_available":1.0,
      "htf_age_min":(ts-ii(e["event_time_ms"]))/60000.0,
      "htf_ret_5m_side":sign*(f(snap.get("ret_5m_pct")) or 0.0),
      "htf_ret_15m_side":sign*(f(snap.get("ret_15m_pct")) or 0.0),
      "htf_ret_1h_side":sign*(f(snap.get("ret_1h_pct")) or 0.0),
      "htf_regime_score":regime_score,"htf_structure_score":structure_score,"htf_taker_score":taker_score,
      "htf_oi_score":oi_score,"htf_stage_score":stage_score,"htf_opposing_score":opposing,
      "htf_score_edge":abs(ls-ss),"htf_health_score":f(e.get("health_score")),
      "htf_contradiction_count":float(len(contradictions)) if isinstance(contradictions,list) else None
    }

ANCHORS=[]
htf_future_violation=0
for pid,m in MASTER.items():
    rows=TL.get(pid,[])
    side=str(m["side"]);red=first_reduce_ts(pid)
    econ=[f(r.get("economic_pnl_if_closed_now")) for r in rows]
    peak=[f(r.get("peak_economic_pnl")) for r in rows]
    gb=[f(r.get("economic_giveback_ratio")) for r in rows]
    for th in THRESHOLDS:
        hit=None
        for i in range(len(rows)):
            if peak[i] is not None and peak[i]>0 and gb[i] is not None and gb[i]>=th:
                hit=i;break
        if hit is None:continue
        r=rows[hit];ts=ii(r["candle_close_ms"]);known_peak=peak[hit]
        fut=[x for x in econ[hit+1:] if x is not None]
        new_peak=bool(fut and max(fut)>known_peak+1e-12)
        fut5=[]
        for j in range(hit+1,len(rows)):
            t=ii(rows[j]["candle_close_ms"])
            if t is not None and t<=ts+5*60000 and econ[j] is not None:fut5.append(econ[j])
        new_peak5=bool(fut5 and max(fut5)>known_peak+1e-12)
        sr1=side_adjust(side,f(r.get("ret_1m_pct")));sr3=side_adjust(side,f(r.get("ret_3m_pct")))
        share=f(r.get("taker_buy_share_1m"))
        taker_strength=None if share is None else ((share-0.5) if side=="LONG" else (0.5-share))
        oi=f(r.get("oi_change_5m_pct"));rv5=f(r.get("rv5_1m_pct"));rv15=f(r.get("rv15_1m_pct"))
        favorable=truth(r.get("micro_break_up")) if side=="LONG" else truth(r.get("micro_break_down"))
        adverse=truth(r.get("micro_break_down")) if side=="LONG" else truth(r.get("micro_break_up"))
        rh=f(r.get("rolling_5m_high"));rl=f(r.get("rolling_5m_low"));cl=f(r.get("close"))
        loc=None if None in (rh,rl,cl) or abs(rh-rl)<1e-12 else (cl-rl)/(rh-rl)
        if side=="SHORT" and loc is not None:loc=1.0-loc
        start=max(0,hit-5);new_peak_count=0
        prev=None
        for j in range(start,hit+1):
            pj=peak[j]
            if prev is not None and pj is not None and pj>prev+1e-12:new_peak_count+=1
            if pj is not None:prev=pj
        prior_reduce=1.0 if red is not None and red<=ts else 0.0
        minutes_since_reduce=(ts-red)/60000.0 if prior_reduce else None
        htf=htf_features(pid,side,ts)
        if htf["htf_available"]:
            e=latest_thesis(pid,ts)
            if e and ii(e.get("event_time_ms"))>ts:htf_future_violation+=1
        ANCHORS.append({
          "position_id":pid,"symbol":m["symbol"],"side":side,"opened_at_ms":ii(m["opened_at_ms"]),
          "closed_at_ms":ii(m["closed_at_ms"]),"anchor_ts":ts,"giveback_threshold":th,
          "terminal_no_new_peak":1 if not new_peak else 0,"new_peak_before_close":1 if new_peak else 0,
          "new_peak_within_5m":1 if new_peak5 else 0,
          "peak_economic_roi_pct":f(r.get("peak_economic_roi_pct")),
          "time_since_peak_min":(f(r.get("time_since_economic_peak_sec")) or 0.0)/60.0,
          "time_since_price_peak_min":(f(r.get("time_since_price_peak_sec")) or 0.0)/60.0,
          "new_peak_count_last5m":float(new_peak_count),
          "side_ret_1m_pct":sr1,"side_ret_3m_pct":sr3,
          "micro_break_favorable":1.0 if favorable else 0.0,"micro_break_against":1.0 if adverse else 0.0,
          "close_location_5m_side":loc,"taker_directional_strength":taker_strength,
          "oi_change_5m_pct":oi,
          "oi_adverse_building":1.0 if oi is not None and oi>=0.05 and sr3 is not None and sr3<=-0.10 else 0.0,
          "oi_aligned_building":1.0 if oi is not None and oi>=0.05 and sr3 is not None and sr3>=0.10 else 0.0,
          "rv5_1m_pct":rv5,"rv15_1m_pct":rv15,"rv5_over_rv15":safe_ratio(rv5,rv15),
          "prior_reduce":prior_reduce,"minutes_since_reduce":minutes_since_reduce,**htf
        })

# Chronological trade split 60/20/20; no position appears in more than one split.
ordered=sorted(MASTER.values(),key=lambda r:ii(r["opened_at_ms"]) or 0)
n=len(ordered);c1=int(math.floor(n*0.60));c2=int(math.floor(n*0.80))
SPLIT={}
for idx,m in enumerate(ordered):
    SPLIT[str(m["position_id"])]="DEV" if idx<c1 else ("OOS_MID" if idx<c2 else "OOS_LATE")
for r in ANCHORS:r["time_split"]=SPLIT[r["position_id"]]
write_csv(OUT/"stage4_anchor_dataset.csv",ANCHORS)

FAMILIES={
 "PEAK_SIZE":["peak_economic_roi_pct"],
 "PEAK_RECENCY":["time_since_peak_min","time_since_price_peak_min","new_peak_count_last5m"],
 "MICRO_STRUCTURE":["side_ret_1m_pct","side_ret_3m_pct","micro_break_favorable","micro_break_against","close_location_5m_side"],
 "TAKER_FLOW":["taker_directional_strength"],
 "OI":["oi_change_5m_pct","oi_adverse_building","oi_aligned_building"],
 "VOLATILITY":["rv5_1m_pct","rv15_1m_pct","rv5_over_rv15"],
 "PRIOR_REDUCE":["prior_reduce","minutes_since_reduce"],
 "HTF_THESIS":["htf_available","htf_age_min","htf_ret_5m_side","htf_ret_15m_side","htf_ret_1h_side","htf_regime_score",
               "htf_structure_score","htf_taker_score","htf_oi_score","htf_stage_score","htf_opposing_score","htf_score_edge",
               "htf_health_score","htf_contradiction_count"]
}
BASE=["peak_economic_roi_pct"]

def fit_transform(train,rows,cols):
    stats={}
    for c in cols:
        vals=[f(r.get(c)) for r in train]
        vals=[x for x in vals if x is not None and math.isfinite(x)]
        m=med(vals) if vals else 0.0
        mu=mean(vals) if vals else 0.0
        sd=std(vals,mu) if vals else 1.0
        stats[c]=(m,mu,sd)
    X=[]
    for r in rows:
        row=[1.0]
        for c in cols:
            v=f(r.get(c));m,mu,sd=stats[c]
            miss=1.0 if v is None or not math.isfinite(v) else 0.0
            if miss:v=m
            row.extend([(v-mu)/sd,miss])
        X.append(row)
    return X,stats

def sigmoid(z):
    if z>=0:
        e=math.exp(-min(z,60));return 1/(1+e)
    e=math.exp(max(z,-60));return e/(1+e)

def logistic_fit(train,cols,iters=260,lr=0.055,l2=0.08):
    X,stats=fit_transform(train,train,cols)
    y=[int(r["terminal_no_new_peak"]) for r in train]
    p1=sum(y)/len(y) if y else .5;p0=1-p1
    w1=0.5/max(p1,1e-6);w0=0.5/max(p0,1e-6)
    beta=[0.0]*len(X[0])
    for _ in range(iters):
        grad=[0.0]*len(beta)
        for xi,yi in zip(X,y):
            pr=sigmoid(sum(b*x for b,x in zip(beta,xi)))
            wt=w1 if yi else w0
            err=(pr-yi)*wt
            for j,x in enumerate(xi):grad[j]+=err*x
        n=max(len(X),1)
        for j in range(len(beta)):
            reg=0.0 if j==0 else l2*beta[j]
            beta[j]-=lr*(grad[j]/n+reg)
    return beta,stats

def predict(rows,cols,beta,stats):
    out=[]
    for r in rows:
        x=[1.0]
        for c in cols:
            v=f(r.get(c));m,mu,sd=stats[c]
            miss=1.0 if v is None or not math.isfinite(v) else 0.0
            if miss:v=m
            x.extend([(v-mu)/sd,miss])
        out.append(sigmoid(sum(b*q for b,q in zip(beta,x))))
    return out

def auc(y,p):
    pairs=sorted(zip(p,y),key=lambda x:x[0])
    n1=sum(y);n0=len(y)-n1
    if n1==0 or n0==0:return None
    rank_sum=0.0;i=0;rank=1
    while i<len(pairs):
        j=i+1
        while j<len(pairs) and abs(pairs[j][0]-pairs[i][0])<1e-15:j+=1
        avg=(rank+(rank+(j-i)-1))/2.0
        rank_sum+=avg*sum(v for _,v in pairs[i:j])
        rank+=j-i;i=j
    return (rank_sum-n1*(n1+1)/2)/(n1*n0)

def brier(y,p):
    return sum((a-b)**2 for a,b in zip(y,p))/len(y) if y else None

def eval_model(dev,test,cols):
    if len(dev)<20 or len(test)<10:return None
    ydev=[int(r["terminal_no_new_peak"]) for r in dev]
    yte=[int(r["terminal_no_new_peak"]) for r in test]
    if len(set(ydev))<2 or len(set(yte))<2:return None
    beta,stats=logistic_fit(dev,cols)
    pp=predict(test,cols,beta,stats)
    return {"auc":auc(yte,pp),"brier":brier(yte,pp),"n":len(test),"terminal_rate":sum(yte)/len(yte)}

FAMILY_RESULTS=[]
FEATURE_RESULTS=[]
for th in THRESHOLDS:
    cohort=[r for r in ANCHORS if abs(r["giveback_threshold"]-th)<1e-12]
    dev=[r for r in cohort if r["time_split"]=="DEV"];mid=[r for r in cohort if r["time_split"]=="OOS_MID"];late=[r for r in cohort if r["time_split"]=="OOS_LATE"]
    intercept_mid=eval_model(dev,mid,[])
    intercept_late=eval_model(dev,late,[])
    base_mid=eval_model(dev,mid,BASE);base_late=eval_model(dev,late,BASE)
    for fam,fc in FAMILIES.items():
        if fam=="PEAK_SIZE":
            cols=BASE
            bm=intercept_mid;bl=intercept_late
        else:
            cols=list(dict.fromkeys(BASE+fc));bm=base_mid;bl=base_late
        em=eval_model(dev,mid,cols);el=eval_model(dev,late,cols)
        cov=[]
        for r in cohort:
            if fam=="HTF_THESIS":
                anyv=(f(r.get("htf_available")) or 0)>0
            else:
                anyv=any(f(r.get(c)) is not None for c in fc)
            cov.append(1 if anyv else 0)
        dm=None if not em or not bm else em["auc"]-bm["auc"]
        dl=None if not el or not bl else el["auc"]-bl["auc"]
        FAMILY_RESULTS.append({
          "giveback_threshold":th,"family":fam,"n_total":len(cohort),"n_dev":len(dev),"n_oos_mid":len(mid),"n_oos_late":len(late),
          "coverage_pct":pct(sum(cov),len(cov)) if cov else None,
          "baseline_auc_mid":None if not bm else bm["auc"],"baseline_auc_late":None if not bl else bl["auc"],
          "family_auc_mid":None if not em else em["auc"],"family_auc_late":None if not el else el["auc"],
          "delta_auc_mid":dm,"delta_auc_late":dl,"mean_delta_auc":mean([dm,dl]),
          "stable_nonnegative_both":bool(dm is not None and dl is not None and dm>=-0.01 and dl>=-0.01 and mean([dm,dl])>0.005)
        })
    if abs(th-.30)<1e-12:
        for fam,fc in FAMILIES.items():
            for col in fc:
                bm=intercept_mid if fam=="PEAK_SIZE" else base_mid
                bl=intercept_late if fam=="PEAK_SIZE" else base_late
                cols=[col] if fam=="PEAK_SIZE" else list(dict.fromkeys(BASE+[col]))
                em=eval_model(dev,mid,cols);el=eval_model(dev,late,cols)
                dm=None if not em or not bm else em["auc"]-bm["auc"]
                dl=None if not el or not bl else el["auc"]-bl["auc"]
                cov=pct(sum(1 for r in cohort if f(r.get(col)) is not None),len(cohort))
                FEATURE_RESULTS.append({
                  "family":fam,"feature":col,"n_total":len(cohort),"coverage_pct":cov,
                  "auc_mid":None if not em else em["auc"],"auc_late":None if not el else el["auc"],
                  "delta_auc_mid":dm,"delta_auc_late":dl,"mean_delta_auc":mean([dm,dl]),
                  "stable_nonnegative_both":bool(dm is not None and dl is not None and dm>=-0.01 and dl>=-0.01 and mean([dm,dl])>0.005)
                })

SUMMARY=[]
for fam in FAMILIES:
    z=[r for r in FAMILY_RESULTS if r["family"]==fam]
    z30=next((r for r in z if abs(r["giveback_threshold"]-.30)<1e-12),None)
    stable=sum(1 for r in z if r["stable_nonnegative_both"])
    d30=z30["mean_delta_auc"] if z30 else None
    cov30=z30["coverage_pct"] if z30 else None
    if z30 and z30["stable_nonnegative_both"] and stable>=2 and d30 is not None and d30>=0.03 and (cov30 or 0)>=50:
        status="KEEP_STRONG"
    elif z30 and z30["stable_nonnegative_both"] and stable>=2 and d30 is not None and d30>=0.01 and (cov30 or 0)>=50:
        status="KEEP_WEAK"
    elif (cov30 or 0)<50:
        status="DEFER_LOW_COVERAGE"
    else:
        status="DISCARD_UNSTABLE"
    SUMMARY.append({
      "family":fam,"screen_status":status,"stable_threshold_count":stable,
      "delta_auc_at_30pct":d30,"coverage_at_30pct":cov30,
      "mean_delta_auc_across_thresholds":mean([r["mean_delta_auc"] for r in z]),
      "feature_count":len(FAMILIES[fam])
    })

# Primary 30% descriptive split.
primary=[r for r in ANCHORS if abs(r["giveback_threshold"]-.30)<1e-12]
DESC=[]
for label,name in [(0,"RECOVER_NEW_PEAK"),(1,"TERMINAL_NO_NEW_PEAK")]:
    z=[r for r in primary if r["terminal_no_new_peak"]==label]
    for c in ["peak_economic_roi_pct","time_since_peak_min","side_ret_1m_pct","side_ret_3m_pct","taker_directional_strength",
              "oi_change_5m_pct","rv15_1m_pct","rv5_over_rv15","prior_reduce","htf_available","htf_ret_15m_side","htf_ret_1h_side",
              "htf_regime_score","htf_structure_score","htf_oi_score","htf_health_score","htf_contradiction_count"]:
        vals=[f(r.get(c)) for r in z]
        vals=[x for x in vals if x is not None]
        DESC.append({"group":name,"feature":c,"n_group":len(z),"n_available":len(vals),"median":med(vals),"mean":mean(vals)})

# Bootstrap AUC delta CI at 30% for family models on combined OOS. Model remains trained on DEV.
BOOT=[]
cohort=primary;dev=[r for r in cohort if r["time_split"]=="DEV"];oos=[r for r in cohort if r["time_split"]!="DEV"]
random.seed(42)
for fam,fc in FAMILIES.items():
    if fam=="PEAK_SIZE":
        basecols=[];cols=BASE
    else:
        basecols=BASE;cols=list(dict.fromkeys(BASE+fc))
    if len(dev)<20 or len(oos)<20:continue
    try:
        b0,s0=logistic_fit(dev,basecols);b1,s1=logistic_fit(dev,cols)
        p0=predict(oos,basecols,b0,s0);p1=predict(oos,cols,b1,s1);y=[int(r["terminal_no_new_peak"]) for r in oos]
        point=auc(y,p1)-auc(y,p0)
        ds=[]
        for _ in range(200):
            idx=[random.randrange(len(oos)) for __ in range(len(oos))]
            yy=[y[i] for i in idx]
            if len(set(yy))<2:continue
            ds.append(auc(yy,[p1[i] for i in idx])-auc(yy,[p0[i] for i in idx]))
        ds.sort()
        lo=ds[int(.025*(len(ds)-1))] if ds else None;hi=ds[int(.975*(len(ds)-1))] if ds else None
        BOOT.append({"family":fam,"oos_combined_n":len(oos),"delta_auc_point":point,"bootstrap_p025":lo,"bootstrap_p975":hi,
                     "ci_excludes_zero":bool(lo is not None and lo>0)})
    except Exception as e:
        BOOT.append({"family":fam,"error":repr(e)})

write_csv(OUT/"stage4_family_results.csv",FAMILY_RESULTS)
write_csv(OUT/"stage4_feature_results_30pct.csv",sorted(FEATURE_RESULTS,key=lambda x:(x["mean_delta_auc"] is not None,x["mean_delta_auc"] or -999),reverse=True))
write_csv(OUT/"stage4_keep_discard_summary.csv",SUMMARY)
write_csv(OUT/"stage4_primary30_descriptive.csv",DESC)
write_csv(OUT/"stage4_bootstrap_30pct.csv",BOOT)

# Stage3 reference
with zipfile.ZipFile(S3ZIP) as z:
    ref=z.read("stage3_envelope_summary.csv").decode("utf-8-sig")
(OUT/"stage4_stage3_reference.csv").write_text(ref,encoding="utf-8-sig")
with zipfile.ZipFile(S3ZIP) as z:
    stage3qa=json.loads(z.read("stage3_qa.json").decode("utf-8"))

splits=defaultdict(set)
for r in ANCHORS:splits[r["position_id"]].add(r["time_split"])
split_leak=sum(1 for v in splits.values() if len(v)>1)
anchor_counts={str(int(th*100)):sum(1 for r in ANCHORS if abs(r["giveback_threshold"]-th)<1e-12) for th in THRESHOLDS}
cohort_counts={str(int(th*100)):sum(1 for r in ANCHORS if abs(r["giveback_threshold"]-th)<1e-12 and (r["peak_economic_roi_pct"] or 0)>=.5) for th in THRESHOLDS}
qa={
 "stage":"Stage 4 - Adaptive Feature Discovery","status":"PASS",
 "input":{"stage1_sha256":sha(S1ZIP),"stage3_sha256":sha(S3ZIP),"frozen_trade_count":len(MASTER),"frozen_cutoff_ms":CUTOFF},
 "causality":{"strict_preclose_rows":sum(len(v) for v in TL.values()),"excluded_postclose_overlap_rows":excluded_postclose,
              "htf_future_event_violations":htf_future_violation,"position_split_leak_count":split_leak,
              "future_outcome_used_only_as_label":True},
 "split":{"method":"chronological by trade opened_at_ms","DEV":"first 60% trades","OOS_MID":"next 20%","OOS_LATE":"last 20%"},
 "anchors":{"all_first_crossings":len(ANCHORS),"by_threshold":anchor_counts,"large_peak_ge_0_5_sensitivity_by_threshold":cohort_counts},
 "screen_rule":{"baseline":"peak economic ROI only (intercept-only for PEAK_SIZE family)",
                "keep_strong":"30% anchor stable both OOS, >=2 thresholds stable, mean delta AUC >=0.03, coverage >=50%",
                "keep_weak":"same but mean delta AUC >=0.01",
                "defer":"coverage <50%","otherwise":"discard unstable"},
 "stage3_reference":{"best_static_total_net_pnl":stage3qa["frontier_acceptance"]["best_static_total_net_pnl"],
                     "best_static_econ_ge2_capture":stage3qa["frontier_acceptance"]["best_static_econ_ge2_capture"],
                     "best_static_mfe2_capture":stage3qa["frontier_acceptance"]["best_static_mfe2_capture"]},
 "family_decisions":{r["family"]:r["screen_status"] for r in SUMMARY},
 "notes":["Stage 4 selects feature families only; it does not select V4 action thresholds or lock coefficients.",
          "HTF_THESIS features use only persisted THESIS_5M evaluations no older than 10 minutes and event_time <= anchor.",
          "No missing 15-second HOLD states are invented.","All models are trained on DEV only."]}
if len(MASTER)!=497 or excluded_postclose!=497 or htf_future_violation or split_leak:qa["status"]="FAIL"
(OUT/"stage4_qa.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")
manifest={
 "stage":"Adaptive Profit Protection Discovery - Stage 4 Adaptive Feature Discovery",
 "status":"COMPLETE_QA_PASS" if qa["status"]=="PASS" else "QA_FAIL","code_version":"stage4-feature-screen-v1-stdlib",
 "stage1_sha256":S1SHA,"stage3_sha256":S3SHA,"frozen_cutoff_ms":CUTOFF,"thresholds":THRESHOLDS,
 "feature_families":FAMILIES,"split":qa["split"],"screen_rule":qa["screen_rule"],
 "outputs":["stage4_anchor_dataset.csv","stage4_family_results.csv","stage4_feature_results_30pct.csv","stage4_keep_discard_summary.csv",
            "stage4_primary30_descriptive.csv","stage4_bootstrap_30pct.csv","stage4_stage3_reference.csv","stage4_qa.json","stage4_manifest.json","stage4_report.md"]
}
(OUT/"stage4_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

summary_sorted=sorted(SUMMARY,key=lambda r:({"KEEP_STRONG":0,"KEEP_WEAK":1,"DEFER_LOW_COVERAGE":2,"DISCARD_UNSTABLE":3}[r["screen_status"]],-(r["delta_auc_at_30pct"] or -999)))
report=["# Stage 4 Adaptive Feature Discovery","",f"Status: **{qa['status']}**","",
"## Method",
"- Frozen 497-trade Stage 1 cohort; strict closed-1m rows only.",
"- Chronological DEV 60% / OOS-MID 20% / OOS-LATE 20%; a position cannot cross splits.",
"- First causal 20/30/40/50% economic-giveback crossings are anchors.",
"- Future new-peak outcome is a label only; every feature is known at the anchor.",
"- Each family is tested for incremental OOS discrimination above peak-size baseline.","",
"## Family screen"]
for r in summary_sorted:
    report.append(f"- {r['family']}: **{r['screen_status']}**; 30% mean delta AUC={r['delta_auc_at_30pct']}; stable thresholds={r['stable_threshold_count']}/4; coverage={r['coverage_at_30pct']}%.")
report+=["","## Stage 3 hurdle",
f"- Best static economic >=2 median capture: {stage3qa['frontier_acceptance']['best_static_econ_ge2_capture']*100:.2f}%.",
f"- Best static persisted-MFE >=2 median capture: {stage3qa['frontier_acceptance']['best_static_mfe2_capture']*100:.2f}%.",
f"- Best static total net PnL: {stage3qa['frontier_acceptance']['best_static_total_net_pnl']:.2f} USDT.",
"",
"## Guardrail",
"Stage 4 does not create a production protector. KEEP means the feature family has earned the right to enter Stage 5 lock/action search; DISCARD/DEFER means it should not increase V4 complexity yet."]
(OUT/"stage4_report.md").write_text("\n".join(report),encoding="utf-8")

zp=Path("/tmp/stage4_adaptive_feature_discovery_497trades.zip")
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file():z.write(p,arcname=p.name)
print(json.dumps({"qa":qa["status"],"anchors":anchor_counts,"cohort":cohort_counts,"summary":summary_sorted,
                  "bootstrap":BOOT,"zip":str(zp),"zip_bytes":zp.stat().st_size,"zip_sha256":sha(zp)},ensure_ascii=False))