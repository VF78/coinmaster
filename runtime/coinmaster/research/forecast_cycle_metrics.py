"""Pure persisted-forecast metrics; no fitting, strategy or price-path code."""
import numpy as np
from sklearn.metrics import roc_auc_score
from .forecast_cycle_data import project_quantiles
TAU=np.array([.2,.5,.8])
def detail(head,y,raw):
 q=raw if head=="D" else project_quantiles(raw)
 r=dict(brier=None,accuracy=None,AUROC=None,AUROC_macro=None,pinball_by_q=None,strict_exceedance=None,nonstrict_exceedance=None,tie_rate=None,zero_prediction=None)
 if head=="D":
  r["brier"]=float(((q-np.eye(3)[y.astype(int)])**2).sum(1).mean());r["accuracy"]=float((q.argmax(1)==y).mean())
  auc=[float(roc_auc_score(y==k,q[:,k])) if len(np.unique(y==k))==2 else None for k in range(3)]
  r["AUROC"]=auc;r["AUROC_macro"]=float(np.mean(auc)) if None not in auc else None
 else:
  e=y[:,None]-q;r["pinball_by_q"]=np.maximum(TAU*e,(TAU-1)*e).mean(0).tolist()
  r["strict_exceedance"]=(y[:,None]>q).mean(0).tolist();r["nonstrict_exceedance"]=(y[:,None]>=q).mean(0).tolist();r["tie_rate"]=(y[:,None]==q).mean(0).tolist();r["zero_prediction"]=(q==0).mean(0).tolist()
 return r
def monthly_records(meta,ids,y,raw,head,base):
 months=np.array([np.datetime_as_string(np.datetime64(int(t),"ms"),unit="M") for t in meta["origin"][ids]])
 out=[]
 for month in np.unique(months):
  mask=months==month;r={**base,"month":str(month),"N":int(mask.sum()),"unique_days":len(np.unique(meta["origin"][ids][mask]//86400000)),**detail(head,y[mask],raw[mask])};out.append(r)
 return out
def reliability_rows(y,p,base):
 out=[]
 for cls in range(3):
  bins=np.minimum((p[:,cls]*10).astype(int),9)
  for b in range(10):
   mask=bins==b;n=int(mask.sum());out.append({**base,"class":("UP","DOWN","NEUTRAL")[cls],"bin":b,"N":n,"mean_probability":float(p[mask,cls].mean()) if n else None,"observed_frequency":float((y[mask]==cls).mean()) if n else None})
 return out
