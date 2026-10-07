from __future__ import annotations
import argparse,csv,gzip,io,itertools,json,math,tempfile,threading,zipfile
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any
import psycopg2.extras,requests
from market_radar.persistence import _postgres_connect

VERSION="lq3gv-preentry-velocity-v1"
EXPECTED=209
LOOKBACKS=(5,15,30,60,120)
STATIC=("f_gate_positioning_oi_change_pct","f_context_taker_share_for_selected","f_f_selected_slope5_norm","f_f_taker_selected_share_3m","f_micro_reversal_pressure")
_local=threading.local()

def sess():
    if not hasattr(_local,"s"):_local.s=requests.Session()
    return _local.s
def f(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def load_csv(p):
    with Path(p).open(encoding="utf-8-sig",newline="") as fh:return list(csv.DictReader(fh))
def days(a,b):
    d=datetime.fromtimestamp(a/1000,timezone.utc).date();e=datetime.fromtimestamp(b/1000,timezone.utc).date();out=[]
    while d<=e:out.append(d.isoformat());d+=timedelta(days=1)
    return out
def load_pos(ids):
    with _postgres_connect() as c:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("select position_id,symbol,side,opened_at_ms,entry_price from positions where position_id=any(%s)",(ids,))
            rr=[dict(x) for x in cur.fetchall()]
    out={str(x["position_id"]):x for x in rr}
    if len(out)!=len(ids):raise RuntimeError(f"position coverage {len(out)}/{len(ids)}")
    return out
def download_filtered(symbol,day,windows):
    url=("https://data.binance.vision/data/futures/um/daily/aggTrades/"
         f"{symbol}/{symbol}-aggTrades-{day}.zip")
    out={pid:[] for pid,_,_ in windows};lo=min(a for _,a,_ in windows);hi=max(b for _,_,b in windows)
    with sess().get(url,timeout=120,stream=True) as resp:
        if resp.status_code!=200:raise RuntimeError(f"HTTP_{resp.status_code} {symbol} {day}")
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            for ch in resp.iter_content(1024*1024):
                if ch:tmp.write(ch)
            tmp.flush()
            with zipfile.ZipFile(tmp.name) as z:
                with z.open(z.namelist()[0]) as raw:
                    rd=csv.reader(io.TextIOWrapper(raw,encoding="utf-8"));first=next(rd,None)
                    it=rd if first and first[0]=="agg_trade_id" else itertools.chain([first],rd)
                    for row in it:
                        if not row:continue
                        try:px=float(row[1]);ts=int(row[5])
                        except:continue
                        if ts<lo:continue
                        if ts>hi:break
                        if px<=0 or not math.isfinite(px):continue
                        for pid,a,b in windows:
                            if a<=ts<=b:out[pid].append((ts,px))
    return out
def load_paths(cohort,pos,cache,workers):
    cache=Path(cache)
    if cache.exists():
        with gzip.open(cache,"rt",encoding="utf-8") as fh:p=json.load(fh)
        if p.get("version")==VERSION and len(p.get("paths",{}))==len(cohort):
            return {k:[(int(t),float(px)) for t,px in v] for k,v in p["paths"].items()},p.get("errors",[])
    groups=defaultdict(list)
    for r in cohort:
        pid=r["position_id"];opened=int(pos[pid]["opened_at_ms"]);a=opened-120000;b=opened
        for d in days(a,b):groups[(str(pos[pid]["symbol"]),d)].append((pid,a,b))
    paths={r["position_id"]:[] for r in cohort};errors=[]
    with ThreadPoolExecutor(max_workers=max(1,min(workers,2))) as pool:
        fm={pool.submit(download_filtered,s,d,w):(s,d) for (s,d),w in groups.items()}
        for fut in as_completed(fm):
            key=fm[fut]
            try:
                got=fut.result()
                for pid,rr in got.items():paths[pid].extend(rr)
            except Exception as exc:errors.append(f"{key[0]} {key[1]}: {exc}")
    for pid in paths:paths[pid].sort()
    cache.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(cache,"wt",encoding="utf-8") as fh:json.dump({"version":VERSION,"paths":paths,"errors":errors},fh)
    return paths,errors
def side_return(side,p0,p1):
    return (p1/p0-1)*100 if side=="LONG" else (p0/p1-1)*100
def latest_le(path,target):
    x=None
    for ts,px in path:
        if ts>target:break
        x=(ts,px)
    return x
def auc(vals):
    vals=[x for x in vals if x[0] is not None];p=[x for x,y in vals if y];n=[x for x,y in vals if not y]
    if not p or not n:return None
    s=0
    for a in p:
        for b in n:s+=1 if a>b else .5 if a==b else 0
    return s/(len(p)*len(n))
def ev(rows,fn):
    rr=[r for r in rows if fn(r)]
    if not rr:return {"n":0}
    wins=sum(r["actual_win"] for r in rr);c=Counter(r["clean_label"] for r in rr)
    return {"n":len(rr),"wins":wins,"wr_pct":round(100*wins/len(rr),2),
            "CR":c["CORRECT_RUNNER"],"RD":c["RECOVERED_DRAWDOWN"],"RTF":c["RIGHT_THEN_FAILURE"],"TW":c["TRUE_WRONG_DIRECTION"],"STALL":c["STALL_NO_EDGE"]}
def derive(r,p,path,lq):
    side=str(p["side"]).upper();opened=int(p["opened_at_ms"])
    anchor=latest_le(path,opened)
    if anchor is None:return {}
    anchor_px=anchor[1];prices={0:anchor_px}
    out={"pre_anchor_price":anchor_px}
    for sec in LOOKBACKS:
        q=latest_le(path,opened-sec*1000)
        prices[sec]=None if q is None else q[1]
        ret=None if q is None else side_return(side,q[1],anchor_px)
        out[f"pre_ret_{sec}s"]=ret
        out[f"pre_v_{sec}s_pps"]=None if ret is None else ret/sec
        # range in last sec window relative to anchor
        pts=[px for ts,px in path if opened-sec*1000<=ts<=opened]
        if pts:
            rs=[side_return(side,anchor_px,px) for px in pts]
            out[f"pre_range_{sec}s"]=max(rs)-min(rs)
        else:out[f"pre_range_{sec}s"]=None
    # segment velocities: older boundary -> newer boundary.
    segs=((120,60),(60,30),(30,15),(15,5),(5,0))
    for old,new in segs:
        po=prices.get(old);pn=prices.get(new)
        out[f"pre_seg_v_{old}_{new}s_pps"]=None if po is None or pn is None else side_return(side,po,pn)/(old-new)
    # acceleration toward entry.
    pairs=(((30,15),(15,5)),((15,5),(5,0)),((60,30),(30,15)))
    for (a,b),(c,d) in pairs:
        v1=out.get(f"pre_seg_v_{a}_{b}s_pps");v2=out.get(f"pre_seg_v_{c}_{d}s_pps")
        out[f"pre_dv_{a}_{b}_to_{c}_{d}"]=None if v1 is None or v2 is None else v2-v1
    # recent/medium speed ratio.
    for a,b in ((5,30),(15,60),(30,120)):
        va=out.get(f"pre_v_{a}s_pps");vb=out.get(f"pre_v_{b}s_pps")
        out[f"pre_speed_ratio_{a}_{b}"]=None if va is None or vb is None or vb==0 else va/vb
    # location travel time using approach speed
    for sec in (15,30,60):
        v=out.get(f"pre_v_{sec}s_pps")
        for k in ("nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct"):
            d=f(lq.get(k))
            out[f"pre_eta_{k}_{sec}s"]=None if d is None or v is None or v<=0 else d/v
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clean",required=True);ap.add_argument("--lq3c",required=True);ap.add_argument("--cache",required=True);ap.add_argument("--out",required=True);ap.add_argument("--workers",type=int,default=2)
    a=ap.parse_args()
    cohort=load_csv(a.clean)
    if len(cohort)!=EXPECTED:raise RuntimeError(len(cohort))
    ids=[r["position_id"] for r in cohort];pos=load_pos(ids);lq={r["position_id"]:r for r in load_csv(a.lq3c)}
    paths,errors=load_paths(cohort,pos,a.cache,a.workers)
    rows=[]
    for r in cohort:
        x={"position_id":r["position_id"],"symbol":r["symbol"],"chrono_split":r["chrono_split"],"clean_label":r["clean_label"],"actual_win":str(r["actual_win"]).lower()=="true"}
        for k in STATIC:x[k]=f(r.get(k))
        for k in ("nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct","nearest_demand_distance_pct"):x[k]=f(lq[r["position_id"]].get(k))
        x.update(derive(r,pos[r["position_id"]],paths[r["position_id"]],lq[r["position_id"]]))
        rows.append(x)
    tr=[r for r in rows if r["chrono_split"]=="TRAIN"];va=[r for r in rows if r["chrono_split"]=="VALIDATION"];rs=[r for r in rows if r["chrono_split"]=="RESERVE"]
    excluded={"position_id","symbol","chrono_split","clean_label","actual_win",*STATIC,"nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct","nearest_demand_distance_pct","pre_anchor_price"}
    feats=[k for k in rows[0] if k not in excluded]
    rankings=[]
    for k in feats:
        av=auc([(f(r.get(k)),r["actual_win"]) for r in rows])
        if av is not None:rankings.append({"feature":k,"auc_raw":round(av,4),"auc_oriented":round(max(av,1-av),4)})
    rankings.sort(key=lambda x:x["auc_oriented"],reverse=True)
    conds=[]
    for k in [x["feature"] for x in rankings[:30]]:
        vals=sorted(f(r.get(k)) for r in tr if f(r.get(k)) is not None)
        if len(vals)<50:continue
        for q in (.1,.15,.2,.25,.3,.35,.4,.5,.6,.65,.7,.75,.8,.85,.9):
            th=vals[min(len(vals)-1,int(q*(len(vals)-1)))]
            for op in (">=","<="):
                fn=(lambda r,k=k,th=th:f(r.get(k)) is not None and f(r[k])>=th) if op==">=" else (lambda r,k=k,th=th:f(r.get(k)) is not None and f(r[k])<=th)
                mt=ev(tr,fn)
                if mt["n"]>=20:conds.append((mt["wr_pct"],mt["n"],k,op,th,fn))
    conds.sort(key=lambda z:(z[0],z[1]),reverse=True)
    pairs=[]
    base=conds[:90]
    for i,x in enumerate(base):
        for y in base[i+1:]:
            # allow same feature only if it forms a valid band
            if x[2]==y[2] and x[3]==y[3]:continue
            fn=lambda r,fa=x[5],fb=y[5]:fa(r) and fb(r)
            mt,mv,mr=ev(tr,fn),ev(va,fn),ev(rs,fn)
            if mt["n"]<15 or mv["n"]<5 or mr["n"]<5:continue
            pairs.append({"features":[{"key":x[2],"op":x[3],"threshold":x[4]},{"key":y[2],"op":y[3],"threshold":y[4]}],"TRAIN":mt,"VALIDATION":mv,"RESERVE":mr,
                          "min_wr":min(mt["wr_pct"],mv["wr_pct"],mr["wr_pct"])})
    pairs.sort(key=lambda z:(z["min_wr"],z["TRAIN"]["wr_pct"],z["TRAIN"]["n"]),reverse=True)
    stable=[x for x in pairs if x["min_wr"]>=60]
    summary={"version":VERSION,"contract":{"rows":len(rows),"source":"Binance Vision pre-entry aggTrades T-120s..T0","archive_errors":errors,"threshold_selection":"TRAIN only","production_authority":"NONE"},
             "baseline":{"TRAIN":ev(tr,lambda r:True),"VALIDATION":ev(va,lambda r:True),"RESERVE":ev(rs,lambda r:True),"ALL":ev(rows,lambda r:True)},
             "auc_top_preentry_velocity":rankings[:40],"stable60_pair_count":len(stable),"stable60_top":stable[:30],
             "top_single_rules":[{"feature":k,"op":op,"threshold":th,"TRAIN":ev(tr,fn),"VALIDATION":ev(va,fn),"RESERVE":ev(rs,fn)} for _,_,k,op,th,fn in conds[:30]]}
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/"lq3gv_preentry_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    fields=[];seen=set()
    for r in rows:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    with (out/"lq3gv_preentry_trade_level.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()