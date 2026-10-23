"""First economic native-fill/event divergence from saved compact JSON; no traces."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
P=Path(__file__).resolve().parent
oldreceipt=json.loads((P.parent/'b-50-90-next-20261023/owner-XS-receipt.json').read_text());old=json.loads(Path(oldreceipt['artifact']).read_text())
def stamp(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
def first_diff(oldrows,newrows,projection):
 for i in range(max(len(oldrows),len(newrows))):
  o=oldrows[i] if i<len(oldrows) else None;n=newrows[i] if i<len(newrows) else None
  if o is None or n is None or projection(o)!=projection(n):return dict(sequence_index=i,old=o,new=n)
 return None
fillkeys=('fill_ns','submit_ns','accept_ns','action','instrument','reason','level','order_type','post_only','native_liquidity_side','qty','px','notional','commission','commission_currency','policy_hash','venue')
for recipe in sys.argv[1:]:
 r=json.loads((P/f'owner-{recipe}-receipt.json').read_text());d=json.loads(Path(r['artifact']).read_text())
 fd=first_diff(old['fill_audit'],d['fill_audit'],lambda row:{k:row.get(k) for k in fillkeys})
 ot=[e for e in old['next_band_audit'] if e['event']=='S_TRIGGER'];nt=[e for e in d['next_band_audit'] if e['event']=='S_TRIGGER']
 td=first_diff(ot,nt,lambda row:{k:v for k,v in row.items() if k not in ('residual_btc_flat','cadence')})
 if fd:
  times=[int(x['fill_ns']) for x in [fd['old'],fd['new']] if x];fd['first_changed_fill_utc']=stamp(min(times))
  firsttime=min(times);prior=[t for t in nt if int(t['timestamp_ns'])<=firsttime];fd['latest_causal_S_trigger_at_or_before']=prior[-1] if prior else None
 out=dict(recipe=recipe,comparison='ARCHIVED_XS',first_economic_native_fill_divergence=fd,first_economic_S_trigger_divergence=td,all_new_S_triggers=nt,XS_first_S_trigger_utc=stamp(ot[0]['timestamp_ns']) if ot else None,new_first_S_trigger_utc=stamp(nt[0]['timestamp_ns']) if nt else None,qualification='First divergence in complete saved native fill sequence and causal S_TRIGGER sequence. Fill projection includes all economic time/quantity/price/fee/liquidity/action/reason fields. Trigger comparison ignores only added residual_btc_flat/cadence metadata. Not a first-minute marked-trace divergence claim; old full trace not reread.',no_trace_read=True,no_engine=True)
 (P/f'verifier-{recipe}-divergence.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(dict(recipe=recipe,first_changed_fill_utc=fd['first_changed_fill_utc'] if fd else None,old=fd['old'] if fd else None,new=fd['new'] if fd else None,trigger=fd['latest_causal_S_trigger_at_or_before'] if fd else None)))
