"""Causal entry-day Bybit screen; price proxies only, no native PnL replay."""
import csv,json,hashlib,math,resource,statistics,time,urllib.request
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
OUT=Path('reports/btc-split-sol-cover-20261018');OUT.mkdir(parents=True,exist_ok=True)
ROOT=Path('/var/lib/coinmaster-native-gui/data');BASE=ROOT/'runs/jobs/cm113-sizing-v3-20261011/result'
RAW=BASE/'v0-selective-lifecycle-cap30m-btc-direction.json'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(name,x): (OUT/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def csvout(name,rows):
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def desc(xs):
 a=np.array([x for x in xs if x is not None],float)
 return None if not len(a) else dict(n=len(a),mean=float(a.mean()),**{k:float(np.quantile(a,q)) for k,q in [('min',0),('p05',.05),('p25',.25),('median',.5),('p75',.75),('p95',.95),('max',1)]})
assert sha(RAW)=='caa6b209142f4a005f8cd73ee00d030bd841c6a9669e98c971b15f93c36c902a'
r=json.load(RAW.open());assert r['terminal_total']=='5437208.56951095'
eps=[e for e in csv.DictReader(open('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution-episodes.csv')) if e['symbol']=='BTC'];assert len(eps)==105
fills=[f for f in r['fill_audit'] if f['action']=='BTC_ENTRY'];assert len(fills)==105
parents=[]
for e,f,a,s in zip(eps,fills,r['entry_sizing_audit'],r['btc_sizing_audit']):
 t=int(f['fill_ns'])//10**6;assert t==int(e['start_ns'])//10**6==int(a['q1_ns'])//10**6
 exits=[x for x in r['fill_audit'] if x['instrument'].startswith('BTC') and x['action']!='BTC_ENTRY' and t<int(x['fill_ns'])//10**6<=int(e['end_ns'])//10**6]
 parents.append(dict(parent=e['number'],episode_id=a['episode_id'],day=t//86400000,t=t,end=int(e['end_ns'])//10**6,side=e['side'],year=e['start_utc'][:4],p=float(f['px']),qty=f['qty'],reference_qty=a['reference_btc_qty'],q0_ns=a['q0_ns'],q1_ns=a['q1_ns'],reference_price=a['reference_wire_price'],branch=a['branch'],rights=json.dumps(a['sol_right_activations']),first_exit=min(int(x['fill_ns'])//10**6 for x in exits),first_exit_reason=exits[0]['reason']))
days={p['day'] for p in parents};data={};hours={};sources={str(RAW):sha(RAW)}
m=json.load((ROOT/'bybit-1m/manifest.json').open())
assert hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()==r['data_hash']
coverage=[]
for symbol in ('BTC','SOL'):
 for stream in ('execution','mark'):
  path=ROOT/f'normalized/bybit-{symbol}USDT-{stream}-1m.parquet';digest=sha(path)
  spec=next(z for x in m['symbols'] if x['symbol']==symbol+'USDT' for z in x['streams'] if z['stream']==stream);assert digest==spec['parquet_sha256'];sources[str(path)]=digest
  chunks={d:[] for d in days};hc={};n=0;prev=None;first=None;last=None
  for b in pq.ParquetFile(path).iter_batches(batch_size=10080,columns=['open_time_ms','open','high','low','close']):
   ar=np.column_stack([np.array(b.column(i).to_pylist(),dtype=float) for i in range(5)]);ts=ar[:,0].astype('int64')+60000;ar[:,0]=ts
   assert np.all(np.diff(ts)==60000) and (prev is None or ts[0]-prev==60000);prev=int(ts[-1]);first=first or int(ts[0]);last=int(ts[-1]);n+=len(ts)
   for d in np.unique((ts-1)//86400000):
    if int(d) in days:chunks[int(d)].append(ar[(ts-1)//86400000==d].copy())
   if stream=='execution':hc.update({int(t):float(c) for t,c in zip(ts[ts%3600000==0],ar[ts%3600000==0,4])})
  data[symbol,stream]={d:np.concatenate(chunks[d]) for d in days};hours[symbol,stream]=hc
  coverage.append(dict(symbol=symbol,stream=stream,rows=n,first_close_ms=first,last_close_ms=last,sha256=digest,gaps=0))
for sym in ('BTC','SOL'):
 warm=OUT/f'data-warmup-{sym}USDT-1h.csv'
 if warm.exists():
  hours[sym,'execution'].update({int(x['open_time_ms'])+3600000:float(x['close']) for x in csv.DictReader(warm.open())})
print('loaded streams rss KiB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
def beta(t,nd):
 end=t//3600000*3600000;keys=np.arange(end-nd*24*3600000,end+1,3600000,dtype='int64')
 hb=hours['BTC','execution'];hs=hours['SOL','execution']
 if not all(int(k) in hb and int(k) in hs for k in keys):return None,None
 pb=np.array([hb[int(k)] for k in keys]);ps=np.array([hs[int(k)] for k in keys]);b=pb[1:]/pb[:-1]-1;s=ps[1:]/ps[:-1]-1;return float(np.cov(s,b,ddof=1)[0,1]/np.var(b,ddof=1)),float(np.corrcoef(s,b)[0,1])
def confirmations(ar,sign,t):
 # Complete UTC 15m bars strictly after actual fill, two complete post-fill bars.
 bars=[]
 for end in range(int(ar[0,0])//900000*900000+900000,int(ar[-1,0])+1,900000):
  z=ar[(ar[:,0]>end-900000)&(ar[:,0]<=end)]
  if len(z)==15 and z[0,0]-60000>=t:bars.append((end,z[:,2].max(),z[:,3].min(),z[-1,4]))
 out=[]
 for prev,cur in zip(bars,bars[1:]):
  if (cur[3]>prev[1] if sign==1 else cur[3]<prev[2]):out.append(cur[0])
 return out
rows=[];ext=[];betas=[]
for p in parents:
 t=p['t'];sgn=1 if p['side']=='BUY' else -1;dayend=(p['day']+1)*86400000
 b30,r30=beta(t,30);b90,r90=beta(t,90);betas.append(dict(parent=p['parent'],year=p['year'],side=p['side'],beta30=b30,rho30=r30,beta90=b90,rho90=r90))
 for sym,sign in [('BTC',sgn),('SOL',-sgn)]:
  ar=data[sym,'execution'][p['day']];anchor=p['p'] if sym=='BTC' else float(ar[ar[:,0]==t][0,4]);conf=confirmations(ar,sign,t)
  for scope,stop in [('day',dayend),('active',min(dayend,p['end']))]:
   for h in (1,2,4,8,24):
    z=ar[(ar[:,0]>t)&(ar[:,0]<=min(stop,t+h*3600000))];lo=float(z[:,3].min()) if len(z) else anchor;hi=float(z[:,2].max()) if len(z) else anchor
    adv=max(0,1-lo/anchor) if sign==1 else max(0,hi/anchor-1)
    ext.append(dict(parent=p['parent'],year=p['year'],side=p['side'],symbol=sym,stream='execution',scope=scope,hours=h,adverse_pct=adv*100,hit025=adv>=.0025,hit050=adv>=.005))
  for d in ((.0015,.0025,.005) if sym=='BTC' else (.0025,.005,.0075)):
   for h in ((2,4,8) if sym=='BTC' else (4,8)):
    for confirm in (False,True):
     deadline=min(t+h*3600000,dayend-60000);limit=anchor*(1-sign*d);z=ar[(ar[:,0]>t)&(ar[:,0]<=deadline)];chosen=None;armed=None;reason='NO_ADD' if sym=='SOL' else 'DEADLINE';px=None
     for bar in z:
      tm=int(bar[0]);hit=(bar[3]<limit-anchor*.0001 if sign==1 else bar[2]>limit+anchor*.0001)
      if hit and armed is None:armed=tm
      if not confirm and hit:chosen=tm;px=limit;reason='LIMIT_PROXY';break
      if sym=='BTC' and confirm and hit:chosen=tm;px=limit;reason='LIMIT_PROXY';break
      # confirmation at preceding completed 15m, next 1m quote only; SOL armed strictly before confirming bar begins.
      if confirm and tm-60000 in conf and (sym=='BTC' or (armed is not None and armed<=tm-60000-900000)):
       improvement=sign*(anchor-bar[4])/anchor
       if improvement>=(-.001 if sym=='BTC' else d/2):chosen=tm;px=float(bar[4]);reason='CONFIRM';break
     if chosen is None and sym=='BTC':chosen=int(z[-1,0]);px=float(z[-1,4])
     early=p['first_exit']<= (chosen if chosen else deadline)
     imp=sign*(anchor-px)/anchor*10000 if px is not None else None
     result=None;mae=None;returned=None
     if chosen is not None and sym=='SOL':
      later=ar[(ar[:,0]>chosen)&(ar[:,0]<min(dayend,p['end']))];returned=False
      if len(later):
       returns=later[:,2]>=anchor if sign==1 else later[:,3]<=anchor;returned=bool(returns.any());exitpx=anchor if returned else float(later[-1,4]);result=sign*(exitpx/px-1)*10000-11 # Bybit taker in+out, conservative uniform fee proxy
       mae=max(0,1-float(later[:,3].min())/px)*100 if sign==1 else max(0,float(later[:,2].max())/px-1)*100
     rows.append(dict(parent=p['parent'],year=p['year'],side=p['side'],symbol=sym,d_pct=d*100,wait_h=h,confirmation=confirm,reason=reason,anchor=anchor,entry_price=px,wait_actual_h=(chosen-t)/3600000 if chosen else None,improvement_bp=imp,whole_btc_price_bp=imp/2 if sym=='BTC' else None,early_exit_before_entry=early,chosen_after_btc_close=bool(chosen and chosen>=p['end']),sol_return_anchor=returned,sol_tactical_net_proxy_bp=result,sol_postfill_mae_pct=mae))
for p in parents:
 for sym,sign in [('BTC',1 if p['side']=='BUY' else -1),('SOL',-1 if p['side']=='BUY' else 1)]:
  ar=data[sym,'mark'][p['day']];anchor=float(ar[ar[:,0]==p['t']][0,4])
  for scope,stop in [('day',(p['day']+1)*86400000),('active',min((p['day']+1)*86400000,p['end']))]:
   for h in (1,2,4,8,24):
    z=ar[(ar[:,0]>p['t'])&(ar[:,0]<=min(stop,p['t']+h*3600000))];adv=max(0,1-float(z[:,3].min())/anchor) if sign==1 else max(0,float(z[:,2].max())/anchor-1)
    ext.append(dict(parent=p['parent'],year=p['year'],side=p['side'],symbol=sym,stream='mark',scope=scope,hours=h,adverse_pct=adv*100,hit025=adv>=.0025,hit050=adv>=.005))
csvout('screening-parents.csv',parents);csvout('screening-grid.csv',rows);csvout('screening-excursions.csv',ext);csvout('coverage-beta.csv',betas);csvout('data-streams.csv',coverage)
summ=[]
for sym in ('BTC','SOL'):
 combos=sorted(set((x['d_pct'],x['wait_h'],x['confirmation']) for x in rows if x['symbol']==sym))
 for d,h,c in combos:
  for group in ('ALL','TRAIN_12M','SENSITIVITY_12M','2024','2025','2026','BUY','SELL'):
   z=[x for x in rows if x['symbol']==sym and (x['d_pct'],x['wait_h'],x['confirmation'])==(d,h,c) and (group=='ALL' or x['year']==group or x['side']==group or (group=='TRAIN_12M' and next(p['t'] for p in parents if p['parent']==x['parent'])<1756684800000) or (group=='SENSITIVITY_12M' and next(p['t'] for p in parents if p['parent']==x['parent'])>=1756684800000))]
   summ.append(dict(symbol=sym,d_pct=d,wait_h=h,confirmation=c,group=group,n=len(z),limit_hits=sum(x['reason']=='LIMIT_PROXY' for x in z),confirm_hits=sum(x['reason']=='CONFIRM' for x in z),fallback=sum(x['reason']=='DEADLINE' for x in z),no_add=sum(x['reason']=='NO_ADD' for x in z),early_exit=sum(x['early_exit_before_entry'] for x in z),wait=desc([x['wait_actual_h'] for x in z]),whole_btc_bp=desc([x['whole_btc_price_bp'] for x in z]),fallback_bp=desc([x['whole_btc_price_bp'] for x in z if x['reason']=='DEADLINE']),tactical_net_proxy_bp=desc([x['sol_tactical_net_proxy_bp'] for x in z])))
save('screening-summary.json',summ)
exsum=[]
for sym in ('BTC','SOL'):
 for stream in ('execution','mark'):
  for scope in ('day','active'):
   for h in (1,2,4,8,24):
    for group in ('ALL','BUY','SELL','2024','2025','2026'):
     z=[x for x in ext if x['symbol']==sym and x['stream']==stream and x['scope']==scope and x['hours']==h and (group=='ALL' or x['side']==group or x['year']==group)]
     exsum.append(dict(symbol=sym,stream=stream,scope=scope,hours=h,group=group,adverse_pct=desc([x['adverse_pct'] for x in z]),hit025=sum(x['hit025'] for x in z),hit050=sum(x['hit050'] for x in z)))
save('screening-excursion-summary.json',exsum)
pair=[]
for p,be in zip(parents,betas):
 sign=1 if p['side']=='BUY' else -1;bt=data['BTC','execution'][p['day']];so=data['SOL','execution'][p['day']];anchor=float(so[so[:,0]==p['t']][0,4]);bret=sign*(float(bt[-1,4])/p['p']-1);sret=-sign*(float(so[-1,4])/anchor-1)
 pair.append(dict(parent=p['parent'],year=p['year'],side=p['side'],btc_price_return=bret,opposite_sol_price_return=sret,beta30=be['beta30'],rho30=be['rho30'],pair_c050=bret+.5*sret/be['beta30'],pair_c075=bret+.75*sret/be['beta30'],pair_c100=bret+sret/be['beta30']))
csvout('coverage-day-pairs.csv',pair)
save('coverage-pair-summary.json',{k:dict(distribution=desc([x[k]*100 for x in pair]),std_pct=float(np.std([x[k]*100 for x in pair],ddof=1)),btc_loss_helped=sum(x[k]>x['btc_price_return'] for x in pair if x['btc_price_return']<0),btc_loss_worsened=sum(x[k]<x['btc_price_return'] for x in pair if x['btc_price_return']<0)) for k in ('btc_price_return','pair_c050','pair_c075','pair_c100')})
save('coverage-beta-summary.json',{str(nd):{'beta':desc([x['beta'+str(nd)] for x in betas]),'rho':desc([x['rho'+str(nd)] for x in betas]),'missing':sum(x['beta'+str(nd)] is None for x in betas)} for nd in (30,90)})
save('data-method.json',dict(scope='Same historical path price screening, NOT native ROI or execution proof',control_total=r['terminal_total'],data_hash=r['data_hash'],rows_per_stream=1051200,parents=105,causality='Minute close available at end; post-fill extrema only; 15m complete post-fill bars, confirmation next minute close. SOL trigger must precede confirming bar open. No future close used as signal. BTC historical exit flags are diagnostic only.',limits='1bp penetration proxy, no queue/L2/partial fill. No execution guarantees. SOL anchor is simultaneous execution close, not actual hedge fill. Tactical returns truncated at observed BTC close as diagnostic, no same-bar high ordering assumption. No native changed path. Official Bybit Jun1..Sep1 2024 1H warmup supplies prior beta; actual manifest records hashes.',early_exit_policy='Grid reports unconstrained same-day price screen plus explicit early_exit_before_entry/chosen_after_btc_close flags; native must accelerate for TP or cancel for mandatory close. Native min margin UNKNOWN; not recomputed here.',fee_policy='BTC price improvement excludes fees; SOL tactical diagnostic subtracts Bybit 5.5bp each leg uniformly. Funding UNKNOWN, not zero.',peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
for p in OUT.glob('data-warmup*'):
 sources[str(p)]=sha(p)
checks=[]
for p in [parents[i] for i in (0,2,10,40,90)]:
 x=next(x for x in rows if x['parent']==p['parent'] and x['symbol']=='BTC' and x['d_pct']==.25 and x['wait_h']==4 and not x['confirmation']);tm=p['t']+round(x['wait_actual_h']*3600000);ar=data['BTC','execution'][p['day']];bar=ar[ar[:,0]==tm][0]
 checks.append(dict(parent=p['parent'],side=p['side'],entry_ms=p['t'],actual_fill=p['p'],netQ=p['qty'],referenceQ=p['reference_qty'],limit=p['p']*(1-(1 if p['side']=='BUY' else -1)*.0025),selected_ms=tm,selected_minute_high=float(bar[2]),selected_minute_low=float(bar[3]),selected_quote_close=float(bar[4]),reason=x['reason'],whole_btc_price_bp=x['whole_btc_price_bp'],first_exit_ms=p['first_exit'],first_exit_reason=p['first_exit_reason']))
save('screening-handchecks.json',checks)
selected=[]
for sym,d,h,c in [('BTC',.25,4,False),('BTC',.50,4,False),('SOL',.50,4,True)]:
 selected.append({k:v for k,v in next(x for x in summ if x['symbol']==sym and x['d_pct']==d and x['wait_h']==h and x['confirmation']==c and x['group']=='TRAIN_12M').items() if k not in ('wait','fallback_bp')})
save('screening-recommendation.json',dict(selection_period='[2024-09-01,2025-09-01):57 parents',sensitivity_period='[2025-09-01,2026-09-01):48 parents; previously reviewed, NOT honest OOS',selection_rule='Two bounded4h BTC candidates supported by early period; retain .25% baselineplan candidate and .50% competitor. Longer8h has higher price mean but more TP/exit conflicts. SOL .50%4h uses trigger then fresh15m reversal then next1m quote quality>=.25%, no expensive fallback. No pertrade future extrema tuning.',selected=selected,reference='BTC actual native BTC_ENTRY fill price and fill_ns, admitted netQ, original referenceQ/q0/q1 and rights all preserved in parentsCSV. SOL simultaneous Bybit execution minute close at actual BTC fill, NOT actual hedge fill.',horizon='Full firstUTCday plus active-only min(dayend,observed historicalBTCclose) diagnostics separate in excursionCSV; future BTCclose truncation used ONLY offline evaluation, never signal. Grid is same-path price screening; early firstTP/mandatoryexit and pastBTCclose flags expose native conflicts, not executed legal child decisions.',execution='Limit proxy requires high/low penetration1bp beyond limit strictly after fill. No queue, spread, partialfill, trade/L2 evidence. Touch alone not filled. Trigger strictly precedes confirmation15m start; nextminute close quote only. OHLC intraminute ordering unknown.',warmup='Official public BybitJun1..Sep1 2024 1H2208bars/asset, gapfree. ExactrawURL+SHA in data-warmup-manifest.json. Completed720/2160hour simple returns before actualentry; all105 beta30/90 available. Pre-existing24m canonical1m hashes verified.',constraints='Price proxy NOT nativeROI. TP acceleration/cancel races, beta rebalancing, native margin min, funding/slippage/queue, joint path not modeled. UNKNOWN funding is not zero. No backtest run or live changes. Five reproducible checks screening-handchecks.json.',handcheck_count=5))
sources['reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution-episodes.csv']=sha('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution-episodes.csv');sources[str(ROOT/'bybit-1m/manifest.json')]=sha(ROOT/'bybit-1m/manifest.json')
save('manifest-screening.json',{'input_sha256':sources,'output_sha256':{str(p):sha(p) for p in OUT.glob('*') if p.is_file() and p.name.startswith(('screening','data','coverage'))}})
print(json.dumps([x for x in summ if x['group']=='ALL']),flush=True)
