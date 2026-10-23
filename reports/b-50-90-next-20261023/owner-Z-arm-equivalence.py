"""Bounded proof on frozen saved Z events and pinned execution quotes, no engine."""
import json,csv,hashlib,sys
from pathlib import Path
from decimal import Decimal as D
import numpy as np
import pyarrow.parquet as pq
R=Path(__file__).parent.resolve();J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs');recipe=sys.argv[1] if len(sys.argv)>1 else 'Z';folder=J/'b-50-90-next-20261023'/recipe/'result';a=json.load(next(x for x in folder.glob('v0*.json') if not x.name.endswith('-raw-native.json')).open());es=a['next_band_audit'];parents=a['split_cover_audit']['parents'];orders=json.load(next(folder.glob('*-raw-native.json')).open())['native_order_events'];fills=a['fill_audit'];orders=list(orders.values()) if isinstance(orders,dict) else orders;source=J/'sol-conditional-hedge-btc-band-20261023/inputs/data/normalized/bybit-BTCUSDT-execution-1m.parquet';data=pq.read_table(source,columns=['open_time_ms','close']).to_pydict();times=(np.array(data['open_time_ms'],dtype=np.int64)+60000)*1000000;prices=np.array([int(D(x)/D('.1')) for x in data['close']],dtype=np.int64);lookup={int(t):i for i,t in enumerate(times)};checks=[];overwrites=[]
for pidx,p in enumerate(parents):
 group=[(i,e) for i,e in enumerate(es) if e.get('episode_id')==p['episode_id'] and e['event']=='Z_ARM']
 if not group:continue
 side=int(p['side']);first_index,first=group[0];firstns=int(first['timestamp_ns']);end=int(parents[pidx+1]['start_ns']) if pidx+1<len(parents) else 1788220800000000000;triggers=[(i,e) for i,e in enumerate(es) if e.get('episode_id')==p['episode_id'] and e['event']=='Z_TRIGGER'];trigger=triggers[0] if triggers else None;G=D(first['G'])
 # Cancellations after actual trigger (sometimes same timestamp on SOL quote)
 # are target completion, not a reason to suppress that earlier BTC trigger.
 preempts=[(i,e) for i,e in enumerate(es) if first_index<i and firstns<=int(e['timestamp_ns'])<end and e['event']=='RISK_PREEMPT' and e.get('kind')=='Z' and (trigger is None or i<trigger[0])]
 ordinary=[int(f['fill_ns']) for f in fills if int(p['start_ns'])<=int(f['fill_ns'])<end and f['action']=='BTC_REDUCE' and f.get('reason')!='ZERO_RETRACE_RISK'];forced=[int(o['submit_ns']) for o in orders if int(p['start_ns'])<=int(o.get('submit_ns') or 0)<end and o.get('action') in ('FORCED_CLOSE','TERMINAL_CLOSE')]
 stop=min([int(e['timestamp_ns']) for _,e in preempts]+ordinary+forced+[end]);triggerns=int(trigger[1]['timestamp_ns']) if trigger else None
 bound=triggerns if trigger else stop-1
 mask=(times>firstns)&(times<=bound)&(side*(prices-int(G/D('.1')))<=0);indices=np.flatnonzero(mask);cross=int(times[indices[0]]) if len(indices) else None
 for n,(event_index,e) in enumerate(group):
  t=int(e['timestamp_ns']);q=lookup.get(t);value=D(data['close'][q]) if q is not None else None;favorable=value is not None and side*(value-D(e['G']))>=D('.1')
  overwrites.append(dict(episode_id=p['episode_id'],confirmation_number=n+1,timestamp_ns=t,signal_asof_ns=e['signal_asof_ns'],actual_same_timestamp_quote=str(value),G=e['G'],side=side,favorable_at_least_one_tick=favorable,G_unchanged=D(e['G'])==G,source_behavior='armed_ns_overwritten_existing_boolean_and_budget_retained' if n else 'first_arm'))
 checks.append(dict(episode_id=p['episode_id'],parent_index=pidx+1,first_arm_ns=firstns,last_favorable_confirmation_ns=group[-1][1]['timestamp_ns'],arm_log_rows=len(group),trigger_count=len(triggers),actual_trigger_ns=triggerns,eligibility_end_ns=stop,first_return_quote_after_FIRST_arm_ns=cross,first_cross_equivalent=(cross==triggerns if trigger else cross is None),all_qualifying_overwrite_quotes_favorable=all(x['favorable_at_least_one_tick'] and x['G_unchanged'] for x in overwrites if x['episode_id']==p['episode_id']),qualification='Untriggered windows stop on first policy preemption/ordinary native TP/mandatory close; source state and quote ordering retained'))
def save(name,rows):
 with (R/name).open('w',newline='') as f:w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
save('owner-'+recipe+'-arm-first-cross-equivalence.csv',checks);save('owner-'+recipe+'-arm-overwrite-quotes.csv',overwrites)
passall=all(x['first_cross_equivalent'] and x['all_qualifying_overwrite_quotes_favorable'] and x['trigger_count']<=1 for x in checks)
out=dict(status='PASS_BENCHMARK_SPECIFIC_EQUIVALENCE' if passall else 'FAIL_COUNTEREXAMPLE_HALT_AFFECTED_COMBINATIONS',armed_episodes=len(checks),triggered_episodes=sum(x['trigger_count'] for x in checks),untriggered_episodes=sum(not x['trigger_count'] for x in checks),qualifying_confirmation_rows=len(overwrites),actual_overwrites=sum(x['confirmation_number']>1 for x in overwrites),all_same_timestamp_quotes_favorable=all(x['favorable_at_least_one_tick'] for x in overwrites),checks=checks,limitations=['armed_ns is not immutable; scalar timestamp is refreshed on favorable confirmations','Proof is specific to actual pinned zero-spread1mCLOSE quotes, not live spread/latency','Z_ARM/Z_TRIGGER slots dictionaries share mutable task state and are terminal-state audit aliases; reconstruct initial slot budgets from recorded native entry targets, never treat logged eventual zeros as initial frozen targets'],no_extra_engine=True)
(R/('owner-'+recipe+'-arm-equivalence.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='checks'},indent=2))
