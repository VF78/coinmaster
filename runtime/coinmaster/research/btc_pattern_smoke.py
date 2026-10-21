"""Outcome-blind hardware/resource checks on 128 true input windows."""
import gc,importlib.metadata,json,os,platform,resource,sys,time
from pathlib import Path
import numpy as np
from .forecast_independent_data import sha,write_json


def kronos_load(repo,weights,device):
    import torch
    from safetensors.torch import load_file
    sys.path.insert(0,str((Path(repo)/'reports/ai-cycle-20261021-01/kronos-upstream').resolve()))
    from model import Kronos,KronosTokenizer
    receipt=json.loads((Path(weights)/'download-receipt.json').read_text())
    for name,rec in receipt.items():
        if isinstance(rec,dict) and 'sha256' in rec and sha(Path(weights)/name)!=rec['sha256']:raise ValueError('FROZEN_KRONOS_WEIGHT_DRIFT '+name)
    def load(cls,kind):
        p=Path(weights)/kind;m=cls(**json.loads((p/'config.json').read_text()));m.load_state_dict(load_file(str(p/'model.safetensors')),strict=True);m.eval();m.requires_grad_(False);return m.to(device)
    return load(Kronos,'small'),load(KronosTokenizer,'tokenizer')


def kronos_input(raw,stamps):
    import pandas as pd
    amount=raw[:,:,:4].mean(2)*raw[:,:,4];x=np.concatenate((raw,amount[:,:,None]),axis=2).astype('float32')
    x=np.clip((x-x.mean(1,keepdims=True))/(x.std(1,keepdims=True)+1e-5),-5,5)
    s=[]
    for t in stamps:
        d=pd.to_datetime(t,unit='ms',utc=True);s.append(np.column_stack((d.minute,d.hour,d.dayofweek,d.day,d.month)))
    return x,np.array(s,'float32')


def kronos_cache(model,tokenizer,raw,stamps,device,batch=8):
    import torch
    out=[]
    with torch.inference_mode():
        for a in range(0,len(raw),batch):
            views=[]
            for tf in (0,1):
                x,s=kronos_input(raw[a:a+batch,tf],stamps[a:a+batch,tf]);s1,s2=tokenizer.encode(torch.from_numpy(x).to(device),half=True)
                _,context=model.decode_s1(s1,s2,stamp=torch.from_numpy(s).to(device));views.append(context[:,-1,:].cpu().numpy().copy())
            out.append(np.concatenate(views,axis=1))
    return np.concatenate(out).astype('float32')


