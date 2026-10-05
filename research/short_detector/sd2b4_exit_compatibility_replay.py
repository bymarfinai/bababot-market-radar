from __future__ import annotations
import csv, io, json, math, os, statistics, tempfile, zipfile, hashlib, time
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

ROOT=Path('/tmp/sd2b4')
SEL=Path('/tmp/sd2b4_selected128.csv')
POS=Path('/tmp/sd2b4_positions.csv')
OUTDIR=Path('/tmp/sd2b4_out'); OUTDIR.mkdir(parents=True,exist_ok=True)
DETAIL=OUTDIR/'sd2b4_trade_detail.csv'
SUMMARY=OUTDIR/'sd2b4_summary.json'

FEE_RATE=0.00075
SLIP_BPS=2.0
NOTIONAL=500.0
EPS=1e-12

def f(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default

def b(v):
    return str(v).strip().lower() in ('1','true','yes')

def side_ret_short(entry_fill, px):
    return 100.0*(entry_fill/px - 1.0)

def entry_fill_short(market_px, slip_bps):
    return market_px*(1.0-slip_bps/10000.0)

def exit_fill_short(market_px, slip_bps):
    return market_px*(1.0+slip_bps/10000.0)

def realized_piece(entry_fill, exit_market, qty, entry_fee_alloc, fee_rate, slip_bps):
    exit_fill=exit_fill_short(exit_market,slip_bps)
    gross=qty*(entry_fill-exit_fill)
    exit_fee=qty*exit_fill*fee_rate
    return gross-entry_fee_alloc-exit_fee, exit_fill, exit_fee

def date_str(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).date().isoformat()

def date_range(a_ms,b_ms):
    a=datetime.fromtimestamp(a_ms/1000,timezone.utc).date()
    b=datetime.fromtimestamp(b_ms/1000,timezone.utc).date()
    out=[];d=a
    while d<=b:
        out.append(d.isoformat());d+=timedelta(days=1)
    return out

selected=list(csv.DictReader(SEL.open(encoding='utf-8')))
positions={r['position_id']:r for r in csv.DictReader(POS.open(encoding='utf-8'))}
assert len(selected)==128 and len(positions)==128

records={}
for r in selected:
    pid=r['position_id']; p=positions[pid]
    md=json.loads(p['raw_json'] or '{}')
    assert str(p['side']).upper()=='SHORT'
    records[pid]={
      'position_id':pid,'symbol':r['symbol'],'split':r['split'],'strong_win':b(r['strong_win']),
      't3_target_ms':int(r['t3_target_ms']),
      'old_open_ms':int(p['opened_at_ms']),
      'old_close_ms':int(p['closed_at_ms']),
      'old_entry':float(p['entry_price']),'old_exit':float(p['exit_price']),
      'old_realized':float(p['realized_pnl']),
      'old_realized_pct':float(p['realized_pnl_pct']),
      'notional':float(md.get('initial_notional_usdt') or NOTIONAL),
      'fee_rate':float(md.get('fee_rate') or FEE_RATE),
      'slip_bps':float(md.get('slippage_bps') or SLIP_BPS),
      'historical_max_mfe_pct':float(r['historical_max_mfe_pct']),
      'historical_min_mae_pct':float(r['historical_min_mae_pct']),
    }

# ---------- Binance Vision helpers ----------
tls=__import__('threading').local()
def session():
    if not hasattr(tls,'s'):
        s=requests.Session()
        s.headers.update({'User-Agent':'MarketDetector-SD2B4/1.0'})
        tls.s=s
    return tls.s

def fetch_zip_rows(url, parser, retries=3):
    last=None
    for attempt in range(retries):
        tmp=None
        try:
            resp=session().get(url,stream=True,timeout=(15,120))
            resp.raise_for_status()
            fd,tmp=tempfile.mkstemp(prefix='sd2b4_',suffix='.zip',dir='/tmp')
            os.close(fd)
            with open(tmp,'wb') as w:
                for chunk in resp.iter_content(chunk_size=1024*1024):
                    if chunk:w.write(chunk)
            result=parser(tmp)
            os.unlink(tmp)
            return result
        except Exception as e:
            last=e
            if tmp and os.path.exists(tmp):
                try:os.unlink(tmp)
                except:pass
            time.sleep(1.5*(attempt+1))
    raise RuntimeError(f'fetch failed {url}: {last}')

# ---------- Delayed entries from 1m klines ----------
by_kline_pair=defaultdict(list)
for pid,r in records.items():
    target=r['t3_target_ms']
    entry_open=(target//60000)*60000+60000
    r['delayed_entry_open_ms']=entry_open
    by_kline_pair[(r['symbol'],date_str(entry_open))].append(pid)

def process_kline_pair(item):
    (sym,d),pids=item
    url=f'https://data.binance.vision/data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{d}.zip'
    targets={records[pid]['delayed_entry_open_ms']:pid for pid in pids}
    # same symbol/date could theoretically have same minute for multiple pids
    target_multi=defaultdict(list)
    for pid in pids: target_multi[records[pid]['delayed_entry_open_ms']].append(pid)
    def parse(path):
        found={}
        with zipfile.ZipFile(path) as z:
            with z.open(z.namelist()[0]) as raw:
                rd=csv.reader(io.TextIOWrapper(raw,encoding='utf-8'))
                for rr in rd:
                    try:ot=int(rr[0]);op=float(rr[1])
                    except:continue
                    if ot in target_multi:
                        for pid in target_multi[ot]:found[pid]=op
        return found
    return sym,d,pids,fetch_zip_rows(url,parse)

kline_errors=[]
done=0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(process_kline_pair,x) for x in by_kline_pair.items()]
    for fut in as_completed(futs):
        try:
            sym,d,pids,found=fut.result()
            for pid in pids:
                if pid in found: records[pid]['delayed_entry_market']=found[pid]
                else: records[pid]['kline_missing']=True
        except Exception as e:
            kline_errors.append(str(e))
        done+=1
        if done%25==0 or done==len(futs): print(f'KLINES {done}/{len(futs)}',flush=True)

# Determine executable entries and fill.
for pid,r in records.items():
    market=r.get('delayed_entry_market')
    if market is None:
        r['executable']=False;r['no_exec_reason']='KLINE_MISSING';continue
    if r['old_close_ms'] <= r['delayed_entry_open_ms']:
        r['executable']=False;r['no_exec_reason']='HIST_CLOSED_BEFORE_DELAYED_ENTRY';continue
    r['executable']=True;r['no_exec_reason']=''
    r['entry_fill']=entry_fill_short(market,r['slip_bps'])
    r['qty']=r['notional']/r['entry_fill']
    r['entry_fee']=r['notional']*r['fee_rate']
    r['entry_end_ms']=r['old_close_ms']

exec_ids=[pid for pid,r in records.items() if r['executable']]
print('EXECUTABLE',len(exec_ids),'NO_EXEC',128-len(exec_ids),flush=True)

# ---------- Filter daily aggTrades archives into per-position paths ----------
paths={pid:[] for pid in exec_ids}
by_agg_pair=defaultdict(list)
for pid in exec_ids:
    r=records[pid]
    for d in date_range(r['delayed_entry_open_ms'],r['old_close_ms']):
        by_agg_pair[(r['symbol'],d)].append(pid)

def process_agg_pair(item):
    (sym,d),pids=item
    url=f'https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip'
    windows={pid:(records[pid]['delayed_entry_open_ms'],records[pid]['old_close_ms']) for pid in pids}
    local={pid:[] for pid in pids}
    def parse(path):
        with zipfile.ZipFile(path) as z:
            with z.open(z.namelist()[0]) as raw:
                rd=csv.reader(io.TextIOWrapper(raw,encoding='utf-8'))
                for rr in rd:
                    try:px=float(rr[1]);ts=int(rr[5])
                    except:continue
                    for pid,(a,bm) in windows.items():
                        if a <= ts <= bm:
                            local[pid].append((ts,px))
        return local
    return sym,d,fetch_zip_rows(url,parse)

agg_errors=[]
done=0
with ThreadPoolExecutor(max_workers=4) as ex:
    futs=[ex.submit(process_agg_pair,x) for x in by_agg_pair.items()]
    for fut in as_completed(futs):
        try:
            sym,d,local=fut.result()
            for pid,arr in local.items(): paths[pid].extend(arr)
        except Exception as e:
            agg_errors.append(str(e))
        done+=1
        if done%10==0 or done==len(futs): print(f'AGG {done}/{len(futs)}',flush=True)

for pid in exec_ids:
    paths[pid].sort(key=lambda x:x[0])

# ---------- Build 5s samples & anatomy ----------
def build_samples(r,trades):
    next_ms=r['delayed_entry_open_ms']+5000
    end=r['old_close_ms']
    last=r['delayed_entry_market']
    samples=[]
    i=0
    # trades can occur at entry bar open and after
    for ts,px in trades:
        while next_ms < ts and next_ms<=end:
            samples.append((next_ms,last,side_ret_short(r['entry_fill'],last)));next_ms+=5000
        last=px
        while next_ms==ts and next_ms<=end:
            samples.append((next_ms,last,side_ret_short(r['entry_fill'],last)));next_ms+=5000
    while next_ms<=end:
        samples.append((next_ms,last,side_ret_short(r['entry_fill'],last)));next_ms+=5000
    return samples,last

samples={}
for pid in exec_ids:
    r=records[pid];tr=paths[pid]
    s,last=build_samples(r,tr)
    samples[pid]=s
    pxs=[r['delayed_entry_market']]+[px for _,px in tr]
    if pxs:
        rets=[side_ret_short(r['entry_fill'],px) for px in pxs]
        r['delayed_mfe_pct']=max(rets)
        r['delayed_mae_pct']=min(rets)
    else:
        r['delayed_mfe_pct']=r['delayed_mae_pct']=side_ret_short(r['entry_fill'],r['delayed_entry_market'])
    r['last_market_at_close']=tr[-1][1] if tr else last
    r['trade_prints']=len(tr);r['samples_5s']=len(s)

# ---------- Policy simulators ----------
def close_piece(r,market,qty,entry_fee_alloc):
    return realized_piece(r['entry_fill'],market,qty,entry_fee_alloc,r['fee_rate'],r['slip_bps'])[0]

def hold_close(r):
    usd=close_piece(r,r['last_market_at_close'],r['qty'],r['entry_fee'])
    return {'usd':usd,'pct':100*usd/r['notional'],'reason':'HIST_TIME_FALLBACK',
            'actions':1,'realized_positive':usd>0}

def sltp(r,trades):
    for ts,px in trades:
        ret=side_ret_short(r['entry_fill'],px)
        if ret>=1.0:
            usd=close_piece(r,px,r['qty'],r['entry_fee'])
            return {'usd':usd,'pct':100*usd/r['notional'],'reason':'TP_1.00','actions':1,'realized_positive':usd>0}
        if ret<=-1.0:
            usd=close_piece(r,px,r['qty'],r['entry_fee'])
            return {'usd':usd,'pct':100*usd/r['notional'],'reason':'SL_-1.00','actions':1,'realized_positive':usd>0}
    return hold_close(r)

def hybrid(r,samps,*,small_retain,small_confirm,reduce_fraction):
    peak=-999.0; small_consec=0;runner_consec=0;runner_mode=False;small_fired=False
    realized=0.0;qty_closed=0.0;entry_fee_alloc=0.0
    reason='HIST_TIME_FALLBACK';actions=0
    for ts,px,ret in samps:
        peak=max(peak,ret)
        if (not runner_mode) and peak>=1.50:
            runner_mode=True;small_consec=0
        if runner_mode:
            cond=ret<=peak*0.90
            runner_consec=runner_consec+1 if cond else 0
            if runner_consec>=2:
                rem=max(0.0,r['qty']-qty_closed)
                if rem>EPS:
                    alloc=max(0.0,r['entry_fee']-entry_fee_alloc)
                    realized+=close_piece(r,px,rem,alloc)
                    qty_closed+=rem;entry_fee_alloc+=alloc;actions+=1
                reason='RUNNER_CLOSE'
                break
            continue
        if small_fired:continue
        cond=(peak>=0.50 and ret<=peak*small_retain)
        small_consec=small_consec+1 if cond else 0
        if small_consec>=small_confirm:
            rem=max(0.0,r['qty']-qty_closed)
            q=rem*reduce_fraction
            alloc=r['entry_fee']*(q/r['qty']) if r['qty']>0 else 0.0
            realized+=close_piece(r,px,q,alloc)
            qty_closed+=q;entry_fee_alloc+=alloc;actions+=1
            small_fired=True;small_consec=0
            reason='V43_FULL_CLOSE' if reduce_fraction>=0.999 else 'REDUCE25'
            if qty_closed>=r['qty']-EPS:break
    if qty_closed<r['qty']-EPS:
        rem=r['qty']-qty_closed
        alloc=max(0.0,r['entry_fee']-entry_fee_alloc)
        realized+=close_piece(r,r['last_market_at_close'],rem,alloc)
        qty_closed+=rem;actions+=1
        if reason=='REDUCE25':reason='REDUCE25+HIST_FALLBACK'
        elif reason!='RUNNER_CLOSE':reason='HIST_TIME_FALLBACK'
    return {'usd':realized,'pct':100*realized/r['notional'],'reason':reason,
            'actions':actions,'realized_positive':realized>0,
            'small_fired':small_fired,'runner_mode':runner_mode}

policies={}
for pid in exec_ids:
    r=records[pid]
    policies[pid]={
      'DELAYED_HIST_CLOSE':hold_close(r),
      'SL1_TP1':sltp(r,paths[pid]),
      'V42_HYBRID':hybrid(r,samples[pid],small_retain=0.60,small_confirm=3,reduce_fraction=0.25),
      'V43_SHORT_LS4':hybrid(r,samples[pid],small_retain=0.75,small_confirm=1,reduce_fraction=1.00),
    }

# ---------- Metrics ----------
policy_names=['DELAYED_HIST_CLOSE','SL1_TP1','V42_HYBRID','V43_SHORT_LS4']
def metric(pids,policy):
    vals=[policies[pid][policy]['usd'] for pid in pids]
    pct=[policies[pid][policy]['pct'] for pid in pids]
    if not vals:return {'n':0}
    gp=sum(v for v in vals if v>0);gl=sum(v for v in vals if v<0)
    pos=[pid for pid in pids if policies[pid][policy]['usd']>0]
    rets=[]
    for pid in pos:
        mfe=records[pid]['delayed_mfe_pct']
        if mfe>0:
            rets.append(100*policies[pid][policy]['pct']/mfe)
    return {
      'n':len(vals),'win_n':sum(v>0 for v in vals),'wr_pct':100*sum(v>0 for v in vals)/len(vals),
      'pnl_usdt':sum(vals),'avg_return_pct':sum(pct)/len(pct),'median_return_pct':statistics.median(pct),
      'gross_profit_usdt':gp,'gross_loss_usdt':gl,'max_loss_usdt':min(vals),
      'winner_retention_median_pct':statistics.median(rets) if rets else None,
      'winner_retention_mean_pct':statistics.mean(rets) if rets else None,
      'action_counts':dict(Counter(policies[pid][policy]['reason'] for pid in pids)),
    }

def anatomy(pids):
    if not pids:return {'n':0}
    mfe=[records[pid]['delayed_mfe_pct'] for pid in pids];mae=[records[pid]['delayed_mae_pct'] for pid in pids]
    return {'n':len(pids),'mfe_median_pct':statistics.median(mfe),'mfe_mean_pct':statistics.mean(mfe),
            'mae_median_pct':statistics.median(mae),'mae_mean_pct':statistics.mean(mae),
            'mfe_ge_0p5_n':sum(x>=0.5 for x in mfe),'mfe_ge_1p0_n':sum(x>=1.0 for x in mfe)}

split_summary={}
for sp in ['Discovery','Validation','Reserve','ALL']:
    spids=[pid for pid in exec_ids if sp=='ALL' or records[pid]['split']==sp]
    wins=[pid for pid in spids if records[pid]['strong_win']]
    losses=[pid for pid in spids if not records[pid]['strong_win']]
    split_summary[sp]={
      'executable_n':len(spids),'strong_win_n':len(wins),'non_target_n':len(losses),
      'anatomy_all':anatomy(spids),'anatomy_strong_win':anatomy(wins),'anatomy_non_target':anatomy(losses),
      'policies':{pn:metric(spids,pn) for pn in policy_names},
      'strong_win_policies':{pn:metric(wins,pn) for pn in policy_names},
      'non_target_policies':{pn:metric(losses,pn) for pn in policy_names},
    }

# no executable counts
noexec=[pid for pid,r in records.items() if not r['executable']]
noexec_by_split=Counter(records[pid]['split'] for pid in noexec)
noexec_win_by_split=Counter(records[pid]['split'] for pid in noexec if records[pid]['strong_win'])

# compatibility tiers vs baseline
compat={}
for pn in ['SL1_TP1','V42_HYBRID','V43_SHORT_LS4']:
    base_all=split_summary['ALL']['policies']['DELAYED_HIST_CLOSE']
    cur_all=split_summary['ALL']['policies'][pn]
    checks={}
    sep_ok=True
    for sp in ['Validation','Reserve']:
        base=split_summary[sp]['policies']['DELAYED_HIST_CLOSE'];cur=split_summary[sp]['policies'][pn]
        pnl_ok=cur['pnl_usdt']>=base['pnl_usdt']-EPS
        win_ok=cur['win_n']>=base['win_n']-1
        # gross loss is negative: deterioration >10% means abs(cur) > 1.1 abs(base)
        gl_ok=abs(cur['gross_loss_usdt']) <= 1.10*abs(base['gross_loss_usdt']) + EPS
        checks[sp]={'pnl_ok':pnl_ok,'win_ok':win_ok,'gross_loss_ok':gl_ok}
        sep_ok=sep_ok and pnl_ok and win_ok and gl_ok
    full_improve=cur_all['pnl_usdt']>base_all['pnl_usdt']+EPS
    if sep_ok and full_improve:
        tier='COMPATIBLE'
    else:
        vdet=split_summary['Validation']['policies'][pn]['pnl_usdt']-split_summary['Validation']['policies']['DELAYED_HIST_CLOSE']['pnl_usdt']
        rdet=split_summary['Reserve']['policies'][pn]['pnl_usdt']-split_summary['Reserve']['policies']['DELAYED_HIST_CLOSE']['pnl_usdt']
        catastrophic=(cur_all['win_n'] < max(0,base_all['win_n']-max(3,int(0.20*base_all['win_n']))))
        if full_improve and vdet>=-10 and rdet>=-10 and not catastrophic:
            tier='PROMISING'
        else:tier='INCOMPATIBLE'
    compat[pn]={'tier':tier,'full_pnl_delta_usdt':cur_all['pnl_usdt']-base_all['pnl_usdt'],
                'checks':checks}

# detail CSV
detail=[]
for pid,r in records.items():
    row={k:r.get(k) for k in ['position_id','symbol','split','strong_win','t3_target_ms','old_close_ms',
                              'delayed_entry_open_ms','delayed_entry_market','entry_fill','executable','no_exec_reason',
                              'delayed_mfe_pct','delayed_mae_pct','trade_prints','samples_5s']}
    if r['executable']:
        for pn in policy_names:
            pr=policies[pid][pn]
            row[f'{pn}_pnl_usdt']=pr['usd'];row[f'{pn}_return_pct']=pr['pct'];row[f'{pn}_reason']=pr['reason']
    detail.append(row)
fields=[]
for row in detail:
    for k in row:
        if k not in fields:fields.append(k)
with DETAIL.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(detail)

summary={
 'stage':'SD-2B4',
 'status':'COMPLETE',
 'contract':{
   'entry_rule':'Lane1 T+3 confirm_side_return_pct >= 0.0338983050847%',
   'selected_n':128,'frozen_exit_policies':policy_names,
   'fee_rate':FEE_RATE,'slippage_bps':SLIP_BPS,'notional_usdt':NOTIONAL,
   'delayed_entry_proxy':'open of first 1m bar strictly after T+3 target',
   'agg_sampling':'5s latest print <= boundary with carry-forward',
 },
 'market_data':{
   'kline_pairs':len(by_kline_pair),'aggtrade_pairs':len(by_agg_pair),
   'kline_errors':kline_errors,'aggtrade_errors':agg_errors,
 },
 'execution':{
   'selected_n':128,'executable_n':len(exec_ids),'no_executable_n':len(noexec),
   'noexec_by_split':dict(noexec_by_split),'noexec_strong_win_by_split':dict(noexec_win_by_split),
 },
 'splits':split_summary,
 'compatibility':compat,
}
SUMMARY.write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)
print('DETAIL',DETAIL,flush=True)