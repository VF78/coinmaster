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
