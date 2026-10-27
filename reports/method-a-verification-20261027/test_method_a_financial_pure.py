"""Stdlib-only financial adapter contract proof; no actual result analysis."""
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal as D,getcontext
from collections import Counter
import builtins,gzip,hashlib,json,sqlite3,sys


def proof():
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.startswith('nautilus_trader'):raise AssertionError('FINANCIAL_READER_MUST_NOT_IMPORT_NATIVE')
        return original(name,*args,**kwargs)
    builtins.__import__=guarded
    try:
        import method_a_financial_reader as reader
        from method_a_financial_binding import bind
        import prefix_common as c
        assert getcontext().prec==50
        assert reader.es([]) is None
        assert reader.es([D('.5')])=='.5' or D(reader.es([D('.5')]))==D('.5')
        values=[D(i)/100 for i in range(1,7)]
        assert D(reader.es(values))==(D('.06')+D('.2')*D('.05'))/D('1.2')
        assert D(reader.es([-D('.01'),-D('.02')]))==-D('.01')
        assert reader.native_cash_residual('10099','100','-1')==0
        assert reader.native_cash_residual('10099.00000001','100','-1')==D('.00000001')
        assert reader.money('10_000.00000000 USDT')==(D(10000),'USDT')
        assert reader.authorized_tp_prices('10000','.01',1)==tuple(map(D,('10033.4','10066.7','10100')))
        assert reader.authorized_tp_prices('10000','.01',-1)==tuple(map(D,('9966.6','9933.3','9900')))
        assert getcontext().prec==50
        for reference,d3,side in [('NaN','.01',1),('0','.01',1),('10000','0',1),('10000','.00001',1),('10000','.01',0),('10000','4',-1)]:
            try:reader.authorized_tp_prices(reference,d3,side)
            except ValueError:pass
            else:raise AssertionError('INVALID_OR_NONPOSITIVE_GEOMETRY_ACCEPTED')
        for side in (1,-1):
            price=reader.authorized_tp_prices('10000','.01',side)[0];exit_side='SELL' if side==1 else 'BUY'
            order=dict(instrument='BTCUSDT-PERP.P1SIM',side=exit_side,strategy='UNIT-001',price=str(price),quantity='1.000')
            owner=dict(side=exit_side,strategy_id='UNIT-001')
            ack=dict(order)
            assert not reader.tp_order_errors(order,owner,ack,price,side)
            for key,value,issue in [('instrument','SOLUSDT-PERP.P1SIM','wrong_instrument'),('side','BUY' if side==1 else 'SELL','wrong_exit_side'),
                                    ('price','NaN','not_authorized_native_price'),('price','0','not_authorized_native_price'),
                                    ('price',str(price+D('.1')),'not_authorized_native_price')]:
                changed=dict(order,**{key:value})
                assert any(issue in x for x in reader.tp_order_errors(changed,owner,ack,price,side))
            assert 'P1_TP_native_ACK_price_missing' in reader.tp_order_errors(order,owner,None,price,side)
            assert 'P1_TP_current_ACK_price_quantity_mismatch' in reader.tp_order_errors(order,owner,dict(ack,price=str(price+D('.1'))),price,side)
            assert 'P1_TP_strategy_identity_mismatch' in reader.tp_order_errors(order,dict(owner,strategy_id='FOREIGN'),ack,price,side)
        authority=reader.tp_authority([dict(event='ENTITLEMENT',episode_id='UNIT',cumulative_entry_lots=1000,timestamp_ns=n,tp_reference=ref)
                                      for n,ref in [(1,'10000'),(2,'10001'),(3,'10002')]])
        assert authority['references'][('UNIT',1000)] is None
        with TemporaryDirectory(prefix='method-a-financial-pure-') as directory:
            d=Path(directory);gate=d/'gate.json';c.write(gate,dict(schema='OLD_A0_SCHEMA'))
            try:bind(gate,c.sha(gate))
            except (AssertionError,KeyError):pass
            else:raise AssertionError('OLD_FINANCIAL_GATE_ACCEPTED')
            state=dict(native_cash='10000.00000000 USDT',positions=[dict(instrument='BTCUSDT-PERP.P1SIM',quantity='1',side='LONG')],
                active_orders={},owned_pending={},queued=[],episode=dict(id='UNIT',entry_qty_exact='1',target_lots={},actual_tp_filled_lots={},risk_retired_lots={}),
                method_a=None,method_a_active_owners={},method_a_commands={})
            digest=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            first=dict(sequence=1,phase='BEFORE_STRATEGY_on_order_filled_NATIVE_CACHE_ALREADY_MUTATED',event_ns='1',state=state,state_sha256=digest,
                native_event_id='UNIT',native_event_type='OrderFilled')
            second=dict(sequence=2,phase='BEFORE_NATIVE_MATCHING_INPUT',event_ns='2',state_ref_sha256=digest,state_sha256=digest,
                input=dict(instrument='BTCUSDT-PERP.P1SIM',event_ns='2'))
            path=d/'unit-profile.gz'
            with gzip.open(path,'wt') as stream:stream.write(json.dumps(first)+chr(10))
            db=sqlite3.connect(str(d/'transitional.sqlite'));p=reader.profile_read(path,db,{},'P1');db.close()
            assert not any(key.startswith('P1_') for key in p['issues'])
            assert p['complete_interior_quote_universe'] is False
            with gzip.open(path,'wt') as stream:
                stream.write(json.dumps(first)+chr(10));stream.write(json.dumps(second)+chr(10))
            db=sqlite3.connect(str(d/'before-match.sqlite'));p=reader.profile_read(path,db,{},'P1');db.close()
            assert p['issues']['P1_missing_native_TP_state']==1
            db=sqlite3.connect(str(d/'dedup.sqlite'));db.execute('CREATE TABLE facts (id TEXT PRIMARY KEY,body TEXT NOT NULL)');issues=Counter()
            assert reader.insert_unique(db,'facts','UNIT',{'native':'same'},issues)
            assert reader.insert_unique(db,'facts','UNIT',{'native':'same'},issues) is False and not issues
            assert reader.insert_unique(db,'facts','UNIT',{'native':'conflict'},issues) is False and issues['conflicting_facts']==1
            db.close()
            db=sqlite3.connect(str(d/'rights.sqlite'))
            db.execute('CREATE TABLE fills (id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            db.execute('CREATE TABLE sol_before (id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            report=dict(split_cover_audit=dict(parents=[dict(episode_id='UNIT',planref_v1_h_actual='99999')]),
                entry_sizing_audit=[dict(episode_id='UNIT',net_submitted_btc_qty='1',reference_target_lots={'0':212,'1':212,'2':576},
                    omitted_zero_levels=[0],sol_right_activations=[dict(levels=[0],timestamp_ns=1)])])
            empty=reader.rights_evidence(db,report)
            assert empty['mechanism_status']=='NOT_TESTED_NO_ACTUAL_SOL_ADD_FILLS' and empty['actual_SOL_ADD_fills']==0
            fill=dict(action='SOL_ADD',parent='UNIT',native_event_id='UNIT-FILL',level=0,ns=2)
            before=dict(episode=dict(id='UNIT',old_SOL_fractions={'0':'.5'},old_SOL_rights=[0],entry_qty_exact='.5'))
            db.execute('INSERT INTO fills VALUES (?,?)',('UNIT-TRADE',json.dumps(fill)))
            db.execute('INSERT INTO sol_before VALUES (?,?)',('UNIT-FILL',json.dumps(before)))
            rights=reader.rights_evidence(db,report)
            assert rights['status']=='UNKNOWN' and rights['actual_SOL_ADD_fills']==1
            assert not rights['failures'] and rights['examples'][0]['current_parent_matched']
            assert 'profile.episode.h_at_SOL_ADD_admission' in rights['missing_required_fields']
            assert 'profile.episode.sol_add_filled_notional_at_SOL_ADD_admission' in rights['missing_required_fields']
            assert 'profile.current_BTC_SOL_signal_sessions' in rights['missing_required_fields']
            assert 'profile.episode.btc_deferred_right_touched' in rights['missing_required_fields']
            assert rights['examples'][0]['final_parent_H_scope']=='FINAL_ENTRY_SNAPSHOT_NOT_PER_ADMISSION_REMAINING_BUDGET'
            db.close()
        assert not any(name.startswith('nautilus_trader') for name in sys.modules)
        return dict(status='METHOD_A_FINANCIAL_ADAPTER_PURE_PASS',engine_constructors=0,native_modules_imported=0,
            checks=['Decimal50_exact_fractional_tail_ES20_no_clipping','strict_native_cash_residual_zero_no_tolerance',
                'old_A0_gate_schema_rejected','prestrategy_native_cache_transition_not_TP_failure','before_matching_actual_missing_TP_failclosed',
                'disk_dedup_identical_native_ID_vs_conflict','Money_string_numeric_currency_exact','P1_actual_native_geometry_both_sides_positive_ordered_and_negative_cases',
                'P1_native_instrument_exit_side_strategy_current_ACK_price_quantity',
                'P1_conflicting_reference_stays_unknown','old_SOL_missing_current_budget_session_facts_UNKNOWN_no_reconstruction'],
            actual_P0_financial_results='NOT_READ_BY_IMPLEMENTATION_OR_UNIT_PROOF')
    finally:builtins.__import__=original
