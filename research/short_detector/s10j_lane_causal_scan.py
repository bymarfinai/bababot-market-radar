import csv,json,statistics
from pathlib import Path
rows=list(csv.DictReader(open('/tmp/s10j_normalized_detail.csv')))
def fv(r,k):
    try:return float(r[k])
    except:return None
def strong(r):return r['strong']=='True'
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
BASE=[
 'f_new_overheat_pressure','f_new_accel_15_vs_60','f_new_volume_over_range','f_gate_price_drift_pct',
 'f_f_taker_accel_1m','f_new_gate_price_x_flow_gap','f_new_momentum_curvature','f_context_breakdown_down_pct',
 'f_f_oi_accel_x_overheat','f_f_coin_minus_market_30m','f_f_oi_change_30m_pct','f_micro_volume_ratio_last_vs_prev10',
 'f_new_flow_support','f_new_micro_accel_1_vs_3','f_gate_side_ret_1m_pct','f_gate_taker_share_for_selected']
allowed={
 0:BASE,
 1:BASE+['t1_confirm_side_return_pct'],
 2:BASE+['t1_confirm_side_return_pct','t2_confirm_side_return_pct'],
 3:BASE+['t1_confirm_side_return_pct','t2_confirm_side_return_pct','t3_confirm_side_return_pct']}
variants=[]
for lane,fs in allowed.items():
  for f in fs:
    variants += [
      (lane,f,f+'__pct128','low',.30),(lane,f,f+'__pct128','high',.70),
      (lane,f,f+'__lpct64','low',.30),(lane,f,f+'__lpct64','high',.70),
      (lane,f,f+'__rz128','low',-.5),(lane,f,f+'__rz128','high',.5),
      (lane,f,f+'__lrz64','low',-.5),(lane,f,f+'__lrz64','high',.5)]
out=[]
for lane,f,col,side,thr in variants:
  st={};valid=0;neg=pos=0;deltas=[]
  for b in BLOCKS:
    q=[r for r in rows if int(r['lane'])==lane and r['block']==b and fv(r,col) is not None]
    hit=[r for r in q if (fv(r,col)<=thr if side=='low' else fv(r,col)>=thr)]
    keep=[r for r in q if r not in hit]
    hr=sum(strong(r) for r in hit)/len(hit) if hit else None
    kr=sum(strong(r) for r in keep)/len(keep) if keep else None
    delta=None if hr is None or kr is None else hr-kr
    # require at least 3 hits/keeps to count small research lane blocks
    if delta is not None and len(hit)>=3 and len(keep)>=3:
      valid+=1;deltas.append(delta);neg+=delta<0;pos+=delta>0
    st[b]={'n':len(q),'hit_n':len(hit),'hit_strong':sum(strong(r) for r in hit),'hit_rate':hr,'keep_n':len(keep),'keep_strong':sum(strong(r) for r in keep),'keep_rate':kr,'delta':delta}
  out.append({'lane':lane,'feature':f,'column':col,'side':side,'threshold':thr,'valid_blocks':valid,'negative_blocks':neg,'positive_blocks':pos,'mean_delta':statistics.mean(deltas) if deltas else None,'stats':st})
# stable candidates require no positive among valid blocks and >=4 valid, or 5/6 negative max1 pos
stable=[x for x in out if x['valid_blocks']>=4 and x['negative_blocks']>=min(5,x['valid_blocks']) and x['positive_blocks']<=1]
stable.sort(key=lambda x:(x['positive_blocks'],-x['negative_blocks'],x['mean_delta'] if x['mean_delta'] is not None else 999))
for lane in range(4):
  print('\n### LANE',lane)
  q=[x for x in stable if x['lane']==lane]
  for x in q[:20]:
    print(x['column'],x['side'],x['threshold'],'valid',x['valid_blocks'],'neg',x['negative_blocks'],'pos',x['positive_blocks'],'mean',round(x['mean_delta'],4))
    print(' ',[(b,round(x['stats'][b]['delta'],4) if x['stats'][b]['delta'] is not None else None,x['stats'][b]['hit_n']) for b in BLOCKS])
  print('stable_n',len(q))
# raw gate_px_flow special T2 comparison + normalized variants
Path('/tmp/s10j_lane_causal_scan.json').write_text(json.dumps({'stage':'S10J3_LANE_CAUSAL','blocks':BLOCKS,'stable':stable,'all':out},indent=2))