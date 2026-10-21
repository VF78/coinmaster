"""Explicit operational CPU allocation; frozen runtime CLI and science unchanged."""
import argparse,hashlib,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--resource-budget',type=Path,required=True);p.add_argument('--resource-budget-sha256',required=True);p.add_argument('--verify-only',action='store_true');a,rest=p.parse_known_args()
raw=a.resource_budget.read_bytes();envelope=json.loads(raw)
if hashlib.sha256(raw).hexdigest()!=a.resource_budget_sha256:raise ValueError('RESOURCE_AUTHORIZATION_HASH_MISMATCH')
if envelope['family']!='cnn' or envelope['protocol_budget_cpu_minutes']!=120 or envelope['effective_budget_cpu_minutes']!=240:raise ValueError('RESOURCE_ENVELOPE_SCOPE')
if not a.verify_only:
 if not rest or rest[0] not in envelope['stages'] or '--family' not in rest or rest[rest.index('--family')+1]!='cnn':raise ValueError('RESOURCE_ENVELOPE_CNN_ONLY')
 from coinmaster.research import forecast_independent_run as runner
 if envelope['protocol_sha256']!=runner.PROTOCOL_SHA:raise ValueError('RESOURCE_PROTOCOL_MISMATCH')
 original=runner.Budget
 class AllocationBudget(original):
  def __init__(self,minutes):super().__init__(minutes+envelope['effective_budget_cpu_minutes']-envelope['protocol_budget_cpu_minutes'])
 runner.Budget=AllocationBudget
 sys.argv=[str(Path(__file__)),*rest];runner.main()
else:print(json.dumps({'status':'RESOURCE_ENVELOPE_VALID','effective_cpu_minutes':240,'scientific_module_changed':False}))
