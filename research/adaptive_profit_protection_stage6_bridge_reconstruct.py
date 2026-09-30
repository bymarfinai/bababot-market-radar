from market_radar.persistence import _postgres_connect
import csv, json, math, statistics, time, urllib.parse, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

V3=1790687518407
CUT=1790694923721
OUTDIR=Path("/tmp/stage6_bridge_reconstruct")
OUTDIR.mkdir(parents=True,exist_ok=True)
FEE_RATE=0.00075
SLIPPAGE_BPS=2.0

def f(v):
    try:return float(v or 0)
    except:return 0.0

def side_ret(side, entry, px):
    if not entry:return 0.0
    return ((px-entry)/entry*100.0) if side=="LONG" else ((entry-px)/entry*100.0)

def close_fill(side, market):
    slip=SLIPPAGE_BPS/10000.0
    return market*(1-slip) if side=="LONG" else market*(1+slip)

def get_json(url,tries=5):
    err=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"bababot-stage6-bridge/1.0"})
            with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
        except Exception as e:
            err=e; time.sleep(0.5*(i+1))
    raise err

def fetch_symbol_market(spec):
    sym,start,end=spec
    qs=urllib.parse.urlencode({"symbol":sym,"interval":"1m","startTime":start-300000,"endTime":end+60000,"limit":1000})
    kl=get_json("https://fapi.binance.com/fapi/v1/klines?"+qs)
    oq=urllib.parse.urlencode({"symbol":sym,"period":"5m","startTime":start-600000,"endTime":end+300000,"limit":500})
    oi=get_json("https://fapi.binance.com/futures/data/openInterestHist?"+oq)
    return sym,kl,oi

with _postgres_connect() as conn:
    with conn.cursor() as cur:
        cur.execute("""select * from positions where mode='PAPER' and status='CLOSED'
                       and closed_at_ms between %s and %s order by closed_at_ms""",(V3,CUT))
        pcols=[d[0] for d in cur.description]
        positions=[dict(zip(pcols,r)) for r in cur.fetchall()]
        pids=[p["position_id"] for p in positions]
        cur.execute("""select * from paper_orders where position_id=any(%s) and status='FILLED'
                       and executed_at_ms<=%s order by executed_at_ms""",(pids,CUT))
        ocols=[d[0] for d in cur.description]
        orders=[dict(zip(ocols,r)) for r in cur.fetchall()]
        cur.execute("""select * from position_evaluations where position_id=any(%s)
                       and evaluated_at_ms<=%s order by evaluated_at_ms""",(pids,CUT))
        ecols=[d[0] for d in cur.description]
        evals=[dict(zip(ecols,r)) for r in cur.fetchall()]
        cur.execute("""select * from pipeline_cohorts where signal_id=any(%s)""",
                    ([p["signal_id"] for p in positions],))
        ccols=[d[0] for d in cur.description]
        cohorts=[dict(zip(ccols,r)) for r in cur.fetchall()]
orders_by=defaultdict(list)
for o in orders: orders_by[o["position_id"]].append(o)
evals_by=defaultdict(list)
for e in evals: evals_by[e["position_id"]].append(e)
cohort_by={c["signal_id"]:c for c in cohorts}

symbol_ranges={}
for p in positions:
    sym=p["symbol"]; a=int(p["opened_at_ms"]); b=int(p["closed_at_ms"])
    if sym not in symbol_ranges:symbol_ranges[sym]=[a,b]
    else:
        symbol_ranges[sym][0]=min(symbol_ranges[sym][0],a)
        symbol_ranges[sym][1]=max(symbol_ranges[sym][1],b)

market={}
errors={}
specs=[(s,a,b) for s,(a,b) in symbol_ranges.items()]
with ThreadPoolExecutor(max_workers=12) as ex:
    futs={ex.submit(fetch_symbol_market,x):x[0] for x in specs}
    for fut in as_completed(futs):
        sym=futs[fut]
        try:
            s,kl,oi=fut.result()
            market[s]={"klines":kl,"oi":oi}
        except Exception as e:
            errors[sym]=repr(e)

def oi_series(rows):
    out=[]
    prev=None
    for r in rows:
        val=f(r.get("sumOpenInterest")); ts=int(r.get("timestamp") or 0)
        ch=((val-prev)/prev*100.0) if prev else None
        out.append((ts,val,ch))
        prev=val
    return out

def latest_oi(series,ts):
    best=(None,None,None)
    for x in series:
        if x[0]<=ts:best=x
        else:break
    return best

trade_rows=[]
timeline=[]
event_rows=[]

