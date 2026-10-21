"""One connected final artifact verification; no fits, inference or test reruns."""
import hashlib,json,time,subprocess
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd
from coinmaster.research.btc_pattern_evaluate import losses,TASKS
r=Path('reports/btc-pattern-pilot-m2-20261021');j=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');prepared=j/'prepared';began=time.monotonic();checked={};hash_cache={}
def sha(p):
 p=Path(p).resolve()
 if str(p) not in hash_cache:
  with p.open('rb') as stream:hash_cache[str(p)]=hashlib.file_digest(stream,'sha256').hexdigest()
 return hash_cache[str(p)]
def expected(p,value):assert sha(p)==value,str(p)
auth=json.loads((r/'coordinator-q-prior-init-market-go.json').read_text())
for p,digest in auth['source_hashes'].items():expected(p,digest)
for p,digest in auth['additional_source_hashes'].items():expected(p,digest)
expected('runtime/coinmaster/research/pattern_q_prior_init.py',auth['source_sha256']);expected(r/'q-prior-init-protocol.json',auth['recipe_protocol_sha256']);expected(r/'protocol.json',auth['protocol_sha256']);expected(prepared/'manifest.json',auth['prepared_manifest_sha256']);expected(j/'q-prior-init-synthetic/completion.json',auth['qa_receipt_sha256']);expected(j/'development/images.npy',auth['image_cache_sha256']);checked['frozen_sources_protocol_QA_image_cache']='PASS'
manifest=json.loads((prepared/'manifest.json').read_text())
for file,row in manifest['artifacts'].items():assert (prepared/file).stat().st_size==row['bytes'];expected(prepared/file,row['sha256'])
checked['all9_prepared_artifact_hashes']='PASS'
jsons=list(r.glob('*.json'));csvs=list(r.glob('*.csv'));helpers=list(r.glob('*.py'))+[Path('runtime/coinmaster/research/pattern_full_es3.py'),Path('runtime/coinmaster/research/pattern_q_prior_init.py'),Path('runtime/tests/test_pattern_full_es3.py'),Path('runtime/tests/test_pattern_q_prior_init.py')]
for p in jsons:json.loads(p.read_text())
for p in csvs:pd.read_csv(p)
for p in helpers:compile(p.read_text(),str(p),'exec')
checked['JSON_CSV_parse_and_helper_compile']=dict(JSON=len(jsons),CSV=len(csvs),compiled=len(helpers))
meta=np.load(prepared/'metadata.npy',mmap_mode='r');labels=dict(np.load(prepared/'labels.npz'));table=pd.read_csv(r/'recipe-comparison-common-IDs.csv');npzN=0;reuseN=0
for recipe,folder in [('ORIGINAL',j/'development'),('METRIC_OFF',j/'quality-variants/METRIC_OFF'),('Q_PRIOR_INIT',j/'q-prior-init-development')]:
 for f in folder.glob('F*/*.npz'):
  z=dict(np.load(f));ids=z['ids'];n=len(ids);assert z['q_raw'].shape==(n,2,3) and z['probabilities'].shape==(n,3);assert meta['observed'][ids].all();assert np.array_equal(z['truth_D'],labels['direction'][ids]);np.testing.assert_array_equal(z['truth_Q'],labels['mfe'][ids,:,0]);np.testing.assert_array_equal(z['truth_Q_upper'],labels['mfe'][ids,:,1]);np.testing.assert_array_equal(z['q_projected'],np.maximum(0,np.sort(z['q_raw'],axis=2)));assert np.isfinite(z['q_raw']).all() and np.isfinite(z['probabilities']).all();assert np.allclose(z['probabilities'].sum(1),1,atol=1e-5);npzN+=1
  if recipe!='ORIGINAL' and f.stem in ['prior','CatBoost','numeric-knn','random-context']:expected(f,sha(j/'development'/f.parent.name/f.name));reuseN+=1
 for method in ['CNN-direct','CNN-knn','prior','CatBoost']:
  groups=[dict(np.load(f/(method+'.npz'))) for f in sorted(folder.glob('F[123]'))];score=np.concatenate([losses(z['probabilities'],z['q_projected'],z['truth_D'],z['truth_Q']) for z in groups]);assert len(score)==8496;row=table[(table.recipe==recipe)&(table.method==method)].iloc[0];np.testing.assert_allclose(row[list(TASKS)].to_numpy(dtype=float),np.nanmean(score,axis=0),atol=1e-12,rtol=0)
