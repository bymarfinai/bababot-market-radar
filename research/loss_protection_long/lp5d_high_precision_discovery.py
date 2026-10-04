from __future__ import annotations
import csv, io, json, math, zipfile, requests, itertools, threading
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data
from research.wrong_direction.wrong_direction_labels import initialize_wd1_store
from market_radar.persistence import _postgres_connect

BASE=Path(__file__).resolve().parent
RESULTS=BASE/'results'
RESULTS.mkdir(exist_ok=True)
IDS=[x.strip() for x in (BASE/'data'/'LP5D_454_COHORT_IDS.txt').read_text(encoding='utf-8').splitlines() if x.strip()]
positions,_,_=load_market_data(IDS)
initialize_wd1_store()
with _postgres_connect() as conn:
    with conn.cursor() as cur:
        cur.execute("select position_id,outcome_label,max_mfe_pct from wd1_trade_labels where position_id = any(%s)",(IDS,))
        lab={r[0]:{'label':r[1],'hist_mfe':float(r[2])} for r in cur.fetchall()}

def split_of(ms):
    if ms <= 1790772034348: return 'D'
    if ms <= 1790798717384: return 'V'
    return 'R'

OFFSETS=list(range(60,121,5))
rows=[]
for pid in IDS:
    p=positions[pid]
    rows.append({
      'pid':pid,'symbol':json.loads(p.get('raw_json') or '{}').get('symbol') or pid.split(':')[1],'open':int(p['opened_at_ms']),'close':int(p['closed_at_ms']),
      'entry':float(p['entry_price']),'pnl':float(p['realized_pnl']),
      'split':split_of(int(p['opened_at_ms'])),'label':lab[pid]['label'],'hist_mfe':lab[pid]['hist_mfe']
    })

by=defaultdict(list)
for r in rows:
    day=datetime.fromtimestamp(r['open']/1000,timezone.utc).date().isoformat()
    by[(r['symbol'],day)].append(r)

local=threading.local()
def sess():
    if not hasattr(local,'s'): local.s=requests.Session()
    return local.s

def fetch_group(item):
    (sym,day),arr=item
    url=f"https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
    resp=sess().get(url,timeout=90)
    if resp.status_code != 200:
        return {},(sym,day,f'HTTP_{resp.status_code}')
    states={}
    for r in arr:
        states[r['pid']]={'r':r,'i':0,'last':r['entry'],'maxr':0.0,'minr':0.0,'snaps':{}}
    min_start=min(r['open'] for r in arr)
    max_end=max(min(r['open']+120000,r['close']) for r in arr)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        with z.open(z.namelist()[0]) as raw:
            rd=csv.reader(io.TextIOWrapper(raw,encoding='utf-8'))
            first=next(rd,None)
            it=rd if first and first[0]=='agg_trade_id' else itertools.chain([first],rd)
            for x in it:
                if not x: continue
                try: px=float(x[1]); ts=int(x[5])
                except: continue
                if ts < min_start: continue
                if ts > max_end: break
                for st in states.values():
                    r=st['r']; end=min(r['open']+120000,r['close'])
                    if ts < r['open'] or ts > end: continue
                    while st['i']<len(OFFSETS) and r['open']+OFFSETS[st['i']]*1000 < ts:
                        sec=OFFSETS[st['i']]
                        st['snaps'][sec]=(st['last'],st['maxr'],st['minr'])
                        st['i']+=1
                    ret=100.0*(px/r['entry']-1.0)
                    st['last']=px
                    if ret>st['maxr']: st['maxr']=ret
                    if ret<st['minr']: st['minr']=ret
                    while st['i']<len(OFFSETS) and r['open']+OFFSETS[st['i']]*1000 == ts:
                        sec=OFFSETS[st['i']]
                        st['snaps'][sec]=(st['last'],st['maxr'],st['minr'])
                        st['i']+=1
    out={}
    for pid,st in states.items():
        r=st['r']
        while st['i']<len(OFFSETS):
            sec=OFFSETS[st['i']]
            st['snaps'][sec]=(st['last'],st['maxr'],st['minr'])
            st['i']+=1
        out[pid]=st['snaps']
    return out,None

snapshots={}
errors=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    futs=[ex.submit(fetch_group,item) for item in by.items()]
    done=0
    for f in as_completed(futs):
        o,e=f.result(); snapshots.update(o)
        if e: errors.append(e)
        done+=1
        if done%50==0 or done==len(futs):
            print('ARCHIVE',done,'/',len(futs),flush=True)

