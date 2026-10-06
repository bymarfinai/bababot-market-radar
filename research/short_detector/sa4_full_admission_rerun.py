from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/"research"/"short_detector"/"results"

def truth(v): return str(v).strip().lower() in {"true","1","1.0","yes"}

labels={r["position_id"]:r for r in csv.DictReader(open(RES/"ct6a_trade_detail.csv"))}
base={r["position_id"]:r for r in csv.DictReader(open(RES/"ct4_trade_detail.csv")) if r["candidate"]=="T0075"}
ct5_summary=json.load(open(RES/"ct5b_summary.json"))
ct5=set(ct5_summary["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"])
ct6={r["position_id"] for r in csv.DictReader(open(RES/"ct6c_veto_trade_detail.csv"))}
ct7rows={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7c_trade_detail.csv"))}
ct7=set(ct7rows)
q95rows={r["position_id"]:r for r in csv.DictReader(open(RES/"sa2_candidate_trade_detail.csv"))}
q95={pid for pid,r in q95rows.items() if truth(r["Q95_AGGRESSIVE"])}
arch={r["position_id"]:r for r in csv.DictReader(open(RES/"ct7b_trade_membership.csv"))}
rescue={r["position_id"]:r for r in csv.DictReader(open(RES/"sa3_rescue_trade_detail.csv"))}

hard=ct5|ct6
negative=ct7|q95
flagged=(hard|negative)
rescuable=negative-hard
rescued=set(rescue)

# Final SA3 exact executable state.
final={}
for pid,b in base.items():
    if pid in hard:
        continue
    if pid in negative:
        if pid not in rescue:
            continue
        rr=rescue[pid]
        final[pid]={
            "pnl":float(rr["pnl"]),"reason":rr["reason"],"strong":truth(b["strong"]),
            "source":b["source"],"block":b["block"],"rescued":True,
        }
    elif truth(b["executable"]):
        final[pid]={
            "pnl":float(b["pnl"]),"reason":b["reason"],"strong":truth(b["strong"]),
            "source":b["source"],"block":b["block"],"rescued":False,
        }

assert len(base)==1087
assert sum(truth(r["executable"]) for r in base.values())==931
assert len(final)==744
assert abs(sum(x["pnl"] for x in final.values()) - (-67.09448891657092))<1e-9

BUCKETS=["BAD_A_LT_0P30","BAD_B_0P30_0P50","GRAY_0P50_1P00","TARGET_GE_1P00"]
BLOCKS=["Research_Discovery","Research_Validation","Research_Reserve","Fresh_2026-10-01","Fresh_2026-10-02","Fresh_2026-10-03"]

def bucket(pid):return labels[pid]["mfe_bucket"]
def isbad(pid):return bucket(pid) in ("BAD_A_LT_0P30","BAD_B_0P30_0P50")
def selected_metrics(ids):
    ids=set(ids)
    return {
      "selected":len(ids),
      "bad_a":sum(bucket(i)=="BAD_A_LT_0P30" for i in ids),
      "bad_b":sum(bucket(i)=="BAD_B_0P30_0P50" for i in ids),
      "bad_lt_0p5":sum(isbad(i) for i in ids),
      "gray":sum(bucket(i)=="GRAY_0P50_1P00" for i in ids),
      "target":sum(bucket(i)=="TARGET_GE_1P00" for i in ids),
      "strong":sum(truth(base[i]["strong"]) for i in ids),
      "ct4_executable":sum(truth(base[i]["executable"]) for i in ids),
      "ct4_pnl":sum(float(base[i]["pnl"]) for i in ids if truth(base[i]["executable"])),
    }
def final_metrics(ids):
    ids=set(ids)&set(final)
    vals=[final[i] for i in ids]
    return {
      "exec":len(ids),"wins":sum(x["pnl"]>0 for x in vals),
      "wr":sum(x["pnl"]>0 for x in vals)/len(vals) if vals else 0,
      "strong":sum(x["strong"] for x in vals),"pnl":sum(x["pnl"] for x in vals),
      "fallback":sum(x["reason"]=="HIST_TIME_FALLBACK" for x in vals),
      "fallback_pnl":sum(x["pnl"] for x in vals if x["reason"]=="HIST_TIME_FALLBACK"),
    }

# Mutually exclusive funnel attribution.
stage={}
remaining=set(base)
stage["CT5B_HARD"]=remaining&ct5; remaining-=stage["CT5B_HARD"]
stage["CT6C_HARD"]=remaining&ct6; remaining-=stage["CT6C_HARD"]
stage["CT7C_NEGATIVE"]=remaining&ct7; remaining-=stage["CT7C_NEGATIVE"]
stage["Q95_INCREMENTAL"]=remaining&q95; remaining-=stage["Q95_INCREMENTAL"]
# Negative flags that are rescued are pulled back in final; attribute separately.
stage["SA3_RESCUED"]=rescued
stage["FINAL_UNFLAGGED_SELECTED"]=remaining

# Selection-level kill effectiveness by bucket.
initial={b:{i for i in base if bucket(i)==b} for b in BUCKETS}
final_selected=(set(base)-hard-negative)|rescued
# Note: some final-selected have no executable CT4 / delayed rescue and will not appear in final exact state.

# Residual final exact anatomy.
final_ids=set(final)
resid_bad={i for i in final_ids if isbad(i)}
resid_gray={i for i in final_ids if bucket(i)=="GRAY_0P50_1P00"}
resid_target={i for i in final_ids if bucket(i)=="TARGET_GE_1P00"}

def broad_membership(pid):
    r=arch[pid]
    names=[]
    for k in ("A1_LOW_DISPLACEMENT","A2_WEAK_RELATIVE_EXPANSION","A3_LOW_ENERGY_RESIDUAL"):
        if truth(r[k]):names.append(k.split("_")[0])
    return names
def kill_membership(pid):
    r=ct7rows.get(pid)
    if not r:return []
    names=[]
    for k in ("K1_A1_TURBULENT_UNSUPPORTED","K2_A2_ILLIQUID_DISPERSION","K3_A3_SHORT_BURST_NO_EXTENSION"):
        if truth(r[k]):names.append(k.split("_")[0])
    return names

# Residual BAD segmentation by known broad archetype, Q95 morphology, and reason.
segments=defaultdict(lambda:{"exec":0,"pnl":0.0,"fallback":0,"fallback_pnl":0.0,"bad_a":0,"bad_b":0})
for pid in resid_bad:
    broad=broad_membership(pid)
    q="Q95" if pid in q95 else "NO_Q95"
    territory="OUTSIDE_ALL" if not broad else ("MULTI" if len(broad)>1 else broad[0])
    key=f"{territory}|{q}"
    z=segments[key];x=final[pid]
    z["exec"]+=1;z["pnl"]+=x["pnl"];z["bad_a"]+=bucket(pid)=="BAD_A_LT_0P30";z["bad_b"]+=bucket(pid)=="BAD_B_0P30_0P50"
    if x["reason"]=="HIST_TIME_FALLBACK":z["fallback"]+=1;z["fallback_pnl"]+=x["pnl"]

# Reason anatomy.
reasons=defaultdict(lambda:{"exec":0,"wins":0,"strong":0,"pnl":0.0,"bad":0,"gray":0,"target":0})
for pid,x in final.items():
    z=reasons[x["reason"]];z["exec"]+=1;z["wins"]+=x["pnl"]>0;z["strong"]+=x["strong"];z["pnl"]+=x["pnl"]
    z["bad"]+=isbad(pid);z["gray"]+=bucket(pid)=="GRAY_0P50_1P00";z["target"]+=bucket(pid)=="TARGET_GE_1P00"

# Residual BAD feature-territory / lanes / blocks.
bad_lane=defaultdict(lambda:{"exec":0,"pnl":0.0,"fallback":0,"fallback_pnl":0.0})
bad_block=defaultdict(lambda:{"exec":0,"pnl":0.0,"fallback":0,"fallback_pnl":0.0})
for pid in resid_bad:
    x=final[pid];lane=labels[pid]["lane"];blk=labels[pid]["block"]
    for table,key in ((bad_lane,lane),(bad_block,blk)):
        z=table[key];z["exec"]+=1;z["pnl"]+=x["pnl"]
        if x["reason"]=="HIST_TIME_FALLBACK":z["fallback"]+=1;z["fallback_pnl"]+=x["pnl"]

# Incremental effect of each gate on executable economics using CT4 old entry.
gate_diag={}
for name,ids in stage.items():
    if name in ("SA3_RESCUED","FINAL_UNFLAGGED_SELECTED"):continue
    ex=[base[i] for i in ids if truth(base[i]["executable"])]
    gate_diag[name]={
      **selected_metrics(ids),
      "exec_wins":sum(float(r["pnl"])>0 for r in ex),
      "exec_strong":sum(truth(r["strong"]) for r in ex),
    }

# BAD funnel.
bad0={i for i in base if isbad(i)}
bad_final_sel=bad0 & final_selected
bad_final_exec=resid_bad
bad_funnel={
 "initial_selected":len(bad0),
 "initial_executable":sum(truth(base[i]["executable"]) for i in bad0),
 "initial_ct4_pnl":sum(float(base[i]["pnl"]) for i in bad0 if truth(base[i]["executable"])),
 "ct5b_removed_selected":len(stage["CT5B_HARD"]&bad0),
 "ct6c_removed_selected":len(stage["CT6C_HARD"]&bad0),
 "ct7c_removed_selected":len(stage["CT7C_NEGATIVE"]&bad0),
 "q95_incremental_removed_selected":len(stage["Q95_INCREMENTAL"]&bad0),
 "rescued_selected_bad":len(rescued&bad0),
 "final_selected_bad":len(bad_final_sel),
 "final_executable_bad":len(bad_final_exec),
 "final_bad_pnl":sum(final[i]["pnl"] for i in bad_final_exec),
}

# Archetype coverage of residual vs removed BAD.
removed_bad=bad0-bad_final_sel
def territory_metrics(ids):
    ids=set(ids)
    inside={i for i in ids if broad_membership(i)}
    outside=ids-inside
    return {
      "total":len(ids),"inside_broad":len(inside),"outside_all":len(outside),
      "inside_share":len(inside)/len(ids) if ids else 0,
    }

summary={
 "stage":"SHORT-SA4",
 "status":"FULL_ADMISSION_RERUN_COMPLETE",
 "runtime_change":False,
 "universe":{"selected":len(base),"ct4_executable":sum(truth(r["executable"]) for r in base.values()),"ct4_pnl":sum(float(r["pnl"]) for r in base.values() if truth(r["executable"]))},
 "funnel":{name:selected_metrics(ids) for name,ids in stage.items()},
 "gate_diagnostics":gate_diag,
 "bad_funnel":bad_funnel,
 "final":{
   **final_metrics(final_ids),
   "selected_after_negative_and_rescue":len(final_selected),
   "bad":final_metrics(resid_bad),
   "gray":final_metrics(resid_gray),
   "target":final_metrics(resid_target),
 },
 "reason":dict(reasons),
 "residual_bad_segments":dict(sorted(segments.items(),key=lambda kv:kv[1]["pnl"])),
 "residual_bad_lane":dict(bad_lane),
 "residual_bad_block":dict(bad_block),
 "bad_territory":{
   "removed":territory_metrics(removed_bad),
   "residual_selected":territory_metrics(bad_final_sel),
   "residual_executable":territory_metrics(resid_bad),
 },
 "block_final":{b:final_metrics({i for i in final_ids if labels[i]["block"]==b}) for b in BLOCKS},
}

# counterfactual ceilings from residual exact final only
summary["oracle"]={
 "drop_residual_bad_pnl":summary["final"]["pnl"]-summary["final"]["bad"]["pnl"],
 "drop_residual_bad_fallback_pnl":summary["final"]["pnl"]-sum(final[i]["pnl"] for i in resid_bad if final[i]["reason"]=="HIST_TIME_FALLBACK"),
 "drop_residual_gray_fallback_pnl":summary["final"]["pnl"]-sum(final[i]["pnl"] for i in resid_gray if final[i]["reason"]=="HIST_TIME_FALLBACK"),
}

# Residual BAD: distinguish negative-filter miss from rescue collateral,
# then measure how close missed BAD is to frozen CT7C conditions.
RESEARCH={r["meta_position_id"]:r for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))}
FRESH={r["meta_position_id"]:r for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))}
def raw_feature(pid):
    return RESEARCH[pid] if labels[pid]["source"]=="research" else FRESH[pid]
