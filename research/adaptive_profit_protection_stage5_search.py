#!/usr/bin/env python3
import csv, json, math, hashlib, zipfile, itertools
from pathlib import Path
from collections import defaultdict

ROOT=Path("/opt/core-app/app")
S1ZIP=ROOT/"dashboard/audit/stage1_adaptive_profit_protection_497trades.zip"
S3ZIP=ROOT/"dashboard/audit/stage3_static_frontier_497trades.zip"
S4ZIP=ROOT/"dashboard/audit/stage4_adaptive_feature_discovery_497trades.zip"
OUT=Path("/tmp/stage5_adaptive_lock_search")
OUT.mkdir(parents=True,exist_ok=True)

S1SHA="bd6491e74c45a0859cc4b998f4e2aa85902cca76db45e4ecee028a5b552ca4a4"
S3SHA="985bdc104c6bb9d23ab9383d8dacd694491dc1ce4133a5f92becfbae90e6ea57"
S4SHA="12c30cb11059d82a450e6e5369512f60e9a70847e3843328f8d8395f312142e3"
FROZEN_CUTOFF=1790687518406
FEE=0.00075
SLIP_BPS=2.0
NOTIONAL=500.0
REDUCE_FRAC=0.50
RV15_EXTREME=0.183898

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def f(x):
    try:
        if x is None or x=="":return None
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
def qtl(xs,q):
    z=sorted(x for x in xs if x is not None and math.isfinite(x))
    if not z:return None
    if len(z)==1:return z[0]
    p=(len(z)-1)*q;lo=int(math.floor(p));hi=int(math.ceil(p))
    if lo==hi:return z[lo]
    return z[lo]*(hi-p)+z[hi]*(p-lo)
def pct(a,b):return 100*a/b if b else None
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
def readzipcsv(zpath,name):
    with zipfile.ZipFile(zpath) as z:
        raw=z.read(name).decode("utf-8-sig").splitlines()
    return list(csv.DictReader(raw))
def close_fill(side,market):
    slip=SLIP_BPS/10000.0
    return market*(1-slip) if side=="LONG" else market*(1+slip)
def gross(side,qty,entry,fill):
    return qty*(fill-entry) if side=="LONG" else qty*(entry-fill)

assert sha(S1ZIP)==S1SHA,(sha(S1ZIP),S1SHA)
assert sha(S3ZIP)==S3SHA,(sha(S3ZIP),S3SHA)
assert sha(S4ZIP)==S4SHA,(sha(S4ZIP),S4SHA)

MASTER_ROWS=readzipcsv(S1ZIP,"stage1_trade_master.csv")
TIMELINE_RAW=readzipcsv(S1ZIP,"stage1_timeline_1m.csv")
MASTER={str(r["position_id"]):r for r in MASTER_ROWS}

TL=defaultdict(list);excluded=0
for r in TIMELINE_RAW:
    pid=str(r["position_id"]);m=MASTER.get(pid)
    if not m:continue
    if ii(r["candle_close_ms"])<=ii(m["closed_at_ms"]):
        TL[pid].append(r)
    else:excluded+=1
for pid in TL:TL[pid].sort(key=lambda r:ii(r["candle_close_ms"]) or 0)

ordered=sorted(MASTER_ROWS,key=lambda r:ii(r["opened_at_ms"]) or 0)
n=len(ordered);c1=int(math.floor(n*.60));c2=int(math.floor(n*.80))
SPLIT={}
for idx,m in enumerate(ordered):
    SPLIT[str(m["position_id"])]="DEV" if idx<c1 else ("OOS_MID" if idx<c2 else "OOS_LATE")

