from __future__ import annotations
import csv,json,math,gc
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
import psycopg2.extras
from market_radar.persistence import _postgres_connect

SEL=list(csv.DictReader(open('/tmp/s10h_out/fresh_selection.csv')))
CACHE=Path('/tmp/s10h_archive');OUT=Path('/tmp/s10h_out')
SLIP_DEFAULT=2.;FEE_DEFAULT=.00075;NOTIONAL_DEFAULT=500.

def ff(v,d=None):
 try:x=float(v);return x if math.isfinite(x) else d
 except:return d
def dstr(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).date().isoformat()
def date_range(a,b):
 d=datetime.fromtimestamp(a/1000,timezone.utc).date();e=datetime.fromtimestamp(b/1000,timezone.utc).date();o=[]
 while d<=e:o.append(d.isoformat());d+=timedelta(days=1)
 return o
def cp(kind,sym,d):return CACHE/f'{kind}__{sym.replace("/","_")}__{d}.json'
def side_ret(entry,px):return 100*(entry/px-1)
def entry_fill_short(mkt,slip):return mkt*(1-slip/10000)
def exit_fill_short(mkt,slip):return mkt*(1+slip/10000)

ids=[r['meta_position_id'] for r in SEL]
query="""
select p.position_id,p.signal_id,p.symbol,p.opened_at_ms,p.closed_at_ms,p.entry_price,
p.realized_pnl,p.raw_json,r.checked_at_ms as gate_checked_at_ms
from positions p
join lateral (
 select checked_at_ms from entry_revalidations x
 where x.signal_id=p.signal_id and x.verdict='ENTER' and x.checked_at_ms<=p.opened_at_ms
 order by x.checked_at_ms desc limit 1
) r on true
where p.position_id=any(%s)
"""
with _postgres_connect() as conn:
 with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
  cur.execute(query,(ids,));P={x['position_id']:dict(x) for x in cur.fetchall()}
assert len(P)==len(ids),(len(P),len(ids))

def kline_open(sym,ms):
 p=cp('k',sym,dstr(ms))
 rows=json.loads(p.read_text())
 for x in rows:
  try:
   if int(x[0])==ms:return float(x[1])
  except:pass
 return None

