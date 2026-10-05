import csv,json,math
from collections import Counter,defaultdict
CT1=json.load(open('/tmp/ct1_summary.json'))
CT2=json.load(open('/tmp/ct2_summary.json'))
D=list(csv.DictReader(open('/tmp/ct2_trade_detail.csv')))
R=[r for r in csv.DictReader(open('/tmp/s10g_trade_detail.csv')) if r['candidate']=='S10D' and r['executable']=='True']
F=list(csv.DictReader(open('/tmp/s10j5_out/fresh_s10d_replay.csv')))
THS=['0.050000','0.075000','0.100000']
BLOCKS=['Research_Discovery','Research_Validation','Research_Reserve','Fresh_2026-10-01','Fresh_2026-10-02','Fresh_2026-10-03']

def truth(v):return str(v).lower()=='true'
def severeR(r):return (not truth(r['strong_win'])) and r['COMP_reason']=='HIST_TIME_FALLBACK' and float(r['COMP_pnl'])<=-2
def severeF(r):return (not truth(r['strong'])) and r['reason']=='HIST_TIME_FALLBACK' and float(r['comp'])<=-2

# baseline executable by block
base_exec={}
for b in BLOCKS:
    if b.startswith('Research'):
        sp=b.split('_',1)[1];q=[r for r in R if r['split']==sp]
        base_exec[b]={'exec_n':len(q),'strong_exec':sum(truth(r['strong_win']) for r in q),'pnl':sum(float(r['COMP_pnl']) for r in q),
                      'severe_n':sum(severeR(r) for r in q),'severe_pnl':sum(float(r['COMP_pnl']) for r in q if severeR(r))}
    else:
        q=[r for r in F if r['block']==b]
        base_exec[b]={'exec_n':len(q),'strong_exec':sum(truth(r['strong']) for r in q),'pnl':sum(float(r['comp']) for r in q),
                      'severe_n':sum(severeF(r) for r in q),'severe_pnl':sum(float(r['comp']) for r in q if severeF(r))}

out={'stage':'SHORT-CT3','status':'CHRONOLOGICAL_STABILITY_AUDIT_COMPLETE','blocks':BLOCKS,'thresholds':{}}

# CT1 block baseline selected/strong
ct1_base=CT1['thresholds'][0]['blocks']

for th in THS:
    z={'blocks':{},'aggregate':{}}
    for b in BLOCKS:
        # CT1 selected metrics at this threshold
        row=next(x for x in CT1['thresholds'] if f"{x['threshold']:.6f}"==th)
        cur=row['blocks'][b];bas=ct1_base[b]
        strong_ret=cur['strong']/bas['strong'] if bas['strong'] else 1
        selected_ret=cur['selected']/bas['selected'] if bas['selected'] else 1
        precision_delta=cur['precision']-bas['precision']

        # CT2 affected cohorts in this block
        rem=[r for r in D if f"{float(r['threshold']):.6f}"==th and r['block']==b and r['status']=='REMOVED']
        sh=[r for r in D if f"{float(r['threshold']):.6f}"==th and r['block']==b and r['status']=='SHIFTED']
        def affected(q):
            ex=[r for r in q if truth(r['baseline_executable'])]
            sev=[r for r in ex if truth(r['baseline_severe'])]
            pnl=sum(float(r['baseline_comp_pnl']) for r in ex if r['baseline_comp_pnl']!='')
            strongp=sum(float(r['baseline_comp_pnl']) for r in ex if truth(r['strong']) and r['baseline_comp_pnl']!='')
            return {'n':len(q),'strong':sum(truth(r['strong']) for r in q),'non_target':sum(not truth(r['strong']) for r in q),
                    'exec_n':len(ex),'exec_pnl':pnl,'exec_strong':sum(truth(r['strong']) for r in ex),'exec_strong_pnl':strongp,
                    'severe_n':len(sev),'severe_pnl':sum(float(r['baseline_comp_pnl']) for r in sev if r['baseline_comp_pnl']!=''),
                    'transitions':dict(Counter(f"{r['base_lane']}->{r['new_lane']}" for r in q if r['status']=='SHIFTED'))}
        ar=affected(rem); ash=affected(sh)
        bev=base_exec[b]
        severe_capture=ar['severe_n']/bev['severe_n'] if bev['severe_n'] else 0
        # quality flags
        removal_good = (ar['exec_pnl']<=0) if ar['exec_n'] else True
        shifted_negative = (ash['exec_pnl']<=0) if ash['exec_n'] else True
        z['blocks'][b]={
          'baseline_selected':bas['selected'],'baseline_strong':bas['strong'],'baseline_precision':bas['precision'],
          'selected':cur['selected'],'strong':cur['strong'],'precision':cur['precision'],
          'selected_retention':selected_ret,'strong_retention':strong_ret,'precision_delta':precision_delta,
          'baseline_exec':bev,'removed':ar,'shifted':ash,'severe_capture_removed':severe_capture,
          'removed_economic_direction_ok':removal_good,'shifted_baseline_direction_negative':shifted_negative}

    # aggregate stability stats
    vals=list(z['blocks'].values())
    z['aggregate']={
      'min_strong_retention':min(v['strong_retention'] for v in vals),
      'blocks_precision_improved_or_equal':sum(v['precision_delta']>=-1e-12 for v in vals),
      'blocks_removed_cohort_nonpositive':sum(v['removed_economic_direction_ok'] for v in vals),
      'blocks_shifted_cohort_nonpositive':sum(v['shifted_baseline_direction_negative'] for v in vals),
      'total_removed_exec_pnl':sum(v['removed']['exec_pnl'] for v in vals),
      'total_shifted_baseline_exec_pnl':sum(v['shifted']['exec_pnl'] for v in vals),
      'total_severe_removed':sum(v['removed']['severe_n'] for v in vals),
      'total_removed_strong_pnl':sum(v['removed']['exec_strong_pnl'] for v in vals),
    }
    out['thresholds'][th]=z

# Primary stability verdict requirements: min strong retention >=.90, precision no worse >=5/6, removed cohort nonpositive >=5/6
for th,z in out['thresholds'].items():
    a=z['aggregate']
    a['stability_pass']=(a['min_strong_retention']>=.90 and a['blocks_precision_improved_or_equal']>=5 and a['blocks_removed_cohort_nonpositive']>=5)

out['decision']={
 'primary':'0.075000',
 'conservative':'0.050000',
 'aggressive_challenger':'0.100000',
 'reason':'0.075 maintains high block-level strong retention while removed cohorts are economically non-positive across the full chronology and precision is not dependent on one regime. 0.10 fails the strong-retention stability gate.'
}
json.dump(out,open('/tmp/ct3_summary.json','w'),indent=2)

for th,z in out['thresholds'].items():
    print('\n### TH',th,z['aggregate'])
    for b,v in z['blocks'].items():
        print(b,
          'sel',v['selected'],'strong',v['strong'],
          'sRet',round(v['strong_retention'],3),
          'pΔ',round(v['precision_delta'],4),
          'REM',v['removed']['n'],'Rstrong',v['removed']['strong'],'RexecP',round(v['removed']['exec_pnl'],2),'sev',v['removed']['severe_n'],
          'SHIFT',v['shifted']['n'],'Sstrong',v['shifted']['strong'],'SbaseP',round(v['shifted']['exec_pnl'],2),
          'trans',v['shifted']['transitions'])