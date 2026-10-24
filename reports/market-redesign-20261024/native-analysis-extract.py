#!/usr/bin/env python3
"""Read saved native exports; no engine imports, order generation, or process launches."""
import argparse,ast,collections,csv,gzip,hashlib,json,sqlite3
from decimal import Decimal as D,localcontext
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
MIN=60_000_000_000;SEED=D('10000');LEGACY=D('6077107.23887483');FLOOR=D('5470396.514987347');UNK='UNKNOWN'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def date(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
def month(t):return date(t)[:7]
def rows(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def fees(row):
 v=ast.literal_eval(row['commissions']);return sum((D(s.split()[0]) for s in v),D(0)) if all(s.split()[1]=='USDT' for s in v) else None
class Curve:
 def __init__(self,seed,t):self.peak=seed;self.dd=D(0);self.peak_t=t;self.trough_t=t;self.dd_peak_t=t;self.samples=1;self.last=seed
 def add(self,v,t):
  self.samples+=1;self.last=v
  if v>self.peak:self.peak=v;self.peak_t=t
  dd=(self.peak-v)/self.peak*100 if self.peak>0 else D(0)
  if dd>self.dd:self.dd=dd;self.trough_t=t;self.dd_peak_t=self.peak_t
 def result(self):return {'DD_percent':str(self.dd),'peak_ns':self.dd_peak_t,'trough_ns':self.trough_t,'samples':self.samples,'terminal':str(self.last)}
def extract(args):
 artifact=Path(args.artifact).resolve();x=read(artifact)
 rawpath=Path(args.raw).resolve() if args.raw else artifact.with_name(artifact.stem+'-raw-native.json');raw=read(rawpath)
 commands=read(OUT/'owner-commands.json');expected=read(args.expected_config or OUT/f'owner-{args.variant}-expected-config.json');source=read(OUT/'owner-source-receipt.json');e4=read(OUT.parent/'b-50-90-next-20261023/owner-E4-receipt.json')
 execution=read(args.execution_receipt) if args.execution_receipt else {}
 checks={};details={};inputs={str(artifact):sha(artifact),str(rawpath):sha(rawpath)}
 def check(name,value,detail=None):
  checks[name]='PASS' if value is True else 'FAIL' if value is False else 'UNKNOWN'
  if detail is not None:details[name]=detail
 check('raw_financial_metadata_equal',all(x.get(k)==raw.get(k) for k in ['config_hash','data_hash','code_hash','policy_hash','terminal_active','terminal_reserve','terminal_total','native_fees','funding','liquidation_count','terminal_open_positions']))
 check('config_hash_self_consistent',canonical(x['config'])==x['config_hash']);check('expected_full_config_exact',x['config']==expected and x['config_hash']==commands[args.variant]['expected_config_canonical_sha256'])
 check('data_pin',x['data_hash']==e4['data_sha256']);check('policy_pin',x['policy_hash']==e4['policy_sha256']);check('execution_process_exit0',execution.get('native_process_exit_code')==0 if 'native_process_exit_code' in execution else None)
 check('execution_source_commit',execution.get('source_commit')==commands[args.variant]['source_commit']==source['source_commit'] if 'source_commit' in execution else None)
 check('execution_artifact_sha',execution.get('artifact_sha256')==sha(artifact) if 'artifact_sha256' in execution else None)
 mapping={'next_band':'runtime/coinmaster/strategy/next_band.py','hedge_band':'runtime/coinmaster/strategy/hedge_band.py','funding_fixture':'runtime/coinmaster/research/native_fixture.py','market_redesign':'runtime/coinmaster/strategy/market_redesign.py','native_baseline':'runtime/coinmaster/research/native_baseline.py','native_journal':'runtime/coinmaster/ledger/journal.py','split_cover':'runtime/coinmaster/strategy/split_cover.py','wave_domain':'runtime/coinmaster/domain/wave_overlay.py','wave_strategy':'runtime/coinmaster/strategy/wave_overlay.py'}
 matched={}
 for k,v in mapping.items():
  frozen=Path(source['frozen_mac_source'])/v
  expected_hash=source['file_sha256'].get(v) or (sha(frozen) if frozen.exists() else None)
  matched[k]=expected_hash is not None and x.get('source_hashes',{}).get(k)==expected_hash
  if frozen.exists():inputs[str(frozen)]=sha(frozen)
 check('frozen_source_hashes',all(matched.values()) and x['code_hash']==source['file_sha256']['runtime/coinmaster/research/native_baseline.py'],matched)
 total=D(x['terminal_total']);active=D(x['terminal_active']);reserve=D(x['terminal_reserve']);start=ns(x['run_interval']['start']);end=ns(x['run_interval']['end_exclusive']);seed=D(x['run_interval']['initial_active_seed'])
 check('terminal_total_components',total==active+reserve);check('terminal_flat_metadata',x.get('terminal_open_positions')==0 and x.get('terminal_lifecycle',{}).get('status')=='FLAT');check('terminal_orders_zero',raw.get('native_strategy_events',{}).get('terminal_open_orders')==0 if 'terminal_open_orders' in raw.get('native_strategy_events',{}) else None)
 check('zero_model_liquidations',x.get('liquidation_count')==0 and not x.get('liquidation_audit') and not x.get('early_liquidation_cutoff'))
 audit=raw.get('fill_audit',[]);events=raw.get('native_order_events',{});art=x['execution_artifacts'];fills=rows(art['fills']['path']);orders=rows(art['orders']['path'])
 for name,data in [('fills',fills),('orders',orders)]:
  p=Path(art[name]['path']);inputs[str(p)]=sha(p);check(name+'_export_hash_rows',sha(p)==art[name]['sha256'] and len(data)==art[name]['rows'])
 check('order_ids_unique',len({r['client_order_id'] for r in orders})==len(orders));check('filled_export_ids_unique',len({r['client_order_id'] for r in fills})==len(fills))
 orderby={r['client_order_id']:r for r in orders};check('filled_export_matches_native_orders',all(r['client_order_id'] in orderby and all(r.get(k)==orderby[r['client_order_id']].get(k) for k in ['filled_qty','avg_px','side','commissions','status']) for r in fills))
 ag=collections.defaultdict(list);og=collections.defaultdict(list)
 def akey(r):return (str(r['submit_ns']),r['instrument'],str(r.get('reason','')),str(r.get('level','')))
 for a in audit:ag[akey(a)].append(a)
 missing_event=[]
 for o in fills:
  event=events.get(o['client_order_id'])
  if not event:missing_event.append(o['client_order_id']);continue
  og[akey(event)].append(o)
 cash=collections.defaultdict(lambda:D(0));assetfees=collections.defaultdict(lambda:D(0));inventory=collections.defaultdict(lambda:D(0));turnover=collections.defaultdict(lambda:D(0));monthly=collections.defaultdict(lambda:collections.defaultdict(lambda:D(0)));ambiguous=[]
 for key,alist in ag.items():
  ol=og.get(key,[]);sides={o['side'] for o in ol}
  if len(sides)!=1:ambiguous.append(key);continue
  sign=D(1) if next(iter(sides))=='BUY' else D(-1);sym=key[1];aq=sum((D(a['qty']) for a in alist),D(0));oq=sum((D(o['filled_qty']) for o in ol),D(0))
  if aq!=oq:ambiguous.append(key);continue
  for a in alist:
   n=D(a['qty'])*D(a['px']);fee=D(a['commission']);cash[sym]-=sign*n;inventory[sym]+=sign*D(a['qty']);assetfees[sym]+=fee;turnover[sym]+=n
   mo=monthly[month(a['fill_ns'])];mo['fill_cashflow_ex_fees']-=sign*n;mo['fees']+=fee
 check('audit_side_quantity_groups',not missing_event and not ambiguous and set(ag)==set(og),{'missing_order_events':missing_event,'ambiguous_groups':ambiguous})
 check('audit_USDT_commission',all(a['commission_currency']=='USDT' for a in audit));check('native_terminal_inventory_from_actual_fills',all(q==0 for q in inventory.values()) if checks['audit_side_quantity_groups']=='PASS' else None,{k:str(v) for k,v in inventory.items()})
 # Audit uses exact actual per-fill px/qty. Aggregate native avg_px is never tick-rounded.
 nativecash=collections.defaultdict(lambda:D(0));nativefees=D(0);qtyvalid=True
 for o in fills:
  if o['side'] not in ['BUY','SELL']:qtyvalid=False;continue
  nativecash[o['instrument_id']]-=(D(1) if o['side']=='BUY' else D(-1))*D(o['filled_qty'])*D(o['avg_px'])
  f=fees(o)
  if f is None:qtyvalid=False
  else:nativefees+=f
 tolerance=max(D('.000001'),D('.00000001')*(len(audit)+1))
 check('native_aggregate_pricecash_matches_actual_audit',qtyvalid and all(abs(nativecash[k]-v)<=tolerance for k,v in cash.items()) if checks['audit_side_quantity_groups']=='PASS' else None,{'tolerance_USDT':str(tolerance),'native_vs_audit_differences':{k:str(nativecash[k]-v) for k,v in cash.items()}})
 auditfees=sum(assetfees.values(),D(0));check('fees_three_way',abs(nativefees-auditfees)<=tolerance and abs(auditfees-D(x['native_fees']))<=tolerance)
 funding=x.get('funding',{});deltas=funding.get('signed_native_cash_deltas');fundasset=collections.defaultdict(lambda:D(0));fundsum=None
 if isinstance(deltas,list):
  valid=all(isinstance(r,list) and len(r)==6 and D(r[4])-D(r[3])==D(r[5]) for r in deltas)
  check('signed_funding_row5_schema',valid)
  if valid:
   for r in deltas:fundasset[r[1]]+=D(r[5]);monthly[month(r[2])]['funding']+=D(r[5])
   fundsum=sum(fundasset.values(),D(0));check('funding_raw_total_count',len(deltas)==funding['count'] and fundsum==D(funding['signed_amount']))
 else:check('signed_funding_row5_schema',None)
 journal=Path(x['funding_journal']) if x.get('funding_journal') else None
 if journal and journal.exists() and not (Path(str(journal)+'-wal').exists() and Path(str(journal)+'-wal').stat().st_size):
  try:
   inputs[str(journal)]=sha(journal);conn=sqlite3.connect(journal.as_uri()+'?mode=ro&immutable=1',uri=True)
   persisted=conn.execute('SELECT event_id,instrument_id,ts_event,before_total,after_total,signed_delta FROM funding_cash ORDER BY ts_event,event_id').fetchall();eventrows=conn.execute('SELECT event_id,instrument_id,ts_event FROM funding_events').fetchall();conn.close()
   check('funding_journal_cash_matches_raw',collections.Counter(tuple(r) for r in deltas)==collections.Counter(persisted) if deltas is not None else None)
   check('funding_journal_event_count_ids',len(eventrows)==funding['count'] and {(r[0],r[1],r[2]) for r in persisted}==set(eventrows))
   check('funding_journal_interval',all(start<=r[2]<=end for r in persisted))
  except (sqlite3.Error,ValueError) as exc:check('funding_journal_cash_matches_raw',None,str(exc))
 else:check('funding_journal_cash_matches_raw',None,'Missing journal or active/nonemptyWAL; no journal mutation/copy/checkpoint attempted')
 fresh=execution.get('fresh_funding_journal_verified')
 if fresh is None and 'artifact_dir_existed_before_launch' in execution and 'journal_files_before_launch' in execution:fresh=execution['artifact_dir_existed_before_launch'] is False and execution['journal_files_before_launch']==[]
 check('fresh_funding_journal_prelaunch_evidence',fresh if isinstance(fresh,bool) else None)
 check('native_engine_version',execution.get('native_version')=='1.231.0' if 'native_version' in execution else None)
 check('root_mechanical_acceptance',execution.get('mechanical_acceptance_pass') if isinstance(execution.get('mechanical_acceptance_pass'),bool) else None)
 check('root_source_review',execution.get('source_review_pass') if isinstance(execution.get('source_review_pass'),bool) else None)
 no_external=execution.get('external_cash_flows_USDT');check('external_cash_flow_evidence',True if no_external is not None else None)
 independent=None
 if checks['audit_side_quantity_groups']=='PASS' and checks['native_terminal_inventory_from_actual_fills']=='PASS' and fundsum is not None and checks.get('funding_journal_cash_matches_raw')=='PASS' and no_external is not None:
  independent=seed+sum(cash.values(),D(0))-auditfees+fundsum+D(str(no_external));check('independent_cash_identity',abs(independent-total)<=tolerance,{'computed_terminal':str(independent),'observed_terminal':str(total),'difference':str(independent-total),'tolerance_USDT':str(tolerance)})
 else:check('independent_cash_identity',None,'Need actual signedflatfillcash,auditfees,persisted signedfunding and explicit externalflowevidence; no bridge used')
 risk=x.get('minute_risk_observations',{});receipt=risk.get('settled_native_close_receipts',{});trace=Path(receipt['trace_path']) if receipt.get('trace_path') else None
 account=Curve(seed,start);totcurve=Curve(seed,start);count=0;continuous=True;last=None;grosssum=D(0);netsum=D(0);grossmax=D(0);exposure_unknown=0;monthlast={};reserve_zero=reserve==0 and D(str(x['config'].get('reserve_transfer_fraction','NaN')))==0 and all(D(r['reserve'])==0 for r in x.get('cash_account_series',[]))
 totaltraceknown=reserve_zero
 if trace and trace.exists():
  inputs[str(trace)]=sha(trace)
  with gzip.open(trace,'rt') as f:
   for r in csv.DictReader(f):
    t=int(r['source_quote_ns']);rt=int(r['receipt_ns']);count+=1
    if t!=start+count*MIN or rt<t or (last is not None and t-last!=MIN):continuous=False
    last=t;eq=D(r['paired_close_equity']);account.add(eq,rt)
    if reserve_zero:teq=eq
    elif 'reserve' in r:teq=eq+D(r['reserve']);totaltraceknown=True
    else:teq=None;totaltraceknown=False
    if teq is not None:totcurve.add(teq,rt);monthlast[month(t)]=(t,teq)
    gross=D(0);net=D(0)
    for p in json.loads(r['native_positions_and_mark_ohlc_json']):
     side=str(p['side']);sgn=D(1) if side in ['2','LONG'] else D(-1) if side in ['3','SHORT'] else None
     if sgn is None:exposure_unknown+=1;continue
     notional=D(p['quantity'])*D(p['mark_ohlc']['close']);gross+=abs(notional);net+=sgn*abs(notional)
    grosssum+=gross;netsum+=net;grossmax=max(grossmax,gross)
  account.add(active,end);totcurve.add(total,end)
  expected=(end-start)//MIN-1
  check('settled_trace_interval_complete',continuous and count==expected and last==end-MIN and count==receipt.get('receipts') and receipt.get('unavailable_intervening_native_mutation')==0,{'actual_rows':count,'expected_from_interval':expected,'full_required':1051199,'first_source_expected':start+MIN,'last_source':last})
 else:check('settled_trace_interval_complete',None)
 full_interval=start==ns('2024-09-01T00:00:00+00:00') and end==ns('2026-09-01T00:00:00+00:00') and seed==SEED
 check('full_frozen_interval',full_interval and count==1051199)
 check('TOTAL_marked_curve_available',totaltraceknown and trace is not None and trace.exists())
 full_mode=not args.diagnostic;full_ok=full_mode and all(v=='PASS' for v in checks.values());dd=totcurve.dd if totaltraceknown and count else None
 economics=total>=FLOOR and dd is not None and dd<=50 and x.get('liquidation_count')==0
 md=raw.get('market_redesign_audit',{});me=md.get('events',[]);real_u=x['config'].get('research_btc_real_u',False)
 tpio=[o for o in orders if events.get(o['client_order_id'],{}).get('reason','').startswith('BTC_TP') and o['type']!='LIMIT']
 protection_closed=md.get('open_protection_exception_since_ns') is None if real_u else None
 if real_u:
  check('realU_missing_protection_duration_closed',protection_closed);check('realU_no_positive_TP_IOC_orders',not tpio)
  full_ok=full_mode and all(v=='PASS' for v in checks.values())
 pnlrows=[]
 for sym in sorted(set(cash)|set(fundasset)):
  pnlrows.append({'instrument':sym,'actual_fill_price_cashflow_flat_PNL':str(cash[sym]),'native_fees':str(assetfees[sym]),'fill_net_ex_funding':str(cash[sym]-assetfees[sym]),'signed_funding':str(fundasset[sym]) if fundsum is not None else UNK,'native_turnover':str(turnover[sym])})
 statuses=collections.Counter(o['status'] for o in orders)
 check('native_orders_all_terminal',all(o['status'] in ['FILLED','CANCELED','REJECTED','DENIED','EXPIRED'] for o in orders))
 parents=x.get('split_cover_audit',{}).get('parents',[])
 check('native_parents_terminal',all(p.get('closed') is True for p in parents))
 full_ok=full_mode and all(v=='PASS' for v in checks.values())
 partials=sum(D(o['filled_qty'])>0 and D(o['filled_qty'])<D(o['quantity']) for o in orders)
 row={'variant':args.variant,'status':'SHORT_DIAGNOSTIC_NOT_FULL_ACCEPTANCE' if args.diagnostic else 'VALIDATED_FULL_NATIVE' if full_ok else 'FULL_VALIDATION_BLOCKED','TOTAL':str(total),'ACTIVE':str(active),'RESERVE':str(reserve),'net_profit':str(total-SEED) if full_interval else 'SHORT_NOT_COMPARABLE','legacy_net_profit_retention_percent':str((total-SEED)/(LEGACY-SEED)*100) if full_interval else 'SHORT_NOT_COMPARABLE','immutable_legacy_floor':str(FLOOR),'global_TOTAL_settled_DD_percent':str(dd) if dd is not None else UNK,'native_ACCOUNT_settled_DD_percent':str(account.dd) if count else UNK,'receipts':count,'native_fees':str(auditfees),'signed_funding':str(fundsum) if fundsum is not None else UNK,'independent_terminal_cash':str(independent) if independent is not None else UNK,'filled_order_rows':len(fills),'actual_fill_audit_events':len(audit),'native_turnover':str(sum(turnover.values(),D(0))),'mean_gross_exposure_USDT':str(grosssum/count) if count and not exposure_unknown else UNK,'max_gross_exposure_USDT':str(grossmax) if count and not exposure_unknown else UNK,'mean_signed_net_exposure_USDT':str(netsum/count) if count and not exposure_unknown else UNK,'missing_three_TP_ns':md.get('missing_three_tp_ns',UNK) if real_u else 'LEGACY_CONTROL_NOT_REAL3TP','open_protection_exception_since_ns':md.get('open_protection_exception_since_ns') if real_u else 'NOT_APPLICABLE','order_rejections':x.get('native_order_rejections',UNK),'native_partial_terminal_orders':partials,'canceled_orders':statuses.get('CANCELED',0),'model_liquidations':x.get('liquidation_count',UNK),'candidate_parents':len(x.get('split_cover_audit',{}).get('parents',[])),'legacy_positive_TP_IOC_rawflag':x['config'].get('research_btc_split_tp_ioc'),'effective_positive_TP_IOC':False if real_u else x['config'].get('research_btc_split_tp_ioc'),'observed_nonlimit_positive_TP_orders':len(tpio),'fill_qualification':'SYNTHETIC_MINUTE_CLOSE_NATIVE_FILL_CLASSIFICATION_L2_INTRAMINUTE_CRASHRESUME_UNPROVEN','mechanical_and_cash_acceptance':full_ok,'numerical_50_90_only':economics if full_interval else 'SHORT_NOT_COMPARABLE','qualified_50_90_pass':bool(full_ok and economics),'realized_unrealized_report_field':x.get('realized_unrealized',UNK)}
 for a in pnlrows:
  for key in ['actual_fill_price_cashflow_flat_PNL','native_fees','fill_net_ex_funding','signed_funding']:row[a['instrument'].split('USDT')[0]+'_'+key]=a[key]
 report={'row':row,'checks':checks,'details':details,'asset_accounting':pnlrows,'account_marked_curve':account.result() if count else UNK,'TOTAL_marked_curve':totcurve.result() if count and totaltraceknown else UNK,'source_commit_expected':commands[args.variant]['source_commit'],'input_sha256':inputs,'funding_journal':str(journal),'no_bridge_or_simulated_fill':True,'limitations':['Saved exports only; no engine/process/order launched.','Short data are cold lifecycle diagnostics, not full candidate economics.','Native model liquidation0 is not historical venue proof. L2/slippage/queue/intraminute/crash-resume UNKNOWN.','Missing independent cash/execution/fresh-journal evidence stays UNKNOWN and blocks full acceptance.','Funding row5 signed delta checked against persisted actual journal; no unallocated cash bridge.','Multi-fill aggregate nativeVWAP is never rounded to a single tick; exact per-fill auditprices and native order side determine price cashflow.','Monthly native cashflow is not monthly realizedPnL when inventory spans months.','Protection duration is native observer evidence; historical3ACK/race correctness requires separate lifecycle acceptance.']}
 prefix=OUT/args.output_prefix
 if not args.output_prefix.startswith('native-analysis-') or Path(args.output_prefix).name!=args.output_prefix:raise ValueError('Output prefix must be local native-analysis-*')
 Path(str(prefix)+'.json').write_text(json.dumps(report,indent=2)+'\n')
 with Path(str(prefix)+'.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
 if monthlast:
  prev=seed;mr=[]
  for mo,(t,v) in sorted(monthlast.items()):
   if mo==sorted(monthlast)[-1]:v=total
   mr.append({'month':mo,'marked_open_total':str(prev),'marked_close_total':str(v),'marked_change':str(v-prev),'marked_return_percent':str((v/prev-1)*100),'native_fill_cashflow_ex_fees':str(monthly[mo]['fill_cashflow_ex_fees']),'native_fees':str(monthly[mo]['fees']),'signed_funding':str(monthly[mo]['funding']) if fundsum is not None else UNK});prev=v
  with Path(str(prefix)+'-months.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(mr[0]));w.writeheader();w.writerows(mr)
 print(json.dumps({'output':str(prefix)+'.json','status':row['status'],'checks':dict(collections.Counter(checks.values())),'not_PASS':{k:v for k,v in checks.items() if v!='PASS'},'independent_cash':checks['independent_cash_identity'],'qualified_50_90_pass':row['qualified_50_90_pass']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact',required=True);p.add_argument('--raw');p.add_argument('--variant',choices=['R1','R2','R3'],required=True);p.add_argument('--execution-receipt');p.add_argument('--expected-config');p.add_argument('--output-prefix',required=True);p.add_argument('--diagnostic',action='store_true');args=p.parse_args()
 with localcontext() as ctx:ctx.prec=60;extract(args)
