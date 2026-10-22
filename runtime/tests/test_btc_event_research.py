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

# D90 tests use synthetic prices/labels; no market forecast evaluation.
def test_d90_corrected_direct_support_boundaries():
    from coinmaster.research.btc_event_research import direct_input_start
    r=dict(anchor=600*HOUR,activation=700*HOUR)
    assert direct_input_start(r,900*HOUR)==531*HOUR
    r['anchor']=100*HOUR
    assert direct_input_start(r,900*HOUR)==99*HOUR
    assert direct_input_start(r,2*HOUR)==2*HOUR

def test_d90_causal_completed_days_prefix_and_invalid():
    from coinmaster.research.btc_event_d90 import daily_context
    from coinmaster.research.btc_event_research import WARM, DAY
    v=np.ones((94*1440,5));v[:,:4]=np.repeat(np.arange(1,95),1440)[:,None]
    t=WARM+91*DAY+5*HOUR
    a=daily_context(v,[WARM+90*DAY,t,WARM+91*DAY])
    assert a[0]['state'] is None
    assert a[1]['state']==a[2]['state']==1
    assert a[1]['endpoint']==WARM+91*DAY and a[1]['input_start']==WARM
    assert a[1]==daily_context(v[:91*1440],[t])[0]
    v[91*1440:,:4]=100000
    assert a[1]==daily_context(v,[t])[0]
    v[2,:4]=np.nan
    assert daily_context(v,[t])[0]['state'] is None
    v[:,:4]=100
    z=daily_context(v,[t])[0]
    assert z['state'] is None and z['logreturn90']==0

def test_d90_shared_weights_quantiles_and_empty_unknown_fallback():
    from coinmaster.research.btc_event_d90 import predict, weighted_empirical
    e,x,y=synthetic(24)
    for j,r in enumerate(e):r['daily90']=dict(state=1 if j%2 else None)
    i=20;e[i]['daily90']['state']=1
    before=predict(e,x,y,i,1500*HOUR);f=before['daily90'];pool=f['pool'];cell=f['neighbors']
    assert all(e[j]['daily90']['state']==1 for j in cell)
    assert any(e[j]['daily90']['state'] is None for j in pool)
    assert np.allclose(f['arrays'][2],(np.sum([y[j]['touch'] for j in cell],axis=0)+32*before['prior']['arrays'][2])/(len(cell)+32))
    assert np.all(np.diff(f['arrays'][1],axis=-1)>=0)
    for state in (None,-1):
        e[i]['daily90']['state']=state;after=predict(e,x,y,i,1500*HOUR)
        assert not after['daily90']['supported']
        assert all(np.array_equal(a,b) for a,b in zip(after['daily90']['arrays'],after['prior']['arrays']))
    try:weighted_empirical(y,[],[])
    except ValueError as exc:assert str(exc)=='EMPTY_EVENT_PRIOR_INFEASIBLE'
    else:raise AssertionError('fabricated empty prediction')

def test_d90_missing_invalid_labels_never_fabricate():
    from coinmaster.research.btc_event_d90 import predict
    e,x,y=synthetic(24)
    for r in e:r['daily90']=dict(state=1)
    y[0]['touch'][0][0]=float('nan')
    try:predict(e,x,y,20,1500*HOUR)
    except ValueError as exc:assert str(exc)=='INVALID_TRUTH_NO_FORECAST'
    else:raise AssertionError('fabricated invalid prediction')

def test_d90_predictions_prefix_and_phase_semantics():
    from coinmaster.research.btc_event_d90 import predict as d90_predict
    from coinmaster.research.btc_event_research import predict
    e,x,y=synthetic(40)
    for r in e:r['daily90']=dict(state=1)
    a=d90_predict(e,x,y,30,2200*HOUR);old=predict(e,x,y,30,2200*HOUR)
    assert all(np.array_equal(v,w) for v,w in zip(a['phase']['arrays'],old['phase']['arrays']))
    for arm in x:x[arm][31:]=np.nan
    for j in range(31,40):y[j]={'invalid':True}
    b=d90_predict(e[:31],{k:v[:31] for k,v in x.items()},y,30,2200*HOUR)
    for arm in a:assert all(np.array_equal(v,w) for v,w in zip(a[arm]['arrays'],b[arm]['arrays']))

