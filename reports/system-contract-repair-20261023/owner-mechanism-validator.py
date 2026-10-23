"""Read completed artifacts only. No engine, order, source or ledger mutations."""
from decimal import Decimal as D
from pathlib import Path
from collections import Counter
import argparse,hashlib,json
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
J=ROOT/'runtime/var/research-jobs/system-contract-repair-20261023'
R=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def quantile(values):
    a=sorted(values);p=D(len(a)-1)*D('.9');lo=int(p)
    return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(p-lo)

def validate(recipe):
    prep=json.loads((J/recipe/'preparation.json').read_text())
    artifacts=[p for p in Path(prep['artifact_dir']).glob('v0*.json') if not p.name.endswith('-raw-native.json')]
    if len(artifacts)!=1:raise RuntimeError('WAIT_COMPLETE_SINGULAR_ARTIFACT')
    path=artifacts[0];x=json.loads(path.read_text());checks=0;failures=[]
    def check(ok,name,detail=None):
        nonlocal checks
        checks+=1
        if not ok:failures.append(dict(check=name,detail=detail))
    check(x['config_hash']==prep['expected_config_sha256'],'CONFIG_EXACT')
    attempts=[a for a in x.get('system_contract_audit',[]) if a.get('event')=='SOL_ATTEMPT']
    counts=Counter((a['episode_id'],a['level'],a['decision_index']) for a in attempts)
    check(all(n==1 for n in counts.values()),'ONE_ORIGINAL_ATTEMPT_PER_LEVEL_D1')
    for a in attempts:
        check(a['next_attempt_earliest_decision_index']==a['decision_index']+1,'NEXT_ORIGINAL_D1_INDEX',a['intent_id'])
        check(D(a['submitted_quantity'])<=D(a['allowed_quantity'])<=1000,'CHILD_AND_ADMISSION_BOUND',a['intent_id'])
        check(D(a['filled_quantity'])<=D(a['submitted_quantity']),'ACTUAL_FILL_WITHIN_SUBMISSION',a['intent_id'])
        check(D(a['unused_right_notional'])==max(D(0),D(a['original_remaining_notional'])-D(a['filled_notional'])),'ACTUAL_COST_ONLY_RIGHT_DEBIT',a['intent_id'])
    summary=dict(sol_attempts=len(attempts),distinct_level_D1_attempts=len(counts));mechanism_examples=[]
    if recipe in ('H_SOL','COMBINED'):
        rows=x.get('sc_sol_budget_audit',[]);known=[a for a in rows if a.get('reason')=='MAX_LOT_FEASIBLE_ADD'];unknown=[a for a in rows if a not in known]
        bound={a['intent_id']:a for a in attempts}
        curtailed=D(0);requested_violations=existing_over=0
        for a in known:
            fee=D(a['sol_fee']);stress=D(a['sol_atr'])+fee*(D(a['sol_mark'])+D(a['sol_atr']))
            coefficient=stress+fee*D(a['executable'])
            available=D(a['equity'])-D('.55')*D(a['high_water'])-D(a['btc_reserve'])-D(a['pending_entry_fees'])-(D(a['held_sol'])+D(a['pending_sol']))*stress
            requested=D(a['requested_quantity']);allowed=D(a['allowed_quantity'])
            expected=(min(requested,max(D(0),available)/coefficient)//D('.1'))*D('.1')
            curtailed+=requested-allowed;requested_violations+=available-requested*coefficient<0;existing_over+=available<0
            if allowed<requested and len(mechanism_examples)<3:
                floor=D('.55')*D(a['high_water'])
                mechanism_examples.append(dict(timestamp_ns=a['timestamp_ns'],intent_id=a['intent_id'],requested=str(requested),allowed=str(allowed),existing_stressed_equity=str(floor+available),warning_floor=str(floor),full_requested_stressed_equity=str(floor+available-requested*coefficient),allowed_stressed_equity=str(floor+available-allowed*coefficient)))
            check(allowed==expected,'H_SOL_MAXIMAL_NATIVE_LOT',a['intent_id'])
            check(allowed==0 or available-allowed*coefficient>=0,'H_SOL_POST_STRESS_FLOOR',a['intent_id'])
            if allowed<requested and allowed>0:check(available-(allowed+D('.1'))*coefficient<0,'H_SOL_NEXT_LOT_INFEASIBLE',a['intent_id'])
            check(a['intent_id'] in bound and D(bound[a['intent_id']]['allowed_quantity'])==allowed,'H_SOL_OBSERVED_ATTEMPT_BINDING',a['intent_id'])
        for a in unknown:check(D(a['allowed_quantity'])==0,'H_SOL_UNKNOWN_FAILS_CLOSED',a.get('reason'))
        check(bool(rows),'H_SOL_AUDIT_PRESENT')
        summary.update(h_sol_decisions=len(rows),known_budget_states=len(known),fail_closed_states=len(unknown),
            partial_clips=sum(0<D(a['allowed_quantity'])<D(a['requested_quantity']) for a in known),
            full_denials=sum(D(a['allowed_quantity'])==0 for a in rows),
            pending_sol_states=sum(D(a['pending_sol'])>0 for a in known),pending_btc_states=sum(D(a['pending_btc'])>0 for a in known),
            fail_closed_reasons=dict(Counter(a['reason'] for a in unknown)),curtailed_candidate_sol_quantity_sum=str(curtailed),original_child_exceeds_frozen_budget=requested_violations,existing_inventory_already_below_warning_floor=existing_over)
    if recipe in ('H_BTC','COMBINED'):
        rows=x.get('sc_btc_decisions',[]);labels=x.get('sc_btc_labels',[]);outcomes=x.get('sc_btc_outcomes',[])
        parents=[a['parent_id'] for a in labels];check(len(parents)==len(set(parents)),'ONE_LABEL_PER_ACTUAL_PARENT')
        valid=[a for a in labels if a['status']=='VALID']
        for a in valid:
            check(D(a['u'])==D(a['minute_mae'])/D(a['frozen_atr_fraction']),'H_BTC_LABEL_UNITS',a['parent_id'])
            check(a['label_ready_at']>a['first_fill_ns'] and a['mark_count']>0,'H_BTC_CLOSED_LABEL_AFTER_FIRST_FILL',a['parent_id'])
        for a in rows:
            eligible=[l for l in valid if l['label_ready_at']<a['decision_ns']]
            groups=[[D(l['u']) for l in eligible if l['repeated']==group] for group in (False,True)]
            qs=[quantile(g) if g else None for g in groups]
            check([len(g) for g in groups]==[a['n_first'],a['n_repeat']],'H_BTC_STRICT_PAST_SAMPLE_COUNTS',a['parent_id'])
            check([len({l['wave_id'] for l in eligible if l['repeated']==group}) for group in (False,True)]==[a['waves_first'],a['waves_repeat']],'H_BTC_INDEPENDENT_WAVE_COUNTS',a['parent_id'])
            expected=min(D(1),qs[0]/qs[1]) if a['repeated'] and min(map(len,groups))>=8 and qs[1] else D(1)
            check(D(a['k'])==expected,'H_BTC_Q90_CAUSAL_FACTOR',a['parent_id'])
            check(D(a['after_k_notional'])==D(a['before_k_notional'])*expected,'H_BTC_K_ONCE_POST_CAP',a['parent_id'])
            if 'actual_repeated' in a:check(a['repeated']==a['actual_repeated'],'H_BTC_DECISION_ACTUAL_FIRST_REPEAT_MATCH',a['parent_id'])
            if 'first_fill_ns' in a:
                fills=[f for f in outcomes if f['parent_intent_id']==a['parent_id'] and f['action']=='BTC_ENTRY']
                check(bool(fills),'H_BTC_ACTUAL_FIRST_FILL_RECEIPT_PRESENT',a['parent_id'])
                if fills:
                    first=min(fills,key=lambda f:f['timestamp_ns'])
                    check(first['timestamp_ns']==a['first_fill_ns'] and D(first['native_price'])==D(a['label_reference_price']),'H_BTC_FIRST_ACTUAL_FILL_ANCHOR',a['parent_id'])
        check(bool(rows),'H_BTC_AUDIT_PRESENT')
        summary.update(h_btc_decisions=len(rows),repeated_decisions=sum(a['repeated'] for a in rows),
            eligible_8_each=sum(a['repeated'] and min(a['n_first'],a['n_repeat'])>=8 for a in rows),
            reduced_decisions=sum(D(a['k'])<1 for a in rows),minimum_k=str(min((D(a['k']) for a in rows),default=D(1))),
            label_status=dict(Counter(l['status'] for l in labels)),fallback_reasons=dict(Counter(a['fallback'] for a in rows)),
            first_8_each_eligible_decision_ns=min((a['decision_ns'] for a in rows if a['repeated'] and min(a['n_first'],a['n_repeat'])>=8),default=None),
            first_k_below1_decision_ns=min((a['decision_ns'] for a in rows if D(a['k'])<1),default=None))
    result=dict(recipe=recipe,status='PASS' if not failures else 'FAIL',checks=checks,failures=failures,
        source_commit=prep['source_commit'],source_manifest_sha256=prep['source_manifest_sha256'],artifact=str(path),artifact_sha256=sha(path),summary=summary,
        scope='Saved audit/native bindings and frozen mechanism arithmetic; source clock/causal proofs from42tests. Independent money/global DD/liquidation/account reconciliation and mark-label ground truth belong to data verifier.',
        no_engine_or_source_mutations=True,local_mechanism_examples=mechanism_examples)
    output=R/f'owner-{recipe}-mechanism.json';output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if not failures else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('recipe',choices=['H_SOL','H_BTC','COMBINED']);args=parser.parse_args();raise SystemExit(validate(args.recipe))
