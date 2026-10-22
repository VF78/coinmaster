import copy
import json
import numpy as np
import unittest
from coinmaster.research import btc_astra_rank as a
from coinmaster.research import btc_event_research as e


def test_contract_availability_and_fixed_cutoff():
    events=[dict(origin=1,label_end=10,input_start=0),dict(origin=12,label_end=21,input_start=11),dict(origin=30,label_end=40,input_start=5)]
    assert a.pool_for(events,2,25).tolist()==[0,1]
    assert a.pool_for(events,2,25,True).tolist()==[]
    with unittest.TestCase().assertRaisesRegex(ValueError,'FIT_AFTER'):a.pool_for(events,1,25)


def test_selection_calendar_nonoverlap_and_debug_past_only():
    rows=[]
    for fold,lo,hi in e.FOLDS+[(None,'2024-11-01','2025-01-01')]:
        for t in range(e.ms(lo),e.ms(hi),4*e.DAY):rows.append(dict(id=str(t),origin=t,entry_time=t+e.MINUTE,label_end=t+e.MINUTE+72*e.HOUR,fold=fold))
    selected,under=a.select(rows)
    assert not under
    assert sum(x['phase']=='evaluation' for x in selected)==24
    for s in selected:
        assert s['fit_cutoff']<=rows[s['index']]['origin']
    for f,_,_ in e.FOLDS:
        take=[rows[s['index']] for s in selected if s['fold']==f and s['phase']=='evaluation']
        assert all(x['entry_time']>=y['label_end'] or y['entry_time']>=x['label_end'] for k,x in enumerate(take) for y in take[k+1:])


def test_harmonic_aggregate_weights_one_cdf_and_missing_global():
    w=a.weights(range(10),range(8),'rank')
    assert np.isclose(sum(w.values()),16)
    assert np.isclose(w[0]-.8,8/np.sum(1/np.arange(1,9)))
    assert np.isclose(sum(a.weights(range(10),[0,1],'daily90').values()),34)
    assert a.weights(range(10))==dict.fromkeys(range(10),1.)
    truths={i:dict(Q=np.full((2,3,2),i).tolist(),touch=np.full((2,3),i%2).tolist(),D=i%3) for i in range(11)}
    before=a.empirical(truths,w)
    truths[10]=dict(Q=np.full((2,3,2),1e8).tolist(),touch=np.ones((2,3)).tolist(),D=2)
    after=a.empirical(truths,w)
    for x,y in zip(before,after):np.testing.assert_array_equal(x,y)


def test_schema_ids_and_no_match_never_drops_rank():
    row=dict(query_id='q',hidden_mapping={f'c{i}':i for i in range(8)})
    obj=dict(query_id='q',ranked_candidate_ids=list(row['hidden_mapping']),no_match=True,evidence='h1[-4:0]')
    assert a.response(obj,row)==list(range(8))
    for change in [dict(ranked_candidate_ids=['c0']*8),dict(no_match=1),dict(extra=True),dict(query_id='wrong')]:
        bad=copy.deepcopy(obj);bad.update(change)
        with unittest.TestCase().assertRaises(ValueError):a.response(bad,row)


def market():
    n=150*24;t=e.WARM+np.arange(n)*e.HOUR;close=100*np.exp(.001*np.sin(np.arange(n)/12)+np.arange(n)/100000)
    bars=np.column_stack((close,close*1.001,close*.999,close,np.ones(n)))
    v=bars.reshape(-1,4,5);h4=np.column_stack((v[:,0,0],v[:,:,1].max(1),v[:,:,2].min(1),v[:,-1,3],v[:,:,4].sum(1)))
    return {1:(t,bars),4:(t[::4],h4)}


def test_packet_future_mutation_roundtrip_and_direction():
    panels=market();origin=e.WARM+120*e.DAY;j=120*24
    row=dict(origin=origin,anchor=origin-20*e.HOUR,extreme=origin-5*e.HOUR,anchor_log=np.log(panels[1][1][j-21,3]),sigma72=.03,direction=1,daily90={'state':1})
    ctx=dict(status='MISSING_CONTEXT',mode='UP',phase32_32=None,durations_hours=None,confirmation_lags_days=None,confirmed_age_hours=None)
    before=a.episode(row,panels,ctx)
    for tf,(t,v) in panels.items():v[t>=origin]*=2
    after=a.episode(row,panels,ctx)
    assert before==after
    inv=market()
    for tf,(t,v) in inv.items():
        old=v.copy();v[:,0]=10000/old[:,0];v[:,3]=10000/old[:,3];v[:,1]=10000/old[:,2];v[:,2]=10000/old[:,1]
    ir=dict(row,anchor_log=np.log(10000)-row['anchor_log'],direction=-1)
    inverse=a.episode(ir,inv,ctx)
    np.testing.assert_allclose(np.array(inverse['h1'])[:,1:5],-np.array(before['h1'])[:,[1,3,2,4]],atol=2e-13)
    np.testing.assert_allclose(inverse['phase32_32'],-np.array(before['phase32_32']),atol=2e-13)


