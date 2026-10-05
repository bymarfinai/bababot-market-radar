from __future__ import annotations
import csv,json,math,requests,zipfile,io,time,gc
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed

CT2=list(csv.DictReader(open('/tmp/ct2_trade_detail.csv')))
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
FRESH={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
RPOS=json.load(open('/tmp/s10f_db364.json'))['positions']
FPOS={str(x['position_id']):x for x in json.load(open('/tmp/s10j5_positions.json'))}
RBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D'}
FBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv'))}
RSYM={pid:r['symbol'] for pid,r in RBASE.items()}
RC=Path('/tmp/ct4_research_archive');RC.mkdir(exist_ok=True)
FC=Path('/tmp/s10j5_archive')

def dstr(ms):return datetime.fromtimestamp(int(ms)/1000,timezone.utc).date().isoformat()
def drange(a,b):
 d=datetime.fromtimestamp(int(a)/1000,timezone.utc).date();e=datetime.fromtimestamp(int(b)/1000,timezone.utc).date();o=[]
 while d<=e:o.append(d.isoformat());d+=timedelta(days=1)
 return o
def cp(kind,sym,d):return RC/f'{kind}__{sym}__{d}.json'
tls=__import__('threading').local()
def sess():
 if not hasattr(tls,'s'):tls.s=requests.Session();tls.s.headers.update({'User-Agent':'CT4/1.0'})
 return tls.s
def fetch(url):
 last=None
 for a in range(5):
  try:
   r=sess().get(url,timeout=(15,120))
   if r.status_code==404:return None
   r.raise_for_status();return r.content
  except Exception as e:last=e;time.sleep(a+1)
 raise RuntimeError(f'{url}: {last}')
def dl_k(item):
 sym,d=item;p=cp('k',sym,d)
 if p.exists():return item,True
 # reuse fresh cache if same file exists
 fp=FC/f'k__{sym}__{d}.json'
 if fp.exists():p.write_bytes(fp.read_bytes());return item,True
 raw=fetch(f'https://data.binance.vision/data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{d}.zip')
 if raw is None:return item,False
 z=zipfile.ZipFile(io.BytesIO(raw));rows=[]
 with z.open(z.namelist()[0]) as f:
  for x in csv.reader(io.TextIOWrapper(f)):
   try:int(x[0])
   except:continue
   rows.append(x)
 p.write_text(json.dumps(rows,separators=(',',':')));return item,True
def dl_a(item):
 sym,d=item;p=cp('a',sym,d)
 if p.exists():return item,True
 fp=FC/f'a__{sym}__{d}.json'
 if fp.exists():p.write_bytes(fp.read_bytes());return item,True
 raw=fetch(f'https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip')
 if raw is None:return item,False
 z=zipfile.ZipFile(io.BytesIO(raw));rows=[]
 with z.open(z.namelist()[0]) as f:
  for x in csv.reader(io.TextIOWrapper(f)):
   try:rows.append([int(x[5]),float(x[1])])
   except:pass
 p.write_text(json.dumps(rows,separators=(',',':')));return item,True
def run(items,fn,label):
 bad=[];done=0
 with ThreadPoolExecutor(max_workers=8) as ex:
  fut=[ex.submit(fn,x) for x in sorted(items)]
  for fu in as_completed(fut):
   item,ok=fu.result();done+=1
   if not ok:bad.append(item)
   if done%25==0 or done==len(items):print(label,done,'/',len(items),'bad',len(bad),flush=True)
 return bad

# union genuinely lane-shifted research rows. same lane (3->3 source switch) needs no new timing.
q=[r for r in CT2 if r['source']=='research' and r['status']=='SHIFTED' and r['base_lane']!=r['new_lane'] and f"{float(r['threshold']):.6f}" in {'0.050000','0.075000','0.100000'}]
need={}
for r in q:
 pid=r['position_id'];h=int(r['new_lane']);tm=TM[pid];target=int(float(tm[f't{h}_target_ms']));ems=(target//60000)*60000+60000
 p=RPOS[pid];need[(pid,h)]=(ems,int(p['closed_at_ms']),RSYM[pid])
reqk={(sym,dstr(ems)) for ems,end,sym in need.values()}
print('shift keys',len(need),'kline req',len(reqk),flush=True)
badk=run(reqk,dl_k,'KLINE')
def kline_open(sym,ms):
 p=cp('k',sym,dstr(ms))
 if not p.exists():return None
 for x in json.loads(p.read_text()):
  try:
   if int(x[0])==ms:return float(x[1])
  except:pass
 return None
reqa=set()
for (pid,h),(ems,end,sym) in need.items():
 if kline_open(sym,ems) is not None and end>ems:
  for d in drange(ems,end):reqa.add((sym,d))
print('agg req',len(reqa),flush=True)
bada=run(reqa,dl_a,'AGG')
json.dump({'shift_keys':len(need),'kline_req':len(reqk),'kline_bad':badk,'agg_req':len(reqa),'agg_bad':bada},open('/tmp/ct4_market_integrity.json','w'),indent=2)
print('INTEGRITY',json.load(open('/tmp/ct4_market_integrity.json')),flush=True)