BASE={}
for pid,m in MASTER.items():
    side=m["side"];entry=f(m["entry_price"]);qty=f(m["initial_qty"])
    entry_fee=entry*qty*FEE
    path=[];opp_peak=-1e99;opp_peak_t=None
    for r in TL.get(pid,[]):
        market=f(r["close"]);fill=close_fill(side,market)
        econ=gross(side,qty,entry,fill)-entry_fee-qty*fill*FEE
        if econ>opp_peak:opp_peak=econ;opp_peak_t=ii(r["candle_close_ms"])
        share=f(r.get("taker_buy_share_1m"))
        taker_strength=None if share is None else ((share-.5) if side=="LONG" else (.5-share))
        ret3=f(r.get("ret_3m_pct"))
        side_ret3=ret3 if side=="LONG" else (-ret3 if ret3 is not None else None)
        micro_against=truth(r.get("micro_break_down")) if side=="LONG" else truth(r.get("micro_break_up"))
        oi=f(r.get("oi_change_5m_pct"))
        path.append({
          "ts":ii(r["candle_close_ms"]),"market":market,
          "side_ret3":side_ret3,"taker_strength":taker_strength,
          "micro_against":micro_against,"oi_change":oi,"rv15":f(r.get("rv15_1m_pct"))
        })
    final_fill=f(m["exit_price"])
    final_net=gross(side,qty,entry,final_fill)-entry_fee-qty*final_fill*FEE
    if final_net>opp_peak:opp_peak=final_net;opp_peak_t=ii(m["closed_at_ms"])
    BASE[pid]={
      "entry":entry,"qty":qty,"entry_fee":entry_fee,"path":path,
      "censor_fill":final_fill,"censor_ts":ii(m["closed_at_ms"]),
      "opp_peak":max(opp_peak,final_net),"opp_peak_t":opp_peak_t,
      "opp_peak_roi":max(opp_peak,final_net)/NOTIONAL*100,
      "mfe":f(m.get("mfe_pct_persisted")),"split":SPLIT[pid]
    }

def evidence_state(x,peak_age_min):
    stale=1 if peak_age_min>=3.0 else 0
    price_adv=1 if ((x["side_ret3"] is not None and x["side_ret3"]<=-.10) or x["micro_against"]) else 0
    taker_opp=1 if (x["taker_strength"] is not None and x["taker_strength"]<=-.05) else 0
    oi_adv=1 if (x["oi_change"] is not None and x["oi_change"]>=.05 and x["side_ret3"] is not None and x["side_ret3"]<=-.10) else 0
    vol_ext=1 if (x["rv15"] is not None and x["rv15"]>=RV15_EXTREME) else 0
    core=stale+price_adv+taker_opp
    healthy=1 if (core==0 and not oi_adv and not vol_ext and x["side_ret3"] is not None and x["side_ret3"]>0 and x["taker_strength"] is not None and x["taker_strength"]>=0) else 0
    return {"stale":stale,"price_adv":price_adv,"taker_opp":taker_opp,"oi_adv":oi_adv,"vol_ext":vol_ext,"core":core,"healthy":healthy}

def base_lock_for_peak(policy,peak_roi):
    if peak_roi<.5:return None
    if peak_roi<2:return policy["base1"] if policy["base1"]>0 else None
    if peak_roi<5:return policy["base2"] if policy["base2"]>0 else None
    return policy["base3"] if policy["base3"]>0 else None

def adaptive_lock(policy,peak_roi,ev):
    b=base_lock_for_peak(policy,peak_roi)
    if b is None:return None
    lock=b
    if ev["core"]>=2:lock+=policy["tight2"]
    if ev["core"]>=3:lock+=policy["tight3"]
    if ev["oi_adv"]:lock+=policy.get("oi_tight",0.0)
    if ev["vol_ext"]:lock+=policy.get("vol_mod",0.0)
    if ev["healthy"]:lock-=policy.get("cont_bonus",0.0)
    return max(.05,min(.95,lock))

