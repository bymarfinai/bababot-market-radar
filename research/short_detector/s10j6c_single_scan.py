import csv,json,math,statistics
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
def truth(v):return str(v).lower()=='true'
def fv(pid,col):
    try:
        x=float(NORM[pid][col]);return x if math.isfinite(x) else None
    except:return None
def laneR(r):return 0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
rows=[]
for r in R:
    pid=r['position_id']
    if VETO[pid]['primary_veto']=='True' or laneR(r)!=0: continue
    rows.append({'id':pid,'block':'Research_'+r['split'],'source':'research','strong':truth(r['strong_win']),
                 'severe':(not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2),
                 'pnl':float(r['COMP_pnl'])})
for r in F:
    if r['primary_veto']=='True' or int(r['lane'])!=0:continue
    rows.append({'id':r['position_id'],'block':r['block'],'source':'fresh','strong':truth(r['strong']),
                 'severe':(not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2),
                 'pnl':float(r['comp'])})
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
print('T0 rows',len(rows))
for b in BLOCKS:
 q=[r for r in rows if r['block']==b]
 print(b,'n',len(q),'strong',sum(r['strong'] for r in q),'severe',sum(r['severe'] for r in q),'pnl',round(sum(r['pnl'] for r in q),2))

# candidate families from S10J6A stability + related causal T0 normalized features
cand_specs=[
 ('COIN_LPCT','f_f_coin_minus_market_30m__lpct64','low',[.10,.15,.20,.25,.30,.35,.40,.45,.50]),
 ('COIN_PCT','f_f_coin_minus_market_30m__pct128','low',[.10,.15,.20,.25,.30,.35,.40,.45,.50]),
 ('COIN_LRZ','f_f_coin_minus_market_30m__lrz64','low',[-1.5,-1.25,-1,-.75,-.5,-.25,0,.25]),
 ('COIN_RZ','f_f_coin_minus_market_30m__rz128','low',[-1.5,-1.25,-1,-.75,-.5,-.25,0,.25]),
 ('DRIFT_LPCT','f_gate_price_drift_pct__lpct64','high',[.55,.60,.65,.70,.75,.80,.85,.90]),
 ('DRIFT_PCT','f_gate_price_drift_pct__pct128','high',[.55,.60,.65,.70,.75,.80,.85,.90]),
 ('OI_LPCT','f_f_oi_change_30m_pct__lpct64','low',[.10,.15,.20,.25,.30,.35,.40]),
 ('MICROVOL_LPCT','f_micro_volume_ratio_last_vs_prev10__lpct64','low',[.10,.15,.20,.25,.30,.35,.40]),
 ('FLOW_LPCT','f_new_flow_support__lpct64','low',[.10,.15,.20,.25,.30,.35,.40]),
 ('TAKER_LPCT','f_gate_taker_share_for_selected__lpct64','low',[.10,.15,.20,.25,.30,.35,.40]),
]
rules=[]
for name,col,side,grid in cand_specs:
  for thr in grid:
    st={}
    for scope in BLOCKS+['research','fresh']:
      q=[r for r in rows if r['block']==scope] if scope in BLOCKS else [r for r in rows if r['source']==scope]
      q=[r for r in q if fv(r['id'],col) is not None]
      v=[r for r in q if (fv(r['id'],col)<=thr if side=='low' else fv(r['id'],col)>=thr)]
      bs=sum(r['strong'] for r in q);bv=sum(r['strong'] for r in v);sev=sum(r['severe'] for r in q);vsev=sum(r['severe'] for r in v)
      st[scope]={'n':len(q),'veto_n':len(v),'veto_strong':bv,'veto_severe':vsev,'strong_retention':1-bv/bs if bs else 1,
                 'severe_removal':vsev/sev if sev else 0,'veto_pnl':sum(r['pnl'] for r in v),'keep_pnl':sum(r['pnl'] for r in q)-sum(r['pnl'] for r in v)}
    minret=min(st[b]['strong_retention'] for b in BLOCKS)
    neg=sum(st[b]['veto_pnl']<=0 for b in BLOCKS)
    rules.append({'name':name,'col':col,'side':side,'thr':thr,'stats':st,'minret':minret,'negblocks':neg})
good=[x for x in rules if x['stats']['research']['strong_retention']>=.90 and x['stats']['fresh']['strong_retention']>=.90 and x['minret']>=.75 and x['negblocks']>=5]
for x in good:
 s=x['stats'];x['score']=3*s['fresh']['severe_removal']+2*s['research']['severe_removal']+0.003*(-s['fresh']['veto_pnl'])+0.002*(-s['research']['veto_pnl'])+2*(s['fresh']['strong_retention']-.9)+(s['research']['strong_retention']-.9)
good.sort(key=lambda x:-x['score'])
print('\nGOOD SINGLE',len(good))
for x in good[:30]:
 s=x['stats'];print(x['name'],x['side'],x['thr'],'score',round(x['score'],3),'Rret',round(s['research']['strong_retention'],3),'Rsev',round(s['research']['severe_removal'],3),'Rpnl',round(s['research']['veto_pnl'],2),'Fret',round(s['fresh']['strong_retention'],3),'Fsev',round(s['fresh']['severe_removal'],3),'Fpnl',round(s['fresh']['veto_pnl'],2),'min',round(x['minret'],3),'neg',x['negblocks'])
 print([(b,s[b]['veto_n'],s[b]['veto_strong'],s[b]['veto_severe'],round(s[b]['veto_pnl'],2),round(s[b]['strong_retention'],3)) for b in BLOCKS])
json.dump({'stage':'S10J6C_single','rows_n':len(rows),'rules':rules,'good':good},open('/tmp/s10j6c_single_scan.json','w'),indent=2)