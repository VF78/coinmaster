import numpy as np
from coinmaster.research.btc_event_research import Detector, shapes, eligible, choose, START, END, HOUR, MINUTE
from coinmaster.research.btc_pattern_inapp import targets, forecast_scores, block_ci

def feed(prices,split=None):
    d=Detector()
    for j,p in enumerate(prices):d.feed(START+j*HOUR,np.exp(p),.1)
    return d

def test_prefix_and_future_mutation_invariance():
    prices=[0,.12,.25,.13,.02,.15,.28,.16,.04,.17]
    d=feed(prices);prefix=feed(prices[:8]);mut=feed(prices[:8]+[2,-2])
    assert prefix.events==[r for r in d.events if r['origin']<START+8*HOUR]
    assert prefix.events==[r for r in mut.events if r['origin']<START+8*HOUR]
    assert all(r['origin']>r['extreme'] for r in d.events)
    assert all(not r['left_truncated'] for r in d.events)

def test_unknown_left_gap_and_right_censor():
    d=feed([0,.12,.25,.13,.02,.15]);assert len(d.events)==1
    assert {'UNKNOWN_INITIAL','LEFT_TRUNCATED'} <= {r['kind'] for r in d.registry}
    d.feed(START+8*HOUR,1,.1)
    assert 'GAP_RESET' in {r['kind'] for r in d.registry}
    assert d.finish(END)[-1]['kind']=='RIGHT_CENSORED'

def test_threshold_frozen_at_activation():
    d=Detector();d.feed(START,1,.1);d.feed(START+HOUR,np.exp(.2),.01)
    d.feed(START+2*HOUR,np.exp(.15),.001)
    assert not d.events and d.state['direction']==1
    d.feed(START+3*HOUR,np.exp(.09),.03)
    assert d.state['delta']==.03 and d.state['activation']==START+3*HOUR

def test_clock_phase_same_physical_support():
    t=np.arange(20)*HOUR;v=np.sin(np.arange(20)/8)
    r=dict(anchor=2*HOUR,extreme=9*HOUR,origin=19*HOUR,anchor_log=v[2])
    c,p,s=shapes(t,v,r,.2)
    assert len(c)==len(p)==64 and s==[2*HOUR,19*HOUR]
    assert c[0]==p[0]==0 and c[-1]==p[-1]
    assert p[31]==p[32]

def test_maturity_scaler_pool_overlap_and_deterministic_ties():
    events=[dict(origin=j*80*HOUR,label_end=(j*80+72)*HOUR,input_start=j*80*HOUR-336*HOUR) for j in range(12)]
    pool=eligible(events,11,1000*HOUR)
    assert all(events[j]['label_end']<=events[11]['input_start'] for j in pool)
    assert choose(np.zeros(len(pool)),pool,events)==list(pool)
    assert choose(np.zeros(len(pool)),pool,events)==choose(np.zeros(len(pool)),pool,events)

def test_target_handpath_ambiguity_bounds_timeout():
    x=np.tile([100,100,100,100,1.],(4320,1));z=targets(x,.1)
    assert z['D']==2 and np.array(z['Q']).sum()==0 and np.array(z['touch']).sum()==0
    x[0,:4]=[100,120,80,100];z=targets(x,.1)
    assert z['D']==-1 and z['Q'][0][1][0]==0 and z['Q'][0][1][1]>0
    assert np.array(z['touch']).sum()==6

def test_uncertainty_rejects_one_occupied_block():
    z=block_ci([-1,-2,-1],[START,START+HOUR,START+2*HOUR],['F1','F2','F3'])
    assert not z['pass_rule'] and z['status']=='INCONCLUSIVE'

def synthetic(n):
    from coinmaster.research.btc_event_research import empirical, predict
    events=[dict(id=str(j),origin=j*80*HOUR,label_end=(j*80+72)*HOUR,input_start=(j*80-336)*HOUR) for j in range(n)]
    inputs=dict(state=np.arange(n*18,dtype=float).reshape(n,18),clock=np.ones((n,64)),phase=np.ones((n,64)))
    truths={j:dict(D=j%3,Q=np.full((2,3,2),j/10).tolist(),touch=np.full((2,3),j%2).tolist()) for j in range(n)}
    return events,inputs,truths

def test_prior_weighted_empirical_and_fallback_all_ids():
    from coinmaster.research.btc_event_research import empirical, predict, weighted_quantiles
    e,x,y=synthetic(12);pool=np.array([0,1]);base=empirical(y,pool)
    assert np.array_equal(base[1],weighted_quantiles(np.array([y[j]['Q'] for j in pool])[:,:,:,0],[1,1]))
    post=empirical(y,pool,[1])
    assert np.allclose(post[2],(8*base[2]+np.array(y[1]['touch']))/9)
    pred=predict(e,x,y,11,1000*HOUR)
    assert not pred['phase']['supported']
    assert all(np.array_equal(a,b) for a,b in zip(pred['phase']['arrays'],pred['prior']['arrays']))
    assert len(pred)==4 # fallback is retained, not removed

def test_predict_future_rows_cannot_influence_pool_scaler_or_ties():
    from coinmaster.research.btc_event_research import predict
    e,x,y=synthetic(24);before=predict(e,x,y,20,1500*HOUR)
    q=e[20];excluded=[j for j,r in enumerate(e) if r['label_end']>min(1500*HOUR,q['input_start'])]
    for arm in x:x[arm][excluded]=1e20
    # Restore the current observed query; only excluded historical/future rows mutate.
    x['state'][20]=np.arange(20*18,21*18);x['clock'][20]=1;x['phase'][20]=1
    for j in excluded:y[j]=dict(D=2,Q=np.ones((2,3,2)).tolist(),touch=np.ones((2,3)).tolist())
    after=predict(e,x,y,20,1500*HOUR)
    for a in before:
        assert before[a]['pool']==after[a]['pool']
        assert before[a]['neighbors']==after[a]['neighbors']
        assert all(np.array_equal(v,w) for v,w in zip(before[a]['arrays'],after[a]['arrays']))

def test_gate_requires_both_metrics_every_control_and_coverage():
    from coinmaster.research.btc_event_research import gate
    m={a:dict(coverage=1.) for a in ('state','clock','phase')}
    c={a:{k:dict(primary_14d=dict(pass_rule=True)) for k in ('TP','SL')} for a in ('prior','state','clock')}
    assert gate(m,c)['pass_rule']
    c['clock']['SL']['primary_14d']['pass_rule']=False
    assert not gate(m,c)['pass_rule']
    c['clock']['SL']['primary_14d']['pass_rule']=True;m['state']['coverage']=.89
    assert not gate(m,c)['pass_rule']

def test_target_requires_full_uncensored_horizon():
    try:targets(np.ones((4319,5)),.1)
    except ValueError as e:assert str(e)=='WHOLE_HORIZON_REQUIRED'
    else:raise AssertionError('censored path accepted')
