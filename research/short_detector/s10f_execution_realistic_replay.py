from __future__ import annotations
import csv,io,json,math,statistics,zipfile,requests,time,os,tempfile
from collections import defaultdict,Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path('/tmp/s10f')
S8=list(csv.DictReader(open(ROOT/'research/short_detector/results/sds8_unified_655_detail.csv')))
BY={r['position_id']:r for r in S8}
F0={r['meta_position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv'))}
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
DB=json.load(open('/tmp/s10f_db364.json')); POS=DB['positions']; ORDERS=DB['orders']
OUT=Path('/tmp/s10f_out');OUT.mkdir(exist_ok=True)
TH=.0338983050847; EPS=1e-12

def B(v):return str(v).lower()=='true'
def ff(v,default=None):
    try:
        x=float(v);return x if math.isfinite(x) else default
    except:return default
def causal(pid,h):
    try:return int(TM[pid]['primary_label_end_ms'])>int(TM[pid][f't{h}_target_ms'])
    except:return False
def side_ret(entry_fill,px):return 100.0*(entry_fill/px-1.0)
def entry_fill_short(mkt,slip):return mkt*(1.0-slip/10000.0)
def exit_fill_short(mkt,slip):return mkt*(1.0+slip/10000.0)
def date_range(a,b):
    a=datetime.fromtimestamp(a/1000,timezone.utc).date();b=datetime.fromtimestamp(b/1000,timezone.utc).date();o=[];d=a
    while d<=b:o.append(d.isoformat());d+=timedelta(days=1)
    return o
def datestr(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).date().isoformat()

def s10a_h(pid):
    r=BY[pid]
    if r['router_lane']!='1':return None
    for h in (1,2,3):
        v=ff(TM[pid].get(f't{h}_confirm_side_return_pct'))
        if causal(pid,h) and v is not None and v>=TH:return h
    return None
def c_h(pid):
    r=BY[pid]
    if r['router_lane']!='0':return None
    try:
        if causal(pid,2) and float(TM[pid]['t2_delta_f_coin_minus_market_15m'])>=0.032030968083884837:return 2
    except:pass
    try:
        if causal(pid,3) and float(TM[pid]['t3_f_micro_decay_3_vs_prev3'])<=0.2779031656624853:return 3
    except:pass
    return None
def band(pid,f,lo,hi):
    try:v=float(F0[pid][f]);return lo<=v<=hi
    except:return False
def ge(pid,f,t):
    try:return float(F0[pid][f])>=t
    except:return False
def fast(pid):
    r=BY[pid]
    if r['router_lane']!='1':return False
    return (band(pid,'f_new_volume_over_range',1.0170781185420166,1.060973255243714) or
            ge(pid,'f_new_momentum_curvature',1.2636050833333325) or
            band(pid,'f_new_accel_15_vs_60',0.6594,1.7240119999999999) or
            band(pid,'f_context_breakdown_down_pct',0.42735,0.446816) or
            band(pid,'f_f_oi_accel_x_overheat',-0.29188090961795327,-0.23281000377161334) or
            band(pid,'f_f_coin_minus_market_30m',0.6909331187969325,0.7639814635249487))
def alt(pid):
    r=BY[pid]
    if r['router_lane']!='1' or not causal(pid,3):return False
    try:return float(TM[pid]['t3_delta_micro_selected_vwap_extension_20'])>=0.0024105131797624857
    except:return False
def s10c_sel(pid):return s10a_h(pid) is not None or c_h(pid) is not None
def s10d_sel(pid):
    base=s10c_sel(pid)
    return base or fast(pid) or (BY[pid]['router_lane']=='1' and not (s10a_h(pid) is not None) and not fast(pid) and alt(pid))
def s10e_veto(pid):return band(pid,'f_new_overheat_pressure',4.0018436068809455,4.470349182901625)
def max_veto(pid):return band(pid,'f_f_oi_change_30m_pct',-0.1138785521420882,0.03292073490364089)

ids364=[pid for pid in BY if s10d_sel(pid)]
cands={
 'S10C':set(pid for pid in ids364 if s10c_sel(pid)),
 'S10D':set(ids364),
 'S10E':set(pid for pid in ids364 if not s10e_veto(pid)),
 'MAX_PRUNE':set(pid for pid in ids364 if not max_veto(pid)),
}
expect={'S10C':(329,70),'S10D':(364,85),'S10E':(331,83),'MAX_PRUNE':(310,81)}
for k,s in cands.items():
    got=(len(s),sum(B(BY[p]['strong_win']) for p in s))
    print('CAND',k,got,flush=True);assert got==expect[k],(k,got)