def test_d90_gate_both_metrics_and_nonworse_phase():
    from coinmaster.research.btc_event_d90 import gate
    c={arm:{task:dict(primary_14d=dict(pass_rule=True,mean=-.1)) for task in ('TP','SL')} for arm in ('prior','phase')}
    assert gate(c)['pass_rule']
    c['phase']['SL']['primary_14d']['mean']=.001
    assert not gate(c)['pass_rule']
    c['phase']['SL']['primary_14d']['mean']=0;c['prior']['TP']['primary_14d']['pass_rule']=False
    assert not gate(c)['pass_rule']

def test_d90_handcomputed_negative_daily_return_and_support():
    from coinmaster.research.btc_event_d90 import daily_context
    from coinmaster.research.btc_event_research import WARM, DAY
    v=np.tile([100.,100.,100.,100.,1.],(92*1440,1));v[90*1440:91*1440,:4]=50
    c=daily_context(v,[WARM+91*DAY+HOUR])[0]
    assert c['state']==-1 and np.isclose(c['logreturn90'],np.log(.5),rtol=0,atol=1e-15)
    assert c['endpoint']==WARM+91*DAY and c['input_start']==WARM

def test_d90_handcomputed_inverseCDF_and_shared_touch_weights():
    from coinmaster.research.btc_event_d90 import weighted_empirical
    # Global pool0,1:32pseudo split16/16; same-state cell1 adds1.
    # CDF at0=16/33; therefore q20=0,q50=q80=10; touch=17/33.
    y={0:dict(D=0,Q=np.zeros((2,3,2)).tolist(),touch=np.zeros((2,3)).tolist()),
       1:dict(D=1,Q=np.full((2,3,2),10.).tolist(),touch=np.ones((2,3)).tolist())}
    p,q,t=weighted_empirical(y,[0,1],[1])
    assert np.array_equal(q,np.tile([0.,10.,10.],(2,3,1)))
    assert np.allclose(t,17/33,rtol=0,atol=1e-15)
    assert np.allclose(p,[16/33,17/33,0],rtol=0,atol=1e-15)

def test_d90_all_output_guards_preserve_bytes_and_reject_source_overlap():
    import tempfile
    from pathlib import Path
    from coinmaster.research.btc_event_d90 import check_outputs, prepare, evaluate, MUTABLE_OUTPUTS
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);prepared=root/'prepared';reference=root/'reference';out=root/'out'
        for path in (prepared,reference,out):path.mkdir()
        for stage,names in [('prepare',MUTABLE_OUTPUTS),('evaluate',MUTABLE_OUTPUTS[2:])]:
            for name in names:
                p=out/name;p.write_bytes(b'preserve exact output bytes')
                before={x.name:x.read_bytes() for x in out.iterdir()}
                try:
                    if stage=='prepare':prepare(prepared,reference,out,root/'missing-protocol')
                    else:evaluate(prepared,reference,out,root/'missing-protocol','no-go')
                except ValueError as exc:assert str(exc)=='OUTPUT_ALREADY_EXISTS:'+name
                else:raise AssertionError('existing output overwritten')
                assert before=={x.name:x.read_bytes() for x in out.iterdir()}
                p.unlink()
        for source in (prepared,reference):
            for candidate in (source,source/'nested',root):
                try:check_outputs(prepared,reference,candidate,'prepare')
                except ValueError as exc:assert str(exc)=='OUTPUT_SOURCE_OVERLAP'
                else:raise AssertionError('source overlap allowed')
        alias=root/'alias';alias.symlink_to(reference,target_is_directory=True)
        try:check_outputs(prepared,reference,alias,'evaluate')
        except ValueError as exc:assert str(exc)=='OUTPUT_SOURCE_OVERLAP'
        else:raise AssertionError('source alias allowed')