plans={}
for r in SEL:
 pid=r['meta_position_id'];p=P[pid];lane=int(r['entry_lane']);raw=p['raw_json'];raw=json.loads(raw or '{}') if isinstance(raw,str) else (raw or {})
 if lane==0:
  mkt=float(raw.get('entry_market_price') or p['entry_price'])
  plans[pid]={'lane':0,'entry_ms':int(p['opened_at_ms']),'entry_market':mkt,'entry_fill':float(p['entry_price']),'executable':True}
 else:
  target=int(p['gate_checked_at_ms'])+lane*60_000;ems=(target//60_000)*60_000+60_000;mkt=kline_open(p['symbol'],ems)
  ex=bool(mkt is not None and int(p['closed_at_ms'])>ems)
  pl={'lane':lane,'target_ms':target,'entry_ms':ems,'entry_market':mkt,'executable':ex}
  if mkt is not None:
   slip=float(raw.get('slippage_bps',SLIP_DEFAULT));pl['entry_fill']=entry_fill_short(mkt,slip)
  plans[pid]=pl

exec_rows=[r for r in SEL if plans[r['meta_position_id']]['executable']]
print('PLAN selected',len(SEL),'exec',len(exec_rows),'noexec',len(SEL)-len(exec_rows),'strong_exec',sum(r['strong_win']=='True' for r in exec_rows),flush=True)

def load_path(pid):
 p=P[pid];pl=plans[pid];start=pl['entry_ms'];end=int(p['closed_at_ms']);out=[]
 for d in date_range(start,end):
  f=cp('a',p['symbol'],d)
  if not f.exists():continue
  rows=json.loads(f.read_text())
  out.extend((int(x[0]),float(x[1])) for x in rows if start<=int(x[0])<=end)
  del rows;gc.collect()
 out.sort(key=lambda x:x[0]);return out

def meta(pid):
 p=P[pid];raw=p['raw_json'];raw=json.loads(raw or '{}') if isinstance(raw,str) else (raw or {})
 return {'slip':float(raw.get('slippage_bps',SLIP_DEFAULT)),'fee':float(raw.get('fee_rate',FEE_DEFAULT)),'notional':float(raw.get('initial_notional_usdt',NOTIONAL_DEFAULT))}
def calc(pid,mkt):
 p=P[pid];pl=plans[pid];m=meta(pid);q=m['notional']/pl['entry_fill'];ef=m['notional']*m['fee'];fill=exit_fill_short(mkt,m['slip']);xf=q*fill*m['fee'];gross=q*(pl['entry_fill']-fill);u=gross-ef-xf;return u,100*u/m['notional']
def samples(pid,tr):
 pl=plans[pid];end=int(P[pid]['closed_at_ms']);n=pl['entry_ms']+5000;last=pl['entry_market'];o=[]
 for ts,px in tr:
  while n<ts and n<=end:o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
  last=px
  while n==ts and n<=end:o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
 while n<=end:o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
 return o
def hold(pid,tr):
 pl=plans[pid];mkt=tr[-1][1] if tr else pl['entry_market'];return {'usd':calc(pid,mkt)[0],'active':False,'reason':'HIST_TIME_FALLBACK'}
def v43(pid,tr,sa):
 peak=-999.;runner=False;rc=0
 for ts,px,pnl in sa:
  peak=max(peak,pnl)
  if not runner and peak>=1.5:runner=True
  if runner:
   rc=rc+1 if pnl<=peak*.90 else 0
   if rc>=2:return {'usd':calc(pid,px)[0],'active':True,'reason':'RUNNER_CLOSE'}
   continue
  if peak>=.5 and pnl<=peak*.75:return {'usd':calc(pid,px)[0],'active':True,'reason':'FULL_CLOSE_050'}
 return hold(pid,tr)
def be10(pid,tr):
 pl=plans[pid];touched=False;armed=False
 for ts,px in tr:
  gp=side_ret(pl['entry_fill'],px);net=calc(pid,px)[1]
  if gp>=.10:touched=True
  if touched and net>=0 and not armed:armed=True;continue
  if armed and net<=0:return {'usd':calc(pid,px)[0],'active':True,'reason':'BE0.10'}
 return hold(pid,tr)

rec=[]
for i,r in enumerate(exec_rows,1):
 pid=r['meta_position_id'];tr=load_path(pid);sa=samples(pid,tr);h=hold(pid,tr);v=v43(pid,tr,sa);b=be10(pid,tr);c=v if v['active'] else b
 rec.append({'position_id':pid,'symbol':P[pid]['symbol'],'label':r['primary_meta_label'],'strong_win':r['strong_win']=='True','lane':int(r['entry_lane']),
             'hold':h['usd'],'v43':v['usd'],'comp':c['usd'],'reason':c['reason'],'actual_old_pnl':float(P[pid]['realized_pnl'] or 0)})
 del tr,sa;gc.collect()
 if i%50==0 or i==len(exec_rows):print('REPLAY',i,'/',len(exec_rows),flush=True)

def met(g,key):
 vals=[x[key] for x in g];return {'n':len(vals),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals),'gp':sum(v for v in vals if v>0),'gl':sum(v for v in vals if v<0)}
summary={'stage':'SHORT-S10H','status':'SEALED_FRESH_COMPLETE','source_n':1721,'resolved_n':1449,'labels':{'META_LOSS':1031,'TIMEOUT':272,'META_WIN':418},
         'strong_total':261,'selected_n':len(SEL),'selected_strong_n':sum(r['strong_win']=='True' for r in SEL),
         'selected_precision':sum(r['strong_win']=='True' for r in SEL)/len(SEL),'strong_recall':sum(r['strong_win']=='True' for r in SEL)/261,
         'lane_selected':dict(Counter(r['entry_lane'] for r in SEL)),'executable_n':len(exec_rows),'noexec_n':len(SEL)-len(exec_rows),
         'executable_strong_n':sum(r['strong_win']=='True' for r in exec_rows),'hold':met(rec,'hold'),'v43':met(rec,'v43'),'comp':met(rec,'comp'),'actual_old':met(rec,'actual_old_pnl'),
         'lanes':{}}
for lane in (0,1,2,3):
 q=[x for x in rec if x['lane']==lane];summary['lanes'][str(lane)]={'n':len(q),'strong_n':sum(x['strong_win'] for x in q),'comp':met(q,'comp'),'hold':met(q,'hold')}
summary['strong_cohort']={'comp':met([x for x in rec if x['strong_win']],'comp')}
summary['non_target_cohort']={'comp':met([x for x in rec if not x['strong_win']],'comp')}
with open(OUT/'s10h_trade_replay.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rec[0]));w.writeheader();w.writerows(rec)
(OUT/'s10h_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)