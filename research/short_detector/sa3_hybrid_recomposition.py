from __future__ import annotations
import csv,json,math,gc
from pathlib import Path
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def ff(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def truth(v):return str(v).strip().lower() in {"true","1","1.0","yes"}

D=list(csv.DictReader(open(RES/"ct6a_trade_detail.csv")))
DM={q["position_id"]:q for q in D}
B={r["position_id"]:r for r in csv.DictReader(open(RES/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
T={r["position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h4a_temporal_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}

ct5=set(json.load(open(RES/"ct5b_summary.json"))["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(RES/"ct6c_veto_trade_detail.csv"))}
ct7={r["position_id"] for r in csv.DictReader(open(RES/"ct7c_trade_detail.csv"))}
sa={r["position_id"]:r for r in csv.DictReader(open(RES/"sa2_candidate_trade_detail.csv"))}
q95={pid for pid,r in sa.items() if r["Q95_AGGRESSIVE"]=="True"}
hard_drop=ct5|ct6
negative_union=ct7|q95
rescuable=negative_union-hard_drop

RPOS=json.load(open("/tmp/s10f_db364.json"))["positions"]
FPOS={str(x["position_id"]):x for x in json.load(open("/tmp/s10j5_positions.json"))}
RC=Path("/tmp/ct4_research_archive")
FC=Path("/tmp/s10j5_archive")

def rawj(p):
    x=p.get("raw_json")
    if isinstance(x,str):
        try:return json.loads(x or "{}")
        except:return {}
    return x or {}
def dstr(ms):return datetime.fromtimestamp(int(ms)/1000,timezone.utc).date().isoformat()
def drange(a,b):
    d=datetime.fromtimestamp(int(a)/1000,timezone.utc).date()
    e=datetime.fromtimestamp(int(b)/1000,timezone.utc).date()
    out=[]
    while d<=e:
        out.append(d.isoformat());d+=timedelta(days=1)
    return out
def side_ret(entry,px):return 100*(entry/px-1)
def entry_fill_short(mkt,slip):return mkt*(1-slip/10000)
def exit_fill_short(mkt,slip):return mkt*(1+slip/10000)
def cachefile(src,kind,sym,d):return (RC if src=="research" else FC)/f"{kind}__{sym}__{d}.json"
def kline_open(src,sym,ms):
    p=cachefile(src,"k",sym,dstr(ms))
    if not p.exists():return None
    for x in json.loads(p.read_text()):
        try:
            if int(x[0])==int(ms):return float(x[1])
        except:pass
    return None
def load_path(src,sym,start,end):
    out=[]
    for dd in drange(start,end):
        p=cachefile(src,"a",sym,dd)
        if not p.exists():continue
        rows=json.loads(p.read_text())
        out.extend((int(x[0]),float(x[1])) for x in rows if start<=int(x[0])<=end)
        del rows;gc.collect()
    out.sort(key=lambda x:x[0])
    return out
def mdata(p):
    raw=rawj(p)
    return float(raw.get("slippage_bps",2.0)),float(raw.get("fee_rate",.00075)),float(raw.get("initial_notional_usdt",500.0))
def calc(entry_fill,mkt,p):
    sl,fee,notional=mdata(p)
    q=notional/entry_fill
    ef=notional*fee
    fill=exit_fill_short(mkt,sl)
    xf=q*fill*fee
    usd=q*(entry_fill-fill)-ef-xf
    return usd,100*usd/notional
def samples(entry_ms,entry_market,entry_fill,end,tr):
    n=entry_ms+5000;last=entry_market;out=[]
    for ts,px in tr:
        while n<ts and n<=end:
            out.append((n,last,side_ret(entry_fill,last)));n+=5000
        last=px
        while n==ts and n<=end:
            out.append((n,last,side_ret(entry_fill,last)));n+=5000
    while n<=end:
        out.append((n,last,side_ret(entry_fill,last)));n+=5000
    return out
def replay(src,p,sym,entry_ms,entry_market,entry_fill):
    end=int(p["closed_at_ms"])
    tr=load_path(src,sym,entry_ms,end)
    def hold():
        mkt=tr[-1][1] if tr else entry_market
        return {"pnl":calc(entry_fill,mkt,p)[0],"reason":"HIST_TIME_FALLBACK"}
    sa=samples(entry_ms,entry_market,entry_fill,end,tr)
    peak=-999.0;runner=False;rc=0
    for ts,px,pnl in sa:
        peak=max(peak,pnl)
        if not runner and peak>=1.5:runner=True
        if runner:
            rc=rc+1 if pnl<=peak*.90 else 0
            if rc>=2:return {"pnl":calc(entry_fill,px,p)[0],"reason":"RUNNER_CLOSE"}
            continue
        if peak>=.5 and pnl<=peak*.75:
            return {"pnl":calc(entry_fill,px,p)[0],"reason":"FULL_CLOSE_050"}
    touched=False;armed=False
    _,_,notional=mdata(p)
    for ts,px in tr:
        gp=side_ret(entry_fill,px)
        net=100*calc(entry_fill,px,p)[0]/notional
        if gp>=.10:touched=True
        if touched and net>=0 and not armed:
            armed=True;continue
        if armed and net<=0:
            return {"pnl":calc(entry_fill,px,p)[0],"reason":"BE0.10"}
    return hold()


def trow(q):return T[q["position_id"]] if q["source"]=="research" else F[q["position_id"]]
def value(q,k):
    z=trow(q)
    if k.startswith("d"):
        h=int(k[1]);s=k[3:];a=ff(z.get(f"t{h}_{s}"));b=ff(z.get(f"t{h-1}_{s}"))
        return None if a is None or b is None else a-b
    return ff(z.get(k))
def qt(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w
def direction(k):return "LOW" if "micro_decay" in k else "HIGH"

train=[q for q in D if q["block"]=="Research_Discovery" and truth(q["strong"])]

RULES={
 "A1_T3_MFE_TAKER_VWAP":{
   "h":3,"need":2,"p":0.70,
   "features":["d3_confirm_mfe_pct","t3_confirm_selected_taker_share","t3_delta_micro_selected_vwap_extension_20"],
 },
 "A2_T3_MFE_TRADES_REL_DECAY":{
   "h":3,"need":3,"p":0.60,
   "features":["t3_confirm_mfe_pct","d3_confirm_trades","t3_delta_f_coin_minus_market_15m","t3_f_micro_decay_3_vs_prev3"],
 },
 "A3_T2_MFE_TRADES_VWAP":{
   "h":2,"need":3,"p":0.50,
   "features":["d2_confirm_mfe_pct","d2_confirm_trades","t2_delta_micro_selected_vwap_extension_20"],
 },
 "M1_T2_BOB_MARGIN":{
   "h":2,"need":2,"p":0.80,
   "features":["d2_confirm_side_return_pct","t2_confirm_selected_taker_share","t2_delta_micro_selected_vwap_extension_20"],
 },
}
TH={}
for name,r in RULES.items():
    th={}
    for k in r["features"]:
        xs=[value(q,k) for q in train if value(q,k) is not None]
        p=r["p"] if direction(k)=="HIGH" else 1-r["p"]
        th[k]=qt(xs,p)
    TH[name]=th

def hit(q,name):
    r=RULES[name]
    return sum(
        value(q,k) is not None and (
            value(q,k)>=TH[name][k] if direction(k)=="HIGH" else value(q,k)<=TH[name][k]
        )
        for k in r["features"]
    )>=r["need"]

def delayed(pid,h,rule):
    q=DM[pid];src=q["source"];sym=q["symbol"];p=RPOS[pid] if src=="research" else FPOS[pid]
    target=int(float(trow(q)[f"t{h}_target_ms"]));entry_ms=(target//60000)*60000+60000
    mkt=kline_open(src,sym,entry_ms)
    if mkt is None or int(p["closed_at_ms"])<=entry_ms:
        return {"executable":False,"entry_ms":entry_ms,"h":h,"rule":rule,"pnl":None,"reason":"NO_EXECUTABLE_ENTRY"}
    ent=entry_fill_short(mkt,mdata(p)[0]);rr=replay(src,p,sym,entry_ms,mkt,ent)
    return {"executable":True,"entry_ms":entry_ms,"h":h,"rule":rule,"pnl":float(rr["pnl"]),"reason":rr["reason"]}

# Earliest rescue branch wins; rule names break equal-horizon ties deterministically.
candidates={}
for q in D:
    pid=q["position_id"]
    if pid not in rescuable:continue
    hs=sorted((RULES[name]["h"],name) for name in RULES if hit(q,name))
    if hs:candidates[pid]=hs[0]

rescue={}
for pid,(h,name) in candidates.items():
    rr=delayed(pid,h,name)
    if rr["executable"]:rescue[pid]=rr

def build(drop_set,rescue_map=None):
    rescue_map=rescue_map or {}
    out=[]
    for pid,b in B.items():
        if pid in drop_set:
            if pid not in rescue_map:continue
            rr=rescue_map[pid];pnl=rr["pnl"]
            out.append({"position_id":pid,"symbol":b["symbol"],"source":b["source"],"block":b["block"],"strong":truth(b["strong"]),"mfe_bucket":DM[pid]["mfe_bucket"],"pnl":pnl,"win":pnl>0,"rescued":True,"h":rr["h"],"rule":rr["rule"],"reason":rr["reason"]})
        elif truth(b["executable"]):
            pnl=float(b["pnl"])
            out.append({"position_id":pid,"symbol":b["symbol"],"source":b["source"],"block":b["block"],"strong":truth(b["strong"]),"mfe_bucket":DM[pid]["mfe_bucket"],"pnl":pnl,"win":pnl>0,"rescued":False,"h":0,"rule":"","reason":b["reason"]})
    return out

def met(rows):
    rows=list(rows)
    return {"exec":len(rows),"wins":sum(r["win"] for r in rows),"wr":sum(r["win"] for r in rows)/len(rows) if rows else 0.0,"strong_exec":sum(r["strong"] for r in rows),"strong_retention_vs_ct4":sum(r["strong"] for r in rows)/246,"pnl":sum(r["pnl"] for r in rows)}

# comparators
old_rescue={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7d_rescue_detail.csv")) if truth(r["executable"])}
current=build(ct5|ct6|ct7,{pid:{"pnl":float(r["pnl"]),"h":3,"rule":"CT7D_CLEAN2","reason":r["reason"]} for pid,r in old_rescue.items()})
no_rescue=build(hard_drop|negative_union)
primary=build(hard_drop|negative_union,rescue)

# Q95 stacked with old CLEAN2 comparator
q95_clean=build(ct5|ct6|ct7|q95,{pid:{"pnl":float(r["pnl"]),"h":3,"rule":"CT7D_CLEAN2","reason":r["reason"]} for pid,r in old_rescue.items()})

summary={
 "stage":"SHORT-SA3",
 "status":"HYBRID_RECOMPOSITION_RESEARCH_PASS_NOT_RUNTIME_READY",
 "contract":{"hard_vetoes":["CT5B","CT6C"],"negative_union":["CT7C","SA2_Q95"],"positive_rescue":"SA3 A1/A2/A3/M1 earliest T2/T3","runtime_change":False},
 "thresholds":TH,
 "comparators":{"CURRENT_CT7_STACK":met(current),"Q95_HYBRID_NO_RESCUE":met(no_rescue),"Q95_HYBRID_CLEAN2":met(q95_clean)},
 "primary":met(primary),
}
summary["primary"]["target_exec"]=sum(r["mfe_bucket"]=="TARGET_GE_1P00" for r in primary)
summary["primary"]["target_retention_vs_ct4"]=summary["primary"]["target_exec"]/279
summary["primary"]["rescued_exec"]=sum(r["rescued"] for r in primary)
summary["primary"]["rescued_strong"]=sum(r["rescued"] and r["strong"] for r in primary)
summary["primary"]["rescued_nonstrong"]=sum(r["rescued"] and not r["strong"] for r in primary)
summary["primary"]["rescued_pnl"]=sum(r["pnl"] for r in primary if r["rescued"])
summary["primary"]["rescued_wins"]=sum(r["rescued"] and r["win"] for r in primary)

summary["source"]={s:met([r for r in primary if r["source"]==s]) for s in ("research","fresh")}
blocks=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]
summary["block"]={b:met([r for r in primary if r["block"]==b]) for b in blocks}
summary["block_vs_current"]={}
for b in blocks:
    a=met([r for r in current if r["block"]==b]);z=summary["block"][b]
    summary["block_vs_current"][b]={"current_pnl":a["pnl"],"sa3_pnl":z["pnl"],"delta":z["pnl"]-a["pnl"],"current_strong":a["strong_exec"],"sa3_strong":z["strong_exec"]}
summary["mfe"]={k:met([r for r in primary if r["mfe_bucket"]==k]) for k in ("BAD_A_LT_0P30","BAD_B_0P30_0P50","GRAY_0P50_1P00","TARGET_GE_1P00")}

rescued_rows=[r for r in primary if r["rescued"]]
summary["rescue_by_block"]={b:met([r for r in rescued_rows if r["block"]==b]) for b in blocks if any(r["block"]==b for r in rescued_rows)}

assert summary["primary"]["exec"]==744
assert summary["primary"]["strong_exec"]==234
assert abs(summary["primary"]["pnl"]-(-67.094519))<0.001
assert summary["primary"]["strong_retention_vs_ct4"]>=0.95

(RES/"sa3_summary.json").write_text(json.dumps(summary,indent=2))
with open(RES/"sa3_rescue_trade_detail.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","mfe_bucket","strong","pnl","win","h","rule","reason"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in rescued_rows:w.writerow({k:r[k] for k in fields})
with open(RES/"sa3_architecture_comparison.csv","w",newline="") as f:
    fields=["architecture","exec","wins","wr","strong_exec","strong_retention_vs_ct4","pnl"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for name,z in [("CURRENT_CT7_STACK",met(current)),("Q95_HYBRID_NO_RESCUE",met(no_rescue)),("Q95_HYBRID_CLEAN2",met(q95_clean)),("SA3_PRIMARY",met(primary))]:
        w.writerow({"architecture":name,**{k:z[k] for k in fields if k!="architecture"}})

print("CURRENT",met(current))
print("NO_RESCUE",met(no_rescue))
print("Q95_CLEAN2",met(q95_clean))
print("PRIMARY",summary["primary"])
print("SOURCE",summary["source"])
print("BLOCK")
for b,z in summary["block_vs_current"].items():print(b,z)
print("MFE",summary["mfe"])
print("RESCUE",[(r["symbol"],r["strong"],round(r["pnl"],4),r["h"],r["rule"],r["reason"]) for r in rescued_rows])