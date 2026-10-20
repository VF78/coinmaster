import sqlite3,zlib,json,hashlib,copy,statistics
from pathlib import Path
r=Path('reports/sol-corridor-113');db=sqlite3.connect('file:'+str(r/'memory-native-load-bundle-measure.sqlite')+'?mode=ro',uri=True)
real=sqlite3.connect('file:/tmp/pytest-of-root/pytest-680/test_native_existing_lifecycle0/engine1.sqlite?mode=ro',uri=True)
templates={}
for (body,) in real.execute("SELECT payload FROM rows WHERE kind='risk_first_sol_audit'"):
 row=json.loads(body)
 if row.get('event') in ('TARGET','TRIM'):templates[row['event']]=row
if len(templates)<2:
 for (body,) in real.execute("SELECT payload FROM rows WHERE kind='risk_first_sol_audit'"):
  row=json.loads(body)
  for value in row.values():
   if value in ('TARGET','TRIM') if isinstance(value,str) else False:templates[value]=row
assert len(templates)==2,templates
cancel=None
for (body,) in real.execute("SELECT payload FROM native WHERE kind='order_event'"):
 row=json.loads(body)
 if row.get('type')=='OrderCanceled':cancel=row;break
assert cancel
def pack(records):
 h=hashlib.sha256();hh=hashlib.sha256();total=0
 for i in range(0,len(records),256):
  batch=records[i:i+256];raw=json.dumps(batch,separators=(',',':')).encode();enc=zlib.compress(raw,6);dec=zlib.decompress(enc);assert raw==dec;total+=len(enc);h.update(raw);hh.update(dec)
 return dict(logical_records=len(records),compressed_bytes=total,bytes_per_fill=total/30000,original_sha=h.hexdigest(),decoded_sha=hh.hexdigest(),equal=h.digest()==hh.digest())
rows=[];normal=[];partial=[]
for seq,kind,key,ns,body in db.execute("SELECT * FROM native WHERE kind='order' ORDER BY seq"):
 bundle=json.loads(zlib.decompress(body));normal.append([seq,kind,key,ns,bundle])
 extra=copy.deepcopy(cancel)
 for k in ('client_order_id','ts_event','ts_init'):
  if k in extra:extra[k]=key if k=='client_order_id' else ns
 if 'event_id' in extra:extra['event_id']=bundle['events'][0].get('event_id',extra['event_id'])
 plus=copy.deepcopy(bundle);plus['events'].append(extra);partial.append([seq,kind,key,ns,plus])
 for template in templates.values():
  row=copy.deepcopy(template)
  for k in row:
   if k in ('order_id','client_order_id'):row[k]=key
   elif k in ('ts_event','ts_init','ts_ns','timestamp_ns','quote_ns','now_ns'):row[k]=ns
  rows.append([seq,'risk_first_sol_audit',row])
a=pack(rows);b=pack(normal);c=pack(partial)
base=json.loads((r/'memory-storage-chunk-budget.json').read_text())
account_mean=db.execute("SELECT avg(length(payload)) FROM native WHERE kind='account'").fetchone()[0]
accounts=[len(zlib.compress(v[0].encode(),6)) for v in real.execute("SELECT payload FROM native WHERE kind='account'")]
contexts=[len(zlib.compress(v[0].encode(),6)) for v in real.execute("SELECT payload FROM contexts")]
context_mean=db.execute('SELECT avg(length(payload)) FROM contexts').fetchone()[0]
partial_delta=(c['compressed_bytes']-b['compressed_bytes'])/30000
account_extra=max(accounts)-account_mean;context_extra=max(contexts)-context_mean
extra=a['bytes_per_fill']*1.25+max(0,partial_delta)*1.25+max(0,account_extra)+max(0,context_extra)+32
n=2102400;total=n*(base['per_fill_bytes_archive_plus_gzip']+extra)+734003200
out=dict(status='NO_ENGINE_NO_SOURCE_CHANGED_MEASUREMENT',generated_rows_note='Copies of actual existing TARGET/TRIM and native cancellation fields varied only using existing 30k order IDs and timestamps. This is codec measurement, not additional native trading facts.',target_trim_chunk_proof=a,normal_bundle_proof=b,extra_cancel_event_bundle_proof=c,partial_event_delta_bytes_per_order=partial_delta,account_extra_max_vs_load_mean=account_extra,context_extra_max_vs_load_mean=context_extra,extra_per_order_with_25percent_chunk_uplift_and_32byte_index_numeric_allowance=extra,planning_native_fills=n,base_archive_csv_bytes=n*base['per_fill_bytes_archive_plus_gzip'],fixed_outputs_and_reserve_bytes=734003200,total_practical_budget_bytes=total,free_after_derived_cleanup=base['free_disk_bytes']+base['derived_reclaimable_bytes'],headroom_bytes=base['free_disk_bytes']+base['derived_reclaimable_bytes']-total,universal_bound=False,cadence_note='2x minute count plus measured per-order extras is practical planning, not mathematical hard order maximum.',durability='Implementation must FULL-commit each15m batch. Global256 compression requires bounded repack of the last already-committed short chunk, not uncommitted buffers across nativepurge.')
(r/'memory-storage-practical-budget.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

