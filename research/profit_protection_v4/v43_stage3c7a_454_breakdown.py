from __future__ import annotations
import csv, json, statistics
from pathlib import Path

# Execute authoritative 454 archive-5s replay to build samples/meta/helpers.
exec(compile(Path('/tmp/full454_archive5s_exact.py').read_text(encoding='utf-8'), '/tmp/full454_archive5s_exact.py', 'exec'), globals())

# V4.3 LONG LS3 selected parameters.
V43 = {
    'small_arm': 0.50,
    'small_retain': 0.97,
    'small_confirm': 1,
    'reduce_fraction': 1.00,
    'runner_qualify': 1.50,
    'runner_retain': 0.90,
    'runner_confirm': 2,
}

def simulate_with_details(pid, params):
    m=meta[pid]
    peak=-999.0
    small_consec=0
    runner_consec=0
    runner_mode=False
    small_fired=False
    realized=0.0
    qty_closed=0.0
    entry_alloc=0.0
    small_ts=None
    small_px=None
    final_ts=None
    final_px=None
    final_reason=None

    for ts,px,pnl in samples[pid]:
        peak=max(peak,pnl)
        if (not runner_mode) and peak>=params['runner_qualify']:
            runner_mode=True
            small_consec=0

        if runner_mode:
            cond=pnl <= peak*params['runner_retain']
            runner_consec=runner_consec+1 if cond else 0
            if runner_consec>=params['runner_confirm']:
                rem=max(0.0,m['qty']-qty_closed)
                alloc=max(0.0,m['entry_fee']-entry_alloc)
                u,fill=calc_exit(pid,px,rem,alloc)
                realized += u
                final_ts=ts; final_px=fill
                final_reason='REDUCE25+RUNNER_CLOSE' if small_fired else 'RUNNER_CLOSE'
                return {
                    'usd':realized,'pct':full_pct(pid,realized),'reason':final_reason,
                    'small':small_fired,'runner':True,'small_ts':small_ts,'small_fill':small_px,
                    'close_ts':final_ts,'close_fill':final_px,'peak_sampled_pct':peak,
                }
            continue

        if small_fired:
            continue

        cond=peak>=params['small_arm'] and pnl<=peak*params['small_retain']
        small_consec=small_consec+1 if cond else 0
        if small_consec>=params['small_confirm']:
            rem=max(0.0,m['qty']-qty_closed)
            q=rem*params['reduce_fraction']
            alloc=m['entry_fee']*(q/m['qty']) if m['qty']>0 else 0.0
            u,fill=calc_exit(pid,px,q,alloc)
            realized += u
            qty_closed += q
            entry_alloc += alloc
            small_fired=True
            small_ts=ts; small_px=fill
            small_consec=0
            if q >= rem-1e-15:
                return {
                    'usd':realized,'pct':full_pct(pid,realized),'reason':'V43_FULL_CLOSE',
                    'small':True,'runner':False,'small_ts':small_ts,'small_fill':small_px,
                    'close_ts':small_ts,'close_fill':small_px,'peak_sampled_pct':peak,
                }

    # fallback remainder to historical final close
    rem=max(0.0,m['qty']-qty_closed)
    fallback_fill=final_close[pid]
    if rem>1e-15:
        alloc=max(0.0,m['entry_fee']-entry_alloc)
        u,fallback_fill=calc_exit(pid,final_close[pid],rem,alloc)
        realized += u
    return {
        'usd':realized,'pct':full_pct(pid,realized),
        'reason':'REDUCE25_FALLBACK' if small_fired else 'HIST_TIME_FALLBACK',
        'small':small_fired,'runner':False,'small_ts':small_ts,'small_fill':small_px,
        'close_ts':m['close'],'close_fill':fallback_fill,'peak_sampled_pct':peak,
    }

BASE_PARAMS={'small_arm':0.50,'small_retain':0.60,'small_confirm':3,'reduce_fraction':0.25,'runner_qualify':1.50,'runner_retain':0.90,'runner_confirm':2}

def bucket(x):
    x=float(x)
    if x < 0.30: return '<0.30%'
    if x < 0.50: return '0.30-<0.50%'
    if x < 1.00: return '0.50-<1.00%'
    if x < 1.50: return '1.00-<1.50%'
    if x < 2.00: return '1.50-<2.00%'
    if x < 3.00: return '2.00-<3.00%'
    if x < 5.00: return '3.00-<5.00%'
    return '>=5.00%'

order=['<0.30%','0.30-<0.50%','0.50-<1.00%','1.00-<1.50%','1.50-<2.00%','2.00-<3.00%','3.00-<5.00%','>=5.00%']

