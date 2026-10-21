"""Read-checkpoint/arithmetic and tiny-file evaluator probes; zero training/inference."""
import json,time,hashlib,math,warnings
from pathlib import Path
from types import SimpleNamespace
import numpy as np,pandas as pd,torch
from catboost import CatBoostClassifier,CatBoostRegressor
from coinmaster.research.btc_pattern_train import Data,normalize,scales
from coinmaster.research.btc_pattern_data import folds,ms,DAY,HOUR
from coinmaster.research.btc_pattern_models import TCN,CNN,Projection,predict_loss
from coinmaster.research.btc_pattern_evaluate import evaluate,losses,paired_ci
HERE=Path(__file__).resolve().parent
ROOT=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');began=time.monotonic();torch.set_num_threads(4);torch.set_num_interop_threads(1);data=Data(ROOT/'prepared');records=[];catboost=[];ambiguity=[]
for f in folds(data.meta):
 for role in ['subfit','early_stop','refit','outer']:ambiguity.append(dict(fold=f['name'],role=role,N=len(f[role]),ambiguous_D=int((data.d[f[role]]<0).sum())))
 for kind in ['TCN','Kronos','CNN']:
  states={}
  for role,part,cutoff in [('es','subfit',f['inner_cutoff']),('refit','refit',f['fit_cutoff'])]:
   file=ROOT/'development'/f['name']/f'{kind}-{role}.pt';state=torch.load(file,map_location='cpu',weights_only=False);ids=f[part];assert np.array_equal(state['fit_ids'],ids);assert data.meta['label_end'][ids].max()<=cutoff;cm,cs=normalize(data.c,ids);np.testing.assert_allclose(cm,state['context_mean'],rtol=1e-6);np.testing.assert_allclose(cs,state['context_std'],rtol=1e-6);ys,qs,tau=scales(data,ids);np.testing.assert_allclose(state['q_scales'],qs,rtol=1e-6);np.testing.assert_allclose(state['signature_scales'],ys,rtol=1e-6);assert abs(state['tau']-tau)<1e-6
   receipt=json.loads(file.with_suffix('.receipt.json').read_text());history=json.loads(file.with_suffix('.curve.json').read_text());assert state['epochs']==receipt['selected_epochs'];best=float('inf');selected=None
   if role=='es':
    for row in history:
     if row['early_stop_predict']<best-1e-8:best=row['early_stop_predict'];selected=row['epoch']
    assert selected==state['epochs']
   torch.manual_seed(7);initial={'TCN':TCN,'CNN':CNN,'Kronos':Projection}[kind]();delta=math.sqrt(sum(float(((state['weights'][k]-v)**2).sum()) for k,v in initial.state_dict().items()));assert delta>0
   records.append(dict(fold=f['name'],kind=kind,role=role,fit_N=len(ids),epochs=state['epochs'],selected_curve_epoch=selected,context_scales_and_target_scales_exact=True,weight_L2_delta_from_seed7_initial=delta,last_batch_N=len(ids)%(64 if kind=='CNN' else 128),checkpoint_sha256=hashlib.file_digest(open(file,'rb'),'sha256').hexdigest()));states[role]=state
  assert any(not torch.equal(states['es']['weights'][k],states['refit']['weights'][k]) for k in states['es']['weights'])
 for role in ['es','refit']:
  receipt=json.loads((ROOT/'development'/f['name']/f'catboost-{role}.receipt.json').read_text())
  for head in range(3):
   model=CatBoostClassifier() if head==0 else CatBoostRegressor();model.load_model(str(ROOT/'development'/f['name']/f'catboost-{role}-head{head}.cbm'));assert model.tree_count_==receipt['iterations'][head]
   if head==0:np.testing.assert_array_equal(model.classes_,[0,1,2])
   else:assert 'alpha=0.2,0.5,0.8' in model.get_all_params()['loss_function']
   catboost.append(dict(fold=f['name'],role=role,head=head,tree_count=model.tree_count_,loss=model.get_all_params()['loss_function']))
