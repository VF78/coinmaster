"""Stock hook ordering/native object-copy proof, including exact signed funding."""
from decimal import Decimal as D
from types import SimpleNamespace
import gzip,json
import pytest
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.objects import Money
from coinmaster.research.native_fixture import SIM,BTC_PERP,SOL_PERP,FundingInstruction,PerpetualFundingModule
from coinmaster.ledger.journal import NativeEventJournal
from coinmaster.research.paired_observer import CommittedNativeObserver
from test_native_paired_prerequisites import NativeCapabilityProbe
from test_native_episode_risk import tick,run_ticks


def run_observed(tmp_path, enabled=True):
    journal=NativeEventJournal(str(tmp_path/'funding.sqlite'))
    funds=(FundingInstruction('btc-pay',BTC_PERP.id,D('.001'),120_000_000_000,D(100),'venue_mark'),
           FundingInstruction('sol-receive',SOL_PERP.id,D('.002'),120_000_000_000,D(100),'venue_mark'))
    modules=[PerpetualFundingModule(funds,journal)]
    observer=CommittedNativeObserver(tmp_path/'events.jsonl.gz',D(1000000),(BTC_PERP,SOL_PERP),journal) if enabled else None
    if observer:modules.append(observer)
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(1000000,SOL_PERP.quote_currency)],base_currency=SOL_PERP.quote_currency,
        default_leverage=D(1),liquidity_consumption=True,bar_execution=False,modules=modules)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP)
    s=NativeCapabilityProbe();e.add_strategy(s)
    if observer:
        observer.set_week([SimpleNamespace(open_time_ms=x,btc_mark={'close':'100'},sol_mark={'close':'100'}) for x in (0,60000,120000)])
    try:
        run_ticks(e,[tick(BTC_PERP,60_000_000_000),tick(SOL_PERP,60_000_000_000)])
        for inst,side in ((BTC_PERP,OrderSide.BUY),(SOL_PERP,OrderSide.SELL)):
            s.submit_order(s.order_factory.market(inst.id,side,inst.make_qty(D(10)),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(BTC_PERP,60_000_000_001),tick(SOL_PERP,60_000_000_001)])
        run_ticks(e,[tick(BTC_PERP,120_000_000_000),tick(SOL_PERP,120_000_000_000)])
        for inst,side in ((BTC_PERP,OrderSide.SELL),(SOL_PERP,OrderSide.BUY)):
            s.submit_order(s.order_factory.market(inst.id,side,inst.make_qty(D(10)),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,120_000_000_001),tick(SOL_PERP,120_000_000_001),tick(BTC_PERP,180_000_000_000),tick(SOL_PERP,180_000_000_000)])
        e.end()
        report=observer.finish_after_engine_end(180_000_000_000) if observer else None
        actual=str(e.cache.account_for_venue(SIM).balance_total().as_decimal())
        return dict(report=report,cash=actual,funding=journal.funding_cash_audit(),
            fills=[r for r in s.receipts if r['kind']=='FILL'])
    finally:
        if observer:observer.close()
        e.dispose();journal.close()


def test_stock_postfill_account_position_epochs_funding_and_on_off_parity(tmp_path):
    ondir=tmp_path/'on';offdir=tmp_path/'off';ondir.mkdir();offdir.mkdir()
    on=run_observed(ondir);off=run_observed(offdir,False)
    assert on['cash']==off['cash']
    assert on['funding']==off['funding']
    assert on['fills']==off['fills']
    assert on['report']['native_unique_fills']==4
    assert on['report']['native_funding_transitions']==2,on['report']
    assert on['report']['terminal_actual_cash']==on['cash']
    assert on['report']['status']=='PASS',on['report']
    rows=[json.loads(x) for x in gzip.open(ondir/'events.jsonl.gz','rt')]
    post=[r for r in rows if r['kind']=='POST_FILL_COMMITTED_NATIVE']
    assert len(post)==4
    assert len(post[0]['positions'])==1 and len(post[1]['positions'])==2
    assert not post[-1]['positions']
    assert [r['sequence'] for r in rows]==list(range(1,len(rows)+1))
    assert json.loads(json.dumps(on['report']))==on['report']


def test_joined_paired_owner_observer_on_off_native_domain_order_trace_parity(tmp_path):
    from test_native_paired_prefix import native_setup,covered
    import hashlib
    traces=[];proof=None
    for enabled in (False,True):
        folder=tmp_path/("on" if enabled else "off");folder.mkdir()
        observer=CommittedNativeObserver(folder/"events.jsonl.gz",D(10000),(BTC_PERP,SOL_PERP)) if enabled else None
        if observer:
            observer.set_week([SimpleNamespace(open_time_ms=x,btc_mark={'close':'100'},sol_mark={'close':'100'}) for x in (-60000,0,60000,120000)])
        s,e,ep=native_setup(a=".2",modules=(observer,) if observer else ())
        try:
            t=covered(s,e)
            for dt in range(3):
                run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,'99')])
            s._begin_forced_close('TEST_NATIVE_TERMINAL')
            for dt in range(3,8):
                run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt)])
            e.end()
            if observer:proof=observer.finish_after_engine_end(t+7)
            orders=[dict(id=str(o.client_order_id),type=o.order_type.name,side=o.side.name,
                quantity=str(o.quantity),filled=str(o.filled_qty),status=o.status.name,
                price=str(getattr(o,'price',None)),trigger=str(getattr(o,'trigger_price',None)),
                reduce_only=o.is_reduce_only) for o in e.cache.orders()]
            domain=dict(btc_open=ep.btc_open_qty,btc_initial=ep.btc_initial_qty,
                entry_exact=str(ep.btc_entry_qty_exact),entry_notional=str(ep.btc_entry_notional_exact),
                target_lots=ep.btc_tp_target_lots,filled_lots=ep.btc_tp_filled_lots,
                consumed=sorted(ep.btc_filled_tps),sol_qty=ep.sol_qty,
                current_episode=s._domain.episode.id if s._domain.episode else None)
            traces.append(dict(orders=orders,domain=domain,fills=s.fill_audit,
                paired=s._pair_report(),cash=str(e.cache.account_for_venue(SIM).balance_total().as_decimal())))
            assert s._pair is None and not s._pair_work()
            assert not e.cache.positions_open() and not e.cache.orders_open() and not e.cache.orders_inflight()
        finally:
            if observer:observer.close()
            e.dispose()
    assert traces[0]==traces[1]
    assert proof['status']=='PASS',proof
    assert proof['native_unique_fills']==len(traces[1]['fills'])
    assert proof['terminal_actual_cash']==traces[1]['cash']
    receipt=dict(status='PASS',native_economic_trace_sha256=hashlib.sha256(json.dumps(traces[0],sort_keys=True).encode()).hexdigest(),
        native_orders=len(traces[0]['orders']),native_fills=len(traces[0]['fills']),
        observer=proof,parity='EXACT_NATIVE_PARENT_DOMAIN_ORDERS_FILLS_COMMISSIONS_TERMINAL_CASH')
    (tmp_path/'joined-paired-observer-parity.json').write_text(json.dumps(receipt,indent=2))
