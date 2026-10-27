
"""Stdlib-only rights V2 contract unit draft. Synthetic facts are not native execution evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal as D
import builtins,copy,json,sqlite3,sys

def proof():
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.startswith('nautilus_trader'):raise AssertionError('RIGHTS_READER_MUST_NOT_IMPORT_NATIVE')
        return original(name,*args,**kwargs)
    builtins.__import__=guarded
    try:
        import method_a_financial_reader as r
        observer='6e21b00d7df3a7819a67bf0c571ff31f33822888d5095ebf43075c7fa7f72aa7'
        policy=dict(sol_overlay_enabled=True,sol_late_entry_after_tp=True,episode_fixed_beta=False,
            sol_size_multipliers_h=[1.75,2.625,3.5],sol_entry_z=[1.25,2.5,3.75],max_parent_notional=30000000.,
            sol_max_holding_days=14,sol_exit_half_z=.375,sol_exit_all_z=.125)
        sessions=dict(last_accepted_session='100',latest_seen_session='100',
            current_BTC_SOL_signal_sessions=dict(BTC=dict(instrument='BTCUSDT-PERP.P1SIM',ts_event='100'),SOL=dict(instrument='SOLUSDT-PERP.P1SIM',ts_event='100'),
                bar_index=0,source_bar_session_ns='100',bar_close_time='2024-09-02T00:00:00+00:00'),
            current_features=dict(index=0,side=1,beta=1.,relative=2.,mu=0.,sigma=1.,z=2.))
        def ep(consumed=0.,h=100.):
            values=dict(h=h,btc_initial_qty=1.,btc_net_planned_qty=1.,btc_reference_qty=1.,btc_entry_vwap=10000.,beta_entry=1.,fixed_sigma=None)
            maps=dict(sol_add_filled_notional={} if consumed==0 else {'0':consumed},sol_ownership_transfer_credit={},sol_risk_retired_notional={},sol_right_fraction={'0':1.})
            return dict(id='UNIT',side=1,h=h,old_SOL_rights=[0],old_SOL_fractions={'0':1.},omitted_raw_levels=[0],
                sol_add_filled_notional=maps['sol_add_filled_notional'],sol_ownership_transfer_credit={},sol_risk_retired_notional={},
                source_float_values=values,source_float_hex={k:None if v is None else float(v).hex() for k,v in values.items()},
                source_float_maps=maps,source_float_maps_hex={name:{k:float(v).hex() for k,v in x.items()} for name,x in maps.items()},
                raw_entry=dict(btc_entry_qty_exact='1',btc_tp_target_lots={'0':0,'1':500,'2':500},btc_tp_filled_lots={},method_a_raw_target_lots=None),
                btc_deferred_right_touched=True,btc_deferred_right_reference_price='10000.1',sol_right_decision_index={'0':0},
                sol_lifecycle=dict(sol_qty=0.,first_fill_at=None,first_owned_at=None,half_done=False,half_decision_index=None))
        intent=dict(id='I',parent='UNIT',action='SOL_ADD',level=0,side=-1,quantity=None,requested_notional=175.,decision_index=0,reason=None)
        order=dict(order_id='O',instrument='SOLUSDT-PERP.P1SIM',side='SELL',strategy='UNIT-001',quantity='1.7',reduce_only=False,status='INITIALIZED')
        def fixture(db):
            r.rights_v2_tables(db)
            for table in ('fills','sol_before','native_acks','position_trades'):db.execute('CREATE TABLE '+table+' (id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            def put(table,key,value):db.execute('INSERT INTO '+table+' VALUES (?,?)',(key,json.dumps(value,sort_keys=True)))
            entry=dict(episode_id='UNIT',net_submitted_btc_qty='1',q1_ns='10',sol_right_activations=[dict(levels=[0],timestamp_ns='30',confirmed_native_entry_qty='1')])
            report=dict(entry_sizing_audit=[entry])
            put('fills','B',dict(native_event_id='B',action='BTC_ENTRY',parent='UNIT',level=None,sequence=1,ns='10',qty='1',px='10000',instrument='BTCUSDT-PERP.P1SIM',oid='BTC'))
            put('rights_after','B',dict(seq=1,episode=ep()))
            untouched=ep();untouched['btc_deferred_right_touched']=False;untouched['old_SOL_rights']=[];untouched['sol_right_decision_index']={}
            latched=ep();latched['old_SOL_rights']=[];latched['sol_right_decision_index']={}
            unready=copy.deepcopy(sessions);unready['last_accepted_session']=None
            put('rights_quote_actions','2',dict(before_seq=2,after_seq=3,input=dict(instrument='BTCUSDT-PERP.P1SIM',event_ns='20',bid='10000.1',ask='10000.2'),
                before=dict(episode=untouched,sessions=unready),after=dict(episode=latched,sessions=unready)))
            put('rights_quote_actions','4',dict(before_seq=4,after_seq=5,input=dict(instrument='BTCUSDT-PERP.P1SIM',event_ns='30',bid='9999.0',ask='9999.1'),
                before=dict(episode=latched,sessions=sessions),after=dict(episode=ep(),sessions=sessions)))

            put('rights_origin','I',dict(seq=5,method='EARLIEST_ACTUAL_QUEUED_INTENT',intent=intent,context=dict(episode=ep(),sessions=sessions)))
            a=dict(schema='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2',boundary='ORIGINAL_RECORD_SUBMISSION_RETURNED_TRUE_BEFORE_NATIVE_TRANSPORT',
                client_order_id='O',intent_id='I',parent='UNIT',current_parent='UNIT',action='SOL_ADD',level=0,checkpoint_result=True,
                initialized_order_is_ACK_or_fill=False,domain_pending_contains_intent=True,order_decision_index=0,pending_intent=intent,
                original_policy=policy,sessions=sessions,native_initialized_order=order,native_quote=dict(instrument='SOLUSDT-PERP.P1SIM',event_ns='40',bid='100',ask='100.1'),
                instrument=dict(id='SOLUSDT-PERP.P1SIM',size_increment='.1',min_quantity='.1',min_notional=None),
                episode=dict(ep(),h_at_SOL_ADD_admission=100.,sol_add_filled_notional_at_SOL_ADD_admission={}))
            put('rights_admission','O',dict(seq=7,admission=a,context=dict(episode=ep(),sessions=sessions)))
            # Registered MARKET IOC uses no optional Accepted event; history is real fact-chain input here.
            history=[dict(id='INIT',type='OrderInitialized'),dict(id='SUB',type='OrderSubmitted'),dict(id='F1',type='OrderFilled'),dict(id='F2',type='OrderFilled')]
            actual=dict(order,status='FILLED',filled='1.7',leaves='0.0',native_history=history)
            put('rights_native_order','O',dict(seq=11,order=actual,event_id='F2',event_type='OrderFilled'))

            for event,seq,qty,pre,post in [('F1',9,'.5',0.,50.),('F2',11,'1.2',50.,170.)]:
                put('fills',event,dict(native_event_id=event,action='SOL_ADD',parent='UNIT',level=0,sequence=seq,qty=qty,px='100',instrument='SOLUSDT-PERP.P1SIM',oid='O'))
                put('position_trades',event,dict(native_event_id=event,oid='O',qty=qty,px='100'))
                put('sol_before',event,dict(episode=ep(pre),sequence=seq-1))
                put('rights_after',event,dict(seq=seq,episode=ep(post)))
            meta=dict(legacy_SOL_admission_capture=dict(schema='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2',attempts=1,recorded=1,error_count=0))
            return report,meta
        checks=[]
        with TemporaryDirectory(prefix='method-a-rights-v2-unit-') as directory:
            def run_case(name,edit=None):
                db=sqlite3.connect(str(Path(directory)/(name+'.sqlite')));report,meta=fixture(db)
                if edit:edit(db,report,meta)
                result=r.rights_v2_evidence(db,report,'P0',meta,observer);db.close();return result
            result=run_case('positive_partial')
            assert result['status']=='PASS' and result['actual_SOL_ADD_fills']==2 and result['actual_qualified_orders']==1
            assert result['examples'][0]['actual_native_market_execution']['optional_Accepted_present'] is False
            checks.append('market_no_Accepted_genuine_Filled_native_history_and_partial_trade_joins')
            def change_body(db,table,key,edit):
                value=json.loads(db.execute('SELECT body FROM '+table+' WHERE id=?',(key,)).fetchone()[0]);edit(value)
                db.execute('UPDATE '+table+' SET body=? WHERE id=?',(json.dumps(value,sort_keys=True),key))
            missing=run_case('missing_origin',lambda db,*_:db.execute("DELETE FROM rights_origin"))
            assert missing['status']=='UNKNOWN' and any('origin' in x for x in missing['missing_required_fields'])
            checks.append('missing_actual_origin_is_UNKNOWN')
            db=sqlite3.connect(str(Path(directory)/'touch_sequence.sqlite'));report,meta=fixture(db)
            r.rights_guarded_touch(db,ep(),report['entry_sizing_audit'][0],0,7)
            # A later same-timestamp fill must neither invalidate the earlier snapshot nor earn it retroactively.
            future=dict(native_event_id='FUTURE_BTC',action='BTC_ENTRY',parent='UNIT',level=None,sequence=6,ns='30',qty='.5',px='10000',instrument='BTCUSDT-PERP.P1SIM',oid='BTC2')
            db.execute('INSERT INTO fills VALUES (?,?)',('FUTURE_BTC',json.dumps(future)))
            r.rights_guarded_touch(db,ep(),report['entry_sizing_audit'][0],0,7)
            report['entry_sizing_audit'][0]['sol_right_activations'][0]['confirmed_native_entry_qty']='1.5'
            try:r.rights_guarded_touch(db,ep(),report['entry_sizing_audit'][0],0,7)
            except r.RightsPolicyViolation:pass
            else:raise AssertionError('FUTURE_SAME_NS_ENTRY_GRANTED_EARLIER_RIGHT')
            db.close()
            checks.append('earlier_earned_touch_unready_then_later_activation_without_recross_and_sequence_cutoff')
            def fake_init(db,*_):
                change_body(db,'rights_native_order','O',lambda x:x.update(order=dict(order,filled='0',leaves='1.7',native_history=[dict(id='INIT',type='OrderInitialized')]),event_id='INIT',event_type='OrderInitialized'))
            assert run_case('fake_init',fake_init)['status']=='UNKNOWN'
            checks.append('initialized_only_history_never_counts_as_market_execution')
            db=sqlite3.connect(str(Path(directory)/'unfilled_terminal.sqlite'));report,meta=fixture(db)
            db.execute("DELETE FROM fills WHERE id IN ('F1','F2')");db.execute('DELETE FROM position_trades')
            native=dict(order,status='CANCELED',filled='0',leaves='1.7',native_history=[dict(id='INIT',type='OrderInitialized'),dict(id='SUB',type='OrderSubmitted'),dict(id='CANCEL',type='OrderCanceled')])
            db.execute('UPDATE rights_native_order SET body=? WHERE id=?',(json.dumps(dict(seq=8,order=native,event_id='CANCEL',event_type='OrderCanceled')),'O'))
            terminal=r.rights_market_execution(db,'O',order)
            assert terminal['kind']=='GENUINE_UNFILLED_NATIVE_TERMINAL' and terminal['actual_trade_events']==0
            db.close()
            checks.append('unfilled_market_terminal_requires_genuine_native_disposition')
            price=r.authorized_tp_prices('10000','.01',1)[0]
            btc=dict(instrument='BTCUSDT-PERP.P1SIM',side='SELL',strategy='BTC-001',price=str(price),quantity='1')
            assert 'P1_TP_native_ACK_price_missing' in r.tp_order_errors(btc,dict(side='SELL',strategy_id='BTC-001'),None,price,1)
            checks.append('resting_BTC_TP_actual_ACK_remains_strict')

            def conflict(db,*_):change_body(db,'rights_origin','I',lambda x:x['intent'].update(requested_notional=999.))
            assert run_case('conflict',conflict)['status']=='UNKNOWN'
            checks.append('conflicting_immutable_intent_is_UNKNOWN')
            def stale(db,*_):change_body(db,'rights_admission','O',lambda x:x['context']['sessions'].update(last_accepted_session='99'))
            assert run_case('stale',stale)['status']=='UNKNOWN'
            checks.append('stale_current_native_session_is_UNKNOWN')
            def latch(db,report,meta):meta['legacy_SOL_admission_capture']['error_count']=1
            assert run_case('capture_error',latch)['status']=='UNKNOWN'
            def counts(db,report,meta):meta['legacy_SOL_admission_capture']['recorded']=2
            assert run_case('duplicate_count',counts)['status']=='UNKNOWN'
            checks.append('capture_error_or_duplicate_count_cannot_PASS')
            def requeue(db,*_):
                value=json.loads(db.execute("SELECT body FROM rights_admission WHERE id='O'").fetchone()[0])
                value['seq']=15;value['admission']['client_order_id']='O2';value['admission']['native_initialized_order']['order_id']='O2'
                db.execute('INSERT INTO rights_admission VALUES (?,?)',('O2',json.dumps(value)))
            assert run_case('unproven_requeue',requeue)['status']=='UNKNOWN'
            checks.append('same_intent_unproven_requeue_is_UNKNOWN_no_new_policy')
            def missing_fact(db,*_):change_body(db,'rights_admission','O',lambda x:x['context']['episode'].pop('source_float_hex'))
            assert run_case('missing_source_hex',missing_fact)['status']=='UNKNOWN'
            checks.append('mandatory_source_fact_missing_is_UNKNOWN')
            def no_clamp(db,*_):
                def update(x):
                    x['context']['episode']=ep(h=50.)
                    x['admission']['episode']=dict(ep(h=50.),h_at_SOL_ADD_admission=50.,sol_add_filled_notional_at_SOL_ADD_admission={})
                change_body(db,'rights_admission','O',update)
            result=run_case('unobserved_H_change',no_clamp)
            assert result['status']=='UNKNOWN' and any('writer' in x for x in result['missing_required_fields'])
            checks.append('changed_budget_requires_actual_writer_interval_not_fabricated_origin_or_new_clamp')
        assert not any(x.startswith('nautilus_trader') for x in sys.modules)
        return dict(status='METHOD_A_RIGHTS_V2_STDLIB_PURE_PASS',checks=checks,native_imports=0,engine_constructors=0,
            synthetic_unit_facts_are_not_native_evidence=True,actual_P0_replay_read=False)
    finally:builtins.__import__=original
