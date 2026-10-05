from __future__ import annotations
import csv,json,math,statistics
from collections import Counter
from pathlib import Path
from sklearn.metrics import roc_auc_score

UNIV=Path('/work/sd2b1/research/short_detector/results/sd1a_short_universe_655.csv')
WA=Path('/work/sd2b1/research/short_detector/results/sd1c_strong_winner_assignments.csv')
LA=Path('/work/sd2b1/research/short_detector/results/sd1d_loss_cluster_assignments.csv')
TEMP=Path('/data/wd5h4a_temporal_features.csv')
OUT=Path('/work/sd2b1_out'); OUT.mkdir(parents=True,exist_ok=True)

CANON=[
'confirm_side_return_pct','confirm_selected_taker_share',
'f_micro_side_ret_1m','f_micro_side_ret_3m','f_micro_side_ret_5m',
'f_micro_selected_taker_share_1m','f_micro_selected_taker_share_3m',
'f_micro_selected_vwap_extension_20','f_micro_reversal_pressure',
'f_f_market_dispersion_15m','f_f_coin_minus_market_15m',
'f_f_coin_residual_5m_vs_btc','f_f_taker_selected_share_3m',
'f_f_selected_slope5_norm','delta_micro_side_ret_1m',
'delta_micro_side_ret_3m','delta_micro_selected_taker_share_3m',
'delta_micro_selected_vwap_extension_20','delta_f_coin_minus_market_15m',
'delta_f_coin_residual_5m_vs_btc']
SPLITS=['Discovery','Validation','Reserve']