def simulate_adaptive(pid,policy,trace=False):
    m=MASTER[pid];b=BASE[pid];side=m["side"];entry=b["entry"];initial=b["qty"]
    remaining=initial;realized=0.0;allocated_entry=0.0
    peak=-1e99;peak_t=None;floor=None
    reduced=False;reduce_ts=None;close_ts=None;action_count=0;trigger_count=0
    trace_rows=[]
    for x in b["path"]:
        fill=close_fill(side,x["market"])
        unreal=gross(side,remaining,entry,fill)
        rem_entry=max(0.0,b["entry_fee"]-allocated_entry)
        econ=realized+unreal-rem_entry-remaining*fill*FEE
        if econ>peak:
            peak=econ;peak_t=x["ts"]
        age=0.0 if peak_t is None else max(0.0,(x["ts"]-peak_t)/60000.0)
        ev=evidence_state(x,age)
        lock=adaptive_lock(policy,peak/NOTIONAL*100,ev)
        if lock is not None and peak>0:
            cand=peak*lock
            floor=cand if floor is None else max(floor,cand)
        breached=bool(floor is not None and econ<=floor+1e-12)
        action="HOLD"
        if breached:
            trigger_count+=1
            mode=policy["mode"]
            if mode=="CLOSE_FIRST":
                action="CLOSE"
            elif mode=="REDUCE_ONCE":
                action="REDUCE" if not reduced else "HOLD"
            elif mode=="REDUCE_THEN_CLOSE":
                action="REDUCE" if not reduced else "CLOSE"
            elif mode=="EVIDENCE_ESCALATE":
                if not reduced:
                    action="CLOSE" if ev["core"]>=3 else "REDUCE"
                else:
                    action="CLOSE"
            if action=="REDUCE":
                q=remaining*REDUCE_FRAC
                alloc=b["entry_fee"]*(q/initial) if initial else 0.0
                realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
                allocated_entry+=alloc;remaining-=q;reduced=True;reduce_ts=x["ts"];action_count+=1
            elif action=="CLOSE":
                q=remaining;alloc=b["entry_fee"]-allocated_entry
                realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
                allocated_entry+=alloc;remaining=0.0;close_ts=x["ts"];action_count+=1
        if trace:
            trace_rows.append({
              "position_id":pid,"symbol":m["symbol"],"side":side,"ts":x["ts"],
              "economic_pnl":econ,"peak_economic_pnl":peak,"peak_roi_pct":peak/NOTIONAL*100,
              "peak_age_min":age,"lock_ratio":lock,"profit_floor":floor,"breached":breached,
              "core_evidence":ev["core"],"stale":ev["stale"],"price_adverse":ev["price_adv"],
              "taker_opposing":ev["taker_opp"],"oi_adverse":ev["oi_adv"],"vol_extreme":ev["vol_ext"],
              "healthy_continuation":ev["healthy"],"action":action,"remaining_qty_after":remaining
            })
        if remaining<=0:break
    if remaining>0:
        fill=b["censor_fill"];q=remaining;alloc=b["entry_fee"]-allocated_entry
        realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
        allocated_entry+=alloc;remaining=0.0
    final_net=realized;final_roi=final_net/NOTIONAL*100
    opp=b["opp_peak"]
    return {
      "position_id":pid,"final_net":final_net,"final_roi":final_roi,
      "economic_capture":final_net/opp if opp is not None and opp>0 else None,
      "price_mfe_capture":final_roi/b["mfe"] if b["mfe"] is not None and b["mfe"]>0 else None,
      "reduce_ts":reduce_ts,"close_ts":close_ts,
      "premature_close":bool(close_ts is not None and b["opp_peak_t"] is not None and close_ts<b["opp_peak_t"]),
      "premature_reduce":bool(reduce_ts is not None and b["opp_peak_t"] is not None and reduce_ts<b["opp_peak_t"]),
      "action_count":action_count,"trigger_count":trigger_count,
      "positive_peak_final_negative":bool(opp is not None and opp>0 and final_net<0),
      "trace":trace_rows
    }

def simulate_static(pid,arm,giveback,mode):
    m=MASTER[pid];b=BASE[pid];side=m["side"];entry=b["entry"];initial=b["qty"]
    remaining=initial;realized=0.0;allocated_entry=0.0;peak=-1e99;floor=None;reduced=False
    reduce_ts=None;close_ts=None;actions=0;triggers=0
    for x in b["path"]:
        fill=close_fill(side,x["market"]);unreal=gross(side,remaining,entry,fill)
        econ=realized+unreal-max(0,b["entry_fee"]-allocated_entry)-remaining*fill*FEE
        if econ>peak:peak=econ
        if peak/NOTIONAL*100>=arm and peak>0:
            cand=peak*(1-giveback)
            floor=cand if floor is None else max(floor,cand)
        if floor is None or econ>floor+1e-12:continue
        triggers+=1
        if mode=="CLOSE_FIRST":act="CLOSE"
        elif mode=="REDUCE_ONCE":act="REDUCE" if not reduced else "HOLD"
        else:act="REDUCE" if not reduced else "CLOSE"
        if act=="REDUCE":
            q=remaining*REDUCE_FRAC;alloc=b["entry_fee"]*(q/initial)
            realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
            allocated_entry+=alloc;remaining-=q;reduced=True;reduce_ts=x["ts"];actions+=1
        elif act=="CLOSE":
            q=remaining;alloc=b["entry_fee"]-allocated_entry
            realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
            allocated_entry+=alloc;remaining=0;close_ts=x["ts"];actions+=1;break
    if remaining>0:
        fill=b["censor_fill"];q=remaining;alloc=b["entry_fee"]-allocated_entry
        realized+=gross(side,q,entry,fill)-alloc-q*fill*FEE
    final_net=realized;final_roi=final_net/NOTIONAL*100;opp=b["opp_peak"]
    return {
      "position_id":pid,"final_net":final_net,"final_roi":final_roi,
      "economic_capture":final_net/opp if opp and opp>0 else None,
      "price_mfe_capture":final_roi/b["mfe"] if b["mfe"] and b["mfe"]>0 else None,
      "reduce_ts":reduce_ts,"close_ts":close_ts,
      "premature_close":bool(close_ts is not None and b["opp_peak_t"] is not None and close_ts<b["opp_peak_t"]),
      "premature_reduce":bool(reduce_ts is not None and b["opp_peak_t"] is not None and reduce_ts<b["opp_peak_t"]),
      "action_count":actions,"trigger_count":triggers,
      "positive_peak_final_negative":bool(opp and opp>0 and final_net<0)
    }

