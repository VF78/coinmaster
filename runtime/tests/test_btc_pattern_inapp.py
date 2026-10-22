import copy
import numpy as np
from coinmaster.research.btc_pattern_inapp import targets,response_arrays,display,block_ci,forecast_scores,SL,KEYS

def good():
    return dict(window_id='opaque',status='OK',reason='',D=[.6,.3,.1],forecasts={s:{k:dict(q20=.2,q50=.5,q80=.8,p_adverse_touch=p) for k,p in zip(KEYS,[.4,.2,.1])} for s in ('long','short')},tags=['mixed'],evidence='A test.')

def test_validation_and_display():
    obj=good();p,q,t,e,cross=response_arrays(obj,'opaque');assert not e;assert display(p,q,t)['SL']==1
    bad=copy.deepcopy(obj);bad['forecasts']['long']['sl_100']['q20']=2;assert response_arrays(bad,'opaque')[3]
    bad=copy.deepcopy(obj);bad['D']=[float('nan'),0,1];assert response_arrays(bad,'opaque')[3]
    bad=copy.deepcopy(obj);bad['forecasts']['long']['sl_100']['p_adverse_touch']=.8;assert response_arrays(bad,'opaque')[3]
    q[:]=0;assert display(p,q,t)['status']=='NO_TRADE'
    assert display(np.array([.5,.5,0]),q,t)['status']=='NO_TRADE'

def test_stop_minute_and_inclusive_touch():
    v=np.tile([100.,100.,100.,100.,1.],(4320,1));sigma=.1
    v[0,1]=100*np.exp(.5*sigma);v[0,2]=100*np.exp(-sigma)
    t=targets(v,sigma);assert t['touch'][0][1]==1;assert t['Q'][0][1][0]==0;assert np.isclose(t['Q'][0][1][1],.5)
    assert t['Q'][0][2][0]>.49

def test_score_and_bootstrap():
    p,q,t,e,_=response_arrays(good(),'opaque');truth=dict(D=0,Q=np.zeros((2,3,2)).tolist(),touch=np.zeros((2,3)).tolist());s=forecast_scores(p,q,t,truth);assert s['TP']>0 and s['SL']>0
    origins=np.arange(24)*15*86400000;folds=np.repeat(['F1','F2','F3'],8);r=block_ci(-np.arange(1,25),origins,folds);assert r['upper']<0 and r['pass_rule'];assert block_ci(np.ones(24),origins,folds)['status']=='INCONCLUSIVE'
