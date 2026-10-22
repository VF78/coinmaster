"""Analysis-only pinned saved-price diagnostics. No strategy engine or portfolio PnL."""
import os,sys,time,signal,resource,json,hashlib,datetime,collections
START=time.monotonic();signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('180s hardstop')));signal.alarm(180)
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
M=60_000_000_000;H=60*M;B=4*H
base=os.environ.get('CM_ANALYSIS_BASE','/root/.openclaw/workspace/coinmaster/coinmaster')
market=base+'/runtime/var/data/normalized/bybit-BTCUSDT-execution-1m.parquet'
native=os.environ.get('CM_ANALYSIS_NATIVE','/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-rnd-s0-20261020T170935Z/result/v0-selective-lifecycle-cap30m-btc-split50-d0.0025-planref-v1-tp-ioc-btc-direction.json')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for v in iter(lambda:f.read(1024*1024),b''):h.update(v)
 return h.hexdigest()
def guard():
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
 if rss>320*1024**2:raise MemoryError('RSS>320MiB')
 if time.monotonic()-START>180:raise TimeoutError('180s')
 return rss
def utc(ns):return datetime.datetime.fromtimestamp(int(ns)/1e9,datetime.timezone.utc).isoformat()
assert sha(market)=='9c48e97ce1544bb5b7169772eea2d06d8a0c3fefd2522e32ece452c2946c0f88'
assert sha(native)=='e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa'
n=json.load(open(native));parents=sorted(n['split_cover_audit']['parents'],key=lambda p:int(p['start_ns']));audit=n['fill_audit'];assert len(audit)==621
pf=pq.ParquetFile(market);ts=[];cs=[]
for batch in pf.iter_batches(batch_size=16384,columns=['open_time_ms','close']):
 ts.append(batch.column(0).to_numpy(zero_copy_only=False));cs.append(batch.column(1).cast(pa.float64()).to_numpy(zero_copy_only=False));guard()
