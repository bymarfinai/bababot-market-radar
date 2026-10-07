from __future__ import annotations

import argparse
import csv
import gzip
import io
import itertools
import json
import math
import statistics
import tempfile
import threading
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import psycopg2.extras
import requests

from market_radar.persistence import _postgres_connect

VERSION = "lq3f-clean-open-lane-rebuild-v1"
EXPECTED = 209
EARLY_WINDOW_MS = 30 * 60_000
EARLY_ADVERSE = -0.35
WRONG_CEILING = 0.35
DIRECTIONAL = 0.50
RUNNER = 1.00

FEATURES = [
    "f_gate_side_ret_1m_pct","f_gate_side_ret_3m_pct",
    "f_gate_price_drift_pct","f_gate_side_adjusted_drift_pct",
    "f_gate_impulse_concentration_ratio","f_gate_taker_buy_share_1m",
    "f_gate_taker_share_for_selected","f_gate_positioning_oi_change_pct",
    "f_gate_aligned_family_count","f_gate_opposing_family_count",
    "f_context_taker_buy_share","f_context_taker_share_for_selected",
    "f_context_raw_oi_change_pct","f_new_micro_accel_1_vs_3",
    "f_new_accel_5_vs_15","f_new_flow_gap_gate",
    "f_micro_side_ret_1m","f_micro_side_ret_3m","f_micro_side_ret_5m",
    "f_micro_side_ret_10m","f_micro_side_ret_15m","f_micro_side_ret_30m",
    "f_micro_selected_clv_last","f_micro_rejection_wick_last",
    "f_micro_selected_body_last","f_micro_consecutive_selected_bars",
    "f_micro_range_ratio_3v20","f_micro_volume_ratio_3v20",
    "f_micro_trades_ratio_3v20","f_micro_selected_vwap_extension_20",
    "f_micro_reversal_pressure","f_f_coin_minus_market_5m",
    "f_f_coin_minus_market_15m","f_f_coin_minus_market_30m",
    "f_f_selected_slope5_norm","f_f_taker_selected_share_3m",
    "f_f_oi_change_30m_pct",
]

_local=threading.local()

def sess():
    if not hasattr(_local,"s"):
        _local.s=requests.Session()
    return _local.s

