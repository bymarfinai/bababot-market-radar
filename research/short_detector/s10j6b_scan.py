import csv,json,math
from collections import defaultdict

NORM={r['id']:r for r in csv.DictReader(open('/tmp/s10j_normalized_detail.csv'))}
VETO={r['id']:r for r in csv.DictReader(open('/tmp/s10j4_veto_detail.csv'))}
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))

def truth(v): return str(v).lower()=='true'
def fv(r,k):
    try:
        x=float(r[k]); return x if math.isfinite(x) else None
    except: return None

# Primary V2 kept, lane T2 only
rows=[]
for r in R:
    pid=r['position_id']
    if VETO[pid]['primary_veto']=='True': continue
    lane=0 if r['entry_kind']=='T0' else int(r['entry_horizon'])
    if lane!=2: continue
    rows.append({'id':pid,'block':'Research_'+r['split'],'source':'research','strong':truth(r['strong_win']),
                 'severe':(not truth(r['strong_win']) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2),
                 'pnl':float(r['COMP_pnl'])})
for r in F:
    pid=r['position_id']
    if r['primary_veto']=='True' or int(r['lane'])!=2: continue
    rows.append({'id':pid,'block':r['block'],'source':'fresh','strong':truth(r['strong']),
                 'severe':(not truth(r['strong']) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2),
                 'pnl':float(r['comp'])})

BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']
print('T2 rows',len(rows))
for b in BLOCKS:
    q=[r for r in rows if r['block']==b]
    print(b,'n',len(q),'strong',sum(r['strong'] for r in q),'severe',sum(r['severe'] for r in q),'pnl',round(sum(r['pnl'] for r in q),2))

rules=[]
for col,grid in [
 ('t2_confirm_side_return_pct__lrz64',[-1.5,-1.25,-1.0,-0.75,-0.5,-0.25,0,0.25,0.5]),
 ('t2_confirm_side_return_pct__rz128',[-1.5,-1.25,-1.0,-0.75,-0.5,-0.25,0,0.25,0.5]),
 ('t2_confirm_side_return_pct__lpct64',[.10,.15,.20,.25,.30,.35,.40,.45,.50]),
 ('t2_confirm_side_return_pct__pct128',[.10,.15,.20,.25,.30,.35,.40,.45,.50]),
]:
  for thr in grid:
    st={}
    for b in BLOCKS:
      q=[r for r in rows if r['block']==b and r['id'] in NORM and fv(NORM[r['id']],col) is not None]
      v=[r for r in q if fv(NORM[r['id']],col)<=thr]
      k=[r for r in q if r not in v]
      bs=sum(r['strong'] for r in q); bv=sum(r['strong'] for r in v)
      bsev=sum(r['severe'] for r in q); vsev=sum(r['severe'] for r in v)
      st[b]={'n':len(q),'veto_n':len(v),'veto_strong':bv,'veto_severe':vsev,
             'strong_retention':1-bv/bs if bs else 1,
             'severe_removal':vsev/bsev if bsev else 0,
             'veto_pnl':sum(r['pnl'] for r in v),'keep_pnl':sum(r['pnl'] for r in k)}
    for source in ['research','fresh']:
      q=[r for r in rows if r['source']==source and r['id'] in NORM and fv(NORM[r['id']],col) is not None]
      v=[r for r in q if fv(NORM[r['id']],col)<=thr];k=[r for r in q if r not in v]
      bs=sum(r['strong'] for r in q);bsev=sum(r['severe'] for r in q)
      st[source]={'n':len(q),'veto_n':len(v),'veto_strong':sum(r['strong'] for r in v),'veto_severe':sum(r['severe'] for r in v),
                  'strong_retention':1-sum(r['strong'] for r in v)/bs if bs else 1,
                  'severe_removal':sum(r['severe'] for r in v)/bsev if bsev else 0,
                  'veto_pnl':sum(r['pnl'] for r in v),'keep_pnl':sum(r['pnl'] for r in k)}
    minret=min(st[b]['strong_retention'] for b in BLOCKS)
    nonneg=sum(st[b]['veto_pnl']<=0 for b in BLOCKS)
    rules.append({'col':col,'thr':thr,'stats':st,'min_block_strong_retention':minret,'nonpositive_veto_pnl_blocks':nonneg})

# hard gate: research/fresh strong retention >=.90, every block >=.75, veto pnl nonpositive >=5/6
good=[x for x in rules if x['stats']['research']['strong_retention']>=.90 and x['stats']['fresh']['strong_retention']>=.90 and x['min_block_strong_retention']>=.75 and x['nonpositive_veto_pnl_blocks']>=5]
# score: maximize fresh severe removal + research severe removal + negative veto pnl while preserve winners
for x in good:
    sr=x['stats']['research'];sf=x['stats']['fresh']
    x['score']=2.5*sf['severe_removal']+1.5*sr['severe_removal']+0.002*(-sf['veto_pnl'])+0.001*(-sr['veto_pnl'])+2*(sf['strong_retention']-.90)+1*(sr['strong_retention']-.90)
good.sort(key=lambda x:-x['score'])
print('\nGOOD',len(good))
for x in good[:25]:
    print(x['col'],'<=',x['thr'],'score',round(x['score'],3),
          'R ret',round(x['stats']['research']['strong_retention'],3),'sevRm',round(x['stats']['research']['severe_removal'],3),'vetoP',round(x['stats']['research']['veto_pnl'],2),
          'F ret',round(x['stats']['fresh']['strong_retention'],3),'sevRm',round(x['stats']['fresh']['severe_removal'],3),'vetoP',round(x['stats']['fresh']['veto_pnl'],2),
          'minRet',round(x['min_block_strong_retention'],3),'negBlocks',x['nonpositive_veto_pnl_blocks'])
    print(' blocks',[(b,x['stats'][b]['veto_n'],x['stats'][b]['veto_strong'],x['stats'][b]['veto_severe'],round(x['stats'][b]['veto_pnl'],2),round(x['stats'][b]['strong_retention'],3)) for b in BLOCKS])
json.dump({'stage':'S10J6B_scan','rules':rules,'good':good},open('/tmp/s10j6b_scan.json','w'),indent=2)