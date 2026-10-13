"""Exactly two approved native engines; sequential, guarded, no automatic retry."""
import json,subprocess,time,hashlib,shutil
from pathlib import Path
ROOT=Path('/root/.openclaw/workspace/coinmaster/coinmaster');OUT=Path(__file__).parent
BASE=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')
def run(*args):return subprocess.check_output(args,text=True)
def pilot():return run('systemctl','show','coinmaster-hl-stageg-testnet.service','-p','MainPID','-p','NRestarts','-p','ActiveState')
contract=json.loads((OUT/'setup-contract.json').read_text());assert (OUT/'GO.json').exists();assert json.loads((OUT/'GO.json').read_text())['source_commit']==contract['source_commit']
go=json.loads((OUT/'GO.json').read_text());assert go['engine_launch_authorized'] is True and go['authorized_variants']==['h1','b1'];assert go['native_mtf_performance_preflight_accepted'] is True;assert go['bounded_cache128_source_review_accepted'] is True;assert go['native_fixture_accepted'] is True
run('systemctl','set-property','--runtime','cm113-v3-risk.slice','MemoryMax=650M','MemorySwapMax=0')
for variant in ['h1','b1']:
 job=BASE/('cm113-h1-b1-'+variant+'-routingfix-20261014');unit=job.name+'.service';assert not (job/'result').exists();assert not (job/'engine-launch-attempt.json').exists(),('NO_IMPLICIT_REPEAT',variant)
 mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()};disk=shutil.disk_usage(job).free
 while mem['MemAvailable']<700*1024**2 or disk<1024**3:
  time.sleep(60)
  mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()};disk=shutil.disk_usage(job).free
 assert mem['MemAvailable']>=700*1024**2;assert disk>=1024**3
 (job/'resource-before.json').write_text(json.dumps({'MemAvailable':mem['MemAvailable'],'disk_free':disk})+'\n')
 state=pilot();assert 'MainPID=2009732' in state and 'NRestarts=0' in state and 'ActiveState=active' in state
 (job/'pilot-before.txt').write_text(state);(job/'launched-at.txt').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+'\n')
 (job/'engine-launch-attempt.json').write_text(json.dumps({'variant':variant,'attempt':1,'source_commit':contract['source_commit'],'repeat_authorized':False})+'\n')
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
 summary={'variant':variant,'artifact':str(artifact),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_commit':contract['source_commit'],'exit_code':0,'TOTAL':p['terminal_total'],'native_minute_DD':m['curves']['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'fees':p['native_fees'],'fills':p['fills'],'liquidations':p['liquidation_count'],'terminal_positions':p['terminal_open_positions'],'minute_rows':m['rows'],'unit_journal':journal,'resource_limit':{'shared_and_perjob_MemoryMax':'650M','MemorySwapMax':0,'MemAvailable_min_bytes':700*1024**2,'disk_free_min_bytes':1024**3},'actual_resource_completion_lines':[line for line in journal.splitlines() if 'memory peak' in line or 'Consumed' in line or 'oom' in line.lower()]}
 (job/'native-run-receipt.json').write_text(json.dumps(summary,indent=2)+'\n');print('COMPLETE',json.dumps({k:v for k,v in summary.items() if k!='unit_journal'}),flush=True)
print('ALL_TWO_COMPLETE_NO_EXTRA_ENGINES',flush=True)
