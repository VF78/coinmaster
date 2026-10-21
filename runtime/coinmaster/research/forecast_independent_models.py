"""Independent bounded forecasters. Imports Torch/aeon only on requested model paths."""
from __future__ import annotations
import copy,json,pickle,time
from pathlib import Path
import numpy as np
from .forecast_independent_data import DAY,MINUTE,ms,write_json,sha
QUANTILES=np.array([.2,.5,.8])
def project(q):
 q=np.sort(np.maximum(np.asarray(q),0.),axis=-1);q[:,1]=np.maximum(q[:,1],q[:,0]);return q

def unpack(raw):return project(raw[:,:12].reshape(-1,2,2,3)),raw[:,12:15]
def pinball(q,y):
 err=y[:,:,:,None]-q;return np.maximum(QUANTILES*err,(QUANTILES-1)*err)
def softmax(logits):
 a=np.asarray(logits,dtype=np.float64);a=a-a.max(1,keepdims=True);a=np.exp(a);return a/a.sum(1,keepdims=True)
def scores(q,logits,y,d):
 p=softmax(logits);loss=pinball(q,y);truth=np.eye(3)[d]
 return {'lower_pinball':float(loss[:,0].mean()),'upper_pinball':float(loss[:,1].mean()),'direction_logloss':float(-np.log(np.maximum(p[np.arange(len(d)),d],1e-12)).mean()),'direction_brier':float(((p-truth)**2).sum(1).mean()),'direction_accuracy':float((p.argmax(1)==d).mean()),'n':len(d)}
class Budget:
 def __init__(self,minutes):self.started=time.process_time();self.limit=minutes*60
 def check(self):
  if time.process_time()-self.started>self.limit:raise RuntimeError('INCOMPLETE_CPU_BUDGET_EXCEEDED')
class Scale:
 def fit(self,getter,ids,chunk=256):
  total=0;mean=None;m2=None
  for i in range(0,len(ids),chunk):
   x=getter(ids[i:i+chunk]).astype(np.float64);n=len(x);mu=x.mean(0);ss=((x-mu)**2).sum(0)
   if mean is None:mean=mu;m2=ss;total=n
   else:
    delta=mu-mean;new=total+n;mean+=delta*n/new;m2+=ss+delta**2*total*n/new;total=new
  self.mean=mean.astype(np.float32);self.std=np.sqrt(m2/max(total,1)).astype(np.float32);self.std[self.std<1e-6]=1.;return self
 def transform(self,x):return ((x-self.mean)/self.std).astype(np.float32)
def make_transform(family):
 if family=='minirocket':
  from aeon.transformations.collection.convolution_based import MiniRocket
  return MiniRocket(n_kernels=2016,max_dilations_per_kernel=32,n_jobs=1,random_state=7)
 if family=='rdst':
  from aeon.transformations.collection.shapelet_based import RandomDilatedShapeletTransform
  return RandomDilatedShapeletTransform(max_shapelets=256,proba_normalization=.8,threshold_percentiles=[5,10],alpha_similarity=.5,random_state=7,n_jobs=1)
 raise ValueError('UNKNOWN_TRANSFORM')
class NumericFeatures:
 def __init__(self,ds,view,family,cache):self.ds=ds;self.view=view;self.family=family;self.cache=Path(cache);self.transformer=None;self.lookup=None;self.array=None
 def fit(self,ids):
  if self.family!='control':
   self.transformer=make_transform(self.family);x,_=self.ds.features(ids,self.view);self.transformer.fit(x.transpose(0,2,1));del x
  return self
 def raw(self,ids):
  x,c=self.ds.features(ids,self.view)
  if self.transformer is None:return np.column_stack((x.reshape(len(x),-1),c)).astype(np.float32)
  z=self.transformer.transform(x.transpose(0,2,1)).astype(np.float32)
  if not np.isfinite(z).all():raise ValueError('NONFINITE_TRANSFORM')
  return np.column_stack((z,c)).astype(np.float32)
 def materialize(self,ids):
  self.cache.mkdir(parents=True,exist_ok=True);width=self.raw(ids[:1]).shape[1];size=len(ids)*width*4
  if size>256*1024**2:raise RuntimeError('INCOMPLETE_TRANSFORM_CACHE_LIMIT')
  self.array=np.lib.format.open_memmap(self.cache/'transformed.npy',mode='w+',dtype=np.float32,shape=(len(ids),width));self.lookup=np.full(len(self.ds.meta),-1,np.int64)
  for first in range(0,len(ids),128):self.array[first:first+128]=self.raw(ids[first:first+128]);self.lookup[ids[first:first+128]]=np.arange(first,min(first+128,len(ids)))
  self.array.flush();return self
 def get(self,ids):
  if self.array is None:return self.raw(ids)
  i=self.lookup[ids]
  if np.any(i<0):raise ValueError('TRANSFORM_CACHE_ROW_NOT_AVAILABLE')
  return np.array(self.array[i],copy=True)
 def clear(self):
  if self.array is not None:self.array._mmap.close();self.array=None
  p=self.cache/'transformed.npy'
  if p.exists():p.unlink()
