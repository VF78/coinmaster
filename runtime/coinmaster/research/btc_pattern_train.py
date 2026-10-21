"""Bounded fixed-recipe expanding-fold experiment. CHECK remains sealed."""
from __future__ import annotations
import copy,csv,gc,json,os,pickle,resource,time
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds,ms,HOUR,DAY,neighbors,method_input_start
from .forecast_independent_data import sha,write_json

DEADLINE=None

def resource_guard(device='cpu'):
    import torch
    if DEADLINE is not None and time.monotonic()>DEADLINE:raise RuntimeError('INCOMPLETE_RESOURCE_WALL_LIMIT')
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if rss>6*1024**3:raise RuntimeError('INCOMPLETE_RESOURCE_RSS_6GIB')
    return dict(rss_peak_bytes=rss,mps_driver_bytes=torch.mps.driver_allocated_memory() if device=='mps' else None,mps_allocated_bytes=torch.mps.current_allocated_memory() if device=='mps' else None)

class Data:
    def __init__(self,path):
        self.path=Path(path);self.meta=np.load(self.path/'metadata.npy',mmap_mode='r');self.x=np.load(self.path/'features.npy',mmap_mode='r');self.c=np.load(self.path/'context.npy',mmap_mode='r');self.raw=np.load(self.path/'raw.npy',mmap_mode='r')
        with np.load(self.path/'labels.npz') as y:self.d=y['direction'];self.y=y['mfe'][:,:,0];self.upper=y['mfe'][:,:,1];self.signature=y['signature']
        self.descriptor=np.concatenate((self.x.reshape(len(self.x),2,16,4,6).mean(3).reshape(len(self.x),-1),self.c),axis=1).astype('float32')
        self.images=None;self.kronos=None
    def image_cache(self,output):
        from .btc_pattern_models import render
        file=Path(output)/'images.npy'
        if not file.exists():
            cache=np.lib.format.open_memmap(file,mode='w+',dtype='uint8',shape=(len(self.meta),224,224,3))
            for i in range(len(cache)):cache[i]=render(self.raw[i])
            cache.flush()
        self.images=np.load(file,mmap_mode='r')


def normalize(x,ids):
    mean=np.asarray(x[ids]).mean(0);std=np.asarray(x[ids]).std(0);return mean,np.maximum(std,1e-6)

def l2(x):return x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)

def scales(data,ids):
    y=data.signature[ids,:6];ys=np.maximum(np.quantile(y,.75,axis=0)-np.quantile(y,.25,axis=0),1e-6)
    q=data.y[ids];qs=np.maximum(np.median(abs(q-np.median(q,axis=0)),axis=0),1e-6)
    rng=np.random.default_rng(7);a=rng.choice(ids,8192);b=rng.choice(ids,8192);valid=(data.meta['origin'][a]>=data.meta['label_end'][b])|(data.meta['label_end'][a]<=data.meta['origin'][b]);a,b=a[valid],b[valid]
    dist=.5*abs((data.signature[a,:6]-data.signature[b,:6])/ys).mean(1)+.5*abs(data.signature[a,6:]-data.signature[b,6:]).mean(1)
    return ys.astype('float32'),qs.astype('float32'),float(np.median(dist[dist>0])) if (dist>0).any() else 1.

def aggregate_predict(records):
    """(rows, valid D rows, D mean, Q mean); independent head denominators."""
    r=np.asarray(records,dtype=float)
    dn=r[:,1].sum(); qn=r[:,0].sum()
    d=float((r[:,1]*r[:,2]).sum()/dn) if dn else 0.
    q=float((r[:,0]*r[:,3]).sum()/qn) if qn else 0.
    return np.array([d+q,d,q])


