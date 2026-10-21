"""Independent small fixtures and DEVELOPMENT-only saved-array audit. Zero fits."""
import json,time,hashlib
from pathlib import Path
import numpy as np
from coinmaster.research.btc_pattern_data import *

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
P=ROOT/'runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared'
started=time.monotonic();passed=[]
def check(name,condition):
    assert condition,name
    passed.append(name)
def flat():return np.tile([100.,100.,100.,100.,1.],(4320,1))
sigma=.1
v=flat();v[0,1]=100*np.exp(.12);v[1,2]=100*np.exp(-.11)
r=path_targets(v,sigma)
check('UP then SL; long log-MFE=1.2',r['direction']==0 and np.allclose(r['mfe'][0],[1.2,1.2]))
v=flat();v[0,2]=100*np.exp(-.12);v[1,1]=100*np.exp(.11)
r=path_targets(v,sigma)
check('DOWN then SL; short sign/log-MFE=1.2',r['direction']==1 and np.allclose(r['mfe'][1],[1.2,1.2]))
v=flat();v[0,1:3]=100*np.exp([.12,-.11]);r=path_targets(v,sigma)
check('same-minute D ambiguous; both Q bounds retained',r['direction']==-1 and r['ambiguous'] and np.allclose(r['mfe'],[[0,1.2],[0,1.1]]))
v=flat();v[1]=[100*np.exp(-.12),100*np.exp(.15),100*np.exp(-.13),100,1];r=path_targets(v,sigma)
check('minute open establishes DOWN before both extrema; long MFE zero',r['direction']==1 and not r['ambiguous'] and np.allclose(r['mfe'][0],[0,0]))
check('short favorable gap establishes lower before same-minute short stop',np.allclose(r['mfe'][1],[1.2,1.3]))
v=flat();v[-1,1]=v[-1,3]=100*np.exp(.11);r=path_targets(v,sigma)
check('last included minute close is entry+72h; first touch last minute',r['direction']==0 and np.isclose(r['signature'][5],1.1) and np.isclose(r['signature'][7],4319/4320))
v=flat();r=path_targets(v,sigma)
check('NONE/no touch sentinels and zero MFE',r['direction']==2 and np.all(r['signature'][6:]==2) and np.all(r['mfe']==0))
try:path_targets(v[:-1],sigma)
except ValueError:passed.append('incomplete path rejected')
else:raise AssertionError('censor rejected')

m=np.load(P/'metadata.npy',mmap_mode='r');minutes=np.load(P/'minutes.npy',mmap_mode='r');labels=dict(np.load(P/'labels.npz'));stamps=np.load(P/'stamps.npy',mmap_mode='r');gap=np.load(P/'entry-gap.npy',mmap_mode='r');refs=np.load(P/'path-reference-indices.npy',mmap_mode='r');manifest=json.loads((P/'manifest.json').read_text())
check('all timestamps entry=origin+60s; end=entry+72h',np.all(m['entry_time']==m['origin']+MINUTE) and np.all(m['label_end']==m['entry_time']+72*HOUR))
check('observed exactly full maturity; censored not zero',np.array_equal(m['observed'],m['label_end']<=manifest['minute_end']) and np.isnan(labels['mfe'][~m['observed']]).all() and np.isnan(labels['signature'][~m['observed']]).all() and np.all(labels['direction'][~m['observed']]==-1))
check('raw input bar ends <= origin',np.all(stamps+np.array([4,1])[None,:,None]*HOUR<=m['origin'][:,None,None]))
check('entry/reference indices preserve excluded gap minute',np.all(refs[:,1]-refs[:,0]==2))
check('entry/reference raw minute alignment',np.array_equal(m['entry'],minutes[m['entry_index'],0]) and np.array_equal(m['reference'],minutes[refs[:,0],3]))
check('entry gap normalized log-return, separate units24/72',np.allclose(gap,np.log(m['entry']/m['reference'])[:,None]/np.stack((m['sigma24'],m['sigma72']),1)))
split=[]
for f in folds(m):
    for part,cut in [('subfit',f['inner_cutoff']),('early_stop',f['fit_cutoff']),('refit',f['fit_cutoff']),('outer',f['outer_end'])]:
        ids=f[part];check(f['name']+' '+part+' purge',np.all(m['label_end'][ids]<=cut))
        split.append(dict(fold=f['name'],part=part,N=len(ids),cutoff=int(cut),max_label_end=int(m['label_end'][ids].max())))
dev=np.flatnonzero(m['observed']&(m['origin']<ms('2026-05-01')));sample=dev[np.linspace(0,len(dev)-1,32).astype(int)]
for i in sample:
    j=m['entry_index'][i];ref=m['reference'][i];hourly=minutes[j-2-60*np.arange(168,-1,-1),3];vol=np.std(np.diff(np.log(hourly)),ddof=1)
    check('saved sigma72 independent '+str(i),np.isclose(m['sigma72'][i],vol*np.sqrt(72),rtol=1e-6))
    value=path_targets(minutes[j:j+4320],m['sigma72'][i]);check('saved label repeat '+str(i),value['direction']==labels['direction'][i] and np.allclose(value['mfe'],labels['mfe'][i],atol=1e-6) and np.allclose(value['signature'],labels['signature'][i],atol=1e-6))
    for hi,h in enumerate((24,72)):
        base=m['sigma24' if h==24 else 'sigma72'][i]
        for si,sl in enumerate((.75,1,1.5)):
            value=path_targets(minutes[j:j+h*60],base*sl,h)['mfe']*sl
            check('policy unit conversion '+str((int(i),h,sl)),np.allclose(value,labels['policy_mfe'][i,hi,si],atol=1e-6))

# Dependency provenance fixture: alter one completed 4h volume BEFORE reported input_start.
n=1700;t=np.arange(n)*HOUR;c=100*np.exp(np.arange(n)*.0001+np.sin(np.arange(n))*.001)
hv=np.column_stack((c,c*1.002,c*.998,c,np.arange(n)%27+10));t4,v4=aggregate(t,hv,4*HOUR);origin=1300*HOUR;panels={1:(t,hv),4:(t4,v4)}
before=features_at(panels,origin);j=np.searchsorted(t4+4*HOUR,origin,side='right');dependency_start=int(t4[j-84]);reported=int(before[4]);v4[j-84,4]*=100;after=features_at(panels,origin)
provenance=dict(reported_input_start=reported,actual_volume_dependency_start=dependency_start,understatement_hours=(reported-dependency_start)/HOUR,changed_feature=float(after[0][0,0,5]-before[0][0,0,5]),before_reported_start=bool(dependency_start<reported))
check('provenance fixture confirms earlier input support',dependency_start<reported and not np.array_equal(before[0],after[0]))
result=dict(status='COMPLETE_ZERO_FIT',fits=0,new_predictions=0,CHECK_scored=False,checks=len(passed),passed=passed,split_counts=split,development_sample_ids=sample.tolist(),dependency_provenance=provenance,censored_N=int((~m['observed']).sum()),source_sha256=sha(ROOT/'runtime/coinmaster/research/btc_pattern_data.py'),wall_seconds=time.monotonic()-started)
(HERE/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['passed','split_counts','development_sample_ids']}))