for p in positions:
    pid=p["position_id"]; side=p["side"]; entry=f(p["entry_price"])
    pos_orders=orders_by[pid]
    open_order=next((o for o in pos_orders if o["action"]=="OPEN"),None)
    initial_qty=f((open_order or {}).get("executed_quantity"))
    entry_fee=f((open_order or {}).get("fee"))
    c=cohort_by.get(p["signal_id"],{})
    raw={}
    try:raw=json.loads(p.get("raw_json") or "{}")
    except:pass
    gross=f(raw.get("realized_gross"))
    total_fees=f(raw.get("allocated_entry_fee"))+f(raw.get("exit_fees"))
    pos_evals=evals_by[pid]
    max_mfe=max([f(e.get("mfe_pct")) for e in pos_evals] or [0])
    min_mae=min([f(e.get("mae_pct")) for e in pos_evals] or [0])
    fast_n=0; thesis_n=0
    for e in pos_evals:
        snap={}
        try:snap=json.loads(e.get("snapshot_json") or "{}")
        except:pass
        layer=snap.get("evaluation_layer")
        if layer=="FAST_GUARD":fast_n+=1
        if layer=="THESIS_5M":thesis_n+=1
        event_rows.append({
          "position_id":pid,"symbol":p["symbol"],"side":side,"event_type":"EVALUATION",
          "event_time_ms":e["evaluated_at_ms"],"action":e.get("final_action"),"layer":layer,
          "price":e.get("current_price"),"unrealized_pnl_pct":e.get("unrealized_pnl_pct"),
          "mfe_pct":e.get("mfe_pct"),"mae_pct":e.get("mae_pct"),"health_score":e.get("health_score"),
          "reasons_json":e.get("reasons_json"),"contradictions_json":e.get("contradictions_json"),
          "snapshot_json":e.get("snapshot_json")
        })
    for o in pos_orders:
        event_rows.append({
          "position_id":pid,"symbol":p["symbol"],"side":side,"event_type":"ORDER",
          "event_time_ms":o.get("executed_at_ms") or o.get("created_at_ms"),"action":o.get("action"),
          "layer":"EXECUTION","price":o.get("fill_price"),"unrealized_pnl_pct":None,
          "mfe_pct":None,"mae_pct":None,"health_score":None,
          "reasons_json":json.dumps([o.get("reason")]),"contradictions_json":"[]",
          "snapshot_json":o.get("payload_json")
        })

    trade_rows.append({
      "position_id":pid,"signal_id":p["signal_id"],"symbol":p["symbol"],"side":side,
      "opened_at_ms":p["opened_at_ms"],"closed_at_ms":p["closed_at_ms"],
      "duration_min":(int(p["closed_at_ms"])-int(p["opened_at_ms"]))/60000.0,
      "entry_price":entry,"exit_price":p["exit_price"],"initial_qty":initial_qty,
      "gross_pnl":gross,"fees":total_fees,"net_pnl":p["realized_pnl"],"net_roi_pct":p["realized_pnl_pct"],
      "mfe_pct_persisted":max_mfe,"mae_pct_persisted":min_mae,
      "reduce_count":sum(1 for o in pos_orders if o["action"]=="REDUCE"),
      "fast_eval_count":fast_n,"thesis_eval_count":thesis_n,"eval_count":len(pos_evals),
      "fresh_gate_version":c.get("fresh_gate_version"),"paper_trading_version":c.get("paper_trading_version"),
      "close_reason":p.get("close_reason")
    })

    mk=market.get(p["symbol"],{})
    klines=mk.get("klines",[])
    oi=oi_series(mk.get("oi",[]))
    relevant=[k for k in klines if int(k[6])>=int(p["opened_at_ms"]) and int(k[0])<=int(p["closed_at_ms"])]
    if not relevant:continue

    reduces=[o for o in pos_orders if o["action"]=="REDUCE"]
    realized_partial=0.0
    remaining_qty=initial_qty
    allocated_entry=0.0
    processed=set()
    peak_econ=-1e99
    peak_econ_time=None
    peak_close_side_ret=-1e99
    peak_close_time=None
    ret_hist=[]
    closes=[]
    highs=[]
    lows=[]
    for k in relevant:
        open_t=int(k[0]); close_t=int(k[6])
        o,h,l,cl=map(float,[k[1],k[2],k[3],k[4]])
        vol=f(k[5]); taker=f(k[9]); taker_share=taker/vol if vol>0 else None
        # Apply partial exits known to have executed by this closed-candle timestamp.
        for ro in reduces:
            oid=ro["order_id"]; et=int(ro.get("executed_at_ms") or 0)
            if oid in processed or et>close_t:continue
            qty=f(ro.get("executed_quantity")); fill=f(ro.get("fill_price")); fee=f(ro.get("fee"))
            gross_event=qty*(fill-entry) if side=="LONG" else qty*(entry-fill)
            alloc=entry_fee*(qty/initial_qty) if initial_qty else 0
            realized_partial += gross_event-alloc-fee
            allocated_entry += alloc
            remaining_qty=max(0.0,remaining_qty-qty)
            processed.add(oid)

        sim_fill=close_fill(side,cl)
        unreal_gross=remaining_qty*(sim_fill-entry) if side=="LONG" else remaining_qty*(entry-sim_fill)
        remaining_entry_fee=max(0.0,entry_fee-allocated_entry)
        est_exit_fee=remaining_qty*sim_fill*FEE_RATE
        econ=realized_partial+unreal_gross-remaining_entry_fee-est_exit_fee

        sr=side_ret(side,entry,cl)
        if econ>peak_econ:peak_econ=econ;peak_econ_time=close_t
        if sr>peak_close_side_ret:peak_close_side_ret=sr;peak_close_time=close_t
        giveback=max(0.0,peak_econ-econ)
        giveback_ratio=(giveback/peak_econ) if peak_econ>0 else None
        time_since_peak=(close_t-peak_econ_time)/1000.0 if peak_econ_time else None

        prev=closes[-1] if closes else None
        r1=(cl/prev-1)*100.0 if prev else None
        if r1 is not None:ret_hist.append(r1)
        closes.append(cl); highs.append(h); lows.append(l)
        r3=(cl/closes[-4]-1)*100.0 if len(closes)>=4 else None
        rv5=statistics.pstdev(ret_hist[-5:]) if len(ret_hist)>=2 else None
        rv15=statistics.pstdev(ret_hist[-15:]) if len(ret_hist)>=2 else None
        roll_high=max(highs[-5:]); roll_low=min(lows[-5:])
        micro_break_up=cl>max(highs[-5:-1]) if len(highs)>=2 else False
        micro_break_down=cl<min(lows[-5:-1]) if len(lows)>=2 else False
        oit,oiv,oich=latest_oi(oi,close_t)
        timeline.append({
          "position_id":pid,"symbol":p["symbol"],"side":side,"candle_open_ms":open_t,"candle_close_ms":close_t,
          "open":o,"high":h,"low":l,"close":cl,"volume":vol,"taker_buy_share_1m":taker_share,
          "ret_1m_pct":r1,"ret_3m_pct":r3,"rv5_1m_pct":rv5,"rv15_1m_pct":rv15,
          "rolling_5m_high":roll_high,"rolling_5m_low":roll_low,"micro_break_up":micro_break_up,"micro_break_down":micro_break_down,
          "oi_timestamp_ms":oit,"open_interest":oiv,"oi_change_5m_pct":oich,
          "realized_partial_pnl":realized_partial,"remaining_qty":remaining_qty,
          "economic_pnl_if_closed_now":econ,"economic_roi_pct":econ/500.0*100.0,
          "peak_economic_pnl":peak_econ,"peak_economic_roi_pct":peak_econ/500.0*100.0,
          "economic_giveback_usd":giveback,"economic_giveback_ratio":giveback_ratio,
          "time_since_economic_peak_sec":time_since_peak,
          "side_return_close_pct":sr,"peak_side_return_close_pct":peak_close_side_ret,
          "time_since_price_peak_sec":(close_t-peak_close_time)/1000.0 if peak_close_time else None
        })