def fnum(v):
    try:return float(v)
    except:return None

KTH={
 "disp70":0.0670849,"acc70":0.7309212,"pos30":0.3000000,
 "disp65":0.0568162,"liq35":4324939.01,
 "prev60":0.382971,"ret60":0.934752,"ext40":0.581813,
}
def k_scores(pid):
    a=arch[pid];z=raw_feature(pid);out=[]
    if truth(a["A1_LOW_DISPLACEMENT"]):
        s=sum([
          fnum(z.get("f_f_market_dispersion_5m")) is not None and fnum(z.get("f_f_market_dispersion_5m"))>=KTH["disp70"],
          fnum(z.get("f_new_accel_5_vs_15")) is not None and fnum(z.get("f_new_accel_5_vs_15"))>=KTH["acc70"],
          fnum(z.get("f_new_positioning_support")) is not None and fnum(z.get("f_new_positioning_support"))<=KTH["pos30"],
        ])
        out.append(("A1",s,2))
    if truth(a["A2_WEAK_RELATIVE_EXPANSION"]):
        s=sum([
          fnum(z.get("f_f_market_dispersion_5m")) is not None and fnum(z.get("f_f_market_dispersion_5m"))>=KTH["disp65"],
          fnum(z.get("f_context_quote_volume_24h")) is not None and fnum(z.get("f_context_quote_volume_24h"))<=KTH["liq35"],
        ])
        out.append(("A2",s,2))
    if truth(a["A3_LOW_ENERGY_RESIDUAL"]):
        s=sum([
          fnum(z.get("f_micro_prev3_side_ret")) is not None and fnum(z.get("f_micro_prev3_side_ret"))>=KTH["prev60"],
          fnum(z.get("f_micro_side_ret_5m")) is not None and fnum(z.get("f_micro_side_ret_5m"))>=KTH["ret60"],
          fnum(z.get("f_new_extension_60m_norm")) is not None and fnum(z.get("f_new_extension_60m_norm"))<=KTH["ext40"],
        ])
        out.append(("A3",s,2))
    return out

