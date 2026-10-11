"""One streaming pass of immutable V3 native observations; no economic replay."""
import bisect,csv,gzip,hashlib,json,sys,time
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0,str(Path('runtime').resolve()))
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
out=Path('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes');out.mkdir(exist_ok=True)
base=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-sizing-v3-20261011/result')
raw=base/'v0-selective-lifecycle-cap30m-btc-direction.json';trace=base/'minute-native-risk.csv.gz'
r=json.load(raw.open());risk=json.load((base/'minute-risk-summary.json').open())
assert hashlib.sha256(raw.read_bytes()).hexdigest()=='caa6b209142f4a005f8cd73ee00d030bd841c6a9669e98c971b15f93c36c902a'
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def utc(ns):return datetime.fromtimestamp(int(ns)//10**9,timezone.utc).isoformat()
def sym(f):return 'BTC' if f['instrument'].startswith('BTC') else 'SOL'
def total(fs,k):return sum((D(f[k]) for f in fs),D(0))
def snapshot(row):
 E=D(row['paired_close_equity']);parts=[]
 for x in json.loads(row['native_positions_and_mark_ohlc_json']):
  s='BTC' if x['instrument_id'].startswith('BTC') else 'SOL';inst=BTC_PERP if s=='BTC' else SOL_PERP
  lo,hi,cl=(inst.make_price(D(x['mark_ohlc'][k])).as_decimal() for k in ('low','high','close'))
  lp,hp=D(x['low_native_pnl']),D(x['high_native_pnl']);pnl=lp if hi==lo else lp+(cl-lo)/(hi-lo)*(hp-lp);n=D(x['quantity'])*cl
  parts.append({'symbol':s,'side':x['side'],'quantity':x['quantity'],'avg_entry_price':x['avg_px_open'],'native_rounded_mark_close':str(cl),'marked_notional':str(n),'native_endpoint_close_unrealized_attribution':str(pnl),'gross_notional_to_equity':str(n/E)})
 unrl=E-D(row['cash']);res=unrl-sum((D(p['native_endpoint_close_unrealized_attribution']) for p in parts),D(0));assert abs(res)<D('.01'),(row,res)
 return {'ns':int(row['close_available_ns']),'utc':utc(row['close_available_ns']),'phase':row['phase'],'cash':row['cash'],'equity':str(E),'native_unrealized':str(unrl),'asset_interpolation_residual':str(res),'gross_notional_to_equity':str(sum((D(p['marked_notional']) for p in parts),D(0))/E),'positions':parts}
# Match authoritative native order side to each immutable fill audit record.
nf=defaultdict(deque)
for f in csv.DictReader(open(r['execution_artifacts']['fills']['path'])):
 ns=int(datetime.fromisoformat(f['ts_last']).timestamp())*10**9;s='BTC' if f['instrument_id'].startswith('BTC') else 'SOL'
 nf[(ns,s,D(f['filled_qty']),D(f['avg_px']).quantize(D('.000001')))].append(f)
fillgroups=defaultdict(list);episodes={'BTC':[],'SOL':[]};qty={'BTC':D(0),'SOL':D(0)};fillout=[]
for f in r['fill_audit']:
 s=sym(f);ns=int(f['fill_ns']);q=D(f['qty']);key=(ns,s,q,D(f['px']).quantize(D('.000001')));native=nf[key].popleft()
 entry=f['action'] in ('BTC_ENTRY','SOL_ADD')
 if entry and qty[s]==0:episodes[s].append({'number':len(episodes[s])+1,'symbol':s,'side':native['side'],'start_ns':ns,'start_utc':utc(ns),'end_ns':None,'fees':D(0),'native_fill_callback_cash_net':D(0),'callback_gross':D(0),'fill_count':0})
 e=episodes[s][-1];e['fees']+=D(f['commission']);e['fill_count']+=1
 qty[s]+=q if entry else -q;assert qty[s]>=0
 if qty[s]==0:e.update(end_ns=ns,end_utc=utc(ns))
 a=dict(f,symbol=s,episode=e['number'],native_side=native['side'],client_order_id=native['client_order_id']);fillgroups[(ns,s)].append(a);fillout.append(a)
assert all(not z for z in nf.values());assert qty=={'BTC':D(0),'SOL':D(0)}
fees=total(r['fill_audit'],'commission');assert fees==D(r['native_fees'])
top=[]
for i,e in enumerate(risk['curves']['all_native_close_samples']['top3_distinct_excursions'],1):
 top.append({'rank':i,'native_summary':e,'landmarks':{},'max_prequote_gross_leverage':None,'state_minutes':Counter()})
callbacks=[];boundary_cash=[];unknown_callbacks=[];phases=Counter();currentpeak=D(10000);peakrow=None;active=None;excursions=[];last_cash=None;matchedgroups=set();rows=0;start=time.time()
def finish_active(rec):
 global active
 if active is not None:
  active['recovery']=rec
  if active['max_drawdown_percent']>D(50):excursions.append(active)
 active=None
for row in csv.DictReader(gzip.open(trace,'rt')):
 rows+=1;ns=int(row['close_available_ns']);rawphase=row['phase'];phases[rawphase]+=1;phase=rawphase.removeprefix('post_boundary_');cash=D(row['cash']);E=D(row['paired_close_equity'])
 if phase=='pre_quote_paired_close':
  if last_cash is not None and cash!=last_cash:boundary_cash.append({'ns':ns,'utc':utc(ns),'cash_delta':str(cash-last_cash),'class':'PREQUOTE_BOUNDARY_UNKNOWN_SIGNED_FUNDING_OR_OTHER'})
  prevphasecash=cash
 else:
  s='BTC' if phase=='post_btc_quote_paired_close' else 'SOL';delta=cash-prevphasecash;fs=fillgroups.get((ns,s),[])
  if fs:
   matchedgroups.add((ns,s));epnums={f['episode'] for f in fs};assert len(epnums)==1,(ns,s,epnums)
   commission=total(fs,'commission');gross=delta+commission;e=episodes[s][next(iter(epnums))-1];e['native_fill_callback_cash_net']+=delta;e['callback_gross']+=gross
   callbacks.append({'ns':ns,'utc':utc(ns),'symbol':s,'episode':next(iter(epnums)),'cash_change':str(delta),'actual_fees':str(commission),'native_callback_gross_before_fees':str(gross),'reasons':sorted({f['reason'] for f in fs}),'fill_rows':len(fs),'is_exit':any(f['action'] not in ('BTC_ENTRY','SOL_ADD') for f in fs),'orders':[f['client_order_id'] for f in fs]})
  elif delta:unknown_callbacks.append({'ns':ns,'utc':utc(ns),'phase':phase,'cash_delta':str(delta)})
  prevphasecash=cash
 last_cash=cash
 # The end-exclusive prequote is retained; its settlement callbacks excluded.
 if ns>=int(risk['end_exclusive_ns']) and phase!='pre_quote_paired_close':continue
 for ep in top:
  e=ep['native_summary'];a,b,c=(int(e[k]['timestamp_ns']) for k in ('peak','trough','recovery'))
  for k in ('peak','trough','recovery'):
   if ns==int(e[k]['timestamp_ns']) and E==D(e[k]['equity']) and k not in ep['landmarks']:ep['landmarks'][k]=snapshot(row)
  if a<=ns<=b and phase=='pre_quote_paired_close':
   point=snapshot(row);state='+'.join(sorted(p['symbol'] for p in point['positions'])) or 'FLAT';ep['state_minutes'][state]+=1
   if ep['max_prequote_gross_leverage'] is None or D(point['gross_notional_to_equity'])>D(ep['max_prequote_gross_leverage']['gross_notional_to_equity']):ep['max_prequote_gross_leverage']=point
 if E>=currentpeak:
  if active:finish_active(snapshot(row))
  currentpeak=E;peakrow=dict(row)
 else:
  dd=(currentpeak-E)/currentpeak*100
  if active is None:active={'peak':None,'peakrow':peakrow,'max_drawdown_percent':D(0),'trough':None,'thresholds':{}}
  for threshold in (25,35,45,50):
   if dd>=threshold and str(threshold) not in active['thresholds']:active['thresholds'][str(threshold)]=snapshot(row)
  if dd>active['max_drawdown_percent']:
   active['max_drawdown_percent']=dd
   # Snapshot only when drawdown has reached a meaningful threshold.
   if dd>=25:active['trough']=snapshot(row)
 if rows%600000==0:print('rows',rows,'seconds',round(time.time()-start),flush=True)
if active:finish_active(None)
import pickle
with open('/tmp/cm113-v3-attribution-scan-checkpoint.pkl','wb') as checkpoint:
 pickle.dump({k:globals()[k] for k in ('callbacks','boundary_cash','unknown_callbacks','episodes','top','excursions','phases','matchedgroups','fillgroups','rows','start')},checkpoint)
assert matchedgroups==set(fillgroups),(set(fillgroups)-matchedgroups,dict(phases))
assert rows==3153600
for e in excursions:
 e['peak']=snapshot(e.pop('peakrow'));e['max_drawdown_percent']=str(e['max_drawdown_percent'])
for e in episodes.values():
 for ep in e:
  ep['native_cash_net_ex_unallocated']=str(ep.pop('native_fill_callback_cash_net'));ep['callback_gross']=str(ep['callback_gross']);ep['fees']=str(ep['fees']);assert ep['end_ns'] is not None

def assetunrl(p,s):return sum((D(x['native_endpoint_close_unrealized_attribution']) for x in p['positions'] if x['symbol']==s),D(0))
def decompose(peak,trough):
 a,b=peak['ns'],trough['ns'];win=[f for f in callbacks if a<int(f['ns'])<=b];cashdelta=D(trough['cash'])-D(peak['cash']);ud=D(trough['native_unrealized'])-D(peak['native_unrealized']);Edelta=D(trough['equity'])-D(peak['equity']);assert cashdelta+ud==Edelta
 assets={}
 for s in ('BTC','SOL'):
  ws=[f for f in win if f['symbol']==s];gross=total(ws,'native_callback_gross_before_fees');fee=total(ws,'actual_fees');u=assetunrl(trough,s)-assetunrl(peak,s)
  assets[s]={'native_fill_callback_gross':str(gross),'actual_window_fees':str(fee),'native_fill_callback_cash_net':str(gross-fee),'native_endpoint_unrealized_change':str(u),'sum_cash_net_and_unrealized_change':str(gross-fee+u),'closed_episodes':[ep for ep in episodes[s] if a<ep['end_ns']<=b]}
 res=cashdelta-sum((D(x['native_fill_callback_cash_net']) for x in assets.values()),D(0));inter=ud-sum((D(x['native_endpoint_unrealized_change']) for x in assets.values()),D(0));need=max(D(0),D(peak['equity'])/2-D(trough['equity']))
 return {'equity_change':str(Edelta),'native_cash_change':str(cashdelta),'native_unrealized_change':str(ud),'assets':assets,'unallocated_cash_residual_not_assigned_funding':str(res),'native_unrealized_attribution_residual_change':str(inter),'avoided_loss_required_at_unchanged_peak_for_DD50_arithmetic_only':str(need),'observed_loss_share_required':str(need/-Edelta),'window_callbacks':win,'boundary_unknown_cash_events':[x for x in boundary_cash+unknown_callbacks if a<x['ns']<=b]}
for e in top:
 assert len(e['landmarks'])==3;e['decomposition']=decompose(e['landmarks']['peak'],e['landmarks']['trough']);e['state_minutes']=dict(e['state_minutes'])
for e in excursions:e['decomposition']=decompose(e['peak'],e['trough'])
# Completed-episode streaks use actual native cash changes only; funding unallocated.
stats={}
for s,es in episodes.items():
 nets=[D(e['native_cash_net_ex_unallocated']) for e in es];streak=longest=0
 for n in nets:streak=streak+1 if n<0 else 0;longest=max(longest,streak)
 stats[s]={'episodes':len(es),'wins':sum(n>0 for n in nets),'losses':sum(n<0 for n in nets),'max_consecutive_losses':longest,'winning_sum':str(sum((n for n in nets if n>0),D(0))),'losing_sum':str(sum((n for n in nets if n<0),D(0))),'native_fill_callback_cash_net':str(sum(nets,D(0)))}
reasonstats=[]
for s,reason in sorted({(f['symbol'],z) for f in callbacks for z in f['reasons']}):
 fs=[f for f in callbacks if f['symbol']==s and f['reasons']==[reason]]
 reasonstats.append({'symbol':s,'reason':reason,'native_callbacks':len(fs),'cash_net_actual_fees':str(total(fs,'cash_change')),'gross':str(total(fs,'native_callback_gross_before_fees')),'actual_fees':str(total(fs,'actual_fees')),'orders':sum(len(f['orders']) for f in fs),'mixed_reason_callbacks_excluded':True})
fullcash=D(r['terminal_total'])-D(10000);fillcash=total(callbacks,'cash_change');unalloc=fullcash-fillcash;unknown=total(boundary_cash+unknown_callbacks,'cash_delta');assert abs(unalloc-unknown)<D('.00000001')
report={'provenance':{'source_commit':'a9cbb737a5239d10b9ffcb97d55f997917945263','head_at_start':'868104b','raw_path':str(raw),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'trace_path':str(trace),'trace_sha256':digest(trace),'native_fills_sha256':r['execution_artifacts']['fills']['sha256'],'method':'Native observed callback CASH changes at filled-instrument callback, gross=callback_cash_change+actual commission; no trade-PnL reconstruction. Same-callback nonfill accounting cannot be separately identified; residual boundary/no-fill cash explicit. Native endpoint close PnL interpolation uses instrument-rounded marks and reconciles cents. No economic engine/backtest.'},'native_TOTAL':r['terminal_total'],'fees':str(fees),'stop_configuration':{k:r['config'][k] for k in ('btc_close_stop_fraction','sol_z_stop','portfolio_loss_limit_fraction','deposit_protection')},'liquidations':r['liquidation_count'],'true_fixed_SL_count':0,'daily_trail':'Daily best_f>0.03; close when f<=best_f-0.03. Three entry-return percentage points retrace after profit arming; not downside portfolio stop. REGIME=opposite daily EMA regime; SOL follows groupclose.','top3':top,'all_global_native_excursions_over50':excursions,'native_callback_events':callbacks,'unallocated_cash_events':boundary_cash+unknown_callbacks,'episodes':episodes,'episode_stats':stats,'single_reason_callback_stats':reasonstats,'full_native_cash_gain':str(fullcash),'full_fill_callback_cash_net':str(fillcash),'unallocated_cash_residual':str(unalloc),'signed_funding':'UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA','checks':{'trace_rows':rows,'phase_counts':dict(phases),'matched_fill_callback_groups':len(matchedgroups),'all_actual_fees':str(total(callbacks,'actual_fees')),'native_fee_reconcile':total(callbacks,'actual_fees')==fees,'full_cash_reconcile':True,'all_landmark_asset_uPnL_residual_lt_cent':True,'new_engines':0,'streaming_trace_passes':2,'corrective_scan_reason':'Terminal rows prefix post_boundary_ stripped only for accounting callback mapping; settlement still excluded from interval DD. First scan failed final group-coverage guard before output; second scan checkpoints before checks.','seconds':round(time.time()-start,2)}}
(out/'attribution.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'attribution-callbacks.csv').open('w') as f:
 fields=['ns','utc','symbol','episode','cash_change','actual_fees','native_callback_gross_before_fees','reasons','fill_rows','is_exit','orders'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(callbacks)
with (out/'attribution-episodes.csv').open('w') as f:
 allrows=episodes['BTC']+episodes['SOL'];w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
(out/'attribution-checks.json').write_text(json.dumps(report['checks'],indent=2)+'\n')
print(json.dumps({'top3':[{'rank':e['rank'],'decomposition':e['decomposition'],'landmarks':e['landmarks']} for e in top],'over50_count':len(excursions),'episode_stats':stats,'full_residual':str(unalloc)},indent=2),flush=True)

# Only the finalized report is a usable perasset attribution output.
import runpy
runpy.run_path(str(out/'attribution-finalize.py'),run_name='__main__')
