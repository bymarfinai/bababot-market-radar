from __future__ import annotations
import csv,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"
D=list(csv.DictReader(open(RES/"ct6a_trade_detail.csv")))
R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}

BUCKETS=["BAD_A_LT_0P30","BAD_B_0P30_0P50","GRAY_0P50_1P00","TARGET_GE_1P00"]

def raw(q): return R[q["position_id"]] if q["source"]=="research" else F[q["position_id"]]
def ff(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except:return None
def truth(v): return str(v).strip().lower() in {"true","1","1.0","yes"}
def vals(rows,k):
    out=[]
    for q in rows:
        x=ff(raw(q).get(k))
        if x is not None: out.append(x)
    return out
def med(rows,k):
    x=vals(rows,k); return statistics.median(x) if x else None
def pct(rows,pred):
    return sum(1 for q in rows if pred(q))/len(rows) if rows else 0.0
def qs(x):
    if not x:return {}
    s=sorted(x)
    def q(p):
        pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
        return s[lo]*(1-w)+s[hi]*w
    return {"p10":q(.1),"p25":q(.25),"p50":q(.5),"p75":q(.75),"p90":q(.9)}

def short_core(q):
    z=raw(q); n=0; parts=[]
    st=z.get("f_context_structure_status")
    if st in ("BREAKDOWN","FAILED_BREAKOUT"): n+=1;parts.append("structure")
    if z.get("f_context_taker_bias")=="SELL": n+=1;parts.append("taker")
    if z.get("f_context_oi_interpretation")=="FRESH_SHORT_PARTICIPATION": n+=1;parts.append("oi")
    return n,tuple(parts)

def short_confirm(q):
    z=raw(q); n=0;parts=[]
    st=z.get("f_context_structure_status")
    if st in ("BREAKDOWN","FAILED_BREAKOUT"):n+=1;parts.append("structure")
    if z.get("f_context_taker_bias")=="SELL":n+=1;parts.append("taker")
    if z.get("f_context_oi_interpretation")=="FRESH_SHORT_PARTICIPATION":n+=1;parts.append("oi")
    if z.get("f_context_market_regime")=="BEAR":n+=1;parts.append("regime")
    return n,tuple(parts)

def short_conflicts(q):
    z=raw(q);n=0;parts=[]
    st=z.get("f_context_structure_status")
    if st in ("BREAKOUT","FAILED_BREAKDOWN"):n+=1;parts.append("structure")
    if z.get("f_context_taker_bias")=="BUY":n+=1;parts.append("taker")
    if z.get("f_context_oi_interpretation") in ("FRESH_LONG_PARTICIPATION","SHORT_COVERING"):n+=1;parts.append("oi")
    if z.get("f_context_market_regime")=="BULL":n+=1;parts.append("regime")
    return n,tuple(parts)

summary={"stage":"SHORT-SA1","status":"ADMISSION_AUDIT_COMPLETE","population":{},"by_bucket":{}}

for b in BUCKETS:
    rows=[q for q in D if q["mfe_bucket"]==b]
    summary["population"][b]=len(rows)
    stages=Counter(raw(q).get("f_stage") for q in rows)
    structures=Counter(raw(q).get("f_context_structure_status") for q in rows)
    takers=Counter(raw(q).get("f_context_taker_bias") for q in rows)
    ois=Counter(raw(q).get("f_context_oi_interpretation") for q in rows)
    regimes=Counter(raw(q).get("f_context_market_regime") for q in rows)
    core_counts=Counter(short_core(q)[0] for q in rows)
    core_patterns=Counter("+".join(short_core(q)[1]) or "NONE" for q in rows)
    confirms=Counter(short_confirm(q)[0] for q in rows)
    conflicts=Counter(short_conflicts(q)[0] for q in rows)
    summary["by_bucket"][b]={
      "n":len(rows),
      "stage":dict(stages),
      "stage2":{
        "ret5_med":med(rows,"f_ret_5m_pct_for_selected"),
        "ret15_med":med(rows,"f_ret_15m_pct_for_selected"),
        "ret1h_med":med(rows,"f_ret_1h_pct_for_selected"),
        "median_abs_ret5_med":med(rows,"f_median_abs_ret_5m_pct"),
        "return_expansion_ratio_med":med(rows,"f_return_expansion_ratio"),
        "volume_ratio_med":med(rows,"f_volume_ratio_signal"),
        "range_ratio_med":med(rows,"f_range_ratio"),
        "trades_ratio_med":med(rows,"f_trades_ratio"),
        "evidence_count_med":med(rows,"f_evidence_count"),
        "directional_persistence_rate":pct(rows,lambda q:truth(raw(q).get("f_directional_persistence"))),
      },
      "stage4":{
        "selected_score_q":qs(vals(rows,"f_selected_score")),
        "opposite_score_q":qs(vals(rows,"f_opposite_score")),
        "edge_q":qs(vals(rows,"f_score_edge_selected_minus_opposite")),
        "momentum_med":med(rows,"f_score_component_selected_momentum"),
        "activity_med":med(rows,"f_score_component_selected_activity"),
        "persistence_med":med(rows,"f_score_component_selected_persistence"),
        "consistency_med":med(rows,"f_score_component_selected_timeframe_consistency"),
        "score_68_72_rate":pct(rows,lambda q:(ff(raw(q).get("f_selected_score")) or 0)>=68 and (ff(raw(q).get("f_selected_score")) or 0)<72),
        "score_lt75_rate":pct(rows,lambda q:(ff(raw(q).get("f_selected_score")) or 999)<75),
        "edge_10_15_rate":pct(rows,lambda q:(ff(raw(q).get("f_score_edge_selected_minus_opposite")) or 0)>=10 and (ff(raw(q).get("f_score_edge_selected_minus_opposite")) or 0)<15),
      },
      "stage5_6":{
        "structure":dict(structures),"taker":dict(takers),"oi":dict(ois),"regime":dict(regimes),
        "core_count":dict(core_counts),"core_patterns":dict(core_patterns),
        "confirm_count_reconstructed":dict(confirms),"conflict_count_reconstructed":dict(conflicts),
        "decision_confirm_med":med(rows,"f_decision_context_confirmations"),
        "decision_conflict_med":med(rows,"f_decision_context_conflicts"),
        "decision_balance_med":med(rows,"f_decision_context_balance"),
        "balance_eq1_rate":pct(rows,lambda q:(ff(raw(q).get("f_decision_context_balance")) or 0)==1),
        "core_exactly1_rate":pct(rows,lambda q:short_core(q)[0]==1),
      }
    }

# Simple fixed sensitivity probes, not optimization.
PROBES={
 "S2_abs_ret5_ge_0p30":lambda q:(ff(raw(q).get("f_ret_5m_pct_for_selected")) or 0)>=.30,
 "S2_evidence_ge_4":lambda q:(ff(raw(q).get("f_evidence_count")) or 0)>=4,
 "S2_persistence_required":lambda q:truth(raw(q).get("f_directional_persistence")),
 "S4_score_ge_75":lambda q:(ff(raw(q).get("f_selected_score")) or 0)>=75,
 "S4_edge_ge_15":lambda q:(ff(raw(q).get("f_score_edge_selected_minus_opposite")) or 0)>=15,
 "S4_momentum_ge_30":lambda q:(ff(raw(q).get("f_score_component_selected_momentum")) or 0)>=30,
 "S5_core_ge_2":lambda q:short_core(q)[0]>=2,
 "S6_balance_ge_2":lambda q:(ff(raw(q).get("f_decision_context_balance")) or 0)>=2,
}
summary["sensitivity"]={}
for name,pred in PROBES.items():
    x={}
    for b in BUCKETS:
        rows=[q for q in D if q["mfe_bucket"]==b]
        keep=sum(pred(q) for q in rows)
        x[b]={"keep":keep,"total":len(rows),"keep_rate":keep/len(rows) if rows else 0}
    summary["sensitivity"][name]=x

# Context-pattern outcome anatomy.
patterns=defaultdict(lambda:Counter())
for q in D:
    pat="+".join(short_core(q)[1]) or "NONE"
    patterns[pat][q["mfe_bucket"]]+=1
summary["core_pattern_outcomes"]={k:dict(v) for k,v in patterns.items()}

(RES/"sa1_summary.json").write_text(json.dumps(summary,indent=2))

print("POP",summary["population"])
for b in BUCKETS:
    z=summary["by_bucket"][b]
    print("\n",b,"n",z["n"],"stage",z["stage"])
    print("S2",z["stage2"])
    print("S4",z["stage4"])
    print("S56 core",z["stage5_6"]["core_count"],"patterns",z["stage5_6"]["core_patterns"],"balance1",z["stage5_6"]["balance_eq1_rate"])
print("\nSENSITIVITY")
for k,v in summary["sensitivity"].items():
    print(k,{b:round(v[b]["keep_rate"],3) for b in BUCKETS})
print("\nCORE PATTERNS")
for k,v in sorted(summary["core_pattern_outcomes"].items(),key=lambda kv:sum(kv[1].values()),reverse=True):
    print(k,v)