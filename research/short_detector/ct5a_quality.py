import csv,json,math
from collections import Counter
from datetime import datetime,timezone

# reuse CT5A detail
rows=list(csv.DictReader(open('/tmp/ct5a_shift_detail.csv')))
CT4=[r for r in csv.DictReader(open('/tmp/ct4_trade_detail.csv')) if r['candidate']=='T0075']
R0={r['meta_position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv'))}
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
S8={r['position_id']:r for r in csv.DictReader(open('/tmp/ct5a/research/short_detector/results/sds8_unified_655_detail.csv'))}
FRESH={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
FF={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv'))}
TH=.075

def truth(v):return str(v).lower()=='true'
def ff(v,d=None):
    try:
        x=float(v);return x if math.isfinite(x) else d
    except:return d
def causal(r,h):
    try:return int(float(r['primary_label_end_ms']))>int(float(r[f't{h}_target_ms']))
    except:return False
def band(r,k,lo,hi):
    v=ff(r.get(k));return v is not None and lo<=v<=hi
def ge(r,k,t):
    v=ff(r.get(k));return v is not None and v>=t
def fast(r,rl):
    if rl!=1:return False
    return (band(r,'f_new_volume_over_range',1.0170781185420166,1.060973255243714) or ge(r,'f_new_momentum_curvature',1.2636050833333325) or
            band(r,'f_new_accel_15_vs_60',.6594,1.7240119999999999) or band(r,'f_context_breakdown_down_pct',.42735,.446816) or
            band(r,'f_f_oi_accel_x_overheat',-.29188090961795327,-.23281000377161334) or band(r,'f_f_coin_minus_market_30m',.6909331187969325,.7639814635249487))
def lane0_rec(r,rl):
    if rl!=0:return None
    if causal(r,2) and ff(r.get('t2_delta_f_coin_minus_market_15m'),-999)>=.032030968083884837:return 2
    if causal(r,3) and ff(r.get('t3_f_micro_decay_3_vs_prev3'),999)<=.2779031656624853:return 3
    return None
def lane1_h(r,rl):
    if rl!=1:return None
    for h in (1,2,3):
        v=ff(r.get(f't{h}_confirm_side_return_pct'))
        if causal(r,h) and v is not None and v>=TH:return h
    return None
def alt(r,rl):
    return rl==1 and causal(r,3) and ge(r,'t3_delta_micro_selected_vwap_extension_20',.0024105131797624857)
def source(r,rl):
    fa=fast(r,rl);ah=lane1_h(r,rl);ch=lane0_rec(r,rl);base=(ah is not None or ch is not None);al=(not base and not fa and alt(r,rl))
    if not(base or fa or al):return None
    if fa:return (0,'FAST_T0')
    if ah is not None:return (ah,'LANE1_TEMPORAL')
    if ch is not None:return (ch,'LANE0_RECOVERY')
    return (3,'ALT_T3')

# transition strong/non-target
out={'transition_quality':{},'alt_t3':{}}
for tr in sorted(set(r['transition'] for r in rows)):
    q=[r for r in rows if r['transition']==tr]
    z={}
    for src in ['research','fresh','all']:
        qq=q if src=='all' else [r for r in q if r['source']==src]
        for grp in ['strong','non_target']:
            g=[r for r in qq if truth(r['strong'])==(grp=='strong')]
            old=sum(float(r['baseline_pnl']) for r in g if r['baseline_pnl'] not in ('',None))
            new=sum(float(r['new_pnl']) for r in g if r['new_pnl'] not in ('',None))
            z[f'{src}_{grp}']={'n':len(g),'old_pnl':old,'new_pnl':new,'delta':new-old,'new_exec':sum(truth(r['new_executable']) for r in g),
                               'new_positive':sum((float(r['new_pnl'])>0) for r in g if r['new_pnl'] not in ('',None))}
    out['transition_quality'][tr]=z

# current source classification for all CT4 T0075 rows
c4={(r['source'],r['position_id']):r for r in CT4}
sel=[]
for src in ['research','fresh']:
    if src=='research':
        for pid,s in S8.items():
            r=dict(R0[pid]);r.update(TM[pid]);rl=int(s['router_lane']);z=source(r,rl)
            if z is None:continue
            c=c4.get((src,pid))
            if not c:continue
            sel.append({'source':src,'id':pid,'block':'Research_'+s['split'],'strong':truth(s['strong_win']),'lane':z[0],'entry_source':z[1],
                        'executable':truth(c['executable']),'pnl':float(c['pnl']) if truth(c['executable']) else None,'reason':c['reason']})
    else:
        for pid,a in FF.items():
            r=FRESH[pid];rl=int(a['router_lane']);z=source(r,rl)
            if z is None:continue
            c=c4.get((src,pid))
            if not c:continue
            ms=int(float(r['meta_opened_at_ms']));b='Fresh_'+datetime.fromtimestamp(ms/1000,timezone.utc).strftime('%Y-%m-%d')
            sel.append({'source':src,'id':pid,'block':b,'strong':truth(a['strong_win']),'lane':z[0],'entry_source':z[1],
                        'executable':truth(c['executable']),'pnl':float(c['pnl']) if truth(c['executable']) else None,'reason':c['reason']})

def met(q):
    ex=[r for r in q if r['executable']]
    vals=[r['pnl'] for r in ex]
    return {'n':len(q),'strong':sum(r['strong'] for r in q),'exec':len(ex),'exec_strong':sum(r['strong'] for r in ex),
            'pnl':sum(vals),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,
            'strong_pnl':sum(r['pnl'] for r in ex if r['strong']),'non_target_pnl':sum(r['pnl'] for r in ex if not r['strong']),
            'fallback_n':sum(r['reason']=='HIST_TIME_FALLBACK' for r in ex),'fallback_pnl':sum(r['pnl'] for r in ex if r['reason']=='HIST_TIME_FALLBACK'),
            'reasons':dict(Counter(r['reason'] for r in ex))}
altq=[r for r in sel if r['entry_source']=='ALT_T3']
out['alt_t3']['overall']=met(altq)
for src in ['research','fresh']:
    out['alt_t3'][src]=met([r for r in altq if r['source']==src])
out['alt_t3']['blocks']={b:met([r for r in altq if r['block']==b]) for b in sorted(set(r['block'] for r in altq))}
# all T3 for context
t3=[r for r in sel if r['lane']==3]
out['t3_all']={'overall':met(t3),'research':met([r for r in t3 if r['source']=='research']),'fresh':met([r for r in t3 if r['source']=='fresh']),
               'by_source':{s:met([r for r in t3 if r['entry_source']==s]) for s in sorted(set(r['entry_source'] for r in t3))}}

json.dump(out,open('/tmp/ct5a_quality.json','w'),indent=2)
print('TRANSITION QUALITY')
for tr,z in out['transition_quality'].items():
    print('\n',tr)
    for src in ['research','fresh']:
      print(src,'STR',z[src+'_strong'],'NT',z[src+'_non_target'])
print('\nALT_T3',json.dumps(out['alt_t3'],indent=2))
print('\nT3_ALL',json.dumps(out['t3_all'],indent=2))