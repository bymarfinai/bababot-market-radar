import csv,json,math
S=json.load(open('/tmp/ct2_summary.json'))
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
F={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
def c(r,h):
 try:return int(float(r['primary_label_end_ms']))>int(float(r[f't{h}_target_ms']))
 except:return False
for th in ['0.075000','0.100000']:
 print('\nTH',th)
 for src in ['research','fresh']:
  print(src)
  for x in S['thresholds'][th][src]['strong_removed_anatomy']:
   r=TM[x['id']] if src=='research' else F[x['id']]
   print(x['symbol'],x['block'],'baseLane',x['base_lane'],'pnl',round(x['baseline_pnl'],2) if x['baseline_pnl'] is not None else None,
         't1',x['t1'],'c1',c(r,1),'t2',x['t2'],'c2',c(r,2),'t3',x['t3'],'c3',c(r,3),
         'label_end',r['primary_label_end_ms'])