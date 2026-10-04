from __future__ import annotations
import csv, json, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FEATURES=Path('/app/data/wd5h1_thesis_labeled_features.csv')
LABELS=Path('/app/data/wd5h3a_triple_barrier_labels.csv')
TEMPORAL=Path('/app/data/wd5h4a_temporal_features.csv')
OUT=Path('/tmp/sd1a_out')
OUT.mkdir(parents=True,exist_ok=True)

def read(path):
    with path.open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))

def f(v):
    try:
        return float(v)
    except Exception:
        return None

def i(v):
    try:
        return int(v)
    except Exception:
        return None

def iso(ms):
    if ms is None: return None
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def mfe_bucket(x):
    if x < 0.30: return '<0.30%'
    if x < 0.50: return '0.30-<0.50%'
    if x < 1.00: return '0.50-<1.00%'
    if x < 1.50: return '1.00-<1.50%'
    if x < 2.00: return '1.50-<2.00%'
    if x < 3.00: return '2.00-<3.00%'
    if x < 5.00: return '3.00-<5.00%'
    return '>=5.00%'

features=read(FEATURES)
labels=read(LABELS)
temporal=read(TEMPORAL)
fm={r['meta_position_id']:r for r in features}
tm={r['position_id']:r for r in temporal}

resolved=[
    r for r in labels
    if r['side']=='SHORT' and r['primary_meta_label'] in {'META_WIN','META_LOSS'}
]
resolved.sort(key=lambda r:int(r['opened_at_ms']))

assert len(resolved)==655, len(resolved)
assert sum(r['primary_meta_label']=='META_WIN' for r in resolved)==163
assert sum(r['primary_meta_label']=='META_LOSS' for r in resolved)==492

n=len(resolved)
d_end=int(n*0.60)
v_end=d_end+int(n*0.20)
assert (d_end,v_end,n)==(393,524,655)

rows=[]
for idx,r in enumerate(resolved):
    pid=r['position_id']
    fr=fm[pid]
    tr=tm.get(pid,{})
    split='Discovery' if idx<d_end else ('Validation' if idx<v_end else 'Reserve')
    mfe=f(r['historical_max_mfe_pct'])
    mae=f(r['historical_min_mae_pct'])
    rpnl=f(r['historical_realized_pnl'])
    rpct=f(r['historical_realized_pnl_pct'])
    strong=(r['primary_meta_label']=='META_WIN' and mfe is not None and mfe>=1.0)
    weak=(r['primary_meta_label']=='META_WIN' and not strong)
    rec={
        'position_id':pid,
        'signal_id':r['signal_id'],
        'symbol':r['symbol'],
        'side':r['side'],
        'opened_at_ms':i(r['opened_at_ms']),
        'closed_at_ms':i(fr.get('meta_closed_at_ms')) if 'meta_closed_at_ms' in fr else None,
        'split':split,
        'primary_meta_label':r['primary_meta_label'],
        'strong_win':strong,
        'weak_meta_win':weak,
        'historical_wd1_outcome':r['historical_wd1_outcome'],
        'historical_max_mfe_pct':mfe,
        'historical_min_mae_pct':mae,
        'historical_realized_pnl_usdt':rpnl,
        'historical_realized_pnl_pct':rpct,
        'historical_realized_positive':rpnl is not None and rpnl>0,
        'mfe_bucket':mfe_bucket(mfe),
        'peak_mfe_dollar_equiv':mfe*5.0,
        'primary_label_end_ms':i(r['primary_label_end_ms']),
        'primary_minutes_to_label':f(r['primary_minutes_to_label']),
    }
    for h in (1,2,3):
        p=f't{h}_confirm_side_return_pct'
        t=f't{h}_target_ms'
        raw=tr.get(p,'') not in ('',None)
        target=i(tr.get(t))
        rec[f't{h}_raw_available']=raw
        rec[f't{h}_target_ms']=target
        rec[f't{h}_causal_survivor']=bool(raw and target is not None and rec['primary_label_end_ms'] is not None and rec['primary_label_end_ms']>target)
    rows.append(rec)

assert sum(r['strong_win'] for r in rows)==99

def med(vals):
    vals=[x for x in vals if x is not None]
    return statistics.median(vals) if vals else None

def mean(vals):
    vals=[x for x in vals if x is not None]
    return statistics.mean(vals) if vals else None

def metrics(g):
    return {
        'n':len(g),
        'meta_win_n':sum(r['primary_meta_label']=='META_WIN' for r in g),
        'meta_loss_n':sum(r['primary_meta_label']=='META_LOSS' for r in g),
        'strong_win_n':sum(r['strong_win'] for r in g),
        'weak_meta_win_n':sum(r['weak_meta_win'] for r in g),
        'strong_win_prevalence_pct':100*sum(r['strong_win'] for r in g)/len(g) if g else None,
        'historical_realized_positive_n':sum(r['historical_realized_positive'] for r in g),
        'historical_realized_positive_rate_pct':100*sum(r['historical_realized_positive'] for r in g)/len(g) if g else None,
        'historical_realized_pnl_usdt':sum(r['historical_realized_pnl_usdt'] for r in g),
        'historical_realized_pct_mean':mean([r['historical_realized_pnl_pct'] for r in g]),
        'mfe_available_n':sum(r['historical_max_mfe_pct'] is not None for r in g),
        'mfe_median_pct':med([r['historical_max_mfe_pct'] for r in g]),
        'mfe_mean_pct':mean([r['historical_max_mfe_pct'] for r in g]),
        'mae_median_pct':med([r['historical_min_mae_pct'] for r in g]),
        'peak_mfe_dollar_equiv':sum(r['peak_mfe_dollar_equiv'] for r in g),
        't1_raw_available_n':sum(r['t1_raw_available'] for r in g),
        't1_causal_survivor_n':sum(r['t1_causal_survivor'] for r in g),
        't2_raw_available_n':sum(r['t2_raw_available'] for r in g),
        't2_causal_survivor_n':sum(r['t2_causal_survivor'] for r in g),
        't3_raw_available_n':sum(r['t3_raw_available'] for r in g),
        't3_causal_survivor_n':sum(r['t3_causal_survivor'] for r in g),
    }

