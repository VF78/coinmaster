"""Offline actual-native comparison. No replay, synthetic cash or proxy fee additions."""
import argparse,bisect,csv,gzip,hashlib,json,resource,math
from collections import Counter,defaultdict,deque
from datetime import datetime
from decimal import Decimal as D,ROUND_HALF_UP
from pathlib import Path
ARCHIVE=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-sizing-v3-20261011/result/v0-selective-lifecycle-cap30m-btc-direction.json')
OUT=Path('reports/btc-split-sol-cover-20261018')
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(name,x):
 (OUT/name).write_text(json.dumps(x,indent=2,default=str,allow_nan=False)+'\n')
def writecsv(name,rows):
 if not rows:return
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def native_round_price(x,sym):
 scale=10 if sym=='BTC' else 100
 return D(math.floor(float(x)*scale+.5))/D(scale)
def symbol(f):return 'BTC' if f.get('instrument',f.get('instrument_id','')).startswith('BTC') else 'SOL'
def basic(path,label,baseline):
 r=json.load(open(path));nf=r.get('execution_artifacts',{}).get('fills',{});native=csv.DictReader(open(nf['path'])) if nf.get('path') else [];fees=defaultdict(D);liquidity=defaultdict(D)
 for f in r.get('fill_audit',[]):
  fees[symbol(f)]+=D(f['commission']);liquidity[symbol(f)+'_'+f.get('native_liquidity_side','UNKNOWN')]+=D(f['commission'])
 assert sum(fees.values(),D(0))==D(r['native_fees'])
 risk=r.get('minute_risk_observations',{});curve=risk.get('curves',{}).get('all_native_close_samples',{});dd=max((D(x['drawdown_peak_percent']) for x in curve.get('top3_distinct_excursions',[])),default=None)
 audit=r.get('split_cover_audit',{});parents=audit.get('parents',[]);sizing=r.get('entry_sizing_audit',[])
 # q0 decision UTC-day is stable matching key; fresh UUID is deliberately ignored.
 basekeys={int(x['q0_ns'])//86400000000000:x for x in baseline.get('entry_sizing_audit',[])}
 sizing_by_ep={x['episode_id']:x for x in sizing};counts=Counter();integrity=[];side_by_ep={x['episode_id']:x.get('side') for x in r.get('btc_sizing_audit',[])}
 for i,p in enumerate(parents if parents else sizing):
  day=int(p.get('start_ns',p.get('q0_ns','0')))//86400000000000;old=basekeys.get(day);planned=p.get('quantity',p.get('admitted_net_quantity'));filled=p.get('filled',p.get('confirmed_native_entry_qty'));cancel=p.get('cancelled');sameplan=(D(planned)==D(filled)) if planned is not None and filled is not None else None
  side=p.get('side',side_by_ep.get(p.get('episode_id')));counts[str(side)]+=1;accepted=sizing_by_ep.get(p.get('episode_id'),p);step=D(p.get('step','.001'));targets=accepted.get('reference_target_lots',{});omitted=set(accepted.get('omitted_zero_levels',[]));net_target_qty=sum((D(v)*step for k,v in targets.items() if int(k) not in omitted),D(0)) if targets else None
  integrity.append(dict(label=label,number=i+1,episode_id=p.get('episode_id'),day=day,side=side,planned_quantity=planned,filled_quantity=filled,first_quantity=p.get('first_quantity'),cancelled=cancel,filled_equals_plan=sameplan,filled_plus_cancelled_equals_plan=(D(filled)+D(cancel)==D(planned)) if planned is not None and filled is not None and cancel is not None else None,completion_reason=p.get('completion_reason'),stop_reason=p.get('stop_reason'),v3_same_day_exists=old is not None,v3_net_quantity=old.get('admitted_net_quantity') if old else None,equals_v3_quantity=(D(planned)==D(old['admitted_net_quantity'])) if old and planned else None,reference_quantity=accepted.get('reference_btc_qty'),reference_target_lots=json.dumps(targets),omitted_zero_levels=json.dumps(sorted(omitted)),accepted_net_quantity=accepted.get('admitted_net_quantity'),planned_matches_accepted_net=(D(planned)==D(accepted['admitted_net_quantity'])) if planned and accepted.get('admitted_net_quantity') else None,net_targets_match_plan=(net_target_qty==D(planned)) if planned and net_target_qty is not None else None,planned_lots=str(D(planned)/step) if planned else None,first_lots=str(D(p['first_quantity'])/step) if p.get('first_quantity') else None,interpretation='Withinrun planned/filled conservation tested; crossrun notional/equity compounding can change Q. No frozen-Q counterfactual asserted.'))
 summary=dict(label=label,path=str(path),sha256=digest(path),terminal_total=r.get('terminal_total'),terminal_active=r.get('terminal_active'),terminal_reserve=r.get('terminal_reserve'),roi_percent=(D(r['terminal_total'])/D(r.get('config',{}).get('initial_total_usdt','10000'))-1)*100,global_marked_dd_percent=dd,minimum_equity=curve.get('minimum'),liquidation_count=r.get('liquidation_count'),native_fees=r.get('native_fees'),actual_fees_by_asset=dict(fees),actual_fees_by_asset_liquidity=dict(liquidity),signed_funding=r.get('funding',{}).get('signed_amount','UNKNOWN'),funding_count=r.get('funding',{}).get('count'),liquidation_rule='Read unchanged native policy; minute close marked DD is separate from OHLC adverse bounds and proves no intraminute DD cap',cash_drawdown_summary={k:v for k,v in r.get('summary',{}).items() if k in ('drawdown_basis','max_drawdown_percent','max_drawdown_amount','drawdown_start','drawdown_trough')},liquidation_policy=r.get('config',{}).get('execution_policy',{}).get('liquidation'),parents=len(integrity),split_parent_count=len(parents),entry_sizing_count=len(sizing),parent_side_counts=dict(counts),filled_equals_plan_count=sum(x['filled_equals_plan'] is True for x in integrity),unfilled_or_partial_count=sum(x['filled_equals_plan'] is False for x in integrity),filled_plus_cancelled_equals_plan_count=sum(x['filled_plus_cancelled_equals_plan'] is True for x in integrity),planned_matches_accepted_net_count=sum(x['planned_matches_accepted_net'] is True for x in integrity),net_targets_match_plan_count=sum(x['net_targets_match_plan'] is True for x in integrity),v3_same_day_matches=sum(x['v3_same_day_exists'] for x in integrity),changed_quantity_vs_v3=sum(x['equals_v3_quantity'] is False for x in integrity),plan_integrity_limit='Cancelled is native quantity; filled+cancelled conservation separately checked. UnknownACK/order constraints require native fixtures.',native_asset_realized_pnl='UNKNOWN_NATIVE_SETTLED_PERASSET_NOT_EXPORTED',fill_attribution='Separate confirmed-fill attribution is diagnostic, excludes funding; asynchronous callback cash cannot be allocated to asset PnL.',trace_streamed=False)
 # Linear confirmed-fill weighted-average attribution only; cash residual remains unallocated.
 sidekeys=defaultdict(deque)
 for f in native:
  ns=int(datetime.fromisoformat(f['ts_last']).timestamp())*1000000000;sidekeys[(ns,symbol(f),D(f['filled_qty']),D(f['avg_px']).quantize(D('.000001')))].append(f['side'])
 state={k:dict(q=D(0),vwap=D(0),gross=D(0)) for k in ('BTC','SOL')};unknown=[];btcbooks={};stamps=sorted(int(x.get('start_ns',x.get('q1_ns',0))) for x in (parents if parents else sizing))
 for f in r.get('fill_audit',[]):
  sym=symbol(f);q=D(f['qty']);px=D(f['px']);ns=int(f['fill_ns']);match=sidekeys[(ns,sym,q,px.quantize(D('.000001')))]
  if not match:unknown.append(dict(symbol=sym,fill_ns=ns,qty=str(q),px=str(px)));continue
  signed=q if match.popleft()=='BUY' else -q;st=state[sym];old=st['q']
  if sym=='BTC':
   key=stamps[max(0,bisect.bisect_right(stamps,ns)-1)];book=btcbooks.setdefault(key,dict(start_ns=key,entry_qty=D(0),entry_notional=D(0),entry_fees=D(0),exit_fees=D(0),gross=D(0),entry_count=0,last_entry_ns=key,exit_reasons=Counter(),exit_times=[]))
   if f.get('action')=='BTC_ENTRY':book['entry_qty']+=q;book['entry_notional']+=q*px;book['entry_fees']+=D(f['commission']);book['entry_count']+=1;book['last_entry_ns']=max(book['last_entry_ns'],ns)
   else:book['exit_fees']+=D(f['commission']);book['exit_reasons'][f.get('reason','UNKNOWN')]+=1;book['exit_times'].append(ns)
  if old==0 or old*signed>0:st['vwap']=(abs(old)*st['vwap']+q*px)/(abs(old)+q)
  else:
   close=min(abs(old),q);realized=close*(px-st['vwap'])*(1 if old>0 else -1);st['gross']+=realized
   if sym=='BTC':book['gross']+=realized
   if q>abs(old):st['vwap']=px
  st['q']+=signed
 summary['confirmed_fill_weighted_average_attribution']={k:dict(gross=v['gross'],actual_fees=fees[k],net_ex_funding=v['gross']-fees[k],terminal_net_qty=v['q']) for k,v in state.items()} if not unknown else 'UNKNOWN_UNMATCHED_NATIVE_FILL_SIDES'
 summary['unmatched_native_fill_sides']=unknown
 if not unknown:
  summary['unallocated_cash_residual_not_funding']=D(r['terminal_total'])-D(r.get('config',{}).get('initial_total_usdt','10000'))-sum((v['gross']-fees[k] for k,v in state.items()),D(0))
 groups=defaultdict(list)
 for f in r.get('fill_audit',[]):groups[int(f['fill_ns'])].append(f)
 qty={'BTC':D(0),'SOL':D(0)};held=with_sol=0;last=None
 for ts,fs in sorted(groups.items()):
  if last is not None and qty['BTC']>0:
   held+=(ts-last)/1e9
   if qty['SOL']>0:with_sol+=(ts-last)/1e9
  for f in fs:qty[symbol(f)]+=D(f['qty'])*(1 if f['action'] in ('BTC_ENTRY','SOL_ADD') else -1)
  last=ts
 starts={x.get('episode_id'):int(x['start_ns']) for x in audit.get('cover',[]) if x.get('event')=='COVER_START'};anchors={}
 for x in audit.get('cover',[]):
  if x.get('event')=='COVER_ANCHOR' and x.get('episode_id') not in anchors and x.get('start_ns') is not None:anchors[x['episode_id']]=int(x['start_ns'])
 summary['actual_base_entry_latency_seconds']=[dict(episode_id=k,btc_first_fill_ns=v,sol_first_base_fill_ns=anchors.get(k),latency_seconds=(anchors[k]-v)/1e9 if k in anchors else None) for k,v in starts.items()]
 summary['exact_fill_eventtime_heldtime']=dict(btc_held_seconds=held,btc_with_sol_seconds=with_sol,fraction_with_sol=with_sol/held if held else None,method='Actualnativefilledpositionpresence intervals; NOT percentprotection. Can differ from nativecachequote snapshot timing.')
 books=[]
 for key,v in sorted(btcbooks.items()):
  v=dict(v);v.update(entry_vwap=v['entry_notional']/v['entry_qty'] if v['entry_qty'] else None,entry_completion_seconds=(v['last_entry_ns']-key)/1e9,net_ex_funding=v['gross']-v['entry_fees']-v['exit_fees']);v['exit_reasons']=dict(v['exit_reasons']);v['exit_times']=json.dumps(v['exit_times']);books.append(v)
 writecsv('comparison-analysis-'+label+'-btc-fill-attribution.csv',books)
 summary['attribution_method']='Native fills actual prices/quantities/side, weighted average linear confirmedfill diagnostic; not authoritative native settled perasset PnL. Funding UNKNOWN; cash delta residual unallocated.'
 return r,summary,integrity

def stream(path,r,label,coverage_only=False):
 """Single bounded gzip pass; retain only aggregates and at most105 episode records."""
 cover=r.get('split_cover_audit',{}).get('cover',[]);starts=sorted((int(x['start_ns']),float(x['beta']),x.get('episode_id')) for x in cover if x.get('event')=='COVER_START')
 basis='ACTUAL_EPISODE_FIXED_COVER_START_BETA' if starts else 'COMMON_P0_30D_BETA_DIAGNOSTIC_NOT_ORIGINAL_V3_DYNAMIC_BETA'
 if not starts:
  eps=list(csv.DictReader(open(OUT/'screening-parents.csv')));betas={x['parent']:float(x['beta30']) for x in csv.DictReader(open(OUT/'coverage-beta.csv'))};starts=[(int(x['t'])*1000000,betas[x['parent']],x['episode_id']) for x in eps]
 keys=[x[0] for x in starts];bins=Counter();metrics=Counter();coverage_sums=0.;minimum_c=None;maximum_c=None;phase_counts=Counter();peak=10000.;mindd=0.;min_eq=float('inf');last_ns=None;last_assets=None;lossbins=Counter();min_free=None;min_margin_ratio=None;rows=0;max_interpolation_residual=0.;joint=[];active_joint=None
 def finish_joint():
  nonlocal active_joint
  if active_joint:joint.append(active_joint);active_joint=None
 for row in csv.DictReader(gzip.open(path,'rt')):
  rows+=1;ns=int(row['close_available_ns']);phase=row['phase'];phase_counts[phase]+=1
  if ns>=1788220800000000000 and phase!='pre_quote_paired_close':continue
  eq=float(row['paired_close_equity']);peak=max(peak,eq);mindd=max(mindd,(peak-eq)/peak*100);min_eq=min(min_eq,eq)
  # One fully paired snapshot per minute; phase callbacks must not triple-count time.
  if phase!='post_quote_paired_close' or ns>=1788220800000000000:continue
  dt=(ns-last_ns)/1e9 if last_ns is not None else 60.;assert 0<dt<=60.;last_ns=ns
  positions=json.loads(row['native_positions_and_mark_ohlc_json']);assets={};notionals={};signs={}
  for p in positions:
   sym='BTC' if p['instrument_id'].startswith('BTC') else 'SOL';ohlc=p['mark_ohlc']
   if coverage_only:cl=D(ohlc['close']);assets[sym]=0.
   else:
    lo=native_round_price(ohlc['low'],sym);hi=native_round_price(ohlc['high'],sym);cl=native_round_price(ohlc['close'],sym);lp=D(p['low_native_pnl']);hp=D(p['high_native_pnl']);assets[sym]=float(lp if hi==lo else lp+(cl-lo)/(hi-lo)*(hp-lp))
   notionals[sym]=float(D(p['quantity'])*cl);signs[sym]=str(p['side'])
  residual=0. if coverage_only else abs((eq-float(row['cash']))-sum(assets.values()));max_interpolation_residual=max(max_interpolation_residual,residual)
  if 'BTC' in assets:
   metrics['btc_held_seconds']+=dt
   if 'SOL' in assets:metrics['btc_with_sol_seconds']+=dt
   i=bisect.bisect_right(keys,ns)-1;beta=starts[i][1] if i>=0 else None
   if beta and beta>0:
    c=notionals.get('SOL',0.)/notionals['BTC']*beta
    if 'SOL' in signs and signs['SOL']==signs['BTC']:c=-c
    bins[round(c*10000)/10000]+=dt;coverage_sums+=c*dt;minimum_c=c if minimum_c is None else min(minimum_c,c);maximum_c=c if maximum_c is None else max(maximum_c,c)
    if c<.5-1e-9:metrics['below050_seconds']+=dt
    if c<.45-1e-9:metrics['below045_seconds']+=dt
    if .45-1e-9<=c<=.55+1e-9:metrics['within045_055_seconds']+=dt
    if c<=1e-9:metrics['zero_coverage_seconds']+=dt
    if c>1+1e-9:metrics['above100_seconds']+=dt
   else:metrics['coverage_unknown_seconds']+=dt
   if assets['BTC']<0:
    metrics['btc_negative_unrealized_seconds']+=dt
    metrics['sol_helping_btc_negative_seconds' if assets.get('SOL',0)>0 else 'sol_not_helping_btc_negative_seconds']+=dt
    if assets.get('SOL',0)<0:
     metrics['joint_negative_unrealized_seconds']+=dt
     if active_joint is None:active_joint=dict(start_ns=ns,end_ns=ns,seconds=dt,min_btc_upnl=assets['BTC'],min_sol_upnl=assets['SOL'])
     else:active_joint.update(end_ns=ns,seconds=active_joint['seconds']+dt,min_btc_upnl=min(active_joint['min_btc_upnl'],assets['BTC']),min_sol_upnl=min(active_joint['min_sol_upnl'],assets['SOL']))
    else:finish_joint()
   else:finish_joint()
  else:finish_joint()
  free=float(row['free_cash']);min_free=free if min_free is None else min(min_free,free)
 finish_joint();held=metrics['btc_held_seconds'];total=sum(bins.values());cum=0;quantiles={}
 for val,secs in sorted(bins.items()):
  cum+=secs
  for q in (.05,.25,.5,.75,.95):
   if q not in quantiles and cum>=total*q:quantiles[q]=val
 writecsv('comparison-analysis-'+label+'-joint-loss-intervals.csv',joint)
 return dict(trace_path=str(path),trace_sha256=digest(path),rows=rows,phase_counts=dict(phase_counts),stream_all_native_close_dd_percent=mindd,stream_min_equity=min_eq,minimum_free_cash=min_free,coverage_basis=basis,coverage_time=dict(metrics),coverage_mean=coverage_sums/total if total else None,coverage_quantiles_rounded_0001=quantiles,coverage_min=minimum_c,coverage_max=maximum_c,btc_time_with_sol_fraction=metrics['btc_with_sol_seconds']/held if held else None,below050_fraction=metrics['below050_seconds']/held if held else None,below045_fraction=metrics['below045_seconds']/held if held else None,within045_055_fraction=metrics['within045_055_seconds']/held if held else None,zero_coverage_fraction=metrics['zero_coverage_seconds']/held if held else None,above100_fraction=metrics['above100_seconds']/held if held else None,maximum_asset_upnl_interpolation_residual=None if coverage_only else max_interpolation_residual,joint_loss_intervals=len(joint),asset_upnl_reconstruction_status='NOT_ATTEMPTED_COVERAGE_ONLY' if coverage_only else ('RECONCILED_LT_CENT' if max_interpolation_residual<.01 else 'NOT_FULLY_RECONCILED_UNALLOCATED_RESIDUAL'),coverage_mark_basis='ACTUAL_RECORDED_MARK_CLOSE_NO_PNL_RECONSTRUCTION' if coverage_only else 'NORMALIZED_MARK_DIAGNOSTIC',joint_loss_intervals_authoritative=False,coverage_does_not_require_upnl_reconstruction=True,limitations='Coverage snapshot postpairedquote, seconds held until nextminute approximated from precedingminute. Native roundedmark endpoint interpolation only diagnostics, not pertrade native settled PnL; negative uPnL cohorts are not realized loss events. No intraminute order path proof. Coverage basis is explicit.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--result',default=str(ARCHIVE));ap.add_argument('--label',default='v3');ap.add_argument('--trace');ap.add_argument('--coverage-only',action='store_true');a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);baseline=json.load(ARCHIVE.open());r,s,integrity=basic(Path(a.result),a.label,baseline)
 if a.trace:s.update(trace_streamed=True,trace=stream(Path(a.trace),r,a.label,a.coverage_only))
 # Reuse reviewed archive attribution without relabeling it native settled perasset cash.
 if Path(a.result)==ARCHIVE:
  old=json.load(open('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution.json'));s['confirmed_fill_asset_attribution_ex_funding']={k:dict(net=v['confirmed_fill_net_ex_funding'],method='Existing reviewed confirmed-native-fill attribution, NOT native settled perasset PnL') for k,v in old['episode_stats'].items()};s['unallocated_cash_residual_not_funding']=old['unallocated_native_cash_residual_not_funding']
 s['resource_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;s['comparison_method']='Compare actual native terminal values. No priceproxy savings added. Same-run netplannedQ conservation separate from crossrun compoundingQ differences.'
 writecsv('comparison-analysis-'+a.label+'-parents.csv',integrity);write('comparison-analysis-'+a.label+'.json',s);print(json.dumps({k:s[k] for k in ('label','terminal_total','parents','native_fees','global_marked_dd_percent','resource_peak_rss_kib')},default=str))
if __name__=='__main__':main()
