"""Actual bounded native fixture diagnostic, never historical portfolio recovery."""
import json
from decimal import Decimal
from pathlib import Path
from test_native_residual_recovery import held,cut,observe,run_ticks,tick,BTC_PERP,H4,D,next_closed_bar
from coinmaster.research.native_audit import audit_json_default
s,e,ep=held()
try:
 cut(s,e)
 observe(s,2*H4,btc='80');s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(80),D(80),D(80),D(80),2*H4).data)
 for n in range(1,6):
  observe(s,2*H4+n,btc='80');run_ticks(e,[tick(BTC_PERP,2*H4+n,'80')])
 payload=dict(c1_audit=s.c1_audit,c1_denial_counts=s.c1_denials,c1_terminal_state=s._c1_export_terminal())
 bad=[]
 def visit(x,path='$'):
  if isinstance(x,Decimal):bad.append(dict(path=path,type=type(x).__name__,exact_repr=repr(x)))
  elif isinstance(x,dict):
   for k,v in x.items():visit(v,path+'.'+str(k))
  elif isinstance(x,(list,tuple)):
   for i,v in enumerate(x):visit(v,path+'['+str(i)+']')
 visit(payload)
 error=None
 try:json.dumps(payload,indent=2,sort_keys=True,default=audit_json_default)
 except TypeError as exc:error=str(exc)
 print(json.dumps(dict(provenance='BOUNDED_REAL_NATIVE_C1_FIXTURE_NOT_HISTORICAL_ATTEMPT_PAYLOAD',source='78100d4',native_events=len(s.fill_audit),c1_events=len(s.c1_audit),unsupported_values=bad,error=error),indent=2))
 assert bad and error=='Object of type Decimal is not JSON serializable'
finally:e.end();e.dispose()
