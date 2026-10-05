import csv,json,math
from collections import Counter
from pathlib import Path
ROWS=list(csv.DictReader(open('/tmp/s10j_normalized_detail.csv')))
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
def fv(r,k):
 try:
  x=float(r[k]);return x if math.isfinite(x) else None
 except:return None
def strong(r):return r['strong']=='True'
def met(q):
 s=sum(strong(r) for r in q);return {'n':len(q),'strong':s,'non':len(q)-s,'precision':s/len(q) if q else 0}
def veto_primary(r):
 lane=int(r['lane'])
 if lane==1:
  x=fv(r,'f_micro_volume_ratio_last_vs_prev10__pct128')
  return x is not None and x<=.30
 if lane==3:
  x=fv(r,'t3_confirm_side_return_pct__pct128')
  return x is not None and x<=.30
 return False
def veto_conservative(r):
 return int(r['lane'])==1 and fv(r,'f_micro_volume_ratio_last_vs_prev10__pct128') is not None and fv(r,'f_micro_volume_ratio_last_vs_prev10__pct128')<=.30
def veto_challenger_t2(r):
 if veto_conservative(r):return True
 return int(r['lane'])==2 and fv(r,'t2_confirm_side_return_pct__pct128') is not None and fv(r,'t2_confirm_side_return_pct__pct128')<=.30
cands={'PRIMARY_V2':veto_primary,'CONSERVATIVE_T1_ONLY':veto_conservative,'CHALLENGER_T1_PLUS_T2':veto_challenger_t2}
summary={'stage':'S10J4','status':'SUPPRESSOR_V2_PRIMARY_FROZEN_FOR_J5_REPLAY','baseline':'S10D','protector':'V4.3 SHORT-LS4 + BE0.10 frozen','candidates':{}}
for name,fn in cands.items():
 z={'overall':{},'blocks':{},'lanes':{}}
 for source in ['research','fresh','all']:
  q=ROWS if source=='all' else [r for r in ROWS if r['source']==source]
  v=[r for r in q if fn(r)];k=[r for r in q if not fn(r)]
  bm=met(q);vm=met(v);km=met(k)
  z['overall'][source]={'base':bm,'veto':vm,'keep':km,'strong_retention':km['strong']/bm['strong'],'non_target_removal':vm['non']/bm['non'],'precision_delta':km['precision']-bm['precision']}
 for b in BLOCKS:
  q=[r for r in ROWS if r['block']==b];v=[r for r in q if fn(r)];k=[r for r in q if not fn(r)]
  bm=met(q);vm=met(v);km=met(k)
  z['blocks'][b]={'base':bm,'veto':vm,'keep':km,'strong_retention':km['strong']/bm['strong'] if bm['strong'] else 1,'non_target_removal':vm['non']/bm['non'] if bm['non'] else 0,'precision_delta':km['precision']-bm['precision']}
 for lane in [0,1,2,3]:
  q=[r for r in ROWS if int(r['lane'])==lane];v=[r for r in q if fn(r)];k=[r for r in q if not fn(r)]
  z['lanes'][str(lane)]={'base':met(q),'veto':met(v),'keep':met(k)}
 summary['candidates'][name]=z
summary['primary_rules']=[
 {'lane':'T+1','feature':'f_micro_volume_ratio_last_vs_prev10','normalization':'causal empirical percentile vs prior 128 S10D-selected trades','action':'VETO if percentile <= 0.30'},
 {'lane':'T+3','feature':'t3_confirm_side_return_pct','normalization':'causal empirical percentile vs prior 128 S10D-selected trades','action':'VETO if percentile <= 0.30'}]
summary['not_used']=[
 'No T0 suppressor: no 6/6 clean normalized candidate.',
 'No S10E/S10G absolute hard bands.',
 'No T+2 rule in primary: T2 normalized candidates were either weaker or had limited research support.',
 'No OR of T+1 overheat + micro-volume: fresh strong retention fell below 90%.']
Path('/tmp/s10j4_summary.json').write_text(json.dumps(summary,indent=2))
# detail
out=[]
for r in ROWS:
 q={k:r.get(k,'') for k in ['id','time','block','source','split','lane','strong']}
 q['primary_veto']=veto_primary(r);q['conservative_veto']=veto_conservative(r);q['challenger_t2_veto']=veto_challenger_t2(r)
 q['t1_microvol_pct128']=r.get('f_micro_volume_ratio_last_vs_prev10__pct128','')
 q['t2_confirm_pct128']=r.get('t2_confirm_side_return_pct__pct128','')
 q['t3_confirm_pct128']=r.get('t3_confirm_side_return_pct__pct128','')
 out.append(q)
with open('/tmp/s10j4_veto_detail.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps(summary['candidates']['PRIMARY_V2'],indent=2))