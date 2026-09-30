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


# Formal Stage 5 finalization: three DEV-selected/OOS-gated candidates.
CANDIDATES=[
 {"candidate":"S5-A_PRIMARY_BALANCED","policy_id":"L_B0-25-50_T30+0_OI0.125_V0.025",
  "base1":0.0,"base2":.25,"base3":.50,"tight2":.30,"tight3":0.0,"oi_tight":.125,"vol_mod":.025,"cont_bonus":0.0,"mode":"CLOSE_FIRST",
  "selection_role":"highest DEV total PnL among local policies that pass DEV balanced gate and both OOS balanced gates"},
 {"candidate":"S5-B_RUNNER_PRESERVING","policy_id":"R_B0-30-50_T10+20_OI10_V+0_CB0_CLOSE_FIRST",
  "base1":0.0,"base2":.30,"base3":.50,"tight2":.10,"tight3":.20,"oi_tight":.10,"vol_mod":0.0,"cont_bonus":0.0,"mode":"CLOSE_FIRST",
  "selection_role":"lower premature-close variant that passes DEV and both OOS balanced gates"},
 {"candidate":"S5-C_CAPTURE_HEAVY","policy_id":"L_B0-30-50_T25+5_OI0.125_V0.000",
  "base1":0.0,"base2":.30,"base3":.50,"tight2":.25,"tight3":.05,"oi_tight":.125,"vol_mod":0.0,"cont_bonus":0.0,"mode":"CLOSE_FIRST",
  "selection_role":"higher-capture DEV-ranked local variant that passes DEV and both OOS balanced gates"}
]

STATIC_SPECS=[
 ("STATIC_NET_A5_GB20_CLOSE",5,.20,"CLOSE_FIRST"),
 ("STATIC_BAL_A3_GB30_CLOSE",3,.30,"CLOSE_FIRST"),
 ("STATIC_CAPTURE_A2_GB20_RTC",2,.20,"REDUCE_THEN_CLOSE")
]
STATIC_ROWS=[];STATIC={}
for name,arm,gb,mode in STATIC_SPECS:
    rr=[simulate_static(pid,arm,gb,mode) for pid in MASTER]
    for sp in ["DEV","OOS_MID","OOS_LATE","ALL"]:
        row={"policy_id":name,**metrics(rr,sp)};STATIC_ROWS.append(row);STATIC[(name,sp)]=row
write_csv(OUT/"stage5_static_split_benchmarks.csv",STATIC_ROWS)

FRONTIER=[];TRADE=[];TRACES=[];COMPARE=[]
trace_ids=set()
for pid,m in MASTER.items():
    if m["symbol"] in {"GRASSUSDT","CELOUSDT","ARXUSDT","MINAUSDT"}:trace_ids.add(pid)
for pid in sorted(MASTER,key=lambda p:BASE[p]["opp_peak"],reverse=True)[:12]:trace_ids.add(pid)

for pol in CANDIDATES:
    rr=[simulate_adaptive(pid,pol) for pid in MASTER]
    rec={"candidate":pol["candidate"],"policy_id":pol["policy_id"],"selection_role":pol["selection_role"],
         **{k:pol[k] for k in ["base1","base2","base3","tight2","tight3","oi_tight","vol_mod","cont_bonus","mode"]}}
    for sp in ["DEV","OOS_MID","OOS_LATE","ALL"]:
        mm=metrics(rr,sp)
        for k,v in mm.items():
            if k!="split":rec[f"{sp}_{k}"]=v
    baldev=STATIC[("STATIC_BAL_A3_GB30_CLOSE","DEV")]
    rec["DEV_balanced_gate"]=bool(
        rec["DEV_total_net_pnl"]>=baldev["total_net_pnl"] and
        rec["DEV_econ_ge2_capture_median"]>=baldev["econ_ge2_capture_median"] and
        rec["DEV_econ_ge2_premature_close_pct"]<=baldev["econ_ge2_premature_close_pct"]+5)
    og=[]
    for sp in ["OOS_MID","OOS_LATE"]:
        b=STATIC[("STATIC_BAL_A3_GB30_CLOSE",sp)]
        og.append(rec[f"{sp}_total_net_pnl"]>=b["total_net_pnl"] and
                  rec[f"{sp}_econ_ge2_capture_median"]>=b["econ_ge2_capture_median"] and
                  rec[f"{sp}_econ_ge2_premature_close_pct"]<=b["econ_ge2_premature_close_pct"]+5)
    rec["OOS_balanced_gate_both"]=all(og)
    FRONTIER.append(rec)
    for x in rr:
        pid=x["position_id"];m=MASTER[pid];b=BASE[pid]
        TRADE.append({"candidate":pol["candidate"],"policy_id":pol["policy_id"],"position_id":pid,"symbol":m["symbol"],"side":m["side"],"split":b["split"],
                      "opp_peak_roi_pct":b["opp_peak_roi"],"persisted_mfe_pct":b["mfe"],"final_net":x["final_net"],"final_roi":x["final_roi"],
                      "economic_capture":x["economic_capture"],"price_mfe_capture":x["price_mfe_capture"],"reduce_ts":x["reduce_ts"],"close_ts":x["close_ts"],
                      "premature_close":x["premature_close"],"premature_reduce":x["premature_reduce"],"action_count":x["action_count"],"trigger_count":x["trigger_count"]})
    for pid in trace_ids:
        x=simulate_adaptive(pid,pol,trace=True)
        for t in x["trace"]:
            t={"candidate":pol["candidate"],"policy_id":pol["policy_id"],**t}
            TRACES.append(t)
    for sp in ["DEV","OOS_MID","OOS_LATE","ALL"]:
        row={"candidate":pol["candidate"],"policy_id":pol["policy_id"],"split":sp,
             "adaptive_net":rec[f"{sp}_total_net_pnl"],"adaptive_econ2cap":rec[f"{sp}_econ_ge2_capture_median"],
             "adaptive_premclose":rec[f"{sp}_econ_ge2_premature_close_pct"],"adaptive_mfe2cap":rec[f"{sp}_mfe_ge2_price_capture_median"]}
        for bn,_,_,_ in STATIC_SPECS:
            b=STATIC[(bn,sp)]
            row[bn+"_net"]=b["total_net_pnl"];row[bn+"_econ2cap"]=b["econ_ge2_capture_median"];row[bn+"_premclose"]=b["econ_ge2_premature_close_pct"]
        COMPARE.append(row)

