from __future__ import annotations
import csv,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"
D=list(csv.DictReader(open(RES/"ct6a_trade_detail.csv")))
BASE={r["position_id"]:r for r in csv.DictReader(open(RES/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
R={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
F={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}

def raw(q):return R[q["position_id"]] if q["source"]=="research" else F[q["position_id"]]
def ff(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def truth(v):return str(v).strip().lower() in {"true","1","1.0","yes"}

RULES={
 "Q97_CONSERVATIVE":{
   "logic":"ALL_LOW",
   "conditions":[
     ("f_median_abs_ret_5m_pct",0.1431742,"Research Discovery TARGET Q20"),
     ("f_context_quote_volume_5m",20292.694019,"Research Discovery TARGET Q10"),
     ("f_f_coin_minus_market_30m",0.9372983228207556,"Research Discovery TARGET Q40"),
   ],
 },
 "Q97_MAX":{
   "logic":"ALL_LOW",
   "conditions":[
     ("f_median_abs_ret_5m_pct",0.1298166,"Research Discovery TARGET Q15"),
     ("f_context_quote_volume_5m",28174.7840488,"Research Discovery TARGET Q20"),
     ("f_f_coin_minus_market_30m",0.9372983228207556,"Research Discovery TARGET Q40"),
   ],
 },
 "Q95_AGGRESSIVE":{
   "logic":"ALL_LOW",
   "conditions":[
     ("f_ret_1h_pct_for_selected",1.2273333,"Research Discovery TARGET Q30"),
     ("f_context_quote_volume_5m",28174.7840488,"Research Discovery TARGET Q20"),
     ("f_f_coin_minus_market_30m",0.8913809141829247,"Research Discovery TARGET Q35"),
   ],
 },
}

BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]

def ids_for(spec):
    out=set()
    for q in D:
        ok=True
        for k,th,_ in spec["conditions"]:
            x=ff(raw(q).get(k))
            ok=ok and x is not None and x<=th
        if ok:out.add(q["position_id"])
    return out

def base_metrics(ids):
    bad=[q for q in D if q["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
    target=[q for q in D if q["mfe_bucket"]=="TARGET_GE_1P00"]
    strong=[q for q in D if truth(q["strong"])]
    def rej(rows):return sum(q["position_id"] in ids for q in rows)
    ex=[BASE[i] for i in ids if i in BASE and truth(BASE[i]["executable"])]
    return {
      "selected_reject":len(ids),
      "bad_reject":rej(bad),"bad_total":len(bad),"bad_reject_rate":rej(bad)/len(bad),
      "target_reject":rej(target),"target_total":len(target),"target_retention":1-rej(target)/len(target),
      "strong_reject":rej(strong),"strong_total":len(strong),"strong_retention":1-rej(strong)/len(strong),
      "ct4_reject_executable":len(ex),"ct4_reject_wins":sum(float(x["pnl"])>0 for x in ex),
      "ct4_reject_pnl":sum(float(x["pnl"]) for x in ex),
      "ct4_keep_pnl":sum(float(x["pnl"]) for x in BASE.values() if truth(x["executable"]))-sum(float(x["pnl"]) for x in ex),
    }

# frozen current stack CT5B+CT6C+CT7C+CT7D
ct5=set(json.load(open(RES/"ct5b_summary.json"))["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(RES/"ct6c_veto_trade_detail.csv"))}
ct7={r["position_id"] for r in csv.DictReader(open(RES/"ct7c_trade_detail.csv"))}
resc={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7d_rescue_detail.csv")) if truth(r["executable"])}
drop=(ct5|ct6|ct7)-set(resc)
current={}
for pid,b in BASE.items():
    if pid in drop:continue
    if pid in resc:
        p=float(resc[pid]["pnl"])
        current[pid]={"pnl":p,"win":p>0,"strong":truth(b["strong"]),"source":b["source"],"block":b["block"]}
    elif truth(b["executable"]):
        p=float(b["pnl"])
        current[pid]={"pnl":p,"win":p>0,"strong":truth(b["strong"]),"source":b["source"],"block":b["block"]}

assert len(current)==794
assert abs(sum(x["pnl"] for x in current.values())+136.316975469426)<1e-9

summary={"stage":"SHORT-SA2","status":"OPPORTUNITY_QUALITY_GATE_RESEARCH_PASS_NOT_RUNTIME_READY","runtime_change":False,"rules":{}}

for name,spec in RULES.items():
    ids=ids_for(spec)
    z=base_metrics(ids)
    z["conditions"]=spec["conditions"]
    z["by_source"]={}
    for src in ("research","fresh"):
        q=[x for x in D if x["source"]==src]
        bad=[x for x in q if x["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
        target=[x for x in q if x["mfe_bucket"]=="TARGET_GE_1P00"]
        strong=[x for x in q if truth(x["strong"])]
        z["by_source"][src]={
          "bad_reject_rate":sum(x["position_id"] in ids for x in bad)/len(bad),
          "target_retention":1-sum(x["position_id"] in ids for x in target)/len(target),
          "strong_retention":1-sum(x["position_id"] in ids for x in strong)/len(strong),
        }
    z["by_block"]={}
    for b in BLOCKS:
        q=[x for x in D if x["block"]==b]
        bad=[x for x in q if x["mfe_bucket"] in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")]
        target=[x for x in q if x["mfe_bucket"]=="TARGET_GE_1P00"]
        strong=[x for x in q if truth(x["strong"])]
        rem=[current[x["position_id"]] for x in q if x["position_id"] in ids and x["position_id"] in current]
        z["by_block"][b]={
          "bad_reject":sum(x["position_id"] in ids for x in bad),
          "bad_total":len(bad),
          "target_reject":sum(x["position_id"] in ids for x in target),
          "target_total":len(target),
          "strong_reject":sum(x["position_id"] in ids for x in strong),
          "strong_total":len(strong),
          "current_stack_removed_exec":len(rem),
          "current_stack_removed_pnl":sum(x["pnl"] for x in rem),
        }
    removed={pid:x for pid,x in current.items() if pid in ids}
    keep={pid:x for pid,x in current.items() if pid not in ids}
    z["current_stack_diagnostic"]={
      "removed_exec":len(removed),
      "removed_wins":sum(x["win"] for x in removed.values()),
      "removed_strong":sum(x["strong"] for x in removed.values()),
      "removed_pnl":sum(x["pnl"] for x in removed.values()),
      "post_exec":len(keep),
      "post_wins":sum(x["win"] for x in keep.values()),
      "post_wr":sum(x["win"] for x in keep.values())/len(keep),
      "post_strong_exec":sum(x["strong"] for x in keep.values()),
      "post_pnl":sum(x["pnl"] for x in keep.values()),
    }
    summary["rules"][name]=z

# Stress frontier from SA2 asymmetric scan. These are diagnostic, not frozen runtime gates.
summary["stress_frontier"]=[
 {"label":"~20%","bad_reject_rate":0.166,"target_retention":0.966,"strong_retention":0.962},
 {"label":"~30%","bad_reject_rate":0.256,"target_retention":0.929,"strong_retention":0.925},
 {"label":"~40%","bad_reject_rate":0.362,"target_retention":0.871,"strong_retention":0.861},
 {"label":"~50%","bad_reject_rate":0.455,"target_retention":0.801,"strong_retention":0.782},
 {"label":"~60%","bad_reject_rate":0.555,"target_retention":0.712,"strong_retention":0.684},
]
summary["verdict"]={
 "safe_97_ceiling_bad_reject_rate":0.131,
 "safe_95_ceiling_bad_reject_rate":0.183,
 "primary_research_candidate":"Q95_AGGRESSIVE",
 "safety_comparator":"Q97_MAX",
 "reason":"Q95 is the highest tested global gate near the requested 20% BAD rejection while retaining about 95% TARGET/strong; >=30% BAD rejection causes unacceptable collateral. Q97 provides a higher-retention comparator.",
 "runtime_authority":"NONE",
}

(RES/"sa2_summary.json").write_text(json.dumps(summary,indent=2))

with open(RES/"sa2_candidate_trade_detail.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","mfe_bucket","strong","Q97_CONSERVATIVE","Q97_MAX","Q95_AGGRESSIVE"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    idmaps={name:ids_for(spec) for name,spec in RULES.items()}
    for q in D:
        if not any(q["position_id"] in x for x in idmaps.values()):continue
        w.writerow({
          "position_id":q["position_id"],"symbol":q["symbol"],"source":q["source"],"block":q["block"],
          "mfe_bucket":q["mfe_bucket"],"strong":q["strong"],
          **{name:q["position_id"] in ids for name,ids in idmaps.items()}
        })

print(json.dumps(summary["verdict"],indent=2))
for name,z in summary["rules"].items():
 print(name,"BAD",z["bad_reject"],"/",z["bad_total"],round(z["bad_reject_rate"],3),
       "Tret",round(z["target_retention"],3),"Sret",round(z["strong_retention"],3),
       "CT4 removed pnl",round(z["ct4_reject_pnl"],3),
       "current post",round(z["current_stack_diagnostic"]["post_pnl"],3))