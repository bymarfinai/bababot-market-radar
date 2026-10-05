import csv,itertools,json,math
from collections import defaultdict
from pathlib import Path

ROWS=list(csv.DictReader(open('/tmp/s10j_normalized_detail.csv')))
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']

def fv(r,k):
    try:
        x=float(r[k]);return x if math.isfinite(x) else None
    except:return None
def strong(r): return r['strong']=='True'

# deliberately compact, non-duplicative candidate set from S10J-3
CANDS=[
 {'name':'T1_REL_OVERHEAT_HIGH','lane':1,'col':'f_new_overheat_pressure__lrz64','op':'>=','thr':0.5,'family':'overheat'},
 {'name':'T1_REL_MICROVOL_LOW','lane':1,'col':'f_micro_volume_ratio_last_vs_prev10__pct128','op':'<=','thr':0.30,'family':'microvol'},
 {'name':'T2_REL_T1CONF_LOW','lane':2,'col':'t1_confirm_side_return_pct__rz128','op':'<=','thr':-0.5,'family':'confirmation'},
 {'name':'T2_REL_T2CONF_LOW','lane':2,'col':'t2_confirm_side_return_pct__pct128','op':'<=','thr':0.30,'family':'confirmation2'},
 {'name':'T2_REL_FLOW_SUPPORT_LOW','lane':2,'col':'f_new_flow_support__lpct64','op':'<=','thr':0.30,'family':'flow_support'},
 {'name':'T3_REL_MICROVOL_HIGH','lane':3,'col':'f_micro_volume_ratio_last_vs_prev10__pct128','op':'>=','thr':0.70,'family':'microvol'},
 {'name':'T3_REL_T3CONF_LOW','lane':3,'col':'t3_confirm_side_return_pct__pct128','op':'<=','thr':0.30,'family':'confirmation'},
]

def hit(r,c):
    if int(r['lane'])!=c['lane']: return False
    x=fv(r,c['col'])
    if x is None:return False
    return x>=c['thr'] if c['op']=='>=' else x<=c['thr']

def met(q):
    n=len(q);s=sum(strong(r) for r in q);non=n-s
    return {'n':n,'strong':s,'non':non,'precision':s/n if n else 0}

BASE=met(ROWS)
RES=[r for r in ROWS if r['source']=='research']
FR=[r for r in ROWS if r['source']=='fresh']
BRES=met(RES);BFR=met(FR)

def evaluate(combo):
    veto=[r for r in ROWS if any(hit(r,c) for c in combo)]
    keep=[r for r in ROWS if r not in veto]
    vres=[r for r in RES if any(hit(r,c) for c in combo)]
    kres=[r for r in RES if r not in vres]
    vfr=[r for r in FR if any(hit(r,c) for c in combo)]
    kfr=[r for r in FR if r not in vfr]
    out={'rules':[c['name'] for c in combo],'n_rules':len(combo),
         'research':{'keep':met(kres),'veto':met(vres)},
         'fresh':{'keep':met(kfr),'veto':met(vfr)},
         'all':{'keep':met(keep),'veto':met(veto)},'blocks':{}}
    out['research']['strong_retention']=out['research']['keep']['strong']/BRES['strong']
    out['research']['non_retention']=out['research']['keep']['non']/BRES['non']
    out['research']['precision_delta']=out['research']['keep']['precision']-BRES['precision']
    out['fresh']['strong_retention']=out['fresh']['keep']['strong']/BFR['strong']
    out['fresh']['non_retention']=out['fresh']['keep']['non']/BFR['non']
    out['fresh']['precision_delta']=out['fresh']['keep']['precision']-BFR['precision']
    goodblocks=0;badblocks=0
    minret=1
    mindelta=999
    for b in BLOCKS:
        q=[r for r in ROWS if r['block']==b]
        v=[r for r in q if any(hit(r,c) for c in combo)]
        k=[r for r in q if r not in v]
        bm=met(q);vm=met(v);km=met(k)
        ret=km['strong']/bm['strong'] if bm['strong'] else 1
        delta=km['precision']-bm['precision'] if km['n'] else -1
        non_rem=(vm['non']/bm['non']) if bm['non'] else 0
        str_rem=(vm['strong']/bm['strong']) if bm['strong'] else 0
        out['blocks'][b]={'base':bm,'keep':km,'veto':vm,'strong_retention':ret,'precision_delta':delta,'strong_removal_rate':str_rem,'non_removal_rate':non_rem}
        minret=min(minret,ret);mindelta=min(mindelta,delta)
        if delta>0 and non_rem>=str_rem:goodblocks+=1
        elif delta<0 or str_rem>non_rem:badblocks+=1
    out['good_blocks']=goodblocks;out['bad_blocks']=badblocks;out['min_block_strong_retention']=minret;out['min_precision_delta']=mindelta
    # score rewards fresh/research precision gain and non-target pruning, penalizes winner loss
    rnpr=1-out['research']['non_retention'];fnpr=1-out['fresh']['non_retention']
    rwloss=1-out['research']['strong_retention'];fwloss=1-out['fresh']['strong_retention']
    out['score']=(
      5*out['research']['precision_delta']+6*out['fresh']['precision_delta']+
      1.5*rnpr+2*fnpr-4*rwloss-5*fwloss+0.15*goodblocks-0.3*badblocks
    )
    return out

