"""Frozen independent forecasting data, with no strategy or execution imports."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
MINUTE=60_000; HOUR=60*MINUTE; DAY=24*HOUR
PROTOCOL_SHA='121942c4eaa70e831fc46e8ac07cdfa1fdbd458760cd200b2c90e4895736f626'
FIELDS=('open','high','low','close','volume','SMA20')
META=np.dtype([('origin','<i8'),('asset','i1'),('sigma','<f8'),('reference','<f8'),('entry','<f8'),('expiry','<i8'),('observed','?')])
def ms(value):return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1000)
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write_json(path,obj):
 p=Path(path);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');t.replace(p)
def protocol(path):
 if sha(path)!=PROTOCOL_SHA:raise ValueError('FROZEN_PROTOCOL_HASH_MISMATCH')
 return json.loads(Path(path).read_text())
def validate(times,values,step):
 if len(times)!=len(values) or not len(times) or np.any(np.diff(times)!=step) or np.any(times%step):raise ValueError('REAL_BAR_TIMESTAMPS_GAP_DUPLICATE_OR_ALIGNMENT')
 if not np.isfinite(values).all():raise ValueError('NONFINITE_BARS')
 o,h,l,c,v=values.T
 if np.any(values[:,:4]<=0) or np.any(v<0) or np.any(l>np.minimum(o,c)) or np.any(h<np.maximum(o,c)) or np.any(l>h):raise ValueError('INVALID_OHLCV')
def aggregate(times,values,step):
 source=int(times[1]-times[0]);validate(times,values,source)
 if step%source:raise ValueError('NO_SYNTHETIC_UPSAMPLING')
 width=step//source;first=((int(times[0])+step-1)//step)*step;end=((int(times[-1])+source)//step)*step
 keep=(times>=first)&(times<end);t=times[keep];v=values[keep]
 if len(t)%width:raise ValueError('PARTIAL_BIN')
 b=v.reshape(-1,width,5)
 return t[::width],np.column_stack((b[:,0,0],b[:,:,1].max(1),b[:,:,2].min(1),b[:,-1,3],b[:,:,4].sum(1)))
def sma20(values):
 out=np.full((len(values),6),np.nan);out[:,:5]=values
 s=np.r_[0.,np.cumsum(values[:,3])];out[19:,5]=(s[20:]-s[:-20])/20
 return out
def pattern(times,values,origin,tf,window):
 j=int(np.searchsorted(times+tf,origin,side='right'))-1
 if j<window-1 or origin-(int(times[j])+tf)>=tf:return None
 x=values[j-window+1:j+1].copy()
 if not np.isfinite(x).all():return None
 prices=x[:,[0,1,2,3,5]];lo=prices.min();hi=prices.max();v=x[:,4].max()
 x[:,[0,1,2,3,5]]=(prices-lo)/max(hi-lo,1e-12);x[:,4]/=max(v,1e-12)
 return x.astype(np.float32),int(times[j])+tf,float(values[j,3])
def targets(open_,high,low,close,sigma):
 """Exact whole horizon; lower/upper x long/short MFE in sigma units."""
 if len(open_)!=1440 or any(len(v)!=1440 for v in (high,low,close)):raise ValueError('WHOLE_24H_REQUIRED')
 if not np.isfinite(sigma) or sigma<=0:raise ValueError('INVALID_SCALE')
 e=float(open_[0]);result=np.zeros((2,2),np.float64);stop_indices=[]
 for a,side in enumerate((1,-1)):
  stop=e*np.exp(-side*sigma);hits=low<=stop if side==1 else high>=stop
  first=int(np.flatnonzero(hits)[0]) if hits.any() else 1440
  favorable=side*np.log((high if side==1 else low)/e)/sigma
  guaranteed=max(0.,float(favorable[:first].max())) if first else 0.
  if first==1440:lower=upper=guaranteed
  else:
   at_open=max(0.,side*np.log(open_[first]/e)/sigma);lower=max(guaranteed,at_open)
   gap=open_[first]<=stop if side==1 else open_[first]>=stop
   upper=lower if gap else max(lower,float(favorable[first]))
  result[:,a]=lower,upper;stop_indices.append(first)
 ret=np.log(close[-1]/e);direction=0 if ret>.25*sigma else 1 if ret<-.25*sigma else 2
 return result,direction,stop_indices
def target_batch(values,indices,sigmas):
 """Bounded vectorization, never create an all-origin future-path matrix."""
 idx=np.asarray(indices)[:,None]+np.arange(1440)[None,:]
 o=np.asarray(values[idx,0]);h=np.asarray(values[idx,1]);l=np.asarray(values[idx,2]);c=np.asarray(values[idx[:,-1],3]);e=o[:,0]
 out=np.zeros((len(indices),2,2));grid=np.arange(1440)[None,:]
 for a,side in enumerate((1,-1)):
  stop=e*np.exp(-side*sigmas);hit=l<=stop[:,None] if side==1 else h>=stop[:,None]
  exists=hit.any(1);first=np.where(exists,hit.argmax(1),1440);safe=np.minimum(first,1439)
  fav=side*np.log((h if side==1 else l)/e[:,None])/sigmas[:,None]
  before=np.maximum(0.,np.where(grid<first[:,None],fav,0.).max(1))
  opening=np.maximum(0.,side*np.log(o[np.arange(len(o)),safe]/e)/sigmas)
  lower=np.maximum(before,np.where(exists,opening,0.));gap=o[np.arange(len(o)),safe]<=stop if side==1 else o[np.arange(len(o)),safe]>=stop
  upper=np.maximum(lower,np.where(exists&~gap,fav[np.arange(len(o)),safe],0.));out[:,0,a]=lower;out[:,1,a]=upper
 ret=np.log(c/e);directions=np.where(ret>.25*sigmas,0,np.where(ret<-.25*sigmas,1,2)).astype(np.int8)
 return out,directions
def mature(meta,start,end):return (meta['origin']>=start)&(meta['origin']<end)&meta['observed']&(meta['expiry']<=end)
def _read_csv(path):
 with Path(path).open() as f:rows=list(csv.DictReader(f))
 return np.array([int(r['open_time_ms']) for r in rows],np.int64),np.array([[float(r[k]) for k in FIELDS[:5]] for r in rows])
def prepare(repo,output,protocol_path):
 import pyarrow.parquet as pq
 repo=Path(repo);output=Path(output);lock=protocol(protocol_path);output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 train_start=ms(lock['train'][0]);cut=ms(lock['train'][1]);end=ms(lock['check'][1]);warm=train_start-DAY
 origins=np.arange(train_start,end,HOUR,dtype=np.int64);n=2*len(origins)
 meta=np.lib.format.open_memmap(output/'metadata.npy',mode='w+',dtype=META,shape=(n,));meta['origin']=np.repeat(origins,2);meta['asset']=np.tile([0,1],len(origins));meta['entry']=np.nan;meta['sigma']=np.nan;meta['reference']=np.nan;meta['expiry']=meta['origin']+MINUTE+DAY;meta['observed']=False
 views={f'{tf}x{w}':np.lib.format.open_memmap(output/f'features-{tf}x{w}.npy',mode='w+',dtype=np.float32,shape=(n,w,6)) for tf in lock['features']['timeframes_minutes'] for w in lock['features']['windows_bars']}
 context=np.lib.format.open_memmap(output/'context.npy',mode='w+',dtype=np.float32,shape=(n,8,4));targets_all=np.full((n,2,2),np.nan);directions=np.full(n,-1,np.int8);source={str(protocol_path):sha(protocol_path)};latest=np.lib.format.open_memmap(output/'feature-bar-ends.npy',mode='w+',dtype=np.int64,shape=(n,8))
 origin_indices=(origins-warm)//MINUTE
 parent=repo/'runtime/var/research-datasets/forecast-independent-20261021-v1'
 for asset,symbol in enumerate(('BTCUSDT','SOLUSDT')):
  count=(end-warm)//MINUTE;minutes=np.lib.format.open_memmap(output/f'minutes-{symbol}.npy',mode='w+',dtype=np.float64,shape=(count,5));actual=np.empty(count,np.int64);cursor=0
  def append(ts,v):
   nonlocal cursor
   if cursor+len(ts)>count:raise ValueError('EXCESS_SOURCE_ROWS')
   actual[cursor:cursor+len(ts)]=ts;minutes[cursor:cursor+len(ts)]=v;cursor+=len(ts)
  wp=parent/'execution-warmup'/symbol/'execution-1m.csv';ts,v=_read_csv(wp);append(ts,v);source[str(wp)]=sha(wp)
  bp=repo/'runtime/var/data/normalized'/f'bybit-{symbol}-execution-1m.parquet';source[str(bp)]=sha(bp)
  for b in pq.ParquetFile(bp).iter_batches(batch_size=4096,columns=['open_time_ms',*FIELDS[:5]]):
   d=b.to_pydict();append(np.array(d['open_time_ms'],np.int64),np.column_stack([d[k] for k in FIELDS[:5]]).astype(np.float64))
  tp=parent/'execution-tail'/symbol/'execution-1m.csv';ts,v=_read_csv(tp);append(ts,v);source[str(tp)]=sha(tp);del ts,v
  if cursor!=count or not np.array_equal(actual,np.arange(warm,end,MINUTE)):raise ValueError('ACTUAL_MINUTE_SEQUENCE_OR_COUNT_MISMATCH')
  validate(actual,minutes,MINUTE);minutes.flush()
  hp=repo/'reports/btc-split-sol-cover-20261018'/f'data-warmup-{symbol}-1h.csv';ht,hv=_read_csv(hp);source[str(hp)]=sha(hp);validate(ht,hv,HOUR)
  overlap_t,overlap_v=aggregate(actual[:1440],minutes[:1440],HOUR)
  prior=hv[np.searchsorted(ht,overlap_t)]
  if not np.allclose(prior,overlap_v,rtol=1e-12,atol=1e-8):raise ValueError('WARMUP_HOURLY_OVERLAP_MISMATCH')
  bt,bv=aggregate(actual[1440:],minutes[1440:],HOUR)
  if ht[-1]+HOUR!=bt[0]:raise ValueError('HOURLY_WARMUP_BOUNDARY_GAP')
  hourly_t=np.r_[ht,bt];hourly_v=np.vstack((hv,bv));validate(hourly_t,hourly_v,HOUR)
  panels={1:(actual,sma20(minutes)),15:None,60:(hourly_t,sma20(hourly_v)),240:None}
  for tf in (15,240):
   t,v=aggregate(actual,minutes,tf*MINUTE) if tf==15 else aggregate(hourly_t,hourly_v,tf*MINUTE);panels[tf]=(t,sma20(v))
  for i,t in enumerate(origins):
   row=2*i+asset;j=int(np.searchsorted(hourly_t+HOUR,t,side='right'))-1
   if j<168:raise ValueError('HOURLY_SIGMA_WARMUP_SHORT')
   close=hourly_v[j-168:j+1,3];sigma=float(np.std(np.diff(np.log(close)),ddof=1)*np.sqrt(24))
   if not np.isfinite(sigma) or sigma<=0:raise ValueError('INVALID_SCALE')
   last=int(origin_indices[i])-1;meta[row]['sigma']=sigma;meta[row]['reference']=minutes[last,3]
   entry=int(origin_indices[i])+1
   if entry<count:meta[row]['entry']=minutes[entry,0]
   meta[row]['observed']=entry+1440<=count
   for vi,((key,array),(tf,w)) in enumerate(zip(views.items(),[(tf,w) for tf in lock['features']['timeframes_minutes'] for w in lock['features']['windows_bars']])):
    result=pattern(*panels[tf],int(t),tf*MINUTE,w)
    if result is None:raise ValueError(f'FEATURE_WARMUP_OR_STALE {symbol} {t} {key}')
    x,available,lastclose=result;array[row]=x;latest[row,vi]=available;context[row,vi]=[sigma,meta[row]['reference']/lastclose,(t-available)/(tf*MINUTE),asset]
  observed=np.flatnonzero(meta['observed']&(meta['asset']==asset))
  for first in range(0,len(observed),128):
   ids=observed[first:first+128];indices=(meta['origin'][ids]+MINUTE-warm)//MINUTE;y,d=target_batch(minutes,indices,meta['sigma'][ids]);targets_all[ids]=y;directions[ids]=d
  del panels,minutes,actual,ht,hv,hourly_t,hourly_v
  print(json.dumps({'event':'asset_prepared','asset':symbol,'origins':len(origins),'seconds':time.monotonic()-started}),flush=True)
 for a in views.values():a.flush()
 context.flush();latest.flush();meta.flush()
 for label,mask in [('train',meta['origin']<cut),('check',meta['origin']>=cut)]:
  ids=np.flatnonzero(mask);np.savez(output/f'labels-{label}.npz',ids=ids,target=targets_all[ids],direction=directions[ids])
 np.save(output/'origin_ids.npy',np.arange(n,dtype=np.int64))
 manifest={'schema':'coinmaster.forecast.prepared.v1','protocol_sha256':PROTOCOL_SHA,'sources':source,'views':list(views),'rows':n,'hourly_origins':len(origins),'minute_start_ms':warm,'minute_end_exclusive_ms':end,'context_fields':['sigma','reference/last_panel_close','closed_panel_age/TF','asset_indicator'],'label_axis':['bound_lower_upper','side_long_short'],'direction_classes':['UP','DOWN','NEUTRAL'],'check_performance':'SEALED_NOT_INSPECTED','feature_rows_all_valid':True,'feature_bar_ends_max_minus_origin_ms':int((latest-meta['origin'][:,None]).max()),'prepare_seconds':time.monotonic()-started,'source_code_sha256':sha(__file__)}
 manifest['artifacts']={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()};write_json(output/'manifest.json',manifest);print(json.dumps({k:v for k,v in manifest.items() if k not in ('sources','artifacts')}),flush=True)
_VERIFIED_DATASETS=set()
def verify_prepared(path):
 p=Path(path);manifest=json.loads((p/"manifest.json").read_text())
 if manifest.get("protocol_sha256")!=PROTOCOL_SHA:raise ValueError("PREPARED_PROTOCOL_HASH_MISMATCH")
 identity=(str(p.resolve()),sha(p/"manifest.json"))
 if identity not in _VERIFIED_DATASETS:
  for name,record in manifest["artifacts"].items():
   f=p/name
   if not f.is_file() or f.stat().st_size!=record["bytes"] or sha(f)!=record["sha256"]:raise ValueError("PREPARED_ARTIFACT_HASH_MISMATCH "+name)
  _VERIFIED_DATASETS.add(identity)
 return manifest
class Dataset:
 def __init__(self,path,protocol_path,allow_check=False):
  self.path=Path(path);self.lock=protocol(protocol_path);self.manifest=verify_prepared(self.path);self.meta=np.load(self.path/'metadata.npy',mmap_mode='r');self.context=np.load(self.path/'context.npy',mmap_mode='r');self.views=self.manifest['views'];self._features={};self.targets=np.full((len(self.meta),2,2),np.nan);self.direction=np.full(len(self.meta),-1,np.int8)
  for part in (['train','check'] if allow_check else ['train']):
   with np.load(self.path/f'labels-{part}.npz') as z:self.targets[z['ids']]=z['target'];self.direction[z['ids']]=z['direction']
  self.allow_check=allow_check
 def features(self,ids,view):
  if view not in self._features:self._features[view]=np.load(self.path/f'features-{view}.npy',mmap_mode='r')
  x=np.array(self._features[view][ids],copy=True);c=np.array(self.context[ids,self.views.index(view)],copy=True)
  return x,c
 def rows(self,start,end):
  a,b=ms(start),ms(end)
  if not self.allow_check and b>ms(self.lock['train'][1]):raise ValueError('CHECK_LABELS_SEALED')
  ids=np.flatnonzero(mature(self.meta,a,b))
  if np.any(self.direction[ids]<0) or not np.isfinite(self.targets[ids]).all():raise ValueError('UNOBSERVED_OR_SEALED_LABELS')
  return ids
 def x(self,ids,view):
  x,c=self.features(ids,view);return np.column_stack((x.reshape(len(x),-1),c)).astype(np.float32)
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);a=p.parse_args();prepare(a.repo,a.output,a.protocol)
if __name__=='__main__':main()
