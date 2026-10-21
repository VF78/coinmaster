"""Report-only derivative tables. Never modifies forecasts, models or gates."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
curves=[]
for f in a.job.glob('development/F*/*.curve.json'):
    for row in json.loads(f.read_text()):curves.append(dict(fold=f.parent.name,fit=f.stem,**row))
if curves:pd.DataFrame(curves).to_csv(a.report/'learning-curves.csv',index=False)
evaluation=a.job/'development-evaluation'; forecasts=evaluation/'forecasts.parquet'
if forecasts.exists():
    df=pd.read_parquet(forecasts);meta=np.load(a.job/'prepared/metadata.npy',mmap_mode='r');extra=[]
    for f in a.job.glob('development/F*/*.npz'):
        z=dict(np.load(f));version=f.stem+'-'+f.parent.name+'-'+hashlib.file_digest(f.open('rb'),'sha256').hexdigest()[:12]
        for row,oi in enumerate(z['ids']):
            q=z['q_raw'][row];upper=z['truth_Q_upper'][row];extra.append(dict(fold=f.parent.name,method=f.stem,id=int(oi),Qlong_raw20=float(q[0,0]),Qlong_raw50=float(q[0,1]),Qlong_raw80=float(q[0,2]),Qshort_raw20=float(q[1,0]),Qshort_raw50=float(q[1,1]),Qshort_raw80=float(q[1,2]),truth_Qlong_upper=float(upper[0]),truth_Qshort_upper=float(upper[1]),entry_time=int(meta['entry_time'][oi]),input_start=int(meta['input_start'][oi]),valid=bool(meta['valid'][oi]),censored=not bool(meta['observed'][oi]),abstain=(f.stem.endswith('-knn') and int(z['support'][row])<16),model_version=version))
    df=df.merge(pd.DataFrame(extra),on=['fold','method','id'],validate='one_to_one');cutoffs=pd.read_csv(a.report/'folds.csv');fc=dict(zip(cutoffs[cutoffs.part=='refit'].fold,cutoffs[cutoffs.part=='refit'].cutoff));df['model_index_cutoff']=df.fold.map(fc);df.to_parquet(a.report/'forecasts.parquet',index=False)
    df['month']=pd.to_datetime(df.origin,unit='ms',utc=True).dt.strftime('%Y-%m')
    reliability=[];quantile_metrics=[]
    for (fold,method),g in df.groupby(['fold','method']):
        valid=g.truth_D>=0
        for klass,col in enumerate(['p_UP','p_DOWN','p_NONE']):
            probabilities=g.loc[valid,col].to_numpy();truth=(g.loc[valid,'truth_D'].to_numpy()==klass)
            for k in range(10):
                sel=(probabilities>=k/10)&((probabilities<(k+1)/10) if k<9 else (probabilities<=1))
                reliability.append(dict(fold=fold,method=method,klass=klass,bin=k,N=int(sel.sum()),mean_pred=float(probabilities[sel].mean()) if sel.any() else None,actual_fraction=float(truth[sel].mean()) if sel.any() else None))
        for side in ['Qlong','Qshort']:
            actual=g['truth_'+side].to_numpy();upper=g['truth_'+side+'_upper'].to_numpy()
            for q in [20,50,80]:
                level=q/100;pred=g[side+str(q)].to_numpy();raw=g[side+'_raw'+str(q)].to_numpy();error=actual-pred;rawerror=actual-raw;uppererror=upper-pred
                quantile_metrics.append(dict(fold=fold,method=method,side=side,q=level,N=len(g),pinball=float(np.maximum(level*error,(level-1)*error).mean()),pinball_raw=float(np.maximum(level*rawerror,(level-1)*rawerror).mean()),pinball_upper_sensitivity=float(np.maximum(level*uppererror,(level-1)*uppererror).mean()),coverage=float((actual<=pred).mean()),strict_coverage=float((actual<pred).mean()),tie_fraction=float((actual==pred).mean()),TP_hit_lower_nonstrict=float((actual>=pred).mean()),TP_hit_upper_nonstrict=float((upper>=pred).mean()),TP_hit_lower_strict=float((actual>pred).mean()),TP_hit_upper_strict=float((upper>pred).mean()),zero_fraction=float((pred==0).mean())))
    pd.DataFrame(reliability).to_csv(a.report/'raw-reliability-bins.csv',index=False);pd.DataFrame(quantile_metrics).to_csv(a.report/'quantile-metrics.csv',index=False)
    regimes=pd.read_csv(a.report/'causal-regimes.csv')[['fold','id','regime']];df=df.merge(regimes,on=['fold','id'],how='left',validate='many_to_one');rows=[]
    for level in ('month','regime'):
        for (fold,method,cohort),g in df.groupby(['fold','method',level],dropna=False):
            d=g.truth_D.to_numpy();valid=d>=0;probs=g[['p_UP','p_DOWN','p_NONE']].to_numpy();dl=-np.log(np.maximum(probs[valid,d[valid]],1e-12))
            for task,loss in [('D',dl),*[(side,np.maximum(np.array([.2,.5,.8])*(g['truth_'+side.replace('-','')].to_numpy()[:,None]-g[[side.replace('-','')+str(q) for q in [20,50,80]]].to_numpy()),(np.array([.2,.5,.8])-1)*(g['truth_'+side.replace('-','')].to_numpy()[:,None]-g[[side.replace('-','')+str(q) for q in [20,50,80]]].to_numpy())).mean(1)) for side in ['Q-long','Q-short']]]:
                rows.append(dict(cohort_type=level,cohort=str(cohort),fold=fold,method=method,task=task,N=len(loss),loss=float(loss.mean()) if len(loss) else None))
    pd.DataFrame(rows).to_csv(a.report/'metrics-by-month-regime.csv',index=False)
    # Fixed chronological ten examples; no search for attractive charts/errors.
    ids=np.sort(df.id.unique());chosen=ids[np.linspace(0,len(ids)-1,10,dtype=int)];df[df.id.isin(chosen)].to_csv(a.report/'fixed-ten-origin-forecasts.csv',index=False)
    neighbor=a.job/'development/neighbors.parquet'
    if neighbor.exists():
        nd=pd.read_parquet(neighbor);labels=np.load(a.job/'prepared/labels.npz');ni=nd.neighbor.to_numpy();nd['truth_Qlong_lower']=labels['mfe'][ni,0,0];nd['truth_Qlong_upper']=labels['mfe'][ni,0,1];nd['truth_Qshort_lower']=labels['mfe'][ni,1,0];nd['truth_Qshort_upper']=labels['mfe'][ni,1,1];nd['index_cutoff']=nd.fold.map(fc);nd.to_parquet(a.report/'neighbors.parquet',index=False);nd[nd['query'].isin(chosen)].to_parquet(a.report/'fixed-ten-origin-neighbors.parquet',index=False)
records={str(f.relative_to(a.job)):dict(bytes=f.stat().st_size,sha256=hashlib.file_digest(f.open('rb'),'sha256').hexdigest()) for f in a.job.rglob('*') if f.is_file() and 'uv-cache' not in f.parts}
(a.report/'local-artifact-manifest.json').write_text(json.dumps(dict(root=str(a.job.resolve()),artifacts=records),indent=2)+'\n')
print(json.dumps(dict(curves=len(curves),forecast_report=forecasts.exists(),artifacts=len(records))))
