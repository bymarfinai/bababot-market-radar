#!/usr/bin/env python3
import csv,math,json
from pathlib import Path
from collections import defaultdict

D=Path("/tmp/stage6_bridge_reconstruct_host")
OUT=Path("/tmp/stage6_walk_forward")
OUT.mkdir(exist_ok=True)
FEE=.00075
SLIP_BPS=2.0
NOTIONAL=500.0
RV15_EXTREME=.183898

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
def pct(a,b):return 100*a/b if b else None
def close_fill(side,market):
    s=SLIP_BPS/10000
    return market*(1-s) if side=="LONG" else market*(1+s)
def gross(side,qty,entry,fill):
    return qty*(fill-entry) if side=="LONG" else qty*(entry-fill)
def write_csv(path,rows):
    rows=list(rows)
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with open(path,"w",newline="",encoding="utf-8-sig") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)

with open(D/"stage1_trade_master.csv",encoding="utf-8-sig") as h:MROWS=list(csv.DictReader(h))
M={str(r["position_id"]):r for r in MROWS}
with open(D/"stage1_timeline_1m.csv",encoding="utf-8-sig") as h:T=list(csv.DictReader(h))
TL=defaultdict(list)
for r in T:
    pid=str(r["position_id"])
    if ii(r["candle_close_ms"])<=ii(M[pid]["closed_at_ms"]):TL[pid].append(r)
for pid in TL:TL[pid].sort(key=lambda x:ii(x["candle_close_ms"]))

BASE={}
for pid,m in M.items():
    side=m["side"];entry=f(m["entry_price"]);qty=f(m["initial_qty"]);entry_fee=entry*qty*FEE
    path=[];opp=-1e99;oppt=None
    for r in TL.get(pid,[]):
        px=f(r["close"]);fill=close_fill(side,px)
        econ=gross(side,qty,entry,fill)-entry_fee-qty*fill*FEE
        if econ>opp:opp=econ;oppt=ii(r["candle_close_ms"])
        share=f(r.get("taker_buy_share_1m"))
        taker=None if share is None else ((share-.5) if side=="LONG" else (.5-share))
        ret3=f(r.get("ret_3m_pct"))
        sret3=ret3 if side=="LONG" else (-ret3 if ret3 is not None else None)
        micro=truth(r.get("micro_break_down")) if side=="LONG" else truth(r.get("micro_break_up"))
        path.append({"ts":ii(r["candle_close_ms"]),"market":px,"side_ret3":sret3,"taker":taker,
                     "micro":micro,"oi":f(r.get("oi_change_5m_pct")),"rv15":f(r.get("rv15_1m_pct"))})
    exitfill=f(m["exit_price"])
    final=gross(side,qty,entry,exitfill)-entry_fee-qty*exitfill*FEE
    if final>opp:opp=final;oppt=ii(m["closed_at_ms"])
    BASE[pid]={"entry":entry,"qty":qty,"fee":entry_fee,"path":path,"exitfill":exitfill,
               "opp":max(opp,final),"oppt":oppt,"opp_roi":max(opp,final)/NOTIONAL*100,
               "mfe":f(m["mfe_pct_persisted"]),"actual_net":f(m["net_pnl"])}

def evstate(x,age):
    stale=1 if age>=3 else 0
    price=1 if ((x["side_ret3"] is not None and x["side_ret3"]<=-.1) or x["micro"]) else 0
    taker=1 if (x["taker"] is not None and x["taker"]<=-.05) else 0
    oi=1 if (x["oi"] is not None and x["oi"]>=.05 and x["side_ret3"] is not None and x["side_ret3"]<=-.1) else 0
    vol=1 if (x["rv15"] is not None and x["rv15"]>=RV15_EXTREME) else 0
    return {"core":stale+price+taker,"oi":oi,"vol":vol}

def simulate_adaptive(pid,p):
    m=M[pid];b=BASE[pid];side=m["side"];entry=b["entry"];initial=b["qty"]
    remaining=initial;realized=0.;allocfee=0.;peak=-1e99;peakt=None;floor=None;close_ts=None
    for x in b["path"]:
        fill=close_fill(side,x["market"])
        econ=realized+gross(side,remaining,entry,fill)-max(0,b["fee"]-allocfee)-remaining*fill*FEE
        if econ>peak:peak=econ;peakt=x["ts"]
        age=0 if peakt is None else max(0,(x["ts"]-peakt)/60000)
        e=evstate(x,age);proi=peak/NOTIONAL*100
        if proi>=.5:
            base=p["b1"] if proi<2 else p["b2"] if proi<5 else p["b3"]
            if base>0:
                lock=base+(p["t2"] if e["core"]>=2 else 0)+(p["t3"] if e["core"]>=3 else 0)+p["oi"]*e["oi"]+p["vol"]*e["vol"]
                lock=max(.05,min(.95,lock))
                cand=peak*lock
                floor=cand if floor is None else max(floor,cand)
        if floor is not None and econ<=floor+1e-12:
            q=remaining;af=b["fee"]-allocfee
            realized+=gross(side,q,entry,fill)-af-q*fill*FEE
            remaining=0;close_ts=x["ts"];break
    if remaining>0:
        fill=b["exitfill"];q=remaining;af=b["fee"]-allocfee
        realized+=gross(side,q,entry,fill)-af-q*fill*FEE
    cap=realized/b["opp"] if b["opp"]>0 else None
    return {"position_id":pid,"net":realized,"cap":cap,"premclose":bool(close_ts and close_ts<b["oppt"]),"close_ts":close_ts}

