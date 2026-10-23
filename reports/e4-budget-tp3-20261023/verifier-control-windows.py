"""Saved receipt only; one E4 stream, no strategy or economic reconstruction."""
import csv,gzip,hashlib,json
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
OLD=ROOT/'reports/b-50-90-next-20261023'
protocol=json.loads((OUT/'protocol-freeze.json').read_text())
cache=json.loads((OLD/'verifier-E4-risk-cache.json').read_text())
manifest=json.loads((OLD/'runs_manifest.json').read_text())
e4=next(r for r in manifest['runs'] if r['recipe']=='E4')
trace=Path(e4['native_artifact']).parent/'minute-native-settled-receipts.csv.gz'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ns(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())*10**9
def utc(n):return datetime.fromtimestamp(n/1e9,timezone.utc).isoformat()
w={k:{'start_ns':ns(a),'end_exclusive_ns':ns(b),'samples':0,'local_peak':None,'local_max_DD':D(0),'global_window_max_DD':D(0)} for k,(a,b) in protocol['target_windows_UTC'].items()}
h=hashlib.sha256();gp=D('10000');gn=None;rows=0
with gzip.open(trace,'rb') as f:
 def lines():
  for b in f:
   h.update(b)
   yield b.decode()
 for r in csv.DictReader(lines()):
  rows+=1;n=int(r['receipt_ns']);e=D(r['paired_close_equity'])
  if e>gp:gp=e;gn=n
  for a in w.values():
   if a['start_ns']<=n<a['end_exclusive_ns']:
    a['samples']+=1
    if a['local_peak'] is None or e>a['local_peak']:a['local_peak']=e;a['local_peak_ns']=n
    dd=(a['local_peak']-e)/a['local_peak']
    if dd>a['local_max_DD']:
     a['local_max_DD']=dd;a['local_max_endpoint']={'peak_utc':utc(a['local_peak_ns']),'peak_equity':str(a['local_peak']),'trough_utc':utc(n),'trough_equity':str(e)}
    dd=(gp-e)/gp
    if dd>a['global_window_max_DD']:
     a['global_window_max_DD']=dd;a['global_max_endpoint']={'global_peak_utc':utc(gn),'global_peak_equity':str(gp),'trough_utc':utc(n),'trough_equity':str(e)}
assert rows==cache['risk']['receipts']
assert h.hexdigest()==e4['settled_uncompressed_sha256']==cache['risk']['uncompressed_trace_sha256']
compressed=sha(trace);assert compressed==cache['compressed_trace_sha256']
for a in w.values():
 a['local_window_rebased_DD_percent']=str(a.pop('local_max_DD')*100)
 a['continuous_global_peak_DD_inside_window_percent']=str(a.pop('global_window_max_DD')*100)
 a.pop('local_peak');a.pop('local_peak_ns')
controls=[r for r in csv.DictReader((OLD/'comparison.csv').open()) if r['recipe'] in ('S0','E4')]
result={'status':'CONTROL_WINDOWS_READY','scope':'observed native saved receipts only; no strategy rerun or hypothetical equity','protocol_sha256':sha(OUT/'protocol-freeze.json'),'source_pins':{str(p):sha(p) for p in [OLD/'comparison.csv',OLD/'verifier-E4-risk-cache.json',OLD/'runs_manifest.json']},'E4_source_commit':e4['source_commit'],'E4_config_sha256':e4['config_sha256'],'trace':str(trace),'compressed_trace_sha256':compressed,'uncompressed_trace_sha256':h.hexdigest(),'complete_stream_passes_this_study':1,'receipt_rows':rows,'fixed_window_basis':'receipt_ns in half-open UTC window; first included observed equity initializes local window high water; continuous global DD separately retains full prior peak','controls':controls,'windows':w,'E4_full_continuous_global_DD_percent':cache['risk']['global_settled_DD_percent'],'E4_all_seven_excursion_endpoint_histories':cache['risk']['excursions_ge_30percent'],'qualifications':protocol['qualifications'],'signed_asset_funding':'UNKNOWN','baseline_reruns':0}
(OUT/'verifier-control-windows.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'windows':w},indent=2))
