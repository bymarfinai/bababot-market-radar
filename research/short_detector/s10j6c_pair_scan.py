import csv,json,math,itertools
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
def truth(v):return str(v).lower()=='true'
def getv(pid,col):
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
A=[
 ('COIN_LPCT_20','f_f_coin_minus_market_30m__lpct64','<=',.20),
 ('COIN_LPCT_25','f_f_coin_minus_market_30m__lpct64','<=',.25),
 ('COIN_LPCT_30','f_f_coin_minus_market_30m__lpct64','<=',.30),
 ('COIN_LPCT_35','f_f_coin_minus_market_30m__lpct64','<=',.35),
 ('COIN_PCT_20','f_f_coin_minus_market_30m__pct128','<=',.20),
 ('COIN_PCT_25','f_f_coin_minus_market_30m__pct128','<=',.25),
 ('COIN_PCT_30','f_f_coin_minus_market_30m__pct128','<=',.30),
 ('COIN_RZ_-0.5','f_f_coin_minus_market_30m__rz128','<=',-.5),
 ('COIN_RZ_0','f_f_coin_minus_market_30m__rz128','<=',0),
]
B=[
 ('DRIFT_LPCT_60','f_gate_price_drift_pct__lpct64','>=',.60),
 ('DRIFT_LPCT_70','f_gate_price_drift_pct__lpct64','>=',.70),
 ('DRIFT_LPCT_80','f_gate_price_drift_pct__lpct64','>=',.80),
 ('DRIFT_PCT_60','f_gate_price_drift_pct__pct128','>=',.60),
 ('DRIFT_PCT_70','f_gate_price_drift_pct__pct128','>=',.70),
 ('DRIFT_PCT_80','f_gate_price_drift_pct__pct128','>=',.80),
 ('MICROVOL_PCT_20','f_micro_volume_ratio_last_vs_prev10__pct128','<=',.20),
 ('MICROVOL_PCT_30','f_micro_volume_ratio_last_vs_prev10__pct128','<=',.30),
 ('MICROVOL_LPCT_20','f_micro_volume_ratio_last_vs_prev10__lpct64','<=',.20),
 ('MICROVOL_LPCT_30','f_micro_volume_ratio_last_vs_prev10__lpct64','<=',.30),
 ('TAKER_LPCT_70','f_gate_taker_share_for_selected__lpct64','>=',.70),
 ('TAKER_PCT_70','f_gate_taker_share_for_selected__pct128','>=',.70),
]
def cond(pid,s):
    _,col,op,t=s;x=getv(pid,col)
    if x is None:return False
    return x<=t if op=='<=' else x>=t
def evaluate(a,b):
    def veto(r):return cond(r['id'],a) and cond(r['id'],b)
    st={}
    for scope in BLOCKS+['research','fresh']:
        q=[r for r in rows if r['block']==scope] if scope in BLOCKS else [r for r in rows if r['source']==scope]
        v=[r for r in q if veto(r)]
        bs=sum(r['strong'] for r in q);bv=sum(r['strong'] for r in v);sev=sum(r['severe'] for r in q);vsev=sum(r['severe'] for r in v)
        st[scope]={'n':len(q),'veto_n':len(v),'veto_strong':bv,'veto_severe':vsev,
                   'strong_retention':1-bv/bs if bs else 1,'severe_removal':vsev/sev if sev else 0,
                   'veto_pnl':sum(r['pnl'] for r in v),'keep_pnl':sum(r['pnl'] for r in q)-sum(r['pnl'] for r in v)}
    minret=min(st[b]['strong_retention'] for b in BLOCKS)
    neg=sum(st[b]['veto_pnl']<=0 for b in BLOCKS)
    return {'rules':[a[0],b[0]],'a':a,'b':b,'stats':st,'minret':minret,'negblocks':neg}
res=[evaluate(a,b) for a in A for b in B]
good=[x for x in res if x['stats']['research']['strong_retention']>=.90 and x['stats']['fresh']['strong_retention']>=.90 and x['minret']>=.75 and x['negblocks']>=5]
for x in good:
 s=x['stats'];x['score']=3*s['fresh']['severe_removal']+2*s['research']['severe_removal']+0.003*(-s['fresh']['veto_pnl'])+0.002*(-s['research']['veto_pnl'])+2*(s['fresh']['strong_retention']-.9)+(s['research']['strong_retention']-.9)
good.sort(key=lambda x:-x['score'])
print('GOOD PAIRS',len(good))
for x in good[:35]:
 s=x['stats'];print(x['rules'],'score',round(x['score'],3),'Rret',round(s['research']['strong_retention'],3),'Rsev',round(s['research']['severe_removal'],3),'Rpnl',round(s['research']['veto_pnl'],2),'Fret',round(s['fresh']['strong_retention'],3),'Fsev',round(s['fresh']['severe_removal'],3),'Fpnl',round(s['fresh']['veto_pnl'],2),'min',round(x['minret'],3),'neg',x['negblocks'])
 print([(b,s[b]['veto_n'],s[b]['veto_strong'],s[b]['veto_severe'],round(s[b]['veto_pnl'],2),round(s[b]['strong_retention'],3)) for b in BLOCKS])
json.dump({'stage':'S10J6C_pair','all':res,'good':good},open('/tmp/s10j6c_pair_scan.json','w'),indent=2)