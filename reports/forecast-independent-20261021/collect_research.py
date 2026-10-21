"""Durable receipts for an explicitly named own transient research job."""
import argparse,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('launch',type=Path);a=p.parse_args();receipt=json.loads(a.launch.read_text());unit=receipt['unit'];job=Path(receipt['job'])
if not unit.startswith('cm113-pred02-'):raise ValueError('NOT_OWN_UNIT')
read=subprocess.run(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','Result','-p','ExecMainStatus','-p','MemoryMax','-p','MemorySwapMax','-p','CPUQuotaPerSecUSec','-p','MemoryPeak','-p','CPUUsageNSec'],capture_output=True,text=True).stdout
props=dict(line.split('=',1) for line in read.splitlines() if '=' in line)
if props.get('SubState')=='running':print(json.dumps({'status':'RUNNING','properties':props}));raise SystemExit(0)
report=Path('reports/forecast-independent-20261021/receipts');report.mkdir(exist_ok=True)
for name in ['stdout.txt','stderr.txt','time.txt']:
 path=job/'result'/name
 if path.exists():(report/f'{unit}-{name}').write_bytes(path.read_bytes())
log=subprocess.run(['journalctl','-u',unit,'--no-pager','-n','12','-o','cat'],capture_output=True,text=True).stdout
summary={'unit':unit,'job':str(job),'launch':str(a.launch),'properties':props,'journal_tail':log,'time_receipt':str(report/f'{unit}-time.txt'),'stdout_receipt':str(report/f'{unit}-stdout.txt'),'stderr_receipt':str(report/f'{unit}-stderr.txt')}
result=job/'result/profile/result.json'
if result.exists():summary['profile']=json.loads(result.read_text())
train=job/'result/train/result.json'
if train.exists():summary['train_result']=json.loads(train.read_text())
failure=job/'result/profile/failure.json'
if failure.exists():summary['failure']=json.loads(failure.read_text())
train_failure=job/'result/train/failure.json'
if train_failure.exists():summary['failure']=json.loads(train_failure.read_text())
summary['status']='PASS' if props.get('Result')=='success' and props.get('ExecMainStatus')=='0' and (job/'result/time.txt').exists() and 'Exit status: 0' in (job/'result/time.txt').read_text() else 'INCOMPLETE'
(report/f'{unit}.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
# Stop only this completed own transient unit after durable readback.
subprocess.run(['systemctl','stop',unit],check=True)
