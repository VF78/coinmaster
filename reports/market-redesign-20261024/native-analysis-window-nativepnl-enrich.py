#!/usr/bin/env python3
"""Observed native cash/UPNL decomposition, not independent price-PNL proof."""
import argparse,collections,csv,gzip,hashlib,json
from pathlib import Path
from decimal import Decimal as D,localcontext
OUT=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readcsv(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows):
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));w.writeheader();w.writerows(rows)
def run(variant):
 analysispath=OUT/f'native-analysis-{variant}.json';analysis=read(analysispath);assert analysis['row']['status']=='VALIDATED_FULL_NATIVE'
 artifact=next(Path(k) for k in analysis['input_sha256'] if k.endswith('.json') and '/result/' in k and not k.endswith('-raw-native.json'));x=read(artifact);rawpath=artifact.with_name(artifact.stem+'-raw-native.json');raw=read(rawpath)
 receiptpath=OUT/f'root-{variant}-execution-receipt.json';execution=read(receiptpath);assert D(str(execution['external_cash_flows_USDT']))==0
 inputs=[analysispath,artifact,rawpath,receiptpath,OUT/f'native-analysis-attribution-{variant}-windows.csv',OUT/f'native-analysis-attribution-{variant}-DDge30.csv'];hashes={str(p):sha(p) for p in inputs}
 original=readcsv(inputs[-2])+readcsv(inputs[-1]);assert len(original)==29
 assert D(x['terminal_reserve'])==0 and x['config']['research_sol_off'] is True
 audit=raw['fill_audit'];assert all(a['instrument'].startswith('BTC') for a in audit) and all(not r[1].startswith('SOL') for r in raw['funding']['signed_native_cash_deltas'])
 parents=x['split_cover_audit']['parents'];starts={int(p['start_ns']) for p in parents};assert sum(a['action']=='BTC_ENTRY' and int(a['fill_ns']) in starts for a in audit)==len(parents)
 assert x['config']['btc_close_stop_fraction'] is None and not any('SL' in a['reason'] or 'STOP_LOSS' in a['reason'] for a in audit)
 required={(r[f'actual_{s}_source_quote_ns'],r[f'actual_{s}_receipt_ns'],r[f'{s}_fill_epoch']) for r in original for s in ['start','end']}
 # Seed and terminal use actual native accepted run facts, not invented trace rows.
 first=next(r for r in original if r['window']=='FULL_PERIOD');seedkey=(first['actual_start_source_quote_ns'],first['actual_start_receipt_ns'],first['start_fill_epoch']);endkey=(first['actual_end_source_quote_ns'],first['actual_end_receipt_ns'],first['end_fill_epoch'])
 seed=D(x['run_interval']['initial_active_seed']);total=D(x['terminal_total']);snap={seedkey:{'cash':seed,'eq':seed,'basis':'ACTUAL_INITIAL_NATIVE_SEED'},endkey:{'cash':total,'eq':total,'basis':'ACTUAL_TERMINAL_NATIVE_FLAT_CASH'}}
 trace=Path(x['minute_risk_observations']['settled_native_close_receipts']['trace_path']);assert sha(trace)==analysis['input_sha256'][str(trace)];hashes[str(trace)]=sha(trace);tracecount=0
 with gzip.open(trace,'rt') as f:
  for row in csv.DictReader(f):
   tracecount+=1;k=(row['source_quote_ns'],row['receipt_ns'],row['fill_epoch'])
   if k in required and k not in [seedkey,endkey]:
    assert k not in snap;snap[k]={'cash':D(row['cash']),'eq':D(row['paired_close_equity']),'basis':'ACTUAL_NATIVE_SETTLED_RECEIPT_CASH_AND_EQUITY'}
 assert tracecount==1051199 and required<=set(snap),'Missing exact native endpoint; do not substitute nearest quote'
 enriched=[];identitychecks=0;unknown=0
 names=['BTC_FIRST_ENTRY','BTC_SECOND_ENTRY','BTC_TP1','BTC_TP2','BTC_TP3','BTC_REGIME','BTC_TRAIL','BTC_TERMINAL','BTC_OTHER_EXIT']
 for originalrow in original:
  r=dict(originalrow);a=snap[(r['actual_start_source_quote_ns'],r['actual_start_receipt_ns'],r['start_fill_epoch'])];b=snap[(r['actual_end_source_quote_ns'],r['actual_end_receipt_ns'],r['end_fill_epoch'])]
  assert a['eq']==D(r['start_marked_TOTAL']) and b['eq']==D(r['end_marked_TOTAL'])
  dc=b['cash']-a['cash'];ua=a['eq']-a['cash'];ub=b['eq']-b['cash'];du=ub-ua;de=b['eq']-a['eq'];assert de==dc+du==D(r['marked_TOTAL_change']);identitychecks+=1
  i=int(r['start_fill_epoch']);j=int(r['end_fill_epoch']);fs=audit[i:j];fees=sum((D(a['commission']) for a in fs),D(0));assert fees==D(r['BTCUSDT-PERP.P1SIM_native_fees'])
  funding=D(r['BTCUSDT-PERP.P1SIM_signed_funding']);known=not json.loads(r['endpoint_funding_exact_timestamp_ties']);realized=dc+fees-funding if known else None
  if realized is None:unknown+=1
  else:assert de==realized+du-fees+funding
  counts=collections.Counter();quant=collections.defaultdict(lambda:D(0))
  for f in fs:
   if f['action']=='BTC_ENTRY':name='BTC_FIRST_ENTRY' if int(f['fill_ns']) in starts else 'BTC_SECOND_ENTRY'
   elif f['reason'] in ['BTC_TP1','BTC_TP2','BTC_TP3']:name=f['reason']
   elif f['reason'] in ['REGIME','TRAIL']:name='BTC_'+f['reason']
   elif f['action']=='TERMINAL_CLOSE' or f['reason']=='TERMINAL_BOUNDARY_SETTLEMENT':name='BTC_TERMINAL'
   else:name='BTC_OTHER_EXIT'
   counts[name]+=1;quant[name]+=D(f['qty'])
  assert sum(counts.values())==len(fs)
  r.update(native_pnl_basis='OBSERVED_NATIVE_CASH_EQUITY_DECOMPOSITION_NOT_INDEPENDENT_PRICE_PNL_PROOF',native_start_endpoint_basis=a['basis'],native_end_endpoint_basis=b['basis'],native_start_cash=str(a['cash']),native_end_cash=str(b['cash']),native_cash_change=str(dc),native_start_UPNL=str(ua),native_end_UPNL=str(ub),native_UPNL_change=str(du),native_cash_plus_UPNL_change_exact=str(dc+du),native_equity_decomposition_identity='EXACT',native_realized_PRICE_PNL=str(realized) if realized is not None else 'UNKNOWN_ENDPOINT_FUNDING_TIMESTAMP_ORDER',native_realized_PRICE_PNL_basis='OBSERVED_DELTA_CASH_PLUS_FEES_MINUS_KNOWN_SIGNED_FUNDING_EXTERNAL0' if known else 'UNKNOWN_NATIVE_FUNDING_ORDER_AT_ENDPOINT',native_external_flows_actual='0',native_BTC_fees_actual=str(fees),native_BTC_signed_funding=str(funding),native_funding_inclusion_qualification='KNOWN_FROM_ORIGINAL_STRICT_LT_ACTUAL_ENDPOINT_CONVENTION' if known else 'UNKNOWN_EXACT_ENDPOINT_ORDER_ORIGINAL_STRICT_LT_VALUE_RETAINED',SOL_price_PNL_actual='0',SOL_fees_actual='0',SOL_signed_funding_actual='0',SOL_zero_basis='ACTUAL_GLOBAL_NO_SOL_NATIVE_FILLS_OR_FUNDING_SEE_ACCEPTED_SOL_OFF_RUN',actual_executed_fill_events=len(fs),actual_price_SL_events=0,actual_price_SL_basis='CONFIG_PRICE_STOP_DISABLED_AND_NO_NATIVE_SL_FILL_EVENTS')
  for name in names:r[name+'_actual_fill_count']=counts[name];r[name+'_actual_filled_qty']=str(quant[name])
  r['observed_economic_note']=('BTC marked loss' if de<0 else 'BTC marked gain' if de>0 else 'BTC marked unchanged')+'; native cash delta '+str(dc)+'; actual native UPNL delta '+str(du)+'; executed fees '+str(fees)+'; '+('realized-price component '+str(realized)+' with separately recorded signed funding '+str(funding) if known else 'realized-price split UNKNOWN due endpoint funding timestamp order')+'; SOL inactive. Observations only, no counterfactual causal profit decomposition.'
  assert all(r[k]==v for k,v in originalrow.items()),'Original attribution fields must remain byte-value unchanged in enrichment'
  enriched.append(r)
 for p in inputs:assert sha(p)==hashes[str(p)],'Stable existing input modified'
 out=OUT/f'native-analysis-window-nativepnl-{variant}.csv';writecsv(out,enriched)
 return {'variant':variant,'output':str(out),'rows':len(enriched),'required_unique_endpoints':len(required),'native_endpoint_lookup_complete':True,'streamed_trace_rows':tracecount,'equity_delta_cash_delta_plus_UPNL_delta_exact_checks':identitychecks,'realized_PRICE_PNL_known_rows':len(enriched)-unknown,'realized_PRICE_PNL_UNKNOWN_endpoint_tie_rows':unknown,'all_original_window_fields_unchanged':True,'stable_input_hashes_unchanged':hashes,'observed_no_SOL':True,'engine_launches':0}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=['R1','R2','R3','all'],default='all');args=p.parse_args()
 with localcontext() as ctx:
  ctx.prec=60;results=[run(v) for v in (['R1','R2','R3'] if args.variant=='all' else [args.variant])]
 meta={'status':'PASS_OBSERVED_NATIVE_WINDOW_DECOMPOSITION_ONLY','variants':results,'qualification':'Realized PRICE PNL derived from observed nativecash when signedfunding orderingknown; NOT independent price-PNL proof. Original independent fill/rawmark residual and funding timing statuses retained unchanged.','engine_launches':0}
 (OUT/'native-analysis-window-nativepnl-verification.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps([{k:v[k] for k in ['variant','rows','required_unique_endpoints','realized_PRICE_PNL_known_rows','realized_PRICE_PNL_UNKNOWN_endpoint_tie_rows','equity_delta_cash_delta_plus_UPNL_delta_exact_checks']} for v in results],indent=2))
