"""Explicit staged CLI: profile, TRAIN screen/fit, then separately sealed CHECK."""
from __future__ import annotations
import argparse,json,pickle,resource,time,traceback,os,struct,zlib
from pathlib import Path
import numpy as np
from .forecast_independent_data import Dataset,PROTOCOL_SHA,ms,sha,write_json,DAY,MINUTE
from .forecast_independent_models import Analog,Budget,Calibrator,Learned,PhasedRDST,project,scores,softmax,pinball

def emit(obj):print(json.dumps(obj,allow_nan=False),flush=True)
def average(predictions):
 q=np.mean([p[0] for p in predictions],axis=0);p=np.mean([softmax(v[1]) for v in predictions],axis=0)
 return project(q),np.log(np.maximum(p,1e-12))
def aggregate_scores(records):
 n=sum(r['score']['n'] for r in records);return {k:sum(r['score'][k]*r['score']['n'] for r in records)/n for k in ['lower_pinball','upper_pinball','direction_logloss','direction_brier','direction_accuracy']}
def ordering(score,view,config):return (score['lower_pinball'],score['direction_logloss'],int(view.split('x')[0]),int(view.split('x')[1]),config)
def _predict(model,ids,budget):return model.predict(ids,budget) if isinstance(model,(Analog,PhasedRDST)) else model.predict(ids)
def _fit(ds,family,view,config,train,val,cache,budget,seed=7,epochs=None,progress=None,profile_only=False):
 if family=='stumpy':return Analog(ds,view,int(config)).fit(train)
 if family=='rdst':return PhasedRDST(ds,view,float(config),seed,cache).fit(train,val,budget,epochs,progress,profile_only)
 return Learned(ds,view,family,float(config),seed,cache).fit(train,val,budget,epochs,progress,profile_only)
def _save_model(model,path):
 if isinstance(model,PhasedRDST):
  with Path(path).open('wb') as f:pickle.dump(model.artifact(),f,protocol=5)
  return
 obj={'kind':'stumpy','view':model.view,'k':model.k,'library':model.library,'train':model.train,'prior_q':model.prior_q,'prior_p':model.prior_p} if isinstance(model,Analog) else {'kind':'learned','state':model.artifact()}
 with Path(path).open('wb') as f:pickle.dump(obj,f,protocol=5)
def _load_model(ds,path,cache):
 with Path(path).open('rb') as f:obj=pickle.load(f)
 if obj['kind']=='learned':return Learned.restore(ds,obj['state'],cache)
 if obj['kind']=='rdst-phased':return PhasedRDST.restore(ds,obj,cache)
 model=Analog(ds,obj['view'],obj['k']);model.library=obj['library'];model.train=obj['train'];model.prior_q=obj['prior_q'];model.prior_p=obj['prior_p'];return model

def profile(ds,family,view,output,budget):
 fold=ds.lock['inner_folds'][0];train=ds.rows(ds.lock['train'][0],fold['fit_end']);val=ds.rows(fold['fit_end'],fold['validation_end'])
 # Uniform timestamps, independent of labels; profile is not a final trained recipe.
 train=train[np.linspace(0,len(train)-1,min(256,len(train)),dtype=int)];val=val[np.linspace(0,len(val)-1,min(128,len(val)),dtype=int)]
 config=20 if family=='stumpy' else .001;before=Budget.cpu()
 model=_fit(ds,family,view,config,train,val,output/'cache',budget,epochs=1,progress=lambda o:emit({'profile_epoch':o}),profile_only=True)
 q,logits=_predict(model,val,budget)
 if q.shape!=(len(val),2,2,3) or logits.shape!=(len(val),3) or not np.isfinite(q).all() or not np.isfinite(logits).all():raise ValueError('PROFILE_INVALID_OUTPUT_CONTRACT')
 # These TRAIN-only profile predictions are retained but never used for recipe selection.
 np.savez(output/'profile-predictions.npz',ids=val,q=q,logits=logits)
 if not isinstance(model,Analog):model.release_training_cache()
 return {'status':'PROFILE_PASS_NOT_RECIPE_SELECTION','family':family,'view':view,'train_rows':len(train),'validation_rows':len(val),'profile_cpu_seconds':Budget.cpu()-before,'maxrss_bytes':max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)*1024,'output_shapes':[list(q.shape),list(logits.shape)],'profile_only':True,'measurements':getattr(model,'measurements',{}),'head_features':None if isinstance(model,Analog) or family=='cnn' else model.head_features if isinstance(model,PhasedRDST) else len(model.scale.mean)}

