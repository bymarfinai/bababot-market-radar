from __future__ import annotations
import csv,json,os
from pathlib import Path
from collections import Counter
from market_radar.parallel_protection_shadow_adapters import _evaluate_branch
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data
from research.profit_protection_v4.stage3d2_recoverability_analysis import prepare_market

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"research/profit_protection_v4/results/all_positive_mfe_v42c_replay.csv"
LSEL=ROOT/"research/profit_protection_v4/archive/failed/results/v43_ls3_long_reduce25_selected_trades.csv"
SSEL=ROOT/"research/profit_protection_v4/archive/failed/results/v43_ls4_short_reduce25_selected_trades.csv"
BE2=ROOT/"research/profit_protection_v4/results/na_be2_causal_replay.csv"
DATA_ROOT=Path(os.environ.get("CORE_DATA_DIR","/opt/core-app/data"))
MARKET=DATA_ROOT/"na_be1_market.json"
RAW=DATA_ROOT/"na_be1_aggtrades_raw.json"
OUT=ROOT/"research/profit_protection_v4/results/ps3_historical_parity.json"

def branch(key):
 return {"branch_key":key,"state_json":"{}","mfe_pct":None,"mae_pct":None}

def apply(parent,b,event):
 st,mfe,mae,cs=_evaluate_branch(parent=parent,branch=b,event=event)
 b={**b,"state_json":json.dumps(st),"mfe_pct":mfe,"mae_pct":mae,"current_state":cs}
 return b,st

def parent_from_db(p):
 meta=json.loads(p.get("raw_json") or "{}")
 return {"side":p["side"],"entry_price":float(p["entry_price"]),
   "initial_quantity":float(meta.get("initial_quantity") or 0),
   "initial_notional_usdt":float(meta.get("initial_notional_usdt") or 500),
   "metadata_json":json.dumps(meta)}

def classify(st):
 small=bool(st.get("small_fired")); runner=bool(st.get("runner_qualified")) and bool(st.get("decision_terminal"))
 if small and runner:return "REDUCE25+RUNNER_CLOSE"
 if runner:return "RUNNER_CLOSE"
 if small:return "REDUCE25"
 return "NO_ACTION"

def main():
 rows=list(csv.DictReader(BASE.open()))
 ids=[r["position_id"] for r in rows]
 positions,obs,orders=load_market_data(ids)
 v42_mismatch=[]
 v42_counts=Counter()
 for row in rows:
  pid=row["position_id"];p=positions[pid];parent=parent_from_db(p);b=branch("V42_BASELINE");st={}
  path=[x for x in obs[pid] if int(p["opened_at_ms"])<=int(x["observed_at_ms"])<=int(p["closed_at_ms"])]
  for seq,x in enumerate(path,1):
   ev={"event_seq":seq,"source_event_id":f"S:{seq}","event_time_ms":int(x["observed_at_ms"]),
       "event_type":"PROTECTION_SAMPLE_5S","market_price":float(x["current_price"])}
   b,st=apply(parent,b,ev)
  got=classify(st);exp=row["protection_actions"];v42_counts[got]+=1
  if got!=exp:v42_mismatch.append({"position_id":pid,"expected":exp,"got":got})

 selected={}
 for path in (LSEL,SSEL):
  for r in csv.DictReader(path.open()): selected[r["position_id"]]=r
 v43_mismatch=[]
 for pid,r in selected.items():
  p=positions[pid];parent=parent_from_db(p);b=branch("V43_LS");st={}
  path=[x for x in obs[pid] if int(p["opened_at_ms"])<=int(x["observed_at_ms"])<=int(p["closed_at_ms"])]
  for seq,x in enumerate(path,1):
   ev={"event_seq":seq,"source_event_id":f"S:{seq}","event_time_ms":int(x["observed_at_ms"]),
       "event_type":"PROTECTION_SAMPLE_5S","market_price":float(x["current_price"])}
   b,st=apply(parent,b,ev)
   if st.get("decision_terminal"): break
  intent=st.get("virtual_intent") or {}
  got=intent.get("event_time_ms");exp=int(float(r["small_at_ms"]))
  if got!=exp:v43_mismatch.append({"position_id":pid,"expected_ms":exp,"got_ms":got,"reason":st.get("reason")})

 anatomy=[r for r in csv.DictReader((ROOT/"research/profit_protection_v4/results/v43_ls2_trade_anatomy.csv").open()) if r["protection_actions"]=="NO_ACTION"]
 pos,_,_=prepare_market(json.loads(MARKET.read_text()))
 raw=json.loads(RAW.read_text())["positions"]
 exp={(r["position_id"],r["arm_pct"]):r for r in csv.DictReader(BE2.open()) if r["latency_ms"]=="0" and r["arm_pct"] in {"0.18","0.25"}}
 be_mismatch=[]
 for row in anatomy:
  pid=row["position_id"];p=pos[pid];meta=p["metadata"];parent={"side":p["side"],"entry_price":float(p["entry_price"]),
      "initial_quantity":float(meta.get("initial_quantity") or 0),"initial_notional_usdt":float(meta.get("initial_notional_usdt") or 500),
      "metadata_json":json.dumps(meta)}
  trades=sorted([t for t in raw[pid]["trades"] if int(p["opened_at_ms"])<=int(t["transact_time"])<=int(p["closed_at_ms"])],key=lambda x:(int(x["transact_time"]),int(x["agg_trade_id"])))
  for arm,key in (("0.18","BE018_AGGRESSIVE"),("0.25","BE025_CONSERVATIVE")):
   b=branch(key);st={}
   for seq,t in enumerate(trades,1):
    ev={"event_seq":seq,"source_event_id":str(t["agg_trade_id"]),"event_time_ms":int(t["transact_time"]),
        "event_type":"AGG_TRADE","market_price":float(t["price"])}
    b,st=apply(parent,b,ev)
    if st.get("decision_terminal"): break
   e=exp[(pid,arm)]
   got_trig=bool(st.get("decision_terminal")); expected=e["triggered"]=="True"
   got_ts=(st.get("virtual_intent") or {}).get("event_time_ms")
   expected_ts=int(float(e["cross_ts"])) if e["cross_ts"] else None
   if got_trig!=expected or got_ts!=expected_ts:
    be_mismatch.append({"position_id":pid,"arm":arm,"expected_triggered":expected,"got_triggered":got_trig,"expected_ts":expected_ts,"got_ts":got_ts})

 out={"stage":"PS-3-HISTORICAL-PARITY","status":"PASS" if not(v42_mismatch or v43_mismatch or be_mismatch) else "FAIL",
  "v42":{"n":len(rows),"mismatch_n":len(v42_mismatch),"action_counts":dict(v42_counts),"mismatches":v42_mismatch[:20]},
  "v43":{"n":len(selected),"mismatch_n":len(v43_mismatch),"mismatches":v43_mismatch[:20]},
  "be":{"positions":len(anatomy),"comparisons":len(anatomy)*2,"mismatch_n":len(be_mismatch),"mismatches":be_mismatch[:20]}}
 OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print(json.dumps(out,sort_keys=True))
 if out["status"]!="PASS": raise SystemExit(1)
if __name__=="__main__":main()
