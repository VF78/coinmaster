"""Outcomes-blind synthetic forward/backward timing. No optimizer or parameter updates."""
import json,time,resource
from pathlib import Path
import numpy as np,torch
from coinmaster.research.pattern_form_models import Context
from coinmaster.research.btc_pattern_models import predict_loss,soft_metric
from coinmaster.research.forecast_independent_data import sha,write_json

def main():
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(7)
    model=Context();before={k:v.detach().clone() for k,v in model.state_dict().items()};c=torch.randn(64,12);y=torch.rand(64,2);d=torch.arange(64)%3;signature=torch.rand(64,12);origins=torch.arange(64)*96*3600000;times=[]
    for i in range(22):
        t=time.perf_counter();model.zero_grad(set_to_none=True);z,logits,q=model(torch.empty(64,0),c);pred,_,_=predict_loss(logits,q,d,y,torch.ones(2));metric,_=soft_metric(z,signature,origins,origins+72*3600000,torch.ones(6),1.);(pred+.1*metric).backward()
        if i>=2:times.append(time.perf_counter()-t)
    assert all(torch.equal(before[k],v) for k,v in model.state_dict().items())
    protocol=Path('reports/btc-pattern-pilot-m2-20261021/form-signal-20261022/experiment-protocol-draft.json');p=json.loads(protocol.read_text());steps=sum(f['context_max_optimizer_steps'] for f in p['folds']);per_step=float(np.quantile(times,.95));estimate=(steps*per_step+180)*1.2
    result=dict(stage='CONTEXT_OUTCOME_BLIND_RESOURCE',source_sha256=sha(__file__),protocol_sha256=sha(protocol),device='cpu',threads=4,batch=64,warmup=2,timed_batches=20,median_forward_backward_seconds=float(np.median(times)),p95_forward_backward_seconds=per_step,max_market_optimizer_steps=steps,optimizer_step_timing_allowance='included within180s aggregate reserve along with ES/inference/scales/curves/retrieval/evaluation',max_full_cost_with20percent_seconds=estimate,wall_request_seconds=max(600,int(np.ceil(estimate))),rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,optimizer_steps=0,market_fits=0,synthetic_fits=0,parameter_changes=0)
    write_json(protocol.with_name('context-resource.json'),result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
