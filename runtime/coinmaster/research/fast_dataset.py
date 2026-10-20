"""One causal FAST-RND dataset. Future minute OHLC is used only by labels."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
import numpy as np

EPS = 1e-12
MINUTE = 60_000_000_000
HOUR = 60 * MINUTE
DAY = 24 * HOUR
HORIZON = 72 * HOUR
PANELS = ("BTC1h","SOL1h","BTC4h","SOL4h","BTC1d","SOL1d")
DURATIONS = (HOUR,HOUR,4*HOUR,4*HOUR,DAY,DAY)
FIELDS = ("open","high","low","close","volume","causal_MA20")
SAMPLE_FIELDS = ("sample_id","decision_ns","split","selected_train","feature_valid",
    "joint_eligible","btc_label","sol_label","btc_ready_ns","sol_ready_ns",
    "horizon_end_ns","btc_ambiguous","sol_ambiguous","censored",
    "future_start_index","future_end_index")

def ns(value):
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())*1_000_000_000

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def validate_bars(times, values, step):
    if len(times)!=len(values) or len(times)==0 or np.any(np.diff(times)!=step):
        raise ValueError("BAR_GAP_DUPLICATE_OR_ALIGNMENT")
    if np.any(times%step) or not np.isfinite(values).all():
        raise ValueError("INVALID_BAR_VALUES_OR_UTC_ALIGNMENT")
    o,h,l,c,v=values.T
    if np.any(values[:,:4]<=0) or np.any(v<0) or np.any(l>np.minimum(o,c)) or np.any(h<np.maximum(o,c)) or np.any(l>h):
        raise ValueError("INVALID_OHLCV")

def aggregate(times, values, step):
    """UTC left-closed/right-open complete groups; never pad missing bars."""
    source_step=int(times[1]-times[0])
    validate_bars(times,values,source_step)
    if step%source_step:raise ValueError("INCOMPATIBLE_AGGREGATION")
    width=step//source_step
    keep=(times>=((times[0]+step-1)//step)*step)&(times<((times[-1]+source_step)//step)*step)
    t=times[keep];v=values[keep]
    if len(t)%width:raise ValueError("INCOMPLETE_AGGREGATION")
    blocks=v.reshape(-1,width,5)
    return t[::width],np.column_stack((blocks[:,0,0],blocks[:,:,1].max(1),
        blocks[:,:,2].min(1),blocks[:,-1,3],blocks[:,:,4].sum(1)))

def with_ma(values):
    result=np.full((len(values),6),np.nan,dtype=np.float64)
    result[:,:5]=values
    if len(values)>=20:
        sums=np.concatenate(([0.],np.cumsum(values[:,3],dtype=np.float64)))
        result[19:,5]=(sums[20:]-sums[:-20])/20
    return result

def window(panel, decision, duration):
    opened,available,values=panel
    j=int(np.searchsorted(available,decision,side="right"))-1
    if j<19:return None
    w=values[j-19:j+1]
    if not np.isfinite(w).all() or np.any(np.diff(opened[j-19:j+1])!=duration):
        return None
    # Last completed bar must be the actual latest bin, not a silently stale gap.
    if decision-available[j]>=duration:return None
    prices=w[:,[0,1,2,3,5]]
    lo=float(prices.min());hi=float(prices.max());mv=float(w[:,4].max())
    x=w.copy()
    x[:,[0,1,2,3,5]]=(prices-lo)/(hi-lo+EPS)
    x[:,4]=w[:,4]/(mv+EPS)
    context=((hi-lo)/w[-1,3],np.log1p(mv),(decision-available[j])/duration)
    return j,x,context

def sigma(panel,decision):
    _,available,values=panel
    j=int(np.searchsorted(available,decision,side="right"))-1
    if j<168:return np.nan
    closes=values[j-168:j+1,3]
    if not np.isfinite(closes).all() or np.any(closes<=0):return np.nan
    return float(np.std(np.diff(np.log(closes)),ddof=0))

def label(minutes, start_ns, decision, price, volatility, end_ns):
    first=int((decision-start_ns)//MINUTE);last=first+72*60
    if decision+HORIZON>end_ns or first<0 or last>len(minutes) or not np.isfinite(volatility) or not np.isfinite(price) or price<=0:
        return -1,-1,False,True
    future=minutes[first:last]
    b=volatility*np.sqrt(72.)
    up=price*np.exp(b);down=price*np.exp(-b)
    high_col,low_col=(0,1) if future.shape[1]==2 else (1,2)
    upper=np.flatnonzero(future[:,high_col]>=up)
    lower=np.flatnonzero(future[:,low_col]<=down)
    u=int(upper[0]) if len(upper) else len(future)
    d=int(lower[0]) if len(lower) else len(future)
    if u==d and u<len(future):return -1,decision+(u+1)*MINUTE,True,False
    if u<d:return 0,decision+(u+1)*MINUTE,False,False
    if d<u:return 1,decision+(d+1)*MINUTE,False,False
    return 2,decision+HORIZON,False,False

def selected_train(decisions, t_end, cap=6000):
    ids=np.flatnonzero(decisions<t_end)
    return set(ids[np.linspace(0,len(ids)-1,min(cap,len(ids)),dtype=np.int64)].tolist()) if len(ids) else set()

def fit_mask(rows, cutoff):
    """Full fixed horizon, not early-touch readiness, controls every fit purge."""
    return np.array([bool(int(r["joint_eligible"])) and int(r["horizon_end_ns"])<cutoff for r in rows])

def build(data_root, repo, output, lock_path):
    from coinmaster.research.native_baseline import ParquetMinuteCursor
    import pyarrow.parquet as pq
    data_root,repo,output=map(Path,(data_root,repo,output))
    lock=json.loads(Path(lock_path).read_text())
    start,end=map(ns,lock["period"])
    if (end-start)%HOUR:raise ValueError("NON_HOURLY_PERIOD")
    output.mkdir(parents=True,exist_ok=False)
    sources={str(Path(lock_path)):digest(lock_path)}
    minute_times=np.arange(start,end,MINUTE,dtype=np.int64)
    minute_values=[];hourly=[];daily=[]
    for symbol in ("BTCUSDT","SOLUSDT"):
        mp=data_root/"normalized"/f"bybit-{symbol}-execution-1m.parquet"
        wp=repo/"reports/btc-split-sol-cover-20261018"/f"data-warmup-{symbol}-1h.csv"
        dp=data_root/"normalized"/f"bybit-{symbol}-daily.parquet"
        for p in (mp,wp,dp):sources[str(p)]=digest(p)
        values=np.empty((len(minute_times),5),dtype=np.float64)
        for i,row in enumerate(ParquetMinuteCursor(mp,start//1_000_000,end//1_000_000)):
            values[i]=[float(row[k]) for k in FIELDS[:5]]
        validate_bars(minute_times,values,MINUTE)
        ht,hv=aggregate(minute_times,values,HOUR)
        # Labels need only minute high/low; discard the larger OHLCV matrix
        # before loading the next asset. Full trajectories reference source.
        minute_values.append(values[:,1:3].copy())
        del values
        with wp.open() as f: warm=list(csv.DictReader(f))
        wt=np.array([int(x["open_time_ms"])*1_000_000 for x in warm],dtype=np.int64)
        wv=np.array([[float(x[k]) for k in FIELDS[:5]] for x in warm])
        validate_bars(wt,wv,HOUR)
        if wt[-1]+HOUR!=start:raise ValueError("WARMUP_BOUNDARY_GAP")
        ht=np.concatenate((wt,ht));hv=np.concatenate((wv,hv))
        validate_bars(ht,hv,HOUR);hourly.append((ht,hv))
        table=pq.read_table(dp,columns=["open_time_ms",*FIELDS[:5]]).to_pydict()
        dt=np.array(table["open_time_ms"],dtype=np.int64)*1_000_000
        dv=np.column_stack([table[k] for k in FIELDS[:5]]).astype(np.float64)
        keep=dt<end;dt,dv=dt[keep],dv[keep]
        validate_bars(dt,dv,DAY);daily.append((dt,dv))
    panels=[]
    for duration in (HOUR,4*HOUR,DAY):
        for a in range(2):
            t,v=daily[a] if duration==DAY else hourly[a] if duration==HOUR else aggregate(*hourly[a],duration)
            panels.append((t,t+duration,with_ma(v)))
    packed={}
    for p,(opened,available,values) in enumerate(panels):
        packed.update({f"p{p}_open_ns":opened,f"p{p}_available_ns":available,f"p{p}_values":values})
    np.savez(output/"panels.npz",**packed)
    decisions=np.arange(start,end,HOUR,dtype=np.int64)
    n=len(decisions)
    features=np.lib.format.open_memmap(output/"features.npy",mode="w+",dtype=np.float32,shape=(n,6,20,6));features[:]=np.nan
    contexts=np.lib.format.open_memmap(output/"context.npy",mode="w+",dtype=np.float32,shape=(n,20));contexts[:]=np.nan
    ends=np.full((n,6),-1,dtype=np.int32)
    t_end=ns(lock["T"][1]);v_end=ns(lock["V"][1]);selected=selected_train(decisions,t_end,lock["train_cap"])
    counts={s:{"samples":0,"features_valid":0,"eligible":0,"ambiguous":0,"censored":0,"selected_train":0,"fit_eligible":0} for s in ("T","V","U")}
    with (output/"samples.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=SAMPLE_FIELDS);writer.writeheader()
        for i,decision in enumerate(decisions):
            split="T" if decision<t_end else "V" if decision<v_end else "U"
            cutoff=t_end if split=="T" else v_end if split=="V" else end
            ok=True
            for p,(panel,duration) in enumerate(zip(panels,DURATIONS)):
                result=window(panel,int(decision),duration)
                if result is None:ok=False;continue
                j,x,c=result;ends[i,p]=j;features[i,p]=x;contexts[i,3*p:3*p+3]=c
            sigmas=[sigma(panels[a],int(decision)) for a in range(2)]
            contexts[i,18:]=sigmas;ok=ok and np.isfinite(contexts[i]).all()
            labels=[]
            for a in range(2):
                j=int(np.searchsorted(panels[a][1],decision,side="right"))-1
                price=panels[a][2][j,3] if j>=0 else np.nan
                labels.append(label(minute_values[a],start,int(decision),price,sigmas[a],end))
            ambiguous=any(x[2] for x in labels);censored=any(x[3] for x in labels)
            eligible=bool(ok and all(x[0]>=0 for x in labels) and not ambiguous and not censored)
            row=dict(sample_id=i,decision_ns=int(decision),split=split,selected_train=int(i in selected),
                feature_valid=int(ok),joint_eligible=int(eligible),btc_label=labels[0][0],sol_label=labels[1][0],
                btc_ready_ns=labels[0][1],sol_ready_ns=labels[1][1],horizon_end_ns=int(decision+HORIZON),
                btc_ambiguous=int(labels[0][2]),sol_ambiguous=int(labels[1][2]),censored=int(censored),
                future_start_index=int((decision-start)//MINUTE),future_end_index=int((decision+HORIZON-start)//MINUTE))
            writer.writerow(row)
            c=counts[split];c["samples"]+=1;c["features_valid"]+=int(ok);c["eligible"]+=int(eligible)
            c["ambiguous"]+=int(ambiguous);c["censored"]+=int(censored);c["selected_train"]+=int(i in selected)
            c["fit_eligible"]+=int(eligible and decision+HORIZON<cutoff and (split!="T" or i in selected))
    features.flush();contexts.flush();np.save(output/"panel_end_indices.npy",ends)
    manifest={"schema":"coinmaster.fast-dataset.v1","panels":PANELS,"fields":FIELDS,"counts":counts,
        "sources":sources,"builder_sha256":digest(__file__),"experiment_lock":lock,"epsilon":EPS,"sigma_ddof":0,
        "first_decision_ns":int(start),"last_decision_ns":int(decisions[-1]),
        "context":"6 triples range/lastclose,log1p(maxvolume),closedbarage/TF; sigmaBTC,sigmaSOL",
        "future_trajectory_reference":"same pinned execution1m source; half-open minute indices in samples.csv",
        "labels":{"UP":0,"DOWN":1,"NONE":2,"unavailable":-1},"purge":"full horizon_end_ns < fit cutoff",
        "U":"saved programmatically; aggregate counts only; no development inspection"}
    manifest["artifacts"]={p.name:{"sha256":digest(p),"bytes":p.stat().st_size} for p in output.iterdir() if p.is_file()}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument("--data-root",type=Path,required=True);p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--lock",type=Path,required=True);a=p.parse_args()
    result=build(a.data_root,a.repo,a.output,a.lock)
    print(json.dumps({"schema":result["schema"],"counts":result["counts"],"output":str(a.output)}))
if __name__=="__main__":main()

