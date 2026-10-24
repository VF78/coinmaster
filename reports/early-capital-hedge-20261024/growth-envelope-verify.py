"""Independent exact-rational check using parent CSV money, no Decimal product loop."""
import csv, json, hashlib
from fractions import Fraction as F
from decimal import Decimal, localcontext
from pathlib import Path
P=Path(__file__).resolve().parent; root=P.parents[1]
rows=[r for r in csv.DictReader((root/'reports/new-system-plan-20261024/btc-participation-parents.csv').open()) if r['variant']=='R3']
result=json.loads((P/'growth-envelope-results.json').read_text())
capital=F(10000); factor_numerators={k:F(1) for k in result['scenarios']}; denominators=F(1); exact_paths={k:[] for k in factor_numerators}
for r in rows:
 net=F(r['actual_fill_net_ex_funding'])+F(r['signed_BTC_funding'])
 assert abs(capital-F(r['own_settled_equity_at_decision']))<=F('0.000001')
 adjustments={'observed':net,'uniformhalf':net/2,'oraclelosshalving':net/2 if net<0 else net}
 denominators*=capital
 for key,adj in adjustments.items():
  factor_numerators[key]*=capital+adj
  exact_paths[key].append(F(10000)*factor_numerators[key]/denominators)
 capital+=net
assert capital==F('120718.40416503')
checks={}
with localcontext() as ctx:
 ctx.prec=100
 def dec(f):return Decimal(f.numerator)/Decimal(f.denominator)
 for key,path in exact_paths.items():
  high=F(10000);dd=F(0)
  for value in path:
   high=max(high,value);dd=max(dd,1-value/high)
  totaldiff=dec(path[-1])-Decimal(result['scenarios'][key]['algebraic_total_equivalent'])
  dddiff=dec(dd*100)-Decimal(result['scenarios'][key]['cycle_boundary_DD_pct'])
  assert abs(totaldiff)<Decimal('1e-65') and abs(dddiff)<Decimal('1e-65')
  checks[key]={'exact_rational_total_difference':str(totaldiff),'exact_rational_boundary_DD_difference':str(dddiff)}
 for name,co in result['cohorts'].items():
  for key in exact_paths:
   assert abs(dec(exact_paths[key][co['count']-1])-Decimal(co['values'][key]))<Decimal('1e-65')
verification={'status':'PASS','method':'exact Fraction products from independently loaded parent ex-funding net + signed funding; Decimal100 only converts for comparison','scenario_checks':checks,'cohort_checks':'PASS','code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (P/'growth-envelope-calculate.py',Path(__file__).resolve())}}
(P/'growth-envelope-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification,indent=2))
