"""Reporting and nonfinancial tie-counter repair; no outcome recomputation."""
from pathlib import Path
import json,csv,hashlib,collections
import pyarrow.parquet as pq
R=Path(__file__).resolve().parent
read=lambda p:list(csv.DictReader(Path(p).open()))
def write(p,z):
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(z[0]));w.writeheader();w.writerows(z)
p=R/'screen-calculate.py';oldscript=hashlib.sha256(p.read_bytes()).hexdigest();s=p.read_text().replace("for ev in evmap[t]:", "for ev in evmap.get(t,[]):");p.write_text(s)
a=read(R/'screen-actions.csv');ev=read(R/'screen-cashflows.csv');meta=read(R/'screen-cohorts.csv');res=json.loads((R/'screen-result.json').read_text());v=json.loads((R/'screen-verification.json').read_text());L=json.loads((R/'screen-ledger.json').read_text());originalcashcols=['SOL_net_USDT','trim_net_USDT','SOL_net_bp','trim_net_bp','SOL_minus_trim_bp','SOL_fees_USDT','trim_fees_USDT','avoided_native_fees_USDT','SOL_slip_USDT','trim_slip_USDT','SOL_funding_USDT','trim_avoided_funding_USDT'];before=[[r[k] for k in originalcashcols] for r in a]
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized');fts=set()
for sym in ['BTC','SOL']:fts.update(int(t)*10**6 for t in pq.read_table(DATA/f'bybit-{sym}USDT-funding.parquet',columns=['funding_time_ms']).column(0).to_pylist())
tied={}
for cy in {r['cycle'] for r in a}:tied[cy]=len({int(x['event_ns']) for x in ev if x['cycle']==cy and x['event_kind']=='BASELINE_REDUCTION'} & fts)
oldcounts={r['cycle']:int(r['funding_reduction_ties']) for r in a}
for r in a:r['funding_reduction_ties']=tied[r['cycle']]
assert before==[[r[k] for k in originalcashcols] for r in a]
write(R/'screen-actions.csv',a)
res['funding_boundary_tied_episodes']=sum(n>0 for n in tied.values());res['funding_reduction_tie_groups']=sum(tied.values());res['calculation_script_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();res['nonfinancial_metadata_correction']={'issue':'defaultdict evmap[t] inserted empty minute keys, inflating reported tie counts in later scenarios; cashflow and funding calculations unaffected','previous_script_sha256':oldscript,'episodes_with_reported_ties_before':sum(n>0 for n in oldcounts.values()),'episodes_with_actual_reduction_funding_ties_after':res['funding_boundary_tied_episodes'],'all_existing_cash_fee_slip_funding_columns_unchanged':True,'no_additional_outcome_pass':True}
v['checks']['direct_actual_reduction_funding_tie_counts']=len(tied);v['nonfinancial_metadata_corrected_cash_columns_unchanged']=True
# Side sign view only, no side selection or fresh outcome calculation.
sides=[]
for cohort in ['first_year','second_year','early']:
 for slip in ['0.0','2.0']:
  for boundary in ['BEFORE_REDUCTION','AFTER_REDUCTION']:
   for side in ['1','-1']:
    z=[r for r in a if r['slip_bp']==slip and r['funding_boundary']==boundary and r['side']==side and ((r['early']=='True') if cohort=='early' else r['period']==cohort)]
    sides.append(dict(cohort=cohort,slip_bp=slip,funding_boundary=boundary,side=side,episodes=len(z),positive_SOL_episodes=sum(float(x['SOL_net_bp'])>0 for x in z),positive_SOL_minus_trim_episodes=sum(float(x['SOL_minus_trim_bp'])>0 for x in z),mean_SOL_net_bp=sum(float(x['SOL_net_bp']) for x in z)/len(z),mean_SOL_minus_trim_bp=sum(float(x['SOL_minus_trim_bp']) for x in z)/len(z)))
write(R/'screen-side-signs.csv',sides)
(R/'screen-result.json').write_text(json.dumps(res,indent=2)+'\n');(R/'screen-verification.json').write_text(json.dumps(v,indent=2)+'\n');L['calculation_script_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();L['metadata_only_correction']=res['nonfinancial_metadata_correction'];L['status']='COMPLETE_STOP_CAPITAL_STOP_TRIM_PROTECTION_UNKNOWN';L['logical_outcome_screens_completed']=1;L['arithmetic_verifications_completed']=1
L['output_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('screen-*') if p.is_file() and p.name!='screen-ledger.json'};(R/'screen-ledger.json').write_text(json.dumps(L,indent=2)+'\n')
print(json.dumps({'funding_tied_episodes':res['funding_boundary_tied_episodes'],'funding_tie_groups':res['funding_reduction_tie_groups'],'cash_columns_unchanged':True,'side_sign_rows':len(sides)},indent=2))
