"""Causal joint numeric features for the bounded AI cycle; no trading imports."""
from pathlib import Path
import csv
import numpy as np
from .forecast_independent_data import HOUR, MINUTE, DAY, aggregate, mature, Dataset as LegacyDataset, ms as legacy_ms
from datetime import datetime,timezone
def utc_boundary(value):
 dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
 if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
 return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def ms(value):return legacy_ms(utc_boundary(value))
class Dataset(LegacyDataset):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  for key in ("train","check"):
   if key in self.lock:self.lock[key]=[utc_boundary(v) for v in self.lock[key]]
  for key in ("final_fit_end","calibration_end"):
   if key in self.lock:self.lock[key]=utc_boundary(self.lock[key])
 def rows(self,start,end):return super().rows(utc_boundary(start),utc_boundary(end))
ASSETS=("BTCUSDT","SOLUSDT")
FIELDS=("r1","body","upper_wick","lower_wick","range","volume_deviation")
def feature_names():
 names=[]
 for a in ASSETS:
  for tf in (15,60,240):
   names += [f"{a}.tf{tf}.lag{lag}.{field}" for lag in range(19,-1,-1) for field in FIELDS]
  names += [f"{a}.{field}" for field in ("sigma","r1h","r4h","r24h","r168h","rv24h","rv168h","sma20_1h","sma20_4h","age15m","age1h","age4h")]
 return names+["joint.corr168","joint.beta168","joint.residual1h","joint.residual4h","joint.residual24h","joint.log_sigma_ratio"]
def read_hourly(path):
 with Path(path).open() as f: rows=list(csv.DictReader(f))
 return np.array([int(r["open_time_ms"]) for r in rows],np.int64),np.array([[float(r[k]) for k in ("open","high","low","close","volume")] for r in rows])
class JointFeatures:
 def __init__(self,prepared,warmup):
  self.prepared=Path(prepared);self.manifest=__import__("json").loads((self.prepared/"manifest.json").read_text())
  self.meta=np.load(self.prepared/"metadata.npy",mmap_mode="r")
  self.start=int(self.manifest["minute_start_ms"])
  self.panels={}
  for a in ASSETS:
   v=np.load(self.prepared/f"minutes-{a}.npy",mmap_mode="r")
   t=self.start+np.arange(len(v))*MINUTE
   ht,hv=read_hourly(Path(warmup)/f"data-warmup-{a}-1h.csv")
   bt,bv=aggregate(t,v,HOUR)
   overlap=bt<=ht[-1]
   if overlap.any():
    j=np.searchsorted(ht,bt[overlap])
    if np.any(j>=len(ht)) or not np.array_equal(ht[j],bt[overlap]) or not np.allclose(hv[j],bv[overlap],rtol=1e-12,atol=1e-8): raise ValueError("HOURLY_WARMUP_OVERLAP")
   keep=ht<bt[0];hour_t=np.r_[ht[keep],bt];hour_v=np.vstack((hv[keep],bv))
   if np.any(np.diff(hour_t)!=HOUR):raise ValueError("HOURLY_WARMUP_GAP")
   p15=aggregate(t,v,15*MINUTE)
   p4=aggregate(hour_t,hour_v,4*HOUR)
   self.panels[a]={15:p15,60:(hour_t,hour_v),240:p4}
 def one(self,origin):
  result=[];sigmas=[];returns=[];rs=[]
  for a in ASSETS:
   ht,hv=self.panels[a][60];j=np.searchsorted(ht+HOUR,origin,side="right")-1
   if j<168: return None
   c=hv[j-168:j+1,3];r=np.diff(np.log(c));sigma=float(np.std(r,ddof=1)*np.sqrt(24))
   if not np.isfinite(sigma) or sigma<=0:return None
   sigmas.append(sigma);returns.append(r);ages=[];smas=[]
   for tf in (15,60,240):
    t,v=self.panels[a][tf];k=np.searchsorted(t+tf*MINUTE,origin,side="right")-1
    if k<39:return None
    x=v[k-19:k+1];prev=v[k-20:k,3];o,h,l,c,vol=x.T
    lv=np.log1p(v[k-39:k+1,4]);prefix=np.r_[0.,np.cumsum(lv)]
    vm=(prefix[20:40]-prefix[:20])/20
    z=np.column_stack((np.log(c/prev),np.log(c/o),np.log(h/np.maximum(o,c)),np.log(np.minimum(o,c)/l),np.log(h/l),lv[20:]-vm))
    z[:,:5]/=sigma*np.sqrt((tf/60)/24)
    result.extend(z.ravel());ages.append((origin-int(t[k])-tf*MINUTE)/HOUR)
    if tf in (60,240):smas.append((c[-1]/v[k-19:k+1,3].mean()-1)/sigma)
   hist=hv[:,3];ret=[np.log(hist[j]/hist[j-n]) for n in (1,4,24,168)];rs.append(ret)
   result += [sigma,*ret,np.std(r[-24:],ddof=1),np.std(r,ddof=1),*smas,*ages]
  var=np.var(returns[0],ddof=1)
  if var<=0 or np.std(returns[1],ddof=1)<=0:return None
  beta=float(np.cov(returns[0],returns[1],ddof=1)[0,1]/var);corr=float(np.corrcoef(returns)[0,1])
  result += [corr,beta,*[rs[1][n]-beta*rs[0][n] for n in range(3)],np.log(sigmas[1]/sigmas[0])]
  z=np.asarray(result,np.float32)
  return z if np.isfinite(z).all() else None
 def build(self,output,limit=None):
  output=Path(output);output.mkdir(parents=True,exist_ok=False)
  origins=np.unique(self.meta["origin"]);origins=origins if limit is None else origins[:limit]
  out=np.lib.format.open_memmap(output/"X_joint.npy",mode="w+",dtype=np.float32,shape=(len(origins),len(feature_names())))
  valid=np.zeros(len(origins),bool)
  for i,t in enumerate(origins):
   z=self.one(int(t));valid[i]=z is not None;out[i]=z if z is not None else np.nan
  out.flush();np.save(output/"valid.npy",valid);np.save(output/"origins.npy",origins)
  return {"origins":len(origins),"valid":int(valid.sum()),"invalid":int((~valid).sum()),"features":len(feature_names()),"bytes":int(out.nbytes)}
def split_ids(meta,valid,start,end,asset=None):
 mask=mature(meta,ms(start),ms(end)) & valid
 if asset is not None: mask &= meta["asset"]==asset
 return np.flatnonzero(mask)
def early_split(meta,ids,fit_end):
 end=ms(fit_end);boundary=end-28*DAY
 train=ids[meta["expiry"][ids]<=boundary]
 val=ids[(meta["origin"][ids]>=boundary)&(meta["expiry"][ids]<=end)]
 if not len(train) or not len(val):raise ValueError("INSUFFICIENT_PURGED_EARLY_STOP_PREFIX")
 return train,val
def project_quantiles(q):
 return np.sort(np.maximum(q,0),axis=-1)
