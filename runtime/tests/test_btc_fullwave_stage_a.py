import copy
import math
import numpy as np
import unittest
from coinmaster.research.btc_fullwave_stage_a import Detector, DAY, HOUR, WARM, START, END, wave, max_nonoverlap, support_counts
from coinmaster.research.research_rss import peak_rss_bytes
from coinmaster.research.btc_pattern_inapp import response_arrays_future, KEYS

def feed(prices):
    d=Detector();snaps=[]
    for i,p in enumerate(prices):
        d.feed(WARM+i*DAY,p);snaps.append(d.snapshot(WARM+(i+1)*DAY))
    return d,snaps

def test_prefix_invariance_future_mutation_and_distinct_confirmation():
    prices=[100,105,111,125,125,120,110,99,105,110]
    full,snaps=feed(prices)
    for k in range(1,len(prices)+1):
        part,ps=feed(prices[:k]);assert ps[-1]==snaps[k-1]
        _,mut=feed(prices[:k]+[1e6,1,2]);assert mut[k-1]==snaps[k-1]
    assert full.pivots[1]['bar']==WARM+3*DAY # equal 125 retains earliest
    assert full.pivots[1]['confirmation']==WARM+7*DAY
    assert full.pivots[1]['confirmation']>full.pivots[1]['bar']+DAY
    assert all(s['C'] is None and s['D'] is None for s in snaps)
    assert snaps[0]['status']=='UNDECIDED';assert snaps[2]['status']=='NO_CONFIRMED_B'

def test_gap_invalid_symmetric_threshold_and_right_censor():
    d=Detector();d.feed(WARM,100)
    with unittest.TestCase().assertRaisesRegex(ValueError,'D1_GAP'):d.feed(WARM+2*DAY,110)
    with unittest.TestCase().assertRaisesRegex(ValueError,'INVALID_CLOSE'):d.feed(WARM+DAY,float('nan'))
    d,s=feed([121,120,109.99]);assert d.pivots[0]['kind']=='HIGH'
    assert s[-1]['status']=='NO_CONFIRMED_B'
    d,s=feed([100,111,125,110]);assert len(d.pivots)==2;assert s[-1]['status']=='C_D_UNKNOWN'

def test_cross_A_left_truncation_all_triples_and_interval_upper_bound():
    d,_=feed([100,111,125,110,90,100,120,105])
    w=[wave(*d.pivots[i:i+3],i) for i in range(len(d.pivots)-2)]
    assert len(w)==2;assert w[0]['cross_A'];assert all(x['left_truncated'] for x in w)
    assert len(max_nonoverlap(w))==1
    assert w[0]['D']==w[0]['C']['confirmation']

def test_fixed_cutoff_maturity_and_no_seed_input_disjoint_support():
    a=dict(bar=START,log=1);b=dict(bar=START+DAY,log=2,confirmation=START+2*DAY);c=dict(bar=START+3*DAY,log=1.5,confirmation=START+4*DAY)
    w=wave(a,b,c,0);w['h1_complete']=True;q=dict(q=START+100*DAY,A=dict(bar=START+90*DAY))
    assert support_counts([w],q,START+5*DAY)['CAUSAL_WALK_FORWARD']['raw']==0 # +60s matters
    counts=support_counts([w],q,START+6*DAY)
    assert counts['CAUSAL_WALK_FORWARD']['raw']==1;assert counts['OLD_STRICT']['raw']==0
    assert support_counts([w],q,q['q']+DAY)['CAUSAL_WALK_FORWARD']['raw']==0

def response(u=.4,d=.3,n=.3,up=.55,down=.45):
    return dict(window_id='x',status='OK',reason='',D=[u,d,n],forecasts={s:{k:dict(q20=0,q50=.2,q80=.5,p_adverse_touch=p) for k,p in zip(KEYS,[max(t,.8),t,min(t,.2)])} for s,t in [('long',down),('short',up)]},tags=[],evidence='')

def test_future_response_existing_and_all_joint_bounds():
    assert not response_arrays_future(response(),'x')[3]
    cases=[response(up=.39),response(up=.71),response(down=.29),response(down=.71),response(up=.4,down=.3)]
    # Sum lower bound needs n=0.2: .4+.3 < .8 while each marginal bound passes.
    cases[-1]=response(u=.4,d=.4,n=.2,up=.4,down=.4-2e-6) # also lower-bound violation
    for obj in cases:assert response_arrays_future(obj,'x')[3]
    # A standalone union constraint is possible when u+d=1-n only within sum tolerance.
    obj=response(u=.3,d=.3,n=.3995,up=.3,down=.3)
    assert response_arrays_future(obj,'x')[3]
    assert not response_arrays_future(response(up=.4-5e-7),'x')[3]
    obj=response();obj['forecasts']['long']['sl_100']['q20']=float('nan');assert response_arrays_future(obj,'x')[3]
    assert response_arrays_future(response(),'wrong')[3]
    obj=response();obj['D']=[True,0,0];assert response_arrays_future(obj,'x')[3]
    # Balanced zero/no-touch boundary and certain up-touch boundary.
    assert not response_arrays_future(response(0,0,1,0,0),'x')[3]
    assert not response_arrays_future(response(1,0,0,1,0),'x')[3]

def test_rss_portability():
    assert peak_rss_bytes(123,'darwin')==123
    assert peak_rss_bytes(123,'linux')==123*1024

def test_fixed_causal_motif_positive_and_balanced_null_reuse_existing_functions():
    """Deterministic plumbing fixtures, not statistical evidence or a market experiment."""
    from coinmaster.research.btc_event_research import choose, eligible, empirical
    from coinmaster.research.btc_pattern_inapp import forecast_scores
    events=[dict(origin=i*100*HOUR,label_end=(i*100+72)*HOUR,input_start=(i*100-24)*HOUR) for i in range(65)]
    query=64;cutoff=events[query]['input_start'];pool=eligible(events,query,cutoff)
    motifs=np.r_[np.zeros(32),np.ones(32),0.]
    neighbors=choose((motifs[pool]-motifs[query])**2,pool,events)
    assert neighbors==list(range(32));assert all(events[i]['label_end']<=cutoff for i in pool)
    def truth(v):return dict(D=int(v),Q=np.full((2,3,2),float(v)).tolist(),touch=np.full((2,3),float(v)).tolist())
    signal=[truth(i//32) for i in range(64)]
    prior=empirical(signal,pool);local=empirical(signal,pool,neighbors)
    ps=forecast_scores(*prior,truth(0));ls=forecast_scores(*local,truth(0))
    assert ls['TP']<ps['TP'] and ls['SL']<ps['SL']
    null=[truth(i%2) for i in range(64)]
    prior=empirical(null,pool);local=empirical(null,pool,neighbors)
    assert all(np.allclose(a,b) for a,b in zip(prior,local))
    assert forecast_scores(*prior,truth(0))==forecast_scores(*local,truth(0))


def test_inclusive_exact_ten_percent_log_threshold_all_modes():
    up,_=feed([100.,110.,100.])
    down,_=feed([110.,100.,110.])
    assert [p['kind'] for p in up.pivots]==['LOW','HIGH']
    assert [p['kind'] for p in down.pivots]==['HIGH','LOW']
    assert [p['confirmation'] for p in up.pivots]==[WARM+2*DAY,WARM+3*DAY]
    assert [p['confirmation'] for p in down.pivots]==[WARM+2*DAY,WARM+3*DAY]