# Write CSV/JSON outputs.
def write_csv(path,rows):
    if not rows:return
    fields=[]
    seen=set()
    for r in rows:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

write_csv(OUTDIR/"stage1_trade_master.csv",trade_rows)
write_csv(OUTDIR/"stage1_timeline_1m.csv",timeline)
write_csv(OUTDIR/"stage1_events.csv",sorted(event_rows,key=lambda x:(x["position_id"],int(x["event_time_ms"] or 0))))

# Coverage and reconstruction diagnostics.
tl_by=defaultdict(list)
for r in timeline:tl_by[r["position_id"]].append(r)
coverage=[]
for t in trade_rows:
    rows=tl_by.get(t["position_id"],[])
    recon_peak=max([f(x["peak_side_return_close_pct"]) for x in rows] or [0])
    coverage.append({
      "position_id":t["position_id"],"symbol":t["symbol"],"timeline_rows":len(rows),
      "persisted_eval_count":t["eval_count"],"persisted_fast_count":t["fast_eval_count"],
      "persisted_mfe_pct":t["mfe_pct_persisted"],"reconstructed_peak_close_pct":recon_peak,
      "mfe_minus_reconstructed_close_peak_pp":t["mfe_pct_persisted"]-recon_peak
    })
write_csv(OUTDIR/"stage1_coverage.csv",coverage)

with_tl=sum(1 for x in coverage if x["timeline_rows"]>0)
manifest={
 "stage":"Adaptive Profit Protection Discovery - Stage 1 Dataset Reconstruction",
 "snapshot_cutoff_ms":CUT,"v3_start_ms":V3,"trade_count":len(trade_rows),
 "unique_symbols":len(symbol_ranges),"symbols_market_data_ok":len(market),"symbols_market_data_error":len(errors),
 "trades_with_1m_timeline":with_tl,"timeline_rows":len(timeline),"event_rows":len(event_rows),
 "resolution":{"market_path":"closed 1m Binance USD-M klines","oi":"5m Binance openInterestHist","exact_events":"persisted position_evaluations + paper_orders"},
 "causality_notes":[
   "Only closed 1m candles are used for reconstructed decision rows.",
   "Partial exits are applied only after their executed_at_ms.",
   "Economic PnL estimates use paper fee 0.075% and 2 bps adverse exit slippage.",
   "Unpersisted 15-second HOLD ticks are not invented; exact FAST_GUARD rows exist only where persisted.",
   "Candle high/low are retained as descriptive path data but adaptive decisions should use closed-candle fields unless replay explicitly models intrabar execution."
 ],
 "market_data_errors":errors
}
(OUTDIR/"stage1_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False))