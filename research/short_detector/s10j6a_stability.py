import csv,math,statistics,json
NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
R=[r for r in R if VETO[r['position_id']]['primary_veto']!='True']
F=[r for r in F if r['primary_veto']!='True']
def truth(v):return str(v).lower()=='true'
def fv(r,k):
    try:
        x=float(r[k]);return x if math.isfinite(x) else None
    except:return None
def auc(pos,neg):
    vals=[(x,1) for x in pos]+[(x,0) for x in neg];vals.sort(key=lambda z:z[0])
    rank=1;sumr=0;i=0
    while i<len(vals):
        j=i
        while j+1<len(vals) and vals[j+1][0]==vals[i][0]:j+=1
        av=(rank+rank+(j-i))/2
        sumr+=av*sum(vals[k][1] for k in range(i,j+1))
        rank+=j-i+1;i=j+1
    np=len(pos);nn=len(neg)
    return (sumr-np*(np+1)/2)/(np*nn) if np and nn else None

C=[]
for r in R:
    lane=0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
    C.append({'id':r['position_id'],'lane':lane,'block':'Research_'+r['split'],'strong':truth(r['strong_win']),
              'severe':(not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2)})
for r in F:
    C.append({'id':r['position_id'],'lane':int(r['lane']),'block':r['block'],'strong':truth(r['strong']),
              'severe':(not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2)})
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
base=[
'f_new_overheat_pressure','f_new_accel_15_vs_60','f_new_volume_over_range','f_gate_price_drift_pct',
'f_f_taker_accel_1m','f_new_gate_price_x_flow_gap','f_new_momentum_curvature','f_context_breakdown_down_pct',
'f_f_oi_accel_x_overheat','f_f_coin_minus_market_30m','f_f_oi_change_30m_pct','f_micro_volume_ratio_last_vs_prev10',
'f_new_flow_support','f_new_micro_accel_1_vs_3','f_gate_side_ret_1m_pct','f_gate_taker_share_for_selected']
allowed={0:base,1:base+['t1_confirm_side_return_pct'],2:base+['t1_confirm_side_return_pct','t2_confirm_side_return_pct'],3:base+['t1_confirm_side_return_pct','t2_confirm_side_return_pct','t3_confirm_side_return_pct']}
sufs=['__pct128','__rz128','__lpct64','__lrz64']
out={}
for lane in [0,1,2,3]:
    cand=[]
    for bfeat in allowed[lane]:
      for suf in sufs:
        col=bfeat+suf
        stats={};vals_auc=[]
        for b in BLOCKS:
          st=[];sev=[]
          for r in C:
            if r['lane']!=lane or r['block']!=b or r['id'] not in NORM:continue
            x=fv(NORM[r['id']],col)
            if x is None:continue
            if r['strong']:st.append(x)
            elif r['severe']:sev.append(x)
          a=auc(st,sev) if len(st)>=3 and len(sev)>=3 else None
          stats[b]={'strong_n':len(st),'severe_n':len(sev),'auc':a}
          if a is not None:vals_auc.append(a)
        if len(vals_auc)>=4:
          dirpos=sum(a>.5 for a in vals_auc);dirneg=sum(a<.5 for a in vals_auc)
          same=max(dirpos,dirneg);direction='higher_for_strong' if dirpos>=dirneg else 'lower_for_strong'
          cand.append({'col':col,'valid_blocks':len(vals_auc),'same_dir_blocks':same,'direction':direction,'mean_auc':statistics.mean(vals_auc),'mean_sep':statistics.mean(abs(a-.5) for a in vals_auc),'stats':stats})
    cand.sort(key=lambda x:(-x['same_dir_blocks'],-x['valid_blocks'],-x['mean_sep']))
    out[str(lane)]=cand[:20]
    print('\nLANE',lane)
    for x in cand[:12]:
      print(x['col'],'valid',x['valid_blocks'],'same',x['same_dir_blocks'],x['direction'],'meanAUC',round(x['mean_auc'],3),'meanSep',round(x['mean_sep'],3),
            [(b,round(x['stats'][b]['auc'],3) if x['stats'][b]['auc'] is not None else None,x['stats'][b]['strong_n'],x['stats'][b]['severe_n']) for b in BLOCKS])
json.dump(out,open('/tmp/s10j6a_stable_separators.json','w'),indent=2)