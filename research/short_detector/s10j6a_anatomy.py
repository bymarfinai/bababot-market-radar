import csv,math,statistics,collections,json
REP=[r for r in csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')) if r['primary_veto']!='True']
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv')) if r['source']=='fresh'}
FEAT={r['meta_position_id']:r for r in csv.DictReader(open('/tmp/s10h_fresh_features.csv'))}
def truth(v):return str(v).lower()=='true'
def f(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except:return None
def auc(pos,neg):
    # probability pos > neg; tie .5
    vals=[(x,1) for x in pos]+[(x,0) for x in neg]
    vals.sort(key=lambda z:z[0])
    rank=1;sumr=0;i=0
    while i<len(vals):
        j=i
        while j+1<len(vals) and vals[j+1][0]==vals[i][0]:j+=1
        av=(rank+rank+(j-i))/2
        sumr+=av*sum(vals[k][1] for k in range(i,j+1))
        rank+=j-i+1;i=j+1
    np=len(pos);nn=len(neg)
    return (sumr-np*(np+1)/2)/(np*nn) if np and nn else None

for r in REP:
    pnl=float(r['comp'])
    r['_strong']=truth(r['strong'])
    r['_severe']= (not r['_strong'] and r['reason']=='HIST_TIME_FALLBACK' and pnl<=-2)
    r['_benign_nt']= (not r['_strong'] and not r['_severe'])

print('### LANE DAMAGE')
for lane in ['0','1','2','3']:
    q=[r for r in REP if r['lane']==lane]
    st=[r for r in q if r['_strong']]
    nt=[r for r in q if not r['_strong']]
    sev=[r for r in q if r['_severe']]
    print('lane',lane,'n',len(q),'strong',len(st),'non',len(nt),'lane_pnl',round(sum(float(r['comp']) for r in q),2),
          'severe',len(sev),'severe_pnl',round(sum(float(r['comp']) for r in sev),2),
          'sev/non',round(len(sev)/len(nt),3) if nt else 0,
          'counterfactual_no_severe',round(sum(float(r['comp']) for r in q)-sum(float(r['comp']) for r in sev),2))

# available normalized causal columns per lane
basecols=[
'f_new_overheat_pressure','f_new_accel_15_vs_60','f_new_volume_over_range','f_gate_price_drift_pct',
'f_f_taker_accel_1m','f_new_gate_price_x_flow_gap','f_new_momentum_curvature','f_context_breakdown_down_pct',
'f_f_oi_accel_x_overheat','f_f_coin_minus_market_30m','f_f_oi_change_30m_pct','f_micro_volume_ratio_last_vs_prev10',
'f_new_flow_support','f_new_micro_accel_1_vs_3','f_gate_side_ret_1m_pct','f_gate_taker_share_for_selected']
allowed={0:basecols,1:basecols+['t1_confirm_side_return_pct'],2:basecols+['t1_confirm_side_return_pct','t2_confirm_side_return_pct'],3:basecols+['t1_confirm_side_return_pct','t2_confirm_side_return_pct','t3_confirm_side_return_pct']}
suffixes=['__pct128','__rz128','__lpct64','__lrz64']
out={}
for lane in [0,1,2,3]:
    st=[r for r in REP if r['lane']==str(lane) and r['_strong']]
    sev=[r for r in REP if r['lane']==str(lane) and r['_severe']]
    rows=[]
    for base in allowed[lane]:
        for suf in suffixes:
            col=base+suf
            pv=[f(NORM[r['position_id']].get(col)) for r in st if r['position_id'] in NORM]
            nv=[f(NORM[r['position_id']].get(col)) for r in sev if r['position_id'] in NORM]
            pv=[x for x in pv if x is not None];nv=[x for x in nv if x is not None]
            if len(pv)<8 or len(nv)<8:continue
            a=auc(pv,nv)
            if a is None:continue
            sep=abs(a-.5)
            rows.append({'col':col,'auc_strong_vs_severe':a,'sep':sep,'strong_n':len(pv),'severe_n':len(nv),
                         'strong_median':statistics.median(pv),'severe_median':statistics.median(nv)})
    rows.sort(key=lambda x:-x['sep'])
    print('\n### LANE',lane,'TOP SEPARATORS strong vs severe-fallback')
    for x in rows[:15]:
        print(x['col'],'AUC',round(x['auc_strong_vs_severe'],3),'strong_med',round(x['strong_median'],3),'sev_med',round(x['severe_median'],3))
    out[str(lane)]=rows[:40]

# day composition severe
print('\n### SEVERE BY DAY')
for b in ['Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']:
    q=[r for r in REP if r['block']==b];sev=[r for r in q if r['_severe']]
    print(b,'exec',len(q),'strong',sum(r['_strong'] for r in q),'severe',len(sev),'severe_pnl',round(sum(float(r['comp']) for r in sev),2),'lanes',dict(collections.Counter(r['lane'] for r in sev)))

json.dump({'lane_separators':out},open('/tmp/s10j6a_separators.json','w'),indent=2)