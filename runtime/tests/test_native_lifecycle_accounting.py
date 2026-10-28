"""Two genuine close/reopen lifecycles under one native NETTING position ID."""
from decimal import Decimal as D
import json
import pytest
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType,OmsType,OrderSide,TimeInForce
from nautilus_trader.model.objects import Money
from coinmaster.research.native_fixture import SIM,BTC_PERP
from coinmaster.research.native_accounting import native_position_lifecycles
from test_native_c1_funding_observer import NativeCapabilityProbe
from test_native_episode_risk import tick,run_ticks

@pytest.mark.parametrize('side',[1,-1])
def test_all_closed_lifecycles_and_duplicate_snapshot_are_native_cash_complete(tmp_path,side):
 e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
 e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
  starting_balances=[Money(100000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1))
 e.add_instrument(BTC_PERP);s=NativeCapabilityProbe();e.add_strategy(s)
 try:
  run_ticks(e,[tick(BTC_PERP,1)])
  for cycle in range(2):
   ns=10+cycle*10;entry=OrderSide.BUY if side==1 else OrderSide.SELL;exit=OrderSide.SELL if side==1 else OrderSide.BUY
   s.submit_order(s.order_factory.market(BTC_PERP.id,entry,BTC_PERP.make_qty(D(10)),time_in_force=TimeInForce.IOC))
   run_ticks(e,[tick(BTC_PERP,ns,'100'),tick(BTC_PERP,ns+1,'100')])
   s.submit_order(s.order_factory.market(BTC_PERP.id,exit,BTC_PERP.make_qty(D(10)),time_in_force=TimeInForce.IOC,reduce_only=True))
   price=str(110+cycle*10 if side==1 else 90-cycle*10)
   run_ticks(e,[tick(BTC_PERP,ns+2,price),tick(BTC_PERP,ns+3,price)])
  e.end()
  report=native_position_lifecycles(e.cache)
  cash=e.cache.account_for_venue(SIM).balance_total().as_decimal()
  assert len(e.cache.positions())==1 and len(e.cache.position_snapshots())==1
  assert report['unique_lifecycles']==2 and report['native_snapshot_count']==1 and not report['unknown']
  assert len({r['position_id'] for r in report['positions']})==1
  assert len({(r['opened_ns'],r['closed_ns'],r['opening_order_id']) for r in report['positions']})==2
  total=sum((D(r['realized_pnl']) for r in report['positions']),D(0))
  old_total=sum((p.realized_pnl.as_decimal() for p in e.cache.positions()),D(0))
  assert cash-D(100000)-total==0
  assert cash-D(100000)-old_total!=0 # Old last-position-only exporter drops first life.
  # A native duplicate snapshot of the final current closed lifecycle must not double-count it.
  e.cache.snapshot_position(e.cache.positions()[0])
  duplicate=native_position_lifecycles(e.cache)
  assert duplicate['unique_lifecycles']==2 and duplicate['duplicate_native_copies']==1
  assert sum((D(r['realized_pnl']) for r in duplicate['positions']),D(0))==total
  (tmp_path/('lifecycle-proof-'+str(side)+'.json')).write_text(json.dumps(dict(cash=str(cash),old_last_only_total=str(old_total),all_native_lifecycle_total=str(total),report=duplicate),indent=2))
 finally:e.dispose()
