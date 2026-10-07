from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import psycopg2.extras

from market_radar.persistence import _postgres_connect

VERSION = "lq3gv-clean-velocity-anatomy-v1"
EXPECTED = 209
WINDOWS = (5, 15, 30, 60, 120)
GOOD_LABELS = {"CORRECT_RUNNER", "RECOVERED_DRAWDOWN"}
FAIL_LABELS = {"TRUE_WRONG_DIRECTION", "STALL_NO_EDGE"}
STATIC_COMPARE = (
    "f_gate_positioning_oi_change_pct",
    "f_context_taker_share_for_selected",
    "f_f_selected_slope5_norm",
    "f_f_taker_selected_share_3m",
    "f_micro_reversal_pressure",
)

def f(v: Any) -> float | None:
    try:
        x=float(v)
    except (TypeError,ValueError):
        return None
    return x if math.isfinite(x) else None

def load_csv(path: Path) -> list[dict[str,str]]:
    with path.open(encoding="utf-8-sig",newline="") as fh:
        return list(csv.DictReader(fh))

def load_positions(ids: list[str]) -> dict[str,dict[str,Any]]:
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """select position_id,side,opened_at_ms,closed_at_ms,entry_price,realized_pnl
                   from positions where position_id=any(%s)""",
                (ids,),
            )
            rows=[dict(x) for x in cur.fetchall()]
    out={str(x["position_id"]):x for x in rows}
    if len(out)!=len(ids):
        raise RuntimeError(f"position coverage {len(out)}/{len(ids)}")
    return out

def side_ret(side: str, entry: float, px: float) -> float:
    if side=="LONG":
        return (px/entry-1.0)*100.0
    return (entry/px-1.0)*100.0

def latest_at_or_before(points: list[tuple[int,float]], target: int) -> tuple[int,float] | None:
    best=None
    for ts,ret in points:
        if ts>target:
            break
        best=(ts,ret)
    return best

def first_cross(points: list[tuple[int,float]], threshold: float, favorable: bool) -> int | None:
    for ts,ret in points:
        if favorable and ret>=threshold:
            return ts
        if not favorable and ret<=-threshold:
            return ts
    return None