# Tiny tensor arithmetic only: no models/optimizer, exact independent loss formula.
logits=torch.tensor([[2.,0.,-1.],[0.,1.,0.],[0.,0.,0.]]);d=torch.tensor([0,-1,2]);q=torch.tensor([[[.1,.5,.9],[.2,.6,1.]],[[.3,.7,1.1],[.1,.4,.8]],[[0.,.1,.2],[.2,.5,.9]]]);y=torch.tensor([[.4,.7],[.8,.2],[.1,.6]]);scale=torch.tensor([.2,.5]);total,dl,ql=predict_loss(logits,q,d,y,scale);p=torch.softmax(logits,1).numpy();manualD=float((-np.log(p[[0,2],[0,2]])).mean());e=y.numpy()[:,:,None]-q.numpy();manualQ=float((np.maximum(np.array([.2,.5,.8])*e,(np.array([.2,.5,.8])-1)*e)/scale.numpy()[None,:,None]).mean());assert abs(float(dl)-manualD)<1e-6 and abs(float(ql)-manualQ)<1e-6
# Deliberate malformed evaluator inputs, synthetic files ONLY, no saved-model inference.
fixture=HERE/'fixtures';fixture.mkdir(exist_ok=True);N=36;meta=np.zeros(N,dtype=[('origin','i8'),('label_end','i8')]);starts=[ms('2025-01-01'),ms('2025-07-01'),ms('2026-01-01')]
for fi,start in enumerate(starts):meta['origin'][fi*12:(fi+1)*12]=start+np.arange(12)*3*DAY;meta['label_end'][fi*12:(fi+1)*12]=meta['origin'][fi*12:(fi+1)*12]+72*HOUR
prepared=fixture/'prepared';prepared.mkdir(exist_ok=True);np.save(prepared/'metadata.npy',meta) # intentionally NO labels/manifest/completion: evaluator never requires them.
results={}
for case in ['missing_candidate_F3','inconsistent_saved_truth','inconsistent_saved_truth_shifted']:
 inputs=fixture/case;inputs.mkdir(exist_ok=True)
 for fi,name in enumerate(['F1','F2','F3']):
  folder=inputs/name;folder.mkdir(exist_ok=True);ids=np.arange(fi*12,(fi+1)*12);truth=np.arange(12)%3;target=np.ones((12,2),dtype='float32')
  for method in ['prior','CatBoost','numeric-knn','random-context','TCN-direct']:
   if case=='missing_candidate_F3' and name=='F3' and method=='TCN-direct':continue
   candidate=method=='TCN-direct';savedtruth=(np.zeros(12,int) if case=='inconsistent_saved_truth' else np.roll(truth,1)) if candidate and case.startswith('inconsistent_saved_truth') else truth;pred=np.full((12,3),1/3)
   if candidate:
    pred=np.full((12,3),.01);pred[np.arange(12),savedtruth]=.98
   raw=np.ones((12,2,3))*(1 if candidate else 2);np.savez(folder/(method+'.npz'),ids=ids,probabilities=pred,q_raw=raw,q_projected=raw,support=np.zeros(12,int),truth_D=savedtruth,truth_Q=target,truth_Q_upper=target)
 try:
  with warnings.catch_warnings():
   warnings.simplefilter('ignore')
   output=fixture/(case+'-evaluation');existing=output/'development-gates.json'
   g=json.loads(existing.read_text()) if existing.exists() else evaluate(SimpleNamespace(prepared=prepared,input=inputs,output=fixture/(case+'-evaluation-resumed') if output.exists() else output,protocol=Path('reports/btc-pattern-pilot-m2-20261021/protocol.json')))
  results[case]=dict(status=g['status'],shortlist=g['shortlist'],D=g['tasks']['TCN-direct']['D'],missing_prepared_labels_accepted=True)
  assert g['tasks']['TCN-direct']['D']['status']=='PREDICTIVE_PASS'
 except ValueError as exc:
  assert case=='inconsistent_saved_truth' and 'JSON compliant' in str(exc)
  results[case]=dict(exception=type(exc).__name__,message=str(exc),cause='one-classAUROCnan reachesstrictJSON instead ofNone')
# Actual historical files: completeness and truth checks independently of evaluator.
actual_groups=0
for run in [ROOT/'development',ROOT/'quality-variants/METRIC_OFF',ROOT/'q-prior-init-development']:
 names=None
 for f in folds(data.meta):
  found={x.stem for x in (run/f['name']).glob('*.npz')};names=found if names is None else names;assert found==names
  for file in (run/f['name']).glob('*.npz'):
   z=dict(np.load(file));ids=z['ids'];np.testing.assert_array_equal(ids,f['outer']);np.testing.assert_array_equal(z['truth_D'],data.d[ids]);np.testing.assert_array_equal(z['truth_Q'],data.y[ids]);np.testing.assert_array_equal(z['truth_Q_upper'],data.upper[ids]);np.testing.assert_array_equal(z['q_projected'],np.maximum(0,np.sort(z['q_raw'],axis=2)));actual_groups+=1
aggregation=dict(curve_unweighted_example=float(np.mean([0.,10.])),curve_row_weighted_example=float(np.average([0.,10.],weights=[64,1])),masked_ES_implemented_D=float(np.average([10.,0.],weights=[2,2])),masked_ES_correct_valid_D=10/3,CNN_F1_refit_last8_report_weight=1/80,CNN_F1_refit_last8_row_weight=8/5064)
# Independent bootstrap reconstruction verifies loss/origin pairing, not statistical validity.
origins=np.arange(64)*DAY;delta=np.sin(np.arange(64));ci=paired_ci(delta,origins);blocks=origins//(14*DAY);unique=np.unique(blocks);rng=np.random.default_rng(7);which=rng.integers(0,len(unique),(1000,len(unique)));boot=np.array([np.concatenate([delta[blocks==unique[k]] for k in sample]).mean() for sample in which]);assert abs(ci['lower']-np.quantile(boot,.025))<1e-12 and abs(ci['upper']-np.quantile(boot,.975))<1e-12
pd.DataFrame(records).to_csv(HERE/'checkpoint-checks.csv',index=False);pd.DataFrame(catboost).to_csv(HERE/'catboost-checks.csv',index=False);pd.DataFrame(ambiguity).to_csv(HERE/'ambiguity-counts.csv',index=False);(HERE/'evaluator-guard-repro.json').write_text(json.dumps(results,indent=2)+'\n');(HERE/'aggregation-repro.json').write_text(json.dumps(aggregation,indent=2)+'\n');receipt=dict(status='COMPLETE_AUDIT',wall_seconds=time.monotonic()-began,fit_calls=0,optimizer_steps=0,saved_model_inference_calls=0,new_forecasts=0,CHECK_used=False,baseline_checkpoints_checked=len(records),CatBoost_models_checked=len(catboost),historical_forecast_groups_truth_and_fold_verified=actual_groups,manual_loss=dict(D=float(dl),Q=float(ql),matches_numpy=True),all_actual_ES_D_ambiguity=sum(x['ambiguous_D'] for x in ambiguity if x['role']=='early_stop'),bootstrap_arithmetic_matches=True,core_edited=False);assert receipt['wall_seconds']<180;(HERE/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
