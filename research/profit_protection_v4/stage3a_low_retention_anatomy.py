from __future__ import annotations
import argparse,csv,json,statistics
from collections import Counter,defaultdict
from pathlib import Path
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data
from research.profit_protection_v4.stage2c_runner_preservation import simulate_hybrid

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"research/profit_protection_v4/results/all_positive_mfe_v42c_replay.csv"
S1J=ROOT/"research/profit_protection_v4/results/stage1j_clean_post_entry_mfe_evidence.json"

def classify_failure(obs_ratio,runner_closed,runner_ratio,small_fired,retention):
    if obs_ratio<.80:return "OBSERVATION_MISS"
    if runner_closed and runner_ratio is not None and runner_ratio<.80:return "RUNNER_TRIGGER_DELAY"
    if runner_closed and runner_ratio is not None and runner_ratio>=.80 and retention<.75:return "EXECUTION_ACCOUNTING_DRAG"
    if small_fired and not runner_closed:return "PARTIAL_REDUCE_DRAG"
    return "MIXED_OTHER"

def band(mfe):
    if mfe<1:return "0.5-1"
    if mfe<1.5:return "1-1.5"
    if mfe<2:return "1.5-2"
    if mfe<3:return "2-3"
    return "3+"

def build():
    rows=list(csv.DictReader(SRC.open()))
    for r in rows:
        for k in ["clean_mfe_pct","observed_gross_peak_pct","observable_net_peak_pct","protected_pct","protected_usdt","actual_realized_pct","actual_realized_usdt"]:
            r[k]=None if r[k]=="" else float(r[k])
        r["ret_true"]=r["protected_pct"]/r["clean_mfe_pct"] if r["clean_mfe_pct"]>0 else None
    all_low=[r for r in rows if r["ret_true"]<.75]
    primary=[r for r in all_low if r["protection_actions"]!="NO_ACTION"]
    no_action=[r for r in all_low if r["protection_actions"]=="NO_ACTION"]
    s1={r["position_id"]:r for r in json.loads(S1J.read_text())}
    ids=[r["position_id"] for r in primary]
    positions,observations,orders=load_market_data(ids)

    def obs_at(pid,ts):
        if ts is None:return None
        for o in observations[pid]:
            if int(o["observed_at_ms"])==int(ts):return o
        return None

    def qualify(pid):
        p=positions[pid];peak=-1e99
        for o in observations[pid]:
            t=int(o["observed_at_ms"])
            if t<int(p["opened_at_ms"]) or t>int(p["closed_at_ms"]):continue
            peak=max(peak,float(o["current_pnl_pct"]))
            if peak>=1.5:return t,peak
        return None,None

    out=[]
    for r in primary:
        pid=r["position_id"];sim=simulate_hybrid(s1[pid],small_template=(.5,.6,3),reduce_fraction=.25,runner_qualify_pct=1.5,positions=positions,observations=observations,orders=orders)
        true=r["clean_mfe_pct"];obs=r["observed_gross_peak_pct"];final=r["protected_pct"];ret=final/true
        so=obs_at(pid,sim.get("small_at_ms"));ro=obs_at(pid,sim.get("runner_at_ms"));qts,qpeak=qualify(pid)
        sp=float(so["current_pnl_pct"]) if so else None;rp=float(ro["current_pnl_pct"]) if ro else None
        oratio=obs/true;rratio=rp/true if rp is not None else None
        cls=classify_failure(oratio,bool(sim.get("runner_closed")),rratio,bool(sim.get("small_fired")),ret)
        tags=[]
        if true>=1.5 and not sim.get("runner_closed") and obs<1.5:tags.append("RUNNER_TRANSITION_MISS")
        tags.append("TARGET_80_OBSERVABLE_5S" if oratio>=.8 else "TARGET_80_NOT_OBSERVABLE_5S")
        out.append({
            "position_id":pid,"symbol":r["symbol"],"side":r["side"],"clean_mfe_pct":true,
            "observed_gross_peak_pct":obs,"observed_capture_of_true_pct":oratio*100,
            "small_trigger_at_ms":sim.get("small_at_ms"),"small_trigger_pnl_pct":sp,
            "runner_qualified_at_ms":qts,"runner_close_at_ms":sim.get("runner_at_ms"),
            "runner_close_pnl_pct":rp,"protected_pct":final,"retention_vs_true_mfe_pct":ret*100,
            "true_to_observed_gap_pp":true-obs,
            "observed_to_runner_trigger_gap_pp":obs-rp if rp is not None else None,
            "runner_trigger_to_final_gap_pp":rp-final if rp is not None else None,
            "target80_pct":.8*true,"target80_shortfall_pp":.8*true-final,
            "protection_actions":r["protection_actions"],"primary_class":cls,
            "secondary_tags":"|".join(tags),"mfe_band":band(true)
        })
    classes=Counter(x["primary_class"] for x in out)
    side={s:dict(Counter(x["primary_class"] for x in out if x["side"]==s)) for s in ["LONG","SHORT"]}
    bands={}
    for b in ["0.5-1","1-1.5","1.5-2","2-3","3+"]:
        g=[x for x in out if x["mfe_band"]==b]
        bands[b]={"n":len(g),"classes":dict(Counter(x["primary_class"] for x in g)),"median_retention_pct":statistics.median([x["retention_vs_true_mfe_pct"] for x in g]) if g else None}
    class_stats={}
    for cls in sorted(classes):
        g=[x for x in out if x["primary_class"]==cls]
        class_stats[cls]={
            "n":len(g),"share_pct":100*len(g)/len(out),
            "median_clean_mfe_pct":statistics.median(x["clean_mfe_pct"] for x in g),
            "median_observed_capture_pct":statistics.median(x["observed_capture_of_true_pct"] for x in g),
            "median_retention_vs_true_mfe_pct":statistics.median(x["retention_vs_true_mfe_pct"] for x in g),
            "median_target80_shortfall_pp":statistics.median(x["target80_shortfall_pp"] for x in g)
        }
    summary={
        "stage":"PP-V4-3A","status":"COMPLETE_RESEARCH_ONLY","positive_mfe_total_n":len(rows),
        "all_lt75_n":len(all_low),"primary_active_lt75_n":len(out),"secondary_no_action_lt75_n":len(no_action),
        "triggered_total_n":sum(r["protection_actions"]!="NO_ACTION" for r in rows),
        "triggered_ge75_n":sum(r["protection_actions"]!="NO_ACTION" and r["ret_true"]>=.75 for r in rows),
        "classes":dict(classes),"class_stats":class_stats,"side_class_counts":side,"mfe_bands":bands,
        "target80_observable_5s_n":sum(x["observed_capture_of_true_pct"]>=80 for x in out),
        "target80_observable_5s_share_pct":100*sum(x["observed_capture_of_true_pct"]>=80 for x in out)/len(out),
        "target80_not_observable_5s_n":sum(x["observed_capture_of_true_pct"]<80 for x in out),
        "runner_transition_miss_n":sum("RUNNER_TRANSITION_MISS" in x["secondary_tags"] for x in out),
        "no_action_observed_peak_lt050_n":sum((r["observed_gross_peak_pct"] or -99)<.5 for r in no_action),
        "no_action_observed_peak_ge050_n":sum((r["observed_gross_peak_pct"] or -99)>=.5 for r in no_action),
        "top_target80_shortfalls":sorted(out,key=lambda x:x["target80_shortfall_pp"],reverse=True)[:20],
        "decision":{"proceed_to_v4_3b_feasibility_ceiling":True,"runtime_change_authority":"NONE"}
    }
    return out,summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--csv-output",required=True);ap.add_argument("--json-output",required=True);a=ap.parse_args()
    rows,summary=build()
    fields=list(rows[0].keys())
    with open(a.csv_output,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\\n");w.writeheader();w.writerows(rows)
    Path(a.json_output).write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,sort_keys=True))
if __name__=="__main__":main()
