from pathlib import Path
from decimal import Decimal as D
import sys,json,csv,hashlib,shutil,collections
report=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/sol-conditional-hedge-btc-band-20261023')
base=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023')
recipe=sys.argv[1];job=base/recipe;comp=json.loads((job/'completion.json').read_text());prep=json.loads((job/'preparation.json').read_text());path=Path(comp['artifact']);d=json.loads(path.read_text());rawpath=path.with_name(path.stem+'-raw-native.json');raw=json.loads(rawpath.read_text())
p0=next(x for x in (base/'P0/result').glob('*.json') if x.name.endswith('direction.json'));s0=json.loads(p0.read_text())
out=report/('owner-'+recipe+'-events');out.mkdir(exist_ok=False)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvexport(name,rows):
    if isinstance(rows,dict):rows=[dict(client_order_id=k,**v) for k,v in rows.items()]
    p=out/name;keys=sorted({k for r in rows for k in r})
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,sort_keys=True,separators=(',',':')) if isinstance(v,(dict,list,tuple,set)) else v for k,v in row.items()})
    return dict(path=str(p),rows=len(rows),sha256=digest(p))
exports={}
for kind,meta in d['execution_artifacts'].items():
    src=Path(meta['path']);assert digest(src)==meta['sha256'];dest=out/('native-'+kind+'.csv');shutil.copy2(src,dest);exports[kind]=dict(path=str(dest),rows=meta['rows'],sha256=digest(dest))
for name,rows in [('native-fill-audit.csv',d['fill_audit']),('native-order-events.csv',raw['native_order_events']),('hedge-band-audit.csv',d['hedge_band_audit']),('entry-sizing-audit.csv',d['entry_sizing_audit']),('split-parent-audit.csv',d.get('split_cover_audit',{}).get('parents',[]))]:
    exports[name]=csvexport(name,rows)
rights=[]
for i,row in enumerate(d['fill_audit']):
    if row.get('action') in ('BTC_REDUCE','SOL_ADD','SOL_HALF_EXIT','SOL_EXIT'):
        rights.append(dict(source_kind='native_fill_audit',source_index=i,timestamp_ns=row.get('fill_ns'),**row))
for i,row in enumerate(d['hedge_band_audit']):
    if row.get('event')=='BTC_FLAT_INVALIDATE_RIGHTS':rights.append(dict(source_kind='hedge_band_audit',source_index=i,**row))
exports['rights_lifecycle']=csvexport('actual-rights-and-fill-lifecycle.csv',rights)
valid=dict(full_rows=d['streaming']['processed_rows_per_source']==1051200,terminal_positions_flat=d['terminal_open_positions']==0,terminal_open_orders_zero=raw['native_strategy_events']['terminal_open_orders']==0,terminal_pending_flat=d['terminal_lifecycle']['status']=='FLAT',expected_config_exact=d['config_hash']==prep['expected_config_sha256'],s0_data_exact=d['data_hash']==s0['data_hash'],s0_execution_policy_exact=d['policy_hash']==s0['policy_hash'],native_fills_export_rows=exports['fills']['rows']==d['fills'])
parents=d.get('split_cover_audit',{}).get('parents',[])
valid['btc_split_quantity_conserved']=all(D(str(p['filled']))+D(str(p['cancelled']))==D(str(p['quantity'])) for p in parents)
for name,expected in json.loads((base/'source-25a085f-sha256.json').read_text()).items():assert digest(Path(prep['source_snapshot'])/name)==expected,name
valid['source_freeze_exact']=True
risk=d['minute_risk_observations']['curves'];settled=risk['post_quote_paired_close']['top3_distinct_excursions'][0]['drawdown_peak_percent']
allnative=risk['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent']
total=D(d['terminal_total']);s0total=D(s0['terminal_total']);retention=(total-D(10000))/(s0total-D(10000))*100
counts=dict(collections.Counter(r['event'] for r in d['hedge_band_audit']))
with Path(exports['orders']['path']).open() as f:orderrows=list(csv.DictReader(f))
order_status_counts=dict(collections.Counter(r['status'] for r in orderrows))
partial_terminal_orders=sum(D(r['filled_qty'])>0 and D(r['filled_qty'])<D(r['quantity']) for r in orderrows)
children=[r for r in d['hedge_band_audit'] if r['event']=='H4_NATIVE_CHILD']
increases=[r for r in children if r['action']=='SOL_ADD']
activations=[r for r in d['hedge_band_audit'] if r['event']=='H4_ACTIVATION']
if recipe.startswith('H4'):
    valid['h4_increase_strictly_before_frozen_deadline']=all(int(r['timestamp_ns'])<int(r['deadline_ns']) for r in increases)
    valid['h4_single_increase_per_pinned_sol_quote']=len({r['timestamp_ns'] for r in increases})==len(increases)
    valid['h4_activations_finite_positive_daily_beta']=all(D(str(r['beta0'])).is_finite() and D(str(r['beta0']))>0 for r in activations)
    valid['h4_fixed_activation_ttl']=all(int(r['deadline_ns'])-int(r['timestamp_ns'])==14_400_000_000_000 for r in activations)
    valid['h4_increase_only_positive_unfilled_target']=all(D(str(r['target']))>D(str(r['held'])) and D(str(r['quantity']))>0 for r in increases)
actions=dict(collections.Counter(r['action'] for r in d['fill_audit']))
receipt=dict(recipe=recipe,source_commit=prep['source_commit'],artifact=str(path),artifact_sha256=digest(path),raw_artifact=str(rawpath),raw_sha256=digest(rawpath),config_sha256=d['config_hash'],data_sha256=d['data_hash'],policy_sha256=d['policy_hash'],total=str(total),cumulative_ROI_percent=str((total/D(10000)-1)*100),geometric_monthly_ROI_percent=(float(total/10000)**(1/24)-1)*100 if total>0 else None,profit_retention_percent=str(retention),settled_post_quote_DD_percent=settled,all_native_close_DD_percent=allnative,fills=d['fills'],native_fees=d['native_fees'],funding=d['funding'],native_fill_action_counts=actions,hedge_event_counts=counts,native_order_status_counts=order_status_counts,native_partial_terminal_order_count=partial_terminal_orders,resources=comp['resources'],mechanical_checks=valid,status='VALID_NATIVE_COMPLETED' if all(valid.values()) else 'INVALID_NATIVE_MECHANICAL_CHECK',exports=exports,rights_export_note='Actual native fill rows and explicit final-flat right invalidation events; no inferred fill, ownership, or PnL. Native partial/terminal data preserved in native orders/events exports.',no_extra_engine=True)
(job/'collected-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');(report/('owner-'+recipe+'-receipt.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
bpath=report/'run-budget.json';b=json.loads(bpath.read_text());a=next(x for x in b['attempts'] if x.get('recipe')==recipe);a['state']='COMPLETED_VALID_NATIVE' if all(valid.values()) else 'COMPLETED_INVALID_NATIVE';a['receipt']=str(report/('owner-'+recipe+'-receipt.json'));a['lifecycle_checks']=valid;bpath.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('recipe','status','total','cumulative_ROI_percent','geometric_monthly_ROI_percent','profit_retention_percent','settled_post_quote_DD_percent','all_native_close_DD_percent','fills','native_fees','native_fill_action_counts','hedge_event_counts','native_order_status_counts','native_partial_terminal_order_count','resources','mechanical_checks')},ensure_ascii=False,indent=2))
