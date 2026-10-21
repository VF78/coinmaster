"""Zero-fit diagnosis of the immutable failed positive synthetic checkpoint."""
import json,hashlib,math,time
from pathlib import Path
import numpy as np,pandas as pd,torch
from coinmaster.research.btc_pattern_models import CNN,predict_loss,soft_metric
from coinmaster.research.btc_pattern_train import neural_predict,Data
from coinmaster.research.btc_pattern_data import META,HOUR
r=Path('reports/btc-pattern-pilot-m2-20261021');job=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');folder=job/'full-es3-synthetic';out=job/'full-es3-synthetic-zero-fit-diagnosis';out.mkdir(exist_ok=False);rng=np.random.default_rng(701);n=768;latent=np.repeat(rng.integers(0,3,n//8),8);data=type('SyntheticData',(),{})();data.c=rng.normal(0,.05,(n,12)).astype('float32');data.c[:,:3]+=np.eye(3)[latent]*2;colors=np.eye(3,dtype='uint8')*200+20;data.images=np.broadcast_to(colors[latent,None,None,:],(n,224,224,3)).copy();data.x=np.zeros((n,2,64,6),'float32');data.kronos=None;data.meta=np.zeros(n,dtype=META);data.meta['origin']=np.arange(n)*100*HOUR;data.meta['label_end']=data.meta['origin']+72*HOUR;data.d=latent.astype('int64');data.y=np.stack((.2+.5*latent,1.2-.4*latent),axis=1).astype('float32');data.signature=np.tile(latent[:,None],(1,12)).astype('float32')+rng.normal(0,.05,(n,12)).astype('float32');fit=np.arange(512);query=np.arange(512,n)
torch.set_num_threads(4);torch.set_num_interop_threads(1);assert torch.backends.mps.is_available();state=torch.load(folder/'positive.pt',weights_only=False,map_location='cpu');z,p,q=neural_predict(data,state,query,device='mps');prior=np.quantile(data.y[fit],[.2,.5,.8],axis=0).T;rows=[]
for c in range(3):
 sel=latent[query]==c
 for side in range(2):
  for k,level in enumerate([.2,.5,.8]):
   raw=q[sel,side,k];project=np.maximum(0,np.sort(q[sel],axis=2))[:,side,k];true=data.y[query[sel],side]
   rows.append(dict(latent=c,side=['long','short'][side],q=level,N=int(sel.sum()),true_conditional_quantile=float(true[0]),fit_prior_quantile=float(prior[side,k]),raw_mean=float(raw.mean()),raw_std=float(raw.std()),raw_bias=float((raw-true).mean()),projected_mean=float(project.mean()),projected_std=float(project.std()),projected_bias=float((project-true).mean())))
pd.DataFrame(rows).to_csv(out/'conditional-Q.csv',index=False)
torch.manual_seed(7);initial=CNN();initial_qbias=initial.heads.quantiles.bias.detach().numpy().reshape(2,3).tolist();model=CNN().to('mps');model.load_state_dict(state['weights']);model.eval();ids=np.arange(64);x=torch.from_numpy(data.images[ids].transpose(0,3,1,2).astype('float32')/255).to('mps');context=torch.from_numpy(((data.c[ids]-state['context_mean'])/state['context_std']).astype('float32')).to('mps');zz,logits,qq=model(x,context);target=torch.from_numpy(data.y[ids]).to('mps');scale=torch.from_numpy(state['q_scales']).to('mps');prediction,dl,ql=predict_loss(logits,qq,torch.from_numpy(data.d[ids]).to('mps'),target,scale);ml,_=soft_metric(zz,torch.from_numpy(data.signature[ids]).to('mps'),torch.from_numpy(data.meta['origin'][ids].copy()).to('mps'),torch.from_numpy(data.meta['label_end'][ids].copy()).to('mps'),torch.from_numpy(state['signature_scales']).to('mps'),state['tau']);parameters=list(model.named_parameters());gradient=[]
for label,loss in [('Q_only',ql),('D_only',dl),('metric_weighted',.1*ml),('original_total',prediction+.1*ml)]:
 grads=torch.autograd.grad(loss,[p for name,p in parameters],retain_graph=True,allow_unused=True)
 for group,prefix in [('encoder','encoder.'),('projection','heads.projection.'),('D_head','heads.direction.'),('Q_head','heads.quantiles.')]:
  norm=math.sqrt(sum(float((g.detach()**2).sum().cpu()) for (name,p),g in zip(parameters,grads) if name.startswith(prefix) and g is not None));gradient.append(dict(component=label,parameter_group=group,gradient_L2=norm,loss=float(loss.detach().cpu()),batch='fixedfitIDs0..63',optimizer_steps=0))
pd.DataFrame(gradient).to_csv(out/'gradient-norms.csv',index=False)
error=data.y[ids,:,None]-qq.detach().cpu().numpy();manual=float((np.maximum(np.array([.2,.5,.8])*error,(np.array([.2,.5,.8])-1)*error)/state['q_scales'][None,:,None]).mean());counts=[]
for f in sorted((job/'development').glob('F*/CNN-*.receipt.json')):
 receipt=json.loads(f.read_text());counts.append(dict(fold=f.parent.name,role=f.name,fit_rows=receipt['fit_rows'],selected_epochs=receipt['selected_epochs'],executed_epochs=receipt['epochs_executed'],steps_to_selected=math.ceil(receipt['fit_rows']/64)*receipt['selected_epochs'],steps_executed=math.ceil(receipt['fit_rows']/64)*receipt['epochs_executed']))
receipt=dict(status='ZERO_FIT_SAVED_SYNTHETIC_DIAGNOSIS',checkpoint_sha256=hashlib.sha256((folder/'positive.pt').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),fits=0,optimizer_steps=0,CHECK_used=False,q_shape=list(qq.shape),target_shape=list(target.shape),q_scale_MAD=state['q_scales'].tolist(),q_scale_applied='pinball divided by fit-only MAD broadcast[1,2,1]',canonical_normalized_Qloss=float(ql.detach().cpu()),manual_normalized_Qloss=manual,manual_agrees=bool(abs(manual-float(ql.detach().cpu()))<1e-6),initial_Q_bias=initial_qbias,trained_Q_bias=model.heads.quantiles.bias.detach().cpu().numpy().reshape(2,3).tolist(),synthetic_optimizer_steps=64,baseline_optimizer_steps=counts)
(out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
for p in out.glob('*'):r.joinpath('full-es3-zero-fit-'+p.name).write_bytes(p.read_bytes())
print(json.dumps(receipt))
