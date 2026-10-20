import sqlite3,zlib,hashlib,json,shutil,time,itertools
from pathlib import Path
r=Path('reports/sol-corridor-113');source=r/'memory-native-load-bounded.sqlite';target=r/'memory-native-load-bundle-measure.sqlite'
if target.exists():raise ValueError('DIAGNOSTIC_NAMESPACE_EXISTS')
start=time.perf_counter();old=sqlite3.connect(f'file:{source}?mode=ro',uri=True);new=sqlite3.connect(target)
for db in (old,new):db.executescript('PRAGMA cache_size=-2048; PRAGMA temp_store=FILE;')
new.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;')
tables=old.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
for table,sql in tables:new.execute(sql)
proof={}
for table,_ in tables:
 if table=='native':continue
 columns=[row[1] for row in old.execute(f'PRAGMA table_info({table})')]
 payload=columns.index('payload') if 'payload' in columns else None
 n=0;before=hashlib.sha256();after=hashlib.sha256()
 for row in old.execute(f'SELECT * FROM {table}'):
  values=list(row)
  if payload is not None:
   body=values[payload].encode();values[payload]=zlib.compress(body,6)
   before.update(body);after.update(zlib.decompress(values[payload]))
  new.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in values)})',values);n+=1
  if n%1000==0:new.commit()
 new.commit();proof[table]=dict(rows=n,original_sha=before.hexdigest(),decoded_sha=after.hexdigest(),equal=before.digest()==after.digest())
event_rows=old.execute("SELECT json_extract(payload,'$.client_order_id'),payload FROM native WHERE kind='order_event' ORDER BY json_extract(payload,'$.client_order_id'),seq")
groups=iter(itertools.groupby(event_rows,key=lambda row:row[0]));current=next(groups,None)
events_count=orders_count=0;event_before=hashlib.sha256();event_after=hashlib.sha256();state_before=hashlib.sha256();state_after=hashlib.sha256()
for seq,kind,key,ns,body in old.execute("SELECT * FROM native WHERE kind='order' ORDER BY id"):
 assert current is not None and current[0]==key,(current[0] if current else None,key)
 event_bodies=[row[1] for row in current[1]]
 bundle='{"order":'+body+',"events":['+','.join(event_bodies)+']}'
 encoded=zlib.compress(bundle.encode(),6);decoded=json.loads(zlib.decompress(encoded))
 assert decoded['order']==json.loads(body)
 state_before.update(body.encode());state_after.update(json.dumps(decoded['order']).encode())
 for original,event in zip(event_bodies,decoded['events']):
  assert json.loads(original)==event
  event_before.update(original.encode());event_after.update(json.dumps(event).encode())
 events_count+=len(event_bodies);orders_count+=1
 new.execute('INSERT INTO native VALUES (?,?,?,?,?)',(seq,kind,key,ns,encoded))
 if orders_count%1000==0:new.commit()
 current=next(groups,None)
assert current is None
proof['orders']=dict(rows=orders_count,original_sha=state_before.hexdigest(),decoded_sha=state_after.hexdigest(),equal=state_before.digest()==state_after.digest())
proof['order_events']=dict(logical_rows=events_count,original_sha=event_before.hexdigest(),decoded_sha=event_after.hexdigest(),equal=event_before.digest()==event_after.digest())
n=0;h1=hashlib.sha256();h2=hashlib.sha256()
for seq,kind,key,ns,body in old.execute("SELECT * FROM native WHERE kind NOT IN ('order','order_event') ORDER BY seq"):
 enc=zlib.compress(body.encode(),6);h1.update(body.encode());h2.update(zlib.decompress(enc))
 new.execute('INSERT INTO native VALUES (?,?,?,?,?)',(seq,kind,key,ns,enc));n+=1
 if n%1000==0:new.commit()
proof['other_native']=dict(rows=n,original_sha=h1.hexdigest(),decoded_sha=h2.hexdigest(),equal=h1.digest()==h2.digest())
for (sql,) in old.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):new.execute(sql)
new.commit();assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
physical={kind:count for kind,count in new.execute('SELECT kind,count(*) FROM native GROUP BY kind')}
new.close();old.close()
gzip_pair=json.loads((r/'memory-storage-gzip-budget.json').read_text())['gzip_pair_bytes']
size=target.stat().st_size;per=(size+gzip_pair)/30000
out=dict(status='STREAMCOPY_MEASUREMENT_ONLY_NO_SOURCE_OR_ENGINE',source=str(source),target=str(target),archive_bytes=size,gzip_pair_bytes=gzip_pair,per_fill_bytes_archive_plus_gzip=per,
 physical_native_counts=physical,exact_lossless_proof=proof,elapsed_seconds=time.perf_counter()-start,free_disk_bytes=shutil.disk_usage('/var/lib/coinmaster-native-gui/data').free,
 scenarios=[dict(native_fills=n,archive_plus_gzip=n*per,extra_allowance_bytes=700*1024**2,total=n*per+700*1024**2) for n in (250000,500000,1051200,2102400)],
 caveat='Real TARGET/TRIM emitted rows per actual physical submission are absent from this synthetic fixture; not a proven exact candidate bytes/fill or quote-guard upper bound.')
assert all(v['equal'] for v in proof.values())
(r/'memory-storage-bundle-budget.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
