"""Compare only already-qualified native artifact outputs. No engine or data access."""
import argparse,json
from pathlib import Path
from decimal import Decimal as D
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--off',required=True,type=Path);ap.add_argument('--c0',required=True,type=Path);ap.add_argument('--a0',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
x=ap.parse_args()
assert x.output.resolve().parent==Path(__file__).resolve().parent, 'OUTPUT_MUST_STAY_IN_ACCEPTANCE'
r={k:json.loads(getattr(x,k).read_text()) for k in ['off','c0','a0']}
assert [r[k]['variant'] for k in ['off','c0','a0']]==['R2_OFF','R2_C0','R2_A0']
out={'status':'UNKNOWN_BLOCKS','prefix_only':True,'engine_instances_created':0,'global_goal':'NOT_ESTABLISHED_BY_PREFIX','floors':{'70':'4256975.067212381','90':'5470396.514987347'}}
qualified=all(v.get('accounting_qualified') is True for v in r.values())
if qualified:
 off,c,a=[r[k] for k in ['off','c0','a0']]
 gain=D(a['terminal_total'])-D(c['terminal_total']);hurdle=2*max(D(0),D(a['fees'])-D(c['fees']))
 gates={'capital':gain>0,'cost':gain>hurdle,'settled_DD':D(a['settled_DD_percent'])<=50 and D(a['settled_DD_percent'])<=D(c['settled_DD_percent']),'event_DD':D(a['event_DD_percent'])<=50 and D(a['event_DD_percent'])<=D(c['event_DD_percent']),'daily_ES20':D(a['daily_ES20'])<=D(c['daily_ES20'])}
 rights=a.get('rights',{});release=rights.get('positive_filled_release_orders');rights_known=rights.get('status')=='PASS' and type(release) is int and release>=0 and rights.get('native_fill_coverage_complete') is True
 out.update(gates=gates,gain_vs_C0=str(gain),cost_hurdle=str(hurdle),rights=rights,parent_ES20_diagnostic={k:{field:r[k][field] for field in ['parent_count','parent_proven_count','parent_ES20_percent']} for k in r},comparison_vs_matched_R2_OFF={k:{'delta_TOTAL':str(D(r[k]['terminal_total'])-D(off['terminal_total'])),'delta_fees':str(D(r[k]['fees'])-D(off['fees'])),'settled_DD_percent':r[k]['settled_DD_percent'],'event_DD_percent':r[k]['event_DD_percent'],'daily_ES20_percent':r[k]['daily_ES20_percent']} for k in ['c0','a0']})
 if rights_known:
  out['status']='ECONOMICALLY_NOT_TESTED' if release==0 else ('QUALIFIED_POSITIVE_PREFIX' if all(gates.values()) else 'NONPASSING_PREFIX')
  out['unexplained_TOTAL_difference_without_positive_release_fill']=release==0 and gain!=0
  if release==0 and gain!=0:out['mechanism_attribution']='UNEXPLAINED_DIFFERENCE_BLOCKS_BENEFIT_CLAIM'
  elif release==0:out['mechanism_attribution']='NO_ADDITIONAL_BTC_FILL_NOT_TESTED'
  else:out['mechanism_attribution']='ACTUAL_RELEASE_FILL_PRESENT; BENEFIT_REQUIRES_ALL_GATES'
else:out['blocking_qualifications']={k:v.get('qualification','UNKNOWN') for k,v in r.items() if v.get('accounting_qualified') is not True}
x.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