def auc(y,s):
    pos=[v for yy,v in zip(y,s) if yy==1]; neg=[v for yy,v in zip(y,s) if yy==0]
    if not pos or not neg: return None
    wins=0.0
    for a in pos:
        for b in neg:
            if a>b: wins+=1
            elif a==b: wins+=0.5
    return wins/(len(pos)*len(neg))

def fit_logit(X,y):
    n=len(X); k=len(X[0])
    mu=[sum(row[j] for row in X)/n for j in range(k)]
    sd=[]
    for j in range(k):
        v=sum((row[j]-mu[j])**2 for row in X)/max(1,n-1)
        sd.append(math.sqrt(v) if v>1e-12 else 1.0)
    Z=[[1.0]+[(row[j]-mu[j])/sd[j] for j in range(k)] for row in X]
    w=[0.0]*(k+1)
    lr=0.08
    for it in range(1200):
        g=[0.0]*(k+1)
        for zi,yi in zip(Z,y):
            z=sum(a*b for a,b in zip(w,zi))
            p=1/(1+math.exp(-max(-30,min(30,z))))
            e=p-yi
            for j in range(k+1): g[j]+=e*zi[j]
        for j in range(1,k+1): g[j]+=0.02*w[j]
        scale=lr/n
        for j in range(k+1): w[j]-=scale*g[j]
        if it in (399,799): lr*=0.5
    return mu,sd,w

def predict(model,X):
    mu,sd,w=model; out=[]
    for row in X:
        z=w[0]+sum(w[j+1]*((row[j]-mu[j])/sd[j]) for j in range(len(row)))
        out.append(1/(1+math.exp(-max(-30,min(30,z)))))
    return out

def class_kind(r):
    if r['pnl']>0: return 'WIN'
    if r['label']=='TRUE_WRONG_DIRECTION': return 'WD'
    if r['hist_mfe']<0.5: return 'PRE05'
    return 'OTHERLOSS'