rescue_bad=resid_bad & rescued
negative_miss=resid_bad-rescued
summary["residual_bad_origin"]={
 "rescue_collateral":final_metrics(rescue_bad),
 "negative_filter_miss":final_metrics(negative_miss),
 "negative_miss_inside_broad":final_metrics({i for i in negative_miss if broad_membership(i)}),
 "negative_miss_outside_all":final_metrics({i for i in negative_miss if not broad_membership(i)}),
}

closeness=defaultdict(lambda:{"exec":0,"pnl":0.0,"fallback":0,"fallback_pnl":0.0})
for pid in negative_miss:
    ss=k_scores(pid)
    if not ss:
        lab="OUTSIDE_ALL"
    elif max(s/req for _,s,req in ss)>=0.5:
        lab="ONE_CONDITION_SHORT"
    else:
        lab="ZERO_K_SIGNAL"
    x=final[pid];z=closeness[lab]
    z["exec"]+=1;z["pnl"]+=x["pnl"]
    if x["reason"]=="HIST_TIME_FALLBACK":
        z["fallback"]+=1;z["fallback_pnl"]+=x["pnl"]
summary["residual_bad_closeness"]=dict(closeness)
summary["bad_rejection"]={
 "selected_rejected":len(bad0)-len(bad_final_sel),
 "selected_reject_rate":1-len(bad_final_sel)/len(bad0),
 "executable_removed":bad_funnel["initial_executable"]-bad_funnel["final_executable_bad"],
 "executable_remove_rate":1-bad_funnel["final_executable_bad"]/bad_funnel["initial_executable"],
 "bad_pnl_improvement":bad_funnel["final_bad_pnl"]-bad_funnel["initial_ct4_pnl"],
}
summary["selection_retention"]={
 "strong_selected_final":sum(truth(base[i]["strong"]) for i in final_selected),
 "strong_selected_initial":sum(truth(r["strong"]) for r in base.values()),
 "target_selected_final":sum(bucket(i)=="TARGET_GE_1P00" for i in final_selected),
 "target_selected_initial":sum(bucket(i)=="TARGET_GE_1P00" for i in base),
}
summary["selection_retention"]["strong_rate"]=summary["selection_retention"]["strong_selected_final"]/summary["selection_retention"]["strong_selected_initial"]
summary["selection_retention"]["target_rate"]=summary["selection_retention"]["target_selected_final"]/summary["selection_retention"]["target_selected_initial"]