mfe_order=['<0.30%','0.30-<0.50%','0.50-<1.00%','1.00-<1.50%','1.50-<2.00%','2.00-<3.00%','3.00-<5.00%','>=5.00%']
mfe_dist=[]
for b in mfe_order:
    g=[r for r in rows if r['mfe_bucket']==b]
    mfe_dist.append({
        'mfe_bucket':b,
        **metrics(g),
    })

wd1=[]
for lab,count in sorted(Counter(r['historical_wd1_outcome'] for r in rows).items()):
    g=[r for r in rows if r['historical_wd1_outcome']==lab]
    wd1.append({
        'wd1_outcome':lab,
        **metrics(g),
    })

meta=[]
for lab in ('META_WIN','META_LOSS'):
    g=[r for r in rows if r['primary_meta_label']==lab]
    meta.append({'primary_meta_label':lab,**metrics(g)})

splits={s:metrics([r for r in rows if r['split']==s]) for s in ('Discovery','Validation','Reserve')}

# Feature source audit
feature_cols=[c for c in features[0] if c.startswith('f_')]
short_ids={r['position_id'] for r in rows}
short_feature_rows=[fm[x] for x in short_ids]
feature_nonempty_counts={c:sum(r.get(c,'') not in ('',None) for r in short_feature_rows) for c in feature_cols}
fully_covered=sum(v==len(rows) for v in feature_nonempty_counts.values())
partial_covered=sum(0<v<len(rows) for v in feature_nonempty_counts.values())
zero_covered=sum(v==0 for v in feature_nonempty_counts.values())

summary={
    'stage':'SD-1A',
    'status':'PASS_FREEZE',
    'contract':{
        'resolved_rule':"side=SHORT and primary_meta_label in {META_WIN,META_LOSS}",
        'strong_win_rule':"META_WIN and historical_max_mfe_pct >= 1.00%",
        'split_rule':'chronological 60/20/20 after resolved-SHORT filter',
        'peak_mfe_dollar_equiv_rule':'historical_max_mfe_pct * $5',
        'modeling_or_runtime_authority':'NONE',
    },
    'universe':metrics(rows),
    'time_window':{
        'opened_min_ms':min(r['opened_at_ms'] for r in rows),
        'opened_max_ms':max(r['opened_at_ms'] for r in rows),
        'opened_min_utc':iso(min(r['opened_at_ms'] for r in rows)),
        'opened_max_utc':iso(max(r['opened_at_ms'] for r in rows)),
        'label_end_max_ms':max(r['primary_label_end_ms'] for r in rows),
        'label_end_max_utc':iso(max(r['primary_label_end_ms'] for r in rows)),
    },
    'split_metrics':splits,
    'meta_label_anatomy':meta,
    'mfe_distribution':mfe_dist,
    'wd1_outcome_anatomy':wd1,
    'feature_coverage':{
        't0_feature_columns_n':len(feature_cols),
        'fully_covered_feature_n':fully_covered,
        'partially_covered_feature_n':partial_covered,
        'zero_covered_feature_n':zero_covered,
        'row_coverage_n':len(short_feature_rows),
    },
    'source_counts':{
        'features_rows':len(features),
        'labels_rows':len(labels),
        'temporal_rows':len(temporal),
        'all_short_rows_before_timeout_exclusion':sum(r['side']=='SHORT' for r in labels),
        'short_timeout_excluded_n':sum(r['side']=='SHORT' and r['primary_meta_label']=='TIMEOUT' for r in labels),
    }
}

# csv outputs
detail_fields=list(rows[0].keys())
with (OUT/'sd1a_short_universe_655.csv').open('w',newline='',encoding='utf-8') as fobj:
    w=csv.DictWriter(fobj,fieldnames=detail_fields);w.writeheader();w.writerows(rows)

with (OUT/'sd1a_short_mfe_distribution.csv').open('w',newline='',encoding='utf-8') as fobj:
    w=csv.DictWriter(fobj,fieldnames=list(mfe_dist[0].keys()));w.writeheader();w.writerows(mfe_dist)

with (OUT/'sd1a_short_wd1_outcome_anatomy.csv').open('w',newline='',encoding='utf-8') as fobj:
    w=csv.DictWriter(fobj,fieldnames=list(wd1[0].keys()));w.writeheader();w.writerows(wd1)

(OUT/'sd1a_short_universe_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

print(json.dumps(summary,indent=2))