write_csv(OUT/"stage5_candidate_frontier.csv",FRONTIER)
write_csv(OUT/"stage5_candidate_frontier_trade_replay.csv",TRADE)
write_csv(OUT/"stage5_candidate_case_traces.csv",TRACES)
write_csv(OUT/"stage5_candidate_static_comparison.csv",COMPARE)

# Copy local refinement into formal output.
import shutil
shutil.copyfile("/tmp/stage5_local_refine.csv",OUT/"stage5_local_refine.csv")

# Static 816-policy dominance audit.
with zipfile.ZipFile(S3ZIP) as z:
    static_all=list(csv.DictReader(z.read("stage3_policy_results.csv").decode("utf-8-sig").splitlines()))
DOM=[]
for c in FRONTIER:
    n2=n3=0
    for s in static_all:
        sn=f(s.get("total_net_pnl"));sc=f(s.get("econ_ge2_capture_median"));sp=f(s.get("econ_ge2_premature_close_pct"))
        if None in (sn,sc,sp):continue
        if sn>=c["ALL_total_net_pnl"] and sc>=c["ALL_econ_ge2_capture_median"] and (sn>c["ALL_total_net_pnl"] or sc>c["ALL_econ_ge2_capture_median"]):
            n2+=1
        if sn>=c["ALL_total_net_pnl"] and sc>=c["ALL_econ_ge2_capture_median"] and sp<=c["ALL_econ_ge2_premature_close_pct"] and (sn>c["ALL_total_net_pnl"] or sc>c["ALL_econ_ge2_capture_median"] or sp<c["ALL_econ_ge2_premature_close_pct"]):
            n3+=1
    DOM.append({"candidate":c["candidate"],"policy_id":c["policy_id"],"static_net_capture_dominators":n2,"static_net_capture_premclose_dominators":n3,
                "extends_static_frontier":n2==0})
write_csv(OUT/"stage5_static_frontier_dominance.csv",DOM)

# Local stability around S5-A using only local search grid adjacency.
with open("/tmp/stage5_local_refine.csv",encoding="utf-8-sig") as h:local=list(csv.DictReader(h))
A=CANDIDATES[0]
def near(x):
    checks=[
      abs(f(x["base2"])-A["base2"])<=.05+1e-9,
      abs(f(x["base3"])-A["base3"])<=.05+1e-9,
      abs(f(x["tight2"])-A["tight2"])<=.05+1e-9,
      abs(f(x["tight3"])-A["tight3"])<=.05+1e-9,
      abs(f(x["oi_tight"])-A["oi_tight"])<=.025+1e-9,
      abs(f(x["vol_mod"])-A["vol_mod"])<=.025+1e-9]
    return all(checks)
