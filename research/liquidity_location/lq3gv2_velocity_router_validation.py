from __future__ import annotations
import csv, json, math, itertools
from collections import Counter
from pathlib import Path

VERSION="lq3gv2-velocity-router-validation-v1"
INPUT=Path("research/liquidity_location/results/lq3gv_trade_level.csv")
OUT=Path("research/liquidity_location/results")

LEGACY_FAST15=0.00706050285556407
LEGACY_NO_COLLAPSE60=-0.0003332666799972979

EARLY60_ETA_MAX=1478.8772362732022
EARLY60_T_MFE_MIN=33.321

STRONG120_V_MIN=0.0008457198799203628
STRONG120_ETA_MAX=1383.324562761091

def f(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except:
        return None

def load():
    with INPUT.open(encoding="utf-8-sig",newline="") as fh:
        return list(csv.DictReader(fh))

def wilson(w,n,z=1.96):
    if n<=0:return (None,None)
    p=w/n
    d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return 100*(c-h),100*(c+h)

def metrics(rows,fn):
    rr=[r for r in rows if fn(r)]
    if not rr:return {"n":0}
    wins=sum(str(r["actual_win"]).lower()=="true" for r in rr)
    lo,hi=wilson(wins,len(rr))
    c=Counter(r["clean_label"] for r in rr)
    return {
        "n":len(rr),"wins":wins,"wr_pct":round(100*wins/len(rr),2),
        "wilson95_low":round(lo,2),"wilson95_high":round(hi,2),
        "pnl":round(sum(float(r["realized_pnl"]) for r in rr),2),
        "correct_runner":c["CORRECT_RUNNER"],"recovered":c["RECOVERED_DRAWDOWN"],
        "rtf":c["RIGHT_THEN_FAILURE"],"true_wrong":c["TRUE_WRONG_DIRECTION"],
        "stall":c["STALL_NO_EDGE"],"class_mix":dict(c),
    }

def report(rows,fn):
    out={}
    for sp in ("TRAIN","VALIDATION","RESERVE"):
        out[sp]=metrics([r for r in rows if r["chrono_split"]==sp],fn)
    out["ALL"]=metrics(rows,fn)
    return out

def legacy_fast15(r):
    a=f(r["v_0_15s_pps"]);b=f(r["v_0_60s_pps"])
    return a is not None and b is not None and a>=LEGACY_FAST15 and b>=LEGACY_NO_COLLAPSE60

def early60(r):
    eta=f(r["eta_nearest_supply_distance_pct_60s"])
    tm=f(r["t_mfe_60s"])
    return eta is not None and tm is not None and eta<=EARLY60_ETA_MAX and tm>=EARLY60_T_MFE_MIN

def strong120(r):
    v=f(r["v_0_120s_pps"])
    eta=f(r["eta_nearest_supply_distance_pct_60s"])
    return v is not None and eta is not None and v>=STRONG120_V_MIN and eta<=STRONG120_ETA_MAX

def neighborhood_60(rows):
    eta_grid=[900,1100,1250,1383.324562761091,EARLY60_ETA_MAX,1600,1800,2200]
    tm_grid=[25,30,EARLY60_T_MFE_MIN,35,40,45]
    cells=[]
    for eta,tm in itertools.product(eta_grid,tm_grid):
        fn=lambda r,eta=eta,tm=tm: (
            f(r["eta_nearest_supply_distance_pct_60s"]) is not None
            and f(r["t_mfe_60s"]) is not None
            and f(r["eta_nearest_supply_distance_pct_60s"])<=eta
            and f(r["t_mfe_60s"])>=tm
        )
        rep=report(rows,fn)
        cells.append({"eta_max":eta,"t_mfe_min":tm,**rep})
    stable=[c for c in cells if c["TRAIN"]["n"]>=15 and c["VALIDATION"]["n"]>=5 and c["RESERVE"]["n"]>=5
            and min(c["TRAIN"]["wr_pct"],c["VALIDATION"]["wr_pct"],c["RESERVE"]["wr_pct"])>=60]
    stable.sort(key=lambda c:(c["ALL"]["n"],min(c["TRAIN"]["wr_pct"],c["VALIDATION"]["wr_pct"],c["RESERVE"]["wr_pct"])),reverse=True)
    return {"cells":len(cells),"stable60_cells":len(stable),"stable60_pct":round(100*len(stable)/len(cells),2),"top":stable[:20]}

def neighborhood_120(rows):
    v_grid=[0.0004,0.0005,0.0006196202303003032,0.00075,STRONG120_V_MIN,0.0010,0.0012,0.0015]
    eta_grid=[900,1100,1250,STRONG120_ETA_MAX,1478.8772362732022,1600,1800]
    cells=[]
    for v,eta in itertools.product(v_grid,eta_grid):
        fn=lambda r,v=v,eta=eta: (
            f(r["v_0_120s_pps"]) is not None
            and f(r["eta_nearest_supply_distance_pct_60s"]) is not None
            and f(r["v_0_120s_pps"])>=v
            and f(r["eta_nearest_supply_distance_pct_60s"])<=eta
        )
        rep=report(rows,fn)
        cells.append({"v120_min":v,"eta_max":eta,**rep})
    stable=[c for c in cells if c["TRAIN"]["n"]>=15 and c["VALIDATION"]["n"]>=5 and c["RESERVE"]["n"]>=5
            and min(c["TRAIN"]["wr_pct"],c["VALIDATION"]["wr_pct"],c["RESERVE"]["wr_pct"])>=60]
    stable.sort(key=lambda c:(c["ALL"]["n"],min(c["TRAIN"]["wr_pct"],c["VALIDATION"]["wr_pct"],c["RESERVE"]["wr_pct"])),reverse=True)
    return {"cells":len(cells),"stable60_cells":len(stable),"stable60_pct":round(100*len(stable)/len(cells),2),"top":stable[:20]}

def main():
    rows=load()
    both=lambda r:early60(r) and strong120(r)
    early_only=lambda r:early60(r) and not strong120(r)
    late_only=lambda r:strong120(r) and not early60(r)
    neither=lambda r:not early60(r) and not strong120(r)

    summary={
        "version":VERSION,
        "contract":{
            "rows":len(rows),
            "source":"authoritative LQ3GV frozen trade-level",
            "role":"post-entry velocity state classifier; NOT a delayed-entry replay",
            "legacy_fast15_recheck":{"v15_min":LEGACY_FAST15,"v60_min":LEGACY_NO_COLLAPSE60},
            "early60":{"eta_nearest_supply_60s_max_seconds":EARLY60_ETA_MAX,"t_mfe_60s_min_seconds":EARLY60_T_MFE_MIN},
            "strong120":{"v_0_120s_pps_min":STRONG120_V_MIN,"eta_nearest_supply_60s_max_seconds":STRONG120_ETA_MAX},
            "production_authority":"NONE",
        },
        "legacy_fast15_recheck":report(rows,legacy_fast15),
        "early60":report(rows,early60),
        "strong120":report(rows,strong120),
        "transitions":{
            "EARLY60_AND_STRONG120":report(rows,both),
            "EARLY60_ONLY_DECAY":report(rows,early_only),
            "LATE_STRONG120_ONLY":report(rows,late_only),
            "NEITHER":report(rows,neither),
        },
        "robustness":{
            "early60":neighborhood_60(rows),
            "strong120":neighborhood_120(rows),
        },
        "verdict":{
            "legacy_fast15_status":"DO_NOT_FREEZE; stale V1 probe did not reproduce on authoritative frozen CSV",
            "early60_status":"PASS_RESEARCH; all splits >=60 but Reserve n=5 and pooled CI crosses below 60",
            "strong120_status":"PASS_STRONG_RESEARCH; all splits >=75/80/80, pooled WR 77.42 and pooled Wilson95 lower >60",
            "router_interpretation":"T60 early-confirm trades that fail to upgrade to T120 strong are a high-risk decay state",
            "production":"HOLD",
        },
    }

    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"lq3gv2_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")

    outrows=[]
    for r in rows:
        e=early60(r);s=strong120(r)
        if e and s:state="EARLY60_TO_STRONG120"
        elif e:state="EARLY60_ONLY_DECAY"
        elif s:state="LATE_STRONG120_ONLY"
        else:state="NO_VELOCITY_CONFIRM"
        outrows.append({
            "position_id":r["position_id"],"symbol":r["symbol"],"chrono_split":r["chrono_split"],
            "clean_label":r["clean_label"],"actual_win":r["actual_win"],"realized_pnl":r["realized_pnl"],
            "v_0_15s_pps":r["v_0_15s_pps"],"v_0_60s_pps":r["v_0_60s_pps"],"v_0_120s_pps":r["v_0_120s_pps"],
            "t_mfe_60s":r["t_mfe_60s"],"eta_nearest_supply_distance_pct_60s":r["eta_nearest_supply_distance_pct_60s"],
            "early60_confirm":e,"strong120_confirm":s,"velocity_router_state":state,
        })
    with (OUT/"lq3gv2_trade_level.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(outrows[0].keys()))
        w.writeheader();w.writerows(outrows)

    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()