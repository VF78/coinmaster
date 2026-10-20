import sqlite3,zlib,hashlib,json,os,time,shutil
from pathlib import Path
r=Path('reports/sol-corridor-113');source=r/'memory-native-load-bounded.sqlite';target=r/'memory-native-load-zlib-measure.sqlite'
if target.exists():raise ValueError('DIAGNOSTIC_NAMESPACE_EXISTS')
start=time.perf_counter();old=sqlite3.connect(f'file:{source}?mode=ro',uri=True);new=sqlite3.connect(target)
new.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-2048; PRAGMA temp_store=FILE;')
tables=old.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
for table,sql in tables:new.execute(sql)
counts={};digests={};payloads={}
for table,_ in tables:
 columns=[row[1] for row in old.execute(f'PRAGMA table_info({table})')]
 payload=columns.index('payload') if 'payload' in columns else None
 h1=hashlib.sha256();h2=hashlib.sha256();n=0;raw=comp=0
 for row in old.execute(f'SELECT * FROM {table}'):
  values=list(row)
  if payload is not None:
   body=values[payload].encode();encoded=zlib.compress(body,6)
   raw+=len(body);comp+=len(encoded);h1.update(body);h2.update(zlib.decompress(encoded));values[payload]=encoded
  new.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in values)})',values);n+=1
  if n%1000==0:new.commit()
 new.commit();counts[table]=n;digests[table]=dict(original=h1.hexdigest(),decoded=h2.hexdigest(),equal=h1.digest()==h2.digest());payloads[table]=dict(raw=raw,zlib=comp)
for (sql,) in old.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):new.execute(sql)
new.commit();assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok';new.close();old.close()
csv={p.name:p.stat().st_size for p in (r/'memory-load-orders.csv',r/'memory-load-fills.csv')}
size=source.stat().st_size;compressed=target.stat().st_size;csvtotal=sum(csv.values());free=shutil.disk_usage('/var/lib/coinmaster-native-gui/data').free
out=dict(status='READ_ONLY_FACTS_STREAMCOPY_NO_ENGINE_NO_SOURCE_EDIT',source=str(source),target=str(target),source_bytes=size,compressed_bytes=compressed,counts=counts,exact_payload_decode_digests=digests,payload_bytes=payloads,csv_bytes=csv,free_disk_bytes=free,elapsed_seconds=time.perf_counter()-start,
 bytes_per_native_fill=dict(plain_archive=size/30000,zlib_archive=compressed/30000,csv_pair=csvtotal/30000),
 projected_total_bytes=[dict(native_fills=n,plain_archive_plus_csv=n*(size+csvtotal)/30000,zlib_archive_plus_csv=n*(compressed+csvtotal)/30000) for n in (100000,250000,500000,1051200,2102400)],
 caveat='Fill count is not known before the one candidate run. Quote/minute upper scenarios include conservative churn, not expected ROI/fills prediction. Diagnostic copy is not a production artifact.')
(r/'memory-storage-budget.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
