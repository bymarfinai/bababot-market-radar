import csv,json,math
from collections import Counter
from pathlib import Path

ROOT=Path('/tmp/ct1')
S8=list(csv.DictReader(open(ROOT/'research/short_detector/results/sds8_unified_655_detail.csv')))
F0={r['meta_position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv'))}
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
FRESH={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
FF=list(csv.DictReader(open('/tmp/s10i_fresh_funnel.csv')))
THS=[0.0338983050847,0.05,0.075,0.10,0.125,0.15,0.158514,0.20]

def ff(v,d=None):
    try:
        x=float(v);return x if math.isfinite(x) else d
    except:return d
def truth(v):return str(v).lower()=='true'
def causal(r,h):
    try:return int(float(r['primary_label_end_ms']))>int(float(r[f't{h}_target_ms']))
    except:return False
def band(r,k,lo,hi):
    v=ff(r.get(k));return v is not None and lo<=v<=hi
def ge(r,k,t):
    v=ff(r.get(k));return v is not None and v>=t
def fast(r,router_lane):
    if router_lane!=1:return False
    return (band(r,'f_new_volume_over_range',1.0170781185420166,1.060973255243714) or
            ge(r,'f_new_momentum_curvature',1.2636050833333325) or
            band(r,'f_new_accel_15_vs_60',0.6594,1.7240119999999999) or
            band(r,'f_context_breakdown_down_pct',0.42735,0.446816) or
            band(r,'f_f_oi_accel_x_overheat',-0.29188090961795327,-0.23281000377161334) or
            band(r,'f_f_coin_minus_market_30m',0.6909331187969325,0.7639814635249487))
def lane0_recovery(r,router_lane):
    if router_lane!=0:return None
    if causal(r,2) and ff(r.get('t2_delta_f_coin_minus_market_15m'),-999)>=0.032030968083884837:return 2
    if causal(r,3) and ff(r.get('t3_f_micro_decay_3_vs_prev3'),999)<=0.2779031656624853:return 3
    return None
def alt(r,router_lane):
    return router_lane==1 and causal(r,3) and ge(r,'t3_delta_micro_selected_vwap_extension_20',0.0024105131797624857)
def lane1_h(r,router_lane,th):
    if router_lane!=1:return None
    for h in (1,2,3):
        v=ff(r.get(f't{h}_confirm_side_return_pct'))
        if causal(r,h) and v is not None and v>=th:return h
    return None

# canonical research rows
research=[]
for s in S8:
    pid=s['position_id'];r=dict(F0[pid]);t=TM[pid]
    # temporal columns come from TM
    r.update(t)
    research.append({'id':pid,'block':'Research_'+s['split'],'router_lane':int(s['router_lane']),
                     'strong':truth(s['strong_win']),'row':r})
# canonical fresh resolved rows
fresh=[]
for a in FF:
    pid=a['meta_position_id']
    r=FRESH[pid]
    fresh.append({'id':pid,'block':'Fresh','router_lane':int(a['router_lane']),
                  'strong':truth(a['strong_win']),'row':r})

def select_one(x,th):
    r=x['row'];rl=x['router_lane']
    fa=fast(r,rl)
    ah=lane1_h(r,rl,th)
    ch=lane0_recovery(r,rl)
    base=(ah is not None or ch is not None)
    al=(not base and not fa and alt(r,rl))
    selected=bool(base or fa or al)
    if not selected:return None
    if fa:return {'lane':0,'source':'FAST_T0'}
    if ah is not None:return {'lane':ah,'source':'LANE1_TEMPORAL'}
    if ch is not None:return {'lane':ch,'source':'LANE0_RECOVERY'}
    return {'lane':3,'source':'ALT_T3'}

def metrics(dataset,th):
    sel=[]
    for x in dataset:
        z=select_one(x,th)
        if z:sel.append((x,z))
    n=len(sel);strong=sum(x['strong'] for x,z in sel);non=n-strong
    return {
      'selected':n,'strong':strong,'non_target':non,
      'precision':strong/n if n else 0,
      'strong_recall':strong/sum(x['strong'] for x in dataset),
      'lanes':dict(Counter(str(z['lane']) for x,z in sel)),
      'sources':dict(Counter(z['source'] for x,z in sel)),
      'ids':[x['id'] for x,z in sel],
      'strong_ids':[x['id'] for x,z in sel if x['strong']]
    }

out={'stage':'SHORT-CT1','status':'THRESHOLD_SWEEP_COMPLETE','thresholds':[]}
baseR=None;baseF=None
for th in THS:
    R=metrics(research,th);F=metrics(fresh,th)
    if baseR is None:baseR=R;baseF=F
    row={'threshold':th,'research':R,'fresh':F}
    for label,m,b in [('research',R,baseR),('fresh',F,baseF)]:
        m['removed_vs_baseline']=b['selected']-m['selected']
        m['strong_removed_vs_baseline']=b['strong']-m['strong']
        m['non_target_removed_vs_baseline']=b['non_target']-m['non_target']
        m['nt_removed_per_strong_lost']=(m['non_target_removed_vs_baseline']/m['strong_removed_vs_baseline'] if m['strong_removed_vs_baseline'] else None)
    out['thresholds'].append(row)

# split / fresh-day diagnostics using IDs, without using to tune CT1 winner
# Fresh day from opened_at timestamp in feature row
from datetime import datetime,timezone
fresh_block={}
for x in fresh:
    ms=int(float(x['row']['meta_opened_at_ms']))
    fresh_block[x['id']]=datetime.fromtimestamp(ms/1000,timezone.utc).strftime('Fresh_%Y-%m-%d')
for row in out['thresholds']:
    th=row['threshold'];row['blocks']={}
    for b in ['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']:
        ds=research if b.startswith('Research') else fresh
        q=[]
        for x in ds:
            xb=x['block'] if b.startswith('Research') else fresh_block[x['id']]
            if xb!=b:continue
            z=select_one(x,th)
            if z:q.append((x,z))
        totalstrong=sum(x['strong'] for x in ds if (x['block'] if b.startswith('Research') else fresh_block[x['id']])==b)
        row['blocks'][b]={'selected':len(q),'strong':sum(x['strong'] for x,z in q),
                          'precision':sum(x['strong'] for x,z in q)/len(q) if q else 0,
                          'strong_recall':sum(x['strong'] for x,z in q)/totalstrong if totalstrong else 0}

json.dump(out,open('/tmp/ct1_summary.json','w'),indent=2)
print('RESEARCH total strong',sum(x['strong'] for x in research),'n',len(research))
print('FRESH total strong',sum(x['strong'] for x in fresh),'n',len(fresh))
print()
for row in out['thresholds']:
    th=row['threshold'];R=row['research'];F=row['fresh']
    print('TH',th)
    print(' R sel',R['selected'],'strong',R['strong'],'non',R['non_target'],'prec',round(R['precision'],4),'rec',round(R['strong_recall'],4),
          'removed',R['removed_vs_baseline'],'strongLost',R['strong_removed_vs_baseline'],'ntRemoved',R['non_target_removed_vs_baseline'],
          'ratio',None if R['nt_removed_per_strong_lost'] is None else round(R['nt_removed_per_strong_lost'],2),'lanes',R['lanes'],'src',R['sources'])
    print(' F sel',F['selected'],'strong',F['strong'],'non',F['non_target'],'prec',round(F['precision'],4),'rec',round(F['strong_recall'],4),
          'removed',F['removed_vs_baseline'],'strongLost',F['strong_removed_vs_baseline'],'ntRemoved',F['non_target_removed_vs_baseline'],
          'ratio',None if F['nt_removed_per_strong_lost'] is None else round(F['nt_removed_per_strong_lost'],2),'lanes',F['lanes'],'src',F['sources'])
    print(' blocks',[(b,v['selected'],v['strong'],round(v['precision'],3),round(v['strong_recall'],3)) for b,v in row['blocks'].items()])