def fold_candidates(ds,family,views,configs,output,budget):
 records=[]
 for view in views:
  for config in configs:
   folds=[]
   for fi,fold in enumerate(ds.lock['inner_folds']):
    p=output/f'{view}-{config}-fold{fi}';p.mkdir();train=ds.rows(ds.lock['train'][0],fold['fit_end']);val=ds.rows(fold['fit_end'],fold['validation_end'])
    write_json(p/'intent.json',{'family':family,'view':view,'config':config,'train_ids_sha256':__import__('hashlib').sha256(train.tobytes()).hexdigest(),'validation_ids_sha256':__import__('hashlib').sha256(val.tobytes()).hexdigest(),'fit_end':fold['fit_end'],'validation_end':fold['validation_end']})
    def progress(obj):write_json(p/'progress.json',obj);emit({'family':family,'view':view,'config':config,'fold':fi,**obj})
    model=_fit(ds,family,view,config,train,val,p/'cache',budget,progress=progress);q,logits=_predict(model,val,budget);score=scores(q,logits,ds.targets[val],ds.direction[val]);np.savez(p/'predictions.npz',ids=val,q=q,logits=logits)
    record={'fold':fi,'score':score,'best_epoch':None if isinstance(model,Analog) else model.best_epoch,'predictions_sha256':sha(p/'predictions.npz')}
    if isinstance(model,Analog):record['catalogue']=model.catalogue
    else:model.release_training_cache()
    write_json(p/'result.json',record);folds.append(record);del model
   record={'view':view,'config':config,'folds':folds,'score':aggregate_scores(folds)};records.append(record);write_json(output/'candidates-progress.json',records)
 return records

def screen(ds,output,budget):
 records=fold_candidates(ds,'control',ds.views,[.001],output,budget);ranked=sorted(records,key=lambda r:ordering(r['score'],r['view'],r['config']));alternate=next(r for r in ranked if r['view']!='60x20')
 return {'status':'TRAIN_ONLY_SCREEN_COMPLETE','primary':'60x20','alternate':alternate['view'],'method_views':['60x20',alternate['view']],'control_best':ranked[0],'records':records,'no_CHECK_read':True}

