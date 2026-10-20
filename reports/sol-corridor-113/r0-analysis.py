"""One bounded R0 stored-observation screen; post-SOL phase does NOT certify account settlement. No engine, trades, counterfactual PnL or optimizer."""
import csv,gzip,json,math,statistics as st,hashlib,time,resource,bisect,collections
from pathlib import Path
import pyarrow.parquet as pq
P=Path('reports/sol-corridor-113');P.mkdir(exist_ok=True);T=time.monotonic()
START=1725148800000000000;END=1788220800000000000;DAY=86400000000000;FEE=.00055;STEP=.1
def utc(t):return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(t/1e9))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def quant(v):
 v=sorted(v);z=(len(v)-1)*.95;i=int(z);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(z-i)
ref=json.load(open('reports/carry-pair-run-113/control-reference.json'));raw=json.load(open(ref['raw_path']));assert sha(ref['raw_path'])==ref['raw_sha256']
early=json.load(open('reports/immediate-sol-insurance-113/postmortem-early-chop.json'));entries=early['entry_rows'];ets=[int(e['P0_known_ms'])*1000000 for e in entries]
pins={'winner_raw':ref,'winner_source_hashes':raw['source_hashes'],'winner_data_hash':raw['data_hash'],'winner_policy_hash':raw['policy_hash'],'winner_config_hash':raw['config_hash'],'product_HEAD':'5b45a7cfa352315333cc127b72e87ddf88b07eb2','BTC_only_TOTAL':'280748.52263020'}
for f in ['challenge-cushion.json','postmortem-early-chop.json','btc-only-launch-and-completion.json','root-postmortem-final-verification.json']:
 p=Path('reports/immediate-sol-insurance-113')/f
 if p.exists():pins[str(p)]=sha(p)
d={}
for a in ['BTC','SOL']:
 p=Path('runtime/var/data/normalized/bybit-'+a+'USDT-daily.parquet');pins[str(p)]=sha(p);d[a]={int(x['open_time_ms']+86400000)*1000000:float(x['close']) for x in pq.read_table(p,columns=['open_time_ms','close']).to_pylist()}
times=sorted(set(d['BTC'])&set(d['SOL']));est={}
for t in times:
 if t<START-DAY or t>END:continue
 tt=[z for z in times if z<=t][-91:]
 if len(tt)<91 or any(b-a!=DAY for a,b in zip(tt,tt[1:])):continue
 x=[math.log(d['BTC'][b]/d['BTC'][a]) for a,b in zip(tt,tt[1:])];y=[math.log(d['SOL'][b]/d['SOL'][a]) for a,b in zip(tt,tt[1:])]
 beta=st.covariance(x,y)/st.variance(x);a=math.expm1(quant([abs(v) for v in x]));u=math.expm1(quant([abs(s-beta*b) for s,b in zip(y,x)]));assert beta>0 and all(math.isfinite(v) and v>0 for v in [beta,a,u]);est[t]=(beta,a,u)
et=sorted(est);checks=[]
for r in json.load(open('reports/immediate-sol-insurance-113/challenge-cushion.json'))['entry_money_examples']:
 z=est[max(t for t in et if t<=r['start_ns'])];checks.append(max(abs(z[0]-r['beta']),abs(z[1]-r['a_simple']),abs(z[2]-r['u_simple'])))
assert max(checks)<1e-10
def marks(a):
 for b in pq.ParquetFile('runtime/var/data/normalized/bybit-'+a+'USDT-mark-1m.parquet').iter_batches(batch_size=4096,columns=['open_time_ms','close']):
  q=b.to_pydict()
  for t,c in zip(q['open_time_ms'],q['close']):yield int(t),float(c)
bm=marks('BTC');sm=marks('SOL')
def solve(N,h,b,a,u,C):
 def L(x):return a*abs(N-b*x)+u*x+FEE*(abs(x-h)+N+x)
 xs=sorted(set([0.,h,N/b]));ys=[L(x) for x in xs];ml=min(ys);xm=min((x for x,y in zip(xs,ys) if abs(y-ml)<1e-8),key=lambda x:abs(x-h))
 if ml>C+1e-8:return None,None,xm,ml,L
 ok=[]
 for i,x in enumerate(xs):
  if ys[i]<=C+1e-8:ok.append(x)
  if i+1<len(xs) and (ys[i]-C)*(ys[i+1]-C)<0:ok.append(x+(C-ys[i])*(xs[i+1]-x)/(ys[i+1]-ys[i]))
 if ys[-1]<=C+1e-8:ok.append(xs[-1]+(C-ys[-1])/(a*b+u+2*FEE))
 return max(0.,min(ok)),max(ok),xm,ml,L
