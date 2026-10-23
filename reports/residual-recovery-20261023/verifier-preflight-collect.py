import pathlib,json,csv,gzip,hashlib,time,sqlite3,collections
R=pathlib.Path(__file__).resolve().parents[2]; O=R/'reports/residual-recovery-20261023'; root=pathlib.Path('/Users/vf/Documents/ChatGPT/Coinmaster');e=root/'runtime/var/research-jobs/b-50-90-next-20261023/E4/result'
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
s=json.load(open('/tmp/btc-audit-exact-s0-direction.json'));receipt=json.load(open(R/'reports/b-50-90-next-20261023/owner-E4-receipt.json'));cache=json.load(open(R/'reports/b-50-90-next-20261023/verifier-E4-risk-cache.json'));saved=json.load(open(R/'reports/s0-management-20261022/economic-validation-s0.json'))
result={'status':'SAVED_DATA_PREFLIGHT','native_engines_started':0,'source_edits':0,'S0':{'source_commit':'75ffc9c69e9d79c4da4cd0614634a3eeba48d716','local_report':'/tmp/btc-audit-exact-s0-direction.json','report_sha256':sha('/tmp/btc-audit-exact-s0-direction.json'),'config_sha256':s['config_hash'],'TOTAL':s['terminal_total'],'source_hashes':s['source_hashes'],'interval':s['run_interval'],'episodes':s['episodes'],'artifacts':s['execution_artifacts'],'saved_validation':saved,'available_report_keys':list(s)},'E4':{'source_commit':receipt['source_commit'],'config_sha256':receipt['config_sha256'],'TOTAL':receipt['total'],'DD_percent':receipt['settled_native_DD_percent'],'checks':{},'traces':{},'export_schemas':{}}}
for key,hkey in [('artifact','artifact_sha256'),('raw_artifact','raw_sha256')]:
 p=pathlib.Path(receipt[key]);result['E4']['checks'][key]={'path':str(p),'sha256':sha(p),'expected':receipt[hkey],'match':sha(p)==receipt[hkey]}
for key,rec in receipt['exports'].items():
 p=pathlib.Path(rec['path']); actual=sha(p)
 with p.open() as h:
  r=csv.DictReader(h);fields=r.fieldnames;n=sum(1 for _ in r)
 result['E4']['export_schemas'][key]={'path':str(p),'sha256':actual,'hash_match':actual==rec['sha256'],'rows':n,'rows_match':n==rec['rows'],'fields':fields}
for f in e.glob('*.gz'):
 with gzip.open(f,'rt') as h:r=csv.DictReader(h);fields=r.fieldnames;row=next(r)
 result['E4']['traces'][f.name]={'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'fields':fields,'first_row':row}
f=e/'minute-native-settled-receipts.csv.gz';t=time.monotonic();first=last=prev=None;n=0;gaps=0;months=collections.Counter();held=collections.Counter();pkeys=set()
from datetime import datetime,timezone
with gzip.open(f,'rt') as h:
 for row in csv.DictReader(h):
  ns=int(row['source_quote_ns']);rn=int(row['receipt_ns']);first=ns if first is None else first;last=ns;n+=1
  if prev is not None and ns-prev!=60000000000:gaps+=1
  prev=ns;months[datetime.fromtimestamp(ns/1e9,timezone.utc).strftime('%Y-%m')]+=1
  for pos in json.loads(row['native_positions_and_mark_ohlc_json']):
   pkeys.update(pos);held[pos['instrument_id']]+=1
result['E4']['coverage_current_stream']={'receipts':n,'first_source_quote_ns':first,'last_source_quote_ns':last,'last_receipt_ns':rn,'non_minute_steps':gaps,'monthly_counts':dict(months),'held_position_samples':dict(held),'position_fields':sorted(pkeys),'elapsed_seconds':time.monotonic()-t,'uncompressed_fulltrace_hash_not_recomputed':'Prior completed verifier cache reused','compressed_hash_matches_prior_cache':sha(f)==cache['compressed_trace_sha256']}
fp=next(e.glob('*funding.sqlite'));con=sqlite3.connect('file:'+str(fp)+'?mode=ro&immutable=1',uri=True);tables=con.execute("select name,sql from sqlite_master where type='table'").fetchall();result['E4']['funding_sqlite_schema']=tables;con.close()
result['existing_screens']={}
for name in ['s0-weekly-postmortem-20261022/PROPOSAL.json','s0-weekly-postmortem-20261022/candidate-path-diagnostic.json','s0-weekly-postmortem-20261022/candidate-precheck-temporary-cap.json','chop-pair-113/stats-adverse-payoff-bound.md']:
 p=R/'reports'/name;result['existing_screens'][name]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
(O/'verifier-preflight.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':result['E4']['checks'],'coverage':result['E4']['coverage_current_stream'],'funding_schema':tables}))