def fit_family(ds,family,selection_path,output,budget):
 selection=json.loads(Path(selection_path).read_text())
 if selection.get('status')!='TRAIN_ONLY_SCREEN_COMPLETE' or selection.get('protocol_sha256')!=PROTOCOL_SHA or selection.get('dataset_manifest_sha256')!=sha(ds.path/'manifest.json'):raise ValueError('SCREEN_IDENTITY_MISMATCH')
 if family=='control':records=[selection['control_best']]
 else:
  configs=[20,50] if family=='stumpy' else [.0001,.001] if family in ('minirocket','rdst') else [.0001]
  records=fold_candidates(ds,family,selection['method_views'],configs,output,budget)
 winner=min(records,key=lambda r:ordering(r['score'],r['view'],r['config']));view=winner['view'];config=winner['config'];final_epochs=None if family=='stumpy' else max(5 if family=='cnn' else 10,int(np.median([r['best_epoch'] for r in winner['folds']])))
 final_train=ds.rows(ds.lock['train'][0],ds.lock['final_fit_end']);cal=ds.rows(ds.lock['final_fit_end'],ds.lock['calibration_end']);seeds=[7,42] if family=='cnn' else [7];cal_predictions=[];artifacts=[]
 for seed in seeds:
  p=output/f'final-seed{seed}';p.mkdir();model=_fit(ds,family,view,config,final_train,None,p/'cache',budget,seed,final_epochs,lambda obj:emit({'family':family,'final_seed':seed,**obj}))
  if not isinstance(model,Analog):model.release_training_cache()
  q,logits=_predict(model,cal,budget);cal_predictions.append((q,logits));path=p/'model.pkl';_save_model(model,path);artifacts.append({'path':str(path.relative_to(output)),'sha256':sha(path)});del model
 q,logits=average(cal_predictions);calibrator=Calibrator().fit(q,logits,ds.targets[cal],ds.direction[cal]);cq,cl=calibrator.apply(q,logits);np.savez(output/'calibration-predictions.npz',ids=cal,q=q,logits=logits,calibrated_q=cq,calibrated_logits=cl)
 with (output/'calibrator.pkl').open('wb') as f:pickle.dump(calibrator,f,protocol=5)
 recipe={'status':'SEALED_READY_FOR_SEPARATE_CHECK','family':family,'view':view,'config':config,'final_epochs':final_epochs,'seeds':seeds,'winning_TRAIN_inner_score':winner['score'],'winning_inner_folds':winner['folds'],'final_fit_rows':len(final_train),'calibration_rows':len(cal),'calibration_raw':scores(q,logits,ds.targets[cal],ds.direction[cal]),'calibration_adjusted':scores(cq,cl,ds.targets[cal],ds.direction[cal]),'models':artifacts,'calibrator_sha256':sha(output/'calibrator.pkl'),'calibration_predictions_sha256':sha(output/'calibration-predictions.npz'),'selection_sha256':sha(selection_path),'protocol_sha256':PROTOCOL_SHA,'dataset_manifest_sha256':sha(ds.path/'manifest.json'),'source_sha256':source_hashes(),'no_CHECK_read':True}
 write_json(output/'seal.json',recipe);return recipe

def source_hashes():return {p.name:sha(p) for p in Path(__file__).parent.glob('forecast_independent_*.py')}
def detailed_metrics(ds,ids,q,logits):
 y=ds.targets[ids];d=ds.direction[ids];result={'all':scores(q,logits,y,d),'groups':{},'coverage':{},'direction_prior':{}}
 months=np.array([datetime_month(t) for t in ds.meta['origin'][ids]])
 for a in [0,1]:
  for month in ['ALL',*sorted(set(months))]:
   mask=ds.meta['asset'][ids]==a
   if month!='ALL':mask&=months==month
   if not mask.any():continue
   error=pinball(q[mask],y[mask]);result['groups'][f'{a}:{month}']={**scores(q[mask],logits[mask],y[mask],d[mask]),'pinball_bound_side_q':error.mean(0).tolist(),'exceedance_bound_side_q':(y[mask,:,:,None]>=q[mask]).mean(0).tolist(),'mean_sigma_target_distance':q[mask].mean(0).tolist()}
 return result

def datetime_month(t):return np.datetime_as_string(np.datetime64(int(t),'ms'),unit='M')
def actionable(ds,ids,q,logits,support=None):
 p=softmax(logits);direction=p.argmax(1);side=np.where(direction==0,1,-1);index=np.where(direction==0,0,1);levels=q[np.arange(len(ids)),0,index]*ds.meta['sigma'][ids,None]
 okay=(direction!=2)&(p.max(1)>=.5)&(levels[:,0]>.0011)&(levels>0).all(1)&(np.diff(levels,axis=1)>=1e-6).all(1)
 if support is not None:okay&=support>=10
 return okay,side,index,levels