detail=[]
for src in rows:
    pid=src['position_id']
    hist_mfe=float(src['historical_mfe_pct'])
    hist_pnl=float(src['historical_pnl'])
    hist_pct=float(src['historical_return_pct'])

    b=simulate_with_details(pid,BASE_PARAMS)
    baseline_lane=b['reason']

    # V4.3 LS3 only replaces baseline LONG REDUCE25 lane.
    if b['reason']=='REDUCE25_FALLBACK' and b['small'] and not b['runner']:
        v=simulate_with_details(pid,V43)
        v43_applied=True
    else:
        v=b
        v43_applied=False

    retention=(100.0*v['pct']/hist_mfe) if hist_mfe>0 else None
    detail.append({
        'position_id':pid,
        'symbol':src['symbol'],
        'side':meta[pid]['side'],
        'mfe_pct':hist_mfe,
        'mfe_bucket':bucket(hist_mfe),
        'historical_return_pct':hist_pct,
        'historical_pnl_usdt':hist_pnl,
        'historical_close_ms':meta[pid]['close'],
        'historical_close_fill':final_close[pid],
        'v42_action':b['reason'],
        'v42_close_pct':b['pct'],
        'v42_pnl_usdt':b['usd'],
        'v42_close_ms':b['close_ts'],
        'v42_close_fill':b['close_fill'],
        'v43_applied':v43_applied,
        'v43_action':v['reason'],
        'v43_close_pct':v['pct'],
        'v43_pnl_usdt':v['usd'],
        'v43_close_ms':v['close_ts'],
        'v43_close_fill':v['close_fill'],
        'v43_delta_vs_v42_usdt':v['usd']-b['usd'],
        'v43_delta_vs_historical_usdt':v['usd']-hist_pnl,
        'v43_win':v['usd']>0,
        'retention_vs_mfe_pct':retention,
        'sampled_peak_pct':v['peak_sampled_pct'],
    })

# summary by bucket
summary=[]
for bk in order:
    g=[r for r in detail if r['mfe_bucket']==bk]
    if not g: continue
    rets=[r['retention_vs_mfe_pct'] for r in g if r['retention_vs_mfe_pct'] is not None]
    summary.append({
        'mfe_bucket':bk,
        'n':len(g),
        'historical_win_n':sum(r['historical_pnl_usdt']>0 for r in g),
        'historical_wr_pct':100*sum(r['historical_pnl_usdt']>0 for r in g)/len(g),
        'historical_pnl_usdt':sum(r['historical_pnl_usdt'] for r in g),
        'v42_win_n':sum(r['v42_pnl_usdt']>0 for r in g),
        'v42_wr_pct':100*sum(r['v42_pnl_usdt']>0 for r in g)/len(g),
        'v42_pnl_usdt':sum(r['v42_pnl_usdt'] for r in g),
        'v43_win_n':sum(r['v43_win'] for r in g),
        'v43_wr_pct':100*sum(r['v43_win'] for r in g)/len(g),
        'v43_pnl_usdt':sum(r['v43_pnl_usdt'] for r in g),
        'delta_v43_vs_v42_usdt':sum(r['v43_delta_vs_v42_usdt'] for r in g),
        'delta_v43_vs_hist_usdt':sum(r['v43_delta_vs_historical_usdt'] for r in g),
        'v43_applied_n':sum(r['v43_applied'] for r in g),
        'median_v43_close_pct':statistics.median(r['v43_close_pct'] for r in g),
        'median_retention_vs_mfe_pct':statistics.median(rets) if rets else None,
    })

actions={}
for r in detail:
    actions[r['v43_action']]=actions.get(r['v43_action'],0)+1

overall={
    'universe_n':len(detail),
    'all_side':sorted(set(r['side'] for r in detail)),
    'historical':{
        'win_n':sum(r['historical_pnl_usdt']>0 for r in detail),
        'wr_pct':100*sum(r['historical_pnl_usdt']>0 for r in detail)/len(detail),
        'pnl_usdt':sum(r['historical_pnl_usdt'] for r in detail),
    },
    'v42':{
        'win_n':sum(r['v42_pnl_usdt']>0 for r in detail),
        'wr_pct':100*sum(r['v42_pnl_usdt']>0 for r in detail)/len(detail),
        'pnl_usdt':sum(r['v42_pnl_usdt'] for r in detail),
    },
    'v43':{
        'win_n':sum(r['v43_win'] for r in detail),
        'wr_pct':100*sum(r['v43_win'] for r in detail)/len(detail),
        'pnl_usdt':sum(r['v43_pnl_usdt'] for r in detail),
        'applied_n':sum(r['v43_applied'] for r in detail),
        'actions':actions,
    },
    'delta_v43_vs_v42_usdt':sum(r['v43_delta_vs_v42_usdt'] for r in detail),
    'delta_v43_vs_historical_usdt':sum(r['v43_delta_vs_historical_usdt'] for r in detail),
    'params':V43,
}

detail.sort(key=lambda r:(r['mfe_pct'],r['symbol']))
with open('/tmp/v43_454_trade_detail.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(detail[0].keys()));w.writeheader();w.writerows(detail)
with open('/tmp/v43_454_mfe_distribution.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0].keys()));w.writeheader();w.writerows(summary)
Path('/tmp/v43_454_summary.json').write_text(json.dumps({'overall':overall,'mfe_distribution':summary},indent=2),encoding='utf-8')
print(json.dumps({'overall':overall,'mfe_distribution':summary},indent=2),flush=True)