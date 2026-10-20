import sqlite3,zlib,hashlib,json,shutil,time
from pathlib import Path
r=Path('reports/sol-corridor-113');source=r/'memory-native-load-bundle-measure.sqlite';target=r/'memory-native-load-chunk-measure.sqlite'
if target.exists():raise ValueError('DIAGNOSTIC_NAMESPACE_EXISTS')
start=time.perf_counter();old=sqlite3.connect(f'file:{source}?mode=ro',uri=True);new=sqlite3.connect(target)
for db in (old,new):db.executescript('PRAGMA cache_size=-2048; PRAGMA temp_store=FILE;')
new.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; CREATE TABLE chunks(kind TEXT,ordinal INTEGER,n INTEGER,payload BLOB,PRIMARY KEY(kind,ordinal));')
proof={}
def chunks(kind,query):
 before=hashlib.sha256();after=hashlib.sha256();batch=[];count=0;ordinal=0
 def flush():
  nonlocal ordinal
  encoded=zlib.compress(json.dumps(batch,separators=(',',':')).encode(),6)
  restored=json.loads(zlib.decompress(encoded))
  for actual,decoded in zip(batch,restored):
   assert actual==decoded
   after.update(json.dumps(decoded,separators=(',',':')).encode())
  new.execute('INSERT INTO chunks VALUES(?,?,?,?)',(kind,ordinal,len(batch),encoded));ordinal+=len(batch)
 for row in old.execute(query):
  values=list(row);values[-1]=json.loads(zlib.decompress(values[-1]))
  before.update(json.dumps(values,separators=(',',':')).encode());batch.append(values);count+=1
  if len(batch)==256:flush();batch.clear()
 if batch:flush()
 new.commit();proof[kind]=dict(rows=count,original_sha=before.hexdigest(),decoded_sha=after.hexdigest(),equal=before.digest()==after.digest())
for kind, in old.execute('SELECT DISTINCT kind FROM rows'):
 chunks('rows:'+kind,"SELECT * FROM rows WHERE kind='"+kind.replace("'","''")+"' ORDER BY seq")
chunks('native:order',"SELECT * FROM native WHERE kind='order' ORDER BY seq")
for table in ('trade_ids','contexts','native'):
 sql=old.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone()[0];new.execute(sql)
 query='SELECT * FROM '+table+(" WHERE kind!='order'" if table=='native' else '')
 h1=hashlib.sha256();h2=hashlib.sha256();count=0
 for row in old.execute(query):
  new.execute('INSERT INTO '+table+' VALUES('+','.join('?' for _ in row)+')',row);count+=1
  if table!='trade_ids':h1.update(zlib.decompress(row[-1]));h2.update(zlib.decompress(row[-1]))
 new.commit();proof[table]=dict(rows=count,original_sha=h1.hexdigest(),decoded_sha=h2.hexdigest(),equal=h1.digest()==h2.digest())
for name,sql in old.execute("SELECT tbl_name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
 if name!='rows':new.execute(sql)
new.commit();assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
stats={k:dict(chunks=n,logical_rows=c,compressed_payload_bytes=b) for k,n,c,b in new.execute('SELECT kind,count(*),sum(n),sum(length(payload)) FROM chunks GROUP BY kind')}
native={k:dict(rows=n,compressed_payload_bytes=b) for k,n,b in new.execute('SELECT kind,count(*),sum(length(payload)) FROM native GROUP BY kind')}
new.close();old.close()
size=target.stat().st_size;csv=json.loads((r/'memory-storage-gzip-budget.json').read_text())['gzip_pair_bytes'];per=(size+csv)/30000
derived=[r/'memory-native-load-zlib-measure.sqlite',r/'memory-native-load-bundle-measure.sqlite',r/'memory-native-load-dictionary-measure.sqlite',target]
out=dict(status='MEASUREMENT_ONLY_NO_SOURCE_OR_ENGINE',source=str(source),target=str(target),archive_bytes=size,gzip_pair_bytes=csv,per_fill_bytes_archive_plus_gzip=per,chunk_records_max=256,chunk_stats=stats,native_individual_stats=native,exact_lossless_proof=proof,elapsed_seconds=time.perf_counter()-start,free_disk_bytes=shutil.disk_usage(r).free,derived_reclaimable_bytes=sum(p.stat().st_size for p in derived),scenarios=[dict(native_fills=n,archive_and_csv_gzip=n*per,allowance_bytes=700*1024**2,total_bytes=n*per+700*1024**2) for n in (1051200,2102400)],caveat='Extra real TARGET/TRIM/partial events beyond synthetic full-fill three-event order still require allowance; 2x is conservative planning, not universal hard upper bound.')
assert all(v['equal'] for v in proof.values())
(r/'memory-storage-chunk-budget.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

