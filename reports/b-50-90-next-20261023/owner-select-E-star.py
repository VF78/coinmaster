"""Frozen protocol ranking of actual B/E4/EP receipts, never a new run."""
import json
from decimal import Decimal as D
from pathlib import Path
R=Path(__file__).parent.resolve();S0_DD=D('66.256914864686864');rows=[]
for recipe,name in [('B','P0'),('E4','E4'),('EP','EP')]:
 p=R/('owner-'+name+'-receipt.json')
 if not p.exists():raise SystemExit('WAIT_ALL_B_E4_EP_RECEIPTS')
 r=json.load(p.open());native=json.load(Path(r['artifact']).open());turnover=sum((D(f['notional']) for f in native['fill_audit']),D(0));dd=D(r['settled_native_DD_percent']);ret=D(r['profit_retention_percent']);total=D(r['total']);valid=all(r['mechanical_checks'].values()) and r['settled_observer_coverage']['complete'] and r['liquidation_count']==0
 rows.append(dict(recipe=recipe,receipt=str(p),total=total,dd=dd,retention=ret,turnover=turnover,valid=valid))
passing=[r for r in rows if r['valid'] and r['retention']>=90 and r['dd']<=50]
profit=[r for r in rows if r['valid'] and r['retention']>=90 and r['dd']<=S0_DD]
valid=[r for r in rows if r['valid'] and r['dd']<=S0_DD]
if passing:stage='1_MAX_TOTAL_50_90';chosen=min(passing,key=lambda r:(-r['total'],r['dd'],r['turnover']))
elif profit:stage='2_MIN_DD_RETENTION90_DD_LE_S0';chosen=min(profit,key=lambda r:(r['dd'],r['turnover']))
elif valid:stage='3_MAX_TOTAL_DD_LE_S0';chosen=min(valid,key=lambda r:(-r['total'],r['dd'],r['turnover']))
else:stage='NO_ELIGIBLE_E_STAR';chosen=None
out=dict(status='FROZEN_ACTUAL_PROTOCOL_SELECTION',rule='Accepted PLAN section9; no tuning; ties DD then actual fill turnover',stage=stage,selected=chosen['recipe'] if chosen else None,rows=rows,combination_launch_authorized=False)
(R/'owner-E-star-selection.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps(out,indent=2,default=str))