ALL=[]
for k in range(1,5):
  for combo in itertools.combinations(CANDS,k):
    # no >2 rules in same lane
    cnt=defaultdict(int)
    for c in combo:cnt[c['lane']]+=1
    if max(cnt.values())>2:continue
    ALL.append(evaluate(combo))

# hard gate variants
STRICT=[x for x in ALL if x['research']['strong_retention']>=.90 and x['fresh']['strong_retention']>=.90 and x['min_block_strong_retention']>=.80 and x['bad_blocks']==0]
RELAX=[x for x in ALL if x['research']['strong_retention']>=.90 and x['fresh']['strong_retention']>=.90 and x['min_block_strong_retention']>=.75 and x['bad_blocks']<=1 and x['good_blocks']>=5]
for arr in (STRICT,RELAX):
    arr.sort(key=lambda x:(-x['score'],-x['good_blocks'],-x['fresh']['keep']['precision'],-x['research']['keep']['precision'],x['n_rules']))

print('BASE research',BRES,'fresh',BFR)
print('strict',len(STRICT),'relax',len(RELAX))
def show(name,arr,n=25):
  print('\n###',name)
  for x in arr[:n]:
    print(x['rules'],'score',round(x['score'],4),
      'R keep',x['research']['keep'],'Rret',round(x['research']['strong_retention'],4),'RΔp',round(x['research']['precision_delta'],4),
      'F keep',x['fresh']['keep'],'Fret',round(x['fresh']['strong_retention'],4),'FΔp',round(x['fresh']['precision_delta'],4),
      'good/bad',x['good_blocks'],x['bad_blocks'],'minRet',round(x['min_block_strong_retention'],4))
    print(' blocks',[(b,round(x['blocks'][b]['precision_delta'],4),round(x['blocks'][b]['strong_retention'],3),x['blocks'][b]['veto']['n']) for b in BLOCKS])
show('STRICT',STRICT)
show('RELAX',RELAX)

# Pareto: retention vs non-target removal pooled
P=[]
for x in ALL:
    if x['research']['strong_retention']<.85 or x['fresh']['strong_retention']<.85:continue
    dominated=False
    for y in ALL:
        if y is x:continue
        if (y['research']['strong_retention']>=x['research']['strong_retention'] and
            y['fresh']['strong_retention']>=x['fresh']['strong_retention'] and
            y['research']['non_retention']<=x['research']['non_retention'] and
            y['fresh']['non_retention']<=x['fresh']['non_retention'] and
            (y['research']['strong_retention']>x['research']['strong_retention'] or y['fresh']['strong_retention']>x['fresh']['strong_retention'] or y['research']['non_retention']<x['research']['non_retention'] or y['fresh']['non_retention']<x['fresh']['non_retention'])):
            dominated=True;break
    if not dominated:P.append(x)
P.sort(key=lambda x:(-x['fresh']['strong_retention'],x['fresh']['non_retention']))
print('\n### PARETO')
for x in P[:30]:
 print(x['rules'],'Rret',round(x['research']['strong_retention'],3),'RnonRet',round(x['research']['non_retention'],3),'Fret',round(x['fresh']['strong_retention'],3),'FnonRet',round(x['fresh']['non_retention'],3),'good/bad',x['good_blocks'],x['bad_blocks'])

Path('/tmp/s10j4_combo_frontier.json').write_text(json.dumps({'stage':'S10J4','candidates':CANDS,'strict':STRICT,'relaxed':RELAX,'pareto':P,'all':ALL},indent=2))