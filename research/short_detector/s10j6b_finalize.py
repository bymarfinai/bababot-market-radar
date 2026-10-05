import csv,json,math,collections
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
RALL=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D']
FSEL=[r for r in csv.DictReader(open('/tmp/s10i_fresh_funnel.csv')) if r['_d']=='True']
FREP=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
def truth(v):return str(v).lower()=='true'
def getv(pid,col):
    try:
        x=float(NORM[pid][col]);return x if math.isfinite(x) else None
    except:return None
def laneR(r):return 0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
def laneFsel(r):return int(r['_lane'])
def primary_keep(pid):return VETO[pid]['primary_veto']!='True'
def rule(pid,lane,name):
    if lane!=2:return False
    if name=='SAFE_PRIMARY':
        a=getv(pid,'t2_confirm_side_return_pct__lrz64');b=getv(pid,'f_f_coin_minus_market_30m__lpct64')
        return a is not None and b is not None and a<=-0.25 and b<=0.30
    if name=='AGGRESSIVE':
        a=getv(pid,'t2_confirm_side_return_pct__lrz64');b=getv(pid,'f_f_coin_minus_market_30m__lpct64')
        return a is not None and b is not None and a<=0.0 and b<=0.30
    if name=='ALL_BLOCK_NEG':
        a=getv(pid,'t2_confirm_side_return_pct__lpct64');b=getv(pid,'f_gate_price_drift_pct__pct128')
        return a is not None and b is not None and a<=0.35 and b>=0.60
    return False
def met(rows,key):
    vals=[float(r[key]) for r in rows]
    return {'n':len(rows),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,'pnl':sum(vals),'gp':sum(v for v in vals if v>0),'gl':sum(v for v in vals if v<0)}
def cohortR(rows):
    s=[r for r in rows if truth(r['strong_win'])];n=[r for r in rows if not truth(r['strong_win'])]
    return {'strong':met(s,'COMP_pnl'),'non_target':met(n,'COMP_pnl')}
def cohortF(rows):
    s=[r for r in rows if truth(r['strong'])];n=[r for r in rows if not truth(r['strong'])]
    return {'strong':met(s,'comp'),'non_target':met(n,'comp')}

CANDS=['PRIMARY_V2_BASE','SAFE_PRIMARY','AGGRESSIVE','ALL_BLOCK_NEG']
out={'stage':'SHORT-S10J6B','status':'T2_SEVERE_SUPPRESSOR_REPLAY_COMPLETE','candidates':{}}
for name in CANDS:
    rs=[r for r in RALL if primary_keep(r['position_id']) and (name=='PRIMARY_V2_BASE' or not rule(r['position_id'],laneR(r),name))]
    fs=[r for r in FSEL if primary_keep(r['meta_position_id']) and (name=='PRIMARY_V2_BASE' or not rule(r['meta_position_id'],laneFsel(r),name))]
    re=[r for r in rs if truth(r['executable'])]
    fe=[r for r in FREP if primary_keep(r['position_id']) and (name=='PRIMARY_V2_BASE' or not rule(r['position_id'],int(r['lane']),name))]
    z={'research':{},'fresh':{}}
    z['research']['selected']={'n':len(rs),'strong':sum(truth(r['strong_win']) for r in rs)}
    z['research']['exec']={'n':len(re),'strong':sum(truth(r['strong_win']) for r in re),'noexec':len(rs)-len(re)}
    z['research']['comp']=met(re,'COMP_pnl');z['research']['cohorts']=cohortR(re)
    z['fresh']['selected']={'n':len(fs),'strong':sum(truth(r['strong_win']) for r in fs)}
    z['fresh']['exec']={'n':len(fe),'strong':sum(truth(r['strong']) for r in fe),'noexec':len(fs)-len(fe)}
    z['fresh']['comp']=met(fe,'comp');z['fresh']['cohorts']=cohortF(fe)
    z['research']['blocks']={}
    for b in ['Discovery','Validation','Reserve']:
        q=[r for r in re if r['split']==b];z['research']['blocks'][b]={'comp':met(q,'COMP_pnl'),'strong':sum(truth(r['strong_win']) for r in q)}
    z['fresh']['blocks']={}
    for b in ['Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']:
        q=[r for r in fe if r['block']==b];z['fresh']['blocks'][b]={'comp':met(q,'comp'),'strong':sum(truth(r['strong']) for r in q)}
    z['research']['lanes']={};z['fresh']['lanes']={}
    for lane in [0,1,2,3]:
        q=[r for r in re if laneR(r)==lane];z['research']['lanes'][str(lane)]={'comp':met(q,'COMP_pnl'),'strong':sum(truth(r['strong_win']) for r in q)}
        q=[r for r in fe if int(r['lane'])==lane];z['fresh']['lanes'][str(lane)]={'comp':met(q,'comp'),'strong':sum(truth(r['strong']) for r in q)}
    out['candidates'][name]=z

base=out['candidates']['PRIMARY_V2_BASE']
for name,z in out['candidates'].items():
    z['research']['delta_vs_primary_v2']=z['research']['comp']['pnl']-base['research']['comp']['pnl']
    z['fresh']['delta_vs_primary_v2']=z['fresh']['comp']['pnl']-base['fresh']['comp']['pnl']
    z['research']['exec_strong_retention']=z['research']['exec']['strong']/base['research']['exec']['strong']
    z['fresh']['exec_strong_retention']=z['fresh']['exec']['strong']/base['fresh']['exec']['strong']

for name in CANDS[1:]:
    rveto=[r for r in RALL if truth(r['executable']) and primary_keep(r['position_id']) and rule(r['position_id'],laneR(r),name)]
    fveto=[r for r in FREP if primary_keep(r['position_id']) and rule(r['position_id'],int(r['lane']),name)]
    out['candidates'][name]['research']['veto_exec']={'comp':met(rveto,'COMP_pnl'),'strong':sum(truth(r['strong_win']) for r in rveto),
        'severe':sum((not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2) for r in rveto)}
    out['candidates'][name]['fresh']['veto_exec']={'comp':met(fveto,'comp'),'strong':sum(truth(r['strong']) for r in fveto),
        'severe':sum((not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2) for r in fveto)}

out['accepted']='SAFE_PRIMARY'
out['accepted_rule']={
 'scope':'T+2 only',
 'clause':'t2_confirm_side_return_pct__lrz64 <= -0.25 AND f_f_coin_minus_market_30m__lpct64 <= 0.30',
 'normalization':'causal prior-only lane robust-z64 for T2 confirmation; causal prior-only lane percentile64 for coin-minus-market',
 'reason':'higher winner retention than aggressive candidate with nearly same fresh PnL improvement; two-signal monotonic AND; no added timing delay.'}
json.dump(out,open('/tmp/s10j6b_summary.json','w'),indent=2)
for name,z in out['candidates'].items():
 print('\n',name)
 for side in ['research','fresh']:
  a=z[side];print(side,'sel',a['selected'],'exec',a['exec'],'WR',round(100*a['comp']['wr'],2),'PnL',round(a['comp']['pnl'],2),'delta',round(a['delta_vs_primary_v2'],2),'strongRet',round(a['exec_strong_retention'],3))
  print(' blocks',[(b,round(x['comp']['pnl'],2),x['comp']['n']) for b,x in a['blocks'].items()])
  print(' lanes',[(k,round(x['comp']['pnl'],2),x['comp']['n'],x['strong']) for k,x in a['lanes'].items()])
 if name!='PRIMARY_V2_BASE':
  print('veto R',z['research']['veto_exec'],'veto F',z['fresh']['veto_exec'])