class Calibrator:
 def fit(self,q,logits,y,d):
  self.offset=np.empty((2,2,3))
  for b in range(2):
   for s in range(2):
    for k,tau in enumerate(QUANTILES):self.offset[b,s,k]=np.quantile(y[:,b,s]-q[:,b,s,k],tau)
  from scipy.optimize import minimize_scalar
  def loss(temp):return -np.log(np.maximum(softmax(logits/temp)[np.arange(len(d)),d],1e-12)).mean()
  result=minimize_scalar(loss,bounds=(.25,4),method='bounded',options={'xatol':1e-8})
  candidates=[.25,float(result.x),4.];self.temperature=min(candidates,key=loss);return self
 def apply(self,q,logits):return project(q+self.offset),logits/self.temperature

def render(pattern):
 """One past-only grayscale chart, fixed geometry, no future prices/text."""
 w=len(pattern);height,width=(64,60) if w==20 else (96,180)
 if w not in (20,60) or pattern.shape!=(w,6) or not np.isfinite(pattern).all():raise ValueError('RENDER_CONTRACT')
 image=np.zeros((height,width),np.float32);price_bottom=int(height*.75)-1
 def py(p):return int(round((1-np.clip(p,0,1))*price_bottom))
 def line(x0,y0,x1,y1,value):
  n=max(abs(x1-x0),abs(y1-y0))+1
  xs=np.rint(np.linspace(x0,x1,n)).astype(int);ys=np.rint(np.linspace(y0,y1,n)).astype(int);image[ys,xs]=value
 for i,r in enumerate(pattern):
  x=3*i+1;line(x,py(r[2]),x,py(r[1]),1.);image[py(r[0]),max(0,x-1):x+1]=1.;image[py(r[3]),x:min(width,x+2)]=1.
  vh=int(round(np.clip(r[4],0,1)*(height-price_bottom-3)));image[height-vh:height,x]=.6
  if i:line(3*(i-1)+1,py(pattern[i-1,5]),x,py(r[5]),.75)
 return image

def cnn_model():
 import torch
 from torch import nn
 model=nn.Sequential() # The nested module has a deliberately small spatial head.
 class Chart(nn.Module):
  def __init__(self):
   super().__init__();self.conv=nn.Sequential(nn.Conv2d(1,8,3,padding=1),nn.ReLU(),nn.MaxPool2d((2,1)),nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.MaxPool2d((2,1)),nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d((2,1)),nn.AdaptiveAvgPool2d((1,10)));self.head=nn.Linear(324,15)
  def forward(self,image,context):return self.head(torch.cat((self.conv(image).flatten(1),context),1))
 model=Chart()
 if sum(x.numel() for x in model.parameters())>50000:raise ValueError('CNN_PARAMETER_CAP')
 return model

def torch_loss(raw,y,d):
 import torch
 q=raw[:,:12].reshape(-1,2,2,3);tau=torch.tensor(QUANTILES,dtype=q.dtype,device=q.device);err=y[:,:,:,None]-q;loss=torch.maximum(tau*err,(tau-1)*err)
 return loss[:,0].mean()+.5*loss[:,1].mean()+.2*torch.nn.functional.cross_entropy(raw[:,12:],d)
