from __future__ import annotations
import csv,json,math
from pathlib import Path

UNIV=Path('/work/sd2b2/research/short_detector/results/sd1a_short_universe_655.csv')
WA=Path('/work/sd2b2/research/short_detector/results/sd1c_strong_winner_assignments.csv')
LA=Path('/work/sd2b2/research/short_detector/results/sd1d_loss_cluster_assignments.csv')
TEMP=Path('/data/wd5h4a_temporal_features.csv')
OUT=Path('/work/sd2b2_out'); OUT.mkdir(parents=True,exist_ok=True)
SPLITS=('Discovery','Validation','Reserve')

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def truth(v): return str(v).strip().lower() in ('1','true','yes')
def ff(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except: return None
def phi(tp,selected,targets,n):
    if not (0<selected<n and 0<targets<n): return 0.0
    fp=selected-tp; fn=targets-tp; tn=n-selected-fn
    den=math.sqrt(selected*targets*(n-targets)*(n-selected))
    return (tp*tn-fp*fn)/den if den else 0.0
def rule_str(feature,direction,thr):
    return f"{feature} {direction} {thr:.12g}"

u=read(UNIV); wa=read(WA); la=read(LA); temp=read(TEMP)
tm={r['position_id']:r for r in temp}
wc={r['position_id']:int(r['cluster']) for r in wa}
lc={r['position_id']:int(r['loss_cluster']) for r in la}
wins=[r for r in u if truth(r['strong_win'])]
loss=[r for r in u if r['primary_meta_label']=='META_LOSS']

# Predictor columns are mechanically frozen per contract.
all_cols=list(temp[0].keys())
predictors={}
for h in (1,2,3):
    pref=f't{h}_'
    pred=[]
    for c in all_cols:
        if not c.startswith(pref): continue
        base=c[len(pref):]
        if base in {'confirm_mfe_pct','confirm_mae_pct','confirm_closed_bars','oi_new_point_since_t0','oi_age_s'}: continue
        if base.endswith('_ms') or 'timestamp' in base or base in {'target_ms','latest_closed_ms'}: continue
        if base.startswith(('confirm_','f_micro_','f_f_','delta_')):
            pred.append(c)
    assert len(pred)==105,(h,len(pred))
    predictors[h]=pred

def causal_rows(lane,h,split):
    out=[]
    for cls,pop,cm in ((1,wins,wc),(0,loss,lc)):
        for r in pop:
            if r['split']!=split or cm[r['position_id']]!=lane: continue
            tr=tm[r['position_id']]
            target=ff(tr.get(f't{h}_target_ms')); end=ff(tr.get('primary_label_end_ms'))
            if target is None or end is None or end<=target: continue
            if ff(tr.get(f't{h}_confirm_side_return_pct')) is None: continue
            out.append({
                'position_id':r['position_id'],'symbol':r['symbol'],'target':cls,
                'pnl':float(r['historical_realized_pnl_usdt']),
                'return_pct':float(r['historical_realized_pnl_pct']),
                'tr':tr,
            })
    return out

cache={(lane,h,s):causal_rows(lane,h,s) for lane in (0,1) for h in (1,2,3) for s in SPLITS}

def evaluate(rows,feature,direction,thr):
    valid=[r for r in rows if ff(r['tr'].get(feature)) is not None]
    n=len(valid); targets=sum(r['target'] for r in valid)
    if direction=='>=':
        selected=[r for r in valid if ff(r['tr'].get(feature))>=thr]
    else:
        selected=[r for r in valid if ff(r['tr'].get(feature))<=thr]
    sn=len(selected); tp=sum(r['target'] for r in selected)
    return {
        'n':n,'targets':targets,'selected':sn,'rejected':n-sn,'captured':tp,
        'precision':tp/sn if sn else 0.0,
        'recall':tp/targets if targets else 0.0,
        'baseline_prevalence':targets/n if n else 0.0,
        'precision_lift':(tp/sn)/(targets/n) if sn and targets and n else 0.0,
        'phi':phi(tp,sn,targets,n),
        'pnl_usdt':sum(r['pnl'] for r in selected),
        'avg_return_pct':sum(r['return_pct'] for r in selected)/sn if sn else 0.0,
    }

feature_best=[]
horizon_frozen_dv={}
candidate_rule_count=0

for lane in (0,1):
    for h in (1,2,3):
        D=cache[(lane,h,'Discovery')]; V=cache[(lane,h,'Validation')]
        for feature in predictors[h]:
            dvals=sorted(set(ff(r['tr'].get(feature)) for r in D if ff(r['tr'].get(feature)) is not None))
            if len(dvals)<2: continue
            best=None
            for thr in dvals:
                for direction in ('>=','<='):
                    candidate_rule_count+=1
                    dm=evaluate(D,feature,direction,thr)
                    vm=evaluate(V,feature,direction,thr)
                    if dm['selected']<5 or dm['rejected']<5 or dm['recall']<0.40: continue
                    if vm['selected']<5 or vm['rejected']<5 or vm['recall']<0.40: continue
                    score=min(dm['phi'],vm['phi'])
                    minrec=min(dm['recall'],vm['recall'])
                    selected_total=dm['selected']+vm['selected']
                    rep=rule_str(feature,direction,thr)
                    rec={
                        'lane':lane,'horizon':f'T+{h}','feature':feature,
                        'direction':direction,'threshold':thr,'rule':rep,
                        'dv_score':score,'min_dv_recall':minrec,
                        'D':dm,'V':vm
                    }
                    if best is None:
                        best=rec
                    else:
                        b=best
                        better=False
                        if score>b['dv_score']+1e-12: better=True
                        elif abs(score-b['dv_score'])<=1e-12:
                            if vm['phi']>b['V']['phi']+1e-12: better=True
                            elif abs(vm['phi']-b['V']['phi'])<=1e-12:
                                if minrec>b['min_dv_recall']+1e-12: better=True
                                elif abs(minrec-b['min_dv_recall'])<=1e-12:
                                    bsel=b['D']['selected']+b['V']['selected']
                                    if selected_total<bsel: better=True
                                    elif selected_total==bsel and rep<b['rule']: better=True
                        if better: best=rec
            if best:
                feature_best.append(best)

        hg=[r for r in feature_best if r['lane']==lane and r['horizon']==f'T+{h}']
        assert hg,(lane,h)
        hg.sort(key=lambda r:(r['dv_score'],r['V']['phi'],r['min_dv_recall'],
                              -(r['D']['selected']+r['V']['selected'])),reverse=True)
        # lexical tie is practically irrelevant after numeric keys; apply deterministically
        maxkey=(hg[0]['dv_score'],hg[0]['V']['phi'],hg[0]['min_dv_recall'],
                -(hg[0]['D']['selected']+hg[0]['V']['selected']))
        ties=[r for r in hg if (r['dv_score'],r['V']['phi'],r['min_dv_recall'],
                -(r['D']['selected']+r['V']['selected']))==maxkey]
        horizon_frozen_dv[(lane,h)]=sorted(ties,key=lambda r:r['rule'])[0]

# Preferred horizon designation before Reserve opens.
preferred={}
for lane in (0,1):
    hs=[horizon_frozen_dv[(lane,h)] for h in (1,2,3)]
    qualified=[r for r in hs if r['D']['phi']>=0.20 and r['V']['phi']>=0.20
               and r['D']['recall']>=0.40 and r['V']['recall']>=0.40]
    if qualified:
        preferred[lane]=sorted(qualified,key=lambda r:int(r['horizon'][-1]))[0]['horizon']
    else:
        preferred[lane]=max(hs,key=lambda r:r['dv_score'])['horizon']

# Now open Reserve for frozen per-feature rules and horizon candidates only.
flat_feature=[]
for r in feature_best:
    h=int(r['horizon'][-1])
    rm=evaluate(cache[(r['lane'],h,'Reserve')],r['feature'],r['direction'],r['threshold'])
    r['R']=rm
    flat_feature.append({
        'lane':r['lane'],'horizon':r['horizon'],'feature':r['feature'],
        'direction':r['direction'],'threshold':r['threshold'],'rule':r['rule'],
        'dv_score':r['dv_score'],
        'D_phi':r['D']['phi'],'D_precision':r['D']['precision'],'D_recall':r['D']['recall'],
        'D_selected':r['D']['selected'],'D_captured':r['D']['captured'],
        'V_phi':r['V']['phi'],'V_precision':r['V']['precision'],'V_recall':r['V']['recall'],
        'V_selected':r['V']['selected'],'V_captured':r['V']['captured'],
        'R_phi':rm['phi'],'R_precision':rm['precision'],'R_recall':rm['recall'],
        'R_selected':rm['selected'],'R_captured':rm['captured'],
        'R_precision_lift':rm['precision_lift'],
    })

horizon_results=[]
for lane in (0,1):
    for h in (1,2,3):
        r=horizon_frozen_dv[(lane,h)]
        rm=evaluate(cache[(lane,h,'Reserve')],r['feature'],r['direction'],r['threshold'])
        r['R']=rm
        phis=[r[s]['phi'] for s in ('D','V','R')]
        recalls=[r[s]['recall'] for s in ('D','V','R')]
        if min(phis)>=0.25 and min(recalls)>=0.40:
            tier='STRONG'
        elif min(phis)>=0.15 and min(recalls)>=0.40:
            tier='PROMISING'
        else:
            tier='FAIL'
        horizon_results.append({
            'lane':lane,'horizon':f'T+{h}','preferred_pre_reserve':preferred[lane]==f'T+{h}',
            'feature':r['feature'],'direction':r['direction'],'threshold':r['threshold'],'rule':r['rule'],
            'tier':tier,'D':r['D'],'V':r['V'],'R':rm,
            'dv_score':r['dv_score'],
        })

# preferred lane result
preferred_results={}
for lane in (0,1):
    preferred_results[str(lane)]=next(r for r in horizon_results if r['lane']==lane and r['horizon']==preferred[lane])

# Feature robustness around horizon candidate: count per-feature frozen rules passing tiers.
robustness={}
for lane in (0,1):
    for h in (1,2,3):
        g=[r for r in feature_best if r['lane']==lane and r['horizon']==f'T+{h}']
        strong=promising=0
        for r in g:
            vals=[r[s]['phi'] for s in ('D','V','R')]
            recs=[r[s]['recall'] for s in ('D','V','R')]
            if min(vals)>=.25 and min(recs)>=.40: strong+=1
            if min(vals)>=.15 and min(recs)>=.40: promising+=1
        robustness[f'lane{lane}_T+{h}']={'feature_rules_n':len(g),'strong_n':strong,'promising_or_better_n':promising}

with (OUT/'sd2b2_per_feature_frozen_rules.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(flat_feature[0]));w.writeheader();w.writerows(flat_feature)

# horizon compact csv
hrflat=[]
for r in horizon_results:
    z={k:r[k] for k in ('lane','horizon','preferred_pre_reserve','feature','direction','threshold','rule','tier','dv_score')}
    for s in ('D','V','R'):
        for k in ('n','targets','selected','captured','precision','recall','baseline_prevalence','precision_lift','phi','pnl_usdt','avg_return_pct'):
            z[f'{s}_{k}']=r[s][k]
    hrflat.append(z)
with (OUT/'sd2b2_frozen_horizon_rules.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(hrflat[0]));w.writeheader();w.writerows(hrflat)

payload={
    'stage':'SD-2B2','status':'COMPLETE','candidate_rule_count':candidate_rule_count,
    'predictors_per_horizon':105,'feature_frozen_rules_n':len(feature_best),
    'preferred_horizon_pre_reserve':{str(k):v for k,v in preferred.items()},
    'horizon_results':horizon_results,
    'preferred_results':preferred_results,
    'robustness':robustness,
}
(OUT/'sd2b2_summary.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
print(json.dumps(payload,indent=2))