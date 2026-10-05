import csv,json,math,itertools
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
def truth(v):return str(v).lower()=='true'
def fv(r,k):
    try:
        x=float(r[k]);return x if math.isfinite(x) else None
    except:return None
rows=[]
for r in R:
    pid=r['position_id']
    if VETO[pid]['primary_veto']=='True':continue
    lane=0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
    if lane!=2:continue
    rows.append({'id':pid,'block':'Research_'+r['split'],'source':'research','strong':truth(r['strong_win']),
                 'severe':(not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2),'pnl':float(r['COMP_pnl'])})
for r in F:
    if r['primary_veto']=='True' or int(r['lane'])!=2:continue
    rows.append({'id':r['position_id'],'block':r['block'],'source':'fresh','strong':truth(r['strong']),
                 'severe':(not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2),'pnl':float(r['comp'])})
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
# Primary weak-confirm conditions: deliberately small grid
A=[
 ('T2LRZ_LE_-0.5','t2_confirm_side_return_pct__lrz64','<=',-0.5),
 ('T2LRZ_LE_-0.25','t2_confirm_side_return_pct__lrz64','<=',-0.25),
 ('T2LRZ_LE_0','t2_confirm_side_return_pct__lrz64','<=',0.0),
 ('T2LPCT_LE_0.30','t2_confirm_side_return_pct__lpct64','<=',0.30),
 ('T2LPCT_LE_0.35','t2_confirm_side_return_pct__lpct64','<=',0.35),
]
B=[
 ('COINPCT_LE_0.30','f_f_coin_minus_market_30m__pct128','<=',0.30),
 ('COINPCT_LE_0.40','f_f_coin_minus_market_30m__pct128','<=',0.40),
 ('COINLPCT_LE_0.30','f_f_coin_minus_market_30m__lpct64','<=',0.30),
 ('COINLPCT_LE_0.40','f_f_coin_minus_market_30m__lpct64','<=',0.40),
 ('COINRZ_LE_-0.5','f_f_coin_minus_market_30m__rz128','<=',-0.5),
 ('COINRZ_LE_0','f_f_coin_minus_market_30m__rz128','<=',0.0),
 ('DRIFTPCT_GE_0.70','f_gate_price_drift_pct__pct128','>=',0.70),
 ('DRIFTPCT_GE_0.60','f_gate_price_drift_pct__pct128','>=',0.60),
 ('T1CONF_PCT_LE_0.30','t1_confirm_side_return_pct__pct128','<=',0.30),
 ('T1CONF_RZ_LE_-0.5','t1_confirm_side_return_pct__rz128','<=',-0.5),
]
def cond(pid,spec):
    _,col,op,t=spec;x=fv(NORM[pid],col) if pid in NORM else None
    if x is None:return False
    return x<=t if op=='<=' else x>=t
def eval_combo(a,b):
    def veto(r):return cond(r['id'],a) and cond(r['id'],b)
    st={}
    for scope in BLOCKS+['research','fresh']:
        q=[r for r in rows if r['block']==scope] if scope in BLOCKS else [r for r in rows if r['source']==scope]
        v=[r for r in q if veto(r)];k=[r for r in q if not veto(r)]
        bs=sum(r['strong'] for r in q);bv=sum(r['strong'] for r in v);bsev=sum(r['severe'] for r in q);vsev=sum(r['severe'] for r in v)
        st[scope]={'n':len(q),'veto_n':len(v),'veto_strong':bv,'veto_severe':vsev,
                   'strong_retention':1-bv/bs if bs else 1,'severe_removal':vsev/bsev if bsev else 0,
                   'veto_pnl':sum(r['pnl'] for r in v),'keep_pnl':sum(r['pnl'] for r in k)}
    minret=min(st[b]['strong_retention'] for b in BLOCKS)
    neg=sum(st[b]['veto_pnl']<=0 for b in BLOCKS)
    return {'rules':[a[0],b[0]],'a':a,'b':b,'stats':st,'min_block_strong_retention':minret,'nonpositive_veto_pnl_blocks':neg}

res=[eval_combo(a,b) for a in A for b in B]
# robust gate
good=[x for x in res if x['stats']['research']['strong_retention']>=.90 and x['stats']['fresh']['strong_retention']>=.90 and x['min_block_strong_retention']>=.75 and x['nonpositive_veto_pnl_blocks']>=5]
for x in good:
    R=x['stats']['research'];F=x['stats']['fresh']
    x['score']=3*F['severe_removal']+2*R['severe_removal']+0.003*(-F['veto_pnl'])+0.002*(-R['veto_pnl'])+2*(F['strong_retention']-.9)+1*(R['strong_retention']-.9)
good.sort(key=lambda x:-x['score'])
print('GOOD',len(good))
for x in good[:30]:
    s=x['stats'];print(x['rules'],'score',round(x['score'],3),
        'R ret',round(s['research']['strong_retention'],3),'sev',round(s['research']['severe_removal'],3),'vetoP',round(s['research']['veto_pnl'],2),
        'F ret',round(s['fresh']['strong_retention'],3),'sev',round(s['fresh']['severe_removal'],3),'vetoP',round(s['fresh']['veto_pnl'],2),
        'min',round(x['min_block_strong_retention'],3),'neg',x['nonpositive_veto_pnl_blocks'])
    print(' ',[(b,s[b]['veto_n'],s[b]['veto_strong'],s[b]['veto_severe'],round(s[b]['veto_pnl'],2),round(s[b]['strong_retention'],3)) for b in BLOCKS])
json.dump({'stage':'S10J6B_pair_scan','good':good,'all':res},open('/tmp/s10j6b_pair_scan.json','w'),indent=2)