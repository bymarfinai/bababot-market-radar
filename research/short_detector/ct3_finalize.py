import json,csv
x=json.load(open('/tmp/ct3_summary.json'))
rows=[]
for th,z in x['thresholds'].items():
    for b,v in z['blocks'].items():
        baseNT=v['baseline_selected']-v['baseline_strong'];curNT=v['selected']-v['strong']
        rows.append({
          'threshold':th,'block':b,
          'baseline_selected':v['baseline_selected'],'selected':v['selected'],
          'baseline_strong':v['baseline_strong'],'strong':v['strong'],
          'strong_retention':v['strong_retention'],
          'baseline_precision':v['baseline_precision'],'precision':v['precision'],'precision_delta':v['precision_delta'],
          'non_target_removed':baseNT-curNT,
          'removed_n':v['removed']['n'],'removed_strong':v['removed']['strong'],'removed_exec_pnl':v['removed']['exec_pnl'],
          'severe_removed':v['removed']['severe_n'],'severe_capture':v['severe_capture_removed'],
          'shifted_n':v['shifted']['n'],'shifted_strong':v['shifted']['strong'],'shifted_baseline_exec_pnl':v['shifted']['exec_pnl']
        })
with open('/tmp/ct3_block_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
x['decision'].update({
 'primary_status':'PASS_WITH_FRESH_OCT3_WARNING',
 'primary_strengths':[
   'Removed executable cohort is non-positive in all 6/6 blocks.',
   'Strong retention stays >=94.44% in every block.',
   'Precision improves in 5/6 blocks.',
   'Shifted cohort baseline PnL is non-positive in 5/6 blocks.'
 ],
 'primary_warning':'Fresh Oct 3 precision declines by 0.184 percentage points and 2 strong winners are lost; exact execution replay must confirm whether later-entry shifts offset this.',
 'aggressive_status':'FAIL_STABILITY_GATE',
 'aggressive_failure':'0.10% minimum block strong retention falls to 83.33% (Research Reserve) and 86.11% in Fresh Oct 3; lost winner value rises sharply.'
})
json.dump(x,open('/tmp/ct3_summary.json','w'),indent=2)
print('wrote',len(rows),'block rows')