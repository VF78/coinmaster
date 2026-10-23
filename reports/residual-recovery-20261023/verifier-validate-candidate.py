"""Independent C1 saved-output audit. Reuses e4-budget-tp3 verifier-saved.py; no native imports/execution.
Prepared before candidate completion; no positive result implied.
"""
import csv, gzip, json, hashlib, ast, sqlite3
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

SEED=D(10000)
S0_TOTAL=D('6077107.23887483')
START=1725148800000000000
END=1788220800000000000
MINUTE=60000000000

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def iso(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()

def signature(value,drop=()):
    def clean(v):
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in drop}
        if isinstance(v,list):return [clean(x) for x in v]
        return v
    return hashlib.sha256(json.dumps(clean(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def readcsv(path):return list(csv.DictReader(Path(path).open()))

def funding_rows(path):
    # Frozen completed SQLite only; immutable mode prevents WAL/SHM writes.
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT * FROM funding_events ORDER BY ts_event,instrument_id,event_id')]

def native_fill_cashflows(rows):
    assets=[]
    for asset in sorted({r['instrument_id'].split('USDT')[0] for r in rows}):
        selected=[r for r in rows if r['instrument_id'].startswith(asset)]
        q=fees=gross=turnover=D(0)
        for r in selected:
            qty,px=D(r['filled_qty']),D(r['avg_px']);assert r['side'] in ('BUY','SELL')
            sign=1 if r['side']=='BUY' else -1
            q+=sign*qty;gross-=sign*qty*px;turnover+=qty*px
            for item in ast.literal_eval(r['commissions']):
                amount,currency=item.rsplit(' ',1);assert currency=='USDT';fees+=D(amount)
        assets.append(dict(asset=asset,filled_order_rows=len(selected),signed_terminal_quantity=q,gross_fill_cashflow=gross,native_fees=fees,confirmed_fill_net_ex_funding=gross-fees if q==0 else None,native_report_turnover=turnover,signed_funding='UNKNOWN'))
    return assets

def native_closed_cycles(rows):
    """Partition native aggregated filled-order rows by actual flat inventory."""
    cycles=[];streaks=[]
    for asset in sorted({r['instrument_id'].split('USDT')[0] for r in rows}):
        selected=[r for r in rows if r['instrument_id'].startswith(asset)]
        selected=sorted(enumerate(selected),key=lambda item:(item[1]['ts_last'],item[0]))
        position=D(0);current=[];number=0;losing=[]
        for _,row in selected:
            qty=D(row['filled_qty']);sign=1 if row['side']=='BUY' else -1
            if position!=0 and position*sign<0:assert qty<=abs(position),'Inventory crossed zero within one aggregated order'
            position+=sign*qty;current.append(row)
            if position==0:
                number+=1;a=native_fill_cashflows(current)[0];entryQ=sum((D(r['filled_qty']) for r in current if r['is_reduce_only']=='False'),D(0))
                cycle=dict(asset=asset,cycle=number,start=current[0]['ts_last'],end=current[-1]['ts_last'],entry_Q=entryQ,fill_order_rows=len(current),gross_fill_cashflow=a['gross_fill_cashflow'],native_fees=a['native_fees'],confirmed_fill_net_ex_funding=a['confirmed_fill_net_ex_funding'],signed_funding='UNKNOWN',basis='ACTUAL_ZERO_TO_ZERO_NATIVE_INVENTORY_NO_POLICY_COUNTERFACTUAL')
                cycles.append(cycle)
                if cycle['confirmed_fill_net_ex_funding']<0:losing.append(cycle)
                elif losing:
                    streaks.append(dict(asset=asset,start_cycle=losing[0]['cycle'],end_cycle=losing[-1]['cycle'],loss_count=len(losing),start=losing[0]['start'],end=losing[-1]['end'],sum_actual_closed_cycle_net_ex_funding=sum((r['confirmed_fill_net_ex_funding'] for r in losing),D(0)),next_nonlosing_cycle=number));losing=[]
                current=[]
        assert position==0 and not current
        if losing:streaks.append(dict(asset=asset,start_cycle=losing[0]['cycle'],end_cycle=losing[-1]['cycle'],loss_count=len(losing),start=losing[0]['start'],end=losing[-1]['end'],sum_actual_closed_cycle_net_ex_funding=sum((r['confirmed_fill_net_ex_funding'] for r in losing),D(0)),next_nonlosing_cycle=None))
    return cycles,streaks

def settled_stream(path,endpoint_targets=()):
    """Exactly one CSV/gzip traversal: global DD, months, >=30% excursions."""
    peak=SEED;peakts=START;best=D(0);bestrow=None;excursion=None;excursions=[]
    maximum=SEED;minimum=SEED;maximumts=minimumts=START
    months={};last=None;count=0;gaps=0;firstsource=None;lastsource=None;bad_time=0;lastreceipt=None
    peak_snapshot=dict(receipt_ns=START,source_quote_ns=START,equity=str(SEED),cash=str(SEED),native_positions_and_mark_ohlc_json='[]',basis='ORIGINAL_FLAT_SEED')
    endpoints={};remaining=set(endpoint_targets)
    uncompressed_hash=hashlib.sha256()
    protocol=json.loads((Path(__file__).parent/'protocol-freeze.json').read_text())
    windows={k:dict(start_ns=int(datetime.fromisoformat(a.replace('Z','+00:00')).timestamp())*10**9,end_exclusive_ns=int(datetime.fromisoformat(b.replace('Z','+00:00')).timestamp())*10**9,samples=0,local_peak=None,local_DD=D(0),global_DD=D(0)) for k,(a,b) in protocol['target_windows_UTC'].items()}
    def lines():
        with gzip.open(path,'rb') as f:
            for line in f:
                uncompressed_hash.update(line)
                yield line.decode('utf-8')
    for r in csv.DictReader(lines()):
        t=int(r['receipt_ns']);source=int(r['source_quote_ns']);equity=D(r['paired_close_equity'])
        snapshot=dict(receipt_ns=t,source_quote_ns=source,equity=str(equity),cash=r['cash'],native_positions_and_mark_ohlc_json=r['native_positions_and_mark_ohlc_json'])
        for target in sorted(remaining):
            if t>=target:
                endpoints[iso(target)]=dict(target_ns=target,prior_native_receipt=last if last is not None else peak_snapshot,first_native_receipt_at_or_after=snapshot)
        remaining={target for target in remaining if target>t}
        if firstsource is None:firstsource=source;gaps+=(source-(START+MINUTE))//MINUTE
        elif source>lastsource:gaps+=(source-lastsource)//MINUTE-1
        else:bad_time+=1
        if t<source or (lastreceipt is not None and t<lastreceipt):bad_time+=1
        lastsource=source;lastreceipt=t;count+=1
        if equity>maximum:maximum=equity;maximumts=t
        if equity<minimum:minimum=equity;minimumts=t
        if equity>=peak:
            if excursion is not None:
                excursion['recovery_utc']=iso(t);excursion['recovery_equity']=str(equity)
                excursion['recovery_native_snapshot']=snapshot
                if excursion['drawdown_fraction']>=D('.3'):excursions.append(excursion)
                excursion=None
            if equity>peak:peak=equity;peakts=t;peak_snapshot=snapshot
        else:
            dd=(peak-equity)/peak
            if excursion is None:excursion=dict(peak_utc=iso(peakts),peak_equity=str(peak),trough_utc=iso(t),trough_equity=str(equity),drawdown_fraction=dd,recovery_utc=None,recovery_equity=None,peak_native_snapshot=peak_snapshot,trough_native_snapshot=snapshot,recovery_native_snapshot=None)
            elif dd>excursion['drawdown_fraction']:excursion.update(trough_utc=iso(t),trough_equity=str(equity),drawdown_fraction=dd,trough_native_snapshot=snapshot)
            if dd>best:best=dd;bestrow=dict(peak_utc=iso(peakts),peak_equity=str(peak),trough_utc=iso(t),trough_equity=str(equity))
        for win in windows.values():
            if win['start_ns']<=t<win['end_exclusive_ns']:
                win['samples']+=1
                if win['local_peak'] is None or equity>win['local_peak']:win['local_peak']=equity;win['local_peak_utc']=iso(t)
                local_dd=(win['local_peak']-equity)/win['local_peak']
                if local_dd>win['local_DD']:
                    win['local_DD']=local_dd;win['local_endpoint']=dict(peak_utc=win['local_peak_utc'],peak_equity=str(win['local_peak']),trough_utc=iso(t),trough_equity=str(equity))
                global_dd=(peak-equity)/peak
                if global_dd>win['global_DD']:
                    win['global_DD']=global_dd;win['global_endpoint']=dict(peak_utc=iso(peakts),peak_equity=str(peak),trough_utc=iso(t),trough_equity=str(equity))
        month=iso(source)[:7]  # Source-quote UTC calendar; receipt has one-minute lag.
        if month not in months:
            first=SEED if last is None else D(last['equity'])
            months[month]=dict(month=month,start_equity=first,start_receipt_utc=iso(START) if month=='2024-09' else iso(t),end_equity=equity,end_receipt_utc=iso(t),samples=0,peak=first,local_DD_fraction=D(0))
        m=months[month];m['samples']+=1;m['end_equity']=equity;m['end_receipt_utc']=iso(t)
        if equity>m['peak']:m['peak']=equity
        m['local_DD_fraction']=max(m['local_DD_fraction'],(m['peak']-equity)/m['peak'])
        last=snapshot
    if excursion is not None and excursion['drawdown_fraction']>=D('.3'):excursions.append(excursion)
    gaps+=(END-MINUTE-lastsource)//MINUTE
    for m in months.values():m['return_percent']=(m['end_equity']/m['start_equity']-1)*100
    for e in excursions:
        if bestrow is not None and all(e[k]==bestrow[k] for k in ('peak_utc','trough_utc','peak_equity','trough_equity')):bestrow.update(recovery_utc=e['recovery_utc'],recovery_equity=e['recovery_equity'])
    for win in windows.values():
        win['local_window_rebased_DD_percent']=win.pop('local_DD')*100
        win['continuous_global_peak_DD_inside_window_percent']=win.pop('global_DD')*100
        win.pop('local_peak');win.pop('local_peak_utc')
    return dict(fixed_protocol_windows=windows,receipts=count,missing_source_minutes=gaps,invalid_timestamp_rows=bad_time,global_settled_DD_percent=best*100,global_peak_trough_recovery=bestrow,maximum_equity=str(maximum),maximum_equity_utc=iso(maximumts),minimum_equity=str(minimum),minimum_equity_utc=iso(minimumts),last_preterminal_observation=last,monthly=list(months.values()),excursions_ge_30percent=excursions,fixed_prior_A_C_D_boundary_snapshots=endpoints,trace_stream_passes=1,uncompressed_trace_sha256=uncompressed_hash.hexdigest())

def audit_saved(artifact_path,preparation,output_dir,recipe):
    """Caller must establish completion/hash freeze before calling this once."""
    path=Path(artifact_path);d=json.loads(path.read_text());rawpath=path.with_name(path.stem+'-raw-native.json');raw=json.loads(rawpath.read_text())
    out=Path(output_dir);checks={};files={str(path):digest(path),str(rawpath):digest(rawpath)}
    def check(name,value):checks[name]=bool(value)
    job=next(r for r in preparation['jobs'] if r['recipe']==recipe)
    check('expected_config_sha256',d['config_hash']==job['expected_config_sha256'])
    check('frozen_source_commit',job['source_commit']==preparation['source_commit']==json.loads((out/'protocol-freeze.json').read_text())['candidate_source_commit'])
    check('no_BTC_zero_risk_config',d['config']['next_band_research']['zero_retrace'] is False)
    check('exact_E4_base_wait4h',d['config']['next_band_research']['sol_dominant'] is False and d['config']['next_band_research']['wait_4h'] is True)
    check('config_payload_hash_recomputed',signature(d['config'])==d['config_hash'])
    check('original_B_data_hash',d['data_hash']=='7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc')
    check('original_B_execution_policy_hash',d['policy_hash']=='c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834')
    ownerreceipt=json.loads((out/('owner-'+recipe+'-receipt.json')).read_text())
    check('completed_frozen_artifact_hash',files[str(path)]==ownerreceipt['artifact_sha256'])
    check('completed_frozen_raw_hash',files[str(rawpath)]==ownerreceipt['raw_sha256'])
    check('terminal_active_plus_reserve',D(d['terminal_active'])+D(d['terminal_reserve'])==D(d['terminal_total']))
    check('raw_wrapper_TOTAL',raw['terminal_total']==d['terminal_total'])
    check('native_cash_tail_TOTAL',D(d['cash_account_series'][-1]['total'])==D(d['terminal_total']))
    check('terminal_positions_flat',d['terminal_open_positions']==0)
    check('native_terminal_orders_zero',raw['native_strategy_events']['terminal_open_orders']==0)
    check('terminal_lifecycle_flat',d['terminal_lifecycle']['status']=='FLAT')
    check('full_source_rows',d['streaming']['processed_rows_per_source']==1051200)
    exports={}
    for kind,meta in d['execution_artifacts'].items():
        rows=readcsv(meta['path']);files[meta['path']]=digest(meta['path']);exports[kind]=rows
        check(kind+'_hash',files[meta['path']]==meta['sha256']);check(kind+'_row_count',len(rows)==meta['rows'])
    assets=native_fill_cashflows(exports['fills'])
    cycles,streaks=native_closed_cycles(exports['fills'])
    check('fill_count_native_exact',len(exports['fills'])==d['fills']==len(d['fill_audit']))
    check('commissions_native_exact',sum((a['native_fees'] for a in assets),D(0))==D(d['native_fees']))
    check('fill_audit_commissions_exact',sum((D(r['commission']) for r in d['fill_audit']),D(0))==D(d['native_fees']))
    check('signed_asset_inventory_zero',all(a['signed_terminal_quantity']==0 for a in assets))
    check('closed_cycles_all_order_rows_partitioned',sum(r['fill_order_rows'] for r in cycles)==len(exports['fills']))
    check('closed_cycle_cashflows_reconcile',all(sum((r['confirmed_fill_net_ex_funding'] for r in cycles if r['asset']==a['asset']),D(0))==a['confirmed_fill_net_ex_funding'] for a in assets))
    check('native_orders_no_open',all(r['status'] in ('FILLED','CANCELED','REJECTED','DENIED','EXPIRED') for r in exports['orders']))
    ri=d['minute_risk_observations']['settled_native_close_receipts'];trace=Path(ri['trace_path'])
    cachepath=out/('verifier-'+recipe+'-risk-cache.json');trace_digest=digest(trace);files[str(trace)]=trace_digest
    if cachepath.exists():
        cached=json.loads(cachepath.read_text(),parse_float=D)
        if cached['compressed_trace_sha256']!=trace_digest:raise ValueError('Frozen trace changed after risk pass')
        risk=cached['risk']
        for key in ['global_settled_DD_percent']:risk[key]=D(risk[key])
    else:
        controls=json.loads((out/'verifier-control-windows.json').read_text()) if (out/'verifier-control-windows.json').exists() else {'E4_all_seven_excursion_endpoint_histories':[]}
        targets={int(datetime.fromisoformat(e[k]).timestamp())*10**9 for e in controls['E4_all_seven_excursion_endpoint_histories'] for k in ['peak_utc','trough_utc','recovery_utc'] if e[k] is not None}
        risk=settled_stream(trace,targets)
        cachepath.write_text(json.dumps(dict(compressed_trace_sha256=trace_digest,risk=risk),indent=2,default=str)+'\n')
    check('receipt_count_native_exact',risk['receipts']==ri['receipts']==1051199)
    check('full_24_source_calendar_months',len(risk['monthly'])==24 and risk['monthly'][0]['month']=='2024-09' and risk['monthly'][-1]['month']=='2026-08')
    check('receipt_source_first_last',risk['last_preterminal_observation']['source_quote_ns']==END-MINUTE and risk['last_preterminal_observation']['receipt_ns']==END)
    check('source_gaps_count_native_exact',risk['missing_source_minutes']==ri['unavailable_intervening_native_mutation'])
    check('complete_receipt_accounting',risk['receipts']+ri['unavailable_intervening_native_mutation']==1051199)
    check('no_invalid_timestamp_rows',risk['invalid_timestamp_rows']==0)
    expected=D(ri['curve']['top3_distinct_excursions'][0]['drawdown_peak_percent'])
    check('global_settled_DD_exact',risk['global_settled_DD_percent']==expected)
    total=D(d['terminal_total']);net=sum((a['confirmed_fill_net_ex_funding'] for a in assets),D(0));retention=(total-SEED)/(S0_TOTAL-SEED)*100
    sourcecheck={}
    for name,want in preparation.get('source_sha256',preparation.get('source_pins')).items():
        actual=digest(Path(preparation['source_snapshot'])/name);sourcecheck[name]=actual==want
    check('all_frozen_source_files',all(sourcecheck.values()))
    source_names={'hedge_band':'runtime/coinmaster/strategy/hedge_band.py','native_baseline':'runtime/coinmaster/research/native_baseline.py','split_cover':'runtime/coinmaster/strategy/split_cover.py','wave_domain':'runtime/coinmaster/domain/wave_overlay.py','wave_strategy':'runtime/coinmaster/strategy/wave_overlay.py','next_band':'runtime/coinmaster/strategy/next_band.py'}
    for key,want in d['source_hashes'].items():
        if key not in source_names:
            matches=[name for name,value in preparation.get('source_sha256',preparation.get('source_pins')).items() if value==want]
            if len(matches)!=1:raise ValueError('Unmapped native source key: '+key)
            source_names[key]=matches[0]
        check('native_result_source_'+key,want==preparation.get('source_sha256',preparation.get('source_pins'))[source_names[key]])
    inputs={}
    for name,want in job['input_pins'].items():
        inputpath=(Path(preparation['source_snapshot']) if name.startswith('runtime/') else Path(job['data_root']))/name
        actual=digest(inputpath);inputs[name]=dict(path=str(inputpath),expected=want,actual=actual,match=actual==want)
    check('all_actual_input_pins',all(a['match'] for a in inputs.values()))
    settlement=d['post_boundary_settlement'];boundaryfees=sum((D(r['commission']) for r in d['fill_audit'] if int(r['fill_ns'])>=END),D(0))
    funding=funding_rows(d['funding_journal']);files[d['funding_journal']]=digest(d['funding_journal'])
    check('native_funding_row_count',len(funding)==d['funding']['count'])
    result=dict(recipe=recipe,status='NATIVE_ACCOUNTING_PASS_PENDING_MECHANISMS' if all(checks.values()) else 'FAIL',checks=checks,failed_checks=[k for k,v in checks.items() if not v],TOTAL=total,retention_percent=retention,fees=d['native_fees'],fills=d['fills'],BTC_fills=sum(r['instrument_id'].startswith('BTC') for r in exports['fills']),SOL_fills=sum(r['instrument_id'].startswith('SOL') for r in exports['fills']),native_fill_audit_turnover=sum((D(r['notional']) for r in d['fill_audit']),D(0)),assets=assets,unallocated_cash_bridge=total-SEED-net,signed_asset_funding='UNKNOWN',liquidations=d['liquidation_count'],risk=risk,terminal=dict(**settlement,last_preterminal_native_equity=risk['last_preterminal_observation']['equity'],observed_equity_to_TOTAL_bridge=total-D(risk['last_preterminal_observation']['equity']),actual_boundary_fees=boundaryfees),config_hash=d['config_hash'],data_hash=d['data_hash'],policy_hash=d['policy_hash'],source_commit=job['source_commit'],source_files=sourcecheck,input_pins=inputs,artifact_sha256=files,signature_fill_audit=signature(d['fill_audit']),signature_native_fills=signature(exports['fills'],drop=('init_id',)),signature_native_orders=signature(exports['orders'],drop=('init_id',)),signature_native_cash=signature(d['cash_account_series']),signature_funding=signature(funding),no_new_engine=True)
    result['closed_cycle_count']=dict((a['asset'],sum(r['asset']==a['asset'] for r in cycles)) for a in assets)
    result['maximum_loss_streak']=dict((a['asset'],max((r['loss_count'] for r in streaks if r['asset']==a['asset']),default=0)) for a in assets)
    result['loss_streak_basis']='Consecutive negative actual closed-cycle fill net ex funding; zero/nonnegative cycle ends streak. No marked equity or funding allocation.'
    result['native_money_pass_50_90']=total>=D('5470396.514987347') and risk['global_settled_DD_percent']<=50 and d['liquidation_count']==0 and ri['unavailable_intervening_native_mutation']==0 and all(checks.values())
    (out/('verifier-'+recipe+'-audit.json')).write_text(json.dumps(result,indent=2,default=str)+'\n')
    for name,rows in [('monthly',risk['monthly']),('DD-ge30-episodes',risk['excursions_ge_30percent']),('asset-fill-net',assets),('closed-cycle-ledger',cycles),('loss-streaks',streaks)]:
        if not rows:continue
        with (out/('verifier-'+recipe+'-'+name+'.csv')).open('w') as f:
            w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows({k:json.dumps(v,sort_keys=True,default=str) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
    return result

def audit_witness(path,contract,native):
    """Explicit C1 records only; never reconstruct missing decision state.

    Contract belongs to frozen policy and must be independently reviewed. This
    generic preparation validates evidence completeness and native fill binding;
    final action/state semantics are gated until schema-specific validation exists.
    """
    rows=readcsv(path) if Path(path).suffix=='.csv' else [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    missing=[];checks={};required=contract['required_fields'];seqfield=contract['sequence_field'];timefield=contract['timestamp_field']
    sequences=[];timestamps=[]
    for i,row in enumerate(rows):
        absent=[k for k in required if k not in row or row[k] is None or row[k]=='']
        if absent:missing.append({'row':i,'missing':absent});continue
        sequences.append(int(row[seqfield]));timestamps.append(int(row[timefield]))
    checks['required_fields_present']=not missing
    checks['sequences_strictly_increase']=all(a<b for a,b in zip(sequences,sequences[1:]))
    checks['timestamps_nondecreasing']=all(a<=b for a,b in zip(timestamps,timestamps[1:]))
    checks['nonempty_witness']=bool(rows)
    checks['witness_hash_frozen']=digest(path)==contract['witness_sha256']
    # No fabricated provisional semantics: an unknown/new witness cannot pass.
    return {'status':'NOT_PROVEN_SCHEMA_SPECIFIC_C1_RULES_PENDING','checks':checks,'missing_fields':missing,'rows':len(rows),'witness_sha256':digest(path),'mechanism_acceptance':False,'reason':'Generic schema checks are insufficient for causal credit/attempt/right/ordinarypriority proof. Freeze and implement reviewed schema-specific checks before native acceptance.'}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path)
    parser.add_argument('--preparation',type=Path)
    parser.add_argument('--recipe',default='C1')
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--witness',type=Path)
    parser.add_argument('--witness-contract',type=Path)
    parser.add_argument('--completed-freeze',type=Path,help='Root-approved completed candidate manifest: recipe, artifact_sha256, raw_sha256, trace_sha256, status=COMPLETE_VALID_NATIVE')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.prepare_only:
        print(json.dumps({'status':'PREPARED_NOT_RUN','trace_scans':0,'engines':0,'requires':['Root completion notification before invocation','completed-freeze manifest','owner receipt','source/input/config preparation','protocol candidate_source_commit + target_windows_UTC','frozen enriched embedded C1 witness schema'],'reused_helpers':'reports/e4-budget-tp3-20261023/verifier-saved.py','mechanism_checker':'ENRICHED_EMBEDDED_C1_SCHEMA_PREPARED_NOT_RUN'},indent=2));return
    for key in ['artifact','preparation','completed_freeze']:
        if getattr(args,key) is None:parser.error('--'+key.replace('_','-')+' is required outside --prepare-only')
    freeze=json.loads(args.completed_freeze.read_text());artifact=json.loads(args.artifact.read_text());rawpath=args.artifact.with_name(args.artifact.stem+'-raw-native.json');trace=Path(artifact['minute_risk_observations']['settled_native_close_receipts']['trace_path'])
    assert freeze['status']=='COMPLETE_VALID_NATIVE' and freeze['recipe']==args.recipe,'No accepted completed candidate freeze'
    assert digest(args.artifact)==freeze['artifact_sha256'] and digest(rawpath)==freeze['raw_sha256'] and digest(trace)==freeze['trace_sha256'],'Completed output hash mismatch'
    preparation=json.loads(args.preparation.read_text())
    # Only this point can open the complete candidate trace through audit_saved.
    native=audit_saved(args.artifact,preparation,args.output_dir,args.recipe)
    fee_groups={}
    for row in artifact['fill_audit']:
        key=row['native_liquidity_side'];g=fee_groups.setdefault(key,{'count':0,'fees':D(0),'notional':D(0)})
        g['count']+=1;g['fees']+=D(row['commission']);g['notional']+=D(row['notional'])
    fee_checks={'maker_taker_only':set(fee_groups)<= {'MAKER','TAKER'},'native_fee_group_sum':sum((g['fees'] for g in fee_groups.values()),D(0))==D(artifact['native_fees'])}
    native['maker_taker_native_liquidity_costs']=fee_groups;native['maker_taker_checks']=fee_checks
    import runpy
    c1checker=runpy.run_path(str(Path(__file__).with_name('verifier-c1-witness.py')))['validate_c1']
    witness=c1checker(artifact,readcsv(artifact['execution_artifacts']['fills']['path']))
    if args.witness and args.witness_contract:
        witness['external_schema_check']=audit_witness(args.witness,json.loads(args.witness_contract.read_text()),native)
    if 'H' in artifact.get('c1_terminal_state',{}):
        witness['terminal_global_H_matches_saved_risk']=D(artifact['c1_terminal_state']['H'])==D(native['risk']['maximum_equity'])
        if not witness['terminal_global_H_matches_saved_risk']:
            witness['failed_checks'].append({'check':'terminal_global_H_matches_saved_risk','sequence':None});witness['status']='FAIL';witness['mechanism_acceptance']=False
    native['C1_witness']=witness
    native['status']='PASS' if native['status']=='NATIVE_ACCOUNTING_PASS_PENDING_MECHANISMS' and all(fee_checks.values()) and witness['mechanism_acceptance'] else 'NOT_ACCEPTED'
    native['pass_50_90']=native['native_money_pass_50_90'] and native['status']=='PASS'
    (args.output_dir/('verifier-'+args.recipe+'-audit.json')).write_text(json.dumps(native,indent=2,default=str)+'\n')
    print(json.dumps({'recipe':args.recipe,'status':native['status'],'TOTAL':str(native['TOTAL']),'global_DD':str(native['risk']['global_settled_DD_percent']),'native_money_pass_50_90':native['native_money_pass_50_90'],'C1_witness':witness['status'],'pass_50_90':native['pass_50_90']},indent=2))
    if native['status']!='PASS':raise SystemExit(2)

if __name__=='__main__':main()
