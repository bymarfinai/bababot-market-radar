import csv,json,math,statistics
from collections import Counter,defaultdict
from datetime import datetime,timezone

ROOT='/tmp/ct2'
S8=list(csv.DictReader(open(ROOT+'/research/short_detector/results/sds8_unified_655_detail.csv')))
F0={r['meta_position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv'))}
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
FRESH={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
FF={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv'))}
RREPLAY={r['position_id']:r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D'}
FREPLAY={r['position_id']:r for r in csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv'))}
THS=[0.0338983050847,0.05,0.075,0.10]

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
def lane1_h(r,rl,th):
    if rl!=1:return None
    for h in (1,2,3):
        v=ff(r.get(f't{h}_confirm_side_return_pct'))
        if causal(r,h) and v is not None and v>=th:return h
    return None
def alt(r,rl):
    return rl==1 and causal(r,3) and ge(r,'t3_delta_micro_selected_vwap_extension_20',.0024105131797624857)
def sel(r,rl,th):
    fa=fast(r,rl); ah=lane1_h(r,rl,th); ch=lane0_rec(r,rl)
    base=(ah is not None or ch is not None)
    al=(not base and not fa and alt(r,rl))
    if not(base or fa or al):return None
    if fa:return (0,'FAST_T0')
    if ah is not None:return (ah,'LANE1_TEMPORAL')
    if ch is not None:return (ch,'LANE0_RECOVERY')
    return (3,'ALT_T3')

# canonical records
sets={'research':[],'fresh':[]}
for s in S8:
    pid=s['position_id'];r=dict(F0[pid]);r.update(TM[pid])
    sets['research'].append({'id':pid,'symbol':s['symbol'],'block':'Research_'+s['split'],'strong':truth(s['strong_win']),
      'label':s['primary_meta_label'],'r':r,'rl':int(s['router_lane'])})
for pid,a in FF.items():
    r=FRESH[pid]
    ms=int(float(r['meta_opened_at_ms']));day=datetime.fromtimestamp(ms/1000,timezone.utc).strftime('%Y-%m-%d')
    sets['fresh'].append({'id':pid,'symbol':r['meta_symbol'],'block':'Fresh_'+day,'strong':truth(a['strong_win']),
      'label':r['primary_meta_label'],'r':r,'rl':int(a['router_lane'])})

def replay_info(src,pid):
    rr=(RREPLAY if src=='research' else FREPLAY).get(pid)
    if not rr:return {'executable':False}
    if src=='research':
        if not truth(rr['executable']):return {'executable':False}
        pnl=float(rr['COMP_pnl']);reason=rr['COMP_reason'];mfe=ff(rr['delayed_mfe_pct']);mae=ff(rr['delayed_mae_pct'])
    else:
        pnl=float(rr['comp']);reason=rr['reason'];mfe=None;mae=None
    severe=(reason=='HIST_TIME_FALLBACK' and pnl<=-2)
    return {'executable':True,'pnl':pnl,'reason':reason,'severe':severe,'mfe':mfe,'mae':mae}

out={'stage':'SHORT-CT2','thresholds':{},'status':'ANATOMY_COMPLETE'}
detail=[]
for src,ds in sets.items():
    base={x['id']:sel(x['r'],x['rl'],THS[0]) for x in ds}
    base_ids={pid for pid,z in base.items() if z is not None}
    for th in THS[1:]:
        cur={x['id']:sel(x['r'],x['rl'],th) for x in ds}
        removed=base_ids-{pid for pid,z in cur.items() if z is not None}
        retained=base_ids-removed
        shifted=[];same=[]
        for pid in retained:
            if cur[pid][0]!=base[pid][0] or cur[pid][1]!=base[pid][1]:shifted.append(pid)
            else:same.append(pid)
        rows={x['id']:x for x in ds}
        rem=[rows[p] for p in removed];sh=[rows[p] for p in shifted]
        def cohort(ids):
            q=[rows[p] for p in ids]; infos=[(rows[p],replay_info(src,p)) for p in ids]
            ex=[(r,i) for r,i in infos if i['executable']]
            sev=[(r,i) for r,i in ex if i.get('severe')]
            loss=[(r,i) for r,i in ex if i['pnl']<0]
            return {
              'n':len(q),'strong':sum(r['strong'] for r in q),'non_target':sum(not r['strong'] for r in q),
              'labels':dict(Counter(r['label'] for r in q)),
              'blocks':dict(Counter(r['block'] for r in q)),
              'baseline_lanes':dict(Counter(str(base[r['id']][0]) for r in q)),
              'executable_n':len(ex),'executable_strong':sum(r['strong'] for r,i in ex),
              'baseline_comp_pnl':sum(i['pnl'] for r,i in ex),
              'baseline_loss_n':len(loss),'baseline_severe_n':len(sev),
              'baseline_severe_pnl':sum(i['pnl'] for r,i in sev),
              'reasons':dict(Counter(i['reason'] for r,i in ex))
            }
        c_rem=cohort(removed);c_shift=cohort(shifted)
        transitions=Counter()
        trans_strong=Counter()
        for pid in shifted:
            k=f"{base[pid][0]}->{cur[pid][0]}"
            transitions[k]+=1
            if rows[pid]['strong']:trans_strong[k]+=1
        key=f'{th:.6f}'
        out['thresholds'].setdefault(key,{})[src]={
          'removed':c_rem,'shifted':c_shift,'same_n':len(same),
          'transitions':dict(transitions),'transition_strong':dict(trans_strong)}
        for p in removed:
            r=rows[p];info=replay_info(src,p)
            detail.append({'source':src,'threshold':th,'position_id':p,'symbol':r['symbol'],'block':r['block'],'status':'REMOVED','strong':r['strong'],'label':r['label'],
              'base_lane':base[p][0],'new_lane':'','base_source':base[p][1],'new_source':'',
              'baseline_executable':info.get('executable',False),'baseline_comp_pnl':info.get('pnl',''),'baseline_reason':info.get('reason',''),'baseline_severe':info.get('severe',False)})
        for p in shifted:
            r=rows[p];info=replay_info(src,p)
            detail.append({'source':src,'threshold':th,'position_id':p,'symbol':r['symbol'],'block':r['block'],'status':'SHIFTED','strong':r['strong'],'label':r['label'],
              'base_lane':base[p][0],'new_lane':cur[p][0],'base_source':base[p][1],'new_source':cur[p][1],
              'baseline_executable':info.get('executable',False),'baseline_comp_pnl':info.get('pnl',''),'baseline_reason':info.get('reason',''),'baseline_severe':info.get('severe',False)})

# strong lost detailed temporal anatomy
for thkey,z in out['thresholds'].items():
    for src in ['research','fresh']:
        th=float(thkey); ds=sets[src]; rows={x['id']:x for x in ds}
        base={x['id']:sel(x['r'],x['rl'],THS[0]) for x in ds}
        cur={x['id']:sel(x['r'],x['rl'],th) for x in ds}
        ids=[pid for pid,b in base.items() if b is not None and cur[pid] is None and rows[pid]['strong']]
        anatomy=[]
        for pid in ids:
            x=rows[pid];r=x['r'];info=replay_info(src,pid)
            anatomy.append({'id':pid,'symbol':x['symbol'],'block':x['block'],'base_lane':base[pid][0],
             't1':ff(r.get('t1_confirm_side_return_pct')),'t2':ff(r.get('t2_confirm_side_return_pct')),'t3':ff(r.get('t3_confirm_side_return_pct')),
             'baseline_executable':info.get('executable',False),'baseline_pnl':info.get('pnl'),'baseline_reason':info.get('reason')})
        z[src]['strong_removed_anatomy']=anatomy

json.dump(out,open('/tmp/ct2_summary.json','w'),indent=2)
fields=list(detail[0].keys())
with open('/tmp/ct2_trade_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(detail)

for th,z in out['thresholds'].items():
    print('\nTH',th)
    for src in ['research','fresh']:
        a=z[src]
        print(src.upper(),'REM',a['removed'])
        print(src.upper(),'SHIFT',a['shifted'])
        print(' transitions',a['transitions'],'strong',a['transition_strong'])
        if a['strong_removed_anatomy']:
            print(' strong_removed')
            for q in a['strong_removed_anatomy']:print('  ',q)