def derive_velocity(row: dict[str,str], p: dict[str,Any], path: list[tuple[int,float]]) -> dict[str,Any]:
    opened=int(p["opened_at_ms"])
    closed=int(p["closed_at_ms"])
    side=str(p["side"]).upper()
    entry=float(p["entry_price"])
    pts=[(int(ts),side_ret(side,entry,float(px))) for ts,px in path if int(ts)>=opened]
    out: dict[str,Any]={}

    sampled={}
    for sec in WINDOWS:
        target=opened+sec*1000
        alive=closed>=target
        got=latest_at_or_before(pts,target) if alive else None
        sampled[sec]=None if got is None else got[1]
        out[f"alive_{sec}s"]=1 if alive else 0
        out[f"ret_{sec}s"]=sampled[sec]
        out[f"v_0_{sec}s_pps"]=None if sampled[sec] is None else sampled[sec]/sec

        within=[x for x in pts if x[0]<=target] if alive else []
        if within:
            mfe=max([0.0]+[x[1] for x in within])
            mae=min([0.0]+[x[1] for x in within])
            mfe_candidates=[x for x in within if x[1]==mfe]
            mae_candidates=[x for x in within if x[1]==mae]
            t_mfe=0.0 if mfe==0 else (mfe_candidates[0][0]-opened)/1000.0
            t_mae=0.0 if mae==0 else (mae_candidates[0][0]-opened)/1000.0
            out[f"mfe_{sec}s"]=mfe
            out[f"mae_{sec}s"]=mae
            out[f"t_mfe_{sec}s"]=t_mfe
            out[f"t_mae_{sec}s"]=t_mae
            out[f"fav_speed_to_mfe_{sec}s"]=None if t_mfe<=0 else mfe/t_mfe
            out[f"adv_speed_to_mae_{sec}s"]=None if t_mae<=0 else mae/t_mae

            # Recovery from the local MAE to entry (0%) inside same horizon.
            if mae<0 and t_mae>0:
                mae_ts=mae_candidates[0][0]
                after=[x for x in within if x[0]>mae_ts]
                zero=next((x for x in after if x[1]>=0),None)
                if zero is not None:
                    dt=(zero[0]-mae_ts)/1000.0
                    out[f"recovered_to_zero_{sec}s"]=1
                    out[f"recovery_time_to_zero_{sec}s"]=dt
                    out[f"recovery_speed_to_zero_{sec}s"]=None if dt<=0 else (-mae)/dt
                else:
                    out[f"recovered_to_zero_{sec}s"]=0
                    out[f"recovery_time_to_zero_{sec}s"]=None
                    out[f"recovery_speed_to_zero_{sec}s"]=None

                end_ret=sampled[sec]
                if end_ret is not None and sec>t_mae:
                    out[f"rebound_speed_after_mae_{sec}s"]=(end_ret-mae)/(sec-t_mae)
                    out[f"recovery_efficiency_{sec}s"]=(end_ret-mae)/abs(mae)
                else:
                    out[f"rebound_speed_after_mae_{sec}s"]=None
                    out[f"recovery_efficiency_{sec}s"]=None
            else:
                out[f"recovered_to_zero_{sec}s"]=None
                out[f"recovery_time_to_zero_{sec}s"]=None
                out[f"recovery_speed_to_zero_{sec}s"]=None
                out[f"rebound_speed_after_mae_{sec}s"]=None
                out[f"recovery_efficiency_{sec}s"]=None
        else:
            for k in (
                "mfe","mae","t_mfe","t_mae","fav_speed_to_mfe","adv_speed_to_mae",
                "recovered_to_zero","recovery_time_to_zero","recovery_speed_to_zero",
                "rebound_speed_after_mae","recovery_efficiency",
            ):
                out[f"{k}_{sec}s"]=None

    intervals=((0,5),(5,15),(15,30),(30,60),(60,120))
    for a,b in intervals:
        ra=0.0 if a==0 else sampled[a]
        rb=sampled[b]
        out[f"v_{a}_{b}s_pps"]=None if ra is None or rb is None else (rb-ra)/(b-a)

    # Acceleration as change in interval velocity. Units are delta p.p./s.
    pairs=[((0,5),(5,15)),((5,15),(15,30)),((15,30),(30,60)),((30,60),(60,120))]
    for (a,b),(c,d) in pairs:
        v1=out[f"v_{a}_{b}s_pps"];v2=out[f"v_{c}_{d}s_pps"]
        out[f"dv_{a}_{b}_to_{c}_{d}"]=None if v1 is None or v2 is None else v2-v1

    # Time-to-threshold / effective speed.
    for th in (0.10,0.20,0.30,0.50):
        tf=first_cross(pts,th,True)
        ta=first_cross(pts,th,False)
        out[f"time_to_plus_{th:.2f}"]=None if tf is None else (tf-opened)/1000.0
        out[f"time_to_minus_{th:.2f}"]=None if ta is None else (ta-opened)/1000.0
        out[f"speed_to_plus_{th:.2f}"]=None if tf is None or tf<=opened else th/((tf-opened)/1000.0)
        out[f"speed_to_minus_{th:.2f}"]=None if ta is None or ta<=opened else -th/((ta-opened)/1000.0)

    # Ratios describing whether favorable motion dominates adverse motion.
    for sec in (30,60,120):
        fav=out.get(f"fav_speed_to_mfe_{sec}s")
        adv=out.get(f"adv_speed_to_mae_{sec}s")
        out[f"fav_adv_speed_ratio_{sec}s"]=None if fav is None or adv is None or adv==0 else fav/abs(adv)

    return out

def auc(vals: list[tuple[float|None,bool]]) -> float | None:
    vals=[x for x in vals if x[0] is not None]
    pos=[x for x,y in vals if y];neg=[x for x,y in vals if not y]
    if not pos or not neg:return None
    score=0.0
    for a in pos:
        for b in neg:
            score+=1.0 if a>b else 0.5 if a==b else 0.0
    return score/(len(pos)*len(neg))

