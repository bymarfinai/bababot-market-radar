from __future__ import annotations
import csv, io, json, zipfile, requests, itertools, threading, statistics, math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data, exit_fill_price, gross_pnl
from research.profit_protection_v4.stage2c_runner_preservation import preserve_historical_before

BASE=Path(__file__).resolve().parent
RESULTS=BASE/'results'
FIRES=RESULTS/'LP5D_FINAL_FIRES.csv'
rows=list(csv.DictReader(FIRES.open(encoding='utf-8')))
ids=[r['pid'] for r in rows]
positions,_,orders=load_market_data(ids)

def bv(v): return str(v).lower() in ('true','1','yes')

by=defaultdict(list)
for r in rows:
    pid=r['pid']
    decision=int(r['open'])+int(r['sec'])*1000
    closed=int(positions[pid]['closed_at_ms'])
    day=datetime.fromtimestamp(decision/1000,timezone.utc).date().isoformat()
    by[(r['symbol'],day)].append((pid,decision,closed))

local=threading.local()
def sess():
    if not hasattr(local,'s'): local.s=requests.Session()
    return local.s

def fetch_first(item):
    (sym,day),arr=item
    url=f"https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
    resp=sess().get(url,timeout=90)
    if resp.status_code!=200: return {},(sym,day,f'HTTP_{resp.status_code}')
    pending={pid:(decision,closed) for pid,decision,closed in arr}; found={}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        with z.open(z.namelist()[0]) as raw:
            rd=csv.reader(io.TextIOWrapper(raw,encoding='utf-8'))
            first=next(rd,None)
            it=rd if first and first[0]=='agg_trade_id' else itertools.chain([first],rd)
            for x in it:
                if not x: continue
                try: px=float(x[1]); ts=int(x[5])
                except Exception: continue
                if not pending: break
                done=[]
                for pid,(decision,closed) in pending.items():
                    if ts>decision and ts<=closed:
                        found[pid]=(ts,px); done.append(pid)
                    elif ts>closed:
                        done.append(pid)
                for pid in done: pending.pop(pid,None)
    return found,None

found={}; errors=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(fetch_first,item) for item in by.items()]
    for fut in as_completed(futs):
        z,e=fut.result(); found.update(z)
        if e: errors.append(e)

def overlay_close(pid,exec_ts,market_px):
    p=positions[pid]; side=str(p['side']).upper(); entry=float(p['entry_price'])
    md=json.loads(p.get('raw_json') or '{}')
    initial_qty=float(md.get('initial_quantity') or 0.0)
    initial_notional=float(md.get('initial_notional_usdt') or 500.0)
    entry_fee_total=float(md.get('entry_fee_total') or 0.0)
    fee_rate=float(md.get('fee_rate') or 0.00075)
    slip=float(md.get('slippage_bps') or 2.0)
    realized,qty_closed,entry_alloc=preserve_historical_before(
        pid,exec_ts,side=side,entry_price=entry,initial_quantity=initial_qty,
        entry_fee_total=entry_fee_total,orders=orders)
    remaining=max(0.0,initial_qty-qty_closed)
    if remaining<=1e-15:
        return float(p['realized_pnl']),'NO_REMAINING_AFTER_HIST_ACTION',0.0,float(p['realized_pnl_pct'])
    fill=exit_fill_price(side,market_px,slip)
    realized += gross_pnl(side,entry,fill,remaining)-max(0.0,entry_fee_total-entry_alloc)-remaining*fill*fee_rate
    pct=100.0*realized/initial_notional if initial_notional>0 else 0.0
    return realized,'LP5D_CLOSE',remaining,pct

