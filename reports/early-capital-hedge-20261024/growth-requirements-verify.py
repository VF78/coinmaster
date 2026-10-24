"""Exact-rational verification of cached-decimal bookend and root brackets."""
import json,hashlib
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
P=Path(__file__).resolve().parent
r=json.loads((P/'growth-requirements-results.json').read_text());cached=json.loads((P/'growth-envelope-results.json').read_text())
returns=[F(x['return']) for x in cached['cycle_checks']]
def exact(alpha):
 product=F(10000)
 for x in returns:product*=1+(alpha*x if x<0 else x)
 return product
assert any(x<0 for x in returns) and all(x>-1 for x in returns)
with localcontext() as ctx:
 ctx.prec=100
 def d(x):return D(x.numerator)/D(x.denominator)
 zero=exact(F(0));zero_res=d(zero)-D(r['zero_loser']['algebraic_total_equivalent']);assert abs(zero_res)<D('1e-65')
 checks={}
 for name,root in r['roots'].items():
  floor=F(r['zero_loser']['gaps'][name]['floor'])
  lo=F(root['alpha_bracket_lo']);hi=F(root['alpha_bracket_hi']);mid=F(root['alpha_negative_return_retained'])
  assert F(0)<=lo<hi<=F(1) and exact(lo)>=floor>=exact(hi)
  assert hi-lo<F('1e-70')
  res=d(exact(mid)-floor);assert abs(res)<D('1e-60')
  checks[name]={'exact_bracket_signs':'PASS','exact_mid_money_residual':str(res),'bracket_width':str(d(hi-lo))}
 verification={'status':'PASS','zero_product_decimal_minus_exact_residual':str(-zero_res),'monotonicity':'strictly decreasing on[0,1]: each negative r has positive factor1+alpha*r and negative derivative; positive factors constant;29negative terms','root_checks':checks,'script_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (P/'growth-requirements-calculate.py',Path(__file__).resolve())}}
(P/'growth-requirements-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification,indent=2))
