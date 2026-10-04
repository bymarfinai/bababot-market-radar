from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from typing import Any
from research.profit_protection_v4.stage2b_optimal_protection_frontier import exit_fill_price,gross_pnl,load_market_data
from research.profit_protection_v4.stage2c_runner_preservation import fallback_close_fill,RUNNER_RETAIN,RUNNER_CONFIRM

ROOT=Path(__file__).resolve().parents[2]
S2A=ROOT/"research/profit_protection_v4/results/stage2a_observable_realized_leakage_evidence.json"
S2C=ROOT/"research/profit_protection_v4/results/stage2c_runner_preservation.json"
SMALL=(.50,.60,3); FRAC=.25; RUNNER_Q=1.50; TOL=1e-8

def med(v): return statistics.median(v) if v else None

def replay(row:dict[str,Any],positions,obs,orders)->dict[str,Any]:
    pid=str(row["position_id"]); p=positions[pid]; side=str(p["side"]).upper()
    op=int(p["opened_at_ms"]); cl=int(p["closed_at_ms"]); entry=float(p["entry_price"]); meta=json.loads(p.get("raw_json") or "{}")
    iq=float(meta.get("initial_quantity") or 0); ino=float(meta.get("initial_notional_usdt") or 500); ef=float(meta.get("entry_fee_total") or 0); fr=float(meta.get("fee_rate") or .00075); slip=float(meta.get("slippage_bps") or 2)
    path=[x for x in obs[pid] if op<=int(x["observed_at_ms"])<=cl]
    peak=-1e99; sc=rc=0; runner=small=False; qualified=None; diverged=False; closed=False
    realized=qclosed=alloc=0.0; log=[]; errors=[]; prev=None
    def preserve(ts):
        nonlocal realized,qclosed,alloc
        for od in orders[pid]:
            if str(od["action"]).upper()=="OPEN" or od["executed_at_ms"] is None or int(od["executed_at_ms"])>ts: continue
            q=float(od["executed_quantity"] or 0)
            if q<=0: continue
            a=ef*q/iq if iq else 0.0; fee=float(od["fee"] or 0); pnl=gross_pnl(side,entry,float(od["fill_price"]),q)-a-fee
            realized+=pnl;qclosed+=q;alloc+=a
            log.append({"type":"PRESERVE","action":str(od["action"]).upper(),"at_ms":int(od["executed_at_ms"]),"qty":q,"entry_fee":a,"exit_fee":fee,"net_usdt":pnl})
    for x in path:
        ts=int(x["observed_at_ms"]); pnl=float(x["current_pnl_pct"])
        if prev is not None and ts<prev: errors.append("time_order")
        prev=ts; peak=max(peak,pnl)
        if not runner and peak>=RUNNER_Q:
            runner=True;qualified=ts;sc=0;log.append({"type":"RUNNER_QUALIFY","at_ms":ts,"peak_pct":peak})
        if runner:
            rc=rc+1 if pnl<=peak*RUNNER_RETAIN else 0
            if rc<RUNNER_CONFIRM: continue
            if not diverged: preserve(ts);diverged=True
            rem=max(0.0,iq-qclosed);fill=exit_fill_price(side,float(x["current_price"]),slip);fee=rem*fill*fr;a=max(0.0,ef-alloc);net=gross_pnl(side,entry,fill,rem)-a-fee
            realized+=net;qclosed+=rem;alloc+=a;closed=True
            log.append({"type":"SHADOW_CLOSE_REMAINDER","at_ms":ts,"qty":rem,"fill":fill,"entry_fee":a,"exit_fee":fee,"net_usdt":net,"peak_pct":peak,"pnl_pct":pnl});break
        if small: continue
        sc=sc+1 if peak>=SMALL[0] and pnl<=peak*SMALL[1] else 0
        if sc<SMALL[2]: continue
        if not diverged: preserve(ts);diverged=True
        rem=max(0.0,iq-qclosed);q=rem*FRAC;fill=exit_fill_price(side,float(x["current_price"]),slip);fee=q*fill*fr;a=ef*q/iq if iq else 0.0;net=gross_pnl(side,entry,fill,q)-a-fee
        realized+=net;qclosed+=q;alloc+=a;small=True;sc=0
        log.append({"type":"SHADOW_REDUCE_25","at_ms":ts,"qty":q,"fill":fill,"entry_fee":a,"exit_fee":fee,"net_usdt":net,"peak_pct":peak,"pnl_pct":pnl})
    if diverged and not closed:
        rem=max(0.0,iq-qclosed);fill,ts=fallback_close_fill(pid,positions,orders);fee=rem*fill*fr;a=max(0.0,ef-alloc);net=gross_pnl(side,entry,fill,rem)-a-fee
        realized+=net;qclosed+=rem;alloc+=a;closed=True
        log.append({"type":"FALLBACK_CLOSE","at_ms":ts,"qty":rem,"fill":fill,"entry_fee":a,"exit_fee":fee,"net_usdt":net})
    if not diverged:
        realized=float(p["realized_pnl"]);qclosed=iq;alloc=ef
        log.append({"type":"KEEP_ACTUAL","at_ms":cl,"net_usdt":realized})
    sr=sum(a["type"]=="SHADOW_REDUCE_25" for a in log);rcount=sum(a["type"]=="SHADOW_CLOSE_REMAINDER" for a in log)
    if sr>1: errors.append("small_gt1")
    if rcount>1: errors.append("close_gt1")
    if rcount and qualified is None: errors.append("close_without_runner")
    if abs(qclosed-iq)>TOL: errors.append("quantity_mismatch")
    if abs(alloc-ef)>max(TOL,abs(ef)*1e-8): errors.append("entry_fee_mismatch")
    sim_pct=100*realized/ino if ino else 0.0
    return {"position_id":pid,"symbol":row["symbol"],"side":side,"opened_at_ms":op,"sim_usdt":realized,"sim_pct":sim_pct,"actual_usdt":float(row["realized_pnl_usdt"]),"observable_net_peak_pct":float(row["observable_net_peak_pct"]),"small_fired":small,"runner_closed":bool(rcount),"actions":log,"invariant_errors":errors}

