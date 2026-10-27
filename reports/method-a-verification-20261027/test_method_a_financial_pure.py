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
        assert not any(name.startswith('nautilus_trader') for name in sys.modules)
        return dict(status='METHOD_A_FINANCIAL_ADAPTER_PURE_PASS',engine_constructors=0,native_modules_imported=0,
            checks=['Decimal50_exact_fractional_tail_ES20_no_clipping','strict_native_cash_residual_zero_no_tolerance',
                'old_A0_gate_schema_rejected','prestrategy_native_cache_transition_not_TP_failure','before_matching_actual_missing_TP_failclosed',
                'disk_dedup_identical_native_ID_vs_conflict','Money_string_numeric_currency_exact'],
            actual_P0_financial_results='NOT_READ_BY_IMPLEMENTATION_OR_UNIT_PROOF')
    finally:builtins.__import__=original