def metrics(replays,split):
    ids={pid for pid,b in BASE.items() if split=="ALL" or b["split"]==split}
    z=[r for r in replays if r["position_id"] in ids]
    econ2=[r for r in z if BASE[r["position_id"]]["opp_peak_roi"]>=2]
    econ5=[r for r in z if BASE[r["position_id"]]["opp_peak_roi"]>=5]
    mfe2=[r for r in z if (BASE[r["position_id"]]["mfe"] or 0)>=2]
    mfe5=[r for r in z if (BASE[r["position_id"]]["mfe"] or 0)>=5]
    return {
      "split":split,"n_trades":len(z),"total_net_pnl":sum(r["final_net"] for r in z),
      "win_rate_pct":pct(sum(r["final_net"]>0 for r in z),len(z)),
      "actions_per_trade":sum(r["action_count"] for r in z)/len(z) if z else None,
      "trigger_rate_pct":pct(sum(r["trigger_count"]>0 for r in z),len(z)),
      "positive_peak_final_negative_n":sum(r["positive_peak_final_negative"] for r in z),
      "econ_ge2_n":len(econ2),"econ_ge2_capture_median":med([r["economic_capture"] for r in econ2]),
      "econ_ge2_capture_p25":qtl([r["economic_capture"] for r in econ2],.25),
      "econ_ge2_premature_close_pct":pct(sum(r["premature_close"] for r in econ2),len(econ2)),
      "econ_ge2_premature_reduce_pct":pct(sum(r["premature_reduce"] for r in econ2),len(econ2)),
      "econ_ge5_n":len(econ5),"econ_ge5_capture_median":med([r["economic_capture"] for r in econ5]),
      "econ_ge5_premature_close_pct":pct(sum(r["premature_close"] for r in econ5),len(econ5)),
      "mfe_ge2_n":len(mfe2),"mfe_ge2_price_capture_median":med([r["price_mfe_capture"] for r in mfe2]),
      "mfe_ge5_n":len(mfe5),"mfe_ge5_price_capture_median":med([r["price_mfe_capture"] for r in mfe5])
    }

STATIC_SPECS=[
 ("STATIC_NET_A5_GB20_CLOSE",5,.20,"CLOSE_FIRST"),
 ("STATIC_BAL_A3_GB30_CLOSE",3,.30,"CLOSE_FIRST"),
 ("STATIC_CAPTURE_A2_GB20_RTC",2,.20,"REDUCE_THEN_CLOSE")
]
STATIC_REPLAYS={}
STATIC_ROWS=[]
for name,arm,gb,mode in STATIC_SPECS:
    rr=[simulate_static(pid,arm,gb,mode) for pid in MASTER]
    STATIC_REPLAYS[name]=rr
    for split in ["DEV","OOS_MID","OOS_LATE","ALL"]:
        STATIC_ROWS.append({"policy_id":name,**metrics(rr,split)})
STATIC={(r["policy_id"],r["split"]):r for r in STATIC_ROWS}
write_csv(OUT/"stage5_static_split_benchmarks.csv",STATIC_ROWS)

base1s=[0,.20,.30,.40]
base2s=[.20,.30,.40,.50,.60]
base3s=[.50,.60,.70,.80]
tight2s=[.10,.20,.30]
tight3s=[0,.10,.20]
COARSE=[]
for b1,b2,b3,t2,t3 in itertools.product(base1s,base2s,base3s,tight2s,tight3s):
    if not (b1<=b2<=b3):continue
    pol={"policy_id":f"C_B{int(b1*100)}-{int(b2*100)}-{int(b3*100)}_T{int(t2*100)}+{int(t3*100)}",
         "base1":b1,"base2":b2,"base3":b3,"tight2":t2,"tight3":t3,
         "oi_tight":0.0,"vol_mod":0.0,"cont_bonus":0.0,"mode":"CLOSE_FIRST","search_stage":"COARSE"}
    rr=[simulate_adaptive(pid,pol) for pid in MASTER]
    devm=metrics(rr,"DEV")
    COARSE.append({**pol,**{f"DEV_{k}":v for k,v in devm.items() if k!="split"}})
