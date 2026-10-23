from pathlib import Path
import json,hashlib,os,subprocess,sys
R=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/system-contract-repair-20261023')
P=json.loads((R/'owner-control-preparation.json').read_text());S=Path(P['source_snapshot']);J=S.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
mp=J/('source-'+P['source_commit'][:7]+'-sha256.json')
print('source_manifest',str(mp),mp.exists())
assert mp.exists()
M=json.loads(mp.read_text());checks={};checks['manifest_hash']=sha(mp)==P['source_manifest_sha256']
for rel,pin in M.items():
 checks['source:'+rel]=sha(S/rel)==pin
 checks['readonly:'+rel]=not bool((S/rel).stat().st_mode & 0o222)
for rel,pin in P['input_pins'].items():checks['input:'+rel]=sha(S/rel if rel.startswith('runtime/') else Path(P['data_root'])/rel)==pin
checks['new_result_namespace']=not Path(P['artifact_dir']).exists()
checks['direct_native']=P['argv'][0].endswith('/runtime/.venv/bin/python') and P['argv'][1:3]==['-m','coinmaster.research.native_baseline']
checks['scrubbed_env']=set(P['env'])=={'PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','TMPDIR','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','NUMEXPR_MAX_THREADS','ARROW_NUM_THREADS','PYTHONUNBUFFERED'}
checks['no_unreviewed_flags']=not any(x in ' '.join(P['argv']) for x in ['residual-recovery','sol-add-budget','btc-causal-repeat'])
checks['exact_expected_config']=hashlib.sha256(json.dumps(json.loads(Path(P['expected_config']).read_text()),sort_keys=True,separators=(',',':')).encode()).hexdigest()==P['expected_config_sha256']
D=json.loads((R/'data-manifest.json').read_text());checks['28_offline_tests']=len(D['tests']['checks'])==28 and all(D['tests']['checks'].values())
for rel,pin in D['files'].items():checks['data_report:'+rel]=sha(R/rel)==pin['sha256']
cmd=[P['argv'][0],'-c','import importlib.metadata,importlib.util,hashlib,json;from pathlib import Path;p=Path(importlib.util.find_spec("nautilus_trader.core.nautilus_pyo3").origin);print(json.dumps({"version":importlib.metadata.version("nautilus_trader"),"native_binary":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))']
x=subprocess.run(cmd,capture_output=True,text=True);print(x.stderr);x.check_returncode();e=json.loads(x.stdout);checks['engine_pin']=e['version']=='1.231.0'
report={'checks':checks,'all_pass':all(checks.values()),'count':len(checks),'engine':e,'source_manifest':str(mp),'data_source_commit':D['source_only_commit'],'full_engine_go':False}
(R/'root-control-preflight.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'all_pass':report['all_pass'],'count':len(checks),'failures':[k for k,v in checks.items() if not v],'engine':e},indent=2))
assert report['all_pass']