clusters=[]
for i,c in enumerate(early['CHOP']['descriptive11clusters_coverage']):clusters.append({'id':i+1,'first':c['first'],'last':c['last'],'start_ns':ets[c['first']-1],'end_ns':int(entries[c['last']-1]['last_exit_ms'])*1000000,'counts':collections.Counter(),'first_violation':None,'min_C':None})
exc=[];wanted=collections.defaultdict(list)
for r in csv.DictReader(open('reports/winner-6077107-stats/risk-drawdowns.csv')):
 if float(r['drawdown_percent'])<=50:continue
 z={'id':r['id'],'max_DD_percent':r['drawdown_percent']}
 for k in ['peak','first_underwater','trough','recovery']:
  z[k]=json.loads(r[k]) if r[k] else None
  if z[k]:wanted[int(z[k]['ns'])].append('DD'+r['id']+'/'+k)
 exc.append(z)
import datetime
for s in ['2024-10-11T19:07','2025-01-13T14:34','2025-01-13T14:36','2025-04-06T18:04','2025-04-06T18:07','2025-04-06T20:37','2025-04-06T20:38']:
 wanted[int(datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc).timestamp()*1e9)].append('CARRY_COUNTEREXAMPLE_MATCHING_WINNER_TIME')
cases={d:{'counts':collections.Counter(),'first_violation':None,'min_C':None} for d in ['2024-10-11','2025-01-13','2025-04-06']}
cnt=collections.Counter();kinds=collections.defaultdict(collections.Counter);monthly=collections.defaultdict(collections.Counter);daily=collections.defaultdict(collections.Counter);mc=collections.Counter();first={};entryfirst={};ec=collections.Counter();land=[];H=10000.;nativeH=10000.;nativeDD=0.;n=0;nr=0;nm=0;boundary=0;lastbar=None;lastmonth=None;markdiff=0.;minC=None;maxgap=None;firstbad=None;top=[]
gapminutes=0.;spells=0;spellsum=0.;prevadjust=False;targetvariation=0.;prevq=None;run=None;runs=0;rw=None;rf=open(P/'r0-classification-runs.csv','w')
def flush(r):
 global rw,runs
 if rw is None:rw=csv.DictWriter(rf,fieldnames=list(r));rw.writeheader()
 rw.writerow(r);runs+=1
