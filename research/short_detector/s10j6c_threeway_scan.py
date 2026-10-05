import csv,json,math,itertools
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
def truth(v):return str(v).lower()=='true'
def gv(pid,col):
    try:
        x=float(NORM[pid][col]);return x if math.isfinite(x) else None
    except:return None
def laneR(r):return 0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
rows=[]
for r in R:
    pid=r['position_id']
    if VETO[pid]['primary_veto']=='True' or laneR(r)!=0:continue
    rows.append({'id':pid,'block':'Research_'+r['split'],'source':'research','strong':truth(r['strong_win']),
                 'severe':(not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2),'pnl':float(r['COMP_pnl'])})
for r in F:
    if r['primary_veto']=='True' or int(r['lane'])!=0:continue
    rows.append({'id':r['position_id'],'block':r['block'],'source':'fresh','strong':truth(r['strong']),
                 'severe':(not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2),'pnl':float(r['comp'])})
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
anchors=[
 ('A1',('f_f_coin_minus_market_30m__lpct64','<=',.20),('f_gate_price_drift_pct__pct128','>=',.80)),
 ('A2',('f_f_coin_minus_market_30m__lpct64','<=',.30),('f_gate_price_drift_pct__pct128','>=',.80)),
 ('A3',('f_f_coin_minus_market_30m__lpct64','<=',.35),('f_gate_price_drift_pct__pct128','>=',.80)),
]
thirds=[
 ('MICRO_PCT_20','f_micro_volume_ratio_last_vs_prev10__pct128','<=',.20),
 ('MICRO_PCT_30','f_micro_volume_ratio_last_vs_prev10__pct128','<=',.30),
 ('MICRO_LPCT_20','f_micro_volume_ratio_last_vs_prev10__lpct64','<=',.20),
 ('MICRO_LPCT_30','f_micro_volume_ratio_last_vs_prev10__lpct64','<=',.30),
 ('OIACC_PCT_70','f_f_oi_accel_x_overheat__pct128','>=',.70),
 ('OIACC_LPCT_70','f_f_oi_accel_x_overheat__lpct64','>=',.70),
]
def ok(pid,s):
 col,op,t=s;x=gv(pid,col)
 if x is None:return False
 return x<=t if op=='<=' else x>=t
def evaluate(name,a,b,cname,c):
 def veto(r):return ok(r['id'],a) and ok(r['id'],b) and ok(r['id'],c)
 st={}
 for scope in BLOCKS+['research','fresh']:
  q=[r for r in rows if r['block']==scope] if scope in BLOCKS else [r for r in rows if r['source']==scope]
  v=[r for r in q if veto(r)]
  bs=sum(r['strong'] for r in q);bv=sum(r['strong'] for r in v);sev=sum(r['severe'] for r in q);vsev=sum(r['severe'] for r in v)
  st[scope]={'n':len(q),'veto_n':len(v),'veto_strong':bv,'veto_severe':vsev,'strong_retention':1-bv/bs if bs else 1,
             'severe_removal':vsev/sev if sev else 0,'veto_pnl':sum(r['pnl'] for r in v)}
 minret=min(st[b]['strong_retention'] for b in BLOCKS);neg=sum(st[b]['veto_pnl']<=0 for b in BLOCKS)
 return {'name':name+'+'+cname,'anchor':name,'third':cname,'stats':st,'minret':minret,'negblocks':neg}
res=[]
for name,a,b in anchors:
 for cname,col,op,t in thirds:
  res.append(evaluate(name,a,b,cname,(col,op,t)))
good=[z for z in res if z['stats']['research']['strong_retention']>=.90 and z['stats']['fresh']['strong_retention']>=.90 and z['minret']>=.75 and z['negblocks']>=5]
for z in good:
 s=z['stats'];z['score']=3*s['fresh']['severe_removal']+2*s['research']['severe_removal']+0.003*(-s['fresh']['veto_pnl'])+0.002*(-s['research']['veto_pnl'])+2*(s['fresh']['strong_retention']-.9)+(s['research']['strong_retention']-.9)
good.sort(key=lambda z:-z['score'])
print('GOOD THREEWAY',len(good))
for z in good:
 s=z['stats'];print(z['name'],'Rret',round(s['research']['strong_retention'],3),'Rsev',round(s['research']['severe_removal'],3),'Rpnl',round(s['research']['veto_pnl'],2),'Fret',round(s['fresh']['strong_retention'],3),'Fsev',round(s['fresh']['severe_removal'],3),'Fpnl',round(s['fresh']['veto_pnl'],2),'min',round(z['minret'],3),'neg',z['negblocks'])
 print([(b,s[b]['veto_n'],s[b]['veto_strong'],s[b]['veto_severe'],round(s[b]['veto_pnl'],2)) for b in BLOCKS])
json.dump({'stage':'S10J6C_threeway','all':res,'good':good},open('/tmp/s10j6c_threeway_scan.json','w'),indent=2)