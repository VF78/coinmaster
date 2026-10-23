"""Mutation fixtures for descriptive comparator; no native engine."""
import csv,gzip,importlib.util,json,tempfile,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('ec',Path(__file__).with_name('execution_compare.py'));ec=importlib.util.module_from_spec(spec);spec.loader.exec_module(ec)
t={};base=[dict(receipt_ns='100',cash='10000',held='BTC1',margin='10'),dict(receipt_ns='200',cash='10001',held='BTC1',margin='10')]
def altered(key,value):return [dict(base[0]),dict(base[1],**{key:value})]
x=ec.firstdiff(base,altered('cash','9999'));t['cash_mutation_detected']=not x['equal'] and x['first_divergence']['index']==1;t['preceding_common_state_preserved']=x['first_divergence']['preceding_common_state']['baseline']==base[0]
t['count_mutation_detected']=not ec.firstdiff(base,base[:1])['equal'];t['identical_sequence_equal']=ec.firstdiff(base,base)['equal']
t['UUID_identity_excluded']=ec.clean({'episode_id':'x','cash':'1'})==ec.clean({'episode_id':'y','cash':'1'})
a=dict(instrument_id='SOL',quantity='2000',filled_qty='1000',status='CANCELED');b=dict(a,quantity='1000',status='FILLED');econ=['instrument_id','filled_qty'];t['real_status_request_change_reported']=not ec.firstdiff([a],[b])['equal'];t['status_change_not_automatically_fill_change']=ec.firstdiff([{k:a[k] for k in econ}],[{k:b[k] for k in econ}])['equal']
with tempfile.TemporaryDirectory() as tmp:
 def write(name,rows):
  p=Path(tmp)/name
  with gzip.open(p,'wt') as f:
   w=csv.DictWriter(f,list(base[0]));w.writeheader();w.writerows(rows)
  return p
 p=write('a.gz',base);q=write('b.gz',base);t['distinct_equal_streams']=ec.stream_compare(p,q,list(base[0]))['equal']
 for key,value in [('cash','9999'),('held','SOL1000'),('margin','200')]:
  q=write('changed.gz',altered(key,value));r=ec.stream_compare(p,q,list(base[0]));t[key+'_stream_mutation']=not r['equal'] and r['first_divergence']['fields']==[key] and r['first_divergence']['preceding_common_state']['state']==base[0]
 p=write('short.gz',base[:1]);q=write('long.gz',base);t['stream_count_mutation']=not ec.stream_compare(p,q,list(base[0]))['equal'];t['two_missing_streams_UNKNOWN']=ec.stream_compare(Path(tmp)/'missing1',Path(tmp)/'missing2',list(base[0]))['equal'] is None;t['one_missing_stream_UNKNOWN']=ec.stream_compare(p,Path(tmp)/'missing2',list(base[0]))['equal'] is None
t['terminal_money_mismatch_blocks_path_match']=not all(v['equal'] for k,v in {'terminal_total':{'equal':False},'config_hash':{'equal':True}}.items() if k!='config_hash')
out=Path(sys.argv[1]);archive=out.parent/'data-attribution-ARCHIVE_SELFTEST.json';seven=out.parent/'seven-episodes.json'
if archive.exists():
 from decimal import Decimal as D
 ar=json.loads(archive.read_text());ep=json.loads(seven.read_text())['episodes'];t['archive_1051199_complete_receipts']=ar['receipts']==1051199 and ar['missing_source_minutes']==0;t['archive_24months']=len(ar['monthly'])==24;t['monthly_boundary_uses_previous_receipt']=all(ar['monthly'][i]['start_equity']==ar['monthly'][i-1]['last_equity'] for i in range(1,len(ar['monthly'])));t['archive_exact_E4_global_DD']=D(ar['global_settled_DD_percent'])==D('57.58541045962226379114466259');t['seven_fixed_window_DDs_reproduce_archive']=all(abs(D(w['local_dd'])-D(e['drawdown_fraction'])*100)<D('1e-24') for w,e in zip(ar['seven_fixed_E4_anchor_windows'],ep));t['seven_native_endpoint_cash_identities']=all(w['fixed_endpoint_native_cash_bridge']['identity_exact'] for w in ar['seven_fixed_E4_anchor_windows'])
out.write_text(json.dumps(dict(checks=t,all_pass=all(t.values()),basis='short mutation fixtures plus separate archive identity/collector pass; no trading engine'),indent=2)+'\n');print(json.dumps(dict(passed=sum(t.values()),total=len(t),all_pass=all(t.values()))));assert all(t.values())