def touch_details(ds,ids,q,logits,support=None):
 okay,side,side_index,distances=actionable(ds,ids,q,logits,support);result=[];minutes={}
 for at,row in enumerate(ids):
  if not okay[at]:continue
  asset=int(ds.meta['asset'][row]);symbol=('BTCUSDT','SOLUSDT')[asset]
  if asset not in minutes:minutes[asset]=np.load(ds.path/f'minutes-{symbol}.npy',mmap_mode='r')
  entry=int(ds.meta['origin'][row])+MINUTE;start=(entry-ds.manifest['minute_start_ms'])//MINUTE;v=minutes[asset][start:start+1440];e=float(ds.meta['entry'][row]);sigma=float(ds.meta['sigma'][row]);s=int(side[at]);stop=e*np.exp(-s*sigma);stopmask=v[:,2]<=stop if s==1 else v[:,1]>=stop;si=int(np.flatnonzero(stopmask)[0]) if stopmask.any() else 1440
  gap=si<1440 and (v[si,0]<=stop if s==1 else v[si,0]>=stop)
  times=[]
  for target in e*np.exp(s*distances[at]):
   hits=v[:,1]>=target if s==1 else v[:,2]<=target;found=np.flatnonzero(hits);ti=int(found[0]) if len(found) else 1440
   opened_target=si<1440 and (v[si,0]>=target if s==1 else v[si,0]<=target)
   lower=ti<si or (ti==si and si<1440 and not gap and opened_target);upper=ti<si or (ti==si and si<1440 and not gap)
   times.append({'lower_hit':bool(lower),'upper_hit':bool(upper),'lower_time_minutes':int(ti+1) if lower else None,'upper_time_minutes':int(ti+1) if upper else None})
  result.append({'row':int(row),'asset':symbol,'origin_ms':int(ds.meta['origin'][row]),'entry_ms':entry,'expiry_ms':int(ds.meta['expiry'][row]),'entry':e,'reference':float(ds.meta['reference'][row]),'side':s,'reference_TP':(ds.meta['reference'][row]*np.exp(s*distances[at])).tolist(),'entry_TP':(e*np.exp(s*distances[at])).tolist(),'upper_entry_TP':(e*np.exp(s*q[at,1,side_index[at]]*sigma)).tolist(),'upper_reference_TP':(ds.meta['reference'][row]*np.exp(s*q[at,1,side_index[at]]*sigma)).tolist(),'reference_SL':float(ds.meta['reference'][row]*np.exp(-s*sigma)),'entry_SL':float(stop),'touch':times,'entry_gap_log':float(np.log(e/ds.meta['reference'][row]))})
 return result,okay

def paired_blocks(ds,ids,q,logits,baseline_q,baseline_logits):
 # All comparisons on exactly the same origin/asset IDs; paired14day resampling.
 delta=pinball(q,ds.targets[ids])[:,0].mean((1,2))-pinball(baseline_q,ds.targets[ids])[:,0].mean((1,2));blocks=(ds.meta['origin'][ids]-ms(ds.lock['check'][0]))//(14*DAY);unique=np.unique(blocks);sums=np.array([delta[blocks==b].sum() for b in unique]);counts=np.array([(blocks==b).sum() for b in unique]);rng=np.random.default_rng(7);est=[]
 for i in range(1000):pick=rng.integers(0,len(unique),len(unique));est.append(sums[pick].sum()/counts[pick].sum())
 return {'mean_lower_pinball_difference':float(delta.mean()),'paired14day_CI95':np.quantile(est,[.025,.975]).tolist(),'blocks':len(unique),'bootstrap_replicates':1000,'seed':7}

def check_identity(seal_path,dataset):
 seal_path=Path(seal_path);seal=json.loads(seal_path.read_text());base=seal_path.parent
 if seal['status']!='SEALED_READY_FOR_SEPARATE_CHECK' or seal['protocol_sha256']!=PROTOCOL_SHA or seal['dataset_manifest_sha256']!=sha(Path(dataset)/'manifest.json') or seal['source_sha256']!=source_hashes():raise ValueError('SEALED_RECIPE_OR_SOURCE_IDENTITY_DRIFT')
 for record in seal['models']:
  if sha(base/record['path'])!=record['sha256']:raise ValueError('SEALED_MODEL_HASH_DRIFT')
 if sha(base/'calibrator.pkl')!=seal['calibrator_sha256']:raise ValueError('SEALED_CALIBRATOR_HASH_DRIFT')
 return seal

def validate_registry(path,dataset):
 if path is None:raise ValueError('ALL_FIVE_METHOD_SEALS_REQUIRED_BEFORE_CHECK')
 path=Path(path);records=json.loads(path.read_text())
 if set(records)!={'control','stumpy','minirocket','rdst','cnn'}:raise ValueError('ALL_FIVE_METHOD_SEALS_REQUIRED_BEFORE_CHECK')
 for family,record in records.items():
  seal_path=Path(record['path'])
  if not seal_path.is_absolute():seal_path=path.parent/seal_path
  if sha(seal_path)!=record['sha256']:raise ValueError('METHOD_SEAL_REGISTRY_MISMATCH')
  if check_identity(seal_path,dataset)['family']!=family:raise ValueError('METHOD_SEAL_REGISTRY_MISMATCH')
 return sha(path)