write_csv(OUT/"stage5_coarse_grid.csv",COARSE)

def dominates(a,b):
    av=[a["DEV_total_net_pnl"],a["DEV_econ_ge2_capture_median"],-a["DEV_econ_ge2_premature_close_pct"],-a["DEV_actions_per_trade"]]
    bv=[b["DEV_total_net_pnl"],b["DEV_econ_ge2_capture_median"],-b["DEV_econ_ge2_premature_close_pct"],-b["DEV_actions_per_trade"]]
    return all(x>=y-1e-12 for x,y in zip(av,bv)) and any(x>y+1e-12 for x,y in zip(av,bv))
PARETO=[]
for i,a in enumerate(COARSE):
    if not any(i!=j and dominates(b,a) for j,b in enumerate(COARSE)):PARETO.append(a)

baldev=STATIC[("STATIC_BAL_A3_GB30_CLOSE","DEV")]
pool={}
for x in PARETO:pool[x["policy_id"]]=x
for key in ["DEV_total_net_pnl","DEV_econ_ge2_capture_median"]:
    for x in sorted(COARSE,key=lambda r:r[key],reverse=True)[:12]:pool[x["policy_id"]]=x
for x in COARSE:
    if (x["DEV_total_net_pnl"]>=baldev["total_net_pnl"] and
        x["DEV_econ_ge2_capture_median"]>=baldev["econ_ge2_capture_median"] and
        x["DEV_econ_ge2_premature_close_pct"]<=baldev["econ_ge2_premature_close_pct"]+5):
        pool[x["policy_id"]]=x
def dev_rank(x):
    gate=int(x["DEV_econ_ge2_capture_median"]>=baldev["econ_ge2_capture_median"] and x["DEV_econ_ge2_premature_close_pct"]<=baldev["econ_ge2_premature_close_pct"]+5)
    return (gate,x["DEV_total_net_pnl"],x["DEV_econ_ge2_capture_median"],-x["DEV_econ_ge2_premature_close_pct"])
SEEDS=sorted(pool.values(),key=dev_rank,reverse=True)[:24]
write_csv(OUT/"stage5_coarse_seed_shortlist.csv",SEEDS)

REFINED=[];REF_IDS=set()
for seed in SEEDS:
    for oi_tight,vol_mod,cont_bonus,mode in itertools.product(
        [0,.05,.10],[-.05,0,.05,.10],[0,.05,.10],
        ["CLOSE_FIRST","REDUCE_ONCE","REDUCE_THEN_CLOSE","EVIDENCE_ESCALATE"]):
        pol={k:seed[k] for k in ["base1","base2","base3","tight2","tight3"]}
        pol.update({"oi_tight":oi_tight,"vol_mod":vol_mod,"cont_bonus":cont_bonus,"mode":mode,"search_stage":"REFINE"})
        pol["policy_id"]=(
          f"R_B{int(pol['base1']*100)}-{int(pol['base2']*100)}-{int(pol['base3']*100)}"
          f"_T{int(pol['tight2']*100)}+{int(pol['tight3']*100)}"
          f"_OI{int(oi_tight*100)}_V{int(vol_mod*100):+d}_CB{int(cont_bonus*100)}_{mode}"
        )
        if pol["policy_id"] in REF_IDS:continue
        REF_IDS.add(pol["policy_id"])
        rr=[simulate_adaptive(pid,pol) for pid in MASTER]
        row=dict(pol)
        for s in ["DEV","OOS_MID","OOS_LATE","ALL"]:
            mx=metrics(rr,s)
            for k,v in mx.items():
                if k!="split":row[f"{s}_{k}"]=v
        row["DEV_balanced_gate"]=bool(
          row["DEV_total_net_pnl"]>=baldev["total_net_pnl"] and
          row["DEV_econ_ge2_capture_median"]>=baldev["econ_ge2_capture_median"] and
          row["DEV_econ_ge2_premature_close_pct"]<=baldev["econ_ge2_premature_close_pct"]+5)
        pass_oos=[];pass_net=[]
        for s in ["OOS_MID","OOS_LATE"]:
            bs=STATIC[("STATIC_BAL_A3_GB30_CLOSE",s)]
            pass_oos.append(
              row[f"{s}_total_net_pnl"]>=bs["total_net_pnl"] and
              row[f"{s}_econ_ge2_capture_median"]>=bs["econ_ge2_capture_median"] and
              row[f"{s}_econ_ge2_premature_close_pct"]<=bs["econ_ge2_premature_close_pct"]+5)
            ns=STATIC[("STATIC_NET_A5_GB20_CLOSE",s)]
            pass_net.append(
              row[f"{s}_total_net_pnl"]>=ns["total_net_pnl"] and
              row[f"{s}_econ_ge2_capture_median"]>=ns["econ_ge2_capture_median"] and
              row[f"{s}_econ_ge2_premature_close_pct"]<=ns["econ_ge2_premature_close_pct"]+5)
        row["OOS_balanced_gate_both"]=all(pass_oos)
        row["OOS_net_gate_both"]=all(pass_net)
        REFINED.append(row)
