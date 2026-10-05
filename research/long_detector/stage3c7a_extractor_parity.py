"""Verify PT-L1 heavy T0 feature math against frozen historical caches."""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
from market_radar.long_detector_stage3c7a import (
    _derive_market_relative,_derive_micro_volume_ratio,_derive_slope5,
    _derive_oi_change_30m,
)

def read_csv(p):
    with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def read_jsonl(p):
    out={}
    with open(p) as f:
        for line in f:
            if line.strip():
                x=json.loads(line);out[str(x['position_id'])]=x.get('rows') or []
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',required=True);a=ap.parse_args()
    data=Path(a.data_dir)
    F={r['meta_position_id']:r for r in read_csv(data/'wd5h1_thesis_labeled_features.csv')}
    T=[r for r in read_csv(data/'wd5h4a_temporal_features.csv') if r['side']=='LONG' and r['primary_meta_label'] in {'META_WIN','META_LOSS'}]
    coin=read_jsonl(data/'wd5h1_preentry_1m_cache.jsonl')
    oi=read_jsonl(data/'wd5h1_oi_5m_cache.jsonl')
    bench=json.load(open(data/'wd5h1_benchmark_1m_cache.json'))['symbols']
    keys=['f_micro_volume_ratio_last_vs_prev10','f_f_selected_slope5_norm','f_f_coin_minus_market_15m','f_f_coin_minus_market_30m','f_f_oi_change_30m_pct']
    stats={k:{'n':0,'max_abs':0.0,'bad':0} for k in keys}
    missing=[]
    for r in T:
        pid=r['position_id'];gate=int(r['gate_checked_at_ms'])
        if pid not in coin or pid not in oi or pid not in F:
            missing.append(pid);continue
        c=coin[pid]
        m15,m30=_derive_market_relative(c,bench,gate)
        got={
          'f_micro_volume_ratio_last_vs_prev10':_derive_micro_volume_ratio(c),
          'f_f_selected_slope5_norm':_derive_slope5(c),
          'f_f_coin_minus_market_15m':m15,
          'f_f_coin_minus_market_30m':m30,
          'f_f_oi_change_30m_pct':_derive_oi_change_30m(oi[pid],gate),
        }
        for k,v in got.items():
            exp=float(F[pid][k]);err=abs(v-exp);s=stats[k];s['n']+=1;s['max_abs']=max(s['max_abs'],err)
            if err>1e-9:s['bad']+=1
    print('rows',len(T),'missing',len(missing))
    for k,v in stats.items():print(k,v)
    assert not missing
    assert all(v['bad']==0 for v in stats.values())
    print('PTL1_EXTRACTOR_PARITY=PASS')
if __name__=='__main__':main()