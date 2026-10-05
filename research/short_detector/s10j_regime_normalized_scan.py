import csv,json,math,statistics,bisect
from collections import defaultdict,Counter
from pathlib import Path

ROOT=Path('/tmp/s10j')
OLD=list(csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv')))
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
S8=list(csv.DictReader(open(ROOT/'research/short_detector/results/sds8_unified_655_detail.csv')))
FRESH={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
FF=list(csv.DictReader(open('/tmp/s10i_fresh_funnel.csv')))
F0={r['meta_position_id']:r for r in OLD}
TH=.0338983050847
FEATURES=[
 'f_new_overheat_pressure','f_new_accel_15_vs_60','f_new_volume_over_range','f_gate_price_drift_pct',
 'f_f_taker_accel_1m','f_new_gate_price_x_flow_gap','f_new_momentum_curvature','f_context_breakdown_down_pct',
 'f_f_oi_accel_x_overheat','f_f_coin_minus_market_30m','f_f_oi_change_30m_pct','f_micro_volume_ratio_last_vs_prev10',
 'f_new_flow_support','f_new_micro_accel_1_vs_3','f_gate_side_ret_1m_pct','f_gate_taker_share_for_selected'
]
def ff(v,d=None):
    try:x=float(v);return x if math.isfinite(x) else d
    except:return d
def B(v):return str(v).lower()=='true'
def causal(pid,h):
    try:return int(TM[pid]['primary_label_end_ms'])>int(TM[pid][f't{h}_target_ms'])
    except:return False
def s10a_h(r):
    if r['router_lane']!='1':return None
    for h in (1,2,3):
        v=ff(TM[r['position_id']].get(f't{h}_confirm_side_return_pct'))
        if causal(r['position_id'],h) and v is not None and v>=TH:return h
    return None
def c_h(r):
    if r['router_lane']!='0':return None
    pid=r['position_id']
    if causal(pid,2) and ff(TM[pid].get('t2_delta_f_coin_minus_market_15m'),-999)>=.032030968083884837:return 2
    if causal(pid,3) and ff(TM[pid].get('t3_f_micro_decay_3_vs_prev3'),999)<=.2779031656624853:return 3
    return None
def band0(pid,k,lo,hi):
    x=ff(F0[pid].get(k));return x is not None and lo<=x<=hi
def ge0(pid,k,t):
    x=ff(F0[pid].get(k));return x is not None and x>=t
def fast(r):
    pid=r['position_id']
    if r['router_lane']!='1':return False
    return (band0(pid,'f_new_volume_over_range',1.0170781185420166,1.060973255243714) or ge0(pid,'f_new_momentum_curvature',1.2636050833333325) or band0(pid,'f_new_accel_15_vs_60',.6594,1.7240119999999999) or band0(pid,'f_context_breakdown_down_pct',.42735,.446816) or band0(pid,'f_f_oi_accel_x_overheat',-.29188090961795327,-.23281000377161334) or band0(pid,'f_f_coin_minus_market_30m',.6909331187969325,.7639814635249487))
def alt(r):
    pid=r['position_id']
    return r['router_lane']=='1' and causal(pid,3) and ff(TM[pid].get('t3_delta_micro_selected_vwap_extension_20'),-999)>=.0024105131797624857
# research S10D rows
combined=[]
for r in S8:
    ah=s10a_h(r);ch=c_h(r);fa=fast(r);al=(not (ah is not None or ch is not None) and not fa and alt(r))
    if not ((ah is not None or ch is not None) or fa or al):continue
    pid=r['position_id'];lane=0 if fa else (ah if ah is not None else ch if ch is not None else 3)
    fr=F0[pid]
    q={'id':pid,'time':int(float(fr['meta_opened_at_ms'])),'block':'Research_'+r['split'],'source':'research','split':r['split'],'lane':lane,'strong':B(r['strong_win'])}
    for f in FEATURES:q[f]=ff(fr.get(f))
    # temporal decision feature corresponding lane
    for h in (1,2,3):q[f't{h}_confirm_side_return_pct']=ff(TM[pid].get(f't{h}_confirm_side_return_pct'))
    combined.append(q)
# fresh S10D rows from funnel
for r in FF:
    if r['_d']!='True':continue
    pid=r['meta_position_id'];fr=FRESH[pid];t=int(float(fr['meta_opened_at_ms']))
    day=__import__('datetime').datetime.fromtimestamp(t/1000,__import__('datetime').timezone.utc).strftime('%Y-%m-%d')
    q={'id':pid,'time':t,'block':'Fresh_'+day,'source':'fresh','split':day,'lane':int(r['_lane']),'strong':B(r['strong_win'])}
    for f in FEATURES:q[f]=ff(fr.get(f))
    for h in (1,2,3):q[f't{h}_confirm_side_return_pct']=ff(fr.get(f't{h}_confirm_side_return_pct'))
    combined.append(q)
combined.sort(key=lambda x:(x['time'],x['id']))
print('combined',len(combined),'blocks',Counter(x['block'] for x in combined),'lanes',Counter((x['source'],x['lane']) for x in combined),flush=True)

# causal rolling normalization using PRIOR observations only. Global N=128 and lane N=64.
def pct_rank(hist,x):
    if x is None or len(hist)<20:return None
    s=sorted(hist)
    # midrank
    lo=bisect.bisect_left(s,x);hi=bisect.bisect_right(s,x)
    return (lo+hi)/(2*len(s))
def robust_z(hist,x):
    if x is None or len(hist)<20:return None
    med=statistics.median(hist)
    mad=statistics.median([abs(v-med) for v in hist])
    scale=1.4826*mad
    if scale<1e-12:
        sd=statistics.pstdev(hist)
        scale=sd if sd>1e-12 else None
    return None if not scale else (x-med)/scale

N_GLOBAL=128;N_LANE=64
hg=defaultdict(list);hl=defaultdict(list)
normcols=[]
ALLF=FEATURES+['t1_confirm_side_return_pct','t2_confirm_side_return_pct','t3_confirm_side_return_pct']
for f in ALLF:
    normcols += [f+'__pct128',f+'__rz128',f+'__lpct64',f+'__lrz64']
for row in combined:
    lane=row['lane']
    for f in ALLF:
        x=row.get(f)
        g=hg[f][-N_GLOBAL:];l=hl[(lane,f)][-N_LANE:]
        row[f+'__pct128']=pct_rank(g,x);row[f+'__rz128']=robust_z(g,x)
        row[f+'__lpct64']=pct_rank(l,x);row[f+'__lrz64']=robust_z(l,x)
    # update after calculating current row
    for f in ALLF:
        x=row.get(f)
        if x is not None:
            hg[f].append(x);hl[(lane,f)].append(x)

# block statistics for directional discrimination
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
# Monotonic tails. For percentile: low <=.2/.3/.4, high >=.6/.7/.8. z: <= -0.5/-1, >= .5/1
rules=[]
for f in ALLF:
  variants=[
   (f+'__pct128','low',.30),(f+'__pct128','high',.70),
   (f+'__lpct64','low',.30),(f+'__lpct64','high',.70),
   (f+'__rz128','low',-.5),(f+'__rz128','high',.5),
   (f+'__lrz64','low',-.5),(f+'__lrz64','high',.5)]
  for col,side,thr in variants:
    stats={}
    signs=[];valid=0
    for b in BLOCKS:
      q=[r for r in combined if r['block']==b and r.get(col) is not None]
      hit=[r for r in q if (r[col]<=thr if side=='low' else r[col]>=thr)]
      keep=[r for r in q if r not in hit]
      hs=sum(r['strong'] for r in hit);ks=sum(r['strong'] for r in keep)
      hr=hs/len(hit) if hit else None;kr=ks/len(keep) if keep else None
      delta=(hr-kr) if hr is not None and kr is not None else None
      stats[b]={'n':len(q),'hit_n':len(hit),'hit_strong':hs,'hit_rate':hr,'keep_n':len(keep),'keep_strong':ks,'keep_rate':kr,'delta':delta}
      if delta is not None and len(hit)>=5 and len(keep)>=5:
        valid+=1;signs.append(1 if delta>0 else -1 if delta<0 else 0)
    consistent = valid>=5 and (all(s<=0 for s in signs) or all(s>=0 for s in signs))
    # suppressor wants hit lower strong rate than keep: negative delta
    negblocks=sum(1 for b in BLOCKS if stats[b]['delta'] is not None and stats[b]['delta']<0)
    posblocks=sum(1 for b in BLOCKS if stats[b]['delta'] is not None and stats[b]['delta']>0)
    mean_delta=statistics.mean([stats[b]['delta'] for b in BLOCKS if stats[b]['delta'] is not None]) if valid else None
    rules.append({'feature':f,'column':col,'side':side,'threshold':thr,'valid_blocks':valid,'negative_blocks':negblocks,'positive_blocks':posblocks,'consistent':consistent,'mean_delta':mean_delta,'stats':stats})
# rank suppressor candidates: all/5-6 blocks negative, meaningful mean drop
rank=[r for r in rules if r['valid_blocks']>=5]
rank.sort(key=lambda r:(-r['negative_blocks'],r['positive_blocks'], r['mean_delta'] if r['mean_delta'] is not None else 999))
print('\\nTOP STABLE SUPPRESSOR DIRECTIONS')
for r in rank[:40]:
    print(r['column'],r['side'],r['threshold'],'neg',r['negative_blocks'],'pos',r['positive_blocks'],'mean_delta',round(r['mean_delta'],4))
    print(' ',[(b,round(r['stats'][b]['delta'],4) if r['stats'][b]['delta'] is not None else None,r['stats'][b]['hit_n']) for b in BLOCKS])

# compare failed raw rule directions explicitly by same blocks
FAILED=[
 ('overheat_band','f_new_overheat_pressure','band',4.0018436068809455,4.470349182901625),
 ('t1_accel_band','f_new_accel_15_vs_60','band',.23479833333333333,.42964424999999995),
 ('t1_vol_range_band','f_new_volume_over_range','band',1.6920917148647434,2.7757644232664087),
 ('t1_price_drift_band','f_gate_price_drift_pct','band',.07936507936507908,.19951230325869762),
 ('t2_side_ret_band','t2_confirm_side_return_pct','band',.07608306480486604,.09980039920158834),
 ('t2_taker_accel_band','f_f_taker_accel_1m','band',.09303476722726256,.2024488044201611),
 ('t2_gate_px_flow_band','f_new_gate_price_x_flow_gap','band',.0035063885726661333,.0324416175051618)]
raw_stats=[]
for name,f,typ,lo,hi in FAILED:
    z={'name':name,'feature':f,'blocks':{}}
    for b in BLOCKS:
      q=[r for r in combined if r['block']==b and r.get(f) is not None]
      # apply lane scope for T1/T2 rules
      if name.startswith('t1_'):q=[r for r in q if r['lane']==1]
      if name.startswith('t2_'):q=[r for r in q if r['lane']==2]
      hit=[r for r in q if lo<=r[f]<=hi];keep=[r for r in q if r not in hit]
      hr=sum(r['strong'] for r in hit)/len(hit) if hit else None;kr=sum(r['strong'] for r in keep)/len(keep) if keep else None
      z['blocks'][b]={'hit_n':len(hit),'hit_rate':hr,'keep_n':len(keep),'keep_rate':kr,'delta':None if hr is None or kr is None else hr-kr}
    raw_stats.append(z)
print('\\nFAILED RAW BANDS')
for z in raw_stats:
 print(z['name'],[(b,round(z['blocks'][b]['delta'],4) if z['blocks'][b]['delta'] is not None else None,z['blocks'][b]['hit_n']) for b in BLOCKS])

out={'stage':'S10J-1-3','baseline':'S10D + V4.3 SHORT-LS4 + BE0.10 frozen','normalization':{'global_window':128,'lane_window':64,'prior_only':True,'min_history':20,'methods':['empirical_percentile','robust_z_median_mad']},'blocks':BLOCKS,'top_rules':rank[:80],'failed_raw_bands':raw_stats}
Path('/tmp/s10j_normalized_scan.json').write_text(json.dumps(out,indent=2))
# write combined normalized detail
fields=['id','time','block','source','split','lane','strong']+ALLF+normcols
with open('/tmp/s10j_normalized_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k,'') for k in fields} for r in combined])