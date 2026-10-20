"""One operational read-only incremental gzip reader; no engine/PnL model."""
import csv,json,zlib,time,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,UTC
out=Path(__file__).parent
launch=json.loads((out/'r2-launch-receipt.json').read_text())
job=Path(launch['job_dir']);unit=launch['unit'];pid=int(next(x.split('=',1)[1] for x in launch['systemd_after_startup'].splitlines() if x.startswith('MainPID=')))
trace=job/'result/minute-native-risk.csv.gz'
assert trace.exists() and pid>0
z=zlib.decompressobj(16+zlib.MAX_WBITS);buf='';header=None;rows=minutes=offset=0;peak=D(10000);dd=D(0);last=None;last_emit=0;dead_count=0

def consume(data):
 global buf,header,rows,minutes,peak,dd,last
 buf+=data.decode('utf-8')
 if len(buf)>4*1024*1024:raise ValueError('PROGRESS_BUFFER_BOUND')
 lines=buf.split('\n');buf=lines.pop()
 for line in lines:
  if not line.strip():continue
  row=next(csv.reader([line]))
  if header is None:header=row;continue
  values=dict(zip(header,row));rows+=1
  phase=values['phase']
  if phase.endswith('post_quote_paired_close'):minutes+=1
  if not phase.startswith('post_boundary_'):
   E=D(values['paired_close_equity']);peak=max(peak,E)
   if peak>0:dd=max(dd,(peak-E)/peak*100)
  last={k:values[k] for k in ('close_available_ns','phase','cash','paired_close_equity')}

def native_alive():
 try:return unit in Path('/proc/'+str(pid)+'/cgroup').read_text()
 except FileNotFoundError:return False

def emit(alive):
 rss=None
 try:
  status=Path('/proc/'+str(pid)+'/status').read_text()
  rss=int(next(l.split()[1] for l in status.splitlines() if l.startswith('VmRSS:')))*1024
 except (FileNotFoundError,StopIteration):pass
 sample={'status':'PROVISIONAL_NATIVE_TRACE_PROGRESS' if alive else 'ENGINE_STOPPED_AUDITS_NOT_VALIDATED','observed_utc':datetime.now(UTC).isoformat(),'unit':unit,'engine_PID':pid,'reader_PID':os.getpid(),'engine_alive':alive,'compressed_bytes_consumed_once':offset,'native_sample_rows':rows,'counted_SOL_quote_minutes':minutes,'last_stored_native_sample':last,'provisional_stored_native_peak':str(peak),'provisional_native_DD_lower_bound_percent':str(dd),'current_engine_RSS_bytes':rss,'gzip_complete':z.eof,'limitations':'Stored trace phases are observed native values; settlement NOT certified here. Equity and DD provisional/lower-bound until complete durable audit validation. No price/PnL model, no reread.'}
 if last:sample['last_sample_UTC']=datetime.fromtimestamp(int(last['close_available_ns'])/1e9,UTC).isoformat()
 target=out/'r2-progress.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(sample,indent=2)+'\n');tmp.replace(target)
 with (out/'r2-progress-history.jsonl').open('a') as f:f.write(json.dumps(sample)+'\n')
 print(json.dumps(sample),flush=True)

with trace.open('rb') as stream:
 while True:
  while True:
   block=stream.read(65536)
   if not block:break
   offset+=len(block)
   while block:
    consume(z.decompress(block,1024*1024));block=z.unconsumed_tail
  alive=native_alive()
  if not alive:dead_count+=1
  else:dead_count=0
  if time.monotonic()-last_emit>=30 or not alive:
   emit(alive);last_emit=time.monotonic()
  if dead_count>=2:break
  time.sleep(5)