# candidate-specific entry plans. S10C cannot use fast override; S10D-derived candidates do.
def plan_s10c(pid):
    h=s10a_h(pid)
    if h is None:h=c_h(pid)
    assert h in (1,2,3)
    return ('TEMP',h,int(TM[pid][f't{h}_target_ms']))
def plan_s10d(pid):
    if fast(pid):return ('T0',0,int(POS[pid]['opened_at_ms']))
    if s10c_sel(pid):return plan_s10c(pid)
    assert alt(pid)
    return ('TEMP',3,int(TM[pid]['t3_target_ms']))

plans={}
for cand,s in cands.items():
    for pid in s:
        pl=plan_s10c(pid) if cand=='S10C' else plan_s10d(pid)
        plans[(cand,pid)]=pl

# dedup scenario entry configurations
scenario_defs={}
for (cand,pid),pl in plans.items():
    kind,h,target=pl
    sig=(pid,kind,h,target)
    scenario_defs[sig]={'pid':pid,'kind':kind,'h':h,'target_ms':target}

# metadata
meta={}
for pid in ids364:
    p=POS[pid];md=json.loads(p.get('raw_json') or '{}')
    slip=ff(md.get('slippage_bps'),2.0);fee=ff(md.get('fee_rate'),.00075);notional=ff(md.get('initial_notional_usdt'),500.0)
    oldentry=float(p['entry_price'])
    meta[pid]={'symbol':BY[pid]['symbol'],'split':BY[pid]['split'],'strong':B(BY[pid]['strong_win']),
               'open_ms':int(p['opened_at_ms']),'close_ms':int(p['closed_at_ms']),'old_entry_fill':oldentry,
               'slip':slip,'fee':fee,'notional':notional}