def duel_at(sec,badkind):
    data=[]
    for r in rows:
        kind=class_kind(r)
        bad = (kind=='WD') if badkind=='WD' else (r['pnl']<=0 and r['hist_mfe']<0.5)
        win = r['pnl']>0
        if not (bad or win): continue
        boundary=r['open']+sec*1000
        if r['close']<=boundary: continue
        sn=snapshots.get(r['pid'],{}).get(sec)
        if not sn: continue
        px,mfe,mae=sn
        side=100.0*(px/r['entry']-1.0)
        data.append({'split':r['split'],'y':1 if bad else 0,'x':[side,mfe,mae],'side':side,'mfe':mfe,'mae':mae,'label':r['label']})
    train=[q for q in data if q['split']=='D']
    if len(set(q['y'] for q in train))<2: return None
    model=fit_logit([q['x'] for q in train],[q['y'] for q in train])
    out={'sec':sec}
    for sp in 'DVR':
        z=[q for q in data if q['split']==sp]
        yy=[q['y'] for q in z]
        pp=predict(model,[q['x'] for q in z]) if z else []
        out[sp+'_auc']=auc(yy,pp) if z else None
        out[sp+'_bad']=sum(yy); out[sp+'_win']=len(yy)-sum(yy)
        out[sp+'_side_auc_lowbad']=auc(yy,[-q['side'] for q in z]) if z else None
        out[sp+'_mfe_auc_lowbad']=auc(yy,[-q['mfe'] for q in z]) if z else None
        out[sp+'_mae_auc_lowbad']=auc(yy,[-q['mae'] for q in z]) if z else None
    badrows=[q for q in data if q['y']==1]; winrows=[q for q in data if q['y']==0]
    def med(vals):
        vals=sorted(vals); n=len(vals)
        if not n:return None
        return vals[n//2] if n%2 else (vals[n//2-1]+vals[n//2])/2
    for name,grp in [('bad',badrows),('win',winrows)]:
        out[name+'_n']=len(grp)
        out[name+'_side_med']=med([q['side'] for q in grp])
        out[name+'_mfe_med']=med([q['mfe'] for q in grp])
        out[name+'_mae_med']=med([q['mae'] for q in grp])
    return out

wd=[duel_at(s,'WD') for s in OFFSETS]
pre=[duel_at(s,'PRE05') for s in OFFSETS]
wd=[x for x in wd if x]; pre=[x for x in pre if x]

def earliest(arr,minauc,mincov,total_bad):
    for x in arr:
        aa=[x[k] for k in ('D_auc','V_auc','R_auc') if x[k] is not None]
        if len(aa)==3 and min(aa)>=minauc and x['bad_n']/total_bad>=mincov:
            return x['sec']
    return None

summary={
 'stage':'LP-5C',
 'contract':{
  'universe':'current 454 OPEN LONG',
  'source':'Binance USD-M daily aggTrades archive',
  'sampling':'5-second boundaries 60..120s after actual entry; latest trade at/before boundary with carry-forward; running MFE/MAE from archived trades since entry',
  'alive_filter':'historical close must be strictly after boundary',
  'split':'frozen chronological D/V/R boundaries from 1,236 dataset',
  'model':'3-feature logistic side return + running MFE + running MAE; fit separately at each second on D only, evaluate unchanged V/R'
 },
 'coverage':{'trades':len(rows),'symbol_days':len(by),'archive_groups_ok':len(by)-len(errors),'errors':errors},
 'wd':wd,'pre05':pre,
 'predeclared_stability':{
  'wd':'min D/V/R AUC >=0.75 and >=60% of original 96 WD still alive',
  'pre05':'min D/V/R AUC >=0.70 and >=70% of original 120 pre-0.5 losses still alive'
 },
 'earliest_stable_wd_sec':earliest(wd,0.75,0.60,96),
 'earliest_stable_pre05_sec':earliest(pre,0.70,0.70,120)
}
joint=None
for s in OFFSETS:
    a=next(x for x in wd if x['sec']==s); b=next(x for x in pre if x['sec']==s)
    if min(a['D_auc'],a['V_auc'],a['R_auc'])>=0.75 and a['bad_n']/96>=0.60 and min(b['D_auc'],b['V_auc'],b['R_auc'])>=0.70 and b['bad_n']/120>=0.70:
        joint=s;break
summary['earliest_joint_stable_sec']=joint

open('/tmp/LP5C_RAW5S_SUMMARY.json','w').write(json.dumps(summary,indent=2))
with open('/tmp/LP5C_RAW5S_CURVES.csv','w',newline='') as f:
    fields=['lane','sec','D_auc','V_auc','R_auc','D_bad','D_win','V_bad','V_win','R_bad','R_win','bad_n','win_n','bad_side_med','win_side_med','bad_mfe_med','win_mfe_med','bad_mae_med','win_mae_med','D_side_auc_lowbad','V_side_auc_lowbad','R_side_auc_lowbad','D_mfe_auc_lowbad','V_mfe_auc_lowbad','R_mfe_auc_lowbad']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for lane,arr in [('WD',wd),('PRE05',pre)]:
        for x in arr:
            w.writerow({k:(lane if k=='lane' else x.get(k)) for k in fields})
print(json.dumps(summary,indent=2),flush=True)


# --- LP-5D high-precision extension ---
TIMES = (75, 80, 85, 90)
OUT = RESULTS

def is_target(r):
    return r['pnl'] <= 0 and r['hist_mfe'] < 0.5

def is_winner(r):
    return r['pnl'] > 0

def make_records(sec):
    out = []
    for r in rows:
        boundary = r['open'] + sec * 1000
        if r['close'] <= boundary:
            continue
        sn = snapshots.get(r['pid'], {}).get(sec)
        if not sn:
            continue
        px, mfe, mae = sn
        side = 100.0 * (px / r['entry'] - 1.0)
        out.append({
            **r,
            'sec': sec,
            'side': side,
            'mfe': mfe,
            'mae': mae,
            'target_pre05': is_target(r),
            'winner': is_winner(r),
            'wrong_direction': r['label'] == 'TRUE_WRONG_DIRECTION',
        })
    return out

records = {sec: make_records(sec) for sec in TIMES}

def metrics(group, fired):
    tgt_alive = sum(x['target_pre05'] for x in group)
    win_alive = sum(x['winner'] for x in group)
    fire_n = len(fired)
    tgt = sum(x['target_pre05'] for x in fired)
    win = sum(x['winner'] for x in fired)
    other_loss = fire_n - tgt - win
    wd = sum(x['wrong_direction'] for x in fired)
    return {
        'alive_n': len(group),
        'alive_target_n': tgt_alive,
        'alive_winner_n': win_alive,
        'fire_n': fire_n,
        'target_n': tgt,
        'winner_n': win,
        'other_loss_n': other_loss,
        'wd_n': wd,
        'target_precision': (tgt / fire_n) if fire_n else 0.0,
        'target_recall_alive': (tgt / tgt_alive) if tgt_alive else 0.0,
        'winner_fire_rate': (win / win_alive) if win_alive else 0.0,
    }

def dev_pass(m):
    return (
        m['target_precision'] >= 0.80
        and m['winner_fire_rate'] <= 0.05
        and m['target_recall_alive'] >= 0.10
        and m['fire_n'] >= 5
    )

def val_pass(m):
    return (
        m['target_precision'] >= 0.70
        and m['winner_fire_rate'] <= 0.05
        and m['target_recall_alive'] >= 0.10
        and m['fire_n'] >= 3
    )

def eval_spec(group, spec, score_map=None):
    fam = spec['family']
    if fam == 'SIDE':
        fired = [x for x in group if x['side'] <= spec['side_max']]
    elif fam == 'MFE':
        fired = [x for x in group if x['mfe'] <= spec['mfe_max']]
    elif fam == 'SIDE_AND_MFE':
        fired = [x for x in group if x['side'] <= spec['side_max'] and x['mfe'] <= spec['mfe_max']]
    elif fam == 'LOGIT3':
        fired = [x for x in group if score_map[x['pid']] >= spec['score_min']]
    else:
        raise ValueError(fam)
    return metrics(group, fired), fired

def candidate_rank(item):
    m = item['D']
    fam_order = {'SIDE': 0, 'MFE': 1, 'SIDE_AND_MFE': 2, 'LOGIT3': 3}
    return (m['target_n'], m['target_precision'], -m['winner_fire_rate'], -item['sec'], -fam_order[item['family']])

carried = []
models = {}
scores_by_sec = {}

for sec in TIMES:
    allr = records[sec]
    D = [x for x in allr if x['split'] == 'D']

    # Logistic model is fit only on Development PRE05 + winner controls.
    train = [x for x in D if x['target_pre05'] or x['winner']]
    model = fit_logit([[x['side'], x['mfe'], x['mae']] for x in train], [1 if x['target_pre05'] else 0 for x in train])
    models[sec] = model
    scores = predict(model, [[x['side'], x['mfe'], x['mae']] for x in allr])
    score_map = {x['pid']: s for x, s in zip(allr, scores)}
    scores_by_sec[sec] = score_map

    families = defaultdict(list)

    for th in sorted(set(x['side'] for x in D)):
        spec = {'family': 'SIDE', 'side_max': th}
        m, _ = eval_spec(D, spec)
        if dev_pass(m):
            families['SIDE'].append({'sec': sec, **spec, 'D': m})

    for th in sorted(set(x['mfe'] for x in D)):
        spec = {'family': 'MFE', 'mfe_max': th}
        m, _ = eval_spec(D, spec)
        if dev_pass(m):
            families['MFE'].append({'sec': sec, **spec, 'D': m})

    side_vals = sorted(set(x['side'] for x in D if x['target_pre05']))
    mfe_vals = sorted(set(x['mfe'] for x in D if x['target_pre05']))
    for s_th in side_vals:
        for m_th in mfe_vals:
            spec = {'family': 'SIDE_AND_MFE', 'side_max': s_th, 'mfe_max': m_th}
            m, _ = eval_spec(D, spec)
            if dev_pass(m):
                families['SIDE_AND_MFE'].append({'sec': sec, **spec, 'D': m})

    for th in sorted(set(score_map[x['pid']] for x in D), reverse=True):
        spec = {'family': 'LOGIT3', 'score_min': th}
        m, _ = eval_spec(D, spec, score_map)
        if dev_pass(m):
            families['LOGIT3'].append({'sec': sec, **spec, 'D': m})

    for fam, cands in families.items():
        cands.sort(key=candidate_rank, reverse=True)
        carried.append(cands[0])

# Validation screening only for one Development winner per timestamp/family.
screened = []
for c in carried:
    sec = c['sec']
    V = [x for x in records[sec] if x['split'] == 'V']
    smap = scores_by_sec[sec] if c['family'] == 'LOGIT3' else None
    vm, _ = eval_spec(V, c, smap)
    cc = dict(c)
    cc['V'] = vm
    cc['validation_pass'] = val_pass(vm)
    screened.append(cc)

survivors = [x for x in screened if x['validation_pass']]

family_order = {'SIDE': 0, 'MFE': 1, 'SIDE_AND_MFE': 2, 'LOGIT3': 3}
def final_rank(c):
    return (
        c['V']['target_n'],
        c['V']['target_precision'],
        c['D']['target_n'],
        -c['sec'],
        -family_order[c['family']],
    )

survivors.sort(key=final_rank, reverse=True)
final = survivors[0] if survivors else None

summary = {
    'stage': 'LP-5D',
    'status_pre_reserve': 'CANDIDATE_FROZEN' if final else 'FAIL_NO_VALIDATION_SURVIVOR',
    'contract': {
        'times_sec': list(TIMES),
        'development_gates': {'target_precision_min': 0.80, 'winner_fire_rate_max': 0.05, 'target_recall_alive_min': 0.10, 'fire_n_min': 5},
        'validation_gates': {'target_precision_min': 0.70, 'winner_fire_rate_max': 0.05, 'target_recall_alive_min': 0.10, 'fire_n_min': 3},
        'reserve_gate': {'target_precision_min': 0.70, 'winner_fire_rate_max': 0.05, 'target_recall_alive_min': 0.10, 'reserve_pnl_delta_positive': True, 'winner_to_nonpositive_max': 1},
    },
    'carried_from_development': carried,
    'validation_screen': screened,
    'validation_survivor_n': len(survivors),
    'frozen_candidate_pre_reserve': final,
}

# SEALED RESERVE: only opened for the one frozen D+V candidate.
selected_all = []
if final:
    sec = final['sec']
    R = [x for x in records[sec] if x['split'] == 'R']
    smap = scores_by_sec[sec] if final['family'] == 'LOGIT3' else None
    rm, rfired = eval_spec(R, final, smap)
    summary['reserve_classification'] = rm
    summary['reserve_classification_gate_pass'] = (
        rm['target_precision'] >= 0.70
        and rm['winner_fire_rate'] <= 0.05
        and rm['target_recall_alive'] >= 0.10
    )
    for sp in ('D','V','R'):
        g = [x for x in records[sec] if x['split'] == sp]
        m, fired = eval_spec(g, final, smap)
        for x in fired:
            selected_all.append(x)
        summary[f'{sp}_final_classification'] = m

RESULTS/'LP5D_DISCOVERY_SUMMARY.json'.write_text(json.dumps(summary, indent=2), encoding='utf-8')

# Candidate table.
with open(RESULTS/'LP5D_CANDIDATE_SCREEN.csv','w',newline='',encoding='utf-8') as f:
    fields=['sec','family','side_max','mfe_max','score_min','D_fire','D_target','D_winner','D_otherloss','D_precision','D_recall','D_winner_rate','V_fire','V_target','V_winner','V_otherloss','V_precision','V_recall','V_winner_rate','validation_pass']
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for c in screened:
        w.writerow({
            'sec':c['sec'],'family':c['family'],'side_max':c.get('side_max'),'mfe_max':c.get('mfe_max'),'score_min':c.get('score_min'),
            'D_fire':c['D']['fire_n'],'D_target':c['D']['target_n'],'D_winner':c['D']['winner_n'],'D_otherloss':c['D']['other_loss_n'],'D_precision':c['D']['target_precision'],'D_recall':c['D']['target_recall_alive'],'D_winner_rate':c['D']['winner_fire_rate'],
            'V_fire':c['V']['fire_n'],'V_target':c['V']['target_n'],'V_winner':c['V']['winner_n'],'V_otherloss':c['V']['other_loss_n'],'V_precision':c['V']['target_precision'],'V_recall':c['V']['target_recall_alive'],'V_winner_rate':c['V']['winner_fire_rate'],'validation_pass':c['validation_pass']
        })

if final:
    with open(RESULTS/'LP5D_FINAL_FIRES.csv','w',newline='',encoding='utf-8') as f:
        fields=['pid','symbol','split','sec','side','mfe','mae','pnl','hist_mfe','label','target_pre05','winner','wrong_direction','open','close','entry']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:x.get(k) for k in fields} for x in selected_all])

print('=== LP5D PRE-REPLAY ===')
print(json.dumps(summary, indent=2))