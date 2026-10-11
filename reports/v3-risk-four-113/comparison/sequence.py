"""Exactly four approved native engines; sequential, guarded, no automatic retry."""
import json,subprocess,time,hashlib,shutil
from pathlib import Path
ROOT=Path('/root/.openclaw/workspace/coinmaster/coinmaster');OUT=Path(__file__).parent
BASE=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')
def run(*args):return subprocess.check_output(args,text=True)
def pilot():return run('systemctl','show','coinmaster-hl-stageg-testnet.service','-p','MainPID','-p','NRestarts','-p','ActiveState')
contract=json.loads((OUT/'setup-contract.json').read_text());assert (OUT/'GO.json').exists();assert json.loads((OUT/'GO.json').read_text())['source_commit']==contract['source_commit']
run('systemctl','set-property','--runtime','cm113-v3-risk.slice','MemoryMax=900M','MemorySwapMax=0')
for variant in ['b25','s10_15','r2','t3']:
 job=BASE/('cm113-v3-'+variant+'-20261011');unit=job.name+'.service';assert not (job/'result').exists()
 mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()};disk=shutil.disk_usage(job).free
 assert mem['MemAvailable']>=900*1024**2,('LOW_MEMORY_HOLD',mem['MemAvailable']);assert disk>=1024**3,('LOW_DISK_HOLD',disk)
 (job/'resource-before.json').write_text(json.dumps({'MemAvailable':mem['MemAvailable'],'disk_free':disk})+'\n')
 state=pilot();assert 'MainPID=2009732' in state and 'NRestarts=0' in state and 'ActiveState=active' in state
 (job/'pilot-before.txt').write_text(state);(job/'launched-at.txt').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+'\n')
 print('LAUNCH',variant,run(str(job/'launch-reviewed-only.sh')),flush=True);print(run('systemctl','show',unit,'-p','MainPID','-p','InvocationID'),flush=True)
 tick=0
 while run('systemctl','show',unit,'-p','ActiveState','--value').strip()=='active':
  time.sleep(30);tick+=1
  if tick%6==0:print('PROGRESS',variant,run('systemctl','show',unit,'-p','CPUUsageNSec','-p','MemoryPeak').strip(),flush=True)
 journal=run('journalctl','-u',unit,'--no-pager');(job/'unit-journal.txt').write_text(journal);assert 'Deactivated successfully' in journal,('ACTUAL_ENGINE_FAILED_NO_RETRY',variant)
 arts=[p for p in (job/'result').glob('*.json') if p.name!='minute-risk-summary.json'];assert len(arts)==1,arts
 artifact=arts[0];p=json.loads(artifact.read_text());m=json.loads((job/'result/minute-risk-summary.json').read_text())
 assert p['streaming']['processed_rows_per_source']==1051200 and m['rows']==3153600
 assert m['conditional_upper_to_later_lower_bound']['samples']==1051200
 state=pilot();assert 'MainPID=2009732' in state and 'NRestarts=0' in state
 (job/'pilot-after.txt').write_text(state);hashes=json.loads((job/'immutable-source-hashes.json').read_text());assert all(hashlib.sha256((job/'source'/name).read_bytes()).hexdigest()==h for name,h in hashes.items());run('sha256sum','-c',str(job/'source-input-hashes.sha256'))
 summary={'variant':variant,'artifact':str(artifact),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_commit':contract['source_commit'],'exit_code':0,'TOTAL':p['terminal_total'],'native_minute_DD':m['curves']['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'fees':p['native_fees'],'fills':p['fills'],'liquidations':p['liquidation_count'],'terminal_positions':p['terminal_open_positions'],'minute_rows':m['rows'],'unit_journal':journal}
 (job/'native-run-receipt.json').write_text(json.dumps(summary,indent=2)+'\n');print('COMPLETE',json.dumps({k:v for k,v in summary.items() if k!='unit_journal'}),flush=True)
print('ALL_FOUR_COMPLETE_NO_EXTRA_ENGINES',flush=True)