# kline targets for TEMP scenarios
byk=defaultdict(list)
for sig,sc in scenario_defs.items():
    if sc['kind']=='T0':continue
    entry_ms=(sc['target_ms']//60000)*60000+60000
    sc['entry_ms']=entry_ms
    byk[(meta[sc['pid']]['symbol'],datestr(entry_ms))].append(sig)

tls=__import__('threading').local()
def sess():
    if not hasattr(tls,'s'):
        tls.s=requests.Session();tls.s.headers.update({'User-Agent':'MarketDetector-S10F/1.0'})
    return tls.s
def fetch(url,retries=3):
    last=None
    for a in range(retries):
        try:
            rr=sess().get(url,timeout=(15,120));rr.raise_for_status();return rr.content
        except Exception as e:
            last=e;time.sleep(1.2*(a+1))
    raise RuntimeError(f'{url}: {last}')

def kproc(item):
    (sym,d),sigs=item
    raw=fetch(f'https://data.binance.vision/data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{d}.zip')
    targets=defaultdict(list)
    for sig in sigs:targets[scenario_defs[sig]['entry_ms']].append(sig)
    found={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open(z.namelist()[0]) as f:
            for x in csv.reader(io.TextIOWrapper(f,encoding='utf-8')):
                try:ts=int(x[0]);op=float(x[1])
                except:continue
                if ts in targets:
                    for sig in targets[ts]:found[sig]=op
    return sigs,found
kerr=[];done=0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(kproc,x) for x in byk.items()]
    for fu in as_completed(futs):
        try:
            sigs,found=fu.result()
            for sig in sigs:
                if sig in found:scenario_defs[sig]['entry_market']=found[sig]
        except Exception as e:kerr.append(str(e))
        done+=1
        if done%25==0 or done==len(futs):print('KLINE',done,'/',len(futs),'err',len(kerr),flush=True)
if kerr:raise RuntimeError(kerr[:3])

# finalize scenario entries
for sig,sc in scenario_defs.items():
    m=meta[sc['pid']]
    if sc['kind']=='T0':
        sc['entry_ms']=m['open_ms'];sc['entry_fill']=m['old_entry_fill']
        sc['entry_market']=m['old_entry_fill']/(1.0-m['slip']/10000.0)
        sc['executable']=m['close_ms']>m['open_ms'];sc['noexec']='' if sc['executable'] else 'HIST_CLOSED_AT_OPEN'
    else:
        if 'entry_market' not in sc:
            sc['executable']=False;sc['noexec']='KLINE_MISSING';continue
        if m['close_ms']<=sc['entry_ms']:
            sc['executable']=False;sc['noexec']='HIST_CLOSED_BEFORE_DELAYED_ENTRY';continue
        sc['entry_fill']=entry_fill_short(sc['entry_market'],m['slip']);sc['executable']=True;sc['noexec']=''
    if sc['executable']:
        sc['qty']=m['notional']/sc['entry_fill'];sc['entry_fee']=m['notional']*m['fee']

# raw agg paths from original open -> close, once per pid
rawpaths={pid:[] for pid in ids364};bya=defaultdict(list)
for pid in ids364:
    m=meta[pid]
    for d in date_range(m['open_ms'],m['close_ms']):bya[(m['symbol'],d)].append(pid)
def aproc(item):
    (sym,d),pids=item
    raw=fetch(f'https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip')
    loc={p:[] for p in pids};wins={p:(meta[p]['open_ms'],meta[p]['close_ms']) for p in pids}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open(z.namelist()[0]) as f:
            for x in csv.reader(io.TextIOWrapper(f,encoding='utf-8')):
                try:px=float(x[1]);ts=int(x[5])
                except:continue
                for p,(a,b) in wins.items():
                    if a<=ts<=b:loc[p].append((ts,px))
    return loc
aerr=[];done=0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs=[ex.submit(aproc,x) for x in bya.items()]
    for fu in as_completed(futs):
        try:
            loc=fu.result()
            for p,a in loc.items():rawpaths[p].extend(a)
        except Exception as e:aerr.append(str(e))
        done+=1
        if done%25==0 or done==len(futs):print('AGG',done,'/',len(futs),'err',len(aerr),flush=True)
if aerr:raise RuntimeError(aerr[:3])
for p in rawpaths:rawpaths[p].sort(key=lambda x:x[0])

def realized(sc,mkt,qty=None,ef=None):
    m=meta[sc['pid']];q=sc['qty'] if qty is None else qty;ef=sc['entry_fee'] if ef is None else ef
    fill=exit_fill_short(mkt,m['slip']);exitfee=q*fill*m['fee'];gross=q*(sc['entry_fill']-fill)
    usd=gross-ef-exitfee;return usd,100*usd/m['notional']
def scenepath(sc):
    return [(t,p) for t,p in rawpaths[sc['pid']] if t>=sc['entry_ms']]
def samples(sc,tr):
    end=meta[sc['pid']]['close_ms'];n=sc['entry_ms']+5000;last=sc['entry_market'];o=[]
    for ts,px in tr:
        while n<ts and n<=end:o.append((n,last,side_ret(sc['entry_fill'],last)));n+=5000
        last=px
        while n==ts and n<=end:o.append((n,last,side_ret(sc['entry_fill'],last)));n+=5000
    while n<=end:o.append((n,last,side_ret(sc['entry_fill'],last)));n+=5000
    return o
def hold(sc,tr):
    fm=tr[-1][1] if tr else sc['entry_market'];u,p=realized(sc,fm);return {'usd':u,'pct':p,'active':False,'reason':'HIST_TIME_FALLBACK'}
def v43(sc,tr,samp):
    peak=-999.;runner=False;rc=0
    for ts,px,pnl in samp:
        peak=max(peak,pnl)
        if not runner and peak>=1.5:runner=True
        if runner:
            rc=rc+1 if pnl<=peak*.90 else 0
            if rc>=2:
                u,p=realized(sc,px);return {'usd':u,'pct':p,'active':True,'reason':'RUNNER_CLOSE'}
            continue
        if peak>=.5 and pnl<=peak*.75:
            u,p=realized(sc,px);return {'usd':u,'pct':p,'active':True,'reason':'FULL_CLOSE_050'}
    return hold(sc,tr)
def be10(sc,tr):
    touched=False;armed=False
    for ts,px in tr:
        gp=side_ret(sc['entry_fill'],px);net=realized(sc,px)[1]
        if gp>=.10:touched=True
        if touched and net>=0 and not armed:armed=True;continue
        if armed and net<=0:
            u,p=realized(sc,px);return {'usd':u,'pct':p,'active':True,'reason':'BE0.10'}
    return hold(sc,tr)

sim={}
for sig,sc in scenario_defs.items():
    if not sc['executable']:continue
    tr=scenepath(sc);sa=samples(sc,tr);h=hold(sc,tr);v=v43(sc,tr,sa);b=be10(sc,tr);c=v if v['active'] else b
    px=[sc['entry_market']]+[p for _,p in tr];rets=[side_ret(sc['entry_fill'],p) for p in px]
    sim[sig]={'hold':h,'v43':v,'comp':c,'mfe':max(rets),'mae':min(rets),'prints':len(tr),'samples':len(sa)}

def get_sig(cand,pid):
    pl=plans[(cand,pid)];return (pid,pl[0],pl[1],pl[2])
def met(cand,pids,key='comp'):
    vals=[];execp=[];no=[];strongexec=0
    for p in pids:
        sig=get_sig(cand,p);sc=scenario_defs[sig]
        if not sc['executable']:no.append(p);continue
        execp.append(p);strongexec+=meta[p]['strong'];vals.append(sim[sig][key]['usd'])
    n=len(execp);wins=sum(v>0 for v in vals)
    return {'selected_n':len(pids),'executable_n':n,'noexec_n':len(no),'noexec_strong_n':sum(meta[p]['strong'] for p in no),
            'strong_selected_n':sum(meta[p]['strong'] for p in pids),'strong_executable_n':strongexec,'non_target_executable_n':n-strongexec,
            'wins':wins,'wr':wins/n if n else 0,'pnl':sum(vals),'gp':sum(v for v in vals if v>0),'gl':sum(v for v in vals if v<0)}
def anatomy(cand,pids):
    vals=[];sv=[];nv=[];entries=Counter()
    for p in pids:
        sig=get_sig(cand,p);sc=scenario_defs[sig]
        entries['T0' if sc['kind']=='T0' else f"T+{sc['h']}"]+=1
        if not sc['executable']:continue
        d=sim[sig];vals.append(d['mfe']);(sv if meta[p]['strong'] else nv).append(d['mfe'])
    def a(x):
        return {'n':len(x),'median':statistics.median(x) if x else None,'mean':statistics.mean(x) if x else None,'ge0p5':sum(v>=.5 for v in x),'ge1p0':sum(v>=1 for v in x)}
    return {'entry_methods':dict(entries),'all_mfe':a(vals),'strong_mfe':a(sv),'non_target_mfe':a(nv)}

summary={'stage':'SHORT-S10F','status':'COMPLETE_EXECUTION_REALISTIC_FRONTIER','market_data':{'kline_pairs':len(byk),'agg_pairs':len(bya),'kline_errors':kerr,'agg_errors':aerr},'candidates':{}}
detail=[]
for cand,pids in cands.items():
    cs={'hold':met(cand,pids,'hold'),'v43':met(cand,pids,'v43'),'comp':met(cand,pids,'comp'),'anatomy':anatomy(cand,pids),'splits':{}}
    for sp in ['Discovery','Validation','Reserve']:
        q=set(p for p in pids if meta[p]['split']==sp)
        cs['splits'][sp]={'hold':met(cand,q,'hold'),'v43':met(cand,q,'v43'),'comp':met(cand,q,'comp')}
    summary['candidates'][cand]=cs
    for p in sorted(pids):
        sig=get_sig(cand,p);sc=scenario_defs[sig]
        row={'candidate':cand,'position_id':p,'symbol':meta[p]['symbol'],'split':meta[p]['split'],'strong_win':meta[p]['strong'],
             'entry_kind':sc['kind'],'entry_horizon':sc['h'],'entry_target_ms':sc['target_ms'],'entry_ms':sc.get('entry_ms'),
             'entry_market':sc.get('entry_market'),'entry_fill':sc.get('entry_fill'),'executable':sc['executable'],'noexec_reason':sc['noexec']}
        if sc['executable']:
            d=sim[sig];row.update({'delayed_mfe_pct':d['mfe'],'delayed_mae_pct':d['mae'],'trade_prints':d['prints'],
                'HOLD_pnl':d['hold']['usd'],'V43_pnl':d['v43']['usd'],'V43_reason':d['v43']['reason'],
                'COMP_pnl':d['comp']['usd'],'COMP_reason':d['comp']['reason']})
        detail.append(row)
(OUT/'s10f_summary.json').write_text(json.dumps(summary,indent=2))
fields=[]
for r in detail:
    for k in r:
        if k not in fields:fields.append(k)
with open(OUT/'s10f_trade_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(detail)
print(json.dumps(summary,indent=2),flush=True)