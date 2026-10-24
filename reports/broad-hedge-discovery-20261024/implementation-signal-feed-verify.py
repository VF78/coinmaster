"""Independent full market-only formulas plus physically truncated-input prefix tests."""
from pathlib import Path
from decimal import Decimal as D,localcontext
import csv,json,math,bisect,hashlib,importlib.util,ast,collections
import numpy as np
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;M=60000000000;H=60*M;DAY=24*H
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
meta=json.loads((O/'implementation-signal-feed-metadata.json').read_text());contract=json.loads((O/'implementation-signal-feed-contract.json').read_text());assert sha(O/'implementation-signal-feed.csv')==meta['csv_sha256'] and sha(O/'implementation-signal-feed-build.py')==meta['builder_sha256'] and sha(O/'implementation-signal-feed-contract.json')==meta['contract_sha256']
market={}
for p,s in meta['market_input_sha256'].items():
 assert sha(p)==s;sym='BTC' if 'BTCUSDT' in p else 'SOL';kind='execution-1m' if 'execution-1m' in p else 'daily' if 'daily' in p else 'funding';cols=['open_time_ms','open','high','low','close'] if kind=='execution-1m' else ['open_time_ms','close'] if kind=='daily' else ['funding_time_ms','funding_rate'];market[sym,kind]=pq.read_table(p,columns=cols).to_pydict()
assert len(market)==6;rows=list(csv.DictReader((O/'implementation-signal-feed.csv').open()));assert len(rows)==4380 and list(rows[0])==contract['columns'];checks=collections.Counter();bars={}
for sym in ['BTC','SOL']:
 d=market[sym,'execution-1m'];assert len(d['open_time_ms'])==1051200 and all(b-a==60000 for a,b in zip(d['open_time_ms'],d['open_time_ms'][1:]));bars[sym]=[]
 for k in range(4380):
  j=240*k;bars[sym].append((str(d['open'][j]),str(d['close'][j+239]),max(map(D,d['high'][j:j+240])),min(map(D,d['low'][j:j+240])),(d['open_time_ms'][j]+14400000)*1000000))
dB=market['BTC','daily'];dS=market['SOL','daily'];dt=[int(t)*1000000+DAY for t in dB['open_time_ms']];assert dt==[int(t)*1000000+DAY for t in dS['open_time_ms']];db=list(map(float,dB['close']));ds=list(map(float,dS['close']));fund={sym:([int(t)*1000000 for t in market[sym,'funding']['funding_time_ms']],list(map(float,market[sym,'funding']['funding_rate']))) for sym in ['BTC','SOL']};trs=[];atr=None
with localcontext() as ctx:
 ctx.prec=50
 for k,r in enumerate(rows):
  B=bars['BTC'][k];S=bars['SOL'][k];t=int(r['decision_ns']);assert t==B[4]==S[4] and int(r['available_ns'])==t and int(r['not_before_ns'])==t+M and t%(4*H)==0
  assert r['btc_close']==B[1] and r['sol_close']==S[1] and r['btc_h4_open']==B[0] and r['f0_open_o']==B[0] and r['btc_previous_h4_close']==(bars['BTC'][k-1][1] if k else '')
  for name in ['risk_coefficients_valid','sol_atr_valid','b2_pattern_valid','b2_long','b2_short','f0_pattern_valid','f0_long','f0_short']:assert r[name] in ['0','1']
  i=bisect.bisect_right(dt,t-DAY)-1;assert i>=30;bx=[db[j]/db[j-1]-1 for j in range(i-29,i+1)];sy=[ds[j]/ds[j-1]-1 for j in range(i-29,i+1)];mx=math.fsum(bx)/30;my=math.fsum(sy)/30;vx=math.fsum((x-mx)**2 for x in bx)/29;vy=math.fsum((y-my)**2 for y in sy)/29;cov=math.fsum((x-mx)*(y-my) for x,y in zip(bx,sy))/29;beta=cov/vx;rho=cov/math.sqrt(vx*vy)
  for field,want in [('beta_d1_30',beta),('rho_d1_30',rho),('sigma_btc_d1_30',math.sqrt(vx)),('sigma_sol_d1_30',math.sqrt(vy))]:assert math.isclose(float(r[field]),want,rel_tol=2e-12,abs_tol=1e-15);assert D(r[field]).is_finite()
  assert int(r['d1_last_return_end_ns'])==dt[i] and dt[i]<=t-DAY and int(r['d1_first_return_end_ns'])==dt[i-29] and (i+1==len(dt) or dt[i+1]>t-DAY)
  tr=S[2]-S[3] if not k else max(S[2]-S[3],abs(S[2]-D(bars['SOL'][k-1][1])),abs(S[3]-D(bars['SOL'][k-1][1])));trs.append(tr)
  if k==13:atr=sum(trs[:14],D(0))/14
  elif k>13:atr=(atr*13+tr)/14
  if atr is None:assert r['sol_atr_valid']=='0' and r['sol_atr_h4_14']=='' and r['atr_last_h4_end_ns']==''
  else:assert D(r['sol_atr_h4_14'])==atr and r['sol_atr_valid']=='1' and int(r['atr_last_h4_end_ns'])==t
  if k<7:assert r['b2_pattern_valid']=='0' and r['b2_long_k']==r['b2_short_k']=='' and r['b2_long']==r['b2_short']=='0'
  else:
   prior=D(bars['BTC'][k-1][1]);current=D(B[1]);Klong=max(bars['BTC'][j][2] for j in range(k-7,k-1));Kshort=min(bars['BTC'][j][3] for j in range(k-7,k-1));assert D(r['b2_long_k'])==Klong and D(r['b2_short_k'])==Kshort and r['b2_pattern_valid']=='1';assert int(r['b2_long'])==int(prior>Klong and current<=Klong and current<prior) and int(r['b2_short'])==int(prior<Kshort and current>=Kshort and current>prior)
  g={}
  for sym,prefix in [('BTC','btc'),('SOL','sol')]:
   ft,fr=fund[sym];j=bisect.bisect_left(ft,t)-1;assert j>=1 and ft[j]<t and int(r[prefix+'_funding_last_ns'])==ft[j] and int(r[prefix+'_funding_previous_ns'])==ft[j-1];g[sym]=fr[j]/((ft[j]-ft[j-1])/H)
  diff=g['SOL']-float(r['beta_d1_30'])*g['BTC'];assert math.isclose(float(r['funding_differential_per_hour']),diff,rel_tol=1e-12,abs_tol=1e-18);assert r['f0_pattern_valid']==('1' if k else '0')
  long=bool(k and D(B[1])<D(bars['BTC'][k-1][1]) and diff>0);short=bool(k and D(B[1])>D(bars['BTC'][k-1][1]) and diff<0);assert int(r['f0_long'])==int(long) and int(r['f0_short'])==int(short)
  checks['all_H4_exact_rawprices_and_clocks']+=1;checks['all_lagged_D1_coefficients']+=1;checks['all_SOL_ATR14']+=1;checks['all_raw_bothside_B2_F0_K_O']+=1
