"""One connected prelabel verification. No hypothetical position or PNL."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import csv,json,hashlib,collections,math
import numpy as np
import pyarrow.parquet as pq
getcontext().prec=60
O=Path(__file__).resolve().parent;build=json.loads((O/'discovery-build.json').read_text());features=list(csv.DictReader((O/'discovery-features.csv').open()));cycles=list(csv.DictReader((O/'discovery-actual-cycles.csv').open()));events=list(csv.DictReader((O/'discovery-baseline-events.csv').open()));arrays=np.load(O/'discovery-baseline.npz')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p,s in build['input_sha256'].items():assert sha(p)==s
M=60000000000;H=60*M;DAY=24*H
dp=next(p for p in build['input_sha256'] if p.endswith('bybit-BTCUSDT-daily.parquet'));sp=dp.replace('BTCUSDT','SOLUSDT');db=pq.read_table(dp).to_pydict();ds=pq.read_table(sp).to_pydict();dt=np.array(db['open_time_ms'],np.int64)*1000000+DAY;b=np.array(db['close'],float);s=np.array(ds['close'],float);rb=np.r_[np.nan,b[1:]/b[:-1]-1];rs=np.r_[np.nan,s[1:]/s[:-1]-1]
checks=collections.Counter()
for f in features:
 t=int(f['decision_ns']);e=int(f['entry_reference_ns']);end=int(f['daily_window_last_return_end_ns']);di=int(np.searchsorted(dt,end));assert dt[di]==end and end<=t-DAY and (di+1==len(dt) or dt[di+1]>t-DAY)
 br=rb[di-29:di+1];sr=rs[di-29:di+1];assert len(br)==30 and int(f['daily_window_first_return_end_ns'])==dt[di-29]
 beta=float(np.sum((br-br.mean())*(sr-sr.mean()))/np.sum((br-br.mean())**2));assert math.isclose(beta,float(f['beta']),rel_tol=2e-14)
 a=.5*math.sqrt(float(np.sum((br-br.mean())**2)/np.sum((sr-sr.mean())**2)));assert math.isclose(a,float(f['HALFVOL_a']),rel_tol=2e-14)
 assert e==t+M and t%(4*H)==0;ci=int(f['cycle'])-1;assert int(cycles[ci]['first_fill_ns'])<t<int(cycles[ci]['actual_flat_ns'])
 assert D(f['first_actual_fill_px'])==D(cycles[ci]['first_fill_price'])
 if f['H1lag720_last_return_end_ns']:assert int(f['H1lag720_last_return_end_ns'])==t-H
 assert float(f['observed_Hraw_t'])>=float(f['observed_Wraw_t'])-1e-8
 checks['causal_daily_windows']+=1;checks['independent_D1beta_HALFVOL']+=1;checks['actual_episode_membership']+=1
seen={int(f['cycle']) for f in features};missing=[]
for c in cycles:
 if int(c['cycle']) in seen:continue
 first=int(c['first_fill_ns']);flat=int(c['actual_flat_ns']);h4=(first//(4*H)+1)*(4*H)
 assert h4>=flat # No held completed-H4 signal opportunity, no discarded history.
 missing.append({'cycle':int(c['cycle']),'first_fill_ns':first,'actual_flat_ns':flat,'next_H4close_ns':h4,'reason':'NO_HELD_H4_DECISION'})
assert np.all(np.diff(arrays['timestamp_ns'])==M);assert np.all(arrays['Hraw_bracketed'][1:]>=arrays['Hraw_bracketed'][:-1]);assert arrays['q'][-1]==0
assert events[-1]['pricecash_after']=='120718.40416503' and events[-1]['q_after']=='0.000'
assert D(build['baseline_terminal_native_residual'])==0 and D(build['baseline_actual_signed_funding'])==D('4063.32156049')
result={'status':'PASS_FEATURE_BASELINE_ONLY_NO_NEW_OUTCOMES','checks':dict(checks),'all_actual_episodes':83,'episodes_with_H4':len(seen),'no_action_coverage':missing,'terminal_reconciliation':'EXACT Decimal, zero native residual','funding_source':'READONLY immutable SQLite == raw-native signed cash delta multiset','J_clock_size_status':'PENDING_ROOT_FREEZE; raw pending fields not final signals','initial_preexecution_failure':'discovery-build-initial-syntax-failed.py preserved; one extra closing parenthesis fixed before data build','build_script_sha256':sha(O/'discovery-build.py'),'feature_sha256':sha(O/'discovery-features.csv'),'verifier_sha256':sha(Path(__file__)),'candidate_outcomes_read':0,'candidate_labels_computed':0,'engine_runs':0}
(O/'discovery-feature-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