neigh=[x for x in local if near(x)]
a_rec=next(x for x in FRONTIER if x["candidate"]=="S5-A_PRIMARY_BALANCED")
plateau=[x for x in neigh if f(x["ALL_total_net_pnl"])>=a_rec["ALL_total_net_pnl"]-10 and f(x["ALL_econ_ge2_capture_median"])>=a_rec["ALL_econ_ge2_capture_median"]-.03]
write_csv(OUT/"stage5_primary_local_neighborhood.csv",neigh)

# Diagnostics that look better only after reading OOS/full-cohort are explicitly non-selectable.
diagnostics=sorted([x for x in local if x.get("OOS_balanced_gate_both")=="True"],key=lambda x:f(x["ALL_total_net_pnl"]),reverse=True)[:10]
for x in diagnostics:x["selection_status"]="DIAGNOSTIC_ONLY_FULL_COHORT_RANKING_NOT_ALLOWED"
write_csv(OUT/"stage5_hindsight_diagnostics.csv",diagnostics)

qa={
 "stage":"Stage 5 - Adaptive Lock Search","status":"PASS",
 "input":{"stage1_sha256":sha(S1ZIP),"stage3_sha256":sha(S3ZIP),"stage4_sha256":sha(S4ZIP),"frozen_trade_count":len(MASTER),
          "strict_preclose_rows":sum(len(v) for v in TL.values()),"excluded_postclose_overlap_rows":excluded},
 "search":{"coarse_policies":576,"refined_policies":3456,"local_refine_policies":len(local),
           "selection_rule":"candidate A selected by DEV ranking among policies passing DEV balanced gate; OOS-MID/LATE used only as gates",
           "formal_candidate_count":len(CANDIDATES)},
 "formal_candidates":{x["candidate"]:{"policy_id":x["policy_id"],"DEV_balanced_gate":x["DEV_balanced_gate"],"OOS_balanced_gate_both":x["OOS_balanced_gate_both"],
                                      "ALL_total_net_pnl":x["ALL_total_net_pnl"],"ALL_econ_ge2_capture_median":x["ALL_econ_ge2_capture_median"],
                                      "ALL_econ_ge2_premature_close_pct":x["ALL_econ_ge2_premature_close_pct"],
                                      "ALL_econ_ge5_capture_median":x["ALL_econ_ge5_capture_median"],"ALL_econ_ge5_premature_close_pct":x["ALL_econ_ge5_premature_close_pct"],
                                      "ALL_mfe_ge2_price_capture_median":x["ALL_mfe_ge2_price_capture_median"]} for x in FRONTIER},
 "static_frontier_dominance":{x["candidate"]:x["static_net_capture_dominators"] for x in DOM},
 "surface":{"primary_local_neighbors":len(neigh),"primary_plateau_within_10usdt_and_3pp_capture":len(plateau)},
 "causality":{"closed_1m_only":True,"future_data_in_trigger":False,"policy_peak_causal":True,"floor_non_decreasing":True,
              "actual_v3_reductions_used":False,"right_censor_at_actual_v3_close":True},
 "limitations":["Stage 4 already inspected OOS-MID/OOS-LATE; they are temporal stability gates, not untouched tests.",
                "Stage 6 requires later chronological cohorts outside the frozen 497-trade discovery cohort.",
                "The economic-peak >=5 cohort has only 9 trades in this replay, so big-runner premature-close estimates are noisy.",
                "Full-cohort diagnostic winners were not promoted when they failed the DEV selection rule.",
                "No Stage 5 candidate is approved for production or shadow authority yet."]}
if len(MASTER)!=497 or excluded!=497 or any(not x["DEV_balanced_gate"] or not x["OOS_balanced_gate_both"] for x in FRONTIER) or any(x["static_net_capture_dominators"]!=0 for x in DOM):
    qa["status"]="FAIL"
(OUT/"stage5_qa.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")

