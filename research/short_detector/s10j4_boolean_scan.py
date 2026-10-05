import csv,json,math,itertools
ROWS=list(csv.DictReader(open('/tmp/s10j_normalized_detail.csv')))
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
def fv(r,k):
 try:
  x=float(r[k]);return x if math.isfinite(x) else None
 except:return None
def strong(r):return r['strong']=='True'
def met(q):
 s=sum(strong(r) for r in q);return {'n':len(q),'strong':s,'non':len(q)-s,'precision':s/len(q) if q else 0}
def A(r):return int(r['lane'])==1 and fv(r,'f_new_overheat_pressure__lrz64') is not None and fv(r,'f_new_overheat_pressure__lrz64')>=.5
def B(r):return int(r['lane'])==1 and fv(r,'f_micro_volume_ratio_last_vs_prev10__pct128') is not None and fv(r,'f_micro_volume_ratio_last_vs_prev10__pct128')<=.30
def C(r):return int(r['lane'])==2 and fv(r,'t1_confirm_side_return_pct__rz128') is not None and fv(r,'t1_confirm_side_return_pct__rz128')<=-.5
def D(r):return int(r['lane'])==2 and fv(r,'t2_confirm_side_return_pct__pct128') is not None and fv(r,'t2_confirm_side_return_pct__pct128')<=.30
def E(r):return int(r['lane'])==3 and fv(r,'t3_confirm_side_return_pct__pct128') is not None and fv(r,'t3_confirm_side_return_pct__pct128')<=.30
STRUCTS={
'T1_OVERHEAT_ONLY':lambda r:A(r),
'T1_MICROVOL_ONLY':lambda r:B(r),
'T1_AND':lambda r:A(r) and B(r),
'T1_OR':lambda r:A(r) or B(r),
'T1_AND_OR_T2_T1CONF':lambda r:(A(r) and B(r)) or C(r),
'T1_AND_OR_T2_T2CONF':lambda r:(A(r) and B(r)) or D(r),
'T1_AND_OR_T3_CONF':lambda r:(A(r) and B(r)) or E(r),
'T1_MICROVOL_OR_T2_T1CONF':lambda r:B(r) or C(r),
'T1_MICROVOL_OR_T2_T2CONF':lambda r:B(r) or D(r),
'T1_MICROVOL_OR_T3_CONF':lambda r:B(r) or E(r),
}
for name,fn in STRUCTS.items():
 print('\n###',name)
 for source in ['research','fresh']:
  q=[r for r in ROWS if r['source']==source];v=[r for r in q if fn(r)];k=[r for r in q if not fn(r)]
  bm=met(q);vm=met(v);km=met(k)
  print(source,'base',bm,'veto',vm,'keep',km,'strong_ret',round(km['strong']/bm['strong'],4),'non_remove',round(vm['non']/bm['non'],4),'prec_delta',round(km['precision']-bm['precision'],4))
 good=bad=0
 for b in BLOCKS:
  q=[r for r in ROWS if r['block']==b];v=[r for r in q if fn(r)];k=[r for r in q if not fn(r)]
  bm=met(q);vm=met(v);km=met(k);ret=km['strong']/bm['strong'] if bm['strong'] else 1;pd=km['precision']-bm['precision']
  sr=vm['strong']/bm['strong'] if bm['strong'] else 0;nr=vm['non']/bm['non'] if bm['non'] else 0
  if pd>0 and nr>=sr:good+=1
  elif pd<0 or sr>nr:bad+=1
  print(b,'veto',vm,'ret',round(ret,3),'pd',round(pd,4),'sr/nr',round(sr,3),round(nr,3))
 print('good/bad',good,bad)