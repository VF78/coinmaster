"""Source induction + saved native prefix proof; never runs a combined engine."""
from decimal import Decimal as D
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');J=ROOT/'runtime/var/research-jobs/system-contract-repair-20261023';R=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ns(s):return int(datetime.fromisoformat(s).timestamp()*1_000_000_000)
def q90(a):
 a=sorted(a);p=D(len(a)-1)*D('.9');i=int(p);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(p-i)
def factor(labels,row):
 past=[x for x in labels if x['status']=='VALID' and x['label_ready_at']<row['decision_ns']]
 groups=[[D(x['u']) for x in past if x['repeated']==group] for group in (False,True)]
 qs=[q90(g) if g else None for g in groups]
 k=min(D(1),qs[0]/qs[1]) if row['repeated'] and min(map(len,groups))>=8 and qs[1] else D(1)
 return k,list(map(len,groups))

prep=json.loads((J/'H_SOL/preparation.json').read_text());done=json.loads((J/'H_SOL/completion.json').read_text());path=Path(done['artifact']);x=json.loads(path.read_text());attribution=R/'data-attribution-H_SOL.json';a=json.loads(attribution.read_text());w=a['global_peak_trough_recovery'];cut=ns(w['trough_utc']);labels=x['sc_btc_labels'];rows=x['sc_btc_decisions'];prefix=[r for r in rows if r['decision_ns']<=cut]
checks=[]
def check(ok,name):checks.append(dict(name=name,pass_=bool(ok)))
check(done['native_process_exit_code']==0 and done['config_exact'],'H_SOL_VALID_NATIVE_EXPORT_EXACT_CONFIG')
check(D(w['DD_percent'])>50,'IRREVERSIBLE_PRIOR_GLOBAL_DD_GT50')
verified=[]
for row in prefix:
 k,counts=factor(labels,row);check(k==D(row['k'])==1 and counts==[row['n_first'],row['n_repeat']],'PREFIX_STRICT_PAST_Q90_K1_'+str(row['decision_ns']))
 check(len(D(row['before_k_notional']).as_tuple().digits)<=28,'K1_EXACT_DECIMAL_VALUE_'+str(row['decision_ns']))
 verified.append({key:row[key] for key in ('decision_ns','parent_id','repeated','n_first','n_repeat','k','fallback','before_k_notional')})
reduced=[r for r in rows if factor(labels,r)[0]<1];eligible=[r for r in rows if r['repeated'] and min(factor(labels,r)[1])>=8]
first_reduction=min((r['decision_ns'] for r in reduced),default=None)
check(first_reduction is None or first_reduction>cut,'NO_H_BTC_INTERVENTION_BEFORE_H_SOL_FAILURE')
cs=json.loads((J/'COMBINED/expected-config.json').read_text());hs=json.loads((J/'H_SOL/expected-config.json').read_text());diff={key:[hs.get(key),cs.get(key)] for key in set(hs)|set(cs) if hs.get(key)!=cs.get(key)}
check(diff=={'research_btc_repeat_sizing':[False,True]},'COMBINED_ONLY_FUNCTIONAL_CONFIG_DELTA_IS_H_BTC')
source=Path(prep['source_snapshot']);manifest=J/'source-8f2f780-sha256.json';pins=json.loads(manifest.read_text());source_files=('runtime/coinmaster/strategy/system_contract.py','runtime/coinmaster/strategy/wave_overlay.py','runtime/coinmaster/strategy/next_band.py')
for relative in source_files:check(sha(source/relative)==pins[relative],'FROZEN_SOURCE_'+relative)
proof=dict(status='PASS' if all(c['pass_'] for c in checks) else 'FAIL',source_commit=prep['source_commit'],source_manifest_sha256=prep['source_manifest_sha256'],h_sol_artifact=str(path),h_sol_artifact_sha256=sha(path),attribution_sha256=sha(attribution),checks=checks,
 irreversible_native_global_DD=w,prefix_decisions=verified,
 first_h_sol_path_8_each_eligible_ns=min((r['decision_ns'] for r in eligible),default=None),first_h_sol_path_counterfactual_k_below1_ns=first_reduction,
 induction='Same frozen engine, inputs and H_SOL policy. Enabling H_BTC changes only the already-capped q0 target from before to before*k. Every actual H_SOL q0 before the witnessed January trough recomputes k=1 using strict-past completed labels. Thus each target, zero-TP branch input, lot, native order/fill/equity state and subsequent label remains the H_SOL prefix by induction. Metadata and random episode IDs do not create an economic intervention. The combined policy therefore retains at least the witnessed January global drawdown; later trades cannot erase a global historical maximum.',
 conclusion='COMBINED_NOT_RUN_PROVEN_DD50_FUTILITY' if all(c['pass_'] for c in checks) else 'UNPROVEN',scope='No synthetic PnL or claimed combined TOTAL; logical prefix bound from a valid native H_SOL path and exact frozen source. Root retains launch/status authority.')
other=J/'H_BTC/completion.json'
if other.exists():
 d=json.loads(other.read_text());p=Path(d['artifact']);b=json.loads(p.read_text());br=b['sc_btc_decisions'];before=[r for r in br if r['decision_ns']<=cut];bad=[r for r in before if factor(b['sc_btc_labels'],r)[0]!=1];proof['actual_h_btc_crosscheck']=dict(native_exit=d['native_process_exit_code'],artifact_sha256=sha(p),prefix_decisions=len(before),all_prefix_k1=not bad,first_actual_k_below1_ns=min((r['decision_ns'] for r in br if D(r['k'])<1),default=None))
else:proof['actual_h_btc_crosscheck']='PENDING_NORMAL_NATIVE_COMPLETION;H_SOL_PREFIX_PROOF_ALREADY_COMPLETE'
(R/'owner-combination-prefix-futility.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:proof[k] for k in ('status','conclusion','first_h_sol_path_8_each_eligible_ns','first_h_sol_path_counterfactual_k_below1_ns','actual_h_btc_crosscheck')},indent=2))
