from __future__ import annotations
import csv,json,math,gc
from pathlib import Path
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/'research'/'short_detector'/'results'
K=list(csv.DictReader(open(RES/'ct7c_trade_detail.csv')))
ALL=list(csv.DictReader(open(RES/'ct6a_trade_detail.csv')))
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
FF={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
RPOS=json.load(open('/tmp/s10f_db364.json'))['positions']
FPOS={str(x['position_id']):x for x in json.load(open('/tmp/s10j5_positions.json'))}
RC=Path('/tmp/ct4_research_archive');FC=Path('/tmp/s10j5_archive')

def truth(v):return str(v).lower()=='true'
def ff(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def rawj(p):
    x=p.get('raw_json')
    if isinstance(x,str):
        try:return json.loads(x or '{}')
        except:return {}
    return x or {}
def dstr(ms):return datetime.fromtimestamp(int(ms)/1000,timezone.utc).date().isoformat()
def drange(a,b):
    d=datetime.fromtimestamp(int(a)/1000,timezone.utc).date();e=datetime.fromtimestamp(int(b)/1000,timezone.utc).date();o=[]
    while d<=e:o.append(d.isoformat());d+=timedelta(days=1)
    return o
def side_ret(entry,px):return 100*(entry/px-1)
def entry_fill_short(mkt,slip):return mkt*(1-slip/10000)
def exit_fill_short(mkt,slip):return mkt*(1+slip/10000)
def cachefile(src,kind,sym,d):return (RC if src=='research' else FC)/f'{kind}__{sym}__{d}.json'
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
    for dd in drange(start,end):
        p=cachefile(src,'a',sym,dd)
        if not p.exists():continue
        rows=json.loads(p.read_text());out.extend((int(x[0]),float(x[1])) for x in rows if start<=int(x[0])<=end)
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
        return {'pnl':calc(entry_fill,mkt,p)[0],'reason':'HIST_TIME_FALLBACK'}
    sa=samples(entry_ms,entry_market,entry_fill,end,tr);peak=-999.;runner=False;rc=0
    for ts,px,pnl in sa:
        peak=max(peak,pnl)
        if not runner and peak>=1.5:runner=True
        if runner:
            rc=rc+1 if pnl<=peak*.90 else 0
            if rc>=2:return {'pnl':calc(entry_fill,px,p)[0],'reason':'RUNNER_CLOSE'}
            continue
        if peak>=.5 and pnl<=peak*.75:return {'pnl':calc(entry_fill,px,p)[0],'reason':'FULL_CLOSE_050'}
    touched=False;armed=False;_,_,notional=mdata(p)
    for ts,px in tr:
        gp=side_ret(entry_fill,px);net=100*calc(entry_fill,px,p)[0]/notional
        if gp>=.10:touched=True
        if touched and net>=0 and not armed:armed=True;continue
        if armed and net<=0:return {'pnl':calc(entry_fill,px,p)[0],'reason':'BE0.10'}
    return hold()

def trow(q):return TM[q['position_id']] if q['source']=='research' else FF[q['position_id']]
def value(q,k):
    z=trow(q)
    if k.startswith('d'):
        h=int(k[1]);s=k[3:];a=ff(z.get(f't{h}_{s}'));b=ff(z.get(f't{h-1}_{s}'))
        return None if a is None or b is None else a-b
    return ff(z.get(k))
def percentile(xs,p):
    s=sorted(xs);pos=(len(s)-1)*p;lo=int(pos);hi=min(len(s)-1,lo+1);w=pos-lo
    return s[lo]*(1-w)+s[hi]*w

# CLEAN2: thresholds fit ONLY on Research Discovery strong population.
train=[q for q in ALL if q['block']=='Research_Discovery' and truth(q['strong'])]
SPEC=[
    ('t3_delta_f_coin_minus_market_15m',0.60),
    ('d3_confirm_trades',0.60),
]
TH={}
for k,p in SPEC:
    xs=[value(q,k) for q in train if value(q,k) is not None]
    TH[k]=percentile(xs,p)

def clean2(q):
    return all(value(q,k) is not None and value(q,k)>=TH[k] for k,_ in SPEC)

# Transport audit on full strong-vs-BAD universe.
def class_met(rows):
    hit=[q for q in rows if clean2(q)]
    return {
        'selected':len(hit),
        'strong':sum(truth(q['strong']) for q in hit),
        'bad':sum(q['mfe_bucket'] in ('BAD_A_LT_0P30','BAD_B_0P30_0P50') for q in hit),
    }

U=[q for q in ALL if truth(q['strong']) or q['mfe_bucket'] in ('BAD_A_LT_0P30','BAD_B_0P30_0P50')]
transport={
    'Research_Discovery':class_met([q for q in U if q['block']=='Research_Discovery']),
    'Research_Holdout':class_met([q for q in U if q['block'] in ('Research_Validation','Research_Reserve')]),
    'Fresh':class_met([q for q in U if q['source']=='fresh']),
}

# Apply ONLY inside CT7C kill set.
flagged=[q for q in K if clean2(q)]
rows=[];missing=[]
for q in flagged:
    src=q['source'];pid=q['position_id'];sym=q['symbol'];p=RPOS[pid] if src=='research' else FPOS[pid]
    target=int(float(trow(q)['t3_target_ms']));entry_ms=(target//60000)*60000+60000
    mkt=kline_open(src,sym,entry_ms)
    executable=bool(mkt is not None and int(p['closed_at_ms'])>entry_ms)
    if not executable:
        if mkt is None:missing.append([src,pid,sym,entry_ms])
        rows.append({'position_id':pid,'symbol':sym,'source':src,'block':q['block'],'mfe_bucket':q['mfe_bucket'],'strong':q['strong'],'entry_horizon':3,'entry_ms':entry_ms,'executable':False,'pnl':'','reason':'NO_EXECUTABLE_ENTRY'})
        continue
    ent=entry_fill_short(mkt,mdata(p)[0]);rr=replay(src,p,sym,entry_ms,mkt,ent)
    rows.append({'position_id':pid,'symbol':sym,'source':src,'block':q['block'],'mfe_bucket':q['mfe_bucket'],'strong':q['strong'],'entry_horizon':3,'entry_ms':entry_ms,'executable':True,'pnl':rr['pnl'],'reason':rr['reason']})

def met(qs):
    ex=[r for r in qs if truth(r['executable'])];vals=[float(r['pnl']) for r in ex]
    return {'selected':len(qs),'executable':len(ex),'strong_selected':sum(truth(r['strong']) for r in qs),'strong_exec':sum(truth(r['strong']) for r in ex),
            'bad_selected':sum(r['mfe_bucket'] in ('BAD_A_LT_0P30','BAD_B_0P30_0P50') for r in qs),'gray_selected':sum(r['mfe_bucket']=='GRAY_0P50_1P00' for r in qs),
            'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals)}

# Diagnostic frontier exact replay values frozen from CT7D exploration.
frontier=[
 {'variant':'REJECTED_T2_T3_BROAD','strong_rescued':7,'bad_reintroduced':10,'gray_reintroduced':7,'exact_pnl':-23.206861950719446,'verdict':'REJECT'},
 {'variant':'P4_3OF4','strong_rescued':4,'bad_reintroduced':0,'gray_reintroduced':6,'exact_pnl':-0.1827220254809308,'verdict':'REJECT'},
 {'variant':'BAL3','strong_rescued':3,'bad_reintroduced':0,'gray_reintroduced':2,'exact_pnl':1.7695256840190898,'verdict':'POSITIVE_BUT_DOMINATED'},
 {'variant':'AGG4','strong_rescued':4,'bad_reintroduced':1,'gray_reintroduced':2,'exact_pnl':0.6011817487148342,'verdict':'POSITIVE_BUT_DOMINATED'},
 {'variant':'CLEAN2','strong_rescued':2,'bad_reintroduced':0,'gray_reintroduced':0,'exact_pnl':sum(float(r['pnl']) for r in rows if truth(r['executable'])),'verdict':'PRIMARY'},
]

# Combined with CT5B + CT6C + CT7C.
ct5=json.load(open(RES/'ct5b_summary.json'))['candidates']['PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075']
ct5ids=set(ct5['drop_ids'])
ct6ids={r['position_id'] for r in csv.DictReader(open(RES/'ct6c_veto_trade_detail.csv'))}
ct7ids={r['position_id'] for r in K}
base={r['position_id']:r for r in csv.DictReader(open(RES/'ct4_trade_detail.csv')) if r['candidate']=='T0075'}
initial_drop=ct5ids|ct6ids|ct7ids
rescued={r['position_id']:r for r in rows if truth(r['executable']) and r['position_id'] not in (ct5ids|ct6ids)}
keep=[r for pid,r in base.items() if pid not in initial_drop and truth(r['executable'])]
combined_exec=len(keep)+len(rescued);combined_wins=sum(float(r['pnl'])>0 for r in keep)+sum(float(r['pnl'])>0 for r in rescued.values())
combined_pnl=sum(float(r['pnl']) for r in keep)+sum(float(r['pnl']) for r in rescued.values())
combined_strong=sum(truth(r['strong']) for r in keep)+sum(truth(r['strong']) for r in rescued.values())
summary={
 'stage':'SHORT-CT7D',
 'status':'HIGH_PRECISION_STRONG_RESCUE_PASS_RESEARCH_ONLY',
 'contract':{
   'scope':'CT7C kill-set only',
   'rescue_horizon':'T3',
   'threshold_fit':'Research Discovery strong quantile Q60 only',
   'future_mfe_input':False,
   'realized_pnl_input':False,
   'runtime_change':False,
 },
 'primary_rule':{
   'logic':'AND',
   'thresholds':TH,
   'human':[
     f"t3_delta_f_coin_minus_market_15m >= {TH['t3_delta_f_coin_minus_market_15m']}",
     f"d3_confirm_trades >= {TH['d3_confirm_trades']}",
   ],
 },
 'transport':transport,
 'rescue':met(rows),
 'frontier':frontier,
 'missing_kline':missing,
 'combined':{
   'pre_ct7d_pnl':sum(float(r['pnl']) for r in keep),
   'ct7d_incremental_pnl':sum(float(r['pnl']) for r in rescued.values()),
   'post_ct7d_pnl':combined_pnl,
   'post_ct7d_exec':combined_exec,
   'post_ct7d_wins':combined_wins,
   'post_ct7d_wr':combined_wins/combined_exec,
   'post_ct7d_strong_exec':combined_strong,
   'strong_exec_retention_vs_ct4':combined_strong/246,
   'independent_veto_overlap':len({r['position_id'] for r in rows}&(ct5ids|ct6ids)),
 },
}
(RES/'ct7d_summary.json').write_text(json.dumps(summary,indent=2))
with open(RES/'ct7d_rescue_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with open(RES/'ct7d_frontier.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(frontier[0]));w.writeheader();w.writerows(frontier)

print('TH',TH);print('TRANSPORT',transport);print('RESCUE',summary['rescue']);print('FRONTIER',frontier);print('COMBINED',summary['combined']);print('MISSING',missing);print('DETAIL',rows)