t=np.concatenate(ts);c=np.concatenate(cs);del ts,cs;assert len(t)==1051200 and np.all(np.diff(t)==60000)
a=(t+60000)*1000000;guard();h1=[];h3=[]
for num,p in enumerate(parents,1):
 st=int(p['start_ns']);end=int(parents[num]['start_ns']) if num<len(parents) else int(a[-1])+M
 f=[z for z in audit if z['instrument'].startswith('BTC') and st<=int(z['fill_ns'])<end];ef=[z for z in f if z['action']=='BTC_ENTRY'];outs=[z for z in f if z['action']!='BTC_ENTRY'];assert len(ef)==2
 side=int(p['side']);p0=float(p['planref_v1_p0']);q0=float(p['quantity']);firstq=float(p['first_filled']);secondq=q0-firstq;deadline=int(p['deadline_ns']);terminal=int(p['management_reference_frozen_ns'])
 ordinary=min((int(z['fill_ns']) for z in outs),default=None);bound=min(deadline,ordinary) if ordinary is not None else deadline
 lo=np.searchsorted(a,terminal,side='right');hi=np.searchsorted(a,bound,side='left');r=side*(c[lo:hi]/p0-1)
 def hit(condition):
  ix=np.flatnonzero(condition);return lo+int(ix[0]) if len(ix) else None
 plus=hit(r>=.0025);minus=hit(r<=-.0025);ordinary=min((int(z['fill_ns']) for z in outs),default=None);ni=plus+1 if plus is not None and plus+1<len(a) else None
 validnext=ni is not None and int(a[ni])<bound
 record={'trade_number':num,'side':'LONG' if side==1 else 'SHORT','entry_ns':st,'entry_utc':utc(st),'first_actual_VWAP':p0,'first_half_terminal_ns':terminal,'exact_native_parent_deadline_ns':deadline,'analysis_window_exclusive_end_ns':bound,'first_actual_qty':firstq,'planned_total_qty':q0,'theoretical_second_qty':secondq,'original_completion_reason':p.get('completion_reason','LIMIT_NATIVE'),'plus025_ns':int(a[plus]) if plus is not None else None,'minus025_ns':int(a[minus]) if minus is not None else None,'touch_order':'NEITHER' if plus is None and minus is None else 'PLUS_ONLY' if minus is None else 'MINUS_ONLY' if plus is None else 'PLUS_FIRST' if plus<minus else 'MINUS_FIRST' if minus<plus else 'SAME_CLOSE','conditional_add_reference_ns':int(a[ni]) if validnext else None,'conditional_add_reference_price':float(c[ni]) if validnext else None,'next_close_within_4h':validnext,'first_original_ordinary_fill_ns':ordinary,'ordinary_fill_before_native_deadline':ordinary is not None and ordinary<deadline,'first_ordinary_reason':next((z['reason'] for z in outs if int(z['fill_ns'])==ordinary),None),'ordinary_before_signal':ordinary is not None and plus is not None and ordinary<=int(a[plus]),'ordinary_before_conditional_add':ordinary is not None and validnext and ordinary<=int(a[ni]),'half_only_control':'FIRST_HALF_RETAINED_NO_ADD; economics NOT_COMPUTED','native_candidate_fill':'UNKNOWN','candidate_remaining_orders_SOLrights':'UNKNOWN_AFTER_PATH_DIVERGENCE'}
 if validnext:
  price=float(c[ni]);passive=p0*(1-side*.0025);actual2=next(z for z in ef if int(z['fill_ns'])!=st)
  record.update({'add_delay_minutes':(int(a[ni])-st)/M,'directional_price_cost_vs_passive_target_fraction_of_P0':side*(price-passive)/p0,'additional_taker_vs_maker_fee_fraction_of_second_notional':.00035,'directional_price_cost_vs_original_second_fill_fraction_of_P0':side*(price-float(actual2['px']))/p0})
 h1.append(record)
 # Actual positively referenced TP2 only; generic reductions not imputed.
 activation=[z for z in outs if z['reason']=='BTC_TP2' and side*(float(z['px'])/p0-1)>0]
 for z in activation:
  act=int(z['fill_ns']);exit_ns=max((int(v['fill_ns']) for v in outs),default=act)
  # Fully post-activation UTC4h bars, complete close-only maximum and 4h-only check.
  first_open=((act+B-1)//B)*B;first_close=first_open+B;ii=np.searchsorted(a,first_close);peak=None;peak_ns=None;trigger=None
  while ii<len(a) and int(a[ii])<=exit_ns:
   now=int(a[ii]);ret=side*(float(c[ii])/p0-1)
   if peak is None or ret>peak:peak=ret;peak_ns=now
   if peak-ret>=.03:trigger=ii;break
   ii+=240
  rr={'trade_number':num,'side':'LONG' if side==1 else 'SHORT','activation_fill_ns':act,'activation_fill_utc':utc(act),'activation_price':float(z['px']),'activation_qty':float(z['qty']),'P0':p0,'native_TP2_liquidity':z['native_liquidity_side'],'first_eligible_full_4h_close_ns':first_close,'original_final_fill_ns':exit_ns,'activation_to_original_exit_hours':(exit_ns-act)/H,'trigger_ns':int(a[trigger]) if trigger is not None else None,'trigger_status':'CLOSED4H_GIVEBACK' if trigger is not None else 'NO_TRIGGER_BEFORE_ORIGINAL_EXIT','candidate_fill':'UNKNOWN','order_intent_eligibility':'UNKNOWN','SOL_untouched':True,'alternative_TOTAL_DD_PnL':'NOT_COMPUTED'}
  if trigger is not None:
   ni=trigger+1;within=ni<len(a) and int(a[ni])<exit_ns;now=int(a[trigger]);remaining=sum(float(v['qty'])*(1 if v['action']=='BTC_ENTRY' else -1) for v in f if int(v['fill_ns'])<=now)
   rr.update({'peak_signed_close_return':peak,'peak_close_ns':peak_ns,'trigger_signed_close_return':side*(float(c[trigger])/p0-1),'activation_to_trigger_hours':(now-act)/H,'native_recorded_remaining_qty_at_trigger':remaining,'theoretical_trim_qty':max(0,remaining)/2,'strict_next_close_before_original_exit':within,'conditional_trim_reference_ns':int(a[ni]) if within else None,'conditional_trim_reference_price':float(c[ni]) if within else None,'fee_reference_taker_rate':.00055})
  h3.append(rr)
 guard()
result={'status':'COMPLETE_SAVED_PRICE_DIAGNOSTIC_ONLY','native_runs_added':0,'alternative_TOTAL_DD_PnL':'NOT_COMPUTED','market_source':{'path':market,'sha256':sha(market),'bytes':os.stat(market).st_size,'rows':len(t),'schema':str(pf.schema_arrow)},'native_source':{'path':native,'sha256':sha(native),'fill_rows':len(audit)},'timestamp_contract':'open_time_ms is candle OPEN; close available at open+60000ms; signal then STRICTLY NEXT close reference, never guaranteed executable fill/bidask','h1_rows':h1,'h3_rows':h3,'h3_contract':'actual positive-price-vs-P0 TP2 fills only; full UTC4h bars opened at/after activation; max CLOSE signedreturn vsP0; 3percentagepoint giveback checked only atclosed4h close; next1mclose conditionalreference','elapsed_seconds':time.monotonic()-START,'peak_RSS_bytes':guard()}
print(json.dumps(result))
