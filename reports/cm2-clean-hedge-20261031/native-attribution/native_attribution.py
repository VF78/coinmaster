"""Streaming native cash/UPNL attribution, not a matcher or counterfactual engine."""
import argparse,csv,gzip,hashlib,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D,getcontext
from pathlib import Path

getcontext().prec=60
SEED=D(10000);TOL=D('0.00000001');STEP=6*3600*1_000_000_000
START=1725148800000000000;END=1788220800000000000
ASSETS={'BTC-USD-PERP.HYPERLIQUID':'BTC','SOL-USD-PERP.HYPERLIQUID':'SOL'}
POSTS={'POST_FILL_COMMITTED_NATIVE','POST_FUNDING_ACCOUNT_NATIVE'}
WM='SETTLED_PRE_NEXT_SOURCE_WATERMARK'


def num(value):
    value=D(str(value))
    if not value.is_finite():raise ValueError('NONFINITE_NATIVE_VALUE')
    return value


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def instrument(value):
    if value not in ASSETS:raise ValueError('FOREIGN_OR_UNKNOWN_ASSET')
    return ASSETS[value]


def position_values(row):
    if not isinstance(row['positions'],list):raise ValueError('NATIVE_POSITIONS_MISSING')
    upnl={'BTC':D(0),'SOL':D(0)};sides={}
    for p in row['positions']:
        asset=instrument(p['instrument_id'])
        if asset in sides or num(p['quantity'])<=0 or p['side'] not in ('LONG','SHORT'):
            raise ValueError('DUPLICATE_OR_INVALID_NATIVE_POSITION')
        upnl[asset]=num(p['native_upnl']);sides[asset]=p['side']
    cash,equity=num(row['cash']),num(row['equity'])
    if abs(cash+sum(upnl.values())-equity)>TOL:raise ValueError('NATIVE_CASH_UPNL_EQUITY_MISMATCH')
    if not isinstance(row.get('native_positions_sha256'),str) or len(row['native_positions_sha256'])!=64:
        raise ValueError('NATIVE_POSITION_STATE_HASH_MISSING')
    return upnl,sides,cash,equity


def report_maps(report,errors):
    fills=report.get('fill_audit',report.get('actual_native_fill_audit'))
    funding=report.get('funding_cash_audit')
    if not isinstance(fills,list):errors.add('REPORT_FILL_AUDIT_MISSING');fills=[]
    if not isinstance(funding,list):errors.add('REPORT_FUNDING_CASH_AUDIT_MISSING');funding=[]
    fillmap={};fundmap=defaultdict(list);bad_ids=set();fundkeys=set()
    for f in fills:
        try:
            identity=str(f['trade_id']);asset=instrument(f['instrument'])
            if not identity:raise ValueError('FILL_ID_EMPTY')
            if identity in fillmap:bad_ids.add(identity);errors.add('DUPLICATE_REPORT_FILL_ID')
            fillmap[identity]={'asset':asset,'ns':int(f['fill_ns'])}
        except (KeyError,ValueError,TypeError):errors.add('REPORT_FILL_MAPPING_UNKNOWN')
    for i,row in enumerate(funding):
        try:
            if len(row)!=6:raise ValueError('FUNDING_SCHEMA')
            identity,asset=str(row[0]),instrument(row[1]);key=(identity,row[1])
            if key in fundkeys:errors.add('DUPLICATE_REPORT_FUNDING_KEY')
            fundkeys.add(key)
            before,after,delta=map(num,row[3:6])
            if abs(after-before-delta)>TOL:raise ValueError('FUNDING_NATIVE_BRIDGE')
            fundmap[identity].append({'index':i,'asset':asset,'ns':int(row[2]),'before':before,'after':after,'delta':delta})
        except (KeyError,ValueError,TypeError):errors.add('REPORT_FUNDING_MAPPING_UNKNOWN')
    return fillmap,fundmap,bad_ids,len(funding)