def neural_fit(data,kind,fit_ids,es_ids,out,epochs=None,device='cpu',seed=7):
    import torch
    from .btc_pattern_models import TCN,CNN,Projection,predict_loss,soft_metric
    torch.manual_seed(seed);rng=np.random.default_rng(seed)
    factory={'TCN':TCN,'CNN':CNN,'Kronos':Projection};model=factory[kind]().to(device);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    cm,cs=normalize(data.c,fit_ids);xm,xs=normalize(data.x,fit_ids) if kind=='TCN' else (0.,1.)
    km,ks=normalize(data.kronos,fit_ids) if kind=='Kronos' else (0.,1.)
    ys,qs,tau=scales(data,fit_ids);batch=64 if kind=='CNN' else 128
    def input_batch(ids):
        if kind=='TCN':x=(np.asarray(data.x[ids])-xm)/xs
        elif kind=='CNN':x=np.asarray(data.images[ids]).transpose(0,3,1,2).astype('float32')/255
        else:x=(np.asarray(data.kronos[ids])-km)/ks
        return torch.from_numpy(np.asarray(x,dtype='float32')).to(device),torch.from_numpy(((np.asarray(data.c[ids])-cm)/cs).astype('float32')).to(device)
    def loss_for(ids,training):
        x,c=input_batch(ids);z,d,q=model(x,c);pred,dl,ql=predict_loss(d,q,torch.from_numpy(data.d[ids].astype('int64')).to(device),torch.from_numpy(data.y[ids]).to(device),torch.from_numpy(qs).to(device))
        ml,stat=soft_metric(z,torch.from_numpy(data.signature[ids]).to(device),torch.from_numpy(data.meta['origin'][ids].copy()).to(device),torch.from_numpy(data.meta['label_end'][ids].copy()).to(device),torch.from_numpy(ys).to(device),tau) if training else (pred*0,dict(eligible_anchors=0,eligible_pairs=0,target_entropy=0))
        return pred+.1*ml,pred,dl,ql,ml,stat
    optimizer_steps=0;history=[];best=np.inf;best_epoch=1;wait=0;selected=None;start=time.monotonic()
    for epoch in range(1,(epochs or 30)+1):
        model.train();order=rng.permutation(fit_ids);records=[]
        for a in range(0,len(order),batch):
            resource_guard(device);ids=order[a:a+batch];opt.zero_grad(set_to_none=True);total,pred,dl,ql,ml,stat=loss_for(ids,True);total.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();optimizer_steps+=1;records.append([len(ids),int((data.d[ids]>=0).sum()),float(dl.detach().cpu()),float(ql.detach().cpu()),float(ml.detach().cpu()),stat['eligible_anchors'],stat['eligible_pairs'],stat['target_entropy']])
        model.eval();validation=[]
        if es_ids is not None:
            with torch.no_grad():
                for a in range(0,len(es_ids),batch):
                    ids=es_ids[a:a+batch];values=loss_for(ids,False);validation.append((len(ids),int((data.d[ids]>=0).sum()),*[float(v.detach().cpu()) for v in values[2:4]]))
            vl=aggregate_predict(validation);score=vl[0]
        else:vl=[None]*3;score=None
        with torch.no_grad():
            probe_x,probe_c=input_batch(fit_ids[:128]);probe_z=model(probe_x,probe_c)[0].cpu().numpy();singular=np.linalg.svd(probe_z-probe_z.mean(0),compute_uv=False);energy=singular**2;energy=energy/max(float(energy.sum()),1e-12);rank=float(np.exp(-(energy[energy>0]*np.log(energy[energy>0])).sum()))
        online=aggregate_predict([r[:4] for r in records]); rr=np.asarray(records); metric=float(np.average(rr[:,4],weights=rr[:,0]))
        row=dict(target_entropy=float(np.mean(rr[:,7])),embedding_variance=float(probe_z.var(0).mean()),embedding_effective_rank=rank,epoch=epoch,fit_predict=float(online[0]),fit_D=float(online[1]),fit_Q=float(online[2]),metric=metric,fit_rows=int(rr[:,0].sum()),valid_D_rows=int(rr[:,1].sum()),optimizer_steps=optimizer_steps,loss_semantics='online_parameter_changing_head_weighted',eligible_anchors=float(np.mean(rr[:,5])),eligible_pairs=float(np.mean(rr[:,6])),early_stop_predict=vl[0],early_stop_D=vl[1],early_stop_Q=vl[2]);history.append(row)
        write_json(out.with_suffix('.curve.json'),history)
        if es_ids is not None:
            if score<best-1e-8:best=score;best_epoch=epoch;wait=0;selected=copy.deepcopy({k:v.cpu() for k,v in model.state_dict().items()})
            else:wait+=1
            if wait>=5:break
    if selected is not None:model.load_state_dict(selected)
    state=dict(kind=kind,seed=seed,epochs=epochs or best_epoch,fit_ids=fit_ids,fit_cutoff=int(data.meta['label_end'][fit_ids].max()),context_mean=cm,context_std=cs,x_mean=xm,x_std=xs,k_mean=km,k_std=ks,signature_scales=ys,q_scales=qs,tau=tau,weights={k:v.cpu() for k,v in model.state_dict().items()})
    torch.save(state,out);receipt=dict(optimizer_steps=optimizer_steps,kind=kind,selected_epochs=epochs or best_epoch,epochs_executed=len(history),wall_seconds=time.monotonic()-start,fit_rows=len(fit_ids),early_stop_rows=0 if es_ids is None else len(es_ids),rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write_json(out.with_suffix('.receipt.json'),receipt);del model,opt;gc.collect()
    if device=='mps':torch.mps.empty_cache()
    return state,receipt


def neural_predict(data,state,ids,device='cpu'):
    import torch
    from .btc_pattern_models import TCN,CNN,Projection
    kind=state['kind'];model={'TCN':TCN,'CNN':CNN,'Kronos':Projection}[kind]().to(device);model.load_state_dict(state['weights']);model.eval();zall=[];pall=[];qall=[]
    with torch.inference_mode():
        for a in range(0,len(ids),128 if kind!='CNN' else 64):
            resource_guard(device);ii=ids[a:a+(128 if kind!='CNN' else 64)]
            if kind=='TCN':x=(np.array(data.x[ii])-state['x_mean'])/state['x_std']
            elif kind=='CNN':x=np.array(data.images[ii]).transpose(0,3,1,2).astype('float32')/255
            else:x=(np.array(data.kronos[ii])-state['k_mean'])/state['k_std']
            c=(np.array(data.c[ii])-state['context_mean'])/state['context_std'];z,p,q=model(torch.from_numpy(x.astype('float32')).to(device),torch.from_numpy(c.astype('float32')).to(device));zall.append(z.cpu().numpy());pall.append(torch.softmax(p,1).cpu().numpy());qall.append(q.cpu().numpy())
    result=tuple(np.concatenate(a) for a in (zall,pall,qall));del model;gc.collect()
    if device=='mps':torch.mps.empty_cache()
    return result


def catboost_fit(data,fit,es,out,iterations=None):
    from catboost import CatBoostClassifier,CatBoostRegressor
    args=dict(depth=4,learning_rate=.03,l2_leaf_reg=10,random_seed=7,thread_count=4,verbose=False,allow_writing_files=False)
    models=[];selected=[];start=time.monotonic()
    for head in range(3):
        ids=fit[data.d[fit]>=0] if head==0 else fit
        target=data.d[ids] if head==0 else data.y[ids,head-1]
        model=(CatBoostClassifier(loss_function='MultiClass',iterations=400 if iterations is None else iterations[head],**args) if head==0 else CatBoostRegressor(loss_function='MultiQuantile:alpha=0.2,0.5,0.8',iterations=400 if iterations is None else iterations[head],**args))
        extra={}
        if es is not None:
            ei=es[data.d[es]>=0] if head==0 else es;extra=dict(eval_set=(data.descriptor[ei],data.d[ei] if head==0 else data.y[ei,head-1]),early_stopping_rounds=40,use_best_model=True)
        model.fit(data.descriptor[ids],target,**extra);models.append(model);selected.append(model.tree_count_);model.save_model(str(out.with_name(out.name+f'-head{head}.cbm')))
    write_json(out.with_suffix('.receipt.json'),dict(head_fits=3,iterations=selected,wall_seconds=time.monotonic()-start,fit_ids_sha256=__import__('hashlib').sha256(fit.tobytes()).hexdigest()))
    return models,selected


def empirical(data,index,query,iz,qz,cutoff,random_context=False,support_method=None):
    support_start=method_input_start(data.meta,support_method or ('random-context' if random_context else 'numeric-knn'))
    priorids=index[data.d[index]>=0];pp=np.bincount(data.d[priorids],minlength=3)/len(priorids)
    pq=np.quantile(data.y[index],[.2,.5,.8],axis=0).T
    probabilities=[];quantiles=[];records=[];support=[];rng=np.random.default_rng(7);vcut=np.median(data.c[index,5])
    for row,qi in enumerate(query):
        resource_guard();local=index
        if random_context:
            match=(np.sign(data.c[index,3])==np.sign(data.c[qi,3]))&((data.c[index,5]>=vcut)==(data.c[qi,5]>=vcut));eligible=np.flatnonzero(match&(data.meta['label_end'][index]<=cutoff)&(data.meta['label_end'][index]<=support_start[qi]));order=rng.permutation(eligible);chosen=[]
            for j in order:
                if all(abs(int(data.meta['origin'][index[j]])-int(data.meta['origin'][index[k]]))>=72*HOUR for k in chosen):
                    chosen.append(int(j))
                    if len(chosen)==32:break
            ni=np.array(chosen,dtype='int64')
        else:ni=neighbors(iz,qz[row],data.meta['origin'][index],data.meta['label_end'][index],cutoff,support_start[qi])
        chosen=index[ni];n=len(chosen);support.append(n)
        if n<16:p,q=pp,pq
        else:
            matureD=chosen[data.d[chosen]>=0];nd=len(matureD);p=(np.bincount(data.d[matureD],minlength=3)+8*pp)/(nd+8)
            q=[]
            for side in range(2):
                vals=np.r_[data.y[chosen,side],data.y[index,side]];weights=np.r_[np.ones(n),np.full(len(index),8/len(index))];order=np.argsort(vals,kind='stable');cdf=np.cumsum(weights[order]);q.append(vals[order][np.searchsorted(cdf,np.array([.2,.5,.8])*cdf[-1],side='left')])
            q=np.array(q)
        probabilities.append(p);quantiles.append(q)
        for j in ni:records.append(dict(query=int(qi),neighbor=int(index[j]),query_origin=int(data.meta['origin'][qi]),neighbor_origin=int(data.meta['origin'][index[j]]),neighbor_label_end=int(data.meta['label_end'][index[j]]),query_input_start=int(support_start[qi]),cosine_distance=float(1-iz[j]@qz[row]),direction=int(data.d[index[j]])))
    return np.array(probabilities),np.array(quantiles),np.array(support),records


def train(a):
    import torch
    global DEADLINE
    DEADLINE=time.monotonic()+21600
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    lock=json.loads(a.protocol.read_text());auth=json.loads(a.authorization.read_text()) if a.authorization else {}
    sources={str(p):sha(p) for p in Path(__file__).parent.glob('btc_pattern_*.py')}
    if auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('source_hashes')!=sources or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json') or not auth.get('development_training'):raise ValueError('EXACT_COORDINATOR_GO_REQUIRED')
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise ValueError('WATERMARK_DISABLED')
    a.output.mkdir(parents=True,exist_ok=False);data=Data(a.prepared);data.image_cache(a.output)
    from .btc_pattern_smoke import kronos_load,kronos_cache
    repo=Path(__file__).resolve().parents[3];weights=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/ai-cycle-20261021-01/kronos-weights');model,tokenizer=kronos_load(repo,weights,'cpu');stamps=np.load(a.prepared/'stamps.npy',mmap_mode='r')
    cache=np.lib.format.open_memmap(a.output/'kronos-cache.npy',mode='w+',dtype='float32',shape=(len(data.meta),1024))
    for first in range(0,len(cache),128):cache[first:first+128]=kronos_cache(model,tokenizer,np.array(data.raw[first:first+128]),np.array(stamps[first:first+128]),'cpu')
    cache.flush();del model,tokenizer;gc.collect();data.kronos=cache
    ledger=[];allneighbors=[]
    for fold in folds(data.meta):
        name=fold['name'];out=a.output/name;out.mkdir();index=fold['refit'];query=fold['outer'];priorD=index[data.d[index]>=0];p=np.bincount(data.d[priorD],minlength=3)/len(priorD);q=np.quantile(data.y[index],[.2,.5,.8],axis=0).T
        def save(method,pred,qraw,support=None,z=None):
            np.savez(out/f'{method}.npz',ids=query,probabilities=pred,q_raw=qraw,q_projected=np.maximum(0,np.sort(qraw,axis=2)),support=np.zeros(len(query),int) if support is None else support,truth_D=data.d[query],truth_Q=data.y[query],truth_Q_upper=data.upper[query]);ledger.append(dict(fold=name,method=method,rows=len(query)))
        save('prior',np.tile(p,(len(query),1)),np.tile(q,(len(query),1,1)))
        dm,ds=normalize(data.descriptor,index);iz=l2((data.descriptor[index]-dm)/ds);qz=l2((data.descriptor[query]-dm)/ds)
        for method,random in [('numeric-knn',False),('random-context',True)]:
            pp,qq,ss,nr=empirical(data,index,query,iz,qz,fold['fit_cutoff'],random);save(method,pp,qq,ss);allneighbors.extend([dict(method=method,fold=name,**r) for r in nr])
        esmodels,iterations=catboost_fit(data,fold['subfit'],fold['early_stop'],out/'catboost-es');del esmodels
        models,_=catboost_fit(data,index,None,out/'catboost-refit',iterations);save('CatBoost',models[0].predict_proba(data.descriptor[query]),np.stack([m.predict(data.descriptor[query]) for m in models[1:]],axis=1));del models
        for kind in ('TCN','Kronos','CNN'):
            esstate,receipt=neural_fit(data,kind,fold['subfit'],fold['early_stop'],out/f'{kind}-es.pt',device='mps' if kind in ('TCN','CNN') and torch.backends.mps.is_available() else 'cpu');del esstate
            state,_=neural_fit(data,kind,index,None,out/f'{kind}-refit.pt',epochs=receipt['selected_epochs'],device='mps' if kind in ('TCN','CNN') and torch.backends.mps.is_available() else 'cpu');z,pred,qraw=neural_predict(data,state,np.r_[index,query],device='mps' if kind in ('TCN','CNN') and torch.backends.mps.is_available() else 'cpu');iz,qz=z[:len(index)],z[len(index):];save(kind+'-direct',pred[len(index):],qraw[len(index):]);pp,qq,ss,nr=empirical(data,index,query,iz,qz,fold['fit_cutoff'],support_method=kind);save(kind+'-knn',pp,qq,ss);allneighbors.extend([dict(method=kind+'-knn',fold=name,**r) for r in nr]);del state
            write_json(a.output/'progress.json',dict(completed=ledger,quality_opened=False))
    import pandas as pd
    pd.DataFrame(allneighbors).to_parquet(a.output/'neighbors.parquet',index=False)
    write_json(a.output/'development-complete.json',dict(status='DEVELOPMENT_FITS_COMPLETE_METRICS_PENDING',ledger=ledger,source_hashes=sources,protocol_sha256=sha(a.protocol),resource=resource_guard()))
    from .btc_pattern_evaluate import write_evaluation_contract
    write_evaluation_contract(a.output,a.prepared,a.protocol,sorted({r['method'] for r in ledger}),dict(mode='same_run',authorization_sha256=sha(a.authorization)))
    return dict(status='DEVELOPMENT_FITS_COMPLETE_METRICS_PENDING',groups=len(ledger))