def acquire_check_lock(seal_path,output):
 path=Path(seal_path).parent/'CHECK_EVALUATION_LOCK.json'
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump({'seal_sha256':sha(seal_path),'output':str(output),'pid':os.getpid(),'status':'CHECK_ATTEMPT_NO_AUTOMATIC_RETRY'},f)

def png(path,image):
 image=np.rint(np.clip(image,0,1)*255).astype(np.uint8)
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 body=b''.join(b'\x00'+row.tobytes() for row in image)
 Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',image.shape[1],image.shape[0],8,0,0,0,0))+chunk(b'IDAT',zlib.compress(body))+chunk(b'IEND',b''))

def evaluate(ds,seal_path,output,budget,baseline_path=None):
 seal_path=Path(seal_path);seal=json.loads(seal_path.read_text());base=seal_path.parent
 if seal['status']!='SEALED_READY_FOR_SEPARATE_CHECK' or seal['protocol_sha256']!=PROTOCOL_SHA or seal['dataset_manifest_sha256']!=sha(ds.path/'manifest.json') or seal['source_sha256']!=source_hashes():raise ValueError('SEALED_RECIPE_OR_SOURCE_IDENTITY_DRIFT')
 for record in seal['models']:
  if sha(base/record['path'])!=record['sha256']:raise ValueError('SEALED_MODEL_HASH_DRIFT')
 if sha(base/'calibrator.pkl')!=seal['calibrator_sha256']:raise ValueError('SEALED_CALIBRATOR_HASH_DRIFT')
 ids=ds.rows(*ds.lock['check']);all_check=np.flatnonzero(ds.meta['origin']>=ms(ds.lock['check'][0]));predictions=[];support=None;catalogue=[]
 for record in seal['models']:
  model=_load_model(ds,base/record['path'],output/'cache');predictions.append(_predict(model,all_check,budget))
  if isinstance(model,Analog):support=model.support.copy();catalogue=model.catalogue
  del model
 all_q,all_logits=average(predictions)
 observed=np.searchsorted(all_check,ids)
 if support is not None:all_support=support.copy();support=support[observed]
 else:all_support=None
 with (base/'calibrator.pkl').open('rb') as f:calibrator=pickle.load(f)
 all_cq,all_cl=calibrator.apply(all_q,all_logits);np.savez(output/'predictions-all-origins.npz',ids=all_check,q=all_q,logits=all_logits,calibrated_q=all_cq,calibrated_logits=all_cl,observed=ds.meta['observed'][all_check]);q=all_q[observed];logits=all_logits[observed];cq=all_cq[observed];cl=all_cl[observed];np.savez(output/'predictions.npz',ids=ids,q=q,logits=logits,calibrated_q=cq,calibrated_logits=cl)
 details,okay=touch_details(ds,ids,cq,cl,support);write_json(output/'actionable-forecasts.json',details)
 censored=[];all_ok,all_side,all_index,all_distance=actionable(ds,all_check,all_cq,all_cl,all_support)
 for pos,row in enumerate(all_check):
  if ds.meta['observed'][row]:continue
  sig=float(ds.meta['sigma'][row]);ref=float(ds.meta['reference'][row]);e=float(ds.meta['entry'][row]);side=int(all_side[pos]);offset=all_distance[pos]
  censored.append({'row':int(row),'asset':int(ds.meta['asset'][row]),'origin_ms':int(ds.meta['origin'][row]),'entry_ms':int(ds.meta['origin'][row])+MINUTE,'expiry_ms':int(ds.meta['expiry'][row]),'status':'CENSORED_NOT_ZERO_LABEL','actionable_forecast':bool(all_ok[pos]),'side':side,'probabilities':softmax(all_cl[pos:pos+1])[0].tolist(),'reference_TP':(ref*np.exp(side*offset)).tolist(),'entry_TP':(e*np.exp(side*offset)).tolist(),'reference_SL':float(ref*np.exp(-side*sig)),'entry_SL':float(e*np.exp(-side*sig))})
 write_json(output/'censored-forecasts.json',censored)
 train=ds.rows(ds.lock['train'][0],ds.lock['final_fit_end']);prior_q=np.quantile(ds.targets[train], [.2,.5,.8],axis=0).transpose(1,2,0);prior_p=np.bincount(ds.direction[train],minlength=3)/len(train);bq=np.broadcast_to(prior_q,(len(ids),2,2,3)).copy();bl=np.broadcast_to(np.log(np.maximum(prior_p,1e-12)),(len(ids),3)).copy()
 result={'status':'ONE_FROZEN_CHECK_EVALUATION_COMPLETE','family':seal['family'],'seal_sha256':sha(seal_path),'raw':detailed_metrics(ds,ids,q,logits),'calibrated':detailed_metrics(ds,ids,cq,cl),'prefix_prior':detailed_metrics(ds,ids,bq,bl),'vs_prefix_prior':paired_blocks(ds,ids,cq,cl,bq,bl),'coverage':{'fully_observed':len(ids),'censored_origins':len(all_check)-len(ids),'actionable':int(okay.sum()),'abstain':int((~okay).sum()),'label_ambiguity_rows':int((ds.targets[ids,1]>ds.targets[ids,0]+1e-12).any(1).sum())},'catalogue':catalogue,'predictions_sha256':sha(output/'predictions.npz')}
 if baseline_path:
  with np.load(baseline_path) as b:
   if not np.array_equal(ids,b['ids']):raise ValueError('BASELINE_CHECK_IDS_MISMATCH')
   result['vs_raw_control']=paired_blocks(ds,ids,cq,cl,b['calibrated_q'],b['calibrated_logits'])
 # Deterministic first actionable per asset, never selected by future success.
 examples=[]
 for symbol in ('BTCUSDT','SOLUSDT'):
  first=next((v for v in details if v['asset']==symbol),None)
  if first is not None:
   row=first['row'];x,_=ds.features([row],seal['view']);from .forecast_independent_models import render
   image=render(x[0]);png(output/f'example-{symbol}.png',image);examples.append(first)
   minute_name=f'minutes-{symbol}.npy';minute=np.load(ds.path/minute_name,mmap_mode='r');entry=first['entry_ms'];offset=(entry-ds.manifest['minute_start_ms'])//MINUTE;path=minute[offset:offset+1440,:4]
   if len(path)!=1440:raise ValueError('POSTHOC_EXAMPLE_REQUIRES_FULL_PATH')
   actual={'status':'POSTHOC_ACTUAL_PATH_NEVER_FEATURE','row':row,'asset':symbol,'origin_ms':first['origin_ms'],'entry_ms':entry,'expiry_ms':first['expiry_ms'],'reference':first['reference'],'entry':first['entry'],'side':first['side'],'reference_SL':first['reference_SL'],'entry_SL':first['entry_SL'],'reference_TP':first['reference_TP'],'entry_TP':first['entry_TP'],'minute_UTC_epoch_ms':(entry+np.arange(1440)*MINUTE).tolist(),'OHLC_fields':['open','high','low','close'],'OHLC':path.tolist(),'prepared_minutes_sha256':ds.manifest['artifacts'][minute_name]['sha256'],'source_sha256':ds.manifest['artifacts'][minute_name]['sha256'],'minutes':np.column_stack((entry+np.arange(1440)*MINUTE,path)).tolist(),'ambiguous_minute_ms':sorted({entry+(v['upper_time_minutes']-1)*MINUTE for v in first['touch'] if v['upper_hit'] and not v['lower_hit'] and v['upper_time_minutes'] is not None})}
   write_json(output/f'example-path-{symbol}.json',actual);del minute
 result['deterministic_examples']=examples
 result['entry_gap_all_observed']={'n':len(ids),'mean_log':float(np.log(ds.meta['entry'][ids]/ds.meta['reference'][ids]).mean()),'quantiles_0_25_50_75_100':np.quantile(np.log(ds.meta['entry'][ids]/ds.meta['reference'][ids]),[0,.25,.5,.75,1]).tolist()}
 result['actionable_touch_summary']={}
 for asset in ('BTCUSDT','SOLUSDT'):
  subset=[v for v in details if v['asset']==asset]
  result['actionable_touch_summary'][asset]={'n':len(subset),'targets':[{bound+'_hit_frequency':sum(v['touch'][j][bound+'_hit'] for v in subset)/len(subset) if subset else None for bound in ('lower','upper')} for j in range(3)]}
 result['TRAIN_pattern_examples']=[]
 for asset,symbol in enumerate(('BTCUSDT','SOLUSDT')):
  row=int(train[ds.meta['asset'][train]==asset][0]);x,_=ds.features([row],seal['view']);from .forecast_independent_models import render
  png(output/f'TRAIN-example-{symbol}.png',render(x[0]));result['TRAIN_pattern_examples'].append({'row':row,'origin_ms':int(ds.meta['origin'][row]),'asset':symbol,'selection':'first mature TRAIN origin; independent of outcomes'})
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['profile','screen','fit','check']);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--family',choices=['control','stumpy','minirocket','rdst','cnn'],default='control');p.add_argument('--view',default='60x20');p.add_argument('--selection',type=Path);p.add_argument('--seal',type=Path);p.add_argument('--baseline',type=Path);p.add_argument('--execute-train',action='store_true');p.add_argument('--execute-check',action='store_true');p.add_argument('--prior-cpu-seconds',type=float);p.add_argument('--all-method-seals',type=Path);a=p.parse_args()
 if a.stage in ('screen','fit') and not a.execute_train:raise ValueError('EXPLICIT_TRAIN_EXECUTION_FLAG_REQUIRED')
 if a.stage=='check' and (not a.execute_check or a.seal is None):raise ValueError('EXPLICIT_SEPARATE_CHECK_FLAG_AND_SEAL_REQUIRED')
 if a.stage!='profile' and (a.prior_cpu_seconds is None or a.prior_cpu_seconds<0):raise ValueError('DURABLE_PRIOR_CPU_BUDGET_ACCOUNTING_REQUIRED')
 a.output.mkdir(parents=True,exist_ok=False);started=Budget.cpu();budget=Budget(max(0,(120 if a.family=='cnn' else 60)-(a.prior_cpu_seconds or 0)/60));write_json(a.output/'intent.json',{'stage':a.stage,'family':a.family,'source_sha256':source_hashes(),'protocol_sha256':PROTOCOL_SHA,'CHECK_read_authorized':a.stage=='check'})
 try:
  if a.stage=='check':
   seal=check_identity(a.seal,a.dataset);validate_registry(a.all_method_seals,a.dataset)
   if seal['family']!='control' and a.baseline is None:raise ValueError('RAW_CONTROL_BASELINE_REQUIRED')
   acquire_check_lock(a.seal,a.output)
  ds=Dataset(a.dataset,a.protocol,allow_check=a.stage=='check')
  if a.stage=='profile':result=profile(ds,a.family,a.view,a.output,budget)
  elif a.stage=='screen':result=screen(ds,a.output,budget)
  elif a.stage=='fit':result=fit_family(ds,a.family,a.selection,a.output,budget)
  else:result=evaluate(ds,a.seal,a.output,budget,a.baseline)
  result.update(protocol_sha256=PROTOCOL_SHA,dataset_manifest_sha256=sha(ds.path/'manifest.json'),prior_cpu_seconds=a.prior_cpu_seconds or 0,cpu_seconds=Budget.cpu()-started,maxrss_bytes=max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)*1024);write_json(a.output/'result.json',result);emit(result)
 except BaseException as error:
  write_json(a.output/'failure.json',{'status':'INCOMPLETE_NO_AUTOMATIC_RETRY','error':str(error),'type':type(error).__name__,'cpu_seconds':Budget.cpu()-started,'traceback':traceback.format_exc()});raise
if __name__=='__main__':main()
