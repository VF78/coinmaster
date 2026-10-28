"""Frozen prospective M3-CODE0 runner. Default stdlib-only locked validation.

--gate requires NEW direct native allocation/root claim/preflight. It reuses
exactly ONE existing native launch function with harness-only observations and
amount assertions derived from the registered source intent/actual native cash.
It does not qualify the full-held CODE0 endpoint: that is REQUIRED_M8.
"""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,re,gzip,argparse,sys,subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DATA=HERE/'M3_CODE0_DATA_PROSPECTIVE.json'
SCOPE='M3_LIFECYCLE_CODE0_PARTIAL_RESIDUAL_ONLY'
OLD_ATTEMPTS={'63ad9d1a-a374-472f-ba03-d02fb2f4e997','acd8fedd-0842-48a7-9df2-b8414bba3fb8'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def integer(v):
    if type(v)is int and v>=0:return v
    if type(v)is str and re.fullmatch(r'0|[1-9][0-9]*',v):return int(v)
    raise ValueError('NONCANONICAL_NONNEGATIVE_INTEGER')
def data_validation():
    case=json.loads(DATA.read_text());epochs={'BTC':0,'SOL':0};quotes=[]
    assert case['native_scope']==SCOPE and case['code0_full_endpoint_claim'] is False
    assert case['cancel_latency_ns']==2_000_000_000 and case['research_method_a_recovery_code0'] is True
    previous=-1
    for row in case['rows']:
        assert integer(row['ns'])>previous;previous=row['ns']
        for q in row.get('quotes',[]):
            assert D(q['bid'])<=D(q['ask']) and min(D(q[k]) for k in ('bid','ask','bid_depth','ask_depth'))>0
            epochs[q['asset']]+=1
            quotes.append(dict(global_input_index=len(quotes)+1,native_input_epoch=epochs[q['asset']],asset=q['asset'],ns=row['ns'],quote=q))
    first=next(q for q in quotes if q['ns']==70_100_000_000)
    second=next(q for q in quotes if q['ns']==70_200_000_000)
    assert D(first['quote']['ask'])==D('132.9') and D(second['quote']['ask'])==D('132.91')<=D('133.03')
    return dict(status='STDLIB_VALIDATED_NATIVE0_UNOBSERVED',quote_universe=epochs,global_input_list=quotes,data_sha256=sha(DATA),native_scope=SCOPE,full_CODE0_endpoint='REQUIRED_M8_NOT_YET_RUN')
def read_rows(path):
    with gzip.open(path,'rt') as f:
        return [(i,json.loads(line),hashlib.sha256(line.encode()).hexdigest()) for i,line in enumerate(f,1)]
def bind_engineering_receipts(out):
    expected=data_validation()['global_input_list'];risk_path=out/'risk.jsonl.gz';paired_path=out/'paired.jsonl.gz'
    paired={}
    for physical,row,linehash in read_rows(paired_path):
        if row['event']!='SOL_NATIVE_BOUNDARY':continue
        key=integer(row['sequence'])
        if key in paired:raise ValueError('DUPLICATE_SOL_BOUNDARY_SEQUENCE')
        paired[key]=(physical,row,linehash)
    risk_rows=read_rows(risk_path)
    receipts=[(physical,row) for physical,row,_ in risk_rows if row['event']=='SOL_BOUNDARY_RECEIPT']
    actual_result=json.loads((out/'result.json').read_text())
    first_parent=actual_result['result']['mechanism_case_witnesses']['normal_phase_witnesses']['first_parent']
    sol_inits=[(physical,row) for physical,row,_ in risk_rows if row['event']=='BEFORE_NATIVE_DISPATCH' and row.get('native_order',{}).get('instrument_id','').startswith('SOLUSDT') and row.get('native_initialized_event_id')]
    assert sol_inits,'MISSING_FIRST_SOL_INITIALIZATION_EVIDENCE'
    first_sol_init_physical,first_sol_init_row=sol_inits[0]
    assert len(receipts)==len(expected),'INDEPENDENT_SOURCE_QUOTE_UNIVERSE'
    seen=set();resolved=[];uncaptured=[];observed_episodes=set();initial_capture=None
    for (physical,receipt),item in zip(receipts,expected):
        index=integer(receipt['global_input_index']);assert index==item['global_input_index'] and index not in seen;seen.add(index)
        assert integer(receipt['native_input_epoch'])==item['native_input_epoch'] and integer(receipt['timestamp_ns'])==item['ns']
        quote=receipt['native_quote'];assert quote['instrument_id'].split('USDT')[0]==item['asset']
        assert integer(quote['ts_event'])==item['ns']
        for raw,key in (('bid_price','bid'),('ask_price','ask'),('bid_size','bid_depth'),('ask_size','ask_depth')):assert D(quote[raw])==D(item['quote'][key])
        raw=receipt['native_receipt_snapshot']
        episode=receipt['risk_episode_id'];number=integer(episode.rsplit(':',1)[1]);first_observed=episode not in observed_episodes
        observed_episodes.add(episode)
        if 'native_orders' not in raw:
            assert raw.get('availability')=='NOT_CAPTURED_NO_NEW_RISK_EPISODE'
            if first_observed and number>0:raise ValueError('MISSING_FIRST_EPISODE_FULL_CAPTURE')
            uncaptured.append(dict(risk_physical_row=physical,parent=receipt['parent'],risk_episode_id=episode,availability=raw['availability']))
            continue
        assert not raw['unresolved_ids'] and raw['raw_native_queue_visibility']=='NOT_EXPOSED_BY_PUBLIC_API'
        assert integer(receipt['sequence'])==integer(raw['risk_sequence_before_receipt'])+1
        ref=receipt['boundary_state_ref'];assert type(ref)is str and re.fullmatch(r'paired:[1-9][0-9]*',ref)
        bphysical,boundary,bhash=paired[integer(ref.split(':')[1])]
        assert boundary['event']=='SOL_NATIVE_BOUNDARY' and boundary['label']=='BEFORE_NATIVE_MATCHING_INPUT'
        assert integer(boundary['timestamp_ns'])==integer(receipt['timestamp_ns'])==item['ns']
        assert boundary['parent']==receipt['parent']==raw['parent']
        assert boundary['risk_episode_id']==receipt['risk_episode_id']==raw['risk_episode_id']
        inventory=raw['producer_inventory'];assert len(inventory['strategy_ids'])==1 and inventory['actor_ids']==[] and inventory['exec_algorithm_ids']==[]
        orders=raw['native_orders'];ids={o['client_order_id'] for o in orders};order_index={o['client_order_id']:o for o in orders}
        assert len(ids)==len(orders) and {v['client_order_id'] for v in raw['native_init_events']}==ids
        assert len(raw['native_init_events'])==len(ids)
        targets=raw['paired_owners']+raw['pending_by_order']+raw['native_open_ids']+raw['native_inflight_ids']+raw['native_emulated_ids']
        assert all(v['resolved'] and v['client_order_id'] in ids and v['instrument']==order_index[v['client_order_id']]['instrument_id'] for v in targets)
        assert all(o['strategy_id']==inventory['strategy_ids'][0] and o.get('exec_algorithm_id') is None for o in orders)
        if raw['parent']==first_parent and episode==str(first_parent)+':1' and initial_capture is None:
            assert physical<first_sol_init_physical and first_sol_init_row['parent']==first_parent,'EMPTY_CAPTURE_MUST_PRECEDE_FIRST_SOL_INIT_PHYSICAL_ROW'
            is_sol=lambda v:v.get('instrument_id',v.get('instrument','')).startswith('SOLUSDT')
            assert not any(is_sol(v) for v in orders+raw['native_init_events'])
            assert not any(is_sol(v) and D(v.get('quantity','0'))!=0 for v in raw['native_positions'])
            assert not any(is_sol(v) for v in targets)
            assert all(v['owner']['instrument']==v['instrument'] for v in raw['paired_owners'])
            assert not any(v['owner']['instrument'].startswith('SOLUSDT') for v in raw['paired_owners'])
            known_btc={'BTC_ENTRY','BTC_REDUCE'}
            assert all(v['intent']['action'] in known_btc for v in raw['pending_by_order'])
            assert all(v['action'] in known_btc for v in raw['domain_pending'].values())
            assert all(v['intent']['action'] in known_btc for v in raw['queued_intents'])
            assert raw['mandatory_sol_exit'] is None
            control=raw['native_control_state']
            assert control['liquidating'] is False and control['exiting'] is False and control['method_a_failed'] is False and control['forced_close_reason'] is None
            assert integer(raw['high_watermarks']['factory_client_order_id_count'])==len(ids)
            assert integer(raw['high_watermarks']['factory_order_list_id_count'])==0
            initial_capture=dict(parent=first_parent,risk_episode_id=episode,risk_physical_row=physical,first_sol_init_risk_physical_row=first_sol_init_physical,empty_SOL_before_init=True)
        resolved.append(dict(risk_physical_row=physical,boundary_ref=ref,paired_physical_row=bphysical,paired_line_sha256=bhash,parent=raw['parent'],risk_episode_id=raw['risk_episode_id'],input_index=index))
    assert resolved and initial_capture is not None,'MANDATORY_INITIAL_EPISODE_EMPTY_SOL_CAPTURE_MISSING'
    result=dict(status='ENGINEERING_EVIDENCE_BINDING_ONLY_ROOT_POSTRUN_MANUAL_SOURCE_CLOSURE_REQUIRED',initial_capture=initial_capture,uncaptured_receipts=uncaptured,complete_command_universe='UNKNOWN_REQUIRES_ROOT_POSTRUN_SEALED_SOURCE_CLOSURE',financial_qualification=False,risk_sha256=sha(risk_path),paired_sha256=sha(paired_path),source_data_sha256=sha(DATA),quote_universe=data_validation()['quote_universe'],resolved_boundaries=resolved,private_queue_visibility='NOT_EXPOSED_BY_PUBLIC_API')
    (out/'ENGINEERING_BINDER_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def install_harness():
    sys.path[:0]=[str(ROOT/'runtime'),str(ROOT/'runtime/tests')]
    import run_method_a_sol as m
    from msgspec.structs import replace
    original_config=m.config_for;original_phase=m.assert_m3_phase;original_cleanup=m.assert_m3_before_cleanup;OriginalProbe=m.M3Probe;Book=m.MethodABookWitness
    def config_for(case,*args,**kwargs):
        return replace(original_config(case,*args,**kwargs),research_method_a_recovery_code0=True)
    class DetailedBook(Book):
        def __init__(self):super().__init__(detailed=True);self.code0_current_input=None
        def pre_process(self,data):
            self.code0_current_input=data
            return super().pre_process(data)
        def receipt_snapshot(self):
            # Existing boundary hook returns early without a paired owner.
            # Emit a fresh READ-ONLY no-SOL-owner boundary for those public
            # input barriers too, rather than reusing a stale parent's ref.
            st=self.strategy
            if st is not None and st._pair is None:
                sol=st.config.sol_id;ep=st._domain.episode;parent=None if ep is None else ep.id
                held=st._pair_qty(sol)
                active=[o for o in st.cache.orders_open()+st.cache.orders_inflight() if o.instrument_id==sol]
                st._pair_log('SOL_NATIVE_BOUNDARY',self.code0_current_input.ts_event,
                    label='BEFORE_NATIVE_MATCHING_INPUT',parent=parent,
                    risk_episode_id=str(parent)+':'+str(st._mr_episode),actual_sol=held,
                    state='FLAT' if not held and not active else 'UNKNOWN',exact=not held and not active,
                    orders=[o.to_dict() for o in active],retiring=[],protection_since=None,entry_basis=None)
            return super().receipt_snapshot()
    class Code0Probe(OriginalProbe):
        def __init__(self,cfg):
            super().__init__(cfg);self.code0_sizing={};self.code0_dispatch_books=[]
        def _record_submission(self,order,intent_id,episode_id,action,reason=None,level=None):
            if action=='BTC_ENTRY' and episode_id not in self.code0_sizing:
                account=self.cache.account_for_venue(self.config.btc_id.venue)
                cash=account.balance_total(self.cache.instrument(self.config.btc_id).quote_currency).as_decimal()
                p=self._split_parent;intent=p['intent'];mult=self._domain.episode.btc_sizing_multiplier
                if mult is None:mult=self.config.candidate.btc_notional_multiplier
                requested=min(mult*float(cash),self.config.candidate.max_parent_notional)
                assert intent.requested_notional==requested,'REGISTERED_DOMAIN_NATIVE_CASH_REQUEST'
                self.code0_sizing[episode_id]=dict(native_cash=str(cash),requested_notional=str(intent.requested_notional),multiplier=str(mult),max_parent=str(self.config.candidate.max_parent_notional),initial_native_order=order.to_dict())
            return super()._record_submission(order,intent_id,episode_id,action,reason,level)
        def _mr_log(self,event,ns,**fields):
            row=super()._mr_log(event,ns,**fields)
            if event=='BEFORE_NATIVE_DISPATCH' and fields.get('recovery_code0'):
                try:book=self.config.research_native_book.matching(self.config.sol_id)
                except ValueError:book=None # zero consumed ask is NOT fabricated as positive liquidity
                self.code0_dispatch_books.append(dict(order_id=fields['order_id'],ns=ns,book=book))
            return row
    def recovery_orders(engine,strategy):
        return [(o,owner) for o,owner in m.m3_orders(engine,strategy,parent=strategy.m3_witnesses['first_parent']) if o.order_type.name=='LIMIT' and o.time_in_force.name=='IOC' and o.is_reduce_only and owner.get('code0_route')]
    def phase(engine,strategy,row,case):
        label=row['phase'];ns=row['ns'];w=strategy.m3_witnesses
        if label=='PUBLIC_OFF_INTENT_BEFORE_BREACH':
            assert strategy._pair_qty(m.BTC_PERP.id)==D(200) and strategy._pair_qty(m.SOL_PERP.id)==D('132.9')
            assert not strategy._mr_on and strategy._pair['close_sol'] and not strategy._mr_failed
            m.m3_protection(engine,strategy,{0,1,2});return
        if label=='HEALTHY_DEFER':
            original_phase(engine,strategy,row,case)
            zero=[o for o,_ in recovery_orders(engine,strategy) if o.ts_init==70*10**9]
            assert zero and all(o.status.name=='CANCELED' and not o.filled_qty.as_decimal() for o in zero),'CODE0_GENUINE_ZERO_NO_PENDING_CREDIT'
            w['CODE0_ZERO']=[o.to_dict() for o in zero];return
        if label in {'CODE0_PARTIAL_ONE','CODE0_RESIDUAL_PARTIAL'}:
            expected_qty=D('132.9') if label=='CODE0_PARTIAL_ONE' else D('132.8')
            held=D('132.8') if label=='CODE0_PARTIAL_ONE' else D('132.7')
            orders=[o for o,_ in recovery_orders(engine,strategy) if o.ts_init==ns]
            assert len(orders)==1;order=orders[0]
            assert order.quantity.as_decimal()==expected_qty and order.price.as_decimal()==D('133.03') and order.side.name=='BUY'
            assert order.status.name=='CANCELED' and order.filled_qty.as_decimal()==D('.1')
            fills=[e for e in order.events if type(e).__name__=='OrderFilled'];assert len(fills)==1 and fills[0].last_qty.as_decimal()==D('.1')
            ask=D('132.9') if label=='CODE0_PARTIAL_ONE' else D('132.91')
            assert fills[0].last_px.as_decimal()==ask and strategy._pair_qty(m.SOL_PERP.id)==held
            before=next(v for v in strategy.code0_dispatch_books if v['order_id']==str(order.client_order_id))
            assert before['book'] is not None and D(before['book']['ask'])==ask and D(before['book']['ask_size'])==D('.1'),'ACTUAL_NEW_ASK_LEVEL_NOT_ASSUMED_REPLENISH'
            assert not strategy._mr_failed and strategy._pair['debt_since']<=70*10**9
            m.m3_protection(engine,strategy,{0,1,2});w[label]=dict(native_order=order.to_dict(),fills=[type(e).to_dict(e) for e in fills],dispatch_book=before)
            return
        if label=='FIRST_FLAT_ACK':
            assert not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight() and not strategy._pending_by_order
            cash=engine.cache.account_for_venue(m.SIM).balance_total(m.BTC_PERP.quote_currency).as_decimal()
            assert cash==D('6010.94888295') and D(str(strategy.config.research_method_a_peak_source.events.peak['equity']))==D(10000)
            w[label]=dict(native_cash=str(cash),native_account=m.native_account_snapshot(engine.cache.account_for_venue(m.SIM),(m.BTC_PERP.id,m.SOL_PERP.id)));return
        if label=='SECOND_PARENT_PASSIVE':
            p=strategy._split_parent;assert p and p['episode_id']!=w['first_parent'];sizing=strategy.code0_sizing[p['episode_id']]
            assert D(sizing['native_cash'])==D(w['FIRST_FLAT_ACK']['native_cash'])
            step=strategy.cache.instrument(m.BTC_PERP.id).size_increment.as_decimal()
            total=(D(str(float(D(sizing['requested_notional'])/D(100))))//step)*step
            first=D(max(1,int(total/step)//2))*step;second=total-first
            assert p['quantity']==total and p['first_filled']==p['first_quantity']==first and second>0
            seconds=[o for o in engine.cache.orders() if o.instrument_id==m.BTC_PERP.id and not o.is_reduce_only and o.order_type.name=='LIMIT' and o.side.name=='SELL']
            assert len(seconds)==1;order=seconds[0]
            assert order.status.name=='ACCEPTED' and order.is_post_only and order.price.as_decimal()==D('100.3') and not order.filled_qty.as_decimal() and order.quantity.as_decimal()==second
            w[label]=order.to_dict();w['second_parent']=p['episode_id'];w['second_expected']=dict(total=str(total),first=str(first),second=str(second),registered_native_cash_sizing=sizing);return
        if label=='SECOND_PARENT_FULL':
            o=next(o for o in engine.cache.orders() if str(o.client_order_id)==w['SECOND_PARENT_PASSIVE']['client_order_id']);fills=[e for e in o.events if type(e).__name__=='OrderFilled'];accepted=[e for e in o.events if type(e).__name__=='OrderAccepted']
            assert o.status.name=='FILLED' and o.filled_qty.as_decimal()==D(w['second_expected']['second'])
            assert fills and all(e.last_px.as_decimal()==D('100.3') and e.liquidity_side.name=='MAKER' and accepted[0].ts_event<e.ts_event==ns for e in fills)
            assert strategy._pair_position(m.BTC_PERP.id).is_short and strategy._pair_qty(m.BTC_PERP.id)==D(w['second_expected']['total']);w[label]=o.to_dict();return
        if label=='SECOND_SOL_PROTECTED':
            entries=m.m3_orders(engine,strategy,'ENTRY',w['second_parent']);assert len(entries)==1;entry,_=entries[0]
            admission=[v for v in strategy.m3_risk if v['event']=='HEDGE_ADMISSION' and v['parent']==w['second_parent']];assert len(admission)==1 and admission[0]['band']=='MEDIUM' and admission[0]['useful']
            target=D(admission[0]['target'])
            assert entry.status.name=='FILLED' and entry.quantity.as_decimal()==entry.filled_qty.as_decimal()==target==strategy._pair_qty(m.SOL_PERP.id)
            assert target>D('.1') and strategy._pair_position(m.SOL_PERP.id).is_long and strategy._pair['atr']==D(2) and strategy._pair['p0']==D(100)
            assert not any(v['action']=='BTC_REDUCE' and v['parent']==w['second_parent'] for v in strategy.native_fill_receipts)
            w['second_sol_quantity']=str(target);w[label]=m.m3_protection(engine,strategy,{0,1,2});return
        return original_phase(engine,strategy,row,case)
    def fault(engine,strategy,case,now):
        start=case['expected_negative_not_before_ns'];rows=[v for v in strategy.m3_risk if v['event']=='QUALIFICATION_NO_GO']
        assert now>=start and len(rows)==1 and int(rows[0]['timestamp_ns'])==start and rows[0]['reason']==case['expected_negative_reason']=='PARTIAL_NATIVE_STOP'
        stopped=[(o,owner) for o,owner in m.m3_orders(engine,strategy,'STOP') if any(type(e).__name__=='OrderFilled' and e.ts_event==start for e in o.events)];assert len(stopped)==1;o,owner=stopped[0]
        assert owner['parent']==strategy.m3_witnesses['second_parent'] and o.order_type.name=='STOP_MARKET' and o.time_in_force.name=='IOC' and o.is_reduce_only and o.side.name=='SELL' and o.trigger_price.as_decimal()==D(98)
        assert o.status.name=='CANCELED' and o.quantity.as_decimal()==D(strategy.m3_witnesses['second_sol_quantity']) and o.filled_qty.as_decimal()==D('.1')
        fills=[e for e in o.events if type(e).__name__=='OrderFilled'];assert len(fills)==1 and fills[0].last_qty.as_decimal()==D('.1') and fills[0].last_px.as_decimal()==D(98)
        assert any(type(e).__name__=='OrderCanceled' and e.ts_event==start for e in o.events)
        assert strategy._mr_failed and strategy._pair_no_increase() and strategy._forced_close_reason=='METHOD_A_PARTIAL_NATIVE_STOP'
        assert not any(not o.is_reduce_only and o.ts_init>=start for o in engine.cache.orders())
        strategy.m3_fault=m.wire(dict(reason=rows[0],STOP=o.to_dict(),native_events=[type(e).to_dict(e) for e in o.events],fault_parent=owner['parent']));return strategy.m3_fault
    def cleanup(engine,strategy):
        result=original_cleanup(engine,strategy)
        assert {'CODE0_ZERO','CODE0_PARTIAL_ONE','CODE0_RESIDUAL_PARTIAL'}<=set(strategy.m3_witnesses)
        result.update(native_scope=SCOPE,full_CODE0_endpoint='REQUIRED_M8_NOT_YET_RUN',financial_qualification=False);return result
    m.config_for=config_for;m.MethodABookWitness=DetailedBook;m.M3Probe=Code0Probe;m.assert_m3_phase=phase;m.assert_m3_fault=fault;m.assert_m3_before_cleanup=cleanup
    return m

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gate');parser.add_argument('--prepare-native-approval');args=parser.parse_args()
    if not args.gate and not args.prepare_native_approval:
        print(json.dumps(data_validation(),indent=2));return 0 # no native imports/constructor
    if args.prepare_native_approval:
        approval=json.loads(Path(args.prepare_native_approval).read_text())
        assert approval['root_public_input_preparation_go'] is True and approval['engine_constructor_authority']==0
        assert approval['harness_sha256']==sha(__file__) and approval['data_sha256']==sha(DATA)
        print(json.dumps(install_harness().prepare(DATA),indent=2));return 0
    gate=json.loads(Path(args.gate).read_text())
    assert gate['root_go']is True and gate['native_scope']==SCOPE and gate['code0_full_endpoint_claim']is False
    assert gate['harness_sha256']==sha(__file__) and gate['raw_data_sha256']==sha(DATA)
    assert gate['attempt_id'] not in OLD_ATTEMPTS and not Path(gate['namespace']).exists()
    allocation_path=Path(gate['new_allocation_receipt']);assert sha(allocation_path)==gate['new_allocation_sha256']
    allocation=json.loads(allocation_path.read_text());assert allocation['owner_approved_fresh_M3_CODE0'] is True and allocation['max_total']==19 and allocation['engineering_cap']==12 and allocation['prefix_cap']==6 and allocation['full_cap']==1
    assert allocation['new_native_authority']==1 and allocation['attempt_id']==gate['attempt_id']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==gate['source_commit']
    code=install_harness().launch(DATA,Path(args.gate)) # exactly one original root-gated constructor
    if code:return code
    bind_engineering_receipts(Path(gate['namespace']));return 0

if __name__=='__main__':raise SystemExit(main())