def smoke(a):
    import torch
    from .btc_pattern_models import TCN,CNN,Projection,render,save_png
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise ValueError('MPS_WATERMARK_MUST_REMAIN_ENABLED')
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(7)
    a.output.mkdir(parents=True,exist_ok=False)
    p=a.prepared;meta=np.load(p/'metadata.npy',mmap_mode='r');ids=np.flatnonzero(meta['valid'])[:128]
    if len(ids)!=128:raise ValueError('128_TRUE_WINDOWS_REQUIRED')
    x=np.array(np.load(p/'features.npy',mmap_mode='r')[ids]);c=np.array(np.load(p/'context.npy',mmap_mode='r')[ids]);raw=np.array(np.load(p/'raw.npy',mmap_mode='r')[ids]);stamps=np.array(np.load(p/'stamps.npy',mmap_mode='r')[ids])
    images=np.stack([render(r) for r in raw]);save_png(a.output/'two-panels.png',images[0])
    datasets={'TCN':x,'CNN':images.transpose(0,3,1,2).astype('float32')/255}
    results=[];devices=['cpu']+(['mps'] if torch.backends.mps.is_available() else [])
    sync=lambda device:torch.mps.synchronize() if device=='mps' else None
    def memory(device):return dict(rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,mps_allocated_bytes=torch.mps.current_allocated_memory() if device=='mps' else None,mps_driver_bytes=torch.mps.driver_allocated_memory() if device=='mps' else None)
    for name,arr in datasets.items():
        cpu_sample=None
        for device in devices:
            torch.manual_seed(7);model=(TCN() if name=='TCN' else CNN()).to(device);model.eval();batch=16 if name=='TCN' else 8
            first=time.monotonic();samples=[]
            with torch.inference_mode():
                for j in range(0,128,batch):samples.append(tuple(v.cpu().numpy().copy() for v in model(torch.from_numpy(arr[j:j+batch]).to(device),torch.from_numpy(c[j:j+batch]).to(device))))
            sync(device);forward=time.monotonic()-first
            if not all(np.isfinite(v).all() for b in samples for v in b):raise ValueError('NONFINITE_SMOKE')
            sample=np.concatenate([b[0] for b in samples]);agreement=None
            if device=='cpu':cpu_sample=sample
            else:agreement=dict(max_abs=float(np.max(abs(sample-cpu_sample))),tolerance=.005,pass_=bool(np.allclose(sample,cpu_sample,rtol=.005,atol=.005)))
            model.train();first=time.monotonic();z,d,q=model(torch.from_numpy(arr[:batch]).to(device),torch.from_numpy(c[:batch]).to(device));loss=z.square().mean()+d.square().mean()+q.square().mean();loss.backward();sync(device);backward=time.monotonic()-first
            if not all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None):raise ValueError('NONFINITE_GRADIENT')
            model.eval();weight=a.output/f'{name}-{device}.pt';torch.save(model.cpu().state_dict(),weight);restored=TCN() if name=='TCN' else CNN();restored.load_state_dict(torch.load(weight,weights_only=True));restored.eval()
            with torch.inference_mode():
                out1=model.cpu()(torch.from_numpy(arr[:2]),torch.from_numpy(c[:2]));out2=restored(torch.from_numpy(arr[:2]),torch.from_numpy(c[:2]))
                if not all(torch.equal(a,b) for a,b in zip(out1,out2)):raise ValueError('SAVE_LOAD_DRIFT')
            results.append(dict(model=name,device=device,n_windows=128,batch=batch,forward_seconds=forward,windows_per_second=128/forward,one_backward_seconds=backward,parameters=sum(v.numel() for v in model.parameters()),agreement=agreement,save_load='PASS',**memory(device)))
            del model,restored;gc.collect()
            if device=='mps':torch.mps.empty_cache()
    repo=Path(__file__).resolve().parents[3];weights=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/ai-cycle-20261021-01/kronos-weights')
    cpucache=None
    for device in devices:
        first=time.monotonic();model,tokenizer=kronos_load(repo,weights,device);loaded=time.monotonic()-first
        first=time.monotonic();cache=kronos_cache(model,tokenizer,raw,stamps,device);sync(device);elapsed=time.monotonic()-first
        if cache.shape!=(128,1024) or not np.isfinite(cache).all():raise ValueError('KRONOS_CONTEXT_INVALID')
        agreement=None
        if device=='cpu':cpucache=cache
        else:agreement=dict(max_abs=float(abs(cache-cpucache).max()),tolerance=.02,pass_=bool(np.allclose(cache,cpucache,rtol=.02,atol=.02)))
        np.save(a.output/f'kronos-{device}.npy',cache)
        projection=Projection();z,d,q=projection(torch.from_numpy(cache.copy()),torch.from_numpy(c));(z.square().mean()+d.square().mean()+q.square().mean()).backward()
        results.append(dict(model='KronosFrozen',device=device,n_windows=128,load_seconds=loaded,forward_seconds=elapsed,windows_per_second=128/elapsed,parameters=sum(v.numel() for v in model.parameters()),agreement=agreement,trainable_projection_backward='PASS_FROM_NUMPY_NORMAL_TENSOR',**memory(device)))
        del model,tokenizer,projection;gc.collect()
        if device=='mps':torch.mps.empty_cache()
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    result=dict(schema='btc-pattern.smoke.v1',quality_accessed=False,learned_full_fits=0,windows_ids=ids.tolist(),protocol_sha256=sha(a.protocol),prepared_manifest_sha256=sha(p/'manifest.json'),torch=torch.__version__,platform=platform.platform(),machine=platform.machine(),mps_built=torch.backends.mps.is_built(),mps_available=torch.backends.mps.is_available(),watermark=os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO','DEFAULT_ENABLED'),fallback=os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK','UNSET_DISABLED'),results=results,packages=packages)
    write_json(a.output/'resource-smoke.json',result);return result
