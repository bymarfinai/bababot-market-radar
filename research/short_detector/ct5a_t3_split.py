import csv,json
CT4=[r for r in csv.DictReader(open('/tmp/ct4_trade_detail.csv')) if r['candidate']=='T0075']
SHIFT=list(csv.DictReader(open('/tmp/ct5a_shift_detail.csv')))
shift_to_t3={(r['source'],r['position_id']):r['transition'] for r in SHIFT if r['transition'] in ('T1_TO_T3','T2_TO_T3')}
# source classification comes from ct5a quality reconstruction stored only in json summary? rebuild using quality output not enough.
# map affected ALT from shift detail; for T3 current source groups use ct5a_quality JSON totals and direct shift membership.
def truth(v):return str(v).lower()=='true'
def met(q):
 ex=[r for r in q if truth(r['executable'])]; vals=[float(r['pnl']) for r in ex]
 return {'n':len(q),'exec':len(ex),'strong':sum(truth(r['strong']) for r in q),'exec_strong':sum(truth(r['strong']) for r in ex),
         'pnl':sum(vals),'wins':sum(v>0 for v in vals),'wr':sum(v>0 for v in vals)/len(vals) if vals else 0,
         'strong_pnl':sum(float(r['pnl']) for r in ex if truth(r['strong'])),
         'non_target_pnl':sum(float(r['pnl']) for r in ex if not truth(r['strong']))}

t3=[r for r in CT4 if int(r['lane'])==3]
shift3=[r for r in t3 if (r['source'],r['position_id']) in shift_to_t3]
native3=[r for r in t3 if (r['source'],r['position_id']) not in shift_to_t3]
out={'all_t3':met(t3),'shifted_to_t3':met(shift3),'not_shifted_to_t3':met(native3),'transition':{}}
for tr in ['T1_TO_T3','T2_TO_T3']:
 q=[r for r in t3 if shift_to_t3.get((r['source'],r['position_id']))==tr]
 out['transition'][tr]={'overall':met(q),'research':met([r for r in q if r['source']=='research']),'fresh':met([r for r in q if r['source']=='fresh'])}
out['shifted_blocks']={}
for b in sorted(set(r['block'] for r in shift3)):
 out['shifted_blocks'][b]=met([r for r in shift3 if r['block']==b])
json.dump(out,open('/tmp/ct5a_t3_shift_split.json','w'),indent=2)
print(json.dumps(out,indent=2))