write_csv(OUT/"stage5_refined_grid.csv",REFINED)

def final_dev_rank(x):
    return (int(x["DEV_balanced_gate"]),x["DEV_total_net_pnl"],x["DEV_econ_ge2_capture_median"],
            -x["DEV_econ_ge2_premature_close_pct"],-x["DEV_actions_per_trade"])
DEV_ORDER=sorted(REFINED,key=final_dev_rank,reverse=True)
SELECTED=next((x for x in DEV_ORDER if x["OOS_balanced_gate_both"]),None)
if SELECTED is None:
    SELECTED=next((x for x in DEV_ORDER if all(
        x[f"{s}_econ_ge2_capture_median"]>=STATIC[("STATIC_BAL_A3_GB30_CLOSE",s)]["econ_ge2_capture_median"]
        for s in ["OOS_MID","OOS_LATE"])),None)
if SELECTED is None:SELECTED=DEV_ORDER[0]
write_csv(OUT/"stage5_candidate_shortlist.csv",DEV_ORDER[:12])

selpol={k:SELECTED[k] for k in ["base1","base2","base3","tight2","tight3","oi_tight","vol_mod","cont_bonus","mode"]}
steps={"base1":.10,"base2":.10,"base3":.10,"tight2":.10,"tight3":.10,"oi_tight":.05,"vol_mod":.05,"cont_bonus":.05}
NEIGH=[];seen=set()
def eval_neighbor(pol,label):
    key=tuple(pol[k] for k in ["base1","base2","base3","tight2","tight3","oi_tight","vol_mod","cont_bonus","mode"])
    if key in seen:return
    seen.add(key)
    if not (0<=pol["base1"]<=pol["base2"]<=pol["base3"]<=.95):return
    if pol["tight2"]<0 or pol["tight3"]<0 or pol["oi_tight"]<0 or pol["cont_bonus"]<0:return
    if pol["vol_mod"]<-.10:return
    rr=[simulate_adaptive(pid,pol) for pid in MASTER]
    row={"neighbor_label":label,**pol}
    for s in ["DEV","OOS_MID","OOS_LATE","ALL"]:
        mm=metrics(rr,s)
        for k,v in mm.items():
            if k!="split":row[f"{s}_{k}"]=v
    NEIGH.append(row)
eval_neighbor(dict(selpol),"CENTER")
for k,step in steps.items():
    for sign in [-1,1]:
        p=dict(selpol);p[k]=round(p[k]+sign*step,10)
        eval_neighbor(p,f"{k}{'+' if sign>0 else '-'}")
write_csv(OUT/"stage5_neighborhood_stability.csv",NEIGH)

sel_id=SELECTED["policy_id"]
selected_policy={k:SELECTED[k] for k in ["base1","base2","base3","tight2","tight3","oi_tight","vol_mod","cont_bonus","mode"]}
sel_rr=[simulate_adaptive(pid,selected_policy) for pid in MASTER]
TRADE=[]
for r in sel_rr:
    pid=r["position_id"];m=MASTER[pid];b=BASE[pid]
    TRADE.append({
      "policy_id":sel_id,"position_id":pid,"symbol":m["symbol"],"side":m["side"],"split":b["split"],
      "opp_peak_roi_pct":b["opp_peak_roi"],"persisted_mfe_pct":b["mfe"],
      "final_net":r["final_net"],"final_roi":r["final_roi"],"economic_capture":r["economic_capture"],
      "price_mfe_capture":r["price_mfe_capture"],"reduce_ts":r["reduce_ts"],"close_ts":r["close_ts"],
      "premature_close":r["premature_close"],"premature_reduce":r["premature_reduce"],
      "action_count":r["action_count"],"trigger_count":r["trigger_count"]
    })
write_csv(OUT/"stage5_selected_trade_replay.csv",TRADE)

trace_ids=set()
for pid,m in MASTER.items():
    if m["symbol"] in {"GRASSUSDT","CELOUSDT","ARXUSDT","MINAUSDT"}:trace_ids.add(pid)
