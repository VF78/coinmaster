import csv
import json
from pathlib import Path
import numpy as np
import pytest
from coinmaster.research.fast_dataset import (
    EPS,MINUTE,HOUR,DAY,HORIZON,aggregate,validate_bars,with_ma,window,sigma,
    label,selected_train,fit_mask,build,ns)

def test_utc_aggregation_and_closed_bar_causality():
    t=np.arange(0,8*HOUR,HOUR,dtype=np.int64)
    close=np.arange(100.,108.)
    v=np.column_stack((close,close+2,close-2,close+1,np.ones(8)))
    a,b=aggregate(t,v,4*HOUR)
    assert a.tolist()==[0,4*HOUR]
    np.testing.assert_array_equal(b[0],[100,105,98,104,4])
    long=np.tile(v,(10,1));times=np.arange(len(long))*HOUR
    panel=(times,times+HOUR,with_ma(long))
    before=window(panel,45*HOUR,HOUR)
    changed=long.copy();changed[45:,:4]*=10
    after=window((times,times+HOUR,with_ma(changed)),45*HOUR,HOUR)
    assert before[0]==44
    np.testing.assert_array_equal(before[1],after[1])
    with pytest.raises(ValueError):validate_bars(t[[0,2]],v[[0,2]],HOUR)

def test_ma_ancestry_normalization_zero_volume_and_169_closes():
    n=200;t=np.arange(n,dtype=np.int64)*HOUR
    v=np.column_stack([np.linspace(1,2,n)]*4+[np.zeros(n)])
    values=with_ma(v);panel=(t,t+HOUR,values)
    assert window(panel,38*HOUR,HOUR) is None
    j,x,c=window(panel,39*HOUR,HOUR)
    assert j==38 and np.isfinite(x).all() and (x[:,4]==0).all()
    assert np.isnan(sigma(panel,168*HOUR))
    expected=np.std(np.diff(np.log(v[:169,3])),ddof=0)
    assert sigma(panel,169*HOUR)==expected
    assert x[:,[0,1,2,3,5]].min()==0
    assert x[:,[0,1,2,3,5]].max()<=1

def test_strict_future_barrier_order_ambiguity_and_censor():
    m=np.tile([100.,100.,100.,100.,1.],(72*60+1,1))
    vol=.01;barrier=100*np.exp(vol*np.sqrt(72))
    m[0,1]=barrier+1
    assert label(m,0,0,100,vol,len(m)*MINUTE)==(0,MINUTE,False,False)
    m[0,2]=100*np.exp(-vol*np.sqrt(72))-1
    assert label(m,0,0,100,vol,len(m)*MINUTE)[2]
    # Input bar before the decision is never used by the future mask.
    assert label(m,0,MINUTE,100,vol,len(m)*MINUTE)==(2,MINUTE+HORIZON,False,False)
    assert label(m,0,2*MINUTE,100,vol,len(m)*MINUTE)[3]

def test_selection_before_labels_no_refill_and_full_horizon_purge():
    decisions=np.arange(100,dtype=np.int64)*HOUR
    selected=selected_train(decisions,60*HOUR,7)
    assert len(selected)==7 and 0 in selected and 59 in selected
    eligible=set(range(100))-{0}
    assert len(selected&eligible)==6  # no replacement for unavailable/ambiguous labels
    rows=[{"joint_eligible":"1","horizon_end_ns":str(100)},{"joint_eligible":"1","horizon_end_ns":str(99)}]
    assert fit_mask(rows,100).tolist()==[False,True]

def test_tiny_builder_schema_alignment_and_provenance(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    root=tmp_path/"repo";data=root/"runtime/var/data";norm=data/"normalized";norm.mkdir(parents=True)
    warm=root/"reports/btc-split-sol-cover-20261018";warm.mkdir(parents=True)
    start=ns("2024-09-01T00:00:00Z");end=start+4*DAY
    lock={"period":["2024-09-01T00:00:00Z","2024-09-05T00:00:00Z"],
        "T":["2024-09-01T00:00:00Z","2024-09-03T00:00:00Z"],
        "V":["2024-09-03T00:00:00Z","2024-09-04T00:00:00Z"],
        "U":["2024-09-04T00:00:00Z","2024-09-05T00:00:00Z"],"train_cap":7}
    lp=root/"lock.json";lp.write_text(json.dumps(lock))
    for symbol in ("BTCUSDT","SOLUSDT"):
        minute=[dict(open_time_ms=int(t//1_000_000),open=100.,high=101.,low=99.,close=100.,volume=1.) for t in range(start,end,MINUTE)]
        pq.write_table(pa.Table.from_pylist(minute),norm/f"bybit-{symbol}-execution-1m.parquet")
        daily=[dict(open_time_ms=int(t//1_000_000),open=100.,high=101.,low=99.,close=100.,volume=100.) for t in range(start-50*DAY,end,DAY)]
        pq.write_table(pa.Table.from_pylist(daily),norm/f"bybit-{symbol}-daily.parquet")
        with (warm/f"data-warmup-{symbol}-1h.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=("open_time_ms","open","high","low","close","volume"));w.writeheader()
            for t in range(start-200*HOUR,start,HOUR):w.writerow(dict(open_time_ms=t//1_000_000,open=100,high=101,low=99,close=100,volume=60))
    out=tmp_path/"out";manifest=build(data,root,out,lp)
    features=np.load(out/"features.npy");context=np.load(out/"context.npy");ends=np.load(out/"panel_end_indices.npy")
    assert features.shape==(96,6,20,6) and features.dtype==np.float32 and context.shape==(96,20)
    assert ends.shape==(96,6) and np.isfinite(features).all()
    with (out/"samples.csv").open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==96 and rows[0]["decision_ns"]==str(start)
    assert sum(int(x["selected_train"]) for x in rows)==7
    assert sum(int(x["censored"]) for x in rows)==71
    packed=np.load(out/"panels.npz")
    for p in range(6):
        assert packed[f"p{p}_available_ns"][ends[0,p]]<=start
    assert len(manifest["sources"])==7
    assert all(len(x["sha256"])==64 for x in manifest["artifacts"].values())