for r in csv.DictReader(gzip.open(raw['minute_risk_observations']['trace_path'],'rt')):
 nr+=1;ns=int(r['close_available_ns']);phase=r['phase']
 if 'post_boundary' not in phase:
  e=float(r['paired_close_equity']);nativeH=max(nativeH,e);nativeDD=max(nativeDD,1-e/nativeH)
 if phase!='post_quote_paired_close' and not(ns==END and phase=='pre_quote_paired_close'):continue
 bar=int(r['bar_open_ms']);bt,bp=next(bm);stt,sp=next(sm);nm+=1;assert bt==stt==bar
 if lastbar is not None:assert bar==lastbar+60000
 lastbar=bar
 if ns==END:boundary+=1;continue
 n+=1;E=float(r['paired_close_equity']);cash=float(r['cash']);H=max(H,E);C=E-.55*H;minC=C if minC is None else min(minC,C)
 B=0.;held=0.;bq=0.;sq=0.;ps=json.loads(r['native_positions_and_mark_ohlc_json'])
 for p in ps:
  q=float(p['quantity'])*(1 if p['side']=='2' else -1);isbtc=p['instrument_id'].startswith('BTC');markdiff=max(markdiff,abs(float(p['mark_ohlc']['close'])-(bp if isbtc else sp)))
  if isbtc:bq=q;B=q*bp
  else:sq=q;held=q*sp
 kind='both' if B and held else 'BTC_only' if B else 'SOL_only' if held else 'flat';date=utc(bar*1000000)[:10];mon=date[:7];ei=bisect.bisect_right(ets,ns)-1;ep=entries[ei] if ei>=0 else None
 t=et[bisect.bisect_right(et,ns)-1];b,a,u=est[t];assert t<=ns and ns-t<DAY
 sign=-1 if B>0 else 1 if B<0 else 1 if held>0 else -1 if held<0 else 0
 if B and held:assert B*held<0
 N=abs(B);h=abs(held);lo,hi,xm,ml,L=solve(N,h,b,a,u,C);lh=L(h)
 if lo is None:cl='SOL_RISK_INFEASIBLE';target=xm;lot='NO_MATH_CORRIDOR'
 else:
  target=min(max(h,lo),hi);q=target/sp;opts={max(0.,math.floor(q/STEP+1e-9)*STEP)*sp,max(0.,math.ceil(q/STEP-1e-9)*STEP)*sp};opts=[v for v in opts if lo-1e-7<=v<=hi+1e-7 and L(v)<=C+1e-7]
  if not opts:cl='LOT_INFEASIBLE';lot='NO_NATIVE_LOT_IN_CORRIDOR'
  else:
   target=min(opts,key=lambda x:abs(x-h));lot='STEP_RECHECK_PASS'
   if lh<=C+1e-8:cl='FLAT_NO_ACTION' if kind=='flat' else 'SAFE_ALPHA_HELD' if held else 'BTC_ONLY_SAFE';target=h
   elif target>h+1e-7:cl='HEDGE_ADD'
   else:cl='ALPHA_TRIM'
   assert L(target)<=C+1e-6
 m='SOL_MARGIN_UNAVAILABLE' if target>h+1e-7 else 'NO_INCREMENTAL_MARGIN_FOR_REDUCE_OR_HOLD';ts=sign*target;tq=ts/sp;gap=abs(ts-held);viol=cl not in ['FLAT_NO_ACTION','SAFE_ALPHA_HELD','BTC_ONLY_SAFE'];adjust=viol and gap>1e-7
 z={'utc':utc(ns),'ns':ns,'kind':kind,'classification':cl,'E':E,'cash':cash,'native_U':E-cash,'H_completed':H,'C':C,'B':B,'held_SOL_notional':held,'BTC_qty':bq,'SOL_qty':sq,'BTC_mark':bp,'SOL_mark':sp,'beta':b,'a':a,'u':u,'estimate_close_utc':utc(t),'L_held':lh,'L_min':ml,'lower_abs_SOL_notional':lo,'upper_abs_SOL_notional':hi,'target_SOL_notional':ts,'target_SOL_qty':tq,'L_target':L(target),'turnover_demand_notional':gap,'margin_status':m,'lot_status':lot,'best_effort_abs_SOL_notional':xm,'best_effort_reduce_only_abs_SOL_notional':min([0.,h]+([N/b] if N/b<=h else []),key=L),'episode':ep['number'] if ep else None}
 cnt[cl]+=1;kinds[kind][cl]+=1;monthly[mon][cl]+=1;daily[date][cl]+=1;mc[m]+=1
 if cl not in first:first[cl]=dict(z)
 if viol and firstbad is None:firstbad=dict(z)
 if maxgap is None or gap>maxgap['turnover_demand_notional']:maxgap=dict(z)
 if adjust:
  gapminutes+=gap
  if not prevadjust:spells+=1;spellsum+=gap
 prevadjust=adjust
 if prevq is not None:targetvariation+=abs(tq-prevq)*sp
 prevq=tq
 if gap>0:
  top.append(dict(z));top.sort(key=lambda x:x['turnover_demand_notional'],reverse=True)
  if len(top)>20:top.pop()
 if ep and B and ns<=int(ep['last_exit_ms'])*1000000:
  if ep['number'] not in entryfirst:entryfirst[ep['number']]=dict(z)
  if ns-ets[ei]<60*60000000000:ec[cl]+=1
 if ns in wanted:land.append({'tags':wanted[ns],'state':dict(z)})
 for c in clusters:
  if c['start_ns']<=ns<=c['end_ns']:
   c['counts'][cl]+=1;c['min_C']=C if c['min_C'] is None else min(c['min_C'],C)
   if viol and c['first_violation'] is None:c['first_violation']=dict(z)
 if date in cases:
  c=cases[date];c['counts'][cl]+=1;c['min_C']=C if c['min_C'] is None else min(c['min_C'],C)
  if viol and c['first_violation'] is None:c['first_violation']=dict(z)
 key=(kind,cl,m)
 if run is None or key!=(run['kind'],run['classification'],run['margin_status']):
  if run:flush(run)
  run={'start_utc':utc(ns),'end_utc':utc(ns),'minutes':1,'kind':kind,'classification':cl,'margin_status':m,'first_E':E,'first_H':H,'min_C':C,'max_gap':gap}
 else:run['end_utc']=utc(ns);run['minutes']+=1;run['min_C']=min(run['min_C'],C);run['max_gap']=max(run['max_gap'],gap)
 if mon!=lastmonth:
  if lastmonth is not None:
   out={'through':utc(ns),'states':n,'counts':dict(cnt),'by_kind':dict(kinds),'early':dict(ec),'first_violation':firstbad,'RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss};save('r0-progress.json',out);print(json.dumps({'through':utc(ns),'states':n,'counts':dict(cnt)}),flush=True)
  lastmonth=mon
if run:flush(run)
rf.close();assert nr==3153600 and n==1051199 and nm==1051200 and boundary==1;assert abs(nativeDD*100-66.31878024969152)<1e-9
for g in [bm,sm]:
 try:next(g);raise ValueError('extra marks')
 except StopIteration:pass
def outcsv(name,rows):
 if not rows:return
 with open(P/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
outcsv('r0-daily.csv',[{'date':k,'states':sum(v.values()),**{c:v.get(c,0) for c in cnt}} for k,v in daily.items()]);outcsv('r0-monthly.csv',[{'month':k,'states':sum(v.values()),**{c:v.get(c,0) for c in cnt}} for k,v in monthly.items()]);outcsv('r0-first-BTC-states.csv',list(entryfirst.values()));outcsv('r0-landmarks.csv',land);outcsv('r0-11-clusters.csv',clusters)
res={'status':'R0_SCENARIO_SCREEN_NOT_BACKTEST_OR_ROI','pins':pins,'checks':{'trace_rows':nr,'completed_states':n,'aligned_marks_each':nm,'terminal_leftlimit_excluded':boundary,'native_global_DD_reproduced_percent':nativeDD*100,'challenge_estimate_max_difference':max(checks),'source_native_mark_max_difference':markdiff,'single_trace_pass':True,'causal_valid_daily90':True,'BTC_never_changed':True,'safe_held_never_changed':True},'classification_minutes':cnt,'by_exposure_kind':kinds,'by_month':monthly,'margin_minutes':mc,'first_by_classification':first,'first_violation':firstbad,'minimum_C':minC,'completed_H_max':H,'early_first60minute_counts':ec,'first_BTC_state_class_counts':collections.Counter(x['classification'] for x in entryfirst.values()),'first_BTC_states':list(entryfirst.values()),'all_above50_native_excursions':exc,'landmarks':land,'saved_11_clusters':clusters,'carry_counterexample_dates_on_winner':cases,'turnover_demand':{'contiguous_adjustment_spells':spells,'first_spell_gap_notional_sum':spellsum,'inventory_gap_notional_minute_sum':gapminutes,'proposed_quantity_total_variation_notional':targetvariation,'max_snapshot_gap':maxgap,'classification_runs':runs},'largest20_gaps':top,'resources':{'seconds':time.monotonic()-T,'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}
res['method']={'account_finality_caveat':'The R1 native fixture proved that a subclass post-SOL recorder callback can precede actual fill settlement. The archive therefore supplies 1,051,199 observed post-SOL phase samples, NOT certified finalized account checkpoints. Completed quote-recording phase does not mean settled native account. R0 E/H/C and feasibility counts remain mathematical screens on stored observations only, not finalized native-budget proof or candidate ROI. The archived native all-phase DD66.31878025% is unchanged and NOT recertified here. R1 must use a deferred native receipt after a proven later settlement boundary.','E_H':'Observed post-SOL phase E values only; archival account-finality is NOT certified. H=max(10000, earlier observed post-SOL E including the current observation); prequote/postBTC observations do not update this screen H. The recorder callback may precede actual fill settlement, so E/H/C do not prove finalized account-budget admissibility. The terminal prequote left-limit remains excluded. Legacy names completed_states, completed_H_max and H_completed refer to the recorded-phase calculation, not certified account settlement. The native all-phase DD remains a separate unchanged archival metric, not recertified.'}
res['checks'].update({'observed_post_SOL_samples':n,'account_settlement_finality_certified':False,'archived_allphase_DD_recertified':False})
save('r0-statistics.json',res);print(json.dumps({'FINAL':True,'counts':dict(cnt),'early':dict(ec),'first_entry':dict(res['first_BTC_state_class_counts']),'resources':res['resources']}),flush=True)