def test_d1_snapshot_causal_and_future_mutation():
    p=market();origin=e.WARM+120*e.DAY
    row=dict(origin=origin,sigma72=.03)
    point=lambda day:dict(bar=e.WARM+day*e.DAY,confirmation=e.WARM+(day+3)*e.DAY,log=np.log(p[1][1][(day+1)*24-1,3]),lag_days=3)
    snap=dict(asof=origin,A=point(50),B=point(100),mode='UP',status='C_D_UNKNOWN',C=None,D=None)
    before=a.d1_context(row,snap,p)
    assert before['P']==0 and len(before['phase32_32'])==64
    assert before['durations_hours']==[50*24,19*24]
    p[1][1][120*24:]*=3
    assert a.d1_context(row,snap,p)==before
    snap['B']['confirmation']=origin+1
    with unittest.TestCase().assertRaisesRegex(ValueError,'UNCONFIRMED'):a.d1_context(row,snap,p)


def test_numeric_d1_scaling_not_query_fitted_and_missing_retained():
    events=[{}]*5;inputs={'state':np.arange(15).reshape(5,3).astype(float),'phase':np.arange(20).reshape(5,4).astype(float)}
    contexts=[dict(phase32_32=np.arange(64).tolist(),durations_hours=[2,3],confirmation_lags_days=[1,2]) for _ in events]
    contexts[1]['phase32_32']=None
    x,y=a.distances(events,inputs,contexts,4,np.arange(4))
    assert np.isfinite(x).all() and np.isfinite(y).all() and len(y)==4
    contexts[4]['phase32_32']=None
    x,y=a.distances(events,inputs,contexts,4,np.arange(4))
    assert np.isfinite(y).all() and len(y)==4


def test_rank_known_positive_and_balanced_null_same_scorer():
    truth=lambda v:dict(Q=np.full((2,3,2),2*v).tolist(),touch=np.full((2,3),v).tolist(),D=v)
    library={i:truth(int(i>=4)) for i in range(8)}
    f=[a.empirical(library,a.weights(range(8),order,'rank')) for order in (list(range(8)),list(reversed(range(8))))]
    loss=[[e.forecast_scores(*forecast,truth(v)) for v in (0,1)] for forecast in f]
    for task in ('TP','SL'):
        assert loss[0][0][task]<loss[1][0][task]
        assert np.isclose(np.mean([x[task] for x in loss[0]]),np.mean([x[task] for x in loss[1]]))


def test_invalid_missing_no_match_all_ids_exact_global_fallback():
    truth=lambda v:dict(Q=np.full((2,3,2),v).tolist(),touch=np.full((2,3),v%2).tolist(),D=v%3)
    library={i:truth(i) for i in range(10)};row=dict(insufficient_support=False,numeric8=list(range(8)),numericD1_8=list(reversed(range(8))))
    prior=a.empirical(library,a.weights(range(10)))
    records=[dict(valid=False,no_match=True,rank=[]),dict(valid=False,no_match=False,rank=[]),dict(valid=True,no_match=True,rank=list(range(8)))]
    scores=[]
    for rec in records:
        local,kind,fallback=a.rank_specs(row,rec)['astra8']
        assert fallback and local==[] and kind=='prior'
        forecast=a.empirical(library,a.weights(range(10),local,kind))
        for x,y in zip(prior,forecast):np.testing.assert_array_equal(x,y)
        scores.append(e.forecast_scores(*forecast,truth(0)))
    assert len(scores)==3 and all(np.isfinite(s['TP']) and np.isfinite(s['SL']) for s in scores)


def test_volume_roundtrip_and_closed_h4_nonboundary_origin():
    p=market();origin=e.WARM+120*e.DAY+e.HOUR
    row=dict(origin=origin,anchor=origin-20*e.HOUR,extreme=origin-5*e.HOUR,anchor_log=np.log(100),sigma72=.03,direction=1,daily90={'state':1})
    for tf,(t,v) in p.items():v[:,4]=np.arange(len(v))+1
    packet=a.episode(row,p,{})
    for tf in (1,4):
        t,v=p[tf];n=np.searchsorted(t+tf*e.HOUR,origin,side='right');z=np.array(packet[f'h{tf}']);logv=np.log1p(v[n-84:n,4]);means=np.array([logv[k-20:k].mean() for k in range(20,84)])
        np.testing.assert_allclose(np.expm1(z[:,5]+means),v[n-64:n,4],rtol=2e-14)
        np.testing.assert_array_equal(z[:,0],(t[n-64:n]+tf*e.HOUR-origin)/e.HOUR)
        assert z[-1,0]<=0 and t[n-1]+tf*e.HOUR<=origin
    assert packet['h4'][-1][0]==-1
