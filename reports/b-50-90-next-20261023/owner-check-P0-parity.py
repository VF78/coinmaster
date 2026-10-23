"""Exact saved B/new OFF control comparison. No engine and no tolerance widening."""
import csv,gzip,hashlib,json
from pathlib import Path
R=Path(__file__).parent.resolve();BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs');OLD=BASE/'sol-conditional-hedge-btc-band-20261023/BTC_REGIME_REENTRY_BAND_05/result';NEW=BASE/'b-50-90-next-20261023/P0/result'
def artifact(p):return json.load(next(x for x in p.glob('v0*.json') if not x.name.endswith('-raw-native.json')).open())
a=artifact(OLD);b=artifact(NEW)
checks={k:a[k]==b[k] for k in ['terminal_total','terminal_active','terminal_reserve','terminal_open_positions','fills','native_fees','funding','liquidation_count','config_hash','data_hash','policy_hash','fill_audit','post_boundary_settlement']}
for k in ['cash_account_series','interval_cash_account_series']:checks[k+'_exact']=a[k]==b[k]
ra=a['minute_risk_observations']['settled_native_close_receipts'];rb=b['minute_risk_observations']['settled_native_close_receipts']
for k in ['curve','receipts','unavailable_intervening_native_mutation','first_unavailable']:checks['settled_'+k+'_exact']=ra[k]==rb[k]
def tracehash(p):
 h=hashlib.sha256()
 with gzip.open(p/'minute-native-settled-receipts.csv.gz','rb') as f:
  while block:=f.read(8*1024*1024):h.update(block)
 return h.hexdigest()
traces=dict(old=tracehash(OLD),new=tracehash(NEW));checks['full_uncompressed_settled_trace_exact']=traces['old']==traces['new']
keys=['instrument_id','type','side','quantity','time_in_force','is_reduce_only','filled_qty','avg_px','status','ts_init','ts_last','price','commissions']
def orderrows(d):
 p=Path(d['execution_artifacts']['orders']['path'])
 with p.open() as f:return [{k:r.get(k) for k in keys} for r in csv.DictReader(f)]
checks['ordered_native_order_economic_fields_exact']=orderrows(a)==orderrows(b)
out=dict(status='PASS_EXACT_B_PARITY' if all(checks.values()) else 'FAIL_EXACT_B_PARITY',source_commit='bd04c9b3858bcda40060a08eff488849c69af5d8',reference_source='25a085f596292df58e51188dd91e996adbe5724c',checks=checks,trace_sha256=traces,old_TOTAL=a['terminal_total'],new_TOTAL=b['terminal_total'],new_config=b['config_hash'],basis='No exclusions/tolerance changes; native economic order fields separate from random init UUID identities',no_extra_engine=True)
(R/'owner-P0-parity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