for pid in sorted(MASTER,key=lambda p:BASE[p]["opp_peak"],reverse=True)[:12]:trace_ids.add(pid)
TRACES=[]
for pid in trace_ids:
    rr=simulate_adaptive(pid,{**selpol,"policy_id":sel_id},trace=True)
    TRACES.extend(rr["trace"])
write_csv(OUT/"stage5_selected_case_traces.csv",TRACES)

COMPARE=[]
for split in ["DEV","OOS_MID","OOS_LATE","ALL"]:
    row={"split":split,"selected_policy":sel_id}
    for bench in ["STATIC_NET_A5_GB20_CLOSE","STATIC_BAL_A3_GB30_CLOSE","STATIC_CAPTURE_A2_GB20_RTC"]:
        b=STATIC[(bench,split)]
        row[f"{bench}_net"]=b["total_net_pnl"]
        row[f"{bench}_econ2cap"]=b["econ_ge2_capture_median"]
        row[f"{bench}_premclose"]=b["econ_ge2_premature_close_pct"]
    row["adaptive_net"]=SELECTED[f"{split}_total_net_pnl"]
    row["adaptive_econ2cap"]=SELECTED[f"{split}_econ_ge2_capture_median"]
    row["adaptive_premclose"]=SELECTED[f"{split}_econ_ge2_premature_close_pct"]
    row["adaptive_mfe2cap"]=SELECTED[f"{split}_mfe_ge2_price_capture_median"]
    COMPARE.append(row)
write_csv(OUT/"stage5_static_comparison.csv",COMPARE)

center=next(r for r in NEIGH if r["neighbor_label"]=="CENTER")
neighbor_nets=[r["ALL_total_net_pnl"] for r in NEIGH]
neighbor_caps=[r["ALL_econ_ge2_capture_median"] for r in NEIGH if r["ALL_econ_ge2_capture_median"] is not None]
stable_neighbors=sum(1 for r in NEIGH if r["ALL_total_net_pnl"]>=center["ALL_total_net_pnl"]-25 and r["ALL_econ_ge2_capture_median"]>=center["ALL_econ_ge2_capture_median"]-.05)

qa={
 "stage":"Stage 5 - Adaptive Lock Search","status":"PASS",
 "input":{"stage1_sha256":sha(S1ZIP),"stage3_sha256":sha(S3ZIP),"stage4_sha256":sha(S4ZIP),
          "frozen_trade_count":len(MASTER),"strict_preclose_rows":sum(len(v) for v in TL.values()),"excluded_postclose_overlap_rows":excluded},
 "search":{"coarse_policies":len(COARSE),"coarse_pareto":len(PARETO),"coarse_seeds":len(SEEDS),
           "refined_policies":len(REFINED),"selection":"DEV rank only; OOS-MID/OOS-LATE as stability gate","neighborhood_variants":len(NEIGH)},
 "selected":{"policy_id":sel_id,"parameters":selpol,"DEV_balanced_gate":SELECTED["DEV_balanced_gate"],
             "OOS_balanced_gate_both":SELECTED["OOS_balanced_gate_both"],"OOS_net_gate_both":SELECTED["OOS_net_gate_both"]},
 "surface":{"neighbors_within_25usdt_and_5pp_capture":stable_neighbors,"neighbor_count":len(NEIGH),
            "all_net_min":min(neighbor_nets),"all_net_max":max(neighbor_nets),
            "all_capture_min":min(neighbor_caps) if neighbor_caps else None,"all_capture_max":max(neighbor_caps) if neighbor_caps else None},
 "causality":{"closed_1m_only":True,"future_data_in_trigger":False,"policy_economic_peak_is_causal":True,
              "profit_floor_non_decreasing":True,"actual_v3_reductions_used":False,"right_censor_at_actual_v3_close":True},
 "notes":["Stage 5 searches policy parameters but does not approve production deployment.",
          "OOS windows were already inspected in Stage 4 and therefore are temporal stability gates, not pristine untouched tests.",
          "Stage 6 must validate the selected policy on later chronological cohorts before Stage 8 shadow mode.",
          "Extreme volatility includes a negative allowance option and positive tightening options; selected sign is empirical.",
          "Prior REDUCE is used only as execution state inside action modes, never as deterioration evidence."]}
if len(MASTER)!=497 or excluded!=497:qa["status"]="FAIL"
(OUT/"stage5_qa.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")