class EpochChoice:
 def __init__(self,minimum,patience,profile_only=False):self.minimum=1 if profile_only else minimum;self.patience=patience;self.best=None;self.best_epoch=0;self.stale=0
 def consider(self,epoch,key):
  if epoch<self.minimum:return False
  if self.best is None or key<self.best:self.best=key;self.best_epoch=epoch;self.stale=0;return True
  self.stale+=1;return False
 def stop(self,epoch):return epoch>=self.minimum and self.stale>=self.patience

class Learned:
 def __init__(self,ds,view,family,l2,seed,cache):self.ds=ds;self.view=view;self.family=family;self.l2=l2;self.seed=seed;self.cache=Path(cache)
 def batch(self,ids):
  import torch
  if self.family=='cnn':
   x,c=self.ds.features(ids,self.view);image=np.stack([render(v) for v in x])[:,None];return torch.from_numpy(image),torch.from_numpy(self.scale.transform(c))
  return (torch.from_numpy(self.scale.transform(self.features.get(ids))),)
 def forward(self,ids):
  args=self.batch(ids);return self.model(*args)
 def predict(self,ids):
  import torch
  self.model.eval();out=[]
  with torch.no_grad():
   for i in range(0,len(ids),self.batch_size):out.append(self.forward(ids[i:i+self.batch_size]).numpy())
  return unpack(np.vstack(out))
 def fit(self,train,validation,budget,epochs=None,progress=None,profile_only=False):
  import torch
  torch.set_num_threads(1);torch.manual_seed(self.seed);np.random.seed(self.seed);fit_started=time.process_time();self.measurements={'epoch_train_cpu_seconds':[],'epoch_validation_cpu_seconds':[]}
  if self.family=='cnn':
   self.batch_size=32;self.scale=Scale().fit(lambda ids:self.ds.features(ids,self.view)[1],train);self.model=cnn_model();maximum=20;minimum=5;patience=3;decay=.0001
  else:
   self.batch_size=256;self.features=NumericFeatures(self.ds,self.view,self.family,self.cache).fit(train)
   if self.family!='control':self.features.materialize(np.r_[train,validation] if validation is not None else train)
   self.scale=Scale().fit(self.features.get,train);self.model=torch.nn.Linear(len(self.scale.mean),15);maximum=80;minimum=10;patience=5;decay=self.l2
  if epochs is not None and epochs<minimum and not profile_only:raise ValueError('FINAL_EPOCHS_BELOW_FROZEN_MINIMUM')
  choice=EpochChoice(minimum,patience,profile_only);optimizer=torch.optim.Adam(self.model.parameters(),lr=.001,weight_decay=decay);best=None;self.measurements['setup_cpu_seconds']=time.process_time()-fit_started
  for epoch in range(1,(epochs if epochs is not None else maximum)+1):
   epoch_started=time.process_time();self.model.train();rng=np.random.default_rng(self.seed+epoch);order=rng.permutation(train)
   for i in range(0,len(order),self.batch_size):
    budget.check();ids=order[i:i+self.batch_size];optimizer.zero_grad(set_to_none=True);raw=self.forward(ids);y=torch.from_numpy(self.ds.targets[ids].astype(np.float32));d=torch.from_numpy(self.ds.direction[ids].astype(np.int64));loss=torch_loss(raw,y,d)
    if not torch.isfinite(loss):raise RuntimeError('INVALID_NONFINITE_TRAIN_LOSS')
    loss.backward();optimizer.step()
   self.measurements['epoch_train_cpu_seconds'].append(time.process_time()-epoch_started);validation_started=time.process_time()
   if validation is not None:
    q,logits=self.predict(validation);score=scores(q,logits,self.ds.targets[validation],self.ds.direction[validation]);key=(score['lower_pinball'],score['direction_logloss'])
    self.measurements['epoch_validation_cpu_seconds'].append(time.process_time()-validation_started)
    if choice.consider(epoch,key):best=copy.deepcopy(self.model.state_dict())
    if progress:progress({'epoch':epoch,'score':score,'best_epoch':choice.best_epoch})
    if epochs is None and choice.stop(epoch):break
   elif progress:progress({'epoch':epoch,'fixed_final_epochs':epochs})
  if validation is not None:self.model.load_state_dict(best)
  self.best_epoch=choice.best_epoch if validation is not None else epochs
  return self
 def release_training_cache(self):
  if self.family!='cnn':self.features.clear()
 def artifact(self):
  return {'family':self.family,'view':self.view,'l2':self.l2,'seed':self.seed,'scale':self.scale,'state':self.model.state_dict(),'transformer':None if self.family in ('cnn','control') else self.features.transformer,'best_epoch':self.best_epoch}
 @classmethod
 def restore(cls,ds,obj,cache):
  import torch
  model=cls(ds,obj['view'],obj['family'],obj['l2'],obj['seed'],cache);model.scale=obj['scale'];model.best_epoch=obj['best_epoch']
  if model.family=='cnn':model.model=cnn_model();model.batch_size=32
  else:
   model.features=NumericFeatures(ds,model.view,model.family,cache);model.features.transformer=obj['transformer'];model.model=torch.nn.Linear(len(model.scale.mean),15);model.batch_size=256
  model.model.load_state_dict(obj['state']);return model

