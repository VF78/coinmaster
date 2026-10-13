import json
from pathlib import Path
o=Path(__file__).parent
g=json.loads((o/'GO.json').read_text());c=json.loads((o/'setup-contract.json').read_text())
assert g['engine_launch_authorized'] is True
assert g['source_commit']==c['source_commit'] and g['native_mtf_performance_preflight_accepted'] is True
assert g['authorized_variants']==['h1','b1']
assert g['bounded_cache128_source_review_accepted'] is True and g['native_fixture_accepted'] is True
import sys,shutil
job=Path(sys.argv[1]);assert job.name in c['job_order']
assert not (job/'result').exists()
assert not (job/'launch-gate-consumed.json').exists(), 'NO_IMPLICIT_REPEAT'
mem={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines()}
assert mem['MemAvailable']>=700*1024**2, ('LOW_MEMORY_HOLD',mem['MemAvailable'])
assert shutil.disk_usage(job).free>=1024**3,'LOW_DISK_HOLD'
(job/'launch-gate-consumed.json').write_text(json.dumps({'source_commit':c['source_commit'],'attempt':1,'repeat_authorized':False})+'\n')