def attribute(report,rows,start=START,end=END):
    """Money allocation indexed by NATIVE STATE_EPOCH, never current receipt epoch."""
    if end<=start or start%STEP or end%STEP:raise ValueError('UTC_SIX_HOUR_BOUNDARIES_REQUIRED')
    errors=set();fillmap,fundmap,bad_ids,funding_count=report_maps(report,errors)
    epochs={};endpoints={};stats=defaultdict(Counter);seenfill=set();seenfund=set();seenpost=set()
    last_seq=0;current_epoch=None;prior=None;terminal=None;initial=None;last_receipt=None;last_current_event=None
    for row in rows:
        try:
            seq=int(row['sequence']);event=int(row['event_ns']);receipt=int(row['receipt_ns'])
            epoch=int(row['epoch']);state_epoch=int(row['state_epoch']);kind=row['kind']
            if seq!=last_seq+1:errors.add('TRACE_SEQUENCE_GAP_OR_DUPLICATE')
            last_seq=seq
            if receipt<event or state_epoch>epoch:raise ValueError('AMBIGUOUS_NATIVE_CLOCK_OR_EPOCH')
            if last_receipt is not None and receipt<last_receipt:raise ValueError('TRACE_RECEIPT_CLOCK_REGRESSION')
            last_receipt=receipt
            if kind!=WM:
                if last_current_event is not None and event<last_current_event:raise ValueError('CURRENT_NATIVE_EVENT_CLOCK_REGRESSION')
                last_current_event=event
            if row.get('positions') and (row.get('mark_available_ns') is None or int(row['mark_available_ns'])>event):
                raise ValueError('NATIVE_UPNL_MARK_CLOCK_UNKNOWN_OR_FUTURE')
            upnl,sides,cash,equity=position_values(row)
            signature=row['native_positions_sha256']
            if current_epoch is None:
                if epoch!=0 or state_epoch!=0 or cash!=SEED or sides or not(start<=event<=start+60_000_000_000):
                    raise ValueError('GENESIS_NATIVE_FLAT_SEED_NOT_PROVEN')
                epochs[0]={'cash':cash,'allocation':{'BTC':D(0),'SOL':D(0)},'signature':signature,'event':start}
                current_epoch=0;initial={'ns':start,'sequence':seq,'state_epoch':0,'receipt_ns':receipt,
                    'mark_available_ns':None,'basis':'ROOT_SEED10000_AND_OBSERVED_NATIVE_EPOCH0_FLAT',
                    'cash':cash,'equity':SEED,'upnl':{'BTC':D(0),'SOL':D(0)},'allocation':{'BTC':D(0),'SOL':D(0)}}
            if kind in POSTS:
                if state_epoch!=epoch or epoch in epochs or epoch!=current_epoch+1:
                    raise ValueError('MISSING_DUPLICATE_OR_NONCONTIGUOUS_MUTATION_EPOCH')
                previous=epochs[current_epoch];identity=str(row.get('native_id',''))
                postkey=(kind,identity,epoch)
                if postkey in seenpost:raise ValueError('DUPLICATE_NATIVE_POST')
                seenpost.add(postkey);delta=num(row['native_cash_delta'])
                if prior is None or prior.get('native_id')!=row.get('native_id') or int(prior['event_ns'])!=event:
                    raise ValueError('COMMITTED_PRE_POST_ID_CLOCK_PAIR_MISSING')
                expected='PRE_FILL_LAST_COMMITTED_NATIVE_COPY' if kind=='POST_FILL_COMMITTED_NATIVE' else 'PRE_FUNDING_COMMITTED_NATIVE_COPY'
                if prior.get('kind')!=expected or int(prior['state_epoch'])!=current_epoch:
                    raise ValueError('COMMITTED_PRE_STATE_EPOCH_UNKNOWN')
                if num(prior['cash'])!=previous['cash'] or prior['native_positions_sha256']!=previous['signature']:
                    raise ValueError('COMMITTED_PRE_STATE_BINDING_MISMATCH')
                if abs(cash-previous['cash']-delta)>TOL:raise ValueError('NATIVE_MUTATION_CASH_DELTA_MISMATCH')
                if kind=='POST_FILL_COMMITTED_NATIVE':
                    if identity in seenfill or identity in bad_ids:raise ValueError('DUPLICATE_OR_AMBIGUOUS_NATIVE_FILL_ID')
                    match=fillmap.get(identity)
                    if match is None or match['ns']!=event:raise ValueError('UNMAPPED_NATIVE_FILL_MONEY')
                    seenfill.add(identity);asset=match['asset']
                else:
                    matches=[f for f in fundmap.get(identity,[]) if f['index'] not in seenfund and f['ns']==event
                        and f['before']==previous['cash'] and f['after']==cash and f['delta']==delta]
                    if len(matches)!=1:raise ValueError('AMBIGUOUS_OR_UNMAPPED_NATIVE_FUNDING_MONEY')
                    match=matches[0];seenfund.add(match['index']);asset=match['asset']
                allocation=dict(previous['allocation']);allocation[asset]+=delta
                if abs(SEED+sum(allocation.values())-cash)>TOL:raise ValueError('CUMULATIVE_NATIVE_ASSET_CASH_BRIDGE')
                epochs[epoch]={'cash':cash,'allocation':allocation,'signature':signature,'event':event};current_epoch=epoch
            elif kind!=WM:
                if state_epoch!=epoch or epoch!=current_epoch:raise ValueError('CURRENT_NATIVE_STATE_EPOCH_MISMATCH')
                current=epochs[current_epoch]
                if cash!=current['cash'] or signature!=current['signature']:
                    raise ValueError('UNMAPPED_NATIVE_CASH_OR_POSITION_MUTATION')
            if kind==WM and start<event<=end and (event-start)%STEP==0:
                if event in endpoints:raise ValueError('DUPLICATE_SIX_HOUR_WATERMARK')
                snapshot=epochs.get(state_epoch)
                if snapshot is None or snapshot['event']>event or snapshot['cash']!=cash or snapshot['signature']!=signature:
                    raise ValueError('RETROSPECTIVE_ENDPOINT_STATE_CASH_ALIGNMENT_UNKNOWN')
                if int(row['mark_available_ns'])!=event or receipt<=event:
                    raise ValueError('ENDPOINT_MARK_OR_RECEIPT_CLOCK_UNKNOWN')
                retention=row.get('prior_source_retention')
                if state_epoch!=epoch:
                    if (not retention or int(retention['state_epoch'])!=state_epoch or int(retention['source_ns'])!=event
                        or retention['signature']!=[str(cash),signature] or int(retention['first_new_mutation_ns'])<=event):
                        raise ValueError('RETAINED_PRIOR_ENDPOINT_PROOF_MISSING')
                endpoints[event]={'ns':event,'sequence':seq,'state_epoch':state_epoch,'receipt_ns':receipt,
                    'mark_available_ns':event,'basis':WM,'cash':cash,'equity':equity,'upnl':upnl,'allocation':dict(snapshot['allocation'])}
            if kind in POSTS or kind=='PREQUOTE_DIRECT_NATIVE':
                if start<=event<end:
                    counts=stats[(event-start)//STEP];counts['native_current_snapshot_rows']+=1
                    if len(sides)==2:
                        counts['coexposure_rows']+=1;counts['opposite_sign_rows' if sides['BTC']!=sides['SOL'] else 'same_sign_rows']+=1
            if kind=='DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED':
                if terminal is not None:raise ValueError('DUPLICATE_TERMINAL_NATIVE_ROW')
                if event!=end or receipt!=end:raise ValueError('TERMINAL_NATIVE_CLOCK_AMBIGUOUS')
                if sides:raise ValueError('TERMINAL_NATIVE_NOT_FLAT')
                terminal={'status':'PENDING_FINAL_GLOBAL_ATTRIBUTION_CHECKS','event_ns':event,'receipt_ns':receipt,'state_epoch':state_epoch,
                    'direct_native_flat_cash_observation':{'status':'DIRECT_NATIVE_FLAT_ROW_OBSERVATION_ONLY',
                        'event_ns':event,'receipt_ns':receipt,'state_epoch':state_epoch,'cash':str(cash)},
                    'asset_cash_delta':{a:str(v) for a,v in epochs[state_epoch]['allocation'].items()},
                    'native_cash_minus_seed':str(cash-SEED),'native_asset_cash_sum':str(sum(epochs[state_epoch]['allocation'].values()))}
            if kind!=WM:prior=row
        except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
            errors.add(str(exc));prior=row if row.get('kind')!=WM else prior
    if set(fillmap)!=seenfill:errors.add('REPORT_NATIVE_FILL_COVERAGE_MISSING')
    if len(seenfund)!=funding_count:errors.add('REPORT_NATIVE_FUNDING_COVERAGE_MISSING')
    observer=report.get('coherent_native_observer',{})
    if observer.get('status')!='PASS' or observer.get('unknown'):errors.add('UPSTREAM_NATIVE_OBSERVER_NOT_PASS')
    if observer.get('sequence_count')!=last_seq:errors.add('REPORT_TRACE_SEQUENCE_COUNT_MISMATCH')
    if observer.get('native_unique_fills')!=len(seenfill):errors.add('REPORT_TRACE_FILL_COUNT_MISMATCH')
    if observer.get('native_funding_transitions')!=len(seenfund):errors.add('REPORT_TRACE_FUNDING_COUNT_MISMATCH')
    # Terminal asset allocation has the SAME final coverage validity as windows.
    # Keep the observed flat cash row separately; it cannot certify allocation.
    if terminal is not None:
        terminal['unknown_reasons']=sorted(errors)
        if errors:
            terminal.update(status='UNKNOWN_NATIVE_ASSET_ATTRIBUTION',asset_cash_delta=None,
                native_cash_minus_seed=None,native_asset_cash_sum=None)
        else:terminal['status']='NATIVE_FLAT_CASH_RECONCILED'
    points={**endpoints}
    if initial:points[start]=initial
    windows=[]
    for index in range((end-start)//STEP):
        a,b=start+index*STEP,start+(index+1)*STEP;p,q=points.get(a),points.get(b)
        reasons=set(errors)
        if p is None or q is None:reasons.add('SIX_HOUR_NATIVE_WATERMARK_ENDPOINT_MISSING')
        window={'index':index,'start_ns':str(a),'end_ns':str(b),'start_utc':utc(a),'end_utc':utc(b),
            'status':'UNKNOWN' if reasons else 'NATIVE_ATTRIBUTION_RECONCILED','unknown_reasons':'|'.join(sorted(reasons)),
            'BTC_pnl':None,'SOL_pnl':None,'native_joint_pnl':str(q['equity']-p['equity']) if p and q else None,
            'native_joint_cash_delta':str(q['cash']-p['cash']) if p and q else None,
            'native_joint_upnl_delta':str(sum(q['upnl'].values())-sum(p['upnl'].values())) if p and q else None,
            'BTC_cash_delta':None,'SOL_cash_delta':None,'BTC_upnl_delta':None,'SOL_upnl_delta':None,
            'asset_sum_minus_native_equity_delta':None,**dict(stats[index])}
        for label,point in (('start',p),('end',q)):
            for field in ('sequence','state_epoch','receipt_ns','mark_available_ns','basis'):
                window[label+'_'+field]=point.get(field) if point else None
        if not reasons:
            contributions={asset:(q['allocation'][asset]-p['allocation'][asset])+(q['upnl'][asset]-p['upnl'][asset]) for asset in ('BTC','SOL')}
            bridge=sum(contributions.values())-(q['equity']-p['equity'])
            if abs(bridge)>TOL:window.update(status='UNKNOWN',unknown_reasons='WINDOW_NATIVE_ATTRIBUTION_BRIDGE')
            else:
                for asset in ('BTC','SOL'):
                    window[asset+'_pnl']=str(contributions[asset]);window[asset+'_cash_delta']=str(q['allocation'][asset]-p['allocation'][asset])
                    window[asset+'_upnl_delta']=str(q['upnl'][asset]-p['upnl'][asset])
                window['asset_sum_minus_native_equity_delta']=str(bridge)
        windows.append(window)
    return windows,{'global_unknown_reasons':sorted(errors),'native_mutation_epochs':len(epochs)-1,
        'mapped_native_fills':len(seenfill),'mapped_native_funding_transitions':len(seenfund),
        'terminal_native_flat_cash_separate':terminal if terminal is not None else {'status':'UNKNOWN_TERMINAL_NATIVE_FLAT_ROW_MISSING'},
        'conditional_diagnostics':conditionals(windows),'trace_sequence_count':last_seq}


def utc(ns):return datetime.fromtimestamp(ns//1_000_000_000,timezone.utc).isoformat()


def conditionals(windows):
    known=[w for w in windows if w['status']=='NATIVE_ATTRIBUTION_RECONCILED']
    output={'known_windows':len(known),'unknown_windows':len(windows)-len(known),
        'basis':'ACTUAL_SAME_INVENTORY_PATH_ATTRIBUTION_NOT_BTC_ONLY_POLICY_COUNTERFACTUAL_OR_CAUSAL_HEDGE_BENEFIT'}
    for label,selected in (('BTC_adverse',[w for w in known if num(w['BTC_pnl'])<0]),('BTC_winner',[w for w in known if num(w['BTC_pnl'])>0])):
        output[label]={'count':len(selected),'SOL_positive_window_count':sum(num(w['SOL_pnl'])>0 for w in selected),
            'SOL_negative_window_count':sum(num(w['SOL_pnl'])<0 for w in selected),
            'SOL_positive_contribution_sum':str(sum((max(D(0),num(w['SOL_pnl'])) for w in selected),D(0))),
            'SOL_negative_contribution_sum':str(sum((min(D(0),num(w['SOL_pnl'])) for w in selected),D(0)))}
    n=max(1,(len(known)+19)//20) if known else 0
    for ranking,key in (('BTC_ranked_worst5pct_matched_windows','BTC_pnl'),('joint_ranked_worst5pct_matched_windows','native_joint_pnl')):
        subset=sorted(known,key=lambda w:num(w[key]))[:n]
        output[ranking]={'count':n,'window_indices':[w['index'] for w in subset],
            'BTC_mean':str(sum((num(w['BTC_pnl']) for w in subset),D(0))/n) if n else None,
            'joint_mean':str(sum((num(w['native_joint_pnl']) for w in subset),D(0))/n) if n else None}
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('report','trace','output'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('report','trace'):p.add_argument('--'+name+'-sha256',required=True)
    p.add_argument('--start-ns',type=int,default=START);p.add_argument('--end-ns',type=int,default=END);p.add_argument('--fixture-scope',action='store_true')
    args=p.parse_args()
    if (args.start_ns,args.end_ns)!=(START,END) and not args.fixture_scope:raise ValueError('NONCANONICAL_SCOPE_REQUIRES_FIXTURE_LABEL')
    for name in ('report','trace'):
        if sha(getattr(args,name))!=getattr(args,name+'_sha256'):raise ValueError('INPUT_PIN_MISMATCH:'+name)
    report=json.loads(args.report.read_text())
    with gzip.open(args.trace,'rt') as stream:
        windows,result=attribute(report,(json.loads(line) for line in stream),args.start_ns,args.end_ns)
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/'WINDOWS_6H.csv').open('x',newline='') as stream:
        fields=sorted({k for row in windows for k in row});writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(windows)
    result.update(status='DESCRIPTIVE_NATIVE_ATTRIBUTION_ONLY_NO_STRUCTURAL_OR_BENCHMARK_PASS',
        scope='FIXTURE_NOT_24M' if args.fixture_scope else 'CANONICAL_24M_SIX_HOUR_UTC',seed='10000',reserve='0',
        reconciliation_tolerance=str(TOL),decimal_precision=60,input_report_sha256=args.report_sha256,input_trace_sha256=args.trace_sha256,
        helper_source_sha256=sha(__file__),binary_identity='UNKNOWN_IF_NOT_EXPORTED; RETAIN_ROOT_EXTERNAL_RUNTIME_GROUP_FOR_COMPARISON',input_source_groups={k:report.get(k) for k in ('source_hashes','code_hash','config_hash','data_hash','policy_hash')},
        limitations=['Only POST native cash deltas are allocated; commissions/funding already in those deltas are not added twice.',
          'Endpoint native UPNL is read directly; no VWAP, fill matching, quantity-price PnL or equity simulation.',
          'Watermarks join snapshot state_epoch, native cash and position-state hash, including explicit prior-source retention.',
          'Missing final six-hour watermark remains UNKNOWN; post-boundary terminal native flat cash is separate.',
          'Malformed/gapped/duplicate/unmapped money or ambiguous clocks invalidate attribution; UNKNOWN never becomes zero.',
          'Conditional/tail comparisons use attributed BTC and joint results on the same actual inventory path, not a BTC-only policy.',
          'Snapshot coexposure counts are not duration weighted; meaningful hedge threshold/business GUID/feature equality remain UNKNOWN.',
          'Source/config/data/binary groups, including old A00/R1 and ARM/x86, are never merged by this single-input helper.'],
        native_engine_constructions=0)
    with (args.output/'SUMMARY.json').open('x') as stream:stream.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'output':str(args.output),'known_windows':result['conditional_diagnostics']['known_windows'],
        'unknown_windows':result['conditional_diagnostics']['unknown_windows'],'native_engine_constructions':0}))


if __name__=='__main__':main()
