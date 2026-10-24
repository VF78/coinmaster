"""POST-RESULT scalar requirement diagnostic; never a trading parameter."""
import json,hashlib
from pathlib import Path
from decimal import Decimal as D,getcontext
getcontext().prec=80
P=Path(__file__).resolve().parent
inp=P/'growth-envelope-results.json'; protocol=P/'GROWTH_REQUIREMENTS_PROTOCOL.md'
saved=json.loads(inp.read_text()); rs=[D(x['return']) for x in saved['cycle_checks']]
assert len(rs)==83 and all(r>D(-1) for r in rs)
seed=D(10000);s0net=D('6067107.23887483');floors={'70':D('4256975.067212381'),'90':D('5470396.514987347')}
def value(alpha):
 a=seed
 for r in rs:a*=1+(alpha*r if r<0 else r)
 return a
zero=value(D(0));base=value(D(1));total=seed; endpoints={}
for i,r in enumerate(rs,1):
 total*=1+max(r,D(0))
 if i in (19,43,83):endpoints[str(i)]=str(total)
roots={}
for name,floor in floors.items():
 if zero<floor:roots[name]={'status':'NOT_REACHABLE_IN_THIS_MODEL'};continue
 lo=D(0);hi=D(1)
 assert value(lo)>=floor>=value(hi)
 iterations=0
 while hi-lo>D('1e-70'):
  mid=(lo+hi)/2;v=value(mid)
  if v>=floor:lo=mid
  else:hi=mid
  iterations+=1
 alpha=(lo+hi)/2
 roots[name]={'status':'REACHABLE_ORACLE_ATTENUATION_ONLY','alpha_negative_return_retained':str(alpha),'negative_return_removed_share':str(1-alpha),'alpha_bracket_lo':str(lo),'alpha_bracket_hi':str(hi),'value_lo':str(value(lo)),'value_hi':str(value(hi)),'mid_value':str(value(alpha)),'mid_money_residual':str(value(alpha)-floor),'iterations':iterations}
result={'status':'POST_RESULT_SCALAR_DIAGNOSTIC_ONLY','decimal_precision':80,'inputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (inp,protocol)},'inherited_source_hashes':saved['inputs'],'zero_loser':{'algebraic_total_equivalent':str(zero),'S0_net_retention_pct':str((zero-seed)/s0net*100),'gaps':{k:{'floor':str(v),'required_multiplier':str(v/zero),'log_growth_gap':str((v/zero).ln()),'shortfall':str(v-zero)} for k,v in floors.items()},'cumulative_cycle_endpoints':endpoints},'observed_cached_r_product':str(base),'roots':roots}
(P/'growth-requirements-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('zero_loser','roots')},indent=2))
