from __future__ import annotations
import csv,json,math,statistics
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,accuracy_score,confusion_matrix
from sklearn.preprocessing import StandardScaler

ROOT=Path('/work/sds8')
UNIV=ROOT/'research/short_detector/results/sd1a_short_universe_655.csv'
WA=ROOT/'research/short_detector/results/sd1c_strong_winner_assignments.csv'
LA=ROOT/'research/short_detector/results/sd1d_loss_cluster_assignments.csv'
F0=Path('/data/wd5h1_thesis_labeled_features.csv')
TEMP=Path('/data/wd5h4a_temporal_features.csv')
OUT=Path('/work/sds8_out');OUT.mkdir(parents=True,exist_ok=True)

FEATURES=[
'f_gate_flow_family',
'f_gate_taker_share_for_selected',
'f_gate_side_ret_1m_pct',
'f_new_flow_support',
'f_new_micro_accel_1_vs_3',
'f_f_coin_minus_market_30m',
'f_f_oi_change_30m_pct',
'f_micro_volume_ratio_last_vs_prev10',
]
CAT='f_gate_flow_family'
NUM=[x for x in FEATURES if x!=CAT]
SPLITS=['Discovery','Validation','Reserve']
THR=0.0338983050847

def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def truth(v):return str(v).strip().lower() in ('1','true','yes')
def ff(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except:return None
def pct(a,b):return 100*a/b if b else 0.0

u=read(UNIV); wa=read(WA); la=read(LA); frows=read(F0); trows=read(TEMP)
assert len(u)==655
fm={r['meta_position_id']:r for r in frows}
tm={r['position_id']:r for r in trows}
wlab={r['position_id']:int(r['cluster']) for r in wa}
llab={r['position_id']:int(r['loss_cluster']) for r in la}
assert len(wlab)==99 and len(llab)==492

# Anatomy lane labels only; weak winners are inference-only.
lane_label={}
lane_label.update(wlab);lane_label.update(llab)

# Discovery-only preprocessing.
D=[r for r in u if r['split']=='Discovery' and r['position_id'] in lane_label]
assert len(D)==354

med={}
for c in NUM:
 vals=[ff(fm[r['position_id']].get(c)) for r in D]
 fin=[x for x in vals if x is not None]
 assert len(fin)/len(vals)>=0.95,(c,len(fin),len(vals))
 med[c]=float(statistics.median(fin))

cat_levels=sorted({fm[r['position_id']].get(CAT,'') for r in D})
assert cat_levels

def raw_matrix(rows):
 out=[]
 for r in rows:
  fr=fm[r['position_id']]
  x=[med[c] if ff(fr.get(c)) is None else ff(fr.get(c)) for c in NUM]
  x += [1.0 if fr.get(CAT,'')==lvl else 0.0 for lvl in cat_levels]
  out.append(x)
 return np.asarray(out,float)

XD_raw=raw_matrix(D)
# Scale numerics only; leave one-hots unscaled, like simple LONG-style T0 router.
sc=StandardScaler().fit(XD_raw[:,:len(NUM)])
def transform(rows):
 X=raw_matrix(rows)
 X[:,:len(NUM)]=sc.transform(X[:,:len(NUM)])
 return X

XD=transform(D); yD=np.asarray([lane_label[r['position_id']] for r in D],int)
model=LogisticRegression(
 penalty='l2',C=0.1,solver='liblinear',class_weight='balanced',
 random_state=4104,max_iter=5000
).fit(XD,yD)

router_metrics={}
for sp in SPLITS:
 rows=[r for r in u if r['split']==sp and r['position_id'] in lane_label]
 X=transform(rows); y=np.asarray([lane_label[r['position_id']] for r in rows],int)
 prob=model.predict_proba(X)[:,1]; pred=(prob>=0.5).astype(int)
 router_metrics[sp]={
  'n':len(rows),'lane0_true':int((y==0).sum()),'lane1_true':int((y==1).sum()),
  'auc':float(roc_auc_score(y,prob)),'accuracy':float(accuracy_score(y,pred)),
  'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist(),
  'pred_lane0':int((pred==0).sum()),'pred_lane1':int((pred==1).sum()),
 }

# Apply frozen router to all 655.
Xall=transform(u); proball=model.predict_proba(Xall)[:,1]; predall=(proball>=0.5).astype(int)

detail=[]
for r,prob,route in zip(u,proball,predall):
 pid=r['position_id']; strong=truth(r['strong_win'])
 tr=tm[pid]
 t3_present=ff(tr.get('t3_confirm_side_return_pct')) is not None
 t3_target=ff(tr.get('t3_target_ms'))
 end=ff(tr.get('primary_label_end_ms'))
 causal=bool(t3_present and t3_target is not None and end is not None and end>t3_target)
 side_ret=ff(tr.get('t3_confirm_side_return_pct'))
 selected=False
 reason=''
 if int(route)==0:
  reason='ROUTE0_NO_ACCEPTED_SELECTOR'
 else:
  if not causal:
   reason='ROUTE1_T3_NOT_CAUSAL'
  elif side_ret is None:
   reason='ROUTE1_T3_MISSING'
  elif side_ret < THR:
   reason='ROUTE1_T3_THRESHOLD_FAIL'
  else:
   selected=True;reason='OPEN_ROUTE1_T3_PASS'
 hist_pnl=float(r['historical_realized_pnl_usdt'])
 hist_ret=float(r['historical_realized_pnl_pct'])
 mfe=float(r['historical_max_mfe_pct'])
 detail.append({
  'position_id':pid,'symbol':r['symbol'],'split':r['split'],
  'primary_meta_label':r['primary_meta_label'],'strong_win':strong,
  'router_probability_lane1':float(prob),'router_lane':int(route),
  'anatomy_lane':lane_label.get(pid,''),
  't3_causal':causal,'t3_confirm_side_return_pct':side_ret if side_ret is not None else '',
  'selected':selected,'selection_reason':reason,
  'historical_realized_pnl_usdt':hist_pnl,'historical_realized_pnl_pct':hist_ret,
  'historical_max_mfe_pct':mfe,
  'historical_realized_positive':hist_pnl>0,
  'peak_mfe_equiv_usdt':mfe*5.0,
 })

selected=[r for r in detail if r['selected']]
strong_all=[r for r in detail if r['strong_win']]
strong_sel=[r for r in selected if r['strong_win']]
non_sel=[r for r in selected if not r['strong_win']]
weak_sel=[r for r in selected if r['primary_meta_label']=='META_WIN' and not r['strong_win']]
loss_sel=[r for r in selected if r['primary_meta_label']=='META_LOSS']
prof_non=[r for r in non_sel if r['historical_realized_pnl_usdt']>0]
realpos=[r for r in selected if r['historical_realized_pnl_usdt']>0]

def metrics(rows, target_den=None, baseline_prev=None):
 n=len(rows)
 strong=sum(r['strong_win'] for r in rows)
 pnl=sum(r['historical_realized_pnl_usdt'] for r in rows)
 return {
  'n':n,'strong_win_n':strong,
  'precision':strong/n if n else 0.0,
  'recall':strong/target_den if target_den else None,
  'historical_realized_positive_n':sum(r['historical_realized_pnl_usdt']>0 for r in rows),
  'historical_wr':sum(r['historical_realized_pnl_usdt']>0 for r in rows)/n if n else 0.0,
  'historical_pnl_usdt':pnl,
  'historical_avg_return_pct':sum(r['historical_realized_pnl_pct'] for r in rows)/n if n else 0.0,
  'peak_mfe_equiv_usdt':sum(r['peak_mfe_equiv_usdt'] for r in rows),
  'precision_lift':((strong/n)/baseline_prev) if n and baseline_prev else None,
 }

split_results={}
for sp in SPLITS:
 pop=[r for r in detail if r['split']==sp]
 sel=[r for r in pop if r['selected']]
 targ=sum(r['strong_win'] for r in pop)
 base=targ/len(pop)
 split_results[sp]={
  'candidates':len(pop),'strong_win_total':targ,'baseline_prevalence':base,
  **metrics(sel,target_den=targ,baseline_prev=base),
  'non_target_n':sum(not r['strong_win'] for r in sel),
  'profitable_non_target_n':sum((not r['strong_win']) and r['historical_realized_pnl_usdt']>0 for r in sel),
 }

lane_results={}
for lane in (0,1):
 pop=[r for r in detail if r['router_lane']==lane]
 sel=[r for r in pop if r['selected']]
 lane_results[str(lane)]={
  'routed_candidates':len(pop),'strong_win_total_routed':sum(r['strong_win'] for r in pop),
  'open_n':len(sel),'strong_win_captured':sum(r['strong_win'] for r in sel),
  'non_target_selected':sum(not r['strong_win'] for r in sel),
 }

reason_counts={}
for reason,grp in __import__('itertools').groupby(sorted(detail,key=lambda x:x['selection_reason']),key=lambda x:x['selection_reason']):
 g=list(grp)
 reason_counts[reason]={
  'n':len(g),'strong_win_n':sum(r['strong_win'] for r in g),
  'non_target_n':sum(not r['strong_win'] for r in g),
 }

baseline_prev=99/655
overall={
 'candidates':655,'strong_win_total':99,'baseline_prevalence':baseline_prev,
 'open_n':len(selected),'strong_win_captured':len(strong_sel),
 'strong_win_recall':len(strong_sel)/99,'non_target_selected':len(non_sel),
 'precision':len(strong_sel)/len(selected) if selected else 0.0,
 'precision_lift':((len(strong_sel)/len(selected))/baseline_prev) if selected else 0.0,
 'weak_meta_win_selected':len(weak_sel),'meta_loss_selected':len(loss_sel),
 'profitable_non_target_n':len(prof_non),
 'historical_realized_positive_n':len(realpos),
 'historical_wr':len(realpos)/len(selected) if selected else 0.0,
 'historical_pnl_usdt':sum(r['historical_realized_pnl_usdt'] for r in selected),
 'historical_avg_return_pct':sum(r['historical_realized_pnl_pct'] for r in selected)/len(selected) if selected else 0.0,
 'peak_mfe_equiv_usdt':sum(r['peak_mfe_equiv_usdt'] for r in selected),
}

target_anatomy={
 'selected_strong':metrics(strong_sel,target_den=99,baseline_prev=None),
 'selected_non_target':metrics(non_sel,target_den=None,baseline_prev=None),
}

# Write files.
with (OUT/'sds8_unified_655_detail.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(detail)
with (OUT/'sds8_open_baseline.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(selected)
with (OUT/'sds8_missed_strong_winners.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows([r for r in detail if r['strong_win'] and not r['selected']])

summary={
 'stage':'SHORT-S8',
 'status':'COMPLETE',
 'router':{
   'features':FEATURES,'categorical_levels':cat_levels,'C':0.1,
   'train_n':len(D),'coefficients':{
      **{c:float(model.coef_[0][i]) for i,c in enumerate(NUM)},
      **{f'{CAT}=={lvl}':float(model.coef_[0][len(NUM)+j]) for j,lvl in enumerate(cat_levels)}
   },'intercept':float(model.intercept_[0]),
   'metrics':router_metrics,
   'all655_predicted_lane_counts':{
      'lane0':int((predall==0).sum()),'lane1':int((predall==1).sum())
   }
 },
 'policy':{
   'lane0':'NO_ACCEPTED_SELECTOR',
   'lane1':'causal T+3 confirm_side_return_pct >= 0.0338983050847%',
 },
 'overall':overall,'splits':split_results,'lanes':lane_results,
 'selection_reasons':reason_counts,'opportunity_anatomy':target_anatomy,
}
(OUT/'sds8_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))