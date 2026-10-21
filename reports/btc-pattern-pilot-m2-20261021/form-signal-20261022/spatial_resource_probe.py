"""One sequential CPU/hybrid outcome-blind probe; zero optimizer steps or fits."""
from pathlib import Path
import gc,os,time,resource
import numpy as np,torch
from coinmaster.research.pattern_form_models import CNNSpatial,SpatialPool
from coinmaster.research.btc_pattern_models import predict_loss,soft_metric
from coinmaster.research.forecast_independent_data import sha,write_json

def main():
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(7);start=time.monotonic()
    if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():raise RuntimeError('HOST_MPS_REQUIRED_NOT_UNSUPPORTED_CLAIM')
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise RuntimeError('WATERMARK_DISABLED')
    # Compare exact stockCPU operation and its gradient to CPU-route/MPS copy operation.
    a=torch.randn(2,128,28,28,requires_grad=True);b=a.detach().to('mps').requires_grad_(True);w=torch.randn(2,128,2,8);ca=torch.nn.AdaptiveAvgPool2d((2,8))(a);cb=SpatialPool((2,8))(b);(ca*w).sum().backward();(cb*w.to('mps')).sum().backward();torch.mps.synchronize();out_delta=float((ca-cb.cpu()).abs().max());grad_delta=float((a.grad-b.grad.cpu()).abs().max());assert out_delta<1e-6 and grad_delta<1e-6
    del a,b,w,ca,cb;gc.collect();torch.mps.empty_cache();results=[]
    for device in ('cpu','mps'):
        torch.manual_seed(7);model=CNNSpatial().to(device);before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};x=torch.randn(64,3,224,224,device=device);c=torch.randn(64,12,device=device);d=(torch.arange(64,device=device)%3).long();qtrue=torch.rand(64,2,device=device);sig=torch.rand(64,12,device=device);origins=torch.arange(64,device=device)*96*3600000;ones=torch.ones(6,device=device);timings=[];memory=[]
        def sync():
            if device=='mps':torch.mps.synchronize()
        def guard():
            rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if rss>6*1024**3 or time.monotonic()-start>180:raise RuntimeError('RESOURCE_GUARD')
            memory.append(dict(rss_peak_bytes=rss,mps_allocated_bytes=torch.mps.current_allocated_memory() if device=='mps' else 0,mps_driver_bytes=torch.mps.driver_allocated_memory() if device=='mps' else 0))
        for i in range(4):
            model.train();model.zero_grad(set_to_none=True);sync();t=time.perf_counter();z,logits,q=model(x,c);pred,_,_=predict_loss(logits,q,d,qtrue,ones[:2]);metric,_=soft_metric(z,sig,origins,origins+72*3600000,ones,1.);(pred+.1*metric).backward();sync();elapsed=time.perf_counter()-t;guard()
            if i:timings.append(elapsed)
        forward=[];model.eval()
        with torch.inference_mode():
            for i in range(3):
                sync();t=time.perf_counter();model(x,c);sync();forward.append(time.perf_counter()-t);guard()
        assert all(torch.equal(before[k],v.detach().cpu()) for k,v in model.state_dict().items())
        results.append(dict(device=device,forward_loss_metric_backward_seconds=timings,forward_seconds=forward,sampled_memory_max={k:max(r[k] for r in memory) for k in memory[0]}))
        del model,before,x,c,d,qtrue,sig,origins,ones,z,logits,q,pred,metric;gc.collect()
        if device=='mps':torch.mps.empty_cache()
    path=Path('reports/btc-pattern-pilot-m2-20261021/form-signal-20261022');import json
    protocol=json.loads((path/'experiment-protocol-draft.json').read_text());steps=sum(f['context_max_optimizer_steps'] for f in protocol['folds']);ES=30*sum((f['ES']+63)//64 for f in protocol['folds']);infer=sum((f['refit']+f['outer']+63)//64 for f in protocol['folds']);reserve=180;optimizer_allowance=.003*steps
    for r in results:r['full_worst_with20percent_seconds']=(max(r['forward_loss_metric_backward_seconds'])*steps+max(r['forward_seconds'])*(ES+infer)+optimizer_allowance+reserve)*1.2
    selected=min(results,key=lambda r:r['full_worst_with20percent_seconds'])
    result=dict(stage='SPATIAL_OUTCOME_BLIND_RESOURCE',source_sha256=sha(__file__),model_source_sha256=sha('runtime/coinmaster/research/pattern_form_models.py'),protocol_sha256=sha(path/'experiment-protocol-draft.json'),torch_version=torch.__version__,cpu_threads=4,batch=64,results=results,selected_device=selected['device'],wall_request_seconds=int(np.ceil(selected['full_worst_with20percent_seconds'])),pool_parity=dict(output_max_abs_delta=out_delta,input_gradient_max_abs_delta=grad_delta,tolerance=1e-6),max_market_optimizer_steps=steps,max_ES_forward_batches=ES,max_refit_outer_inference_batches=infer,optimizer_timing_allowance_seconds=optimizer_allowance,IO_scalers_SVD_retrieval_evaluation_reserve_seconds=reserve,exact_MPS_peak='UNKNOWN; sampled afterbackward/inference only',watermark_env=os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO','DEFAULT'),fallback_env=os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK','UNSET'),optimizer_steps=0,parameter_changes=0,market_fits=0,synthetic_fits=0,wall_seconds=time.monotonic()-start)
    write_json(path/'spatial-resource.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