def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def truth(v): return str(v).lower() in ('1','true','yes')
def ff(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except:return None
def auc(y,x):
 pairs=[(a,b) for a,b in zip(y,x) if b is not None]
 if len(pairs)<4 or len({a for a,b in pairs})<2:return None
 try:return float(roc_auc_score([a for a,b in pairs],[b for a,b in pairs]))
 except:return None
def med(vals):
 vals=[x for x in vals if x is not None]
 return float(statistics.median(vals)) if vals else None

u=read(UNIV); wa=read(WA); la=read(LA); t=read(TEMP)
tm={r['position_id']:r for r in t}
wc={r['position_id']:int(r['cluster']) for r in wa}
lc={r['position_id']:int(r['loss_cluster']) for r in la}
wins=[r for r in u if truth(r['strong_win'])]
loss=[r for r in u if r['primary_meta_label']=='META_LOSS']

rows=[]; summaries=[]; feature_rows=[]
earliest={0:None,1:None}
for lane in (0,1):
 for h in (1,2,3):
  hp=f't{h}_'
  # freeze directions from Discovery only
  D=[]
  for cls,pop,cm in [(1,wins,wc),(0,loss,lc)]:
   for r in pop:
    if r['split']!='Discovery' or cm[r['position_id']]!=lane:continue
    tr=tm[r['position_id']]
    target=int(tr[f't{h}_target_ms'])
    end=int(tr['primary_label_end_ms'])
    if end<=target:continue
    D.append((r,cls,tr))
  dirs={}
  for base in CANON:
   col=hp+base
   y=[cls for r,cls,tr in D]; x=[ff(tr.get(col)) for r,cls,tr in D]
   a=auc(y,x)
   if a is not None:dirs[base]='HIGH' if a>=.5 else 'LOW'

  for sp in SPLITS:
   eligible=[]
   frozen_total=0
   for cls,pop,cm in [(1,wins,wc),(0,loss,lc)]:
    gp=[r for r in pop if r['split']==sp and cm[r['position_id']]==lane]
    frozen_total+=len(gp)
    for r in gp:
     tr=tm[r['position_id']]
     target=int(tr[f't{h}_target_ms']); end=int(tr['primary_label_end_ms'])
     if end<=target:continue
     if tr.get(f't{h}_confirm_side_return_pct') in ('',None):continue
     eligible.append((r,cls,tr))
   wn=sum(cls==1 for r,cls,tr in eligible); ln=sum(cls==0 for r,cls,tr in eligible)
   sideW=[ff(tr[f't{h}_confirm_side_return_pct']) for r,cls,tr in eligible if cls==1]
   sideL=[ff(tr[f't{h}_confirm_side_return_pct']) for r,cls,tr in eligible if cls==0]
   mfeW=[ff(tr[f't{h}_confirm_mfe_pct']) for r,cls,tr in eligible if cls==1]
   mfeL=[ff(tr[f't{h}_confirm_mfe_pct']) for r,cls,tr in eligible if cls==0]
   maeW=[ff(tr[f't{h}_confirm_mae_pct']) for r,cls,tr in eligible if cls==1]
   maeL=[ff(tr[f't{h}_confirm_mae_pct']) for r,cls,tr in eligible if cls==0]
   takW=[ff(tr[f't{h}_confirm_selected_taker_share']) for r,cls,tr in eligible if cls==1]
   takL=[ff(tr[f't{h}_confirm_selected_taker_share']) for r,cls,tr in eligible if cls==0]
   failmix=Counter(r['historical_wd1_outcome'] for r,cls,tr in eligible if cls==0)
   summaries.append({
    'lane':lane,'horizon':f'T+{h}','split':sp,'eligible_n':len(eligible),
    'winner_n':wn,'loss_n':ln,'coverage_pct':100*len(eligible)/frozen_total if frozen_total else None,
    'winner_side_return_median':med(sideW),'loss_side_return_median':med(sideL),
    'winner_mfe_median':med(mfeW),'loss_mfe_median':med(mfeL),
    'winner_mae_median':med(maeW),'loss_mae_median':med(maeL),
    'winner_taker_share_median':med(takW),'loss_taker_share_median':med(takL),
    'failure_wd1_mix':dict(failmix)
   })
   for base in CANON:
    col=hp+base; direction=dirs.get(base)
    if direction is None:continue
    y=[cls for r,cls,tr in eligible]; x=[ff(tr.get(col)) for r,cls,tr in eligible]
    raw=auc(y,x)
    oriented=(raw if direction=='HIGH' else 1-raw) if raw is not None else None
    wvals=[ff(tr.get(col)) for r,cls,tr in eligible if cls==1]
    lvals=[ff(tr.get(col)) for r,cls,tr in eligible if cls==0]
    feature_rows.append({'lane':lane,'horizon':f'T+{h}','split':sp,'feature':base,
      'frozen_direction':direction,'raw_auc':raw,'oriented_auc':oriented,
      'winner_median':med(wvals),'loss_median':med(lvals),'winner_n':wn,'loss_n':ln})

# stability rollup
roll=[]
for lane in (0,1):
 for h in (1,2,3):
  hs=f'T+{h}'
  for feat in CANON:
   rr=[r for r in feature_rows if r['lane']==lane and r['horizon']==hs and r['feature']==feat]
   by={r['split']:r for r in rr}
   if not all(s in by and by[s]['oriented_auc'] is not None for s in SPLITS):continue
   vals=[by[s]['oriented_auc'] for s in SPLITS]
   roll.append({'lane':lane,'horizon':hs,'feature':feat,'frozen_direction':by['Discovery']['frozen_direction'],
     'D_auc':vals[0],'V_auc':vals[1],'R_auc':vals[2],
     'DV_floor':min(vals[:2]),'DVR_floor':min(vals),
     'all_ge_060':all(x>=.60 for x in vals)})
for lane in (0,1):
 candidates=[r for r in roll if r['lane']==lane and r['all_ge_060']]
 if candidates:
  candidates.sort(key=lambda r:(int(r['horizon'][-1]),-r['DVR_floor']))
  earliest[lane]=candidates[0]['horizon']

best={}
for lane in (0,1):
 g=[r for r in roll if r['lane']==lane]
 best[lane]=max(g,key=lambda r:r['DVR_floor']) if g else None

with (OUT/'sd2b1_causal_coverage_anatomy.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
with (OUT/'sd2b1_canonical_feature_auc.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(feature_rows[0]));w.writeheader();w.writerows(feature_rows)
with (OUT/'sd2b1_temporal_stability_rollup.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(roll[0]));w.writeheader();w.writerows(roll)

payload={'stage':'SD-2B1','status':'ANATOMY_COMPLETE','earliest_all_split_ge_060':earliest,
 'best_all_split_feature':best,'coverage':summaries,
 'top_by_lane_horizon':{}}
for lane in (0,1):
 for h in (1,2,3):
  key=f'lane{lane}_T+{h}'
  g=[r for r in roll if r['lane']==lane and r['horizon']==f'T+{h}']
  payload['top_by_lane_horizon'][key]=sorted(g,key=lambda r:r['DVR_floor'],reverse=True)[:10]
(OUT/'sd2b1_summary.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
print(json.dumps(payload,indent=2))