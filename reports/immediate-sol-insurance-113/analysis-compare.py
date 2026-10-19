"""One compact completed-result audit. No engine, strategy replay, PnL ledger or trace decoding."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
from bisect import bisect_right
from datetime import datetime,timezone
import csv,json,hashlib,statistics as st,math,time,resource,importlib.util,gc
import pyarrow as pa,pyarrow.parquet as pq
P=Path('reports/immediate-sol-insurance-113');T=time.time();assert not (P/'analysis-summary.json').exists();assert int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))>=700*1024

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,indent=2,default=str,ensure_ascii=False,allow_nan=False)+'\n')
def csvout(n,rows):
 with (P/n).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def utc(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
def ns(t):
 try:return int(t)
 except ValueError:return int(datetime.fromisoformat(t).timestamp()*1e9)
def sym(f):return 'BTC' if f.get('instrument',f.get('instrument_id','')).startswith('BTC') else 'SOL'
def quant(vals):
 a=sorted(float(v) for v in vals)
 if not a:return {'n':0}
 def pct(p):i=(len(a)-1)*p;j=int(i);return a[j]+(a[min(j+1,len(a)-1)]-a[j])*(i-j)
 return {'n':len(a),'min':a[0],'p05':pct(.05),'median':pct(.5),'p95':pct(.95),'max':a[-1]}
sp=importlib.util.spec_from_file_location('prior_compact','reports/sol-risk-first-20261018/analyze-comparison.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
aggpath=P/'launch-and-completion-receipts.json';assert sha(aggpath)=='f29ae17453b79b7bc38a94c3084897ee50a16ab474bc98fd982d5154ba156aa4';agg=json.loads(aggpath.read_text());assert agg['research_slice_empty'] and len(agg['runs'])==4
prov=json.loads(Path('reports/sol-risk-first-20261018/analysis-control-provenance.json').read_text());controlpath=Path(prov['control']['result']);assert sha(controlpath)==prov['control']['result_sha256'];control=json.loads(controlpath.read_text())
# One small daily-price logical read solely verifies exported W90 estimator. Not a strategy simulation.
daily={};dailyhash={}
for s in ['BTC','SOL']:
 p=Path('runtime/var/data/normalized')/('bybit-'+s+'USDT-daily.parquet');b=p.read_bytes();dailyhash[str(p)]=hashlib.sha256(b).hexdigest();daily[s]=[(int(z['open_time_ms']+86400000)*10**6,float(z['close'])) for z in pq.read_table(pa.BufferReader(b),columns=['open_time_ms','close']).to_pylist()]
def estimate(t):
 a={s:[p for n,p in v if n<=t][-91:] for s,v in daily.items()};assert all(len(z)==91 for z in a.values());z={s:[math.log(y/x) for x,y in zip(v,v[1:])] for s,v in a.items()};sb=st.stdev(z['BTC']);ss=st.stdev(z['SOL']);return sb/ss,sb,max(n for n,p in daily['BTC'] if n<=t)

# Existing confirmed-fill diagnostic expressed as signed native execution cashflows only.
# Flat complete asset interval: sum(SELL notional - BUY notional) - known commissions.
# NOT native account settled/component PnL; no second cash account or hypothetical fills.
def execution_diagnostic(r):
 orders=list(csv.DictReader(open(r['execution_artifacts']['orders']['path'])));side_map=defaultdict(set)
 for a in orders:side_map[sym(a),ns(a['ts_init'])].add(a['side'])
 parents=sorted(r['split_cover_audit']['parents'],key=lambda a:int(a['start_ns']));starts=[int(p['start_ns']) for p in parents];per=[{'number':i+1,'episode_id':p['episode_id'],'start_ns':int(p['start_ns']),'start_utc':utc(p['start_ns']),'side':p['side'],'Q':p['quantity'],'BTC_gross':D(0),'BTC_fees':D(0),'SOL_gross':D(0),'SOL_fees':D(0),'BTC_end_qty':D(0),'SOL_end_qty':D(0),'SOL_add_fills':0,'SOL_reduce_fills':0} for i,p in enumerate(parents)];tot={s:dict(gross=D(0),fees=D(0),net=D(0),end_signed_qty=D(0),events=0) for s in ['BTC','SOL']};ev=defaultdict(list);solsidebad=[];firstsol={};auditcount=Counter()
 for f in r['fill_audit']:
  s=sym(f);sides=side_map[s,int(f['submit_ns'])];assert len(sides)==1,(s,f['submit_ns'],sides);sign=1 if next(iter(sides))=='BUY' else -1;q=D(f['qty']);px=D(f['px']);fee=D(f['commission']);t=int(f['fill_ns']);i=bisect_right(starts,t)-1;assert i>=0;a=per[i];flow=-sign*q*px;tot[s]['gross']+=flow;tot[s]['fees']+=fee;tot[s]['events']+=1;tot[s]['end_signed_qty']+=sign*q;a[s+'_gross']+=flow;a[s+'_fees']+=fee;a[s+'_end_qty']+=sign*q;ev[t].append((s,sign*q));auditcount[s+'_'+f['action']]+=1
  if s=='SOL':
   a['SOL_add_fills' if f['action']=='SOL_ADD' else 'SOL_reduce_fills']+=1
   if f['action']=='SOL_ADD':
    firstsol.setdefault(a['episode_id'],t)
    if sign!=-int(parents[i]['side']):solsidebad.append({'timestamp_ns':t,'native_side':next(iter(sides)),'BTCside':parents[i]['side']})
 for a in tot.values():a['net']=a['gross']-a['fees'];assert a['end_signed_qty']==0
 assert sum(a['fees'] for a in tot.values())==D(r['native_fees'])
 for a in per:
  a['BTC_net']=a['BTC_gross']-a['BTC_fees'];a['SOL_net']=a['SOL_gross']-a['SOL_fees'];a['both_asset_intervals_native_flat']=a['BTC_end_qty']==a['SOL_end_qty']==0
 # Fill-held time is exact quantity presence between actual callbacks, not notional protection.
 qty={'BTC':D(0),'SOL':D(0)};held=over=same=0;last=None
 for t,fs in sorted(ev.items()):
  if last is not None and qty['BTC']:
   dt=t-last;held+=dt
   if qty['SOL']:
    over+=dt
    if qty['SOL']*qty['BTC']>0:same+=dt
  for s,q in fs:qty[s]+=q
  last=t
 return {'assets':tot,'cash_residual_unallocated_NOT_funding':D(r['terminal_total'])-10000-sum(a['net'] for a in tot.values()),'native_SOL_ADD_wrong_side_vs_currentBTC':solsidebad,'actual_action_counts':dict(auditcount),'fill_held_overlap':{'BTC_held_seconds':held/1e9,'BTC_with_SOL_seconds':over/1e9,'fraction':over/held if held else None,'same_direction_BTC_SOL_held_seconds':same/1e9},'method':'Signednativeorder.sidejoinedbyasset+submit_ns UNIQUE toindividualcallbackfills; sumexecutedSELLnotional−BUYnotional−fees. Completeflatintervalsonly;weightedfill/cashflowDIAGNOSTIC,NOTnativeaccountsettledassetPnL. Residualnotassignedfunding/counterfactual.','native_order_side_join_ambiguous':0},per,firstsol

allmetrics={};comparison=[];permissions=[];epcsv=[];pinmap={str(aggpath):sha(aggpath)};coverage_rows=[];schema_limits=['Per-addarm/per-harvestreversebartimestampsNOTexported:causalityforfullconfirmationhistorycertifiedfrozenbranch/nativefixtures,notindependenthistoricalreplay.','TARGET_LATCHactualcoverageisevent-sampled/priorpendingexecution,NOTcontinuoushardcap/timeweightednotionalcoverage. Fill-heldoverlapmeasuresonlynonzerooppositepositionpresence.','I33one-thirdDecimalcanflooroneSOLlotbelowexactmathematical100%atboundary;declaredfrozennativerounding,notrepair.','Original6077includesprofitableindependentSOLoverlay;insurancevariantsreplaceit. DollarPnLdifferencesnotpureprice/fees/hedgeeffectduetoequitycompounding.','SignedfundingUNKNOWN;confirmedfillcashflowdiagnosticnotnativeaccountcomponentPnL.']

def case(v,r,receipt=None):
 m=old.metrics(r);dg,per,firstsol=execution_diagnostic(r);pr,ps=old.permissions(control,r);books=dg['assets'];audit=r.get('immediate_sol_insurance_audit',[]);cycles=r.get('immediate_sol_insurance_cycles',[]);counts=Counter(a['event'] for a in audit);tele={}
 if receipt:
  assert len(cycles)==105 and all(c['closed'] and int(c['returns'])==90 for c in cycles);assert r['config']['candidate']['sol_overlay_enabled'] is False
  cm={c['episode_id']:c for c in cycles};pm={p['episode_id']:p for p in r['split_cover_audit']['parents']};firsts=[a for a in audit if a['event']=='FIRST_BTC_FILL'];assert len(firsts)==105
  coeff=[];clockbad=[];latches=[];originalbad=[];rearm=0;oldfrac={};had_harvest=set();first_target={};new_sol_delays=[]
  for a in firsts:
   t=int(a['timestamp_ns']);c=cm[a['episode_id']];k,sigma,est=estimate(t);assert a['coefficient_valid'] is True and int(a['returns'])==90 and int(a['estimate_close_ns'])==est and int(c['first_fill_ns'])==t
   dk=abs(float(a['k'])-k);ds=abs(float(a['sigma'])-sigma);assert dk<1e-12 and ds<1e-12;assert str(a['k'])==str(c['k']) and str(a['sigma'])==str(c['sigma']);coeff.append({'episode_id':a['episode_id'],'first_fill_ns':t,'estimate_close_ns':est,'returns':90,'k':a['k'],'sigma':a['sigma'],'abs_k_recompute_error':dk,'abs_sigma_error':ds});new_sol_delays.append((firstsol[a['episode_id']]-t)/1e9 if a['episode_id'] in firstsol else None)
  fractions=Counter();stages=Counter();native_original=0;recovery_addwhile=0;active_recovery={}
  for a in audit:
   eid=a['episode_id'];c=cm[eid];t=int(a['timestamp_ns'])
   if 'k' in a:assert D(a['k'])==D(c['k']) and D(a['sigma'])==D(c['sigma'])
   for f in ['bar_close_ns','confirmation_received_ns']:
    if a.get(f) is not None and int(a[f])>t:clockbad.append({'event':a['event'],'field':f,'timestamp_ns':t,'future':a[f]})
   if a['event']=='TARGET_LATCH':
    first_target.setdefault(eid,t);b=D(a['btc_remaining']);solmark=D(a['sol_mark']);bm=D(a['btc_mark']);k=D(a['k']);fraction=max(D(a['fraction']),D(a['recovery_fraction']));raw=b*bm*k*fraction/solmark;target=D(a['target_qty']);assert target<=raw+D('.000000001') and raw-target<=D('.100000001'),('TARGET_FORMULA',v,target,raw)
    fractions[str(a['fraction'])]+=1;actual=D(a['actual_SOL']);f=actual*solmark/(b*bm*k) if b*bm*k else None
    latches.append({'variant':v,'episode_id':eid,'timestamp_ns':t,'actual_BTC':str(b),'actual_SOL':str(actual),'target_SOL':str(target),'k':str(k),'sigma':str(c['sigma']),'fraction':a['fraction'],'recovery_fraction':a['recovery_fraction'],'actual_event_volrisk_fraction':str(f) if f is not None else None,'pending_or_missing_target_qty':str(target-actual)})
   if a['event']=='HARVEST_OR_RECOVERY':had_harvest.add(eid)
   if a['event']=='ADVERSE_STAGE':
    stages[str(a['fraction'])]+=1
    if eid in had_harvest and D(a['fraction'])>oldfrac.get(eid,D(0)):rearm+=1
   if a['event']=='NATIVE_FILL':
    if D(a.get('original_native_quantity','0')):native_original+=1
    if a.get('action')=='SOL_ADD' and active_recovery.get(eid,D(0))>0:recovery_addwhile+=1
   if 'fraction' in a:oldfrac[eid]=D(a['fraction'])
   if 'recovery_fraction' in a:active_recovery[eid]=D(a['recovery_fraction'])
  assert not clockbad and native_original==0 and len(first_target)==105;assert not dg['native_SOL_ADD_wrong_side_vs_currentBTC'];assert all(a['both_asset_intervals_native_flat'] for a in per)
  for a in firsts:assert first_target[a['episode_id']]==int(a['timestamp_ns'])
  tele={'actual_events':dict(counts),'coefficient_recomputed_valid':len(coeff),'coefficient_checks':coeff,'coefficient_missing':0,'coefficient_or_cycle_freeze_violations':0,'firstfill_to_first_target_seconds_all_zero':True,'first_SOL_fill_delay_seconds':quant([x for x in new_sol_delays if x is not None]),'episodes_with_no_actual_SOL_add':sum(x is None for x in new_sol_delays),'native_original_SOL_allocations':native_original,'native_insurance_cycles_closed':len(cycles),'TARGET_formula_and_lotfloor_pass':len(latches),'TARGET_fraction_counts':dict(fractions),'ADVERSE_STAGE_fraction_counts':dict(stages),'rearm_authority_increases_after_prior_harvest':rearm,'rearm_definition':'ADVERSE_STAGEfractionincreaseafterearlierHARVESTauthorityinepisode,notunexportedseparatearmtimestamp','actual_event_volrisk_fraction':quant([D(a['actual_event_volrisk_fraction']) for a in latches if a['actual_event_volrisk_fraction'] is not None]),'event_target_shortfall_rows':sum(D(a['pending_or_missing_target_qty'])>0 for a in latches),'event_target_excess_rows':sum(D(a['pending_or_missing_target_qty'])<0 for a in latches),'Light_latched_cycles':sum(c['light'] for c in cycles),'Recovery_authorization_used_cycles':sum(c['recovery_used'] for c in cycles),'actual_SOL_add_fills_while_recovery_authority_positive':recovery_addwhile,'clock_future_fields':clockbad,'explicit_NativeAddDenied_events':counts.get('NATIVE_ADD_DENIED',0),'scope':'ConfiguredbranchcountsnotPnLbenefit. AuditcountHARVEST!=physicalreducecount!=profitableclosedcashcycle.'};coverage_rows.extend(latches)
  for p in pm.values():assert D(p['filled'])+D(p['cancelled'])==D(p['quantity'])
  for a in pr:permissions.append({'variant':v,**a})
 for a in per:epcsv.append({'variant':v,**a})
 wins=[p for p in per if p['BTC_net']>0];los=[p for p in per if p['BTC_net']<0];paired={'BTC_diagnostic_winning_episodes':len(wins),'BTC_diagnostic_losing_episodes':len(los),'SOL_net_on_BTC_winning':sum(p['SOL_net'] for p in wins),'SOL_net_on_BTC_losing':sum(p['SOL_net'] for p in los),'SOL_negative_on_BTC_winning_count':sum(p['SOL_net']<0 for p in wins),'SOL_positive_on_BTC_losing_count':sum(p['SOL_net']>0 for p in los),'BTC_and_SOL_joint_loss_count':sum(p['SOL_net']<0 for p in los),'complete_native_flat_asset_intervals':sum(p['both_asset_intervals_native_flat'] for p in per)}
 status='ACCEPTED_COMPARISON_WITH_DECLARED_NATIVE_EXECUTION_EFFECTS_AND_TELEMETRY_LIMITS' if receipt else 'REUSED_SHA_VERIFIED_PORTFOLIO_CONTROL';row=old.table_row(v,status,m,ps);row.update(delta_TOTAL_vs_control=D(m['TOTAL'])-D(control['terminal_total']),BTC_actual_fees=books['BTC']['fees'],SOL_actual_fees=books['SOL']['fees'],BTC_fill_cashflow_gross_diagnostic=books['BTC']['gross'],SOL_fill_cashflow_gross_diagnostic=books['SOL']['gross'],BTC_fill_cashflow_net_ex_funding_diagnostic=books['BTC']['net'],SOL_fill_cashflow_net_ex_funding_diagnostic=books['SOL']['net'],unallocated_cash_residual_NOT_funding=dg['cash_residual_unallocated_NOT_funding'],actual_fill_held_overlap=dg['fill_held_overlap']['fraction'],q0_exact=ps['q0_ns_exact'],q1_exact=ps['q1_ns_exact'],P0_exact=ps['first_vwap_exact'],side_exact=ps['side_exact'],execution_delay_count=len(ps['execution_delay_rows']),planned_BTC_lots=sum(D(p['quantity'])/D(p['step']) for p in r['split_cover_audit']['parents']),filled_BTC_lots=sum(D(p['filled'])/D(p['step']) for p in r['split_cover_audit']['parents']),cancelled_BTC_lots=sum(D(p['cancelled'])/D(p['step']) for p in r['split_cover_audit']['parents']))
 comparison.append(row);allmetrics[v]={'acceptance':status,'metrics':m,'BTC_permissions':ps,'actual_confirmed_fill_cashflow_diagnostic':dg,'paired_episode_diagnostic':paired,'insurance':tele,'config':r['config'],'source_result':receipt['artifact'] if receipt else str(controlpath),'result_sha256':receipt['artifact_sha256'] if receipt else prov['control']['result_sha256']}
 print('ANALYZED',v,json.dumps({'TOTAL':m['TOTAL'],'DD':m['global_marked_DD_percent'],'assets':books,'paired':paired,'permissions':ps,'events':dict(counts),'overlap':dg['fill_held_overlap']},default=str),flush=True)

case('control6077',control)
for v in ['i25','i25-light','i25-recovery','i33']:
 rp=P/('implementation-'+v+'-receipt.json');q=json.loads(rp.read_text());pinmap[str(rp)]=sha(rp);assert q['source_commit']=='f878cd401e3ac7482e3919324c11ddaa312b3196' and q['frozen_files_verified']==88 and q['frozen_manifest_sha256']=='d0a0f03acf92af83969bbfce657a09aea76bfcdb573e222d0c843d339cfc38fb';assert sha(q['artifact'])==q['artifact_sha256'];r=json.loads(Path(q['artifact']).read_text());assert r['policy_hash']==control['policy_hash'] and r['data_hash']==control['data_hash'];assert q['terminal_open_positions']==r['terminal_open_positions']==0;assert q['split_qty_conserved'];assert q['variant']['dp']=='OFF';assert q['compressed_native_observer']['rows']==3153600;assert Path(q['compressed_native_observer']['path']).stat().st_size==q['compressed_native_observer']['bytes']
 for p,h in q['funding_journal_files'].items():assert Path(q['job']) in Path(p).parents and sha(p)==h
 audit=r['immediate_sol_insurance_audit'];assert q['immediate_sol_insurance_audit']['sha256']==hashlib.sha256(json.dumps(audit,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 case(v,r,q);del r,q,audit;gc.collect()
assert len(comparison)==5;eligible=[a['variant'] for a in comparison[1:] if D(a['global_native_marked_DD_percent'])<=50];assert not eligible
csvout('analysis-comparison.csv',comparison);csvout('analysis-BTC-permissions.csv',permissions);csvout('analysis-episode-fill-diagnostic.csv',epcsv);csvout('analysis-event-coverage.csv',coverage_rows)
summary={'status':'FINAL_FOUR_NATIVE_RESULTS_ACCEPTED_WITH_DECLARED_EXECUTION_EFFECTS_NO_ELIGIBLE_WINNER','ranking':'NO_ELIGIBLE_WINNER','criterion':'MaximumTOTAL amongvalidfourvariantswithDecimalglobalnative1mDD<=50;nonequalifies,controlDD66.3188alsonoteligible. No furtherengine/control/repeat.','variants':allmetrics,'comparison':comparison,'limitations':schema_limits,'proofs':{'aggregate':str(aggpath),'aggregate_sha256':sha(aggpath),'receipt_SHA':pinmap,'daily_SHA':dailyhash,'source_commit':'f878cd401e3ac7482e3919324c11ddaa312b3196','frozen_files':88,'manifest_sha256':'d0a0f03acf92af83969bbfce657a09aea76bfcdb573e222d0c843d339cfc38fb','root_independent_checkpoint':'reports/immediate-sol-insurance-113/root-four-completion-checkpoint.json','compressed_observer_SHA':'Enginecollector+rootverified;statscheckedfilebytes/compactcounts,NODECODEDtracepass.','observer_decoded_read_passes':0},'resources':{'elapsed_seconds':round(time.time()-T,3),'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},'trading_conclusion':'PENDING_REVIEW_OF_COMPUTED_NUMBERS_BEFORE_HUMAN_FINAL_REPORT'}
save('analysis-summary.json',summary);print('FINAL_COMPUTED',sha(P/'analysis-summary.json'),flush=True)