checked['NPZ_schema_labels_projection_and_commonID_CSV']=dict(PASS=True,forecast_groups=npzN,exact_reused_control_groups=reuseN,common_origins=8496)
q=pd.read_csv(r/'q-prior-init-fixed-SL-competing-events-and-TP-calibration.csv')
for method in q.method.unique():
 groups=[dict(np.load(f/(method+'.npz'))) for f in sorted((j/'q-prior-init-development').glob('F[123]'))];ids=np.concatenate([z['ids'] for z in groups]);pred=np.concatenate([z['q_projected'] for z in groups]);truth=np.concatenate([z['truth_Q'] for z in groups]);upper=np.concatenate([z['truth_Q_upper'] for z in groups])
 for side,name in enumerate(['long','short']):
  for k,level in enumerate([.2,.5,.8]):
   row=q[(q.method==method)&(q.side==name)&(q['quantile']==level)].iloc[0];target=pred[:,side,k];e=truth[:,side]-target;gross=np.expm1(target*meta['sigma72'][ids]) if side==0 else -np.expm1(-target*meta['sigma72'][ids]);np.testing.assert_allclose([row.TP_before_SL_lower,row.TP_before_SL_upper,row.pinball,row.mean_target_gross_pct],[(truth[:,side]>=target).mean(),(upper[:,side]>=target).mean(),np.maximum(level*e,(level-1)*e).mean(),gross.mean()*100],rtol=0,atol=1e-12)
checked['TP_pinball_hit_bounds_and_signed_price_distance_CSV_vs_NPZ']='PASS'
drift=pd.read_csv(r/'drift-decomposition.csv');assert len(drift)==126;np.testing.assert_allclose(drift.common_delta,drift.common_mix+drift.common_within,rtol=0,atol=1e-12);assert (drift.bootstrap_valid_draws.between(0,1000)).all();bad=drift.bootstrap_valid_draws<800;assert drift.loc[bad,'within_CI_lower'].isna().all();pop=json.loads((r/'drift-populations.json').read_text());assert sum(x['N'] for x in pop)==8496
for x in pop:
 assert x['early_N']+x['late_N']==x['N'];assert abs(x['early_common_coverage']-(x['early_N']-x['early_excluded_N'])/x['early_N'])<1e-12;assert abs(x['late_common_coverage']-(x['late_N']-x['late_excluded_N'])/x['late_N'])<1e-12
checked['Kitagawa_identity_support_counts_and_CI_withholding']='PASS'
for file in ['metric-off-local-artifact-manifest.json','q-prior-init-local-artifact-manifest.json','synthetic-qa-local-artifact-manifest.json']:
 x=json.loads((r/file).read_text())
 for row in x['files']:
  p=Path(row.get('local_path',row.get('path')));assert p.stat().st_size==row['bytes'];expected(p,row['sha256'])
checked['new_local_model_forecast_neighbor_diagnostic_manifests']='PASS'
for file in ['real-shared-gradient-pre-manifest.json','drift-decomposition-pre-manifest.json']:
 x=json.loads((r/file).read_text())
 for p,digest in x.get('checkpoint_sha256',x.get('files',{})).items():expected(p,digest)
checked['preanalysis_checkpoint_data_prediction_hashes']='PASS'
assert len((r/'findings.md').read_text().splitlines())<=150
checked['findings_line_limit']=len((r/'findings.md').read_text().splitlines())
status=subprocess.run(['git','status','--short'],capture_output=True,text=True,check=True).stdout;(r/'bounded-pilot-dirty-list.txt').write_text(status)
ready=[p for p in r.glob('*') if p.is_file() and p.name not in ['bounded-pilot-ready-files.json','bounded-pilot-artifact-QA.json']]+[Path('runtime/coinmaster/research/pattern_full_es3.py'),Path('runtime/coinmaster/research/pattern_q_prior_init.py'),Path('runtime/tests/test_pattern_full_es3.py'),Path('runtime/tests/test_pattern_q_prior_init.py')]
ready_receipt=dict(owner_package_root=str(r.resolve()),files=[dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(ready)],large_caches_not_in_Git=True,root_owns_commit_Project_and_ops=True);(r/'bounded-pilot-ready-files.json').write_text(json.dumps(ready_receipt,indent=2)+'\n')
receipt=dict(status='PASS',checks=checked,wall_seconds=time.monotonic()-began,UTC=datetime.now(timezone.utc).isoformat(),fits=0,optimizer_steps=0,new_predictions=0,CHECK_used=False,previous_focused_tests='16PASS.526s; unchanged training/testsource, not rerun',source_sha256=sha(Path(__file__)),ready_files_receipt_sha256=sha(r/'bounded-pilot-ready-files.json'),training_decision='NO_GO_Q_ONLY_OR_BLIND_REWEIGHTING',economic_goal='TARGET_NOT_MET_UNMET_OR_UNPROVEN',actual_ROI_MaxDD='NOT_EVALUATED_NATIVE0');(r/'bounded-pilot-artifact-QA.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
