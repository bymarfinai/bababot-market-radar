import csv,json,collections,math
RTRADE=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D']
VM={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
FTRADE=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
FUN=[r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv')) if r['_d']=='True']
POL=[
 ('S10D_BASE',None),
 ('T1_ONLY','conservative_veto'),
 ('PRIMARY_V2','primary_veto'),
 ('T1_PLUS_T2','challenger_t2_veto')]
def truth(v):return str(v).lower()=='true'
def rkeep(r,key):
 return True if key is None else not truth(VM[r['position_id']][key])
def fkeep(r,key):
 return True if key is None else not truth(r[key])
def met(rows,key='comp'):
 vals=[float(r[key]) for r in rows]
 return {'n':len(rows),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals),'gp':sum(v for v in vals if v>0),'gl':sum(v for v in vals if v<0)}
def cohort(rows,strongkey='strong_win',pnlkey='COMP_pnl'):
 s=[r for r in rows if truth(r[strongkey])];n=[r for r in rows if not truth(r[strongkey])]
 return {'strong':met(s,pnlkey),'non_target':met(n,pnlkey)}
out={'stage':'S10J5','status':'EXECUTION_REPLAY_COMPLETE','policies':{}}
for name,key in POL:
 # research selected and exec
 rs=[r for r in RTRADE if rkeep(r,key)]
 re=[r for r in rs if truth(r['executable'])]
 # fresh selected count from 807 map
 fs=[r for r in FUN if key is None or not truth(VM[r['meta_position_id']][key])]
 fe=[r for r in FTRADE if fkeep(r,key)]
 z={'research':{},'fresh':{}}
 z['research']['selected']={'n':len(rs),'strong':sum(truth(r['strong_win']) for r in rs)}
 z['research']['executable']={'n':len(re),'strong':sum(truth(r['strong_win']) for r in re),'noexec':len(rs)-len(re)}
 z['research']['hold']=met(re,'HOLD_pnl');z['research']['v43']=met(re,'V43_pnl');z['research']['comp']=met(re,'COMP_pnl');z['research']['cohorts']=cohort(re)
 z['research']['lanes']={}
 for lane in ['0','1','2','3']:
  q=[r for r in re if ('0' if r['entry_kind']=='T0' else r['entry_horizon'])==lane]
  z['research']['lanes'][lane]={'comp':met(q,'COMP_pnl'),'strong':sum(truth(r['strong_win']) for r in q)}
 z['fresh']['selected']={'n':len(fs),'strong':sum(truth(r['strong_win']) for r in fs)}
 z['fresh']['executable']={'n':len(fe),'strong':sum(truth(r['strong']) for r in fe),'noexec':len(fs)-len(fe)}
 z['fresh']['hold']=met(fe,'hold');z['fresh']['v43']=met(fe,'v43');z['fresh']['comp']=met(fe,'comp')
 s=[r for r in fe if truth(r['strong'])];n=[r for r in fe if not truth(r['strong'])]
 z['fresh']['cohorts']={'strong':met(s,'comp'),'non_target':met(n,'comp')}
 z['fresh']['lanes']={}
 for lane in ['0','1','2','3']:
  q=[r for r in fe if r['lane']==lane]
  z['fresh']['lanes'][lane]={'comp':met(q,'comp'),'strong':sum(truth(r['strong']) for r in q)}
 z['fresh']['blocks']={}
 for b in ['Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']:
  q=[r for r in fe if r['block']==b]
  z['fresh']['blocks'][b]={'comp':met(q,'comp'),'strong':sum(truth(r['strong']) for r in q)}
 out['policies'][name]=z

# delta vs baseline
baseR=out['policies']['S10D_BASE']['research']['comp']['pnl'];baseF=out['policies']['S10D_BASE']['fresh']['comp']['pnl']
for name,z in out['policies'].items():
 z['research']['delta_comp_vs_s10d']=z['research']['comp']['pnl']-baseR
 z['fresh']['delta_comp_vs_s10d']=z['fresh']['comp']['pnl']-baseF

# vetoed executable economics per candidate
for name,key in POL[1:]:
 rv=[r for r in RTRADE if truth(r['executable']) and not rkeep(r,key)]
 fv=[r for r in FTRADE if not fkeep(r,key)]
 out['policies'][name]['research']['vetoed_exec']={'comp':met(rv,'COMP_pnl'),'strong':sum(truth(r['strong_win']) for r in rv)}
 out['policies'][name]['fresh']['vetoed_exec']={'comp':met(fv,'comp'),'strong':sum(truth(r['strong']) for r in fv)}

# integrity
out['integrity']=json.load(open('/tmp/s10j5_out/integrity.json'))
json.dump(out,open('/tmp/s10j5_summary.json','w'),indent=2)
# concise table
for name,z in out['policies'].items():
 print('\n',name)
 for side in ['research','fresh']:
  a=z[side]
  print(side,'sel',a['selected'],'exec',a['executable'],'HOLD',round(a['hold']['pnl'],2),'V43',round(a['v43']['pnl'],2),'COMP',round(a['comp']['pnl'],2),'WR',round(100*a['comp']['wr'],2),'delta',round(a['delta_comp_vs_s10d'],2))
  print(' strong',a['cohorts']['strong']['n'],round(a['cohorts']['strong']['pnl'],2),'non',a['cohorts']['non_target']['n'],round(a['cohorts']['non_target']['pnl'],2))
  if side=='fresh': print(' blocks',[(b,round(x['comp']['pnl'],2),x['comp']['n']) for b,x in a['blocks'].items()])
 if name!='S10D_BASE':
  print('veto R',z['research']['vetoed_exec'],'veto F',z['fresh']['vetoed_exec'])
print('\\nINTEGRITY',out['integrity'])