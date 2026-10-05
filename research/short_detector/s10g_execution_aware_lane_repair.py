import csv,json,math,collections
ROWS=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10E']
F0={r['meta_position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h1_thesis_labeled_features.csv'))}
TM={r['position_id']:r for r in csv.DictReader(open('/opt/core-app/data/wd5h4a_temporal_features.csv'))}
def af(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def band(v,lo,hi):
    x=af(v);return x is not None and lo<=x<=hi
def lane(r):return 'T0' if r['entry_kind']=='T0' else 'T+'+r['entry_horizon']
def veto1(pid):
    return (
      band(F0[pid].get('f_new_accel_15_vs_60'),0.23479833333333333,0.42964424999999995) or
      band(F0[pid].get('f_new_volume_over_range'),1.6920917148647434,2.7757644232664087) or
      band(F0[pid].get('f_gate_price_drift_pct'),0.07936507936507908,0.19951230325869762)
    )
def veto2(pid):
    return (
      band(TM[pid].get('t2_confirm_side_return_pct'),0.07608306480486604,0.09980039920158834) or
      band(F0[pid].get('f_f_taker_accel_1m'),0.09303476722726256,0.2024488044201611) or
      band(F0[pid].get('f_new_gate_price_x_flow_gap'),0.0035063885726661333,0.0324416175051618)
    )
for r in ROWS:
    l=lane(r);r['_veto']=(l=='T+1' and veto1(r['position_id'])) or (l=='T+2' and veto2(r['position_id']))
keep=[r for r in ROWS if not r['_veto']];veto=[r for r in ROWS if r['_veto']]
def count(g):
    return {'n':len(g),'strong':sum(r['strong_win']=='True' for r in g),'non':sum(r['strong_win']=='False' for r in g)}
def exmet(g):
    q=[r for r in g if r['executable']=='True'];vals=[float(r['COMP_pnl']) for r in q]
    return {'selected_n':len(g),'selected_strong':sum(r['strong_win']=='True' for r in g),'executable_n':len(q),
            'strong_executable':sum(r['strong_win']=='True' for r in q),'non_target_executable':sum(r['strong_win']=='False' for r in q),
            'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals),
            'gp':sum(v for v in vals if v>0),'gl':sum(v for v in vals if v<0),
            'noexec_n':sum(r['executable']!='True' for r in g),'noexec_strong':sum(r['executable']!='True' and r['strong_win']=='True' for r in g)}
print('BASE',exmet(ROWS));print('KEEP',exmet(keep));print('VETO',exmet(veto))
for l in ['T0','T+1','T+2','T+3']:
    k=[r for r in keep if lane(r)==l];v=[r for r in veto if lane(r)==l]
    print('\\nLANE',l,'KEEP',exmet(k),'VETO',exmet(v))
for sp in ['Discovery','Validation','Reserve']:
    k=[r for r in keep if r['split']==sp];v=[r for r in veto if r['split']==sp]
    print('\\nSPLIT',sp,'KEEP',exmet(k),'VETO',exmet(v))
print('\\nVETO STRONG')
for r in veto:
    if r['strong_win']=='True':
        print(r['symbol'],r['split'],lane(r),'exec',r['executable'],'pnl',r.get('COMP_pnl'))
# save
summary={'stage':'SHORT-S10G','status':'PASS_RESEARCH_EXECUTION_AWARE_REPAIR','baseline':exmet(ROWS),'after_repair':exmet(keep),'veto_total':exmet(veto),
         'lanes':{l:{'keep':exmet([r for r in keep if lane(r)==l]),'veto':exmet([r for r in veto if lane(r)==l])} for l in ['T0','T+1','T+2','T+3']},
         'splits':{sp:{'keep':exmet([r for r in keep if r['split']==sp]),'veto':exmet([r for r in veto if r['split']==sp])} for sp in ['Discovery','Validation','Reserve']},
         'rules':{
          'T+1_OR':[
           'f_new_accel_15_vs_60 in [0.23479833333333333,0.42964424999999995]',
           'f_new_volume_over_range in [1.6920917148647434,2.7757644232664087]',
           'f_gate_price_drift_pct in [0.07936507936507908,0.19951230325869762]'],
          'T+2_OR':[
           't2_confirm_side_return_pct in [0.07608306480486604,0.09980039920158834]',
           'f_f_taker_accel_1m in [0.09303476722726256,0.2024488044201611]',
           'f_new_gate_price_x_flow_gap in [0.0035063885726661333,0.0324416175051618]']
         }}
open('/tmp/s10g_summary.json','w').write(json.dumps(summary,indent=2))
fields=[]
for r in veto:
    q={k:v for k,v in r.items() if not k.startswith('_')}
    for k in q:
        if k not in fields:fields.append(k)
with open('/tmp/s10g_veto_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:v for k,v in r.items() if not k.startswith('_')} for r in veto])