manifest={
 "stage":"Adaptive Profit Protection Discovery - Stage 5 Adaptive Lock Search",
 "status":"COMPLETE_QA_PASS" if qa["status"]=="PASS" else "QA_FAIL",
 "code_version":"stage5-adaptive-lock-search-v1-stdlib","frozen_cutoff_ms":FROZEN_CUTOFF,
 "stage1_sha256":S1SHA,"stage3_sha256":S3SHA,"stage4_sha256":S4SHA,
 "economics":{"notional":NOTIONAL,"fee_rate":FEE,"slippage_bps":SLIP_BPS,"reduce_fraction":REDUCE_FRAC},
 "base_lock_tiers":"0.5-2%, 2-5%, >=5% causal policy peak economic ROI",
 "core_evidence":["stale_peak_ge3m","adverse_3m_or_microbreak","opposing_taker_45_55"],
 "conditional_modifiers":["adverse_oi_building","extreme_rv15_stage2_q75"],
 "continuation_bonus":"core evidence=0, no OI/vol deterioration, positive side-adjusted 3m, non-opposing taker",
 "selected_policy":sel_id,"selected_parameters":selpol
}
(OUT/"stage5_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

allcmp=next(r for r in COMPARE if r["split"]=="ALL")
report=[
"# Stage 5 Adaptive Lock Search","",f"Status: **{qa['status']}**","",
"## Search design",
f"- Coarse policies: {len(COARSE)}; Pareto: {len(PARETO)}; DEV-selected seeds: {len(SEEDS)}.",
f"- Refined policies: {len(REFINED)}.",
"- Policy ranking is DEV-only. OOS-MID and OOS-LATE are stability gates, not ranking targets.",
"- Counterfactual economics ignore actual V3 REDUCEs, apply 0.075% fee + 2 bps adverse exit slippage, and right-censor at the actual V3 close.",
"",
"## Selected Stage 5 candidate",
"- Policy: "+sel_id,
"- Parameters: "+json.dumps(selpol,sort_keys=True),
f"- DEV balanced gate: {SELECTED['DEV_balanced_gate']}",
f"- OOS balanced gate both: {SELECTED['OOS_balanced_gate_both']}",
f"- OOS net gate both: {SELECTED['OOS_net_gate_both']}",
"",
"## Full frozen-cohort comparison",
f"- Adaptive total net PnL: {allcmp['adaptive_net']:.2f} USDT",
f"- Adaptive economic >=2 median capture: {allcmp['adaptive_econ2cap']*100:.2f}%",
f"- Adaptive persisted-MFE >=2 median capture: {allcmp['adaptive_mfe2cap']*100:.2f}%",
f"- Adaptive economic >=2 premature CLOSE: {allcmp['adaptive_premclose']:.2f}%",
f"- Static-net benchmark PnL: {allcmp['STATIC_NET_A5_GB20_CLOSE_net']:.2f} USDT; capture {allcmp['STATIC_NET_A5_GB20_CLOSE_econ2cap']*100:.2f}%",
f"- Static-balanced PnL: {allcmp['STATIC_BAL_A3_GB30_CLOSE_net']:.2f} USDT; capture {allcmp['STATIC_BAL_A3_GB30_CLOSE_econ2cap']*100:.2f}%",
f"- Static-capture PnL: {allcmp['STATIC_CAPTURE_A2_GB20_RTC_net']:.2f} USDT; capture {allcmp['STATIC_CAPTURE_A2_GB20_RTC_econ2cap']*100:.2f}%",
"",
"## Surface stability",
f"- Local one-step neighbors: {len(NEIGH)}.",
f"- Neighbors within selected PnL -25 USDT and capture -5pp: {stable_neighbors}/{len(NEIGH)}.",
f"- Neighbor full-cohort PnL range: {min(neighbor_nets):.2f} to {max(neighbor_nets):.2f} USDT.",
f"- Neighbor economic >=2 capture range: {min(neighbor_caps)*100:.2f}% to {max(neighbor_caps)*100:.2f}%.",
"",
"## Guardrail",
"Stage 5 produces a candidate adaptive policy, not production authority. Stage 6 must validate it chronologically on later cohorts; Stage 8 shadow mode remains mandatory before deployment."
]
(OUT/"stage5_report.md").write_text("\n".join(report),encoding="utf-8")

zp=Path("/tmp/stage5_adaptive_lock_search_497trades.zip")
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file():z.write(p,arcname=p.name)
print(json.dumps({"qa":qa["status"],"coarse":len(COARSE),"refined":len(REFINED),"selected":SELECTED,
                  "compare":COMPARE,"surface":qa["surface"],"zip_bytes":zp.stat().st_size,"zip_sha256":sha(zp)},ensure_ascii=False))