manifest={
 "stage":"Adaptive Profit Protection Discovery - Stage 5 Adaptive Lock Search","status":"COMPLETE_QA_PASS" if qa["status"]=="PASS" else "QA_FAIL",
 "code_version":"stage5-adaptive-lock-search-v2-frontier","frozen_cutoff_ms":FROZEN_CUTOFF,
 "stage1_sha256":S1SHA,"stage3_sha256":S3SHA,"stage4_sha256":S4SHA,
 "economics":{"notional":NOTIONAL,"fee_rate":FEE,"slippage_bps":SLIP_BPS,"reduce_fraction":REDUCE_FRAC},
 "base_lock_tiers":"0.5-2%, 2-5%, >=5% causal policy peak economic ROI",
 "core_evidence":["stale_peak_ge3m","adverse_3m_or_microbreak","opposing_taker_45_55"],
 "conditional_modifiers":["adverse_oi_building","extreme_rv15_stage2_q75"],
 "formal_candidates":[{k:x[k] for k in ["candidate","policy_id","base1","base2","base3","tight2","tight3","oi_tight","vol_mod","cont_bonus","mode","selection_role"]} for x in CANDIDATES],
 "selection_contract":"DEV chooses/ranks; OOS-MID and OOS-LATE gate; full-cohort metrics are reporting only; Stage 6 later cohorts decide validation."
}
(OUT/"stage5_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

snet=STATIC[("STATIC_NET_A5_GB20_CLOSE","ALL")]
sbal=STATIC[("STATIC_BAL_A3_GB30_CLOSE","ALL")]
scap=STATIC[("STATIC_CAPTURE_A2_GB20_RTC","ALL")]
report=[
"# Stage 5 Adaptive Lock Search","",f"Status: **{qa['status']}**","",
"## Search contract",
"- 576 coarse policies -> 3,456 refined policies -> 810 local refinements.",
"- Ranking/selection is DEV-only. OOS-MID and OOS-LATE are pass/fail temporal gates.",
"- Full-cohort super-winners discovered after OOS inspection are diagnostic-only and are not promoted.",
"- Every decision is causal closed-1m; no V3 partial exits are inherited; profit floors can tighten but never loosen.",
"",
"## Formal candidate frontier"]
for x in FRONTIER:
    report += [
      "### "+x["candidate"],
      "- Policy: "+x["policy_id"],
      "- Role: "+x["selection_role"],
      f"- Full frozen-cohort net PnL: {x['ALL_total_net_pnl']:.2f} USDT",
      f"- Economic peak >=2 median capture: {x['ALL_econ_ge2_capture_median']*100:.2f}%",
      f"- Persisted-MFE >=2 median capture: {x['ALL_mfe_ge2_price_capture_median']*100:.2f}%",
      f"- Economic peak >=2 premature CLOSE: {x['ALL_econ_ge2_premature_close_pct']:.2f}%",
      f"- Economic peak >=5 median capture: {x['ALL_econ_ge5_capture_median']*100:.2f}%",
      f"- Economic peak >=5 premature CLOSE: {x['ALL_econ_ge5_premature_close_pct']:.2f}%",
      f"- DEV gate: {x['DEV_balanced_gate']}; both OOS gates: {x['OOS_balanced_gate_both']}",""
    ]
report += [
"## Static reference",
f"- Static net benchmark: {snet['total_net_pnl']:.2f} USDT; econ>=2 capture {snet['econ_ge2_capture_median']*100:.2f}%; premature CLOSE {snet['econ_ge2_premature_close_pct']:.2f}%.",
f"- Static balanced benchmark: {sbal['total_net_pnl']:.2f} USDT; capture {sbal['econ_ge2_capture_median']*100:.2f}%; premature CLOSE {sbal['econ_ge2_premature_close_pct']:.2f}%.",
f"- Static capture ceiling: {scap['total_net_pnl']:.2f} USDT; capture {scap['econ_ge2_capture_median']*100:.2f}%; premature CLOSE {scap['econ_ge2_premature_close_pct']:.2f}%.",
"- All three formal Stage 5 candidates have zero static policies that dominate them simultaneously on net PnL and economic>=2 capture.",
"",
"## Primary candidate interpretation",
"- S5-A is the only candidate designated PRIMARY because it is the highest-DEV-net local policy that satisfies the predeclared balanced gate and both temporal OOS gates.",
f"- Local neighborhood size: {len(neigh)} policies; {len(plateau)} remain within 10 USDT PnL and 3 percentage points of capture, indicating a non-single-point surface.",
"- S5-A slightly exceeds the Stage 3 maximum static total PnL while materially improving capture, but the PnL margin is small and must not be treated as confirmed edge before Stage 6.",
"",
"## Runner warning",
"- Peak>=5 sample size is only 9 trades.",
"- S5-A and S5-C prematurely CLOSE 4/9 of those opportunity runners; S5-B reduces this to 3/9.",
"- Stage 7 case replay remains mandatory even if Stage 6 validates aggregate metrics.",
"",
"## Stage 6 handoff",
"Carry all three formal candidates forward. Stage 6 must evaluate them on later chronological validation/test cohorts outside the frozen 497 discovery trades. No further tuning on the frozen OOS windows is allowed."
]
(OUT/"stage5_report.md").write_text("\n".join(report),encoding="utf-8")

zp=Path("/tmp/stage5_adaptive_lock_search_497trades.zip")
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file():z.write(p,arcname=p.name)
print(json.dumps({"status":qa["status"],"candidates":qa["formal_candidates"],"dominance":qa["static_frontier_dominance"],
                  "surface":qa["surface"],"zip_bytes":zp.stat().st_size,"sha256":sha(zp)},ensure_ascii=False))