(RES/"sa4_summary.json").write_text(json.dumps(summary,indent=2))

with open(RES/"sa4_residual_bad_detail.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","lane","mfe_bucket","strong","pnl","reason","broad_archetypes","q95_flag","rescued","ct7_kill_membership"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for pid in sorted(resid_bad):
        x=final[pid]
        w.writerow({
          "position_id":pid,"symbol":base[pid]["symbol"],"source":base[pid]["source"],"block":base[pid]["block"],"lane":labels[pid]["lane"],
          "mfe_bucket":bucket(pid),"strong":x["strong"],"pnl":x["pnl"],"reason":x["reason"],
          "broad_archetypes":"+".join(broad_membership(pid)) or "OUTSIDE_ALL","q95_flag":pid in q95,"rescued":x["rescued"],
          "ct7_kill_membership":"+".join(kill_membership(pid)) or "NONE",
        })

with open(RES/"sa4_residual_bad_near_miss.csv","w",newline="") as f:
    fields=["position_id","symbol","source","block","lane","mfe_bucket","pnl","reason","rescued","group","A1_score","A2_score","A3_score","broad_archetypes"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for pid in sorted(resid_bad):
        ss={k:s for k,s,_ in k_scores(pid)}
        if pid in rescued:
            group="RESCUE_COLLATERAL"
        elif not ss:
            group="OUTSIDE_ALL"
        elif max(s/2 for s in ss.values())>=0.5:
            group="ONE_CONDITION_SHORT"
        else:
            group="ZERO_K_SIGNAL"
        x=final[pid]
        w.writerow({
          "position_id":pid,"symbol":base[pid]["symbol"],"source":base[pid]["source"],"block":base[pid]["block"],"lane":labels[pid]["lane"],
          "mfe_bucket":bucket(pid),"pnl":x["pnl"],"reason":x["reason"],"rescued":x["rescued"],"group":group,
          "A1_score":ss.get("A1",""),"A2_score":ss.get("A2",""),"A3_score":ss.get("A3",""),
          "broad_archetypes":"+".join(broad_membership(pid)) or "OUTSIDE_ALL",
        })

with open(RES/"sa4_funnel.csv","w",newline="") as f:
    fields=["stage","selected","bad_a","bad_b","bad_lt_0p5","gray","target","strong","ct4_executable","ct4_pnl"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for name,ids in stage.items():w.writerow({"stage":name,**selected_metrics(ids)})

print("UNIVERSE",summary["universe"])
print("BAD FUNNEL",bad_funnel)
print("\nFUNNEL")
for k,v in summary["funnel"].items():print(k,v)
print("\nFINAL",summary["final"])
print("\nREASONS")
for k,v in sorted(reasons.items(),key=lambda kv:kv[1]["pnl"]):print(k,v)
print("\nRESID BAD SEGMENTS")
for k,v in sorted(segments.items(),key=lambda kv:kv[1]["pnl"]):print(k,v)
print("\nBAD TERRITORY",summary["bad_territory"])
print("\nBAD LANE",dict(bad_lane))
print("\nBAD BLOCK",dict(bad_block))
print("\nORACLE",summary["oracle"])