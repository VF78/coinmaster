import sqlite3,zlib,hashlib,json,shutil,time
from pathlib import Path
r=Path('reports/sol-corridor-113');source=r/'memory-native-load-bundle-measure.sqlite';target=r/'memory-native-load-dictionary-measure.sqlite'
if target.exists():raise ValueError('DIAGNOSTIC_NAMESPACE_EXISTS')
start=time.perf_counter();old=sqlite3.connect(f'file:{source}?mode=ro',uri=True)
fields=set()
def keys(value):
 if isinstance(value,dict):
  for key,item in value.items():fields.add(key);keys(item)
 elif isinstance(value,list):
  for item in value:keys(item)
for table in ('rows','contexts','native'):
 for (body,) in old.execute(f'SELECT payload FROM {table}'):keys(json.loads(zlib.decompress(body)))
fields.update('original_attempt_ids native_final_receipt source_quote_ns receipt_ns source_fill_epoch final_fill_epoch checkpoint_valid SOL_unknown_ACK BTC_unknown_ACK E H C L held_L pending_L transition_satisfied BTC_actual BTC_possible Q2_remaining cost cost_basis target alpha beta a u held status'.split())
dictionary=json.dumps({key:None for key in sorted(fields)}).encode()
assert len(dictionary)<=32768
(r/'memory-storage-schema-dictionary.json').write_bytes(dictionary)
def encode(body):
 c=zlib.compressobj(6,zlib.DEFLATED,zlib.MAX_WBITS,zdict=dictionary)
 return c.compress(body)+c.flush()
def decode(body):
 c=zlib.decompressobj(zdict=dictionary)
 return c.decompress(body)+c.flush()
new=sqlite3.connect(target);new.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-2048; PRAGMA temp_store=FILE;')
tables=old.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
for table,sql in tables:new.execute(sql)
proof={}
for table,_ in tables:
 columns=[row[1] for row in old.execute(f'PRAGMA table_info({table})')]
 payload=columns.index('payload') if 'payload' in columns else None
 n=0;h1=hashlib.sha256();h2=hashlib.sha256()
 for row in old.execute(f'SELECT * FROM {table}'):
  values=list(row)
  if payload is not None:
   body=zlib.decompress(values[payload]);values[payload]=encode(body);h1.update(body);h2.update(decode(values[payload]))
  new.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in values)})',values);n+=1
  if n%1000==0:new.commit()
 new.commit();proof[table]=dict(rows=n,original_sha=h1.hexdigest(),decoded_sha=h2.hexdigest(),equal=h1.digest()==h2.digest())
for (sql,) in old.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):new.execute(sql)
new.commit();assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok';new.close();old.close()
gzip_pair=json.loads((r/'memory-storage-gzip-budget.json').read_text())['gzip_pair_bytes']
size=target.stat().st_size;per=(size+gzip_pair)/30000
out=dict(status='LAST_CODEC_MEASUREMENT_NO_SOURCE_NO_ENGINE',dictionary=dict(path=str(r/'memory-storage-schema-dictionary.json'),bytes=len(dictionary),sha256=hashlib.sha256(dictionary).hexdigest(),keys=len(fields),values='null placeholders only; no prices/order IDs/trading values'),source=str(source),target=str(target),archive_bytes=size,gzip_pair_bytes=gzip_pair,bytes_per_fill_archive_plus_gzip=per,exact_decode_proof=proof,elapsed_seconds=time.perf_counter()-start,free_disk_bytes=shutil.disk_usage('/var/lib/coinmaster-native-gui/data').free,
 scenarios=[dict(native_fills=n,archive_plus_gzip=n*per,allowance_bytes=700*1024**2,total=n*per+700*1024**2) for n in (500000,1051200,2102400)],
 caveat='Need separate actual TARGET/TRIM audit row allowance and a source-supported callback/order bound. No source correction unless positive all-output budget.')
assert all(v['equal'] for v in proof.values())
(r/'memory-storage-dictionary-budget.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