def normalized_mass_matrix(x):
 x=np.asarray(x,dtype=np.float64);mean=x.mean(1,keepdims=True);std=x.std(1,keepdims=True);constant=std[:,0]<1e-12
 z=(x-mean)/np.maximum(std,1e-12);z[constant]=0;return z,constant

def mass_distances(query,library):
 q,qc=normalized_mass_matrix(np.atleast_2d(query));l,lc=normalized_mass_matrix(library);width=q.shape[1]
 sq=np.maximum(0.,2*width-2*q@l.T);sq=np.where(qc[:,None]&lc[None,:],0.,np.where(qc[:,None]^lc[None,:],width,sq));return np.sqrt(sq)
class Analog:
 def __init__(self,ds,view,k):self.ds=ds;self.view=view;self.k=k;self.library={};self.catalogue=[]
 def fit(self,train):
  self.train=np.array(train);self.prior_q=np.quantile(self.ds.targets[train],QUANTILES,axis=0).transpose(1,2,0);self.prior_p=np.bincount(self.ds.direction[train],minlength=3)/len(train)
  for a in (0,1):
   ids=train[self.ds.meta['asset'][train]==a];ids=ids[np.linspace(0,len(ids)-1,min(2048,len(ids)),dtype=int)];x,_=self.ds.features(ids,self.view);self.library[a]=(ids,x.reshape(len(x),-1).astype(np.float64))
  return self
 def predict(self,ids,budget=None):
  q=np.empty((len(ids),2,2,3));prob=np.empty((len(ids),3));self.support=np.zeros(len(ids),np.int16);tf,w=map(int,self.view.split('x'));separation=max(DAY,tf*w*MINUTE)
  for a in (0,1):
   where=np.flatnonzero(self.ds.meta['asset'][ids]==a);lib,xlib=self.library[a]
   for offset in range(0,len(where),64):
    if budget:budget.check()
    pos=where[offset:offset+64];x,_=self.ds.features(ids[pos],self.view);dist=mass_distances(x.reshape(len(x),-1),xlib)
    for j,at in enumerate(pos):
     chosen=[]
     for candidate in np.argsort(dist[j],kind='stable'):
      row=int(lib[candidate]);origin=int(self.ds.meta['origin'][row])
      if all(abs(origin-int(self.ds.meta['origin'][v]))>=separation for v in chosen):chosen.append(row)
      if len(chosen)==self.k:break
     n=len(chosen);self.support[at]=n;weight=n/(n+20)
     empirical=np.quantile(self.ds.targets[chosen],QUANTILES,axis=0).transpose(1,2,0);freq=np.bincount(self.ds.direction[chosen],minlength=3)/n
     q[at]=weight*empirical+(1-weight)*self.prior_q;prob[at]=weight*freq+(1-weight)*self.prior_p
     if len(self.catalogue)<4:self.catalogue.append({'query_row':int(ids[at]),'analogue_rows':chosen[:3],'neighbours':n})
  return project(q),np.log(np.maximum(prob,1e-12))