def load_csv(path:Path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def f(v):
    try:
        x=float(v)
    except (TypeError,ValueError):
        return None
    return x if math.isfinite(x) else None

def days(a:int,b:int):
    d=datetime.fromtimestamp(a/1000,timezone.utc).date()
    e=datetime.fromtimestamp(b/1000,timezone.utc).date()
    out=[]
    while d<=e:
        out.append(d.isoformat())
        d+=timedelta(days=1)
    return out

def load_positions(ids):
    with _postgres_connect() as c:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""select position_id,symbol,side,opened_at_ms,closed_at_ms,
                                  entry_price,realized_pnl,realized_pnl_pct,raw_json
                           from positions where position_id=any(%s)""",(ids,))
            rows=[dict(x) for x in cur.fetchall()]
    out={str(x["position_id"]):x for x in rows}
    if len(out)!=len(ids):
        raise RuntimeError(f"position coverage {len(out)}/{len(ids)}")
    return out

def download_filtered(symbol,day,windows):
    url=("https://data.binance.vision/data/futures/um/daily/aggTrades/"
         f"{symbol}/{symbol}-aggTrades-{day}.zip")
    out={pid:[] for pid,_,_ in windows}
    lo=min(x[1] for x in windows); hi=max(x[2] for x in windows)
    with sess().get(url,timeout=120,stream=True) as resp:
        if resp.status_code!=200:
            raise RuntimeError(f"HTTP_{resp.status_code} {symbol} {day}")
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            for chunk in resp.iter_content(1024*1024):
                if chunk: tmp.write(chunk)
            tmp.flush()
            with zipfile.ZipFile(tmp.name) as z:
                with z.open(z.namelist()[0]) as raw:
                    rd=csv.reader(io.TextIOWrapper(raw,encoding="utf-8"))
                    first=next(rd,None)
                    it=rd if first and first[0]=="agg_trade_id" else itertools.chain([first],rd)
                    for row in it:
                        if not row: continue
                        try:
                            px=float(row[1]); ts=int(row[5])
                        except (ValueError,IndexError,TypeError):
                            continue
                        if ts<lo: continue
                        if ts>hi: break
                        if px<=0 or not math.isfinite(px): continue
                        for pid,a,b in windows:
                            if a<=ts<=b:
                                out[pid].append((ts,px))
    return out

def load_paths(cohort,positions,cache,workers):
    if cache.exists():
        with gzip.open(cache,"rt",encoding="utf-8") as fh:
            p=json.load(fh)
        if p.get("version")==VERSION and len(p.get("paths",{}))==len(cohort):
            return {k:[(int(t),float(px)) for t,px in v] for k,v in p["paths"].items()},p.get("errors",[])
    groups=defaultdict(list)
    for row in cohort:
        pid=row["position_id"]; p=positions[pid]
        a=int(p["opened_at_ms"]); b=int(p["closed_at_ms"])
        for d in days(a,b):
            groups[(str(p["symbol"]),d)].append((pid,a,b))
    paths={row["position_id"]:[] for row in cohort}; errors=[]
    with ThreadPoolExecutor(max_workers=max(1,min(workers,2))) as pool:
        fm={pool.submit(download_filtered,s,d,w):(s,d) for (s,d),w in groups.items()}
        for fut in as_completed(fm):
            key=fm[fut]
            try:
                got=fut.result()
                for pid,rows in got.items(): paths[pid].extend(rows)
            except Exception as exc:
                errors.append(f"{key[0]} {key[1]}: {exc}")
    for pid in paths: paths[pid].sort()
    cache.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(cache,"wt",encoding="utf-8") as fh:
        json.dump({"version":VERSION,"paths":paths,"errors":errors},fh)
    return paths,errors

def clean_label(p,path):
    side=str(p["side"]).upper(); entry=float(p["entry_price"]); opened=int(p["opened_at_ms"])
    vals=[]
    for ts,px in path:
        if side=="LONG": ret=(px/entry-1)*100
        else: ret=(entry/px-1)*100
        vals.append((int(ts),ret))
    # entry is exact zero-excursion baseline
    mfe=max([0.0]+[x[1] for x in vals])
    mae=min([0.0]+[x[1] for x in vals])
    early=[x for x in vals if x[0]<=opened+EARLY_WINDOW_MS]
    early_mae=min([0.0]+[x[1] for x in early])
    adv=[x for x in early if x[1]<=EARLY_ADVERSE]
    direc=[x for x in vals if x[1]>=DIRECTIONAL]
    first_adv=min((x[0] for x in adv),default=None)
    first_dir=min((x[0] for x in direc),default=None)
    profitable=float(p.get("realized_pnl") or 0)>0
    if mfe>=DIRECTIONAL and not profitable:
        label="RIGHT_THEN_FAILURE"
    elif mfe>=DIRECTIONAL and profitable and first_adv is not None and first_dir is not None and first_adv<first_dir:
        label="RECOVERED_DRAWDOWN"
    elif mfe>=DIRECTIONAL and profitable:
        label="CORRECT_RUNNER"
    elif mfe<WRONG_CEILING and first_adv is not None and not profitable:
        label="TRUE_WRONG_DIRECTION"
    else:
        label="STALL_NO_EDGE"
    return {
        "clean_label":label,"clean_mfe_pct":mfe,"clean_mae_pct":mae,
        "clean_early_mae_pct":early_mae,"clean_first_adverse_ms":first_adv,
        "clean_first_directional_ms":first_dir,"clean_reached_runner":mfe>=RUNNER,
        "actual_win":profitable,
    }

def auc(vals):
    vals=[x for x in vals if x[0] is not None]
    p=[x for x,y in vals if y]; n=[x for x,y in vals if not y]
    if not p or not n:return None
    score=0.0
    for a in p:
        for b in n:
            score+=1 if a>b else .5 if a==b else 0
    return score/(len(p)*len(n))

def eval_rule(rows,fn):
    rr=[r for r in rows if fn(r)]
    if not rr:return {"n":0}
    wins=sum(r["actual_win"] for r in rr)
    clean=Counter(r["clean_label"] for r in rr)
    return {
        "n":len(rr),"wins":wins,"wr_pct":round(100*wins/len(rr),2),
        "good":clean["CORRECT_RUNNER"]+clean["RECOVERED_DRAWDOWN"],
        "rtf":clean["RIGHT_THEN_FAILURE"],
        "bad":clean["TRUE_WRONG_DIRECTION"]+clean["STALL_NO_EDGE"],
        "class_mix":dict(clean),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--lq3c",default="research/liquidity_location/results/lq3c_trade_level.csv")
    ap.add_argument("--static",default="/app/data/wd5h1_thesis_labeled_features.csv")
    ap.add_argument("--cache",default="/app/data/lq3f_open_lane_raw_paths.json.gz")
    ap.add_argument("--out",default="research/liquidity_location/results")
    ap.add_argument("--workers",type=int,default=2)
    args=ap.parse_args()

    lq=load_csv(Path(args.lq3c))
    cohort=[r for r in lq if str(r.get("lq3c_open_lane") or "").lower()=="true"]
    if len(cohort)!=EXPECTED: raise RuntimeError(f"expected {EXPECTED}, got {len(cohort)}")
    ids=[r["position_id"] for r in cohort]
    pos=load_positions(ids)
    paths,errors=load_paths(cohort,pos,Path(args.cache),args.workers)
    static={r["meta_position_id"]:r for r in load_csv(Path(args.static))}

    rows=[]
    for r in cohort:
        pid=r["position_id"]
        clean=clean_label(pos[pid],paths[pid])
        s=static[pid]
        x={
            "position_id":pid,"symbol":r["symbol"],"chrono_split":r["chrono_split"],
            "legacy_label":r["future_outcome_label"],
            "legacy_mfe_pct":f(r["future_max_mfe_pct"]),
            "realized_pnl":float(pos[pid].get("realized_pnl") or 0),
            "path_points":len(paths[pid]),
            **clean,
        }
        for k in FEATURES:x[k]=f(s.get(k))
        rows.append(x)

    splits=["TRAIN","VALIDATION","RESERVE"]
    baseline={sp:eval_rule([r for r in rows if r["chrono_split"]==sp],lambda r:True) for sp in splits}
    baseline["ALL"]=eval_rule(rows,lambda r:True)

    legacy=Counter(r["legacy_label"] for r in rows)
    clean=Counter(r["clean_label"] for r in rows)
    matrix=Counter((r["legacy_label"],r["clean_label"]) for r in rows)

    tr=[r for r in rows if r["chrono_split"]=="TRAIN"]
    va=[r for r in rows if r["chrono_split"]=="VALIDATION"]
    rs=[r for r in rows if r["chrono_split"]=="RESERVE"]

    ranking=[]
    for k in FEATURES:
        av=auc([(r[k],r["actual_win"]) for r in rows])
        if av is not None: ranking.append((max(av,1-av),av,k))
    ranking.sort(reverse=True)

    # TRAIN-only single thresholds.
    conds=[]
    for _,_,k in ranking[:20]:
        vals=sorted(r[k] for r in tr if r[k] is not None)
        if not vals:continue
        for q in (.15,.20,.25,.30,.35,.40,.50,.60,.65,.70,.75,.80,.85):
            th=vals[min(len(vals)-1,int(q*(len(vals)-1)))]
            for op in (">=","<="):
                fn=(lambda r,k=k,th=th:r[k] is not None and r[k]>=th) if op==">=" else (lambda r,k=k,th=th:r[k] is not None and r[k]<=th)
                m=eval_rule(tr,fn)
                if m["n"]>=20:
                    conds.append((m["wr_pct"],m["n"],k,op,th,fn))
    conds.sort(key=lambda z:(z[0],z[1]),reverse=True)

    pairs=[]
    base=conds[:60]
    for i,a in enumerate(base):
        for b in base[i+1:]:
            if a[2]==b[2]:continue
            fn=lambda r,fa=a[5],fb=b[5]:fa(r) and fb(r)
            mt=eval_rule(tr,fn)
            if mt["n"]<15:continue
            mv=eval_rule(va,fn); mr=eval_rule(rs,fn)
            pairs.append({
                "features":[{"key":a[2],"op":a[3],"threshold":a[4]},{"key":b[2],"op":b[3],"threshold":b[4]}],
                "TRAIN":mt,"VALIDATION":mv,"RESERVE":mr,
                "min_oos_n":min(mv["n"],mr["n"]),
                "min_wr":min(mt.get("wr_pct",0),mv.get("wr_pct",0),mr.get("wr_pct",0)) if mv["n"] and mr["n"] else 0,
            })
    pairs.sort(key=lambda z:(z["min_wr"],z["TRAIN"]["wr_pct"],z["TRAIN"]["n"]),reverse=True)
    stable60=[p for p in pairs if p["VALIDATION"]["n"]>=5 and p["RESERVE"]["n"]>=5 and p["TRAIN"]["wr_pct"]>=60 and p["VALIDATION"]["wr_pct"]>=60 and p["RESERVE"]["wr_pct"]>=60]

    old_rule=lambda r:(r["f_micro_consecutive_selected_bars"] is not None and r["f_micro_consecutive_selected_bars"]<=2 and r["f_gate_side_adjusted_drift_pct"] is not None and r["f_gate_side_adjusted_drift_pct"]<=0.06782)
    old_rule_metrics={sp:eval_rule([r for r in rows if r["chrono_split"]==sp],old_rule) for sp in splits}
    old_rule_metrics["ALL"]=eval_rule(rows,old_rule)

    summary={
        "version":VERSION,
        "contract":{
            "rows":len(rows),"source":"Binance Vision USD-M aggTrades strictly inside position lifetime",
            "archive_errors":errors,"path_coverage":sum(r["path_points"]>0 for r in rows),
            "thresholds":{"early_adverse":EARLY_ADVERSE,"wrong_ceiling":WRONG_CEILING,"directional":DIRECTIONAL,"runner":RUNNER},
            "production_authority":"NONE",
        },
        "legacy_class_mix":dict(legacy),"clean_class_mix":dict(clean),
        "changed_labels":sum(r["legacy_label"]!=r["clean_label"] for r in rows),
        "transition_matrix":{f"{a}->{b}":n for (a,b),n in matrix.items()},
        "baseline":baseline,
        "entry_feature_auc_top":[{"feature":k,"auc_oriented":round(a,4),"auc_raw":round(raw,4)} for a,raw,k in ranking[:20]],
        "old_lq3d_rule_clean_metrics":old_rule_metrics,
        "stable60_pair_count":len(stable60),
        "stable60_top":stable60[:20],
        "top_pairs":pairs[:30],
    }

    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/"lq3f_clean_rebuild_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    keys=list(rows[0].keys())
    with (out/"lq3f_clean_open_lane_trade_level.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=keys);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()