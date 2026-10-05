import csv,json,math
from collections import Counter,defaultdict
from pathlib import Path

TH='0.075000'
CT2=[r for r in csv.DictReader(open('/tmp/ct2_trade_detail.csv')) if f"{float(r['threshold']):.6f}"==TH]
CT4=[r for r in csv.DictReader(open('/tmp/ct4_trade_detail.csv')) if r['candidate']=='T0075']
RBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D'}
FBASE={r['position_id']:r for r in csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv'))}
CT4MAP={(r['source'],r['position_id']):r for r in CT4}
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']

def truth(v): return str(v).lower()=='true'
def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except:return None

def baseline_pnl(src,pid):
    if src=='research':
        r=RBASE[pid]
        return float(r['COMP_pnl']) if truth(r['executable']) else None
    r=FBASE.get(pid)
    return None if r is None else float(r['comp'])

def baseline_reason(src,pid):
    if src=='research':
        r=RBASE[pid]; return r['COMP_reason'] if truth(r['executable']) else 'NO_EXECUTABLE_ENTRY'
    r=FBASE.get(pid); return r['reason'] if r else 'NO_EXECUTABLE_ENTRY'

def new_pnl(src,pid):
    r=CT4MAP.get((src,pid))
    if not r or not truth(r['executable']):return None
    return float(r['pnl'])

def new_reason(src,pid):
    r=CT4MAP.get((src,pid))
    return r['reason'] if r and truth(r['executable']) else 'NO_EXECUTABLE_ENTRY'

def severe(reason,pnl,strong):
    return (not strong) and reason=='HIST_TIME_FALLBACK' and pnl is not None and pnl<=-2

# Build shifted cohorts from CT2 plus source-only 3->3.
shifted=[r for r in CT2 if r['status']=='SHIFTED']
removed=[r for r in CT2 if r['status']=='REMOVED']

# transition labels
def tlabel(r):
    b=int(r['base_lane']); n=int(r['new_lane'])
    if b==1 and n==2:return 'T1_TO_T2'
    if b==1 and n==3:return 'T1_TO_T3'
    if b==2 and n==3:return 'T2_TO_T3'
    if b==3 and n==3:return 'T3_SOURCE_SWITCH'
    return f'T{b}_TO_T{n}'

# derive ALT_T3 currently selected in CT4 threshold 0.075 from entry source in CT2 source-switch or baseline source.
# For all T0075 rows lane==3, classify source using CT2 if affected, otherwise baseline source from research trade detail / fresh funnel unavailable;
# use affected anatomy for ALT-specific distinction only where source is known.
rows=[]
for r in shifted:
    src=r['source'];pid=r['position_id'];strong=truth(r['strong'])
    bp=baseline_pnl(src,pid);np=new_pnl(src,pid);br=baseline_reason(src,pid);nr=new_reason(src,pid)
    rows.append({
      'source':src,'position_id':pid,'symbol':r['symbol'],'block':r['block'],'transition':tlabel(r),
      'base_lane':int(r['base_lane']),'new_lane':int(r['new_lane']),
      'base_source':r['base_source'],'new_source':r['new_source'],'strong':strong,
      'baseline_executable':bp is not None,'baseline_pnl':bp,'baseline_reason':br,
      'baseline_severe':severe(br,bp,strong),
      'new_executable':np is not None,'new_pnl':np,'new_reason':nr,
      'new_severe':severe(nr,np,strong),
      'delta_vs_old':(np if np is not None else 0)-(bp if bp is not None else 0)
    })

def metrics(q):
    bp=[x['baseline_pnl'] for x in q if x['baseline_pnl'] is not None]
    np=[x['new_pnl'] for x in q if x['new_pnl'] is not None]
    return {
      'n':len(q),
      'strong':sum(x['strong'] for x in q),
      'non_target':sum(not x['strong'] for x in q),
      'baseline_exec':sum(x['baseline_executable'] for x in q),
      'new_exec':sum(x['new_executable'] for x in q),
      'new_noexec':sum(not x['new_executable'] for x in q),
      'baseline_pnl':sum(bp),
      'new_pnl':sum(np),
      'delta':sum((x['new_pnl'] if x['new_pnl'] is not None else 0)-(x['baseline_pnl'] if x['baseline_pnl'] is not None else 0) for x in q),
      'baseline_wins':sum((x['baseline_pnl'] or 0)>0 for x in q if x['baseline_pnl'] is not None),
      'new_wins':sum((x['new_pnl'] or 0)>0 for x in q if x['new_pnl'] is not None),
      'baseline_severe':sum(x['baseline_severe'] for x in q),
      'new_severe':sum(x['new_severe'] for x in q),
      'strong_baseline_pnl':sum((x['baseline_pnl'] or 0) for x in q if x['strong']),
      'strong_new_pnl':sum((x['new_pnl'] or 0) for x in q if x['strong'] and x['new_pnl'] is not None),
      'non_target_baseline_pnl':sum((x['baseline_pnl'] or 0) for x in q if not x['strong']),
      'non_target_new_pnl':sum((x['new_pnl'] or 0) for x in q if not x['strong'] and x['new_pnl'] is not None),
      'new_reasons':dict(Counter(x['new_reason'] for x in q)),
      'base_sources':dict(Counter(x['base_source'] for x in q)),
      'new_sources':dict(Counter(x['new_source'] for x in q)),
    }

summary={'stage':'SHORT-CT5A','threshold':0.075,'status':'RESCUE_SHIFT_ANATOMY_COMPLETE','transitions':{},'blocks':{},'source_split':{}}
for tr in sorted(set(x['transition'] for x in rows)):
    q=[x for x in rows if x['transition']==tr]
    summary['transitions'][tr]={'overall':metrics(q),'research':metrics([x for x in q if x['source']=='research']),'fresh':metrics([x for x in q if x['source']=='fresh']),'blocks':{}}
    for b in BLOCKS:
        qb=[x for x in q if x['block']==b]
        if qb:summary['transitions'][tr]['blocks'][b]=metrics(qb)

for b in BLOCKS:
    q=[x for x in rows if x['block']==b]
    summary['blocks'][b]=metrics(q)

for src in ['research','fresh']:
    summary['source_split'][src]=metrics([x for x in rows if x['source']==src])

# classify transition keep/drop upper bound diagnostic: if DROP instead of rescue, contribution = -baseline pnl vs current rescue delta
for tr,z in summary['transitions'].items():
    for scope in ['overall','research','fresh']:
        m=z[scope]
        m['drop_pnl_counterfactual']=0.0
        # relative contribution vs old baseline if dropped = - baseline pnl
        m['drop_delta_vs_old']=-m['baseline_pnl']
        m['drop_vs_current_rescue_delta']=m['drop_delta_vs_old']-m['delta']

# identify worst individual shifted trades under new entry
worst=sorted(rows,key=lambda x:(x['new_pnl'] if x['new_pnl'] is not None else 0))[:30]
best=sorted(rows,key=lambda x:(x['new_pnl'] if x['new_pnl'] is not None else 0),reverse=True)[:20]
summary['worst_new_entries']=worst
summary['best_new_entries']=best

# source-switch/ALT anatomy known from CT2 source strings
alt=[x for x in rows if 'ALT' in (x['new_source'] or '') or 'ALT' in (x['base_source'] or '')]
summary['alt_t3_affected']=metrics(alt)

json.dump(summary,open('/tmp/ct5a_summary.json','w'),indent=2)
with open('/tmp/ct5a_shift_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

print('TOTAL SHIFTED',metrics(rows))
for tr,z in summary['transitions'].items():
    print('\\n###',tr)
    for scope in ['overall','research','fresh']:
        m=z[scope]
        print(scope,'n',m['n'],'strong',m['strong'],'old',round(m['baseline_pnl'],2),'new',round(m['new_pnl'],2),'delta',round(m['delta'],2),
              'dropDelta',round(m['drop_delta_vs_old'],2),'dropVsRescue',round(m['drop_vs_current_rescue_delta'],2),
              'oldSev',m['baseline_severe'],'newSev',m['new_severe'],'newNoExec',m['new_noexec'])
    print(' blocks',[(b,v['n'],v['strong'],round(v['baseline_pnl'],2),round(v['new_pnl'],2),round(v['delta'],2)) for b,v in z['blocks'].items()])
print('\\nALT affected',summary['alt_t3_affected'])
print('\\nWORST')
for x in worst[:20]:print(x['source'],x['symbol'],x['block'],x['transition'],'strong',x['strong'],'old',x['baseline_pnl'],'new',x['new_pnl'],'delta',x['delta_vs_old'],'newReason',x['new_reason'])