def median(vals):
    vals=[x for x in vals if x is not None]
    return statistics.median(vals) if vals else None

def eval_rule(rows: list[dict[str,Any]], fn: Callable[[dict[str,Any]],bool]) -> dict[str,Any]:
    rr=[r for r in rows if fn(r)]
    if not rr:return {"n":0}
    wins=sum(bool(r["actual_win"]) for r in rr)
    classes=Counter(r["clean_label"] for r in rr)
    return {
        "n":len(rr),"wins":wins,"wr_pct":round(100*wins/len(rr),2),
        "correct_runner":classes["CORRECT_RUNNER"],
        "recovered":classes["RECOVERED_DRAWDOWN"],
        "rtf":classes["RIGHT_THEN_FAILURE"],
        "true_wrong":classes["TRUE_WRONG_DIRECTION"],
        "stall":classes["STALL_NO_EDGE"],
        "class_mix":dict(classes),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clean",default="research/liquidity_location/results/lq3f_clean_open_lane_trade_level.csv")
    ap.add_argument("--lq3c",default="research/liquidity_location/results/lq3c_trade_level.csv")
    ap.add_argument("--cache",default="/app/data/lq3f_open_lane_raw_paths.json.gz")
    ap.add_argument("--out",default="research/liquidity_location/results")
    args=ap.parse_args()

    clean=load_csv(Path(args.clean))
    if len(clean)!=EXPECTED:raise RuntimeError(f"expected {EXPECTED}, got {len(clean)}")
    ids=[r["position_id"] for r in clean]
    positions=load_positions(ids)
    with gzip.open(args.cache,"rt",encoding="utf-8") as fh:
        payload=json.load(fh)
    paths={pid:[(int(ts),float(px)) for ts,px in rows] for pid,rows in payload["paths"].items()}
    if len(paths)!=EXPECTED:raise RuntimeError(f"path coverage {len(paths)}/{EXPECTED}")

    lq3c={r["position_id"]:r for r in load_csv(Path(args.lq3c))}
    rows=[]
    for r in clean:
        pid=r["position_id"]
        x={
            "position_id":pid,"symbol":r["symbol"],"chrono_split":r["chrono_split"],
            "clean_label":r["clean_label"],"actual_win":str(r["actual_win"]).lower()=="true",
            "realized_pnl":float(r["realized_pnl"]),
        }
        # Retain static comparator features from clean matrix.
        for k in STATIC_COMPARE:x[k]=f(r.get(k))
        # Location geometry for ETA-like features.
        l=lq3c[pid]
        for k in ("nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct","nearest_demand_distance_pct"):
            x[k]=f(l.get(k))
        x.update(derive_velocity(r,positions[pid],paths[pid]))

        # Zone traversal ETA from post-entry net velocity.
        for sec in (15,30,60):
            v=x.get(f"v_0_{sec}s_pps")
            for k in ("nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct"):
                d=x.get(k)
                x[f"eta_{k}_{sec}s"]=None if d is None or v is None or v<=0 else d/v
        rows.append(x)

    tr=[r for r in rows if r["chrono_split"]=="TRAIN"]
    va=[r for r in rows if r["chrono_split"]=="VALIDATION"]
    rs=[r for r in rows if r["chrono_split"]=="RESERVE"]

    excluded={"position_id","symbol","chrono_split","clean_label","actual_win","realized_pnl"}
    noncausal_full_lifetime_prefixes=("time_to_plus_","time_to_minus_","speed_to_plus_","speed_to_minus_")
    velocity_features=[
        k for k in rows[0]
        if k not in excluded
        and k not in STATIC_COMPARE
        and not k.endswith("_distance_pct")
        and not k.startswith(noncausal_full_lifetime_prefixes)
        and not k.startswith("alive_")
    ]
    numeric_features=[
        k for k in rows[0]
        if (
            k in velocity_features
            or k in STATIC_COMPARE
            or k in ("nearest_supply_distance_pct","5m_supply_distance_pct","15m_supply_distance_pct","nearest_demand_distance_pct")
        )
        and any(r.get(k) is not None for r in rows)
    ]

    # AUC for actual winner vs all non-winners.
    auc_rows=[]
    for k in numeric_features:
        av=auc([(r.get(k),bool(r["actual_win"])) for r in rows])
        if av is None:continue
        auc_rows.append({
            "feature":k,"auc_raw":round(av,4),"auc_oriented":round(max(av,1-av),4),
            "winner_median":median([r.get(k) for r in rows if r["actual_win"]]),
            "loser_median":median([r.get(k) for r in rows if not r["actual_win"]]),
            "family":"velocity" if k in velocity_features else "static_location",
        })
    auc_rows.sort(key=lambda x:x["auc_oriented"],reverse=True)

    # Pairwise class AUCs for diagnosis.
    class_pairs={}
    for target_name,target_fn,neg_fn in (
        ("WIN_vs_TRUE_WRONG",lambda r:r["actual_win"],lambda r:r["clean_label"]=="TRUE_WRONG_DIRECTION"),
        ("WIN_vs_STALL",lambda r:r["actual_win"],lambda r:r["clean_label"]=="STALL_NO_EDGE"),
        ("WIN_vs_RTF",lambda r:r["actual_win"],lambda r:r["clean_label"]=="RIGHT_THEN_FAILURE"),
        ("RECOVERED_vs_TRUE_WRONG",lambda r:r["clean_label"]=="RECOVERED_DRAWDOWN",lambda r:r["clean_label"]=="TRUE_WRONG_DIRECTION"),
    ):
        subset=[r for r in rows if target_fn(r) or neg_fn(r)]
        ranked=[]
        for k in velocity_features:
            av=auc([(r.get(k),target_fn(r)) for r in subset])
            if av is not None:
                ranked.append((max(av,1-av),av,k,
                               median([r.get(k) for r in subset if target_fn(r)]),
                               median([r.get(k) for r in subset if neg_fn(r)])))
        ranked.sort(reverse=True)
        class_pairs[target_name]=[
            {"feature":k,"auc_oriented":round(a,4),"auc_raw":round(raw,4),
             "target_median":tm,"negative_median":nm}
            for a,raw,k,tm,nm in ranked[:20]
        ]

    # TRAIN-only threshold discovery on top velocity features.
    top_velocity=[x["feature"] for x in auc_rows if x["family"]=="velocity"][:25]
    conds=[]
    for k in top_velocity:
        vals=sorted(r[k] for r in tr if r.get(k) is not None)
        if len(vals)<30:continue
        for q in (.15,.20,.25,.30,.35,.40,.50,.60,.65,.70,.75,.80,.85):
            th=vals[min(len(vals)-1,int(q*(len(vals)-1)))]
            for op in (">=","<="):
                fn=(lambda r,k=k,th=th:r.get(k) is not None and r[k]>=th) if op==">=" else (lambda r,k=k,th=th:r.get(k) is not None and r[k]<=th)
                mt=eval_rule(tr,fn)
                if mt["n"]>=20:
                    conds.append((mt["wr_pct"],mt["n"],k,op,th,fn))
    conds.sort(key=lambda z:(z[0],z[1]),reverse=True)

    pair_rules=[]
    base=conds[:70]
    for i,a in enumerate(base):
        for b in base[i+1:]:
            if a[2]==b[2]:continue
            fn=lambda r,fa=a[5],fb=b[5]:fa(r) and fb(r)
            mt=eval_rule(tr,fn)
            if mt["n"]<15:continue
            mv=eval_rule(va,fn);mr=eval_rule(rs,fn)
            pair_rules.append({
                "features":[
                    {"key":a[2],"op":a[3],"threshold":a[4]},
                    {"key":b[2],"op":b[3],"threshold":b[4]},
                ],
                "TRAIN":mt,"VALIDATION":mv,"RESERVE":mr,
                "min_wr":min(mt.get("wr_pct",0),mv.get("wr_pct",0),mr.get("wr_pct",0)) if mv["n"] and mr["n"] else 0,
            })
    pair_rules.sort(key=lambda x:(x["min_wr"],x["TRAIN"]["wr_pct"],x["TRAIN"]["n"]),reverse=True)
    stable60=[x for x in pair_rules if x["VALIDATION"]["n"]>=5 and x["RESERVE"]["n"]>=5 and x["TRAIN"]["wr_pct"]>=60 and x["VALIDATION"]["wr_pct"]>=60 and x["RESERVE"]["wr_pct"]>=60]

    # Time-window specific best AUC.
    by_window={}
    for sec in WINDOWS:
        candidates=[x for x in auc_rows if (
            f"_{sec}s" in x["feature"] or
            x["feature"].endswith(f"_{sec}s_pps") or
            f"_{sec}s_" in x["feature"]
        ) and x["family"]=="velocity"]
        by_window[str(sec)]=candidates[:10]

    # Class summary of central velocity features.
    central=[
        "v_0_5s_pps","v_0_15s_pps","v_0_30s_pps","v_0_60s_pps","v_0_120s_pps",
        "v_5_15s_pps","v_15_30s_pps","v_30_60s_pps",
        "adv_speed_to_mae_30s","adv_speed_to_mae_60s",
        "rebound_speed_after_mae_60s","rebound_speed_after_mae_120s",
        "recovery_efficiency_60s","recovery_efficiency_120s",
        "fav_adv_speed_ratio_60s","fav_adv_speed_ratio_120s",
    ]
    class_summary={}
    for cls in ("CORRECT_RUNNER","RECOVERED_DRAWDOWN","RIGHT_THEN_FAILURE","TRUE_WRONG_DIRECTION","STALL_NO_EDGE"):
        rr=[r for r in rows if r["clean_label"]==cls]
        class_summary[cls]={"n":len(rr),"features":{k:median([r.get(k) for r in rr]) for k in central}}

    baseline={sp:eval_rule([r for r in rows if r["chrono_split"]==sp],lambda r:True) for sp in ("TRAIN","VALIDATION","RESERVE")}
    baseline["ALL"]=eval_rule(rows,lambda r:True)

    horizon_coverage={}
    for sec in WINDOWS:
        horizon_coverage[str(sec)]={
            split: sum(
                int(r.get(f"alive_{sec}s") or 0)
                for r in rows
                if split=="ALL" or r["chrono_split"]==split
            )
            for split in ("TRAIN","VALIDATION","RESERVE","ALL")
        }

    summary={
        "version":VERSION,
        "contract":{
            "rows":len(rows),"source":"clean post-entry Binance Vision aggTrades cache from LQ3F",
            "windows_seconds":list(WINDOWS),
            "velocity_units":"percentage-points per second",
            "recovery_definition":"from local MAE to first return >=0 within horizon; plus end-of-window rebound speed/efficiency",
            "threshold_selection":"TRAIN only; Validation/Reserve untouched",
            "production_authority":"NONE",
        },
        "baseline":baseline,
        "horizon_alive_coverage":horizon_coverage,
        "class_summary":class_summary,
        "auc_top_all":auc_rows[:40],
        "auc_top_velocity":[x for x in auc_rows if x["family"]=="velocity"][:40],
        "auc_top_static_compare":[x for x in auc_rows if x["feature"] in STATIC_COMPARE],
        "best_by_window":by_window,
        "class_pair_velocity_auc":class_pairs,
        "stable60_pair_count":len(stable60),
        "stable60_top":stable60[:20],
        "top_velocity_pair_rules":pair_rules[:30],
        "top_velocity_single_rules":[
            {
                "feature":k,"op":op,"threshold":th,
                "TRAIN":eval_rule(tr,fn),"VALIDATION":eval_rule(va,fn),"RESERVE":eval_rule(rs,fn)
            }
            for _,_,k,op,th,fn in conds[:30]
        ],
    }

    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/"lq3gv_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    fields=[]
    seen=set()
    for r in rows:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    with (out/"lq3gv_trade_level.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()