def metrics(trades):
    pos=[t for t in trades if t["observable_net_peak_pct"]>0];ret=[t["sim_pct"]/t["observable_net_peak_pct"] for t in pos]
    def sub(cut):
        g=[t for t in trades if t["observable_net_peak_pct"]>=cut];r=[t["sim_pct"]/t["observable_net_peak_pct"] for t in g]
        return {"n":len(g),"total_usdt":sum(t["sim_usdt"] for t in g),"median_retention":med(r)}
    return {"n":len(trades),"total_usdt":sum(t["sim_usdt"] for t in trades),"win_rate":sum(t["sim_pct"]>0 for t in trades)/len(trades),"small_reduce_n":sum(t["small_fired"] for t in trades),"runner_close_n":sum(t["runner_closed"] for t in trades),"median_retention":med(ret),"runner_ge1":sub(1.0),"runner_ge2":sub(2.0)}

def build():
    rows=sorted(json.loads(S2A.read_text()),key=lambda r:(int(r["opened_at_ms"]),str(r["position_id"])))
    frozen=json.loads(S2C.read_text());ids=[r["position_id"] for r in rows];p,o,q=load_market_data(ids)
    trades=[replay(r,p,o,q) for r in rows];m=metrics(trades);exp=frozen["selected_research_reference"]["metrics"]
    checks={
      "total_usdt":abs(m["total_usdt"]-float(exp["all"]["total_usdt"]))<=TOL,
      "win_rate":abs(m["win_rate"]-float(exp["all"]["win_rate"]))<=TOL,
      "small_reduce_n":m["small_reduce_n"]==int(exp["all"]["small_reduce_n"]),
      "runner_close_n":m["runner_close_n"]==int(exp["all"]["runner_close_n"]),
      "runner1_ret":abs(m["runner_ge1"]["median_retention"]-float(exp["runner_ge1"]["median_retention"]))<=TOL,
      "runner2_ret":abs(m["runner_ge2"]["median_retention"]-float(exp["runner_ge2"]["median_retention"]))<=TOL,
    }
    failures=[{"position_id":t["position_id"],"errors":t["invariant_errors"]} for t in trades if t["invariant_errors"]]
    audit={"stage":"PP-V4-2D","status":"PASS" if all(checks.values()) and not failures else "FAIL","trade_count":len(trades),"metrics":m,"stage2c_exact_checks":checks,"invariant_failure_count":len(failures),"invariant_failures":failures,"action_counts":{k:sum(a["type"]==k for t in trades for a in t["actions"]) for k in ["PRESERVE","SHADOW_REDUCE_25","RUNNER_QUALIFY","SHADOW_CLOSE_REMAINDER","FALLBACK_CLOSE","KEEP_ACTUAL"]},"prospective_shadow_activation_allowed":all(checks.values()) and not failures,"runtime_authority":"NONE"}
    return trades,audit

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--trades-output",required=True);ap.add_argument("--audit-output",required=True);a=ap.parse_args()
    trades,audit=build();Path(a.trades_output).write_text(json.dumps(trades,indent=2,sort_keys=True,allow_nan=False)+"\n");Path(a.audit_output).write_text(json.dumps(audit,indent=2,sort_keys=True,allow_nan=False)+"\n");print(json.dumps(audit,sort_keys=True))

if __name__=="__main__": main()
