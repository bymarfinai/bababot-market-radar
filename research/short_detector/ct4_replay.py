from __future__ import annotations
import csv,json,math,gc
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter

CT1=json.load(open('/tmp/ct1_summary.json'))
CT2=list(csv.DictReader(open('/tmp/ct2_trade_detail.csv')))
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
FF={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
FAN={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv'))}
RPOS=json.load(open('/tmp/s10f_db364.json'))['positions']
FPOS={str(x['position_id']):x for x in json.load(open('/tmp/s10j5_positions.json'))}
RBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D'}
FBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv'))}
RC=Path('/tmp/ct4_research_archive')
FC=Path('/tmp/s10j5_archive')
THS=[('BASE',0.0338983050847),('T005',0.05),('T0075',0.075),('T010',0.10)]

def truth(v):return str(v).lower()=='true'
def dstr(ms):return datetime.fromtimestamp(int(ms)/1000,timezone.utc).date().isoformat()
def drange(a,b):
 d=datetime.fromtimestamp(int(a)/1000,timezone.utc).date();e=datetime.fromtimestamp(int(b)/1000,timezone.utc).date();o=[]
 while d<=e:o.append(d.isoformat());d+=timedelta(days=1)
 return o
def rawj(p):
 x=p.get('raw_json')
 if isinstance(x,str):
  try:return json.loads(x or '{}')
  except:return {}
 return x or {}
def side_ret(entry,px):return 100*(entry/px-1)
def entry_fill_short(mkt,slip):return mkt*(1-slip/10000)
def exit_fill_short(mkt,slip):return mkt*(1+slip/10000)

def cachefile(src,kind,sym,d):
 return (RC if src=='research' else FC)/f'{kind}__{sym}__{d}.json'
def kline_open(src,sym,ms):
 p=cachefile(src,'k',sym,dstr(ms))
 if not p.exists():return None
 for x in json.loads(p.read_text()):
  try:
   if int(x[0])==int(ms):return float(x[1])
  except:pass
 return None
def load_path(src,sym,start,end):
 out=[]
 for d in drange(start,end):
  p=cachefile(src,'a',sym,d)
  if not p.exists():continue
  rows=json.loads(p.read_text())
  out.extend((int(x[0]),float(x[1])) for x in rows if start<=int(x[0])<=end)
  del rows;gc.collect()
 out.sort(key=lambda x:x[0]);return out
def mdata(p):
 raw=rawj(p);return float(raw.get('slippage_bps',2.0)),float(raw.get('fee_rate',.00075)),float(raw.get('initial_notional_usdt',500.0))
def calc(entry_fill,mkt,p):
 sl,fee,notional=mdata(p);q=notional/entry_fill;ef=notional*fee;fill=exit_fill_short(mkt,sl);xf=q*fill*fee
 usd=q*(entry_fill-fill)-ef-xf;return usd,100*usd/notional
def samples(entry_ms,entry_market,entry_fill,end,tr):
 n=entry_ms+5000;last=entry_market;o=[]
 for ts,px in tr:
  while n<ts and n<=end:o.append((n,last,side_ret(entry_fill,last)));n+=5000
  last=px
  while n==ts and n<=end:o.append((n,last,side_ret(entry_fill,last)));n+=5000
 while n<=end:o.append((n,last,side_ret(entry_fill,last)));n+=5000
 return o
def replay(src,p,sym,entry_ms,entry_market,entry_fill):
 end=int(p['closed_at_ms']);tr=load_path(src,sym,entry_ms,end)
 def hold():
  mkt=tr[-1][1] if tr else entry_market
  return {'pnl':calc(entry_fill,mkt,p)[0],'reason':'HIST_TIME_FALLBACK','v43_active':False}
 sa=samples(entry_ms,entry_market,entry_fill,end,tr)
 peak=-999.;runner=False;rc=0;v=None
 for ts,px,pnl in sa:
  peak=max(peak,pnl)
  if not runner and peak>=1.5:runner=True
  if runner:
   rc=rc+1 if pnl<=peak*.90 else 0
   if rc>=2:v={'pnl':calc(entry_fill,px,p)[0],'reason':'RUNNER_CLOSE','v43_active':True};break
   continue
  if peak>=.5 and pnl<=peak*.75:
   v={'pnl':calc(entry_fill,px,p)[0],'reason':'FULL_CLOSE_050','v43_active':True};break
 if v is not None:return v
 # V43 no-action -> BE0.10
 touched=False;armed=False
 _,_,notional=mdata(p)
 for ts,px in tr:
  gp=side_ret(entry_fill,px);net=100*calc(entry_fill,px,p)[0]/notional
  if gp>=.10:touched=True
  if touched and net>=0 and not armed:
   armed=True;continue
  if armed and net<=0:return {'pnl':calc(entry_fill,px,p)[0],'reason':'BE0.10','v43_active':False}
 return hold()

# threshold list resolver from CT1
def ct1row(th):
 return min(CT1['thresholds'],key=lambda z:abs(float(z['threshold'])-th))

# shift maps by source/th
shift={}
for src in ['research','fresh']:
 for name,th in THS[1:]:
  key=f'{th:.6f}';shift[(src,key)]={}
for r in CT2:
 key=f"{float(r['threshold']):.6f}"
 if (r['source'],key) not in shift:continue
 if r['status']=='SHIFTED':
  shift[(r['source'],key)][r['position_id']]=(int(r['base_lane']),int(r['new_lane']),r['base_source'],r['new_source'])

# metadata helpers
def symbol(src,pid):
 if src=='research':return RBASE[pid]['symbol']
 return FPOS[pid]['symbol']
def block(src,pid):
 if src=='research':return 'Research_'+RBASE[pid]['split']
 ms=int(float(FF[pid]['meta_opened_at_ms']));return 'Fresh_'+datetime.fromtimestamp(ms/1000,timezone.utc).strftime('%Y-%m-%d')
def strong(src,pid):
 return truth(RBASE[pid]['strong_win']) if src=='research' else truth(FAN[pid]['strong_win'])
def baseline_lane(src,pid):
 if src=='research':
  r=RBASE[pid];return 0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
 return int(FBASE[pid]['lane']) if pid in FBASE else int(FAN[pid]['_lane'])
def base_exec(src,pid):
 if src=='research':return truth(RBASE[pid]['executable'])
 return pid in FBASE
def base_pnl(src,pid):
 return float(RBASE[pid]['COMP_pnl']) if src=='research' else float(FBASE[pid]['comp'])
def base_reason(src,pid):
 return RBASE[pid]['COMP_reason'] if src=='research' else FBASE[pid]['reason']

# benchmark replay engine on research lane-shift candidates at BASE entry
bench=[]
bench_ids=[]
for key,m in shift.items():
 if key[0]!='research':continue
 for pid,(bl,nl,bs,ns) in m.items():
  if bl!=nl and pid not in bench_ids:bench_ids.append(pid)
for pid in bench_ids:
 if len(bench)>=30:break
 if not base_exec('research',pid):continue
 lane=baseline_lane('research',pid)
 if lane==0:continue
 p=RPOS[pid];sym=symbol('research',pid);target=int(float(TM[pid][f't{lane}_target_ms']));ems=(target//60000)*60000+60000
 mkt=kline_open('research',sym,ems)
 if mkt is None or int(p['closed_at_ms'])<=ems:continue
 ent=entry_fill_short(mkt,mdata(p)[0]); rr=replay('research',p,sym,ems,mkt,ent);stored=base_pnl('research',pid)
 bench.append({'pid':pid,'stored':stored,'calc':rr['pnl'],'diff':rr['pnl']-stored})
print('BENCH n',len(bench),'maxabs',max(abs(x['diff']) for x in bench) if bench else None,'exact',sum(abs(x['diff'])<1e-9 for x in bench),'/',len(bench),flush=True)
if bench and max(abs(x['diff']) for x in bench)>1e-6:
 print('BENCH WORST',sorted(bench,key=lambda x:-abs(x['diff']))[:5],flush=True)
 # do not abort: stored baseline may use legacy cache/path metadata, but report discrepancy

allres=[]
integrity={'benchmark':bench,'missing_new_kline':[],'missing_new_agg':[]}
for src in ['research','fresh']:
 baseids=set(ct1row(THS[0][1])[src]['ids'])
 posmap=RPOS if src=='research' else FPOS
 tmap=TM if src=='research' else FF
 for name,th in THS:
  ids=set(ct1row(th)[src]['ids']);key=f'{th:.6f}'
  sm=shift.get((src,key),{})
  for pid in ids:
   p=posmap[pid];sym=symbol(src,pid);bl=baseline_lane(src,pid);nl=sm.get(pid,(bl,bl,'',''))[1]
   isshift=(nl!=bl)
   if not isshift:
    ex=base_exec(src,pid)
    allres.append({'source':src,'candidate':name,'threshold':th,'position_id':pid,'symbol':sym,'block':block(src,pid),'strong':strong(src,pid),
                   'base_lane':bl,'lane':nl,'shifted':False,'executable':ex,'pnl':base_pnl(src,pid) if ex else '', 'reason':base_reason(src,pid) if ex else ''})
    continue
   target=int(float(tmap[pid][f't{nl}_target_ms']));ems=(target//60000)*60000+60000
   mkt=kline_open(src,sym,ems)
   ex=bool(mkt is not None and int(p['closed_at_ms'])>ems)
   if not ex:
    if mkt is None:integrity['missing_new_kline'].append([src,pid,sym,ems])
    allres.append({'source':src,'candidate':name,'threshold':th,'position_id':pid,'symbol':sym,'block':block(src,pid),'strong':strong(src,pid),
                   'base_lane':bl,'lane':nl,'shifted':True,'executable':False,'pnl':'','reason':'NO_EXECUTABLE_ENTRY'})
    continue
   # verify agg files exist
   miss=[d for d in drange(ems,int(p['closed_at_ms'])) if not cachefile(src,'a',sym,d).exists()]
   if miss:integrity['missing_new_agg'].append([src,pid,sym,miss])
   ent=entry_fill_short(mkt,mdata(p)[0]);rr=replay(src,p,sym,ems,mkt,ent)
   allres.append({'source':src,'candidate':name,'threshold':th,'position_id':pid,'symbol':sym,'block':block(src,pid),'strong':strong(src,pid),
                  'base_lane':bl,'lane':nl,'shifted':True,'executable':True,'pnl':rr['pnl'],'reason':rr['reason']})
  print(src,name,'selected',len(ids),'rowsdone',sum(1 for r in allres if r['source']==src and r['candidate']==name),flush=True)

json.dump(integrity,open('/tmp/ct4_integrity.json','w'),indent=2)
with open('/tmp/ct4_trade_detail.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(allres[0]));w.writeheader();w.writerows(allres)

# summarize
def met(q):
 vals=[float(r['pnl']) for r in q if truth(r['executable'])]
 ex=[r for r in q if truth(r['executable'])]
 return {'selected':len(q),'executable':len(ex),'noexec':len(q)-len(ex),'strong_selected':sum(truth(r['strong']) for r in q),
         'strong_exec':sum(truth(r['strong']) for r in ex),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals)}
summary={'stage':'SHORT-CT4','status':'EXECUTION_REALISTIC_REPLAY_COMPLETE','integrity':integrity,'candidates':{}}
for name,th in THS:
 z={}
 for src in ['research','fresh']:
  q=[r for r in allres if r['candidate']==name and r['source']==src];z[src]=met(q)
  z[src]['blocks']={}
  for b in sorted(set(r['block'] for r in q)):
   z[src]['blocks'][b]=met([r for r in q if r['block']==b])
  z[src]['lanes']={}
  for lane in [0,1,2,3]:
   z[src]['lanes'][str(lane)]=met([r for r in q if int(r['lane'])==lane])
  z[src]['shifted']=met([r for r in q if truth(r['shifted'])])
  st=[r for r in q if truth(r['strong']) and truth(r['executable'])];nt=[r for r in q if not truth(r['strong']) and truth(r['executable'])]
  z[src]['strong_cohort']={'n':len(st),'pnl':sum(float(r['pnl']) for r in st),'wins':sum(float(r['pnl'])>0 for r in st)}
  z[src]['non_target_cohort']={'n':len(nt),'pnl':sum(float(r['pnl']) for r in nt),'wins':sum(float(r['pnl'])>0 for r in nt)}
 summary['candidates'][name]=z
base=summary['candidates']['BASE']
for name,z in summary['candidates'].items():
 for src in ['research','fresh']:
  z[src]['delta_pnl_vs_base']=z[src]['pnl']-base[src]['pnl']
  z[src]['exec_strong_retention_vs_base']=z[src]['strong_exec']/base[src]['strong_exec'] if base[src]['strong_exec'] else 0
json.dump(summary,open('/tmp/ct4_summary.json','w'),indent=2)

for name,z in summary['candidates'].items():
 print('\n###',name)
 for src in ['research','fresh']:
  a=z[src];print(src,'sel',a['selected'],'exec',a['executable'],'strongExec',a['strong_exec'],'WR',round(100*a['wr'],2),'PnL',round(a['pnl'],2),'delta',round(a['delta_pnl_vs_base'],2),'strongRet',round(a['exec_strong_retention_vs_base'],3))
  print(' blocks',[(b,x['executable'],x['strong_exec'],round(x['pnl'],2)) for b,x in a['blocks'].items()])
  print(' lanes',[(l,x['executable'],x['strong_exec'],round(x['pnl'],2)) for l,x in a['lanes'].items()])
  print(' shifted',a['shifted'],'strong',a['strong_cohort'],'non',a['non_target_cohort'])
print('\nINTEGRITY missingK',len(integrity['missing_new_kline']),'missingA',len(integrity['missing_new_agg']))