detail=[]
for r in rows:
    pid=r['pid']; hist=float(positions[pid]['realized_pnl'])
    decision=int(r['open'])+int(r['sec'])*1000
    close_ms=int(positions[pid]['closed_at_ms'])
    if close_ms<=decision:
        prot=hist; reason='CLOSED_BEFORE_DECISION'; exec_ts=None; raw_px=None; rem=0.0; pct=float(positions[pid]['realized_pnl_pct'])
    elif pid not in found:
        prot=hist; reason='NO_EXEC_TRADE_BEFORE_HIST_CLOSE'; exec_ts=None; raw_px=None; rem=0.0; pct=float(positions[pid]['realized_pnl_pct'])
    else:
        exec_ts,raw_px=found[pid]
        prot,reason,rem,pct=overlay_close(pid,exec_ts,raw_px)
    detail.append({
        'position_id':pid,'symbol':r['symbol'],'split':r['split'],'sec':int(r['sec']),
        'target_pre05':bv(r['target_pre05']),'winner':bv(r['winner']),'wrong_direction':bv(r['wrong_direction']),
        'path':r['label'],'decision_ms':decision,'historical_close_ms':close_ms,
        'exec_ms':exec_ts,'exec_delay_ms':None if exec_ts is None else exec_ts-decision,
        'archive_market_price':raw_px,'historical_pnl':hist,'protected_pnl':prot,'delta_pnl':prot-hist,
        'historical_positive':hist>0,'protected_positive':prot>0,'reason':reason,'remaining_qty_closed':rem,'protected_pct':pct
    })

def metrics(group):
    exe=[x for x in group if x['reason']=='LP5D_CLOSE']
    hist_pos=[x for x in group if x['historical_positive']]
    target=[x for x in group if x['target_pre05']]
    wd=[x for x in group if x['wrong_direction']]
    otherloss=[x for x in group if not x['historical_positive'] and not x['target_pre05']]
    delays=sorted(x['exec_delay_ms'] for x in exe)
    return {
        'fire_n':len(group),'executed_n':len(exe),
        'historical_pnl_on_fires':sum(x['historical_pnl'] for x in group),
        'protected_pnl_on_fires':sum(x['protected_pnl'] for x in group),
        'delta_pnl':sum(x['delta_pnl'] for x in group),
        'helped_n':sum(x['delta_pnl']>1e-12 for x in group),
        'harmed_n':sum(x['delta_pnl']<-1e-12 for x in group),
        'target_n':len(target),'target_delta_pnl':sum(x['delta_pnl'] for x in target),
        'wrong_direction_n':len(wd),'wrong_direction_delta_pnl':sum(x['delta_pnl'] for x in wd),
        'other_loss_n':len(otherloss),'other_loss_delta_pnl':sum(x['delta_pnl'] for x in otherloss),
        'historical_winner_n':len(hist_pos),'winner_delta_pnl':sum(x['delta_pnl'] for x in hist_pos),
        'winner_to_nonpositive_n':sum(x['historical_positive'] and not x['protected_positive'] for x in group),
        'loss_to_positive_n':sum((not x['historical_positive']) and x['protected_positive'] for x in group),
        'median_exec_delay_ms':statistics.median(delays) if delays else None,
        'p90_exec_delay_ms':delays[min(len(delays)-1,math.ceil(.9*len(delays))-1)] if delays else None,
    }

overall=metrics(detail)
splits={sp:metrics([x for x in detail if x['split']==sp]) for sp in ('D','V','R')}
baseline_pnl=62.53208522105432
baseline_win=176
win_delta=sum(int(x['protected_positive'])-int(x['historical_positive']) for x in detail)
summary={
 'stage':'LP-5D',
 'contract':{
   'decision':'frozen 75s SIDE_AND_MFE candidate',
   'rule':'side_return_pct <= -0.27197584845952694 AND running_mfe_pct <= 0.45855335560280874',
   'execution':'first Binance USD-M archived aggregate trade strictly after decision and no later than historical close',
   'overlay':'preserve historical actions through execution; close remaining quantity with stored slippage/fees; ignore later historical actions'
 },
 'coverage':{'fires':len(rows),'archive_groups':len(by),'fills_found':len(found),'errors':errors},
 'overall_fires':overall,
 'splits':splits,
 'current_454':{
   'baseline_pnl':baseline_pnl,'protected_pnl':baseline_pnl+overall['delta_pnl'],'delta_pnl':overall['delta_pnl'],
   'baseline_win_n':baseline_win,'protected_win_n':baseline_win+win_delta,
   'baseline_wr':baseline_win/454,'protected_wr':(baseline_win+win_delta)/454
 }
}
RESULTS/'LP5D_EXECUTION_SUMMARY.json'.write_text(json.dumps(summary,indent=2),encoding='utf-8')
with open(RESULTS/'LP5D_EXECUTION_DETAIL.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(detail[0].keys()));w.writeheader();w.writerows(detail)
print(json.dumps(summary,indent=2))