# The builder imports no economic/native modules. Importing it runs no build.
tree=ast.parse((O/'implementation-signal-feed-build.py').read_text());imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names];assert not any(s and ('nautilus' in s or 'coinmaster' in s or 'discovery' in s) for s in imports)
spec=importlib.util.spec_from_file_location('market_only_builder',O/'implementation-signal-feed-build.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
def truncated(cut):
 z={}
 for (sym,kind),d in market.items():
  clock=[int(t)*1000000+(M if kind=='execution-1m' else DAY if kind=='daily' else 0) for t in d['open_time_ms' if kind!='funding' else 'funding_time_ms']];n=bisect.bisect_right(clock,cut);z[sym,kind]={name:vals[:n] for name,vals in d.items()}
 return z
prefixcuts=[int(rows[7]['decision_ns']),int(rows[13]['decision_ns']),1736899200000000000,1756684800000000000]
for cut in prefixcuts:
 generated=builder.build_rows(truncated(cut));expected=[r for r in rows if int(r['decision_ns'])<=cut];assert len(generated)==len(expected)
 for a,b in zip(generated,expected):assert {k:str(v) for k,v in a.items()}==b
 checks['physical_truncated_input_prefix_invariance']+=1
# Isolated plumbing fixture: change raw current bar OPEN only, not prior close.
fixture=truncated(int(rows[13]['decision_ns']));d=fixture['BTC','execution-1m'];j=240*10;original=d['open'][j];candidate=d['high'][j] if D(d['high'][j])!=D(original) else d['low'][j];assert D(candidate)!=D(original);d['open'][j]=candidate;changed=builder.build_rows(fixture)[10];assert D(changed['f0_open_o'])==D(candidate) and changed['btc_previous_h4_close']==rows[10]['btc_previous_h4_close'] and D(changed['f0_open_o'])!=D(changed['btc_previous_h4_close']);checks['actual_raw_H4_open_not_previousclose_plumbing']=1
# Read only a market-feature projection from the prior discovery feature artifact.
old=O/'discovery-features.csv';bytime={r['decision_ns']:r for r in rows};overlap=0
with old.open() as f:
 reader=csv.reader(f);header=next(reader);names=['decision_ns','side','signal_B2','signal_F0','beta','rho'];idx={n:header.index(n) for n in names}
 for raw in reader:
  oldrow={n:raw[i] for n,i in idx.items()};now=bytime[oldrow['decision_ns']];side='long' if oldrow['side']=='1' else 'short'
  if oldrow['signal_B2']!='':assert now['b2_'+side]==oldrow['signal_B2']
  if oldrow['signal_F0']!='':assert now['f0_'+side]==oldrow['signal_F0']
  assert math.isclose(float(now['beta_d1_30']),float(oldrow['beta']),rel_tol=1e-12) and math.isclose(float(now['rho_d1_30']),float(oldrow['rho']),rel_tol=1e-12);overlap+=1
checks['prior_discovery_market_feature_projection_overlap']=overlap
assert all(sha(p)==s for p,s in meta['market_input_sha256'].items()) and sha(O/'implementation-signal-feed.csv')==meta['csv_sha256']
result={'schema':contract['schema'],'status':'PASS_PURE_MARKET_ALL_H4_FEED','checks':dict(checks),'rows':4380,'columns':contract['columns'],'prefix_cuts_ns':prefixcuts,'first_13_ATR_unavailable_preserved':True,'B2_flags_not_conditioned_on_ATR':True,'F0_O_rawopen_plumbing_proven':True,'builder_uses_only_six_market_sources':True,'prior_discovery_used_for_verification_projection_only':True,'verification_projection_sha256':sha(old),'no_parent_qty_capital_outcome_inputs_to_feed':True,'csv_sha256':sha(O/'implementation-signal-feed.csv'),'builder_sha256':sha(O/'implementation-signal-feed-build.py'),'metadata_sha256':sha(O/'implementation-signal-feed-metadata.json'),'verifier_sha256':sha(Path(__file__)),'engine_runs':0,'new_trade_outcomes':0,'runtime_source_mutations':0}
(O/'implementation-signal-feed-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','rows','checks','csv_sha256','builder_sha256','metadata_sha256','verifier_sha256']},indent=2))