def simulate_static(pid,arm,gb,mode):
    m=M[pid];b=BASE[pid];side=m["side"];entry=b["entry"];initial=b["qty"]
    remaining=initial;realized=0.;allocfee=0.;peak=-1e99;floor=None;reduced=False;close_ts=None
    for x in b["path"]:
        fill=close_fill(side,x["market"])
        econ=realized+gross(side,remaining,entry,fill)-max(0,b["fee"]-allocfee)-remaining*fill*FEE
        if econ>peak:peak=econ
        if peak/NOTIONAL*100>=arm and peak>0:
            cand=peak*(1-gb);floor=cand if floor is None else max(floor,cand)
        if floor is None or econ>floor+1e-12:continue
        act="CLOSE" if mode=="CLOSE_FIRST" else ("REDUCE" if not reduced else "CLOSE")
        if act=="REDUCE":
            q=remaining*.5;af=b["fee"]*(q/initial)
            realized+=gross(side,q,entry,fill)-af-q*fill*FEE
            allocfee+=af;remaining-=q;reduced=True
        else:
            q=remaining;af=b["fee"]-allocfee
            realized+=gross(side,q,entry,fill)-af-q*fill*FEE
            remaining=0;close_ts=x["ts"];break
    if remaining>0:
        fill=b["exitfill"];q=remaining;af=b["fee"]-allocfee
        realized+=gross(side,q,entry,fill)-af-q*fill*FEE
    return {"position_id":pid,"net":realized,"cap":realized/b["opp"] if b["opp"]>0 else None,
            "premclose":bool(close_ts and close_ts<b["oppt"]),"close_ts":close_ts}

CANDS={
"S5-A":{"b1":0,"b2":.25,"b3":.50,"t2":.30,"t3":0,"oi":.125,"vol":.025},
"S5-B":{"b1":0,"b2":.30,"b3":.50,"t2":.10,"t3":.20,"oi":.10,"vol":0},
"S5-C":{"b1":0,"b2":.30,"b3":.50,"t2":.25,"t3":.05,"oi":.125,"vol":0}}
RES=[]
for name,p in CANDS.items():
    rr=[simulate_adaptive(pid,p) for pid in M]
    e2=[x for x in rr if BASE[x["position_id"]]["opp_roi"]>=2]
    RES.append({"policy":name,"type":"ADAPTIVE","n":len(rr),"net_pnl":sum(x["net"] for x in rr),
                "win_rate_pct":pct(sum(x["net"]>0 for x in rr),len(rr)),
                "econ_ge2_n":len(e2),"econ_ge2_capture_median":med([x["cap"] for x in e2]),
                "econ_ge2_premature_close_pct":pct(sum(x["premclose"] for x in e2),len(e2))})
for name,arm,gb,mode in [
    ("STATIC_NET",5,.20,"CLOSE_FIRST"),("STATIC_BAL",3,.30,"CLOSE_FIRST"),("STATIC_CAPTURE",2,.20,"REDUCE_THEN_CLOSE")]:
    rr=[simulate_static(pid,arm,gb,mode) for pid in M]
    e2=[x for x in rr if BASE[x["position_id"]]["opp_roi"]>=2]
    RES.append({"policy":name,"type":"STATIC","n":len(rr),"net_pnl":sum(x["net"] for x in rr),
                "win_rate_pct":pct(sum(x["net"]>0 for x in rr),len(rr)),
                "econ_ge2_n":len(e2),"econ_ge2_capture_median":med([x["cap"] for x in e2]),
                "econ_ge2_premature_close_pct":pct(sum(x["premclose"] for x in e2),len(e2))})
actual=[BASE[pid]["actual_net"] for pid in M]
RES.append({"policy":"ACTUAL_V3","type":"ACTUAL","n":len(actual),"net_pnl":sum(actual),"win_rate_pct":pct(sum(x>0 for x in actual),len(actual))})
write_csv(OUT/"stage6_bridge_candidate_summary.csv",RES)

rows=[]
for pid,m in M.items():
    row={"position_id":pid,"symbol":m["symbol"],"side":m["side"],"opened_at_ms":m["opened_at_ms"],"closed_at_ms":m["closed_at_ms"],
         "opened_after_discovery_cutoff":ii(m["opened_at_ms"])>1790687518406,"actual_v3_net":BASE[pid]["actual_net"],
         "opp_peak_roi_pct":BASE[pid]["opp_roi"],"mfe_pct_persisted":BASE[pid]["mfe"]}
    for name,p in CANDS.items():
        x=simulate_adaptive(pid,p);row[name+"_net"]=x["net"];row[name+"_capture"]=x["cap"];row[name+"_premclose"]=x["premclose"]
    rows.append(row)
write_csv(OUT/"stage6_bridge_trade_replay.csv",rows)
print(json.dumps(RES,indent=2))