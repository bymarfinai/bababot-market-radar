from __future__ import annotations
import csv,json,math,requests,zipfile,io,time,gc
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from pathlib import Path
from collections import Counter,defaultdict

POS={str(x['position_id']):x for x in json.load(open('/tmp/s10j5_positions.json'))}
FUN=[r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv')) if r['_d']=='True']
FEAT={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv')) if r['source']=='fresh'}
assert len(POS)==len(FUN)==len(VETO)==807

CACHE=Path('/tmp/s10j5_archive'); CACHE.mkdir(exist_ok=True)
OUT=Path('/tmp/s10j5_out'); OUT.mkdir(exist_ok=True)

def dtdate(ms): return datetime.fromtimestamp(int(ms)/1000,timezone.utc).date().isoformat()
def drange(a,b):
    d=datetime.fromtimestamp(int(a)/1000,timezone.utc).date()
    e=datetime.fromtimestamp(int(b)/1000,timezone.utc).date(); out=[]
    while d<=e:
        out.append(d.isoformat()); d+=timedelta(days=1)
    return out
def cp(kind,sym,d): return CACHE/f'{kind}__{sym.replace("/","_")}__{d}.json'
tls=__import__('threading').local()
def sess():
    if not hasattr(tls,'s'):
        tls.s=requests.Session(); tls.s.headers.update({'User-Agent':'S10J5/1.0'})
    return tls.s
def fetch(url):
    last=None
    for a in range(5):
        try:
            r=sess().get(url,timeout=(15,120))
            if r.status_code==404:return None
            r.raise_for_status(); return r.content
        except Exception as e:
            last=e; time.sleep(a+1)
    raise RuntimeError(f'{url}: {last}')
def dl_k(item):
    sym,d=item; p=cp('k',sym,d)
    if p.exists(): return item,True,None
    raw=fetch(f'https://data.binance.vision/data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{d}.zip')
    if raw is None:return item,False,'404'
    z=zipfile.ZipFile(io.BytesIO(raw)); rows=[]
    with z.open(z.namelist()[0]) as f:
        for x in csv.reader(io.TextIOWrapper(f)):
            try:int(x[0])
            except:continue
            rows.append(x)
    p.write_text(json.dumps(rows,separators=(',',':'))); return item,True,None
def dl_a(item):
    sym,d=item; p=cp('a',sym,d)
    if p.exists(): return item,True,None
    raw=fetch(f'https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip')
    if raw is None:return item,False,'404'
    z=zipfile.ZipFile(io.BytesIO(raw)); rows=[]
    with z.open(z.namelist()[0]) as f:
        for x in csv.reader(io.TextIOWrapper(f)):
            try: rows.append([int(x[5]),float(x[1])])
            except: continue
    p.write_text(json.dumps(rows,separators=(',',':'))); return item,True,None
def dl_all(items,fn,label,workers=10):
    miss=[];err=[];done=0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut=[ex.submit(fn,x) for x in sorted(items)]
        for fu in as_completed(fut):
            try:
                item,ok,e=fu.result()
                if not ok:miss.append(item)
            except Exception as e:err.append(str(e))
            done+=1
            if done%100==0 or done==len(items):
                print(label,done,'/',len(items),'miss',len(miss),'err',len(err),flush=True)
    if err:raise RuntimeError(err[:3])
    return miss

# build exact execution plans
reqk=set()
for r in FUN:
    lane=int(r['_lane'])
    if lane>0:
        pid=r['meta_position_id']; target=int(float(FEAT[pid][f't{lane}_target_ms']))
        ems=(target//60000)*60000+60000
        reqk.add((POS[pid]['symbol'],dtdate(ems)))
print('KLINE_REQ',len(reqk),flush=True)
missk=dl_all(reqk,dl_k,'KLINE')

def kline_open(sym,ms):
    p=cp('k',sym,dtdate(ms))
    if not p.exists():return None
    for x in json.loads(p.read_text()):
        try:
            if int(x[0])==int(ms):return float(x[1])
        except:pass
    return None
def rawj(p):
    x=p.get('raw_json')
    if isinstance(x,str):
        try:return json.loads(x or '{}')
        except:return {}
    return x or {}
def entry_fill_short(mkt,slip):return mkt*(1-slip/10000.0)

plans={}
for r in FUN:
    pid=r['meta_position_id']; p=POS[pid]; lane=int(r['_lane']); raw=rawj(p)
    slip=float(raw.get('slippage_bps',2.0))
    if lane==0:
        mkt=float(raw.get('entry_market_price') or p['entry_price'])
        plans[pid]={'lane':0,'entry_ms':int(p['opened_at_ms']),'entry_market':mkt,'entry_fill':float(p['entry_price']),'executable':True}
    else:
        target=int(float(FEAT[pid][f't{lane}_target_ms']))
        ems=(target//60000)*60000+60000
        mkt=kline_open(p['symbol'],ems)
        ex=bool(mkt is not None and int(p['closed_at_ms'])>ems)
        pl={'lane':lane,'target_ms':target,'entry_ms':ems,'entry_market':mkt,'executable':ex}
        if mkt is not None:pl['entry_fill']=entry_fill_short(mkt,slip)
        plans[pid]=pl

exrows=[r for r in FUN if plans[r['meta_position_id']]['executable']]
print('PLAN selected',len(FUN),'exec',len(exrows),'noexec',len(FUN)-len(exrows),'strong_exec',sum(r['strong_win']=='True' for r in exrows),'lanes',Counter(plans[r['meta_position_id']]['lane'] for r in exrows),flush=True)

reqa=set()
for r in exrows:
    pid=r['meta_position_id'];p=POS[pid];pl=plans[pid]
    for d in drange(pl['entry_ms'],int(p['closed_at_ms'])): reqa.add((p['symbol'],d))
print('AGG_REQ',len(reqa),flush=True)
missa=dl_all(reqa,dl_a,'AGG',workers=8)

def load_path(pid):
    p=POS[pid]; pl=plans[pid]; start=pl['entry_ms']; end=int(p['closed_at_ms']); out=[]
    for d in drange(start,end):
        f=cp('a',p['symbol'],d)
        if not f.exists():continue
        rows=json.loads(f.read_text())
        out.extend((int(x[0]),float(x[1])) for x in rows if start<=int(x[0])<=end)
        del rows; gc.collect()
    out.sort(key=lambda x:x[0]); return out
def side_ret(entry,px): return 100.0*(entry/px-1.0)
def exit_fill_short(mkt,slip):return mkt*(1+slip/10000.0)
def mdata(pid):
    p=POS[pid];raw=rawj(p)
    return float(raw.get('slippage_bps',2.0)),float(raw.get('fee_rate',.00075)),float(raw.get('initial_notional_usdt',500.0))
def calc(pid,mkt):
    pl=plans[pid];sl,fee,notional=mdata(pid)
    q=notional/pl['entry_fill']; ef=notional*fee
    fill=exit_fill_short(mkt,sl); xf=q*fill*fee
    gross=q*(pl['entry_fill']-fill); usd=gross-ef-xf
    return usd,100*usd/notional
def samples(pid,tr):
    pl=plans[pid]; end=int(POS[pid]['closed_at_ms']); n=pl['entry_ms']+5000; last=pl['entry_market'];o=[]
    for ts,px in tr:
        while n<ts and n<=end:
            o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
        last=px
        while n==ts and n<=end:
            o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
    while n<=end:
        o.append((n,last,side_ret(pl['entry_fill'],last)));n+=5000
    return o
def hold(pid,tr):
    mkt=tr[-1][1] if tr else plans[pid]['entry_market']
    return {'usd':calc(pid,mkt)[0],'active':False,'reason':'HIST_TIME_FALLBACK'}
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
    pl=plans[pid];touched=False;armed=False;_,_,notional=mdata(pid)
    for ts,px in tr:
        gp=side_ret(pl['entry_fill'],px);net=100*calc(pid,px)[0]/notional
        if gp>=.10:touched=True
        if touched and net>=0 and not armed:
            armed=True;continue
        if armed and net<=0:return {'usd':calc(pid,px)[0],'active':True,'reason':'BE0.10'}
    return hold(pid,tr)

rec=[]
for i,r in enumerate(exrows,1):
    pid=r['meta_position_id'];tr=load_path(pid);sa=samples(pid,tr);h=hold(pid,tr);v=v43(pid,tr,sa);b=be10(pid,tr);c=v if v['active'] else b
    vm=VETO[pid]
    rec.append({
        'position_id':pid,'symbol':POS[pid]['symbol'],'strong':r['strong_win']=='True','lane':int(r['_lane']),
        'block':vm['block'],'primary_veto':vm['primary_veto']=='True','conservative_veto':vm['conservative_veto']=='True','challenger_t2_veto':vm['challenger_t2_veto']=='True',
        'hold':h['usd'],'v43':v['usd'],'comp':c['usd'],'reason':c['reason'],'actual_old_pnl':float(POS[pid].get('realized_pnl') or 0)})
    del tr,sa;gc.collect()
    if i%100==0 or i==len(exrows):print('REPLAY',i,'/',len(exrows),flush=True)

with open(OUT/'fresh_s10d_replay.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rec[0]));w.writeheader();w.writerows(rec)
json.dump({'kline_missing':missk,'agg_missing':missa,'selected':len(FUN),'executable':len(exrows)},open(OUT/'integrity.json','w'),indent=2)
print('